from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.common.llm import OpenAICompatibleLLM
from backend.common.utils import compact_text


def read_salient_files(repo_path: Path, structure: dict[str, Any], *, max_chars: int = 26000) -> str:
    selected = [
        *structure.get("configs", [])[:6],
        *structure.get("train_entries", [])[:4],
        *structure.get("eval_entries", [])[:3],
        *structure.get("core_files", [])[:8],
    ]
    seen: set[str] = set()
    blocks: list[str] = []
    total = 0
    for rel in selected:
        if rel in seen:
            continue
        seen.add(rel)
        path = (repo_path / rel).resolve()
        if not str(path).startswith(str(repo_path.resolve())) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        snippet = text[:5000]
        total += len(snippet)
        blocks.append(f"## {rel}\n```text\n{snippet}\n```")
        if total >= max_chars:
            break
    return "\n\n".join(blocks)


def explain_code(structure: dict[str, Any], snippets: str, question: str = "") -> str:
    fallback = _fallback_explanation(structure)
    try:
        return OpenAICompatibleLLM().complete(
            [
                {
                    "role": "system",
                    "content": "你是代码解读 Agent。基于仓库结构和文件片段，找训练入口、核心实现、运行命令和复现路径。用中文回答。",
                },
                {
                    "role": "user",
                    "content": f"用户问题：{question or '请分析仓库复现路径。'}\n\n仓库结构：{structure}\n\n关键文件片段：\n{snippets}",
                },
            ],
            max_tokens=2600,
        )
    except Exception:
        return fallback


def build_run_commands(structure: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    config_names = {Path(item).name for item in structure.get("configs", [])}
    if "requirements.txt" in config_names:
        commands.append("python -m pip install -r requirements.txt")
    if "environment.yml" in config_names:
        commands.append("conda env create -f environment.yml")
    train = structure.get("train_entries", [])
    configs = [item for item in structure.get("configs", []) if item.endswith((".yaml", ".yml", ".json"))]
    if train:
        if configs:
            commands.append(f"python {train[0]} --config {configs[0]}")
        else:
            commands.append(f"python {train[0]}")
    eval_entries = structure.get("eval_entries", [])
    if eval_entries:
        commands.append(f"python {eval_entries[0]}")
    return commands or ["请先阅读 README，当前没有自动识别到训练入口。"]


def _fallback_explanation(structure: dict[str, Any]) -> str:
    lines = ["## 仓库复现路径初判", ""]
    if structure.get("configs"):
        lines.append(f"- 配置文件：{', '.join(structure['configs'][:6])}")
    if structure.get("train_entries"):
        lines.append(f"- 训练入口：{', '.join(structure['train_entries'][:5])}")
    if structure.get("core_files"):
        lines.append(f"- 核心候选实现：{', '.join(structure['core_files'][:8])}")
    if structure.get("eval_entries"):
        lines.append(f"- 评估入口：{', '.join(structure['eval_entries'][:5])}")
    lines.extend(["", "## 建议运行命令", *[f"- `{cmd}`" for cmd in build_run_commands(structure)]])
    return compact_text("\n".join(lines), 3000)
