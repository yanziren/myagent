from __future__ import annotations

import sqlite3
from uuid import uuid4

from claimdesk.agent.loop import (
    INVESTIGATE_GOAL,
    INVESTIGATE_PLAN,
    RunResult,
    Task,
    run_agent,
)
from claimdesk.domain.models import DeskRequest, Suggestion
from claimdesk.domain.seed import World
from claimdesk.store.db import complete_job, insert_job, next_accepted_job
from claimdesk.workflow.intake import run_intake


def handle(
    world: World,
    request: DeskRequest,
    model,
    conn: sqlite3.Connection | None = None,
) -> RunResult:
    if request.intent == "eligibility":
        suggestion = run_intake(world, request.claim_id)
        return RunResult(
            suggestion=suggestion,
            steps=0,
            model_calls=0,
            stop_reason="rules",
        )
    if request.intent == "investigate":
        job_id = None
        if conn is not None:
            job_id = uuid4().hex
            insert_job(
                conn,
                job_id=job_id,
                claim_id=request.claim_id,
                intent=request.intent,
            )
        return RunResult(
            suggestion=Suggestion(decision="已入队", model_calls=0),
            steps=0,
            model_calls=0,
            stop_reason="queued",
            job_id=job_id,
        )
    return RunResult(
        suggestion=Suggestion(
            decision="无法判断",
            model_calls=0,
            rationale="未知意图，不进入协查循环。",
        ),
        steps=0,
        model_calls=0,
        stop_reason="unknown",
    )


def drain_once(conn: sqlite3.Connection, world: World, model) -> RunResult:
    row = next_accepted_job(conn)
    if row is None:
        raise RuntimeError("no accepted investigation")
    claim = world.claim_of(row["claim_id"])
    result = run_agent(
        Task(
            claim_id=claim.claim_id,
            product=claim.product,
            plan=INVESTIGATE_PLAN,
            goal=INVESTIGATE_GOAL,
        ),
        model,
        world,
        job_id=row["id"],
        conn=conn,
    )
    complete_job(conn, row["id"])
    result.job_id = row["id"]
    return result
