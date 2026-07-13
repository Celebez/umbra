# 🌑 Umbra — the shadow engine

[![CI](https://github.com/Celebez/umbra/actions/workflows/tests.yml/badge.svg)](https://github.com/Celebez/umbra/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/badge/PyPI-ready-21e99a?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/umbra/)
[![License](https://img.shields.io/badge/license-Apache--2.0-FFD166?style=flat-square)](LICENSE)

> An AI-native stealth browser for agents. Persistent identities, a proxy mesh,
> and LLM-grounded extraction — over a CDP browser engine.

![Umbra hero](assets/hero.png)

Umbra is a lightweight, anti-detect headless browser that speaks the Chrome
DevTools Protocol. Everything **runs locally on your machine** — there is no
central server, no account, and no callback to anyone's infrastructure. You
install it, you run it.

![Umbra demo](assets/demo.gif)

## Why Umbra

| Layer | What Umbra adds | Why it matters |
|-------|------------------|----------------|
| 🪪 **Identity** | Deterministic, persistent personas (fingerprint = f(seed)). Survives restarts, reusable across sessions. | Real anti-detection needs a *consistent* fingerprint, not fresh-random every run. |
| 🕸️ **Proxy mesh** | Pool of upstreams, round-robin / sticky rotation, quarantine + health re-check, residential preference. | One dead proxy should never break a scrape; identities should ride stable egress. |
| 🧠 **Extraction** | LLM-grounded structured extraction (OpenAI-compatible API), offline rule-based fallback. | Describe the shape you want; get JSON. No brittle per-site selectors. |

Zero third-party runtime dependencies — Umbra drives the bundled `umbra-engine`
binary (a Rust + V8 CDP browser) and adds the layers in pure Python stdlib.

> **Privacy / network note:** Umbra binds **127.0.0.1 only**. The `serve`
> command, `docker-compose.yml`, and the systemd unit all default to loopback
> (`127.0.0.1:9222`). It never opens a port on a public IP. To expose it on a
> LAN you must deliberately change the bind address.

---

## 📦 Install

### Option A — one-liner (recommended)

Installs the engine binary (`umbra-engine`) + the `umbra` package. Local only.

```bash
curl -fsSL https://raw.githubusercontent.com/Celebez/umbra/main/install.sh | bash
```

### Option B — from source

```bash
git clone https://github.com/Celebez/umbra && cd umbra
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# the CDP engine core (download once), then tell Umbra where it is:
curl -fsSL https://github.com/Celebez/umbra/releases/latest/download/umbra-engine-x86_64-linux.tar.gz -o e.tar.gz
tar xzf e.tar.gz && install umbra-engine ~/.local/bin/umbra-engine
export UMBRA_ENGINE_BIN=~/.local/bin/umbra-engine
```

### Supported platforms

| OS | Arch | Engine asset |
|----|------|--------------|
| Linux | x86_64 | `umbra-engine-x86_64-linux.tar.gz` |
| macOS | x86_64 | `umbra-engine-x86_64-macos.tar.gz` |
| macOS | aarch64 | `umbra-engine-aarch64-macos.tar.gz` |

---

## 🚀 Quick start

```bash
# 1. Render a page as markdown (stealth on by default)
umbra fetch https://example.com --stealth

# 2. Choose the output shape
umbra fetch https://example.com --dump text
umbra fetch https://example.com --dump html
umbra fetch https://example.com --dump links
umbra fetch https://example.com --dump assets

# 3. Run JavaScript in the page context
umbra fetch https://example.com --eval "document.title"

# 4. Wait for a selector / load state
umbra fetch https://example.com --wait-until networkidle0 --selector "main"

# 5. Mint and reuse a persistent identity
umbra identities new --name acme
umbra fetch https://example.com --identity acme

# 6. Parallel scrape through a proxy mesh
umbra scrape url1 url2 url3 --concurrency 25 --proxy socks5://127.0.0.1:1080

# 7. Expose Umbra to an agent as an MCP server (stdio)
umbra mcp
```

---

## 🪪 Identities (personas)

A persona is deterministic from a seed — same seed, same fingerprint, every run.

```bash
# create (random seed)
umbra identities new --name acme

# create with a fixed seed (reproducible fingerprint)
umbra identities new --seed 1ea98808b65db550 --name acme

# list stored identities
umbra identities list

# inspect one
umbra identities get --name acme

# export the browser-fingerprint CDP bootstrap script
umbra identities script --seed 1ea98808b65db550

# bind a persona to a residential egress proxy (anti-correlation)
umbra identities bind --seed 1ea98808b65db550 --proxy socks5://user:pass@proxy:1080

# unbind
umbra identities unbind --seed 1ea98808b65db550
```

Stored as JSON in `~/.config/umbra/identities.json` (override with
`UMBRA_IDENTITIES_PATH`).

---

## 🧠 Extraction (LLM-grounded)

Set your OpenAI-compatible endpoint once, then ask for structured JSON:

```bash
export UMBRA_LLM_BASE_URL=https://api.openai.com/v1
export UMBRA_LLM_API_KEY=sk-...
export UMBRA_LLM_MODEL=gpt-4o-mini

umbra fetch https://shop.example/p/42 \
  --extract '{"title": "product name", "price": "price in USD", "in_stock": "boolean"}'
```

No API key? `--extract` falls back to a deterministic offline rule pass that
returns whatever the page clearly contains.

---

## 🖥️ Serve (CDP endpoint for Playwright / Puppeteer)

```bash
umbra serve --port 9222 --stealth
# binds 127.0.0.1:9222 (local only)
```

Then point Playwright/Puppeteer at `http://127.0.0.1:9222`:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = b.new_page()
    page.goto("https://example.com")
```

---

## 🧩 CLI reference

```
umbra fetch <url> [--dump html|text|links|markdown|assets|original]
                 [--eval JS] [--wait-until STATE] [--selector SEL]
                 [--timeout S] [--stealth] [--proxy URL]
                 [--identity NAME] [--extract JSON]

umbra scrape <url...> [--concurrency N] [--eval JS] [--format json|text]
                      [--quiet] [--stealth] [--proxy URL]

umbra identities {list|new|get|script|bind|unbind}
                 [--seed S] [--name N] [--proxy URL]

umbra serve [--port 9222] [--stealth] [--proxy URL]
umbra mcp
```

Global flags: `--stealth`, `--proxy`, `--identity` are accepted before or after
the subcommand and apply to `fetch`, `scrape`, `serve`, and `mcp`.

---

## 🐳 Deploy (optional — self-host on your own box)

All bindings default to loopback. Nothing is exposed publicly.

**Docker Compose**

```bash
docker compose up -d umbra-cdp      # long-lived CDP on 127.0.0.1:9222
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

---

## ⚙️ Configuration (env vars)

| Var | Meaning |
|-----|---------|
| `UMBRA_ENGINE_BIN` | Path to the `umbra-engine` binary. |
| `UMBRA_IDENTITIES_PATH` | Where persona JSON is stored (default `~/.config/umbra/identities.json`). |
| `UMBRA_LLM_BASE_URL` | OpenAI-compatible chat-completions base URL (enables AI extraction). |
| `UMBRA_LLM_API_KEY` | API key for that endpoint. |
| `UMBRA_LLM_MODEL` | Model name. |
| `UMBRA_STARTUP_TIMEOUT` | Seconds to wait for the CDP server (default 15). |

---

## 🏗️ Architecture

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

Every component is a small, swappable module:

- `umbra.engine` — spawn/drive `umbra-engine` (fetch, scrape, serve, CDP endpoint).
- `umbra.identity` — `Identity` (deterministic from seed) + `IdentityStore` (JSON on disk).
- `umbra.proxy` — `ProxyMesh` (round-robin / sticky, quarantine, residential bias).
- `umbra.extract` — `extract(markdown, schema, cfg)` with offline fallback.

## Roadmap (where it grows)

- [x] **Identity ↔ proxy binding** — pin a persona to a residential egress IP (persisted).
- [ ] **Self-evolving personas** — drift fingerprints within plausible envelopes to dodge ML bot-detection.
- [ ] **Captcha solver hook** — pluggable solver backend behind the extraction layer.
- [ ] **Session recorder/replay** — persist a full CDP session and replay it.
- [ ] **Distributed mesh** — share a proxy/identity pool across agent workers.

## License

Apache-2.0.
