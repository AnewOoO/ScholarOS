from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SortMode = Literal["latest", "engagement", "relevance"]


class PaperRecord(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    institutions: list[str] = Field(default_factory=list)
    abstract: str = ""
    arxiv_id: str | None = None
    url: str | None = None
    published: str | None = None
    updated: str | None = None
    engagement: int = 0
    engagement_source: str = "unknown"
    citations: int | None = None
    source: str | None = None
    code_url: str | None = None
    summary: str | None = None
    recommendation_reason: str | None = None
    relevance_score: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class PaperBuilderRequest(BaseModel):
    direction: str = Field(..., min_length=2)
    limit: int = Field(default=5, ge=1, le=20)
    sort: SortMode = "relevance"
    skip_pdf: bool = True
    skip_citations: bool = True
    session_id: str | None = None


class PaperReaderRequest(BaseModel):
    prompt: str = Field(..., min_length=2)
    paper: dict[str, Any] | None = None
    papers: list[dict[str, Any]] = Field(default_factory=list)
    include_pdf: bool = False
    session_id: str | None = None


class CodeInterpreterRequest(BaseModel):
    repo_url: str = Field(..., min_length=2)
    paper: dict[str, Any] | None = None
    question: str = ""
    session_id: str | None = None


class PaperWriterRequest(BaseModel):
    mode: Literal["outline", "related_work", "gap", "innovation", "experiment", "polish"] = "outline"
    prompt: str = ""
    papers: list[dict[str, Any]] = Field(default_factory=list)
    experiment_notes: str = ""
    draft: str = ""
    session_id: str | None = None


class ChatRequest(BaseModel):
    session_id: str | None = None
    messages: list[ChatMessage]
    profile: str = ""
    papers: list[dict[str, Any]] = Field(default_factory=list)
    agent: Literal["general", "paper_builder", "paper_reader", "code_interpreter", "paper_writer"] = "general"
