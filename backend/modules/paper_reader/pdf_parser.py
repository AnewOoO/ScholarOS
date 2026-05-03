from __future__ import annotations

import io
from typing import Any

import requests
from pypdf import PdfReader


def paper_pdf_url(paper: dict[str, Any]) -> str | None:
    url = str(paper.get("url") or "")
    arxiv_id = paper.get("arxiv_id")
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}"
    if "arxiv.org/abs/" in url:
        return url.replace("/abs/", "/pdf/")
    if url.lower().endswith(".pdf"):
        return url
    return None


def extract_pdf_text(paper: dict[str, Any], *, max_pages: int = 12) -> str:
    url = paper_pdf_url(paper)
    if not url:
        return ""
    response = requests.get(url, timeout=(8, 45), headers={"User-Agent": "ScholarOS/1.0"})
    response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    pages: list[str] = []
    for page in reader.pages[:max_pages]:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()
