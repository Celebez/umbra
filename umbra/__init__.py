"""Umbra — the shadow engine.

An AI-native stealth browser for agents, layered on top of the Obscura
headless-browser CDP core. Umbra adds three capabilities Obscura does not
ship with out of the box:

  * persistent, deterministic identities (consistent fingerprints across runs)
  * a proxy mesh (pool, rotation, health checks, failover)
  * an LLM-grounded extraction layer (turn rendered markdown into structure)

The engine layer talks to Obscura via its Chrome DevTools Protocol server and
its CLI, with no third-party Python dependency required at runtime.
"""

from __future__ import annotations

__version__ = "0.1.0"
