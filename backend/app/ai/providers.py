"""Provider-neutral LLM wrapper. Each provider takes (system, user) prompts and returns raw text.

Add a provider by implementing `complete()`. Credentials come only from Settings (env vars).
"""
from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from ..config import Settings


class ProviderError(RuntimeError):
    """Raised for timeouts, HTTP errors and unusable responses. Message is safe to show."""


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, user: str, max_tokens: int = 1500, images: list[dict] | None = None) -> str:
        """images: [{"filename", "media_type", "data" (base64)}] — sent as vision input when supported."""
        ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, s: Settings):
        self.s = s
        self.url = (s.llm_base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
        self.model = s.llm_model or "claude-sonnet-4-5"

    def complete(self, system: str, user: str, max_tokens: int = 1500, images: list[dict] | None = None) -> str:
        headers = {"x-api-key": self.s.llm_api_key or "", "anthropic-version": "2023-06-01", "content-type": "application/json"}
        if self.s.llm_base_url:  # many internal proxies expect a bearer token instead
            headers["authorization"] = f"Bearer {self.s.llm_api_key}"
        content: list[dict] = []
        for i, img in enumerate(images or [], 1):
            content.append({"type": "text", "text": f"Image {i}: filename '{img['filename']}'"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": img["media_type"], "data": img["data"]}})
        content.append({"type": "text", "text": user})
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0, "system": system,
                "messages": [{"role": "user", "content": content}]}
        timeout = self.s.llm_timeout_seconds * (2.5 if images else 1)  # vision calls take longer
        data = _post(self.url, headers, body, timeout)
        try:
            return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (KeyError, TypeError) as e:
            raise ProviderError("Unexpected response shape from AI provider") from e


class OpenAICompatibleProvider:
    name = "openai"

    def __init__(self, s: Settings):
        self.s = s
        self.url = (s.llm_base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        self.model = s.llm_model or "gpt-4o-mini"

    def complete(self, system: str, user: str, max_tokens: int = 1500, images: list[dict] | None = None) -> str:
        headers = {"authorization": f"Bearer {self.s.llm_api_key}", "content-type": "application/json"}
        content: list[dict] | str = user
        if images:
            content = []
            for i, img in enumerate(images, 1):
                content.append({"type": "text", "text": f"Image {i}: filename '{img['filename']}'"})
                content.append({"type": "image_url", "image_url": {"url": f"data:{img['media_type']};base64,{img['data']}"}})
            content.append({"type": "text", "text": user})
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
        data = _post(self.url, headers, body, self.s.llm_timeout_seconds * (2.5 if images else 1))
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError("Unexpected response shape from AI provider") from e


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    try:
        r = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.TimeoutException as e:
        raise ProviderError(f"AI provider timed out after {timeout:.0f}s") from e
    except httpx.HTTPError as e:
        raise ProviderError("Could not reach AI provider") from e
    if r.status_code >= 400:
        raise ProviderError(f"AI provider returned HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError as e:
        raise ProviderError("AI provider returned non-JSON response") from e


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of model text (tolerates ```json fences)."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ProviderError("AI response did not contain JSON")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ProviderError("AI response JSON could not be parsed") from e
    if not isinstance(obj, dict):
        raise ProviderError("AI response JSON was not an object")
    return obj


def build_provider(s: Settings) -> LLMProvider | None:
    """None means: use the deterministic mock."""
    p = s.effective_provider
    if p == "anthropic":
        return AnthropicProvider(s)
    if p == "openai":
        return OpenAICompatibleProvider(s)
    return None
