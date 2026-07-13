"""AI extraction layer: turn rendered page markdown into structured data.

Umbra is "AI-native" — instead of shipping a brittle HTML/CSS selector per
site, you describe the shape you want and an LLM produces it. The LLM backend
is pluggable and speaks the OpenAI-compatible chat-completions API, so any
provider (OpenAI, NVIDIA NIM, Together, local vLLM) works by setting a base
URL + key.

If no model is configured, :func:`extract` falls back to a deterministic,
rule-based schema guesser so the layer still works fully offline.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            base_url=os.environ.get("UMBRA_LLM_BASE_URL", ""),
            api_key=os.environ.get("UMBRA_LLM_API_KEY", ""),
            model=os.environ.get("UMBRA_LLM_MODEL", ""),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.model)


_SYSTEM = (
    "You convert rendered web-page markdown into structured JSON that matches "
    "the schema the user asks for. Respond with ONLY valid JSON, no markdown "
    "fences, no commentary. If a field is missing from the page, use null."
)


def _call_openai(cfg: LLMConfig, prompt: str) -> str:
    payload = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        cfg.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def _fallback_extract(markdown: str, schema: dict) -> dict:
    """Offline heuristic extraction when no LLM is configured.

    Matches each field by trying the field key and its hint as a label, e.g.
    a line ``Title: Super Widget`` satisfies both key ``title`` and hint
    ``product name``.
    """
    out: dict[str, Any] = {}
    lines = [ln.strip() for ln in markdown.splitlines() if ln.strip()]
    lowered = [ln.lower() for ln in lines]
    for key, hint in schema.items():
        out[key] = None
        labels = [str(key).lower()]
        if hint:
            labels.append(str(hint).lower())
        for i, low in enumerate(lowered):
            for label in labels:
                if not label:
                    continue
                if low == label or low.startswith(label + ":") or low.startswith(label + " "):
                    out[key] = lines[i].split(":", 1)[-1].strip()
                    break
            if out[key] is not None:
                break
    return out


def extract(
    markdown: str,
    schema: dict[str, str],
    *,
    cfg: Optional[LLMConfig] = None,
    raw: bool = False,
) -> Any:
    """Extract structured data from ``markdown``.

    ``schema`` maps field name -> natural-language description (used by the LLM;
    ignored by the offline fallback except as a label hint).

    Returns parsed JSON (dict/list) when possible, or the raw model text when
    ``raw`` is set or parsing fails.
    """
    cfg = cfg or LLMConfig.from_env()
    if not cfg.enabled:
        return _fallback_extract(markdown, schema)
    fields = "\n".join(f"- {k}: {v}" for k, v in schema.items())
    prompt = (
        f"Extract these fields from the page markdown below:\n{fields}\n\n"
        f"PAGE MARKDOWN:\n{markdown[:12000]}"
    )
    text = _call_openai(cfg, prompt)
    if raw:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # tolerate ```json fences that some models still emit
        stripped = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text
