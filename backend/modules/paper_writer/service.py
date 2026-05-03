from __future__ import annotations

from typing import Any

from backend.common.llm import OpenAICompatibleLLM
from backend.modules.paper_reader.summarizer import build_reader_context
from backend.modules.paper_writer.experiment_writer import generate_experiment_analysis
from backend.modules.paper_writer.outline import generate_outline
from backend.modules.paper_writer.related_work import generate_related_work


class PaperWriterService:
    def write(
        self,
        *,
        mode: str,
        prompt: str = "",
        papers: list[dict[str, Any]] | None = None,
        experiment_notes: str = "",
        draft: str = "",
    ) -> dict[str, Any]:
        papers = list(papers or [])
        fallback = self._fallback(mode, prompt, papers, experiment_notes, draft)
        try:
            answer = OpenAICompatibleLLM().complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 ScholarOS 的论文写作 Agent。基于论文库和用户草稿写作，"
                            "帮助生成 Related Work、研究 gap、创新点包装、论文大纲、实验分析或润色。"
                            "不要伪造引用，不要编造不存在的实验结果。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"任务类型：{mode}\n写作要求：{prompt}\n\n论文库：\n{build_reader_context(papers)}\n\n"
                            f"实验记录：\n{experiment_notes}\n\n草稿：\n{draft}"
                        ),
                    },
                ],
                max_tokens=3200,
            )
        except Exception:
            answer = fallback
        return {"agent": "paper_writer", "mode": mode, "answer": answer}

    def _fallback(
        self,
        mode: str,
        prompt: str,
        papers: list[dict[str, Any]],
        experiment_notes: str,
        draft: str,
    ) -> str:
        if mode == "related_work":
            return generate_related_work(papers, prompt)
        if mode == "experiment":
            return generate_experiment_analysis(experiment_notes)
        if mode == "polish":
            return draft or "请先输入需要润色的段落。"
        if mode == "gap":
            return "\n".join(
                [
                    "# 研究 Gap",
                    "",
                    "- 复现细节是否完整：代码、数据、超参数和评估脚本。",
                    "- 数据设定是否覆盖真实边界条件。",
                    "- 与强基线的比较是否充分，是否存在只优于弱基线的问题。",
                ]
            )
        if mode == "innovation":
            return "\n".join(
                [
                    "# 创新点包装",
                    "",
                    "1. 从问题设定上强调未被充分处理的约束或场景。",
                    "2. 从方法上强调关键模块如何直接缓解该约束。",
                    "3. 从实验上强调可复现、可解释和边界清晰的验证。",
                ]
            )
        return generate_outline(prompt, papers)
