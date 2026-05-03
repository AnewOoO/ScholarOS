from __future__ import annotations

from typing import Any

from backend.common.utils import compact_text


def deterministic_deep_read(paper: dict[str, Any]) -> dict[str, Any]:
    abstract = compact_text(paper.get("abstract") or "", 900)
    title = paper.get("title") or "Untitled"
    return {
        "overview": f"《{title}》的核心信息来自当前元数据摘要：{abstract or '当前没有可用摘要。'}",
        "method": "建议重点追踪：问题定义、输入输出、核心假设、训练目标、推理流程、关键模块之间的数据流。",
        "experiments": "建议检查：数据集、基线、指标、主结果表、消融实验、失败案例、算力和随机种子。",
        "critique": "建议从有效性、可复现性、泛化边界、数据泄露风险和与自身研究方向的连接五个角度批判阅读。",
    }


def build_reader_context(papers: list[dict[str, Any]]) -> str:
    if not papers:
        return "没有论文上下文。"
    blocks: list[str] = []
    for index, paper in enumerate(papers[:6], start=1):
        blocks.append(
            "\n".join(
                [
                    f"{index}. {paper.get('title') or 'Untitled'}",
                    f"arXiv: {paper.get('arxiv_id') or 'unknown'}",
                    f"URL: {paper.get('url') or 'unknown'}",
                    f"摘要: {compact_text(paper.get('abstract') or '', 1200)}",
                ]
            )
        )
    return "\n\n".join(blocks)
