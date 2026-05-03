from __future__ import annotations

from typing import Any

from backend.common.utils import compact_text


def generate_related_work(papers: list[dict[str, Any]], prompt: str = "") -> str:
    lines = ["# Related Work 草稿", ""]
    if prompt:
        lines.extend([f"写作目标：{prompt}", ""])
    if not papers:
        lines.append("当前论文库为空。请先用 Paper Builder 添加候选论文。")
        return "\n".join(lines)

    lines.append("## 主题脉络")
    for paper in papers[:10]:
        lines.append(
            f"- **{paper.get('title') or 'Untitled'}**：{compact_text(paper.get('summary') or paper.get('abstract') or '', 220)}"
        )
    lines.extend(
        [
            "",
            "## 可写研究 Gap",
            "- 现有方法的评价协议是否一致，是否存在难以公平比较的问题。",
            "- 公开代码、数据构造细节和超参数是否足以支撑复现。",
            "- 方法是否只在有限任务或分布设定上验证，泛化边界是否清晰。",
        ]
    )
    return "\n".join(lines)
