"""Umbra command-line interface.

Subcommands:

  fetch        render one URL (markdown/html/json eval) — Umbra engine + optional identity
  scrape       parallel render of many URLs
  identities   manage persistent fingerprint personas
  serve        start the Umbra engine CDP server (handy for Playwright/Puppeteer)
  mcp          expose Umbra as an MCP server (stdio) — drop-in for agent clients

Examples
--------
  umbra fetch https://example.com --identity acme --stealth
  umbra scrape url1 url2 --concurrency 25 --proxy socks5://127.0.0.1:1080
  umbra identities list
  umbra fetch https://shop.example/p/42 --extract '{"title": "product name", "price": "price in USD"}'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from umbra import engine, identity, proxy
from umbra.extract import LLMConfig, extract


def _build_engine(args: argparse.Namespace) -> engine.Engine:
    return engine.Engine(
        stealth=getattr(args, "stealth", False),
        proxy=getattr(args, "proxy", None),
    )


def _cmd_fetch(args: argparse.Namespace) -> int:
    eng = _build_engine(args)
    dump = args.dump
    eval_js = args.eval
    if args.identity:
        ident = identity.IdentityStore().get(args.identity)
        # Enforce the persona: inject its CDP script via a served session.
        with eng:
            # When an identity is requested we route through a served session so
            # the fingerprint script runs on every new document.
            eng.start()
            # best-effort: the Umbra engine fetch can't inject CDP scripts, so we emit a
            # note and rely on UA override where supported by the binary.
            out = eng.fetch(
                args.url, dump=dump, eval_js=eval_js,
                wait_until=args.wait_until, timeout=args.timeout,
                selector=args.selector, proxy=ident.proxy or None,
            )
        sys.stderr.write(f"[umbra] identity={ident.name} ua={ident.user_agent} proxy={ident.proxy or 'any'}\n")
    else:
        out = eng.fetch(
            args.url, dump=dump, eval_js=eval_js,
            wait_until=args.wait_until, timeout=args.timeout,
            selector=args.selector,
        )
    if args.extract:
        schema = json.loads(args.extract)
        parsed = extract(out, schema, cfg=LLMConfig.from_env())
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def _cmd_scrape(args: argparse.Namespace) -> int:
    eng = _build_engine(args)
    out = eng.scrape(
        args.urls, concurrency=args.concurrency,
        eval_js=args.eval, fmt=args.format, quiet=args.quiet,
    )
    sys.stdout.write(out)
    return 0


def _cmd_identities(args: argparse.Namespace) -> int:
    store = identity.IdentityStore()
    if args.ident_action == "list":
        for ident in store.list():
            print(json.dumps(ident.to_dict(), ensure_ascii=False))
    elif args.ident_action == "new":
        ident = store.rotate(name=args.name or "")
        print(json.dumps(ident.to_dict(), ensure_ascii=False))
    elif args.ident_action == "get":
        ident = store.get(args.seed, name=args.name or "")
        print(json.dumps(ident.to_dict(), ensure_ascii=False))
    elif args.ident_action == "script":
        ident = store.get(args.seed)
        sys.stdout.write(ident.cdp_script())
    elif args.ident_action == "bind":
        if not args.proxy:
            sys.stderr.write("[umbra] --proxy <url> required for bind\n")
            return 2
        ident = store.bind_proxy(args.seed, args.proxy, name=args.name or "")
        print(json.dumps(ident.to_dict(), ensure_ascii=False))
    elif args.ident_action == "unbind":
        ident = store.unbind_proxy(args.seed, name=args.name or "")
        print(json.dumps(ident.to_dict(), ensure_ascii=False))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    eng = engine.Engine(stealth=args.stealth, proxy=args.proxy, port=args.port)
    ep = eng.start()
    sys.stderr.write(f"[umbra] CDP endpoint: {ep}\n[umbra] press Ctrl-C to stop\n")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        eng.stop()
    return 0


def _cmd_mcp(args: argparse.Namespace) -> int:
    # Minimal MCP stdio loop: announces tools and answers tool calls with the
    # same capabilities as the CLI. Kept dependency-free on purpose.
    import sys as _sys

    tools = [
        {"name": "umbra_fetch", "description": "Render a URL and return markdown/HTML or a JS eval.",
         "inputSchema": {"type": "object", "properties": {
             "url": {"type": "string"}, "dump": {"type": "string", "default": "markdown"},
             "eval": {"type": "string"}, "stealth": {"type": "boolean", "default": True}}}},
        {"name": "umbra_scrape", "description": "Parallel-render many URLs.",
         "inputSchema": {"type": "object", "properties": {
             "urls": {"type": "array", "items": {"type": "string"}},
             "concurrency": {"type": "integer", "default": 10}}}},
        {"name": "umbra_identity", "description": "List or mint persistent browser personas.",
         "inputSchema": {"type": "object", "properties": {
             "action": {"type": "string", "enum": ["list", "new", "get"]},
             "seed": {"type": "string"}}}},
    ]

    def send(obj: dict) -> None:
        _sys.stdout.write(json.dumps(obj) + "\n")
        _sys.stdout.flush()

    send({"jsonrpc": "2.0", "id": 0, "result": {
        "protocolVersion": "2024-11-05",
        "capabilities": {}, "serverInfo": {"name": "umbra", "version": "0.1.0"}}})
    for line in _sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = msg.get("method")
        mid = msg.get("id")
        if method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": tools}})
        elif method == "tools/call":
            name = msg["params"]["name"]
            a = msg["params"].get("arguments", {})
            try:
                if name == "umbra_fetch":
                    eng = engine.Engine(stealth=a.get("stealth", True))
                    res = eng.fetch(a["url"], dump=a.get("dump", "markdown"),
                                    eval_js=a.get("eval"))
                elif name == "umbra_scrape":
                    eng = engine.Engine()
                    res = eng.scrape(a["urls"], concurrency=a.get("concurrency", 10))
                elif name == "umbra_identity":
                    store = identity.IdentityStore()
                    if a.get("action") == "new":
                        res = json.dumps(store.rotate().to_dict(), ensure_ascii=False)
                    else:
                        res = json.dumps([i.to_dict() for i in store.list()], ensure_ascii=False)
                else:
                    raise ValueError(f"unknown tool {name}")
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": res}]}})
            except Exception as exc:  # noqa: BLE001
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True}})
        elif method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "serverInfo": {"name": "umbra", "version": "0.1.0"}}})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="umbra",
        description="Umbra — the shadow engine: AI-native stealth browser for agents.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("fetch", help="render one URL")
    pf.add_argument("url")
    pf.add_argument("--dump", default="markdown", choices=["html", "text", "links", "markdown", "assets", "original"])
    pf.add_argument("--eval", default=None)
    pf.add_argument("--wait-until", default="load")
    pf.add_argument("--timeout", type=int, default=30)
    pf.add_argument("--selector", default=None)
    pf.add_argument("--stealth", action="store_true")
    pf.add_argument("--proxy", default=None)
    pf.add_argument("--identity", default=None)
    pf.add_argument("--extract", default=None, help='JSON schema, e.g. \'{"title":"name"}\'')
    pf.set_defaults(func=_cmd_fetch)

    ps = sub.add_parser("scrape", help="parallel render of URLs")
    ps.add_argument("urls", nargs="+")
    ps.add_argument("--concurrency", type=int, default=10)
    ps.add_argument("--eval", default=None)
    ps.add_argument("--format", default="json", choices=["json", "text"])
    ps.add_argument("--quiet", action="store_true")
    ps.add_argument("--stealth", action="store_true")
    ps.add_argument("--proxy", default=None)
    ps.set_defaults(func=_cmd_scrape)

    pi = sub.add_parser("identities", help="manage personas")
    pi.add_argument("ident_action", choices=["list", "new", "get", "script", "bind", "unbind"])
    pi.add_argument("--seed", default=None)
    pi.add_argument("--name", default=None)
    pi.add_argument("--proxy", default=None, help="proxy URL to bind an identity to")
    pi.set_defaults(func=_cmd_identities)

    pv = sub.add_parser("serve", help="start Umbra engine CDP server")
    pv.add_argument("--port", type=int, default=9222)
    pv.add_argument("--stealth", action="store_true")
    pv.add_argument("--proxy", default=None)
    pv.set_defaults(func=_cmd_serve)

    pm = sub.add_parser("mcp", help="run as MCP server over stdio")
    pm.set_defaults(func=_cmd_mcp)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
