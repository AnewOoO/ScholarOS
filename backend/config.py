from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "scholaros.db"
LEGACY_SESSIONS_FILE = DATA_DIR / "sessions.json"
REPOS_DIR = DATA_DIR / "repos"
NOTES_DIR = DATA_DIR / "notes"

DEFAULT_USER_ID = "local-user"
DEFAULT_LIBRARY_TITLE = "新的论文库"


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str


def get_llm_settings() -> LLMSettings:
    api_key = (
        os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
        or ""
    ).strip()
    if not api_key:
        raise RuntimeError("Missing LLM API key. Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or LLM_API_KEY.")

    return LLMSettings(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
    )
