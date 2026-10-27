"""Day 12: restate the claim, compress old observations, bind the result to the task."""

from pathlib import Path

import pytest

from claimdesk.agent.context import MAX_CONTEXT_CHARS, MAX_OBS, Task, render_context
from claimdesk.agent.loop import (
    INVESTIGATE_GOAL,
    INVESTIGATE_PLAN,
    Budget,
    run_agent,
)
from claimdesk.agent.memory import EntitySidecar, MemoryError, remember_fact
from claimdesk.domain.seed import default_world
from claimdesk.store.db import connect

TENANT = "anlan-chengdu"


def _task(**overrides) -> Task:
    fields = {
        "claim_id": "CLM-2026-1842",
        "product": "安康住院2024",
        "plan": INVESTIGATE_PLAN,
        "goal": INVESTIGATE_GOAL,
    }
    fields.update(overrides)
    return Task(**fields)


def test_memory_stores_only_claim_facts_for_the_tenant(tmp_path: Path):
    conn = connect(tmp_path / "memory.sqlite")
    remember_fact(
        "CLM-2026-1842",
        "product",
        "安康住院2024",
        conn=conn,
        tenant_id=TENANT,
    )
    remember_fact(
        "CLM-2026-1842",
        "policy_no",
        "POL-1842",
        conn=conn,
        tenant_id=TENANT,
    )
    remember_fact(
        "CLM-2026-1842",
        "clause_version",
        "V3",
        conn=conn,
        tenant_id=TENANT,
    )

    with pytest.raises(MemoryError):
        remember_fact(
            "CLM-2026-1842",
            "infer_decision",
            "车险划痕",
            conn=conn,
            tenant_id=TENANT,
        )
    with pytest.raises(MemoryError):
        remember_fact(
            "CLM-2026-1842",
            "hospital",
            "市三医院",
            conn=conn,
            tenant_id=TENANT,
        )
    with pytest.raises(MemoryError):
        remember_fact(
            "CLM-2026-1842",
            "product",
            "安康住院2024",
            conn=conn,
            tenant_id="",
        )

    rows = conn.execute(
        "SELECT tenant_id, key, value FROM memory ORDER BY key"
    ).fetchall()
    assert [(row["key"], row["value"]) for row in rows] == [
        ("clause_version", "V3"),
        ("policy_no", "POL-1842"),
        ("product", "安康住院2024"),
    ]
    assert {row["tenant_id"] for row in rows} == {TENANT}

    other = conn.execute(
        "SELECT value FROM memory WHERE tenant_id = ? AND key = ?",
        ("other-tenant", "product"),
    ).fetchone()
    assert other is None

    with pytest.raises(MemoryError):
        render_context(_task(product="车险"), [], conn=conn, tenant_id="")


def test_context_header_reads_product_from_memory_not_the_model(tmp_path: Path):
    conn = connect(tmp_path / "memory.sqlite")
    remember_fact(
        "CLM-2026-1842",
        "claim_id",
        "CLM-2026-1842",
        conn=conn,
        tenant_id=TENANT,
    )
    remember_fact(
        "CLM-2026-1842",
        "product",
        "安康住院2024",
        conn=conn,
        tenant_id=TENANT,
    )
    remember_fact(
        "CLM-2026-1842",
        "policy_no",
        "POL-1842",
        conn=conn,
        tenant_id=TENANT,
    )
    remember_fact(
        "CLM-2026-1842",
        "clause_version",
        "V3",
        conn=conn,
        tenant_id=TENANT,
    )

    prompt = render_context(
        _task(product="车险"),
        [],
        conn=conn,
        tenant_id=TENANT,
        intent="none",
    )
    lines = prompt.splitlines()
    assert lines[0] == "案件：CLM-2026-1842"
    assert lines[1] == "产品：安康住院2024"
    assert lines[2].startswith("计划：")
    assert "计划" in lines[2]
    assert lines[3].startswith("目标：")
    assert "车险" not in prompt
    assert "POL-1842" in prompt
    assert "V3" in prompt


def test_old_observations_collapse_and_recent_text_is_truncated():
    sidecar = EntitySidecar(
        claim_id="CLM-2026-1842",
        product="安康住院2024",
        policy_no="POL-1842",
        clause_version="V3",
    )
    observations = [
        {"tool": "echo", "text": "UNIQUE_OLD" + ("费用明细" * 80)},
        {"tool": "search", "text": "较早全文不应留下"},
        {"tool": "echo", "text": "UNIQUE_NEW" + ("费" * 400)},
        {"tool": "echo", "text": "UNIQUE_NEW" + ("明细" * 400)},
    ]

    prompt = render_context(
        _task(),
        observations,
        sidecar=sidecar,
        intent="none",
    )

    summary = next(line for line in prompt.splitlines() if line.startswith("较早观察摘要:"))
    assert summary == "较早观察摘要: echo、search"
    assert "POL-1842" not in summary
    assert "V3" not in summary
    assert sidecar.claim_id not in summary
    assert "UNIQUE_OLD" not in prompt
    assert "较早全文不应留下" not in prompt
    assert "UNIQUE_NEW" in prompt
    assert "费" * (MAX_OBS + 1) not in prompt
    assert MAX_OBS == 160
    assert len(prompt) <= MAX_CONTEXT_CHARS
    assert MAX_CONTEXT_CHARS == 1800
    assert "保单：POL-1842" in prompt
    assert "条款版本：V3" in prompt


def test_assembled_prompt_stays_within_the_hard_cap():
    observations = [{"tool": "N" * 180, "text": "旧" * 300} for _ in range(20)]
    observations.append({"tool": "echo", "text": "费" * 5000})
    observations.append({"tool": "echo", "text": "费" * 5000})

    prompt = render_context(_task(), observations, intent="none")

    assert len(prompt) <= 1800
    assert prompt.startswith("案件：CLM-2026-1842\n产品：安康住院2024\n")
    assert "计划" in prompt.splitlines()[2]


def test_long_echo_loop_restates_claim_and_ignores_model_product(tmp_path: Path):
    conn = connect(tmp_path / "loop.sqlite")
    remember_fact(
        "CLM-2026-1842",
        "product",
        "车险",
        conn=conn,
        tenant_id=TENANT,
    )
    prompts: list[str] = []

    def echo(args, _world=None):
        return str(args["detail"])

    def model(prompt: str) -> dict:
        prompts.append(prompt)
        step = len(prompts)
        if step <= 15:
            marker = ""
            if step == 1:
                marker = "UNIQUE_OLD"
            elif step >= 14:
                marker = "UNIQUE_NEW"
            detail = f"{marker}S{step}{'费用明细' * 80}"
            return {"type": "tool", "name": "echo", "args": {"detail": detail}}
        assert "CLM-2026-1842" in prompt
        assert "安康住院2024" in prompt
        assert "计划" in prompt
        assert "UNIQUE_NEW" in prompt
        assert "UNIQUE_OLD" not in prompt
        assert "车险" not in prompt
        assert len(prompt) <= MAX_CONTEXT_CHARS
        return {
            "type": "final",
            "decision": "通过",
            "product": "车险",
            "claim_id": "CLM-CAR",
        }

    result = run_agent(
        _task(),
        model,
        default_world(),
        tools={"echo": echo},
        budget=Budget(max_steps=20, max_tokens=200_000),
        conn=conn,
        job_id="job-day12",
    )

    assert len(prompts) == 16
    assert all("CLM-2026-1842" in prompt for prompt in prompts)
    assert all("安康住院2024" in prompt for prompt in prompts)
    assert all("计划" in prompt for prompt in prompts)
    assert all("车险" not in prompt for prompt in prompts)
    assert result.claim_id == "CLM-2026-1842"
    assert result.product == "安康住院2024"
    assert result.suggestion.decision == "通过"
    assert "CLM-2026-1842" in result.suggestion.rationale
    assert "安康住院2024" in result.suggestion.rationale
    assert "车险" not in result.suggestion.rationale
    assert "CLM-CAR" not in result.suggestion.rationale

    stored = conn.execute(
        """
        SELECT key, value FROM memory
        WHERE tenant_id = ? AND claim_id = ?
        ORDER BY key
        """,
        (TENANT, "CLM-2026-1842"),
    ).fetchall()
    facts = {row["key"]: row["value"] for row in stored}
    assert facts["claim_id"] == "CLM-2026-1842"
    assert facts["product"] == "安康住院2024"
    assert facts["policy_no"] == "POL-1842"
    assert facts["clause_version"] == "V3"
    leaked = conn.execute(
        "SELECT value FROM memory WHERE value IN ('车险', 'CLM-CAR')"
    ).fetchall()
    assert leaked == []
