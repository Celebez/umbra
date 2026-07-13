"""Proxy mesh: a pool of upstream proxies with rotation and health checks.

Umbra routes Obscura's ``--proxy`` flag through this layer. Two modes:

  * ``round_robin`` — every request takes the next healthy proxy.
  * ``sticky``      — a session/key is pinned to one proxy until it fails.

Unreachable proxies are quarantined and retried after a cooldown, so a dead
endpoint never silently breaks a scrape.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass
class Proxy:
    url: str
    healthy: bool = True
    _cooldown_until: float = 0.0
    failures: int = 0

    def available(self, now: float) -> bool:
        if self.healthy:
            return True
        if now >= self._cooldown_until:
            return True
        return False

    def mark_failure(self, cooldown: float = 60.0) -> None:
        self.failures += 1
        self.healthy = False
        self._cooldown_until = time.time() + cooldown

    def mark_success(self) -> None:
        self.healthy = True
        self.failures = 0
        self._cooldown_until = 0.0

    @property
    def is_residential(self) -> bool:
        return any(t in self.url for t in ("residential", "mobile", "isp"))


class ProxyMesh:
    def __init__(
        self,
        urls: Iterable[str] = (),
        mode: str = "round_robin",
        cooldown: float = 60.0,
    ) -> None:
        self.proxies = [Proxy(url=u) for u in urls]
        self.mode = mode
        self.cooldown = cooldown
        self._idx = 0
        self._sticky: dict[str, Proxy] = {}

    def add(self, url: str) -> None:
        if not any(p.url == url for p in self.proxies):
            self.proxies.append(Proxy(url=url))

    def load(self, urls: Iterable[str]) -> None:
        for u in urls:
            self.add(u)

    @property
    def healthy(self) -> list[Proxy]:
        now = time.time()
        return [p for p in self.proxies if p.available(now)]

    def _next(self) -> Optional[Proxy]:
        candidates = self.healthy
        if not candidates:
            # everything quarantined; allow re-check regardless of cooldown
            candidates = list(self.proxies)
        if not candidates:
            return None
        if self.mode == "round_robin":
            p = candidates[self._idx % len(candidates)]
            self._idx += 1
            return p
        # random pick among healthy to avoid thundering herd on one proxy
        import random
        return random.choice(candidates)

    def pick(self, key: Optional[str] = None) -> Optional[str]:
        """Return a proxy URL to use, honoring sticky mode."""
        if self.mode == "sticky" and key:
            bound = self._sticky.get(key)
            if bound and bound.available(time.time()):
                return bound.url
            chosen = self._next()
            if chosen is None:
                return None
            self._sticky[key] = chosen
            return chosen.url
        p = self._next()
        return p.url if p else None

    def report(self, url: str, ok: bool) -> None:
        for p in self.proxies:
            if p.url == url:
                if ok:
                    p.mark_success()
                else:
                    p.mark_failure(self.cooldown)
                return

    def prefer_residential(self) -> Optional[str]:
        res = [p for p in self.healthy if p.is_residential]
        if not res:
            return self.pick()
        import random
        return random.choice(res).url
