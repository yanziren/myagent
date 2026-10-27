from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from claimdesk.agent.loop import Budget
from claimdesk.store.db import connect


@dataclass
class StepBill:
    ts: int
    prompt_tokens: int
    completion_tokens: int = 0
    tool: str = ""
    new_evidence: bool = False
    cache_hit: bool = False
    piece: str = "system"


def attribute(steps: list[StepBill], price_per_token: float | None = None) -> dict:
    price = Budget().price_per_token if price_per_token is None else price_per_token
    by_hour: dict[int, float] = {}
    piece_tokens: dict[str, int] = {}
    prompt_total = 0
    for step in steps:
        tokens = step.prompt_tokens + step.completion_tokens
        yuan = tokens * price
        hour = step.ts // 3600
        by_hour[hour] = by_hour.get(hour, 0.0) + yuan
        piece_tokens[step.piece] = piece_tokens.get(step.piece, 0) + step.prompt_tokens
        prompt_total += step.prompt_tokens
    largest = max(piece_tokens, key=piece_tokens.get) if piece_tokens else ""
    behavior = ""
    run = 0
    previous = None
    for step in steps:
        if step.tool == previous and not step.new_evidence and step.tool:
            run += 1
        else:
            run = 0 if step.new_evidence or not step.tool else 1
            previous = step.tool
        if run >= 3 and not step.new_evidence:
            behavior = "no_progress"
    later = sum(step.prompt_tokens for step in steps[2:])
    later_ratio = later / prompt_total if prompt_total else 0.0
    conclusion = ""
    if later_ratio > 0.7 and behavior == "no_progress":
        conclusion = "70% 以上的 token 来自第 3 步之后的历史全文重试，缓存未命中。"
    return {
        "by_hour": by_hour,
        "step_count": len(steps),
        "mean_prompt_tokens": prompt_total / len(steps) if steps else 0,
        "largest_piece": largest,
        "behavior": behavior,
        "later_ratio": later_ratio,
        "conclusion": conclusion,
    }


def record_usage(
    conn: sqlite3.Connection,
    path: str,
    tokens: int,
    yuan: float,
    created_on: str,
) -> None:
    amount = 0.0 if path == "eligibility" else yuan
    conn.execute(
        """
        INSERT INTO usage (path, tokens, yuan, created_on)
        VALUES (?, ?, ?, ?)
        """,
        (path, tokens, amount, created_on),
    )
    conn.commit()


def sum_yuan(conn: sqlite3.Connection, day: str) -> dict:
    rows = conn.execute(
        "SELECT path, yuan FROM usage WHERE created_on = ?",
        (day,),
    ).fetchall()
    total = sum(float(row["yuan"]) for row in rows)
    flagged = any(row["path"] == "dispute" and float(row["yuan"]) > 50 for row in rows)
    return {"total": total, "over_soft": total > 50, "flagged": flagged or total > 50}
