from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    contract_text TEXT NOT NULL,
    decision TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    approver_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if path.parent and str(path.parent) not in {"", "."}:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_trace_id() -> str:
    return uuid4().hex[:12]


def save_trace(
    conn: sqlite3.Connection,
    *,
    trace_id: str,
    actor_id: str,
    contract_text: str,
    decision: str,
    payload: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO traces (trace_id, actor_id, contract_text, decision, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trace_id, actor_id, contract_text, decision, json.dumps(payload, ensure_ascii=False), now()),
    )
    conn.commit()


def get_trace(conn: sqlite3.Connection, trace_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM traces WHERE trace_id = ?",
        (trace_id,),
    ).fetchone()


def record_action(
    conn: sqlite3.Connection,
    *,
    trace_id: str,
    action: str,
    actor_id: str,
    approver_id: str,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO actions (trace_id, action, actor_id, approver_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trace_id, action, actor_id, approver_id, status, now()),
    )
    conn.commit()


def list_actions(conn: sqlite3.Connection, trace_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT action, actor_id, approver_id, status, created_at
        FROM actions WHERE trace_id = ? ORDER BY id
        """,
        (trace_id,),
    ).fetchall()
    return [dict(row) for row in rows]
