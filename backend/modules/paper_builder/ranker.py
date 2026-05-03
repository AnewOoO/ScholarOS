from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from backend.common.utils import compact_text, extract_terms


def relevance_score(paper: dict[str, Any], direction: str, keywords: list[str]) -> float:
    title = str(paper.get("title") or "").lower()
    abstract = str(paper.get("abstract") or "").lower()
    haystack = f"{title} {abstract}"
    direction_terms = extract_terms(direction)
    keyword_terms = []
    for keyword in keywords:
        keyword_terms.extend(extract_terms(keyword))
    terms = list(dict.fromkeys([*direction_terms, *keyword_terms]))

    score = 0.0
    normalized_direction = " ".join(direction.lower().split())
    if normalized_direction and normalized_direction in title:
        score += 50
    if normalized_direction and normalized_direction in abstract:
        score += 18

    for term in terms:
        if term in title:
            score += 9
        if term in abstract:
            score += 2.5

    engagement = int(paper.get("engagement") or 0)
    citations = int(paper.get("citations") or 0)
    score += min(16, math.log1p(max(0, engagement)) * 4)
    score += min(14, math.log1p(max(0, citations)) * 2)
    if paper.get("code_url"):
        score += 10
    if paper.get("arxiv_id"):
        score += 4

    year = _paper_year(paper)
    if year:
        current_year = datetime.utcnow().year
        score += max(0, 8 - max(0, current_year - year) * 1.5)

    return round(score, 2)


def _paper_year(paper: dict[str, Any]) -> int | None:
    value = str(paper.get("published") or "")
    match = re.search(r"(20\d{2}|19\d{2})", value)
    if not match:
        return None
    return int(match.group(1))


def recommendation_reason(paper: dict[str, Any], direction: str, keywords: list[str]) -> str:
    title = str(paper.get("title") or "")
    abstract = str(paper.get("abstract") or "")
    terms = extract_terms(" ".join([direction, *keywords]))
    matched = [term for term in terms if term.lower() in f"{title} {abstract}".lower()][:4]

    reasons: list[str] = []
    if matched:
        reasons.append(f"主题命中：{', '.join(matched)}")
    if paper.get("code_url"):
        reasons.append("有公开代码线索")
    if paper.get("citations") is not None:
        reasons.append(f"引用数 {paper.get('citations')}")
    if paper.get("engagement"):
        reasons.append(f"社区热度 {paper.get('engagement')}")
    if paper.get("source"):
        reasons.append(f"来源 {paper.get('source')}")

    if not reasons:
        return compact_text(abstract, 120) or "标题与研究方向相关，建议作为候选阅读。"
    return "；".join(reasons) + "。"


def rank_papers(papers: list[dict[str, Any]], direction: str, keywords: list[str]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for paper in papers:
        enriched = dict(paper)
        enriched["relevance_score"] = relevance_score(enriched, direction, keywords)
        enriched["recommendation_reason"] = recommendation_reason(enriched, direction, keywords)
        ranked.append(enriched)
    ranked.sort(
        key=lambda item: (
            float(item.get("relevance_score") or 0),
            str(item.get("published") or ""),
            int(item.get("engagement") or 0),
        ),
        reverse=True,
    )
    return ranked
