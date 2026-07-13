"""Persistent, deterministic browser identities ("personas").

An identity is a consistent fingerprint bundle: UA, platform, viewport,
timezone, locale, and a color/contrast/media preference set. The same seed
always yields the same identity, so a given persona looks identical across
sessions — which is what real anti-detection needs (Obscura randomizes per
session; Umbra makes that randomization *persistent and repeatable*).

We expose the identity as an override payload a caller can inject via
``addScriptToEvaluateOnNewDocument`` in the CDP layer, or simply as headers
for the fetch path.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# A realistic, modern Chrome/145 desktop matrix. Keep this list curated so
# generated fingerprints stay inside the "plausible real browser" envelope.
_CHROME_BUILD = "145.0.0.0"
_UA_TEMPLATES = [
    ("Windows NT 10.0; Win64; x64", "Win32", "1920x1080", "America/New_York", "en-US"),
    ("Windows NT 10.0; Win64; x64", "Win32", "1536x864", "America/Los_Angeles", "en-US"),
    ("Macintosh; Intel Mac OS X 10_15_7", "MacIntel", "1440x900", "America/Chicago", "en-US"),
    ("Macintosh; Intel Mac OS X 10_15_7", "MacIntel", "2560x1440", "Europe/London", "en-GB"),
    ("X11; Linux x86_64", "Linux x86_64", "1366x768", "Europe/Berlin", "de-DE"),
    ("X11; Linux x86_64", "Linux x86_64", "1920x1080", "Asia/Jakarta", "id-ID"),
]


@dataclass
class Identity:
    seed: str
    name: str = ""
    platform_string: str = ""
    platform_js: str = ""
    viewport: str = ""
    timezone: str = ""
    locale: str = ""
    user_agent: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def css_prefers(self) -> dict:
        rng = random.Random(self.seed + ":pref")
        return {
            "prefers_color_scheme": rng.choice(["light", "dark", "no-preference"]),
            "prefers_reduced_motion": rng.choice(["reduce", "no-preference"]),
        }

    def cdp_script(self) -> str:
        """JS injected on every new document to enforce the fingerprint."""
        prefs = self.css_prefers()
        ua = json.dumps(self.user_agent)
        plat = json.dumps(self.platform_js)
        loc = json.dumps(self.locale)
        tz = json.dumps(self.timezone)
        prefs_js = json.dumps(prefs)
        return (
            "(function(){"
            "Object.defineProperty(navigator,'userAgent',{get:()=>" + ua + "});"
            "Object.defineProperty(navigator,'platform',{get:()=>" + plat + "});"
            "Object.defineProperty(navigator,'language',{get:()=>" + loc + "});"
            "Object.defineProperty(navigator,'languages',{get:()=>[" + loc + "]});"
            "Object.defineProperty(Intl,'DateTimeFormat',{get:function(){"
            "return function(c,o){return new Intl.DateTimeFormat(c,Object.assign({timeZone:" + tz + "},o));};}});"
            "window.matchMedia=window.matchMedia||function(q){"
            "var m=" + prefs_js + ";"
            "var v=(q.indexOf('prefers-color-scheme')>=0)?m.prefers_color_scheme:"
            "(q.indexOf('prefers-reduced-motion')>=0)?m.prefers_reduced_motion:'no-preference';"
            "return {matches:q.indexOf(v)>=0,media:q,addListener:function(){},removeListener:function(){},"
            "addEventListener:function(){},removeEventListener:function(){},onchange:null,dispatchEvent:function(){return false;}};"
            "};"
            "})();"
        )


def derive_identity(seed: str, name: str = "") -> Identity:
    """Deterministically derive an Identity from a seed string."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    rng = random.Random(h)
    tmpl = rng.choice(_UA_TEMPLATES)
    plat_str, plat_js, viewport, tz, loc = tmpl
    ua = (
        f"Mozilla/5.0 ({plat_str}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{_CHROME_BUILD} Safari/537.36"
    )
    return Identity(
        seed=seed,
        name=name or seed,
        platform_string=plat_str,
        platform_js=plat_js,
        viewport=viewport,
        timezone=tz,
        locale=loc,
        user_agent=ua,
    )


class IdentityStore:
    """Persist identities to disk as JSON so personas survive restarts."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".umbra" / "identities.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Identity] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                for item in data.values():
                    self._cache[item["seed"]] = Identity(**item)
            except (json.JSONDecodeError, TypeError):
                pass

    def _save(self) -> None:
        payload = {k: v.to_dict() for k, v in self._cache.items()}
        self.path.write_text(json.dumps(payload, indent=2))

    def get(self, seed: str, name: str = "") -> Identity:
        if seed not in self._cache:
            self._cache[seed] = derive_identity(seed, name)
            self._save()
        return self._cache[seed]

    def list(self) -> list[Identity]:
        return list(self._cache.values())

    def rotate(self, name: str = "") -> Identity:
        """Mint a fresh identity from a random seed."""
        seed = hashlib.sha256(str(random.random()).encode()).hexdigest()[:16]
        return self.get(seed, name or f"anon-{seed[:6]}")
