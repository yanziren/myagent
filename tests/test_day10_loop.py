from __future__ import annotations

import sqlite3
from pathlib import Path

from claimdesk.agent.context import Task
from claimdesk.agent.loop import (
    INVESTIGATE_GOAL,
    INVESTIGATE_PLAN,
    Budget,
    run_agent,
)
from claimdesk.domain.seed import default_world
from claimdesk.store.db import connect, count_idempotency
from claimdesk.tools.errors import ToolFailure


def _task() -> Task:
    return Task(
        claim_id="CLM-2026-1842",
        product="安康住院2024",
        plan=INVESTIGATE_PLAN,
        goal=INVESTIGATE_GOAL,
    )


def test_timeout_two_rounds_backoff_then_block_message():
    prompts: list[str] = []
    calls = {"n": 0}

    def always_timeout(_args, _world=None):
        calls["n"] += 1
        raise ToolFailure("TIMEOUT")

    toolbox = {"get_claim_history": always_timeout}

    def model(prompt: str) -> dict:
        prompts.append(prompt)
        if "必须换策略或声明无法完成" in prompt:
            return {"type": "final", "decision": "无法完成"}
        return {
            "type": "tool",
            "name": "get_claim_history",
            "args": {"policy_no": "POL-1842"},
        }

    result = run_agent(
        _task(),
        model,
        default_world(),
        tools=toolbox,
        budget=Budget(max_steps=8, max_tokens=200_000),
        sleep=lambda _s: None,
    )

    assert result.bill["retries"] == 4
    assert result.bill["backoff"] == [1, 2, 1, 2]
    assert result.bill["blocked_fingerprints"]
    assert any("必须换策略或声明无法完成" in p for p in prompts)
    assert result.suggestion.decision == "无法完成"
    assert calls["n"] == 6


def test_step_cap_with_distinct_fingerprints():
    prompts: list[str] = []

    def model(_prompt: str) -> dict:
        step = len(prompts) + 1
        prompts.append(_prompt)
        return {
            "type": "tool",
            "name": "get_claim_history",
            "args": {"policy_no": f"POL-{step:04d}"},
        }

    result = run_agent(
        _task(),
        model,
        default_world(),
        budget=Budget(max_steps=3, max_tokens=20_000),
        sleep=lambda _s: None,
    )

    assert result.stop_reason == "step_cap"
    assert len(result.trace) <= 3


def test_token_budget_stops_before_model():
    model_calls = {"n": 0}

    def model(_prompt: str) -> dict:
        model_calls["n"] += 1
        return {"type": "final", "decision": "通过"}

    result = run_agent(
        _task(),
        model,
        default_world(),
        budget=Budget(max_steps=8, max_tokens=1),
        sleep=lambda _s: None,
    )

    assert result.stop_reason == "token_budget"
    assert result.trace == []
    assert model_calls["n"] == 0


def test_idempotency_replays_first_result(tmp_path: Path):
    db_path = tmp_path / "claims.sqlite"
    conn = connect(db_path)
    side_effect_runs = {"n": 0}

    def save_draft(_args, _world=None):
        side_effect_runs["n"] += 1
        return "draft-ok-1"

    toolbox = {"save_draft": save_draft}
    prompts: list[str] = []

    def model(prompt: str) -> dict:
        prompts.append(prompt)
        if len(prompts) == 1:
            return {
                "type": "tool",
                "name": "save_draft",
                "args": {"note": "补件说明"},
            }
        if len(prompts) == 2:
            return {
                "type": "tool",
                "name": "save_draft",
                "args": {"note": "补件说明"},
            }
        return {"type": "final", "decision": "复核"}

    result = run_agent(
        _task(),
        model,
        default_world(),
        tools=toolbox,
        job_id="job-demo",
        conn=conn,
        budget=Budget(max_steps=5, max_tokens=20_000),
        sleep=lambda _s: None,
    )

    assert side_effect_runs["n"] == 1
    assert result.bill["retries"] == 0
    assert count_idempotency(conn) == 1
    assert result.trace[0]["text"] == result.trace[1]["text"] == "draft-ok-1"
    conn.close()


def test_param_error_still_zero_retries():
    prompts: list[str] = []

    def model(prompt: str) -> dict:
        prompts.append(prompt)
        if len(prompts) == 1:
            return {
                "type": "tool",
                "name": "get_claim_history",
                "args": {"user_id": "POL-1842"},
            }
        if len(prompts) == 2:
            return {
                "type": "tool",
                "name": "get_claim_history",
                "args": {"policy_no": "POL-1842"},
            }
        return {"type": "final", "decision": "复核", "clause_ids": ["AK-2024-3.1"]}

    result = run_agent(
        _task(),
        model,
        default_world(),
        budget=Budget(max_steps=4, max_tokens=20_000),
        sleep=lambda _s: None,
    )

    assert result.bill["retries"] == 0
    assert result.bill["backoff"] == []
