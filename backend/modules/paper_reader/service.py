from __future__ import annotations

from typing import Any

from backend.common.llm import OpenAICompatibleLLM
from backend.common.utils import compact_text
from backend.modules.paper_builder.service import PaperBuilderService
from backend.modules.paper_reader.pdf_parser import extract_pdf_text
from backend.modules.paper_reader.section_splitter import split_sections
from backend.modules.paper_reader.summarizer import build_reader_context, deterministic_deep_read


class PaperReaderService:
    def answer(
        self,
        prompt: str,
        *,
        paper: dict[str, Any] | None = None,
        papers: list[dict[str, Any]] | None = None,
        include_pdf: bool = False,
    ) -> dict[str, Any]:
        selected_papers = [paper] if paper else list(papers or [])
        searched = False
        if not selected_papers:
            result = PaperBuilderService().build(prompt, limit=3, sort_by="relevance", skip_pdf=True, skip_citations=True)
            selected_papers = result["papers"]
            searched = True

        sections: dict[str, str] = {}
        pdf_error: str | None = None
        if include_pdf and selected_papers:
            try:
                text = extract_pdf_text(selected_papers[0])
                sections = split_sections(text)
            except Exception as exc:
                pdf_error = str(exc)

        answer = self._llm_answer(prompt, selected_papers, sections)
        deep_read = deterministic_deep_read(selected_papers[0]) if selected_papers else {}
        return {
            "agent": "paper_reader",
            "prompt": prompt,
            "searched": searched,
            "papers": selected_papers,
            "sections": {key: compact_text(value, 2400) for key, value in sections.items()},
            "pdf_error": pdf_error,
            "deep_read": deep_read,
            "answer": answer,
        }

    def _llm_answer(self, prompt: str, papers: list[dict[str, Any]], sections: dict[str, str]) -> str:
        context = build_reader_context(papers)
        section_context = "\n\n".join(f"## {name}\n{content[:1800]}" for name, content in list(sections.items())[:5])
        fallback = _fallback_answer(prompt, papers, sections)
        try:
            return OpenAICompatibleLLM().complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 ScholarOS 的论文精读 Agent。必须基于给定原文摘要或 PDF 片段回答，"
                            "不要编造没有出现在上下文中的实验结果、数字或结论。默认用中文，结构化输出。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"用户问题：{prompt}\n\n论文上下文：\n{context}\n\n"
                            f"PDF/章节片段：\n{section_context or '未加载 PDF 原文。'}"
                        ),
                    },
                ],
                max_tokens=2600,
            )
        except Exception:
            return fallback


def _fallback_answer(prompt: str, papers: list[dict[str, Any]], sections: dict[str, str]) -> str:
    if not papers:
        return "我没有找到可用论文上下文。请先在 Paper Builder 中构建论文库，或在精读区选择一篇论文。"
    lines = [f"## 基于原文信息的精读回答", "", f"问题：{prompt}", ""]
    for paper in papers[:3]:
        lines.extend(
            [
                f"### {paper.get('title') or 'Untitled'}",
                f"- 来源：{paper.get('url') or paper.get('arxiv_id') or 'unknown'}",
                f"- 摘要依据：{compact_text(paper.get('abstract') or '当前没有摘要。', 700)}",
                f"- 初步判断：这篇论文可用于回答该问题，但更细的实验数字需要加载 PDF 原文确认。",
                "",
            ]
        )
    if sections:
        lines.extend(["### 已解析章节", *[f"- {name}：{compact_text(text, 180)}" for name, text in sections.items()]])
    return "\n".join(lines)
