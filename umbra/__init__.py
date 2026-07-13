"""Umbra — the shadow engine.

An AI-native stealth browser for agents, built around a CDP browser engine.
Umbra adds three capabilities on top of the engine core:

  * persistent, deterministic identities (consistent fingerprints across runs)
  * a proxy mesh (pool, rotation, health checks, failover)
  * an LLM-grounded extraction layer (turn rendered markdown into structure)

The engine layer talks to the Umbra engine via its Chrome DevTools Protocol
server and its CLI, with no third-party Python dependency required at runtime.
"""

from __future__ import annotations

__version__ = "0.1.0"
