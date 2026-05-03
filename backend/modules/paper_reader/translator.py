from __future__ import annotations

from backend.common.llm import try_complete


def translate_to_chinese(text: str) -> str:
    if not text.strip():
        return ""
    fallback = text
    return try_complete(
        [
            {"role": "system", "content": "你是论文翻译助手。保留术语，输出自然、准确的中文。"},
            {"role": "user", "content": text[:6000]},
        ],
        fallback,
        max_tokens=1800,
    )
