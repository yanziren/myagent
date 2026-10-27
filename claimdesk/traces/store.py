from __future__ import annotations

import json
import sqlite3

from claimdesk.store.db import append_audit


class TraceStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._next = 0

    def start(self) -> str:
        self._next += 1
        return f"tr-{self._next}"

    def note_intent(self, trace_id: str, tool: str, payload: dict) -> None:
        append_audit(
            self.conn,
            action="tool",
            amount=0,
            target=trace_id,
            approver="trace",
            phase="intent",
            trace_id=trace_id,
            tool=tool,
            payload=json.dumps(payload, ensure_ascii=False),
        )

    def intents(self, trace_id: str) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT tool FROM audit
            WHERE trace_id = ? AND phase = 'intent'
            ORDER BY id
            """,
            (trace_id,),
        ).fetchall()
        return [row["tool"] for row in rows]

    def record(self, trace_id: str, **event) -> None:
        append_audit(
            self.conn,
            action="tool",
            amount=0,
            target=trace_id,
            approver="trace",
            phase="result",
            trace_id=trace_id,
            tool=str(event.get("tool", "")),
            payload=json.dumps(event, ensure_ascii=False),
        )

    def events(self, trace_id: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT payload FROM audit
            WHERE trace_id = ? AND phase = 'result'
            ORDER BY id
            """,
            (trace_id,),
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def checkpoint(self, trace_id: str, state: dict) -> None:
        append_audit(
            self.conn,
            action="checkpoint",
            amount=0,
            target=trace_id,
            approver="trace",
            phase="checkpoint",
            trace_id=trace_id,
            tool="",
            payload=json.dumps(state, ensure_ascii=False),
        )

    def checkpoints(self, trace_id: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT payload FROM audit
            WHERE trace_id = ? AND phase = 'checkpoint'
            ORDER BY id
            """,
            (trace_id,),
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def replay(self, trace_id: str, live) -> list[str]:
        del live
        return [event["tool"] for event in self.events(trace_id)]

    def first_divergence(self, trace_id: str, expected: list[str]) -> dict:
        actual = self.replay(trace_id, None)
        for index, (want, got) in enumerate(zip(expected, actual)):
            if want != got:
                return {"index": index, "actual": got}
        if len(actual) != len(expected):
            return {"index": min(len(actual), len(expected)), "actual": ""}
        return {"index": -1, "actual": ""}


def score_outcome(actual: str, expected: str) -> bool:
    return actual == expected


def trajectory_violations(steps: list[dict]) -> set[str]:
    marks: set[str] = set()
    counts: dict[str, int] = {}
    for step in steps:
        if step.get("tool") == "send_sms" and not step.get("approved"):
            marks.add("unauthorized")
        fingerprint = step.get("fingerprint")
        if fingerprint:
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
        if step.get("decision") == "通过" and not step.get("evidence_ids"):
            marks.add("no_evidence")
    if any(count >= 3 for count in counts.values()):
        marks.add("loop")
    return marks
