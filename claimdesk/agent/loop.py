from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from claimdesk.agent.context import Task, render_context
from claimdesk.agent.memory import EntitySidecar, persist_sidecar
from claimdesk.domain.models import TENANT, Suggestion
from claimdesk.domain.seed import World
from claimdesk.store.db import (
    complete_idempotency,
    connect,
    delete_idempotency,
    get_idempotency_result,
    idempotency_key,
    insert_idempotency_intended,
)
from claimdesk.tools.errors import ToolError, ToolFailure
from claimdesk.tools.schemas import (
    _format_tool_error,
    default_tools,
    invoke_tool,
    tool_spec,
)

INVESTIGATE_PLAN = "计划：先查历史案件，再按返回决定检索词。"
INVESTIGATE_GOAL = "对开放协查给出建议，决定权在核赔人。"
MAX_STEPS = 8
BLOCK_MESSAGE = "必须换策略或声明无法完成"
RETRYABLE_FAILURES = {"TIMEOUT", "429", "500", "502", "503"}


class Budget(BaseModel):
    max_steps: int = 8
    max_tokens: int = 20000
    price_per_token: float = 0.0001


class RunResult(BaseModel):
    suggestion: Suggestion
    claim_id: str = ""
    product: str = ""
    steps: int = 0
    model_calls: int = 0
    stop_reason: str = ""
    trace: list[dict[str, Any]] = Field(default_factory=list)
    job_id: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    bill: dict[str, Any] = Field(
        default_factory=lambda: {"retries": 0, "backoff": [], "blocked_fingerprints": []}
    )


def format_trace(trace: list[dict]) -> str:
    return "\n".join(f"{step['tool']}: {step['text']}" for step in trace)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _as_action(raw: Any) -> dict:
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _execution_code(raw: str) -> str:
    if raw in RETRYABLE_FAILURES:
        return f"HTTP_{raw}" if raw.isdigit() else raw
    return raw


def _is_retryable_failure(code: str) -> bool:
    if code in RETRYABLE_FAILURES:
        return True
    if code.startswith("HTTP_") and code[5:] in {"500", "502", "503", "429"}:
        return True
    return code == "TIMEOUT"


def _tool_fingerprint(name: str, args: dict) -> str:
    return f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"


def _side_effect(name: str) -> str:
    try:
        return str(tool_spec(name)["side_effect"])
    except KeyError:
        return "read"


def _call_tool(
    name: str,
    args: dict,
    *,
    actor_id: str,
    world: World,
    legacy: bool,
    toolbox: dict,
    bill: dict[str, Any],
    conn: sqlite3.Connection | None,
    job_id: str | None,
    sleep: Callable[[float], None],
) -> str | ToolError:
    side = _side_effect(name)
    idem_key: str | None = None
    if side != "read" and conn is not None and job_id:
        idem_key = idempotency_key(job_id, name, args)
        cached = get_idempotency_result(conn, idem_key)
        if cached is not None:
            return cached
        insert_idempotency_intended(conn, idem_key)

    delays: list[int] = []
    last_error: ToolError | None = None

    for attempt in range(3):
        try:
            if legacy:
                outcome = toolbox[name](args, world)
            else:
                outcome = invoke_tool(name, args, actor_id=actor_id, world=world)
        except ToolFailure as failure:
            code = _execution_code(failure.code)
            last_error = ToolError(
                code=code,
                message=failure.message,
                retryable=True,
                suggestion="瞬时错误可机械重试。",
                kind="execution",
            )
            if attempt < 2 and _is_retryable_failure(failure.code):
                delay = 1 if attempt == 0 else 2
                delays.append(delay)
                sleep(delay)
                continue
            break
        else:
            if isinstance(outcome, ToolError):
                if outcome.kind == "param" and idem_key and conn is not None:
                    delete_idempotency(conn, idem_key)
                bill["retries"] += len(delays)
                bill["backoff"].extend(delays)
                return outcome
            if idem_key and conn is not None:
                complete_idempotency(conn, idem_key, outcome)
            bill["retries"] += len(delays)
            bill["backoff"].extend(delays)
            return outcome

    bill["retries"] += len(delays)
    bill["backoff"].extend(delays)
    if last_error is not None:
        return last_error
    return ToolError(
        code="EXECUTION_FAILED",
        message="工具执行失败。",
        retryable=False,
        suggestion="请换策略或声明无法完成。",
        kind="execution",
    )


def _sidecar_for(task: Task, world: World) -> EntitySidecar:
    policy_no = ""
    try:
        policy_no = world.policy_of(task.claim_id).policy_no
    except KeyError:
        policy_no = ""
    return EntitySidecar(
        claim_id=task.claim_id,
        product=task.product,
        policy_no=policy_no,
        clause_version=getattr(world, "clause_version", "") or "",
    )


def run_agent(
    task: Task,
    model,
    world: World,
    tools: dict | None = None,
    *,
    actor_id: str = "linxiao",
    intent: str = "investigate",
    budget: Budget | None = None,
    job_id: str | None = None,
    conn: sqlite3.Connection | None = None,
    sleep: Callable[[float], None] | None = None,
) -> RunResult:
    budget = budget or Budget(max_steps=MAX_STEPS, max_tokens=20000)
    sleeper = sleep if sleep is not None else time.sleep
    legacy = tools is not None
    toolbox = tools if tools is not None else default_tools()
    memory_conn = conn if conn is not None else connect(":memory:")
    observations: list[dict] = []
    trace: list[dict] = []
    events: list[dict] = []
    bill: dict[str, Any] = {"retries": 0, "backoff": [], "blocked_fingerprints": []}
    expanded_tools: set[str] = set()
    tool_round = 0
    fingerprint_hits: dict[str, int] = {}
    model_calls = 0

    def finish(
        *,
        decision: str,
        stop_reason: str,
        clause_ids: list[str] | None = None,
        rationale: str,
    ) -> RunResult:
        return RunResult(
            suggestion=Suggestion(
                decision=decision,
                clause_ids=list(clause_ids or []),
                model_calls=model_calls,
                rationale=rationale,
            ),
            claim_id=task.claim_id,
            product=task.product,
            steps=len(trace),
            model_calls=model_calls,
            stop_reason=stop_reason,
            trace=trace,
            events=events,
            bill=bill,
            job_id=job_id,
        )

    try:
        persist_sidecar(_sidecar_for(task, world), conn=memory_conn, tenant_id=TENANT)
        for _step in range(budget.max_steps):
            tool_round += 1
            prompt = render_context(
                task,
                observations,
                intent=intent,
                expanded_tools=expanded_tools,
                tool_round=tool_round,
                conn=memory_conn,
                tenant_id=TENANT,
            )
            if estimate_tokens(prompt) > budget.max_tokens:
                return finish(
                    decision="无法判断",
                    stop_reason="token_budget",
                    rationale="上下文 token 预算已用尽。",
                )

            action = _as_action(model(prompt))
            model_calls += 1
            if action.get("type") == "final":
                decision = str(action.get("decision", "无法判断"))
                return finish(
                    decision=decision,
                    stop_reason="final",
                    clause_ids=list(action.get("clause_ids") or []),
                    rationale=(
                        f"案件{task.claim_id}，产品{task.product}，"
                        f"开放协查结束，建议{decision}。"
                    ),
                )
            if action.get("type") != "tool":
                return finish(
                    decision="无法判断",
                    stop_reason="unknown",
                    rationale="模型没有返回工具或最终建议。",
                )

            name = str(action.get("name", ""))
            args = dict(action.get("args") or {})
            try:
                tool_spec(name)
                expanded_tools.add(name)
            except KeyError:
                pass

            fingerprint = _tool_fingerprint(name, args)
            fingerprint_hits[fingerprint] = fingerprint_hits.get(fingerprint, 0) + 1
            if fingerprint_hits[fingerprint] >= 3:
                bill.setdefault("blocked_fingerprints", []).append(fingerprint)
                text = BLOCK_MESSAGE
                events.append({"tool": name, "kind": "blocked", "code": "FINGERPRINT"})
                step = {"tool": name, "args": args, "text": text}
                trace.append(step)
                observations.append({"tool": name, "text": text})
                continue

            outcome = _call_tool(
                name,
                args,
                actor_id=actor_id,
                world=world,
                legacy=legacy,
                toolbox=toolbox,
                bill=bill,
                conn=conn,
                job_id=job_id,
                sleep=sleeper,
            )

            if isinstance(outcome, ToolError):
                text = _format_tool_error(outcome)
                events.append(
                    {
                        "tool": name,
                        "kind": outcome.kind,
                        "code": outcome.code,
                    }
                )
            else:
                text = outcome
                events.append({"tool": name, "kind": "ok", "code": ""})

            step = {"tool": name, "args": args, "text": text}
            trace.append(step)
            observations.append({"tool": name, "text": text})

        return finish(
            decision="无法判断",
            stop_reason="step_cap",
            rationale="协查步数已用完。",
        )
    finally:
        if conn is None:
            memory_conn.close()
