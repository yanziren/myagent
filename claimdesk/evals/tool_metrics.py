from __future__ import annotations

import json
import sqlite3


def summarize(events: list[dict]) -> dict:
    total = len(events) or 1
    global_success = sum(event["kind"] == "ok" for event in events) / total
    by_tool: dict[str, dict] = {}
    by_model_counts: dict[str, list[int]] = {}
    for event in events:
        tool = event["tool"]
        slot = by_tool.setdefault(
            tool,
            {"calls": 0, "param": 0, "timeout": 0, "illegal": 0, "ok": 0},
        )
        slot["calls"] += 1
        kind = event["kind"]
        if kind in slot:
            slot[kind] += 1
        model = event.get("model", "")
        bucket = by_model_counts.setdefault(model, [0, 0])
        bucket[1] += 1
        if kind == "ok":
            bucket[0] += 1
    rendered = {}
    for tool, slot in by_tool.items():
        calls = slot["calls"] or 1
        rendered[tool] = {
            "calls": slot["calls"],
            "param_error_rate": slot["param"] / calls,
            "timeout_rate": slot["timeout"] / calls,
            "illegal_rate": slot["illegal"] / calls,
        }
    by_model = {
        model: {"success": ok / count if count else 0.0}
        for model, (ok, count) in by_model_counts.items()
    }
    return {
        "global_success": global_success,
        "by_tool": rendered,
        "by_model": by_model,
    }


def summarize_audit(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT tool, payload FROM audit
        WHERE tool IS NOT NULL AND tool != '' AND payload IS NOT NULL
        """
    ).fetchall()
    events = []
    for row in rows:
        payload = json.loads(row["payload"])
        events.append({"tool": row["tool"], "kind": payload["kind"], "model": payload.get("model", "")})
    return summarize(events)
