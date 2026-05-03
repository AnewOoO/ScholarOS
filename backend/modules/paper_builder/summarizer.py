from __future__ import annotations

import re
from typing import Any

from backend.common.utils import compact_text


def one_sentence_summary(paper: dict[str, Any], direction: str) -> str:
    abstract = compact_text(paper.get("abstract") or "", 420)
    if not abstract:
        return f"这篇论文与“{direction}”相关，但当前来源没有提供可用摘要。"

    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    first = sentences[0].strip() if sentences else abstract
    if len(first) < 40 and len(sentences) > 1:
        first = f"{first} {sentences[1].strip()}"
    return compact_text(first, 220)


def build_agent_message(direction: str, keywords: list[str], source_counts: dict[str, int], papers: list[dict[str, Any]]) -> str:
    source_text = " / ".join(source for source, count in source_counts.items() if count)
    total = sum(source_counts.values())
    lines = [
        f"我根据你的研究方向“{direction}”扩展了 {len(keywords)} 个检索词。",
        f"我从 {source_text or '可用论文源'} 中检索到 {total} 条候选记录。",
        f"经过相关度、代码可用性、引用/热度和时间因素筛选，推荐你优先阅读 {len(papers)} 篇。",
    ]
    return "\n".join(lines)
