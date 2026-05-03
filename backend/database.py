from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from typing import Any

from backend.common.utils import clean_text, json_dump, json_load
from backend.config import DB_FILE, DEFAULT_LIBRARY_TITLE, DEFAULT_USER_ID, LEGACY_SESSIONS_FILE


DB_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now() -> float:
    return time.time()


def init_db() -> None:
    with DB_LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS paper_libraries (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                profile TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                deleted_at REAL
            );

            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                arxiv_id TEXT UNIQUE,
                title TEXT NOT NULL,
                url TEXT,
                published TEXT,
                abstract TEXT,
                authors_json TEXT NOT NULL DEFAULT '[]',
                institutions_json TEXT NOT NULL DEFAULT '[]',
                engagement INTEGER,
                engagement_source TEXT,
                citations INTEGER,
                raw_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS library_papers (
                library_id TEXT NOT NULL REFERENCES paper_libraries(id) ON DELETE CASCADE,
                paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (library_id, paper_id)
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                library_id TEXT NOT NULL REFERENCES paper_libraries(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_libraries_user_updated
                ON paper_libraries(user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_library_created
                ON chat_messages(library_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_library_papers_position
                ON library_papers(library_id, position);
            """
        )
        timestamp = now()
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (DEFAULT_USER_ID, "Local User", timestamp, timestamp),
        )
        _migrate_legacy_sessions(conn)
        conn.commit()


def _migrate_legacy_sessions(conn: sqlite3.Connection) -> None:
    active_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM paper_libraries
        WHERE user_id = ? AND deleted_at IS NULL
        """,
        (DEFAULT_USER_ID,),
    ).fetchone()[0]
    if active_count or not LEGACY_SESSIONS_FILE.exists():
        return

    try:
        legacy_sessions = json_load(LEGACY_SESSIONS_FILE.read_text(encoding="utf-8"), {})
    except OSError:
        return
    if not isinstance(legacy_sessions, dict):
        return

    for session in legacy_sessions.values():
        if not isinstance(session, dict):
            continue
        library_id = str(session.get("id") or uuid.uuid4().hex)
        created_at = float(session.get("created_at") or now())
        updated_at = float(session.get("updated_at") or created_at)
        conn.execute(
            """
            INSERT OR IGNORE INTO paper_libraries (
                id, user_id, title, profile, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                library_id,
                DEFAULT_USER_ID,
                clean_text(session.get("title") or DEFAULT_LIBRARY_TITLE)[:80],
                clean_text(session.get("profile") or ""),
                created_at,
                updated_at,
            ),
        )
        _insert_papers_for_migration(conn, library_id, session.get("papers") or [], created_at)
        _insert_messages_for_migration(conn, library_id, session.get("messages") or [], created_at)


def _insert_papers_for_migration(
    conn: sqlite3.Connection,
    library_id: str,
    papers: list[dict[str, Any]],
    created_at: float,
) -> None:
    for position, paper in enumerate(papers):
        if not isinstance(paper, dict):
            continue
        paper_id = paper_id_for(paper)
        conn.execute(
            """
            INSERT OR REPLACE INTO papers (
                id, arxiv_id, title, url, published, abstract, authors_json,
                institutions_json, engagement, engagement_source, citations,
                raw_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            paper_values(paper, paper_id, created_at),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO library_papers (library_id, paper_id, position, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (library_id, paper_id, position, created_at),
        )


def _insert_messages_for_migration(
    conn: sqlite3.Connection,
    library_id: str,
    messages: list[dict[str, Any]],
    created_at: float,
) -> None:
    timestamp = created_at
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = str(message.get("content") or "")
        if role not in {"user", "assistant", "system"} or not content:
            continue
        conn.execute(
            """
            INSERT INTO chat_messages (id, library_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (uuid.uuid4().hex, library_id, role, content, timestamp),
        )
        timestamp += 0.001


def paper_id_for(paper: dict[str, Any]) -> str:
    return str(paper.get("arxiv_id") or paper.get("url") or paper.get("title") or uuid.uuid4().hex)


def paper_values(paper: dict[str, Any], paper_id: str, timestamp: float) -> tuple[Any, ...]:
    arxiv_id = paper.get("arxiv_id") or None
    raw = dict(paper)
    return (
        paper_id,
        arxiv_id,
        clean_text(paper.get("title") or "Untitled")[:500],
        paper.get("url"),
        paper.get("published"),
        clean_text(paper.get("abstract") or ""),
        json_dump(paper.get("authors") or []),
        json_dump(paper.get("institutions") or []),
        int(paper.get("engagement") or 0),
        paper.get("engagement_source") or "unknown",
        paper.get("citations"),
        json_dump(raw),
        timestamp,
        timestamp,
    )


def paper_from_row(row: sqlite3.Row) -> dict[str, Any]:
    raw = json_load(row["raw_json"], {})
    if not isinstance(raw, dict):
        raw = {}
    paper = {
        **raw,
        "id": row["id"],
        "arxiv_id": row["arxiv_id"],
        "title": clean_text(row["title"]),
        "url": row["url"],
        "published": row["published"],
        "abstract": clean_text(row["abstract"] or ""),
        "authors": json_load(row["authors_json"], []),
        "institutions": json_load(row["institutions_json"], []),
        "engagement": row["engagement"] or 0,
        "engagement_source": row["engagement_source"] or "unknown",
        "citations": row["citations"],
    }
    return paper


def get_messages(conn: sqlite3.Connection, library_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT role, content
        FROM chat_messages
        WHERE library_id = ?
        ORDER BY created_at ASC
        """,
        (library_id,),
    ).fetchall()
    return [{"role": row["role"], "content": clean_text(row["content"])} for row in rows]


def get_library_papers(conn: sqlite3.Connection, library_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.*
        FROM library_papers lp
        JOIN papers p ON p.id = lp.paper_id
        WHERE lp.library_id = ?
        ORDER BY lp.position ASC, lp.created_at ASC
        """,
        (library_id,),
    ).fetchall()
    return [paper_from_row(row) for row in rows]


def row_to_library(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": clean_text(row["title"]),
        "profile": clean_text(row["profile"] or ""),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "papers": get_library_papers(conn, row["id"]),
        "messages": get_messages(conn, row["id"]),
    }


def create_library(title: str = DEFAULT_LIBRARY_TITLE) -> dict[str, Any]:
    timestamp = now()
    library_id = uuid.uuid4().hex
    with DB_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO paper_libraries (id, user_id, title, profile, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (library_id, DEFAULT_USER_ID, title[:80], "", timestamp, timestamp),
        )
        conn.commit()
        return get_library_by_id(conn, library_id) or {}


def get_library_by_id(conn: sqlite3.Connection, library_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT *
        FROM paper_libraries
        WHERE id = ? AND user_id = ? AND deleted_at IS NULL
        """,
        (library_id, DEFAULT_USER_ID),
    ).fetchone()
    return row_to_library(conn, row) if row else None


def get_or_create_library(library_id: str | None) -> dict[str, Any]:
    with DB_LOCK, _connect() as conn:
        if library_id:
            library = get_library_by_id(conn, library_id)
            if library:
                return library
        conn.commit()
    return create_library()


def list_libraries() -> list[dict[str, Any]]:
    with DB_LOCK, _connect() as conn:
        rows = conn.execute(
            """
            SELECT l.*,
                COUNT(DISTINCT lp.paper_id) AS paper_count,
                COUNT(DISTINCT cm.id) AS message_count
            FROM paper_libraries l
            LEFT JOIN library_papers lp ON lp.library_id = l.id
            LEFT JOIN chat_messages cm ON cm.library_id = l.id
            WHERE l.user_id = ? AND l.deleted_at IS NULL
            GROUP BY l.id
            ORDER BY l.updated_at DESC
            """,
            (DEFAULT_USER_ID,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "title": clean_text(row["title"]),
                "profile": clean_text(row["profile"] or ""),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "paper_count": row["paper_count"],
                "message_count": row["message_count"],
            }
            for row in rows
        ]


def load_library(library_id: str) -> dict[str, Any] | None:
    with DB_LOCK, _connect() as conn:
        return get_library_by_id(conn, library_id)


def update_library(library_id: str, **updates: Any) -> dict[str, Any]:
    allowed: dict[str, Any] = {}
    if "title" in updates:
        allowed["title"] = clean_text(updates["title"] or DEFAULT_LIBRARY_TITLE)[:80]
    if "profile" in updates:
        allowed["profile"] = clean_text(updates["profile"] or "")
    allowed["updated_at"] = now()

    assignments = ", ".join(f"{key} = ?" for key in allowed)
    values = list(allowed.values()) + [library_id, DEFAULT_USER_ID]
    with DB_LOCK, _connect() as conn:
        conn.execute(
            f"""
            UPDATE paper_libraries
            SET {assignments}
            WHERE id = ? AND user_id = ? AND deleted_at IS NULL
            """,
            values,
        )
        conn.commit()
        library = get_library_by_id(conn, library_id)
        if library is None:
            raise KeyError(library_id)
        return library


def soft_delete_library(library_id: str) -> None:
    timestamp = now()
    with DB_LOCK, _connect() as conn:
        conn.execute(
            """
            UPDATE paper_libraries
            SET deleted_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (timestamp, timestamp, library_id, DEFAULT_USER_ID),
        )
        conn.commit()


def add_library_paper(library_id: str, paper: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(paper, dict):
        raise ValueError("paper must be an object")
    if not paper.get("title"):
        raise ValueError("paper.title is required")

    timestamp = now()
    paper_id = paper_id_for(paper)
    with DB_LOCK, _connect() as conn:
        library = get_library_by_id(conn, library_id)
        if library is None:
            raise KeyError(library_id)
        conn.execute(
            """
            INSERT OR REPLACE INTO papers (
                id, arxiv_id, title, url, published, abstract, authors_json,
                institutions_json, engagement, engagement_source, citations,
                raw_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            paper_values(paper, paper_id, timestamp),
        )
        max_position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM library_papers WHERE library_id = ?",
            (library_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO library_papers (library_id, paper_id, position, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (library_id, paper_id, int(max_position) + 1, timestamp),
        )
        conn.execute(
            """
            UPDATE paper_libraries
            SET updated_at = ?
            WHERE id = ?
            """,
            (timestamp, library_id),
        )
        conn.commit()
        return get_library_by_id(conn, library_id) or {}


def append_messages(library_id: str, messages: list[dict[str, str]], profile: str = "") -> None:
    clean_messages = [
        {
            "role": str(message.get("role")),
            "content": clean_text(message.get("content") or ""),
        }
        for message in messages
        if message.get("role") in {"user", "assistant", "system"} and str(message.get("content") or "").strip()
    ]
    if not clean_messages and profile == "":
        return

    timestamp = now()
    with DB_LOCK, _connect() as conn:
        if get_library_by_id(conn, library_id) is None:
            raise KeyError(library_id)
        for offset, message in enumerate(clean_messages):
            conn.execute(
                """
                INSERT INTO chat_messages (id, library_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (uuid.uuid4().hex, library_id, message["role"], message["content"], timestamp + offset * 0.001),
            )
        conn.execute(
            """
            UPDATE paper_libraries
            SET profile = ?, updated_at = ?
            WHERE id = ?
            """,
            (clean_text(profile), timestamp, library_id),
        )
        conn.commit()
