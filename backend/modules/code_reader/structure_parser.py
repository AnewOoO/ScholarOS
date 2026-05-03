from __future__ import annotations

from pathlib import Path
from typing import Any


IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", ".mypy_cache", ".pytest_cache"}
CONFIG_NAMES = {"requirements.txt", "environment.yml", "pyproject.toml", "setup.py", "package.json", "Dockerfile"}
TRAIN_NAMES = {"train.py", "main.py", "run.py", "finetune.py", "pretrain.py"}
EVAL_NAMES = {"eval.py", "evaluate.py", "test.py", "infer.py", "inference.py"}


def parse_structure(repo_path: Path, *, max_files: int = 240) -> dict[str, Any]:
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if any(part in IGNORE_DIRS for part in path.relative_to(repo_path).parts):
            continue
        if path.is_file():
            files.append(path)
        if len(files) >= max_files:
            break

    relative = [path.relative_to(repo_path).as_posix() for path in files]
    train_entries = [item for item in relative if Path(item).name in TRAIN_NAMES or "train" in Path(item).stem.lower()]
    eval_entries = [item for item in relative if Path(item).name in EVAL_NAMES or "eval" in Path(item).stem.lower()]
    configs = [item for item in relative if Path(item).name in CONFIG_NAMES or Path(item).suffix in {".yaml", ".yml", ".toml", ".json"}]
    core_files = [
        item
        for item in relative
        if Path(item).suffix in {".py", ".ipynb"}
        and any(term in item.lower() for term in ["model", "loss", "method", "algorithm", "trainer", "dataset"])
    ][:30]

    return {
        "root": str(repo_path),
        "file_count_sampled": len(relative),
        "tree": _compact_tree(relative),
        "train_entries": train_entries[:20],
        "eval_entries": eval_entries[:20],
        "configs": configs[:30],
        "core_files": core_files,
    }


def _compact_tree(paths: list[str], *, limit: int = 120) -> list[str]:
    return sorted(paths)[:limit]
