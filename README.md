# 🌑 Umbra — the shadow engine

[![CI](https://github.com/Celebez/umbra/actions/workflows/tests.yml/badge.svg)](https://github.com/Celebez/umbra/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/badge/PyPI-ready-21e99a?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/umbra/)
[![License](https://img.shields.io/badge/license-Apache--2.0-FFD166?style=flat-square)](LICENSE)

> An AI-native stealth browser for agents. Persistent identities, a proxy mesh,
> and LLM-grounded extraction — over a CDP browser engine.

Umbra is a lightweight, anti-detect headless browser that speaks the Chrome
DevTools Protocol, with three layers baked in so it can grow into a real agent
platform instead of just a scraper:

| Layer | What Umbra adds | Why it matters |
|-------|------------------|----------------|
| 🪪 **Identity** | Deterministic, persistent personas (fingerprint = f(seed)). Survives restarts, reusable across sessions. | Real anti-detection needs a *consistent* fingerprint, not fresh-random every run. |
| 🕸️ **Proxy mesh** | Pool of upstreams, round-robin / sticky rotation, quarantine + health re-check, residential preference. | One dead proxy should never break a scrape; identities should ride stable egress. |
| 🧠 **Extraction** | LLM-grounded structured extraction (OpenAI-compatible API), offline rule-based fallback. | Describe the shape you want; get JSON. No brittle per-site selectors. |

Zero third-party runtime dependencies — Umbra drives the bundled `umbra-engine`
binary (a Rust + V8 CDP browser) and adds the layers in pure Python stdlib.

---

## Install

One-liner (installs the engine binary + the `umbra` package, no public exposure):

```bash
curl -fsSL https://raw.githubusercontent.com/Celebez/umbra/main/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/Celebez/umbra && cd umbra
pip install -e ".[test]"
# engine binary (the CDP core) — download once:
curl -fsSL https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-x86_64-linux.tar.gz -o e.tar.gz
tar xzf e.tar.gz && install obscura ~/.local/bin/umbra-engine
```

> **Network binding:** Umbra binds **127.0.0.1 only** — it is never exposed on a
> public IP/port. The `serve` command, `docker-compose.yml`, and the systemd
> unit all default to loopback (`127.0.0.1:9222`). To expose it on a LAN you
> must deliberately change the bind address; do not do this by default.

## Quick start

```bash
# Render a page as markdown (goes through the Umbra engine, stealth on by default)
umbra fetch https://example.com --stealth

# Extract structured data with an LLM (set UMBRA_LLM_BASE_URL + UMBRA_LLM_MODEL)
umbra fetch https://shop.example/p/42 \
  --extract '{"title": "product name", "price": "price in USD"}'

# Mint and reuse a persistent identity
umbra identities new --name acme
umbra fetch https://example.com --identity acme

# Parallel scrape through a proxy mesh
umbra scrape url1 url2 url3 --concurrency 25 --proxy socks5://127.0.0.1:1080

# Expose Umbra to an agent as an MCP server (stdio)
umbra mcp
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        umbra CLI / MCP                        │
├───────────────┬───────────────────┬──────────────────────────┤
│  identity.py  │     proxy.py      │        extract.py         │
│  personas     │  mesh + rotation  │  LLM-grounded → JSON      │
├───────────────┴───────────────────┴──────────────────────────┤
│                       engine.py                               │
│        wraps `umbra-engine serve` / `umbra-engine fetch` (CDP) │
└───────────────────────────┬───────────────────────────────────┘
                            │ Chrome DevTools Protocol
                    ┌───────▼────────┐
                    │  umbra-engine  │  Rust, V8, ~30 MB RAM
                    │  (stealth)     │
                    └────────────────┘
```

Every component is a small, swapable module:

- `umbra.engine` — spawn/drive `umbra-engine` (fetch, scrape, serve, CDP endpoint).
- `umbra.identity` — `Identity` (deterministic from seed) + `IdentityStore` (JSON on disk).
- `umbra.proxy` — `ProxyMesh` (round-robin / sticky, quarantine, residential bias).
- `umbra.extract` — `extract(markdown, schema, cfg)` with offline fallback.

## Deploy

Umbra ships as a CDP service. Pick one:

**Docker (compose)**

```bash
docker compose up -d umbra-cdp      # long-lived CDP on :9222
docker compose run --rm umbra fetch https://example.com --stealth   # one-off
```

**systemd (host)**

```bash
sudo install -d /opt/umbra && sudo cp -r . /opt/umbra/
sudo install -m 644 umbra.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now umbra
```

**Container image** is published to `ghcr.io/celebez/umbra` on tags (`v*`) via
the `deploy` workflow — `docker run ghcr.io/celebez/umbra serve --port 9222`.

## Configuration (env vars)

| Var | Meaning |
|-----|---------|
| `UMBRA_ENGINE_BIN` | Path to the `umbra-engine` binary. |
| `UMBRA_LLM_BASE_URL` | OpenAI-compatible chat-completions base URL (enables AI extraction). |
| `UMBRA_LLM_API_KEY` | API key for that endpoint. |
| `UMBRA_LLM_MODEL` | Model name. |
| `UMBRA_STARTUP_TIMEOUT` | Seconds to wait for the CDP server (default 15). |

## Roadmap (where it grows)

- [x] **Identity ↔ proxy binding** — pin a persona to a residential egress IP (persisted).
- [ ] **Self-evolving personas** — drift fingerprints within plausible envelopes to dodge ML bot-detection.
- [ ] **Captcha solver hook** — pluggable solver backend behind the extraction layer.
- [ ] **Session recorder/replay** — persist a full CDP session and replay it.
- [ ] **Distributed mesh** — share a proxy/identity pool across agent workers.

## License

Apache-2.0.
