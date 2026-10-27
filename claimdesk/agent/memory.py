from __future__ import annotations

import sqlite3

from pydantic import BaseModel

MEMORY_DDL = """
CREATE TABLE IF NOT EXISTS memory (
    tenant_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (tenant_id, claim_id, key)
);
"""

_FACT_KEYS = {
    "claim_id": "claim_id",
    "案件号": "claim_id",
    "product": "product",
    "产品": "product",
    "policy_no": "policy_no",
    "保单号": "policy_no",
    "clause_version": "clause_version",
    "条款版本": "clause_version",
}


class MemoryError(ValueError):
    """A fact write was rejected, or a memory query had no tenant."""


class EntitySidecar(BaseModel):
    claim_id: str
    product: str
    policy_no: str
    clause_version: str


def ensure_memory(conn: sqlite3.Connection) -> None:
    conn.executescript(MEMORY_DDL)


def remember_fact(
    claim_id: str,
    key: str,
    value: str,
    *,
    conn: sqlite3.Connection,
    tenant_id: str | None,
) -> None:
    if not tenant_id:
        raise MemoryError("写入必须带 tenant_id")
    if key.startswith("infer_") or key.startswith("推断"):
        raise MemoryError("推断不能写入长期记忆")
    canonical = _FACT_KEYS.get(key)
    if canonical is None:
        raise MemoryError("只接受案件号、产品、保单号、条款版本")
    text = str(value)
    if text.startswith("infer_") or text.startswith("推断"):
        raise MemoryError("带推断标记的写入被拒绝")
    ensure_memory(conn)
    conn.execute(
        """
        INSERT INTO memory (tenant_id, claim_id, key, value)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tenant_id, claim_id, key) DO UPDATE SET
            value = excluded.value
        """,
        (tenant_id, claim_id, canonical, text),
    )
    conn.commit()


def load_facts(
    claim_id: str,
    *,
    conn: sqlite3.Connection,
    tenant_id: str | None,
) -> dict[str, str]:
    if not tenant_id:
        raise MemoryError("查询必须带 tenant_id")
    ensure_memory(conn)
    rows = conn.execute(
        """
        SELECT key, value FROM memory
        WHERE tenant_id = ? AND claim_id = ?
        """,
        (tenant_id, claim_id),
    ).fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}


def persist_sidecar(
    sidecar: EntitySidecar,
    *,
    conn: sqlite3.Connection,
    tenant_id: str,
) -> None:
    fields = {
        "claim_id": sidecar.claim_id,
        "product": sidecar.product,
        "policy_no": sidecar.policy_no,
        "clause_version": sidecar.clause_version,
    }
    for key, value in fields.items():
        if value:
            remember_fact(
                sidecar.claim_id,
                key,
                value,
                conn=conn,
                tenant_id=tenant_id,
            )
