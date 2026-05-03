from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import requests

from backend.config import get_llm_settings
from backend.common.exceptions import ExternalServiceError


class OpenAICompatibleLLM:
    """Small wrapper around an OpenAI-compatible chat completions endpoint."""

    def __init__(self) -> None:
        self.settings = get_llm_settings()
        self.url = f"{self.settings.base_url}/v1/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: int = 90,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            response = requests.post(self.url, headers=self._headers(), json=payload, timeout=timeout)
        except requests.RequestException as exc:
            raise ExternalServiceError(f"LLM connection failed: {exc}") from exc
        if response.status_code >= 400:
            raise ExternalServiceError(f"LLM request failed with {response.status_code}: {response.text[:500]}")

        try:
            body = response.json()
            return str(body["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ExternalServiceError("LLM response format was not recognized.") from exc

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        timeout: int = 90,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        try:
            with requests.post(self.url, headers=self._headers(), json=payload, stream=True, timeout=timeout) as response:
                if response.status_code >= 400:
                    raise ExternalServiceError(
                        f"LLM request failed with {response.status_code}: {response.text[:500]}"
                    )
                for line in response.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {}).get("content")
                    except (KeyError, json.JSONDecodeError, IndexError, TypeError):
                        continue
                    if delta:
                        yield str(delta)
        except requests.RequestException as exc:
            raise ExternalServiceError(f"LLM connection failed: {exc}") from exc


def try_complete(messages: list[dict[str, str]], fallback: str, *, max_tokens: int | None = None) -> str:
    try:
        return OpenAICompatibleLLM().complete(messages, max_tokens=max_tokens)
    except Exception:
        return fallback
