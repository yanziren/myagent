from __future__ import annotations

import sqlite3

from pydantic import BaseModel, Field

ALLOWED_STATES = {
    "assigned",
    "running",
    "blocked",
    "completed",
    "failed",
    "timeout",
    "cancelled",
}


class TaskCard(BaseModel):
    task_id: str
    owner: str
    done_when: str
    output_schema: dict[str, str] = Field(default_factory=lambda: {"finding": "str"})
    budget: int = 200
    state: str = "assigned"


def transition(state: str) -> str:
    if state not in ALLOWED_STATES:
        raise ValueError(f"非法状态 {state}")
    return state


def default_cards() -> list[TaskCard]:
    return [
        TaskCard(task_id="T-MED", owner="medical", done_when="给出异常或无异常"),
        TaskCard(task_id="T-CL", owner="clause", done_when="引用条款编号"),
        TaskCard(task_id="T-PR", owner="precedent", done_when="给出判例要点"),
    ]


def claim_job(
    conn: sqlite3.Connection,
    job_id: str,
    owner: str,
    now: int,
    lease_until: int,
) -> int:
    cursor = conn.execute(
        "UPDATE jobs SET owner=?, lease_until=? WHERE id=? AND lease_until < ?",
        (owner, lease_until, job_id, now),
    )
    conn.commit()
    return int(cursor.rowcount)


def run_medical(card: TaskCard, heartbeat: bool) -> dict | None:
    card.state = transition("running")
    if not heartbeat:
        card.state = transition("timeout")
        return None
    card.state = transition("completed")
    return {"finding": "异常", "evidence_id": "E-MED"}


def assemble(cards: list[TaskCard]) -> dict:
    medical = next(card for card in cards if card.owner == "medical")
    if medical.state != "completed":
        return {
            "state": "failed",
            "owner": "medical",
            "text": "无法完成：缺少医学意见",
        }
    return {"state": "completed", "owner": medical.owner, "text": "医学意见已齐"}


def handoff(card: TaskCard, new_owner: str, confirmed: bool) -> TaskCard:
    if confirmed:
        card.owner = new_owner
        card.state = transition("assigned")
    return card
