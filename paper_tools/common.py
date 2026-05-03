from __future__ import annotations

import re
import time
from typing import Any

import requests


HTTP_TIMEOUT = (8, 35)
HTTP_RETRIES = 2
USER_AGENT = "ScholarOS-PaperFinder/1.0 (+https://arxiv.org; research helper)"


def http_get(url: str, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)
    timeout = kwargs.pop("timeout", HTTP_TIMEOUT)
    last_error: requests.RequestException | None = None

    for attempt in range(HTTP_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < HTTP_RETRIES:
                time.sleep(0.6 * (attempt + 1))

    assert last_error is not None
    raise last_error


def normalize_arxiv_id(raw: str) -> str:
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", raw)
    return match.group(1) if match else raw.strip()
