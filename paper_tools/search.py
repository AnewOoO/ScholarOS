from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from bs4 import BeautifulSoup

from paper_tools.common import http_get, normalize_arxiv_id


NS = {"atom": "http://www.w3.org/2005/Atom"}


def build_arxiv_search_query(direction: str) -> str:
    keywords = [
        token
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9-]*", direction)
        if len(token) > 1
    ]
    if 1 <= len(keywords) <= 6:
        return " AND ".join(f"all:{urllib.parse.quote(token)}" for token in keywords)
    return f'all:"{direction}"'


def parse_arxiv_entry(entry: ET.Element) -> dict[str, Any]:
    arxiv_id = normalize_arxiv_id(entry.findtext("atom:id", default="", namespaces=NS))
    authors = [
        author.findtext("atom:name", default="", namespaces=NS).strip()
        for author in entry.findall("atom:author", NS)
    ]
    return {
        "arxiv_id": arxiv_id,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "title": " ".join(entry.findtext("atom:title", default="", namespaces=NS).split()),
        "abstract": " ".join(entry.findtext("atom:summary", default="", namespaces=NS).split()),
        "authors": [name for name in authors if name],
        "published": entry.findtext("atom:published", default="", namespaces=NS) or None,
        "updated": entry.findtext("atom:updated", default="", namespaces=NS) or None,
        "engagement": 0,
        "engagement_source": "arxiv_relevance_fallback",
    }


def search_huggingface_papers(direction: str, limit: int) -> list[dict[str, Any]]:
    url = "https://huggingface.co/papers?q=" + urllib.parse.quote(direction)
    soup = BeautifulSoup(http_get(url).text, "html.parser")
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in soup.select('a[href^="/papers/"]'):
        href = link.get("href", "")
        arxiv_id = normalize_arxiv_id(href)
        if not re.fullmatch(r"\d{4}\.\d{4,5}", arxiv_id) or arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        card_text = link.parent.get_text(" ", strip=True) if link.parent else ""
        upvote_match = re.search(r"\b(\d{1,5})\b", card_text)
        candidates.append(
            {
                "arxiv_id": arxiv_id,
                "url": f"https://huggingface.co/papers/{arxiv_id}",
                "engagement": int(upvote_match.group(1)) if upvote_match else 0,
                "engagement_source": "huggingface_upvotes",
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def search_arxiv(direction: str, limit: int, sort_by: str = "relevance") -> list[dict[str, Any]]:
    arxiv_sort_by = "submittedDate" if sort_by == "latest" else "relevance"
    params = urllib.parse.urlencode(
        {
            "search_query": build_arxiv_search_query(direction),
            "start": 0,
            "max_results": limit,
            "sortBy": arxiv_sort_by,
            "sortOrder": "descending",
        }
    )
    xml_text = http_get(f"https://export.arxiv.org/api/query?{params}").text
    root = ET.fromstring(xml_text)
    candidates: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", NS):
        candidates.append(parse_arxiv_entry(entry))
    return candidates
