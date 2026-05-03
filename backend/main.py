from __future__ import annotations

import json
import re
import time
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.common.exceptions import ExternalServiceError, RepositoryLoadError
from backend.common.llm import OpenAICompatibleLLM
from backend.common.schemas import (
    ChatRequest,
    CodeInterpreterRequest,
    PaperBuilderRequest,
    PaperReaderRequest,
    PaperWriterRequest,
)
from backend.common.utils import compact_text
from backend.config import DEFAULT_LIBRARY_TITLE, FRONTEND_DIR
from backend.database import (
    add_library_paper,
    append_messages,
    create_library,
    get_or_create_library,
    init_db,
    list_libraries,
    load_library,
    soft_delete_library,
    update_library,
)
from backend.modules.code_reader.service import CodeInterpreterService
from backend.modules.paper_builder.service import PaperBuilderService
from backend.modules.paper_reader.service import PaperReaderService
from backend.modules.paper_writer.service import PaperWriterService


app = FastAPI(title="ScholarOS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html not found")
    return FileResponse(index_file)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/agents")
def agents() -> dict[str, Any]:
    return {
        "agents": [
            {
                "id": "paper_builder",
                "name": "Paper Builder Agent",
                "stage": "推荐论文 / 构建论文库",
                "capabilities": ["扩展关键词", "多源检索", "相关度排序", "解释推荐原因"],
            },
            {
                "id": "paper_reader",
                "name": "Paper Reading Agent",
                "stage": "精读论文 / 总结翻译",
                "capabilities": ["检索对应论文", "结合原文摘要/PDF 片段回答", "结构化精读"],
            },
            {
                "id": "code_interpreter",
                "name": "Code Interpreter Agent",
                "stage": "代码解读 / 论文代码对齐",
                "capabilities": ["读取仓库", "定位训练入口", "生成运行命令", "论文-代码对齐"],
            },
            {
                "id": "paper_writer",
                "name": "Paper Writing Agent",
                "stage": "论文写作 / 研究输出",
                "capabilities": ["Related Work", "研究 gap", "创新点", "大纲", "实验分析", "润色"],
            },
        ]
    }


@app.post("/api/session")
def create_session() -> dict[str, Any]:
    return {"session": create_library()}


@app.get("/api/sessions")
def get_sessions() -> dict[str, Any]:
    return {"sessions": list_libraries()}


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    session = load_library(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session": session}


@app.patch("/api/session/{session_id}")
async def patch_session(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"session": update_library(session_id, **payload)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    soft_delete_library(session_id)
    return {"status": "deleted"}


@app.post("/api/session/{session_id}/papers")
async def add_paper_to_library(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        paper = payload.get("paper")
        return {"session": add_library_paper(session_id, paper)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/search")
def search_papers(
    direction: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20),
    sort: Literal["latest", "engagement", "relevance"] = "relevance",
    skip_pdf: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    session = get_or_create_library(session_id)
    result = PaperBuilderService().build(
        direction,
        limit=limit,
        sort_by=sort,
        skip_pdf=skip_pdf,
        skip_citations=skip_pdf,
    )
    update_library(session["id"], title=result["direction"][:80] or DEFAULT_LIBRARY_TITLE)
    return {
        "session_id": session["id"],
        "query": result["direction"],
        "original_query": direction,
        "limit": limit,
        "sort": sort,
        "skip_pdf": skip_pdf,
        "elapsed_seconds": round(time.perf_counter() - start, 2),
        **result,
    }


@app.post("/api/agents/paper-builder")
def paper_builder(payload: PaperBuilderRequest) -> dict[str, Any]:
    session = get_or_create_library(payload.session_id)
    result = PaperBuilderService().build(
        payload.direction,
        limit=payload.limit,
        sort_by=payload.sort,
        skip_pdf=payload.skip_pdf,
        skip_citations=payload.skip_citations,
    )
    update_library(session["id"], title=result["direction"][:80] or DEFAULT_LIBRARY_TITLE)
    return {"session_id": session["id"], **result}


@app.post("/api/agents/paper-reader")
def paper_reader(payload: PaperReaderRequest) -> dict[str, Any]:
    papers = payload.papers
    if not papers and payload.session_id:
        papers = (load_library(payload.session_id) or {}).get("papers", [])
    return PaperReaderService().answer(
        payload.prompt,
        paper=payload.paper,
        papers=papers,
        include_pdf=payload.include_pdf,
    )


@app.post("/api/agents/code-interpreter")
def code_interpreter(payload: CodeInterpreterRequest) -> dict[str, Any]:
    try:
        return CodeInterpreterService().analyze(
            payload.repo_url,
            paper=payload.paper,
            question=payload.question,
        )
    except RepositoryLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/agents/paper-writer")
def paper_writer(payload: PaperWriterRequest) -> dict[str, Any]:
    papers = payload.papers
    if not papers and payload.session_id:
        papers = (load_library(payload.session_id) or {}).get("papers", [])
    return PaperWriterService().write(
        mode=payload.mode,
        prompt=payload.prompt,
        papers=papers,
        experiment_notes=payload.experiment_notes,
        draft=payload.draft,
    )


@app.post("/api/chat")
def chat(payload: ChatRequest) -> StreamingResponse:
    session = get_or_create_library(payload.session_id)
    incoming = [message.model_dump() for message in payload.messages]
    profile = payload.profile or session.get("profile", "")
    papers = payload.papers or session.get("papers", [])
    latest_user_text = _latest_user_text(incoming)
    fresh_candidates: list[dict[str, Any]] = []

    should_search = _should_search_for_chat(latest_user_text) or (
        payload.agent == "paper_builder" and _should_search_for_paper_builder(latest_user_text, papers)
    )
    if should_search:
        try:
            fresh_candidates = PaperBuilderService().build(
                latest_user_text,
                limit=5,
                sort_by="relevance",
                skip_pdf=True,
                skip_citations=True,
            )["papers"]
        except Exception:
            fresh_candidates = []

    stored_messages = session.get("messages", [])
    messages = [
        {"role": "system", "content": _system_prompt(payload.agent)},
        {"role": "system", "content": _context_prompt(profile, papers, fresh_candidates)},
        *stored_messages[-12:],
        *incoming[-8:],
    ]

    def stream() -> Any:
        assistant_text = ""
        if fresh_candidates:
            yield _sse_event(json.dumps({"papers": fresh_candidates}, ensure_ascii=False), event="papers")
        try:
            llm = OpenAICompatibleLLM()
            for delta in llm.stream(messages):
                assistant_text += delta
                yield _sse_event(json.dumps({"delta": delta}, ensure_ascii=False))
        except (ExternalServiceError, RuntimeError) as exc:
            assistant_text = _fallback_chat_answer(latest_user_text, papers, fresh_candidates, exc)
            yield _sse_event(json.dumps({"delta": assistant_text}, ensure_ascii=False))
        recent_user_message = next((message for message in reversed(incoming) if message.get("role") == "user"), None)
        to_save: list[dict[str, str]] = []
        if recent_user_message:
            to_save.append({"role": "user", "content": recent_user_message.get("content") or ""})
        if assistant_text:
            to_save.append({"role": "assistant", "content": assistant_text})
        append_messages(session["id"], to_save, profile)
        yield _sse_event("[DONE]", event="done")

    return StreamingResponse(stream(), media_type="text/event-stream")


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return ""


def _should_search_for_chat(text: str) -> bool:
    lowered = text.lower()
    explicit = ["论文", "文献", "paper", "arxiv", "推荐", "检索", "related work", "survey", "literature"]
    trend = ["最新", "进展", "方向", "相关", "做什么", "有哪些"]
    topic = ["agent", "llm", "rag", "memory", "ood", "oe", "diffusion", "multimodal", "reasoning"]
    return any(item in lowered for item in explicit) or (
        any(item in lowered for item in topic) and any(item in lowered for item in trend)
    )


def _should_search_for_paper_builder(text: str, current_papers: list[dict[str, Any]]) -> bool:
    lowered = text.lower().strip()
    if len(lowered) < 2:
        return False
    action_markers = [
        "找",
        "推荐",
        "检索",
        "搜索",
        "扩展",
        "补充",
        "换一批",
        "再来",
        "更多",
        "近两年",
        "最新",
        "有代码",
        "openreview",
        "papers with code",
        "arxiv",
        "search",
        "recommend",
        "more",
        "latest",
        "code",
        "with code",
    ]
    compare_only_markers = ["为什么", "比较", "排序", "哪篇", "优先读", "解释", "总结"]
    if any(marker in lowered for marker in action_markers):
        return True
    if not current_papers and not any(marker in lowered for marker in compare_only_markers):
        return True
    return False


def _system_prompt(agent: str) -> str:
    role = {
        "paper_builder": "你当前以 Paper Builder Agent 身份工作，主动扩展关键词、筛选论文并解释推荐原因。",
        "paper_reader": "你当前以 Paper Reading Agent 身份工作，回答必须结合给定论文原文摘要或片段。",
        "code_interpreter": "你当前以 Code Interpreter Agent 身份工作，关注仓库结构、训练入口、运行命令和论文-代码对齐。",
        "paper_writer": "你当前以 Paper Writing Agent 身份工作，帮助写 Related Work、gap、创新点、大纲、实验分析和润色。",
    }.get(agent, "你是 ScholarOS，一个覆盖论文发现、精读、代码解读和论文写作的研究操作系统。")
    return (
        f"{role} 默认使用中文，回答要具体、结构化。引用论文时必须使用上下文中的标题，"
        "不要编造论文元数据、实验数字或代码路径。"
    )


def _context_prompt(profile: str, papers: list[dict[str, Any]], fresh_candidates: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        [
            f"用户研究画像：\n{profile or '空'}",
            f"当前论文库：\n{_paper_context(papers)}",
            f"本轮新检索候选：\n{_paper_context(fresh_candidates)}",
        ]
    )


def _paper_context(papers: list[dict[str, Any]]) -> str:
    if not papers:
        return "无"
    blocks: list[str] = []
    for index, paper in enumerate(papers[:8], start=1):
        blocks.append(
            "\n".join(
                [
                    f"{index}. {paper.get('title') or 'Untitled'}",
                    f"arXiv: {paper.get('arxiv_id') or 'unknown'}",
                    f"URL: {paper.get('url') or 'unknown'}",
                    f"摘要: {compact_text(paper.get('abstract') or '', 900)}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _fallback_chat_answer(
    question: str,
    papers: list[dict[str, Any]],
    fresh_candidates: list[dict[str, Any]],
    error: Exception,
) -> str:
    useful = fresh_candidates or papers
    if not useful:
        return f"LLM 暂时不可用：{error}\n\n你可以先在 Paper Builder 输入研究方向构建论文库。"
    lines = [f"LLM 暂时不可用：{error}", "", "我先基于本地论文元数据给一个简版回答：", ""]
    if question:
        lines.extend([f"问题：{question}", ""])
    for paper in useful[:5]:
        lines.append(f"- **{paper.get('title') or 'Untitled'}**：{compact_text(paper.get('abstract') or '', 220)}")
    return "\n".join(lines)


def _sse_event(data: str, event: str | None = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n"
