from __future__ import annotations


def generate_experiment_analysis(notes: str) -> str:
    if not notes.strip():
        notes = "尚未提供实验记录。"
    return "\n".join(
        [
            "# 实验分析草稿",
            "",
            "## 实验设置",
            notes,
            "",
            "## 结果解读",
            "- 先报告主结果相对最强基线的提升或下降。",
            "- 再解释哪些模块贡献最大，哪些场景收益有限。",
            "- 对不稳定结果给出可能原因：数据分布、训练预算、超参数或评估协议。",
            "",
            "## 建议补充",
            "- 增加消融实验，隔离核心模块贡献。",
            "- 增加成本分析，报告训练/推理开销。",
            "- 增加失败案例，说明方法边界。",
        ]
    )
