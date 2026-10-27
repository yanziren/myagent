from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from claimdesk.domain.models import Suggestion

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    clause_ids TEXT NOT NULL,
    rule_ids TEXT NOT NULL,
    rationale TEXT NOT NULL,
    model_calls INTEGER NOT NULL,
    missing_docs TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    status TEXT NOT NULL,
    intent TEXT NOT NULL,
    owner TEXT,
    lease_until INTEGER
);
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    amount INTEGER NOT NULL,
    target TEXT NOT NULL,
    approver TEXT NOT NULL,
    phase TEXT,
    trace_id TEXT,
    tool TEXT,
    payload TEXT,
    version TEXT
);
CREATE TABLE IF NOT EXISTS memory (
    tenant_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (tenant_id, claim_id, key)
);
CREATE TABLE IF NOT EXISTS cache (
    clause_version TEXT NOT NULL,
    query TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (clause_version, query)
);
CREATE TABLE IF NOT EXISTS checkpoints (
    job_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    side_effect_key TEXT NOT NULL,
    PRIMARY KEY (job_id, side_effect_key)
);
CREATE TABLE IF NOT EXISTS usage (
    path TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    yuan REAL NOT NULL,
    created_on TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _save_claim_row(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    actor_id: str,
    suggestion: Suggestion,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO claims (
            claim_id, actor_id, decision, clause_ids, rule_ids,
            rationale, model_calls, missing_docs, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(claim_id) DO UPDATE SET
            actor_id = excluded.actor_id,
            decision = excluded.decision,
            clause_ids = excluded.clause_ids,
            rule_ids = excluded.rule_ids,
            rationale = excluded.rationale,
            model_calls = excluded.model_calls,
            missing_docs = excluded.missing_docs,
            status = excluded.status
        """,
        (
            claim_id,
            actor_id,
            suggestion.decision,
            json.dumps(suggestion.clause_ids, ensure_ascii=False),
            json.dumps(suggestion.rule_ids, ensure_ascii=False),
            suggestion.rationale,
            suggestion.model_calls,
            json.dumps(suggestion.missing_docs, ensure_ascii=False),
            status,
        ),
    )
    conn.commit()


def save_eligibility(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    actor_id: str,
    suggestion: Suggestion,
) -> None:
    _save_claim_row(
        conn,
        claim_id=claim_id,
        actor_id=actor_id,
        suggestion=suggestion,
        status="eligibility_checked",
    )


def save_intake(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    actor_id: str,
    suggestion: Suggestion,
) -> None:
    if suggestion.decision == "补充材料":
        status = "need_docs"
    else:
        status = "eligibility_checked"
    _save_claim_row(
        conn,
        claim_id=claim_id,
        actor_id=actor_id,
        suggestion=suggestion,
        status=status,
    )


def count_claims(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM claims").fetchone()
    return int(row["n"])


def insert_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    claim_id: str,
    intent: str,
) -> None:
    conn.execute(
        """
        INSERT INTO jobs (id, claim_id, status, intent)
        VALUES (?, ?, 'accepted', ?)
        """,
        (job_id, claim_id, intent),
    )
    conn.commit()


def count_jobs(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()
    return int(row["n"])


def next_accepted_job(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, claim_id, status, intent
        FROM jobs
        WHERE status = 'accepted'
        ORDER BY rowid
        LIMIT 1
        """
    ).fetchone()


def complete_job(conn: sqlite3.Connection, job_id: str) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'completed' WHERE id = ?",
        (job_id,),
    )
    conn.commit()


def idempotency_key(job_id: str, tool: str, args: dict) -> str:
    payload = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return f"{job_id}:{tool}:{payload}"


def get_idempotency_result(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT status, result FROM idempotency WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None or row["status"] != "done":
        return None
    return str(row["result"])


def insert_idempotency_intended(conn: sqlite3.Connection, key: str) -> None:
    conn.execute(
        """
        INSERT INTO idempotency (key, status, result)
        VALUES (?, 'intended', '')
        ON CONFLICT(key) DO NOTHING
        """,
        (key,),
    )
    conn.commit()


def complete_idempotency(conn: sqlite3.Connection, key: str, result: str) -> None:
    conn.execute(
        """
        UPDATE idempotency
        SET status = 'done', result = ?
        WHERE key = ?
        """,
        (result, key),
    )
    conn.commit()


def delete_idempotency(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM idempotency WHERE key = ?", (key,))
    conn.commit()


def count_idempotency(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM idempotency").fetchone()
    return int(row["n"])


def set_job_status(conn: sqlite3.Connection, job_id: str, status: str) -> None:
    conn.execute(
        "UPDATE jobs SET status = ? WHERE id = ?",
        (status, job_id),
    )
    conn.commit()


def append_audit(
    conn: sqlite3.Connection,
    *,
    action: str,
    amount: int,
    target: str,
    approver: str,
    phase: str | None = None,
    trace_id: str | None = None,
    tool: str | None = None,
    payload: str | None = None,
    version: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit (
            action, amount, target, approver, phase, trace_id, tool, payload, version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (action, amount, target, approver, phase, trace_id, tool, payload, version),
    )
    conn.commit()


def put_cache(
    conn: sqlite3.Connection,
    *,
    clause_version: str,
    query: str,
    value: str,
) -> None:
    conn.execute(
        """
        INSERT INTO cache (clause_version, query, value)
        VALUES (?, ?, ?)
        ON CONFLICT(clause_version, query) DO UPDATE SET value = excluded.value
        """,
        (clause_version, query, value),
    )
    conn.commit()


def get_cache(
    conn: sqlite3.Connection,
    *,
    clause_version: str,
    query: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT value FROM cache
        WHERE clause_version = ? AND query = ?
        """,
        (clause_version, query),
    ).fetchone()
    if row is None:
        return None
    return str(row["value"])


def count_audit(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM audit").fetchone()
    return int(row["n"])
