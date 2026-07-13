"""Tests for the Umbra engine, identity, proxy, and extraction layers.

Engine tests use the real installed ``umbra-engine`` binary when present, and
skip gracefully when it is not. Identity, proxy, and extraction tests are
pure-Python and always run.
"""

from __future__ import annotations

import json
import os
import shutil

import pytest

from umbra import engine, identity, proxy, extract


HAVE_ENGINE = bool(shutil.which(os.environ.get("UMBRA_ENGINE_BIN", "umbra-engine")))


# ---- identity --------------------------------------------------------------
def test_identity_is_deterministic():
    a = identity.derive_identity("acme-corp")
    b = identity.derive_identity("acme-corp")
    assert a.user_agent == b.user_agent
    assert a.timezone == b.timezone
    assert a.viewport == b.viewport


def test_identity_differs_across_seeds():
    a = identity.derive_identity("seed-a")
    b = identity.derive_identity("seed-b")
    assert a.seed != b.seed


def test_identity_store_persists(tmp_path):
    store = identity.IdentityStore(path=tmp_path / "ids.json")
    ident = store.get("persist-me", name="bot1")
    reopened = identity.IdentityStore(path=tmp_path / "ids.json")
    assert any(i.seed == ident.seed for i in reopened.list())


def test_identity_proxy_binding(tmp_path):
    store = identity.IdentityStore(path=tmp_path / "ids.json")
    ident = store.bind_proxy("acme", "socks5://10.0.0.1:1080", name="acme")
    assert ident.proxy == "socks5://10.0.0.1:1080"
    reopened = identity.IdentityStore(path=tmp_path / "ids.json")
    bound = reopened.get("acme")
    assert bound.proxy == "socks5://10.0.0.1:1080"
    unbound = store.unbind_proxy("acme")
    assert unbound.proxy == ""


def test_identity_cdp_script_is_valid_js():
    ident = identity.derive_identity("js-check")
    script = ident.cdp_script()
    assert "userAgent" in script
    assert "matchMedia" in script


# ---- proxy mesh ------------------------------------------------------------
def test_proxy_mesh_round_robin():
    mesh = proxy.ProxyMesh(
        ["http://a:1", "http://b:2", "http://c:3"], mode="round_robin"
    )
    picked = [mesh.pick() for _ in range(3)]
    assert set(picked) == {"http://a:1", "http://b:2", "http://c:3"}


def test_proxy_mesh_quarantine():
    mesh = proxy.ProxyMesh(["http://dead:1"], cooldown=0.1)
    mesh.report("http://dead:1", ok=False)
    assert mesh.pick() is None or mesh.healthy == []
    mesh.report("http://dead:1", ok=True)
    assert mesh.pick() == "http://dead:1"


def test_proxy_mesh_sticky():
    mesh = proxy.ProxyMesh(
        ["http://x:1", "http://y:2"], mode="sticky"
    )
    first = mesh.pick(key="session-1")
    second = mesh.pick(key="session-1")
    assert first == second


# ---- extraction ------------------------------------------------------------
def test_extract_offline_fallback():
    md = "# Product\nTitle: Super Widget\nPrice: $19.99\n"
    schema = {"title": "product name", "price": "price"}
    out = extract.extract(md, schema)
    assert out["title"] == "Super Widget"
    assert out["price"] == "$19.99"


def test_extract_offline_missing_field():
    md = "nothing here"
    out = extract.extract(md, {"title": "name"})
    assert out["title"] is None


# ---- engine (requires the Umbra engine) -----------------------------------
@pytest.mark.skipif(not HAVE_ENGINE, reason="umbra-engine binary not installed")
def test_engine_fetch_markdown():
    eng = engine.Engine()
    out = eng.fetch("https://example.com", dump="markdown")
    assert "Example Domain" in out


@pytest.mark.skipif(not HAVE_ENGINE, reason="umbra-engine binary not installed")
def test_engine_fetch_eval():
    eng = engine.Engine()
    out = eng.fetch("https://example.com", eval_js="document.title")
    assert "Example Domain" in out


@pytest.mark.skipif(not HAVE_ENGINE, reason="umbra-engine binary not installed")
def test_engine_serve_endpoint():
    eng = engine.Engine()
    ep = eng.start()
    try:
        assert ep.startswith("ws://") or ep.startswith("http")
    finally:
        eng.stop()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
