from __future__ import annotations

import sqlite3

_PRICES = {"none": 0.0, "small": 0.00002, "large": 0.0001}
_LIMIT = 100_000


def complete(
    step: str,
    confidence: float | None = None,
    complained: bool = False,
    *,
    conn: sqlite3.Connection | None = None,
    day_tokens: int = 0,
    limit: int = _LIMIT,
) -> dict:
    if step in {"eligibility", "intake"}:
        return {"tier": "none", "entered_gateway": False, "yuan": 0.0, "limited": False}
    if day_tokens > limit:
        return {"tier": "none", "entered_gateway": False, "yuan": 0.0, "limited": True}
    from claimdesk.routing.router import route

    tier = route(step, confidence=confidence, complained=complained, _via_gateway=True)
    rows = 1
    if step in {"summarize", "extract"} and (complained or (confidence is not None and confidence < 0.8)):
        _write_usage(conn, "small", 200)
        _write_usage(conn, "large", 200)
        rows = 2
        tier = "large"
    else:
        _write_usage(conn, tier, 200)
    return {
        "tier": tier,
        "entered_gateway": True,
        "yuan": _PRICES[tier],
        "limited": False,
        "usage_rows": rows,
    }


def _write_usage(conn: sqlite3.Connection | None, tier: str, tokens: int) -> None:
    if conn is None or tier == "none":
        return
    conn.execute(
        """
        INSERT INTO usage (path, tokens, yuan, created_on)
        VALUES (?, ?, ?, 'gateway')
        """,
        (tier, tokens, tokens * _PRICES[tier]),
    )
    conn.commit()


def online_answer(online_clause: str, shadow_clause: str, conn: sqlite3.Connection) -> dict:
    from claimdesk.store.db import append_audit

    append_audit(
        conn,
        action="shadow",
        amount=0,
        target="clause",
        approver="gateway",
        phase="shadow",
        payload=shadow_clause,
    )
    return {"decision": "复核", "clause_ids": [online_clause]}
