from __future__ import annotations

import sqlite3


class SmsLog:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def write_intent(self, idem: str, recipient: str, body: str, claim_id: str) -> None:
        self.rows.setdefault(idem, {})["intent"] = {
            "recipient": recipient,
            "body": body,
            "claim_id": claim_id,
        }


def resume_send(log: SmsLog, idem: str, send_fn, already_sent) -> None:
    row = log.rows.get(idem)
    if row is None or "intent" not in row:
        return
    if row.get("result") == "sent":
        return
    if already_sent(idem):
        row["result"] = "sent"
        return
    send_fn()
    row["result"] = "sent"


def resume_if_not_done(conn: sqlite3.Connection, idem: str, send_fn) -> bool:
    row = conn.execute(
        "SELECT status FROM idempotency WHERE key = ?",
        (idem,),
    ).fetchone()
    if row is not None and row["status"] == "done":
        return False
    send_fn()
    return True


def save_checkpoint(
    conn: sqlite3.Connection,
    job_id: str,
    step: int,
    side_effect_keys: list[str],
) -> None:
    for key in side_effect_keys:
        conn.execute(
            """
            INSERT INTO checkpoints (job_id, step, side_effect_key)
            VALUES (?, ?, ?)
            ON CONFLICT(job_id, side_effect_key) DO UPDATE SET step = excluded.step
            """,
            (job_id, step, key),
        )
    conn.commit()


def remaining_side_effects(
    conn: sqlite3.Connection,
    job_id: str,
    pending: list[str],
) -> list[str]:
    rows = conn.execute(
        "SELECT side_effect_key FROM checkpoints WHERE job_id = ?",
        (job_id,),
    ).fetchall()
    done = {row["side_effect_key"] for row in rows}
    return [key for key in pending if key not in done]


def restore(checkpoint: dict) -> dict:
    return {
        key: checkpoint[key]
        for key in ("goal", "plan", "done", "recent")
        if key in checkpoint
    }


def reconcile(plan: str, observed_waiting_days: int, checkpoint_waiting_days: int) -> str:
    if observed_waiting_days == checkpoint_waiting_days:
        return plan
    return f"重新观察：等待期已是 {observed_waiting_days} 日。原计划暂停。"
