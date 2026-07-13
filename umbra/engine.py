"""Engine layer: drive the Obscura binary (fetch / serve) over CLI + CDP.

No third-party runtime dependency — we shell out to the ``obscura`` binary
exactly the way the official Hermes plugin does, and additionally expose the
CDP endpoint it serves for callers that want to drive it with Playwright /
Puppeteer.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import urllib.request


DEFAULT_STARTUP_TIMEOUT = float(os.environ.get("UMBRA_STARTUP_TIMEOUT", "15"))


class ObscuraNotFound(RuntimeError):
    """Raised when the obscura binary cannot be located."""


def find_binary() -> str:
    """Resolve the obscura binary from OBSCURA_BIN or PATH."""
    candidate = os.environ.get("OBSCURA_BIN") or "obscura"
    path = shutil.which(candidate)
    if path:
        return path
    if Path(candidate).is_absolute() and Path(candidate).exists():
        return candidate
    raise ObscuraNotFound(
        "obscura binary not found on PATH and OBSCURA_BIN is unset. "
        "Install it from https://github.com/h4ckf0r0day/obscura/releases "
        "or set OBSCURA_BIN to the binary path."
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _cdp_version(host: str, port: int, timeout: float) -> dict:
    url = f"http://{host}:{port}/json/version"
    deadline = time.time() + timeout
    last_err: Optional[Exception] = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001 - poll until it answers
            last_err = exc
            time.sleep(0.25)
    raise TimeoutError(f"obscura CDP server did not come up: {last_err}")


@dataclass
class Engine:
    """A handle to a running Obscura server (or a spawner for one)."""

    binary: str = ""
    host: str = "127.0.0.1"
    port: int = 0
    stealth: bool = False
    proxy: Optional[str] = None
    startup_timeout: float = DEFAULT_STARTUP_TIMEOUT
    _proc: Optional[subprocess.Popen] = None
    _endpoint: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.binary:
            self.binary = find_binary()
        if not self.port:
            self.port = _free_port()

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> str:
        """Spawn ``obscura serve`` and return its CDP websocket endpoint."""
        if self._proc is not None:
            return self._endpoint or ""
        cmd = [self.binary, "serve", "--port", str(self.port)]
        if self.stealth:
            cmd.append("--stealth")
        if self.proxy:
            cmd = [self.binary, "--proxy", self.proxy, "serve", "--port", str(self.port)]
            if self.stealth:
                cmd.append("--stealth")
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        version = _cdp_version(self.host, self.port, self.startup_timeout)
        self._endpoint = version.get("webSocketDebuggerUrl", "")
        return self._endpoint or ""

    def stop(self) -> None:
        if self._proc is None:
            return
        proc = self._proc
        self._proc = None
        self._endpoint = None
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    def __enter__(self) -> "Engine":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    @property
    def endpoint(self) -> str:
        if not self._endpoint:
            raise RuntimeError("engine not started; call start() first")
        return self._endpoint

    # -- single-page fetch ---------------------------------------------------
    def fetch(
        self,
        url: str,
        *,
        dump: str = "markdown",
        eval_js: Optional[str] = None,
        wait_until: str = "load",
        timeout: int = 30,
        selector: Optional[str] = None,
        proxy: Optional[str] = None,
        output: Optional[str] = None,
    ) -> str:
        """Render a page and return its dump or a JS-eval result as text."""
        cmd = [self.binary, "fetch", url, "--dump", dump,
               "--wait-until", wait_until, "--timeout", str(timeout)]
        if eval_js:
            cmd += ["--eval", eval_js]
        if selector:
            cmd += ["--selector", selector]
        if self.stealth:
            cmd.append("--stealth")
        proxy_url = proxy or self.proxy
        if proxy_url:
            cmd = [self.binary, "--proxy", proxy_url, "fetch", url,
                   "--dump", dump, "--wait-until", wait_until,
                   "--timeout", str(timeout)]
            if eval_js:
                cmd += ["--eval", eval_js]
            if selector:
                cmd += ["--selector", selector]
            if self.stealth:
                cmd.append("--stealth")
        if output:
            cmd += ["--output", output]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        if res.returncode != 0:
            raise RuntimeError(
                f"obscura fetch failed ({res.returncode}): {res.stderr.strip()}"
            )
        return (output and Path(output).read_text()) or res.stdout

    # -- parallel scrape -----------------------------------------------------
    def scrape(
        self,
        urls: Iterable[str],
        *,
        concurrency: int = 10,
        eval_js: Optional[str] = None,
        fmt: str = "json",
        quiet: bool = False,
        proxy: Optional[str] = None,
    ) -> str:
        url_list = list(urls)
        cmd = [self.binary, "scrape", *url_list,
               "--concurrency", str(concurrency), "--format", fmt]
        if eval_js:
            cmd += ["--eval", eval_js]
        if quiet:
            cmd.append("--quiet")
        proxy_url = proxy or self.proxy
        if proxy_url:
            cmd = [self.binary, "--proxy", proxy_url, "scrape", *url_list,
                   "--concurrency", str(concurrency), "--format", fmt]
            if eval_js:
                cmd += ["--eval", eval_js]
            if quiet:
                cmd.append("--quiet")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if res.returncode != 0:
            raise RuntimeError(
                f"obscura scrape failed ({res.returncode}): {res.stderr.strip()}"
            )
        return res.stdout
