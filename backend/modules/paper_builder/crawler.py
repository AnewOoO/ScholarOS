from __future__ import annotations

import re
import urllib.parse
from typing import Any

import requests

from paper_tools.common import http_get, normalize_arxiv_id
from paper_tools.search import search_arxiv, search_huggingface_papers


SOURCE_ARXIV = "arXiv"
SOURCE_HF = "Hugging Face Papers"
SOURCE_OPENREVIEW = "OpenReview"
SOURCE_PWC = "Papers with Code"


def expand_keywords(direction: str) -> list[str]:
    normalized = " ".join(str(direction or "").split())
    lowered = normalized.lower()
    keywords: list[str] = []

    if normalized:
        keywords.append(normalized)

    if any(term in lowered for term in ["oe", "outlier exposure", "ood", "near-ood", "dataset selection"]):
        keywords.extend(
            [
                "Outlier Exposure",
                "Auxiliary OOD Data",
                "Near-OOD Selection",
                "Synthetic Outlier Generation",
                "OOD Data Curation",
            ]
        )
    if "agent" in lowered and "memory" in lowered:
        keywords.extend(
            [
                "Agentic Memory LLM Agents",
                "Long-term Memory for LLM Agents",
                "Memory Retrieval Update Compression Agents",
                "Episodic Memory Language Agents",
                "Persistent Memory Agent Systems",
            ]
        )
    if "rag" in lowered or "retrieval" in lowered:
        keywords.extend(
            [
                "Retrieval Augmented Generation",
                "RAG Evaluation",
                "Query Rewriting for Retrieval",
                "Knowledge-intensive Language Models",
            ]
        )

    base_terms = [term for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", normalized) if len(term) > 1]
    if base_terms:
        compact = " ".join(base_terms[:6])
        keywords.extend([f"{compact} survey", f"{compact} benchmark", f"{compact} code"])

    unique: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        cleaned = " ".join(keyword.split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique[:8]


def _with_source(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        clone = dict(item)
        clone["source"] = source
        clone.setdefault("sources", [source])
        enriched.append(clone)
    return enriched


def search_papers_with_code(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "page_size": min(limit, 50)})
    urls = [
        f"https://paperswithcode.com/api/v1/search/?{params}",
        f"https://paperswithcode.com/api/v1/papers/?{params}",
    ]
    for url in urls:
        try:
            payload = http_get(url).json()
        except Exception:
            continue
        records = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            continue
        papers: list[dict[str, Any]] = []
        for record in records[:limit]:
            if not isinstance(record, dict):
                continue
            arxiv_id = normalize_arxiv_id(str(record.get("arxiv_id") or record.get("paper_url") or ""))
            url_value = record.get("url_abs") or record.get("paper_url") or record.get("url")
            papers.append(
                {
                    "title": record.get("title") or "Untitled",
                    "abstract": record.get("abstract") or "",
                    "arxiv_id": arxiv_id if re.fullmatch(r"\d{4}\.\d{4,5}", arxiv_id) else None,
                    "url": url_value,
                    "published": record.get("published") or record.get("date"),
                    "authors": record.get("authors") or [],
                    "code_url": record.get("repository_url") or record.get("code_url"),
                    "engagement": 0,
                    "engagement_source": "paperswithcode",
                }
            )
        return papers
    return []


def search_openreview(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"term": query, "limit": min(limit, 50)})
    url = f"https://api2.openreview.net/notes/search?{params}"
    try:
        payload = http_get(url).json()
    except Exception:
        return []

    notes = payload.get("notes") if isinstance(payload, dict) else None
    if not isinstance(notes, list):
        return []

    papers: list[dict[str, Any]] = []
    for note in notes[:limit]:
        if not isinstance(note, dict):
            continue
        content = note.get("content") or {}
        title = _openreview_field(content.get("title")) or "Untitled"
        abstract = _openreview_field(content.get("abstract")) or ""
        forum = note.get("forum") or note.get("id")
        papers.append(
            {
                "title": title,
                "abstract": abstract,
                "url": f"https://openreview.net/forum?id={forum}" if forum else None,
                "authors": _openreview_field(content.get("authors")) or [],
                "published": str(note.get("pdate") or note.get("cdate") or "")[:10] or None,
                "engagement": 0,
                "engagement_source": "openreview",
            }
        )
    return papers


def _openreview_field(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def crawl_sources(keywords: list[str], per_query_limit: int, sort_by: str = "relevance") -> tuple[list[dict[str, Any]], dict[str, int]]:
    all_candidates: list[dict[str, Any]] = []
    source_counts = {SOURCE_ARXIV: 0, SOURCE_HF: 0, SOURCE_OPENREVIEW: 0, SOURCE_PWC: 0}

    for keyword in keywords:
        for source, searcher in [
            (SOURCE_HF, lambda q: search_huggingface_papers(q, per_query_limit)),
            (SOURCE_ARXIV, lambda q: search_arxiv(q, per_query_limit, sort_by=sort_by)),
            (SOURCE_OPENREVIEW, lambda q: search_openreview(q, per_query_limit)),
            (SOURCE_PWC, lambda q: search_papers_with_code(q, per_query_limit)),
        ]:
            try:
                candidates = _with_source(searcher(keyword), source)
            except requests.RequestException:
                candidates = []
            source_counts[source] += len(candidates)
            all_candidates.extend(candidates)

    return dedupe_candidates(all_candidates), source_counts


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = str(candidate.get("arxiv_id") or candidate.get("url") or candidate.get("title") or "").casefold()
        if not key:
            continue
        if key in unique:
            existing = unique[key]
            sources = list(dict.fromkeys([*(existing.get("sources") or []), *(candidate.get("sources") or [])]))
            existing["sources"] = sources
            existing["source"] = ", ".join(sources)
            if (not existing.get("title") or existing.get("title") == "Untitled") and candidate.get("title"):
                existing["title"] = candidate["title"]
            if not existing.get("url") and candidate.get("url"):
                existing["url"] = candidate["url"]
            if not existing.get("abstract") and candidate.get("abstract"):
                existing["abstract"] = candidate["abstract"]
            if not existing.get("code_url") and candidate.get("code_url"):
                existing["code_url"] = candidate["code_url"]
            existing["engagement"] = max(int(existing.get("engagement") or 0), int(candidate.get("engagement") or 0))
            continue
        unique[key] = dict(candidate)
    return list(unique.values())
