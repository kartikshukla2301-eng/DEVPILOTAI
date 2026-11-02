"""OpenAI-compatible chat completions client (works with OpenAI, Azure-compatible gateways, OpenRouter, Groq, Ollama, LM Studio...)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

MAX_CODE_FOR_AI = 24_000  # characters sent to the model


class AIError(RuntimeError):
    pass


def ai_available() -> bool:
    return get_settings().ai_enabled


def should_use_ai(requested: bool, user_pref: bool) -> bool:
    return requested and user_pref and ai_available()


def provider_host() -> str | None:
    s = get_settings()
    if not s.ai_enabled:
        return None
    return urlparse(s.ai_base_url).hostname


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise AIError("The AI response was not valid JSON")


def clip_code(code: str) -> str:
    if len(code) <= MAX_CODE_FOR_AI:
        return code
    return code[:MAX_CODE_FOR_AI] + "\n\n/* ... truncated for AI analysis ... */"


def chat_json(system: str, user: str, *, max_tokens: int = 3000, temperature: float = 0.2) -> dict[str, Any]:
    s = get_settings()
    if not s.ai_enabled:
        raise AIError("AI is not configured")
    url = s.ai_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {s.ai_api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": s.ai_model,
        "messages": [
            {"role": "system", "content": system + "\nRespond with a single valid JSON object only. No prose outside JSON."},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=s.ai_timeout_seconds) as client:
            r = client.post(url, headers=headers, json=body)
            if r.status_code == 400 and "response_format" in r.text:
                body.pop("response_format")
                r = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        log.warning("AI request failed: %s", exc.__class__.__name__)
        raise AIError("Could not reach the AI provider") from exc
    if r.status_code == 401:
        raise AIError("The AI provider rejected the API key")
    if r.status_code == 429:
        raise AIError("The AI provider rate limit was reached; try again shortly")
    if r.status_code >= 400:
        log.warning("AI provider returned HTTP %s", r.status_code)
        raise AIError(f"The AI provider returned HTTP {r.status_code}")
    try:
        content = r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as exc:
        raise AIError("Unexpected response format from the AI provider") from exc
    return _extract_json(content)


def as_str(v: Any, default: str = "", limit: int = 20000) -> str:
    if v is None:
        return default
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return str(v)[:limit]


def as_str_list(v: Any, limit: int = 30) -> list[str]:
    if isinstance(v, str):
        return [v] if v.strip() else []
    if not isinstance(v, list):
        return []
    return [as_str(x, limit=2000) for x in v[:limit] if as_str(x).strip()]


def as_int(v: Any) -> int | None:
    try:
        i = int(v)
        return i if i > 0 else None
    except (TypeError, ValueError):
        return None
