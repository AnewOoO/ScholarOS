from __future__ import annotations

from typing import Any


def generate_outline(prompt: str, papers: list[dict[str, Any]]) -> str:
    topic = prompt or "当前研究主题"
    return "\n".join(
        [
            f"# 论文大纲：{topic}",
            "",
            "1. Introduction：问题背景、研究动机、挑战和贡献概览。",
            "2. Related Work：按方法族、数据/任务设定、评估协议组织已有工作。",
            "3. Problem Formulation：定义任务、符号、输入输出和评价目标。",
            "4. Method：核心框架、关键模块、训练/推理流程和复杂度。",
            "5. Experiments：数据集、基线、指标、主结果、消融、鲁棒性和失败案例。",
            "6. Discussion：适用边界、风险、与现有方法的差异。",
            "7. Conclusion：总结贡献和未来工作。",
            "",
            f"可引用论文数：{len(papers)}",
        ]
    )
