from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Paper:
    title: str
    authors: list[str]
    institutions: list[str]
    abstract: str
    arxiv_id: str | None = None
    url: str | None = None
    published: str | None = None
    updated: str | None = None
    engagement: int = 0
    engagement_source: str = "unknown"
    citations: int | None = None
