from __future__ import annotations

from typing import Any

from backend.modules.code_reader.code_explainer import build_run_commands, explain_code, read_salient_files
from backend.modules.code_reader.paper_mapper import map_paper_to_code
from backend.modules.code_reader.repo_loader import load_repository
from backend.modules.code_reader.structure_parser import parse_structure


class CodeInterpreterService:
    def analyze(
        self,
        repo_url: str,
        *,
        paper: dict[str, Any] | None = None,
        question: str = "",
    ) -> dict[str, Any]:
        repo_path = load_repository(repo_url)
        structure = parse_structure(repo_path)
        snippets = read_salient_files(repo_path, structure)
        explanation = explain_code(structure, snippets, question)
        return {
            "agent": "code_interpreter",
            "repo_path": str(repo_path),
            "structure": structure,
            "run_commands": build_run_commands(structure),
            "paper_code_map": map_paper_to_code(paper, structure),
            "answer": explanation,
        }
