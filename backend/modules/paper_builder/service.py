from __future__ import annotations

from dataclasses import asdict
from typing import Any

from paper_tools.enrichment import enrich_candidates

from backend.modules.paper_builder.crawler import crawl_sources, expand_keywords
from backend.modules.paper_builder.ranker import rank_papers
from backend.modules.paper_builder.summarizer import build_agent_message, one_sentence_summary


class PaperBuilderService:
    def build(
        self,
        direction: str,
        *,
        limit: int = 5,
        sort_by: str = "relevance",
        skip_pdf: bool = True,
        skip_citations: bool = True,
    ) -> dict[str, Any]:
        normalized_direction = " ".join(str(direction or "").split())
        keywords = expand_keywords(normalized_direction)
        per_query_limit = max(6, min(20, limit * 3))
        candidates, source_counts = crawl_sources(keywords, per_query_limit, sort_by=sort_by)

        arxiv_candidates = [item for item in candidates if item.get("arxiv_id")]
        by_arxiv = {str(item.get("arxiv_id")): item for item in arxiv_candidates}
        papers: list[dict[str, Any]] = []

        if arxiv_candidates:
            try:
                enriched = enrich_candidates(
                    arxiv_candidates,
                    max(limit * 2, limit),
                    normalized_direction,
                    sort_by=sort_by,
                    include_pdf=not skip_pdf,
                    include_citations=not skip_citations,
                    verbose=False,
                )
                for paper in enriched:
                    item = asdict(paper)
                    candidate = by_arxiv.get(str(item.get("arxiv_id"))) or {}
                    item["source"] = candidate.get("source") or "arXiv"
                    item["sources"] = candidate.get("sources") or [item["source"]]
                    item["code_url"] = candidate.get("code_url")
                    papers.append(item)
            except Exception:
                papers.extend(_candidate_to_paper(item) for item in arxiv_candidates)

        papers.extend(_candidate_to_paper(item) for item in candidates if not item.get("arxiv_id"))
        ranked = rank_papers(_dedupe_papers(papers), normalized_direction, keywords)
        selected = ranked[:limit]
        for paper in selected:
            paper["summary"] = one_sentence_summary(paper, normalized_direction)

        return {
            "agent": "paper_builder",
            "direction": normalized_direction,
            "expanded_keywords": keywords,
            "sources": source_counts,
            "candidate_count": len(candidates),
            "papers": selected,
            "message": build_agent_message(normalized_direction, keywords, source_counts, selected),
        }


def _candidate_to_paper(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": candidate.get("title") or "Untitled",
        "authors": candidate.get("authors") or [],
        "institutions": candidate.get("institutions") or [],
        "abstract": candidate.get("abstract") or "",
        "arxiv_id": candidate.get("arxiv_id"),
        "url": candidate.get("url"),
        "published": candidate.get("published"),
        "updated": candidate.get("updated"),
        "engagement": int(candidate.get("engagement") or 0),
        "engagement_source": candidate.get("engagement_source") or "unknown",
        "citations": candidate.get("citations"),
        "source": candidate.get("source"),
        "sources": candidate.get("sources") or ([candidate.get("source")] if candidate.get("source") else []),
        "code_url": candidate.get("code_url"),
        "raw": candidate,
    }


def _dedupe_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for paper in papers:
        key = str(paper.get("arxiv_id") or paper.get("url") or paper.get("title") or "").casefold()
        if not key:
            continue
        if key in unique:
            existing = unique[key]
            for field in ["abstract", "url", "published", "code_url", "source"]:
                if not existing.get(field) and paper.get(field):
                    existing[field] = paper[field]
            existing_sources = existing.get("sources") or []
            incoming_sources = paper.get("sources") or []
            existing["sources"] = list(dict.fromkeys([*existing_sources, *incoming_sources]))
            existing["source"] = ", ".join(existing["sources"]) or existing.get("source")
            continue
        unique[key] = dict(paper)
    return list(unique.values())
