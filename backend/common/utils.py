from __future__ import annotations

import json
import re
from typing import Any


def clean_text(value: Any) -> str:
    text = str(value or "")
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text
    return repaired or text


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def compact_text(value: Any, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if limit is not None and len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "..."
    return text


def extract_terms(text: str, *, min_length: int = 3) -> list[str]:
    terms = [item.lower() for item in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9-]*", text)]
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        if len(term) < min_length or term in seen:
            continue
        seen.add(term)
        unique.append(term)
    return unique


def stable_key(*parts: Any) -> str:
    return "::".join(str(part or "").strip().casefold() for part in parts if str(part or "").strip())
