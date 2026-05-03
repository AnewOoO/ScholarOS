from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.common.utils import extract_terms


def map_paper_to_code(paper: dict[str, Any] | None, structure: dict[str, Any]) -> list[dict[str, str]]:
    if not paper:
        return []
    text = f"{paper.get('title') or ''} {paper.get('abstract') or ''}"
    terms = extract_terms(text)
    mappings: list[dict[str, str]] = []
    for rel in [*structure.get("core_files", []), *structure.get("train_entries", []), *structure.get("eval_entries", [])]:
        stem_terms = extract_terms(Path(rel).stem.replace("_", " "))
        overlap = [term for term in terms if term in stem_terms or term in rel.lower()]
        if overlap:
            mappings.append(
                {
                    "paper_concept": ", ".join(overlap[:4]),
                    "code_path": rel,
                    "reason": "文件名与论文标题/摘要术语重合，建议进一步打开确认实现细节。",
                }
            )
    return mappings[:12]
