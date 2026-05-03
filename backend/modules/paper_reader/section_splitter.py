from __future__ import annotations

import re


SECTION_NAMES = [
    "abstract",
    "introduction",
    "related work",
    "background",
    "method",
    "methods",
    "approach",
    "experiments",
    "experiment",
    "results",
    "discussion",
    "limitations",
    "conclusion",
]


def split_sections(text: str) -> dict[str, str]:
    if not text.strip():
        return {}
    normalized = text.replace("\r\n", "\n")
    matches: list[tuple[str, int, int]] = []
    for name in SECTION_NAMES:
        pattern = re.compile(rf"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?{re.escape(name)}\s*$")
        for match in pattern.finditer(normalized):
            matches.append((name.title(), match.start(), match.end()))
    matches.sort(key=lambda item: item[1])
    if not matches:
        return {"原文片段": normalized[:7000]}

    sections: dict[str, str] = {}
    for index, (name, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(normalized)
        content = normalized[end:next_start].strip()
        if content:
            sections[name] = content[:7000]
    return sections
