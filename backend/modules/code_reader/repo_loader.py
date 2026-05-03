from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from backend.common.exceptions import RepositoryLoadError
from backend.config import REPOS_DIR


def load_repository(repo_url: str) -> Path:
    value = str(repo_url or "").strip()
    if not value:
        raise RepositoryLoadError("仓库地址不能为空。")

    local_path = Path(value).expanduser()
    if local_path.exists() and local_path.is_dir():
        return local_path.resolve()

    if not value.startswith(("https://github.com/", "git@github.com:")):
        raise RepositoryLoadError("当前仅支持本地目录或 GitHub 仓库地址。")

    git = shutil.which("git")
    if not git:
        raise RepositoryLoadError("系统没有找到 git，无法自动读取 GitHub 仓库。")

    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    slug = _repo_slug(value)
    target = REPOS_DIR / slug
    if target.exists():
        return target.resolve()

    try:
        subprocess.run(
            [git, "clone", "--depth", "1", value, str(target)],
            cwd=str(REPOS_DIR),
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.SubprocessError as exc:
        raise RepositoryLoadError(f"克隆仓库失败：{exc}") from exc
    return target.resolve()


def _repo_slug(repo_url: str) -> str:
    cleaned = repo_url.rstrip("/").removesuffix(".git").replace(":", "/")
    parts = [part for part in cleaned.split("/") if part]
    tail = "-".join(parts[-2:]) if len(parts) >= 2 else hashlib.sha1(repo_url.encode()).hexdigest()[:12]
    digest = hashlib.sha1(repo_url.encode()).hexdigest()[:8]
    return f"{tail}-{digest}"
