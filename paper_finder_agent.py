from __future__ import annotations

import argparse
import json
import textwrap
import time
from typing import Any

from backend.modules.paper_builder.service import PaperBuilderService


def run(
    direction: str,
    limit: int,
    sort_by: str = "latest",
    skip_pdf: bool = False,
    skip_citations: bool = False,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    if verbose:
        print(f"[paper-builder] direction={direction!r}, limit={limit}, sort={sort_by}", flush=True)
    result = PaperBuilderService().build(
        direction,
        limit=limit,
        sort_by=sort_by,
        skip_pdf=skip_pdf,
        skip_citations=skip_citations,
    )
    if verbose:
        print(result["message"], flush=True)
    return result["papers"]


def format_markdown(papers: list[dict[str, Any]]) -> str:
    lines = ["# Paper Builder Result", ""]
    for index, paper in enumerate(papers, start=1):
        lines.extend(
            [
                f"## {index}. {paper.get('title') or 'Untitled'}",
                f"- URL: {paper.get('url') or ''}",
                f"- arXiv: {paper.get('arxiv_id') or ''}",
                f"- Published: {paper.get('published') or 'unknown'}",
                f"- Source: {paper.get('source') or 'unknown'}",
                f"- Score: {paper.get('relevance_score') or 'unknown'}",
                f"- Engagement: {paper.get('engagement', 0)} ({paper.get('engagement_source', 'unknown')})",
                f"- Citations: {paper.get('citations') if paper.get('citations') is not None else 'unknown'}",
                f"- Authors: {', '.join(paper.get('authors') or [])}",
                f"- Recommendation: {paper.get('recommendation_reason') or ''}",
                "- Summary:",
                textwrap.fill(paper.get("summary") or paper.get("abstract") or "", width=100),
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    time_start = time.time()
    parser = argparse.ArgumentParser(description="Find papers for a research direction with ScholarOS Paper Builder.")
    parser.add_argument("direction", help='Research direction, e.g. "OE Dataset Selection"')
    parser.add_argument("--limit", type=int, default=5, help="Number of papers to return")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    parser.add_argument(
        "--sort",
        choices=["engagement", "latest", "relevance"],
        default="relevance",
        help="Sort papers by public engagement, latest submission date, or relevance",
    )
    parser.add_argument("--skip-pdf", action="store_true", help="Skip PDF institution extraction for faster output")
    parser.add_argument("--skip-citations", action="store_true", help="Skip Semantic Scholar citation enrichment")
    parser.add_argument("--verbose", action="store_true", help="Print progress logs")
    args = parser.parse_args()

    papers = run(
        args.direction,
        args.limit,
        sort_by=args.sort,
        skip_pdf=args.skip_pdf,
        skip_citations=args.skip_citations,
        verbose=args.verbose,
    )
    if args.json:
        print(json.dumps(papers, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(papers))
    print(f"Time taken: {time.time() - time_start:.2f} seconds")


if __name__ == "__main__":
    main()
