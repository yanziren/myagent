from __future__ import annotations

from claimdesk.agent.context import Task, render_context
from claimdesk.agent.loop import (
    INVESTIGATE_GOAL,
    INVESTIGATE_PLAN,
    format_trace,
    run_agent,
)
from claimdesk.domain.seed import default_world
from claimdesk.tools.catalog import expand_tool, list_tools_for_intent
from claimdesk.tools.errors import ToolError
from claimdesk.tools.schemas import (
    get_claim,
    get_claim_history,
    get_policy,
    tool_spec,
)


def test_tool_spec_get_claim_history_is_read_with_schema_example():
    spec = tool_spec("get_claim_history")
    assert spec["side_effect"] == "read"
    assert spec["retryable"] is True
    assert "policy_no" in spec["schema"]
    assert "POL-1842" in spec["schema"]


def test_user_id_without_policy_no_is_param_error():
    result = get_claim_history({"user_id": "POL-1842"}, default_world())
    assert isinstance(result, ToolError)
    assert result.code == "PARAM_USER_ID"
    assert result.retryable is False
    assert result.kind == "param"
    assert "policy_no" in result.suggestion


def test_policy_no_finds_clm_1831():
    result = get_claim_history({"policy_no": "POL-1842"}, default_world())
    assert isinstance(result, str)
    assert "CLM-2026-1831" in result


def test_get_policy_missing_is_execution_not_param():
    result = get_policy({"policy_no": "POL-NOPE"}, default_world())
    assert isinstance(result, ToolError)
    assert result.kind == "execution"
    assert result.retryable is False
    assert result.code == "POLICY_NOT_FOUND"


def test_linxiao_cannot_view_other_claim():
    result = get_claim(
        {"claim_id": "CLM-2026-0901"},
        default_world(),
        actor_id="intruder",
    )
    assert isinstance(result, ToolError)
    assert result.kind == "param"
    assert result.code == "FORBIDDEN_CLAIM"


def test_catalog_eligibility_has_no_investigate_tools():
    tools = list_tools_for_intent("eligibility")
    assert tools and "get_claim_history" not in str(tools)


def test_investigate_catalog_expands_on_second_round():
    task = Task(
        claim_id="CLM-2026-1842",
        product="安康住院2024",
        plan=INVESTIGATE_PLAN,
        goal=INVESTIGATE_GOAL,
    )
    round1 = render_context(task, [], intent="investigate", tool_round=1)
    assert "POL-1842" not in round1
    round2 = render_context(
        task,
        [],
        intent="investigate",
        expanded_tools={"get_claim_history"},
        tool_round=2,
    )
    assert "POL-1842" in round2
    assert expand_tool("get_claim_history")["schema"] in round2


def test_param_error_then_policy_no_in_agent_loop():
    prompts: list[str] = []

    def model(prompt: str) -> dict:
        prompts.append(prompt)
        step = len(prompts)
        if step == 1:
            return {
                "type": "tool",
                "name": "get_claim_history",
                "args": {"user_id": "POL-1842"},
            }
        if step == 2:
            assert "PARAM_USER_ID" in prompt
            return {
                "type": "tool",
                "name": "get_claim_history",
                "args": {"policy_no": "POL-1842"},
            }
        assert "CLM-2026-1831" in prompt
        return {
            "type": "final",
            "decision": "复核",
            "clause_ids": ["AK-2024-3.1"],
        }

    result = run_agent(
        Task(
            claim_id="CLM-2026-1842",
            product="安康住院2024",
            plan=INVESTIGATE_PLAN,
            goal=INVESTIGATE_GOAL,
        ),
        model,
        default_world(),
        actor_id="linxiao",
        intent="investigate",
    )

    assert result.bill["retries"] == 0
    assert result.bill["backoff"] == []
    assert any(event["kind"] == "param" for event in result.events)
    assert any(event["kind"] == "ok" for event in result.events)
    assert result.suggestion.decision == "复核"
    assert "CLM-2026-1831" in format_trace(result.trace)


def test_execution_500_stops_with_no_param_events():
    prompts: list[str] = []

    def model(prompt: str) -> dict:
        prompts.append(prompt)
        if len(prompts) == 1:
            return {"type": "tool", "name": "500", "args": {}}
        assert "HTTP_500" in prompt
        return {"type": "final", "decision": "无法完成"}

    result = run_agent(
        Task(
            claim_id="CLM-2026-1842",
            product="安康住院2024",
            plan=INVESTIGATE_PLAN,
            goal=INVESTIGATE_GOAL,
        ),
        model,
        default_world(),
        actor_id="linxiao",
        intent="investigate",
        sleep=lambda _s: None,
    )

    assert result.suggestion.decision == "无法完成"
    assert all(event["kind"] != "param" for event in result.events)
    assert any(
        event["kind"] == "execution" and event["code"] == "HTTP_500"
        for event in result.events
    )
    assert result.bill["retries"] == 2
    assert result.bill["backoff"] == [1, 2]


