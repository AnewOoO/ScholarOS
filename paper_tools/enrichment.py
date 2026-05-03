from __future__ import annotations

import io
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Process, Queue
from typing import Any

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from paper_tools.common import http_get, normalize_arxiv_id
from paper_tools.models import Paper


PDF_EXTRACTION_TIMEOUT_SECONDS = 8
ARXIV_METADATA_CHUNK_SIZE = 4


def fetch_hf_upvotes(arxiv_id: str) -> int:
    try:
        text = BeautifulSoup(http_get(f"https://huggingface.co/papers/{arxiv_id}").text, "html.parser").get_text(
            " ", strip=True
        )
    except requests.RequestException:
        return 0
    match = re.search(r"\bUpvote\s+(\d{1,6})\b", text)
    return int(match.group(1)) if match else 0


def fetch_arxiv_metadata_batch(arxiv_ids: list[str]) -> dict[str, Paper]:
    if not arxiv_ids:
        return {}

    params = urllib.parse.urlencode({"id_list": ",".join(arxiv_ids)})
    root = ET.fromstring(http_get(f"https://export.arxiv.org/api/query?{params}").text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers: dict[str, Paper] = {}

    for entry in root.findall("atom:entry", ns):
        arxiv_id = normalize_arxiv_id(entry.findtext("atom:id", default="", namespaces=ns))
        title = " ".join(entry.findtext("atom:title", default="", namespaces=ns).split())
        abstract = " ".join(entry.findtext("atom:summary", default="", namespaces=ns).split())
        published = entry.findtext("atom:published", default="", namespaces=ns) or None
        updated = entry.findtext("atom:updated", default="", namespaces=ns) or None
        authors = [
            author.findtext("atom:name", default="", namespaces=ns).strip()
            for author in entry.findall("atom:author", ns)
        ]
        papers[arxiv_id] = Paper(
            title=title,
            authors=[name for name in authors if name],
            institutions=[],
            abstract=abstract,
            arxiv_id=arxiv_id,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            published=published,
            updated=updated,
        )
    return papers


def fetch_arxiv_metadata_resilient(arxiv_ids: list[str], verbose: bool = False) -> dict[str, Paper]:
    metadata: dict[str, Paper] = {}
    unique_ids = list(dict.fromkeys(arxiv_ids))

    for start in range(0, len(unique_ids), ARXIV_METADATA_CHUNK_SIZE):
        chunk = unique_ids[start : start + ARXIV_METADATA_CHUNK_SIZE]
        try:
            metadata.update(fetch_arxiv_metadata_batch(chunk))
            time.sleep(0.4)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            log_verbose(verbose, f"[enrich] arXiv metadata chunk skipped with HTTP {status_code}: {chunk}")
            if status_code == 429:
                time.sleep(2.0)
        except requests.RequestException as exc:
            log_verbose(verbose, f"[enrich] arXiv metadata chunk skipped: {exc}")

    return metadata


def paper_from_candidate(candidate: dict[str, Any]) -> Paper | None:
    title = candidate.get("title")
    abstract = candidate.get("abstract")
    arxiv_id = candidate.get("arxiv_id")
    if not title or not abstract or not arxiv_id:
        return None
    return Paper(
        title=title,
        authors=list(candidate.get("authors") or []),
        institutions=[],
        abstract=abstract,
        arxiv_id=arxiv_id,
        url=candidate.get("url") or f"https://arxiv.org/abs/{arxiv_id}",
        published=candidate.get("published"),
        updated=candidate.get("updated"),
        engagement=int(candidate.get("engagement", 0)),
        engagement_source=candidate.get("engagement_source", "unknown"),
    )


def fetch_semantic_scholar(arxiv_id: str) -> dict[str, Any]:
    fields = "citationCount,authors.name,abstract,url"
    url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}?fields={fields}"
    try:
        return http_get(url).json()
    except requests.RequestException:
        return {}


def guess_institutions_from_pdf_unbounded(arxiv_id: str) -> list[str]:
    try:
        pdf_bytes = http_get(f"https://arxiv.org/pdf/{arxiv_id}").content
        text = PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text() or ""
    except Exception:
        return []

    candidates: list[str] = []
    patterns = [
        r"(?:Department|School|College|Faculty|Institute|Center|Centre|Laboratory|Lab)[^,\n]*(?:University|Research|Institute|Lab|Laboratory|College|School)[^,\n]*",
        r"(?:Google Research|Google DeepMind|Meta AI|Microsoft Research|OpenAI|Anthropic|Dracodes|Latitude Games|Emergent Garden|Stanford University|Princeton University|Rutgers, The State University of New Jersey|University of California, San Diego|University of Manouba|South Mediterranean University|Mediterranean Institute of Technology|University of [A-Z][A-Za-z ,]+)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text):
            cleaned = re.sub(r"\s+", " ", match).strip(" ,;.")
            if 3 < len(cleaned) < 120 and cleaned not in candidates:
                candidates.append(cleaned)
    return candidates[:8]


def guess_institutions_worker(arxiv_id: str, queue: Queue) -> None:
    queue.put(guess_institutions_from_pdf_unbounded(arxiv_id))


def guess_institutions_from_pdf(arxiv_id: str, timeout: int = PDF_EXTRACTION_TIMEOUT_SECONDS) -> list[str]:
    queue: Queue = Queue()
    process = Process(target=guess_institutions_worker, args=(arxiv_id, queue))
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join()
        return []

    if queue.empty():
        return []
    return queue.get()


def enrich_paper(
    candidate: dict[str, Any],
    paper: Paper,
    include_pdf: bool = True,
    include_citations: bool = True,
) -> Paper:
    arxiv_id = candidate["arxiv_id"]
    paper.engagement = int(candidate.get("engagement", 0)) or fetch_hf_upvotes(arxiv_id)
    paper.engagement_source = candidate.get("engagement_source", "huggingface_upvotes")

    if include_citations:
        semantic = fetch_semantic_scholar(arxiv_id)
        if semantic.get("citationCount") is not None:
            paper.citations = int(semantic["citationCount"])
        if not paper.abstract and semantic.get("abstract"):
            paper.abstract = semantic["abstract"]

    if include_pdf:
        paper.institutions = guess_institutions_from_pdf(arxiv_id)
    return paper


def log_verbose(enabled: bool, message: str) -> None:
    if enabled:
        print(message, file=sys.stderr, flush=True)


def is_relevant_to_direction(paper: Paper, direction: str) -> bool:
    haystack = f"{paper.title} {paper.abstract}".lower()
    normalized_direction = " ".join(direction.lower().split())
    if normalized_direction in haystack:
        return True

    tokens = [token for token in re.findall(r"[a-z0-9]+", normalized_direction) if len(token) > 2]
    return bool(tokens) and all(token in haystack for token in tokens)


def relevance_score(paper: Paper, direction: str) -> int:
    title = paper.title.lower()
    abstract = paper.abstract.lower()
    haystack = f"{title} {abstract}"
    normalized_direction = " ".join(direction.lower().split())
    tokens = [token for token in re.findall(r"[a-z0-9]+", normalized_direction) if len(token) > 2]

    score = 0
    if normalized_direction and normalized_direction in title:
        score += 80
    if normalized_direction and normalized_direction in abstract:
        score += 25

    for token in tokens:
        if token in title:
            score += 14
        if token in abstract:
            score += 4

    is_agent_memory_query = any(token.startswith("agent") for token in tokens) and "memory" in tokens
    if is_agent_memory_query:
        title_has_agent = "agent" in title or "agentic" in title
        title_has_memory = "memory" in title or "mem" in title
        if title_has_agent and title_has_memory:
            score += 60
        if "agentic memory" in title or "memory for llm agents" in title:
            score += 40

        mechanism_terms = [
            "long-term",
            "persistent",
            "retrieval",
            "retrieve",
            "recall",
            "update",
            "consolidat",
            "compress",
            "schema",
            "graph",
            "episodic",
            "semantic",
            "procedural",
            "memory system",
            "memory management",
        ]
        score += sum(6 for term in mechanism_terms if term in haystack)

        noise_terms = [
            "gpu memory",
            "memory efficient",
            "memory-efficient",
            "computationally and memory",
            "residual memory",
        ]
        score -= sum(30 for term in noise_terms if term in haystack)

    return score


def enrich_candidates(
    candidates: list[dict[str, Any]],
    limit: int,
    direction: str,
    sort_by: str = "latest",
    include_pdf: bool = True,
    include_citations: bool = True,
    verbose: bool = False,
) -> list[Paper]:
    ranked_candidates = sorted(
        candidates,
        key=lambda item: (int(item.get("engagement", 0)), item.get("arxiv_id", "")),
        reverse=True,
    )
    metadata_by_id = fetch_arxiv_metadata_resilient(
        [item["arxiv_id"] for item in ranked_candidates],
        verbose=verbose,
    )

    for item in ranked_candidates:
        if item["arxiv_id"] not in metadata_by_id and (paper := paper_from_candidate(item)) is not None:
            metadata_by_id[item["arxiv_id"]] = paper
    relevant_candidates = [
        item
        for item in ranked_candidates
        if (paper := metadata_by_id.get(item["arxiv_id"])) is not None and is_relevant_to_direction(paper, direction)
    ]
    if sort_by == "latest":
        relevant_candidates.sort(
            key=lambda item: metadata_by_id[item["arxiv_id"]].published or "",
            reverse=True,
        )
    elif sort_by == "relevance":
        relevant_candidates.sort(
            key=lambda item: relevance_score(metadata_by_id[item["arxiv_id"]], direction),
            reverse=True,
        )
    candidates_with_metadata = [item for item in ranked_candidates if item["arxiv_id"] in metadata_by_id]
    if sort_by == "relevance":
        candidates_with_metadata.sort(
            key=lambda item: relevance_score(metadata_by_id[item["arxiv_id"]], direction),
            reverse=True,
        )
    selected = (relevant_candidates or candidates_with_metadata)[:limit]
    log_verbose(verbose, f"[enrich] selected {len(selected)} candidates")
    log_verbose(verbose, f"[enrich] relevant candidates={len(relevant_candidates)}")

    papers: list[Paper] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(selected)))) as executor:
        futures = {}
        for candidate in selected:
            paper = metadata_by_id.get(candidate["arxiv_id"])
            if paper is not None:
                future = executor.submit(enrich_paper, candidate, paper, include_pdf, include_citations)
                futures[future] = candidate["arxiv_id"]

        for future in as_completed(futures):
            arxiv_id = futures[future]
            try:
                papers.append(future.result())
                log_verbose(verbose, f"[enrich] completed {arxiv_id}")
            except Exception as exc:
                log_verbose(verbose, f"[enrich] skipped {arxiv_id}: {exc}")

    if sort_by == "latest":
        papers.sort(key=lambda paper: paper.published or "", reverse=True)
    elif sort_by == "relevance":
        papers.sort(key=lambda paper: relevance_score(paper, direction), reverse=True)
    else:
        papers.sort(key=lambda paper: (paper.engagement, paper.citations or 0), reverse=True)
    return papers
