from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from claimdesk.domain.seed import World, default_world
from claimdesk.rag.hybrid import answer_clause_hybrid
from claimdesk.tools.errors import ToolError, ToolFailure

# 专员可见案件（服务端鉴权，不进 Prompt）
ACTOR_VISIBLE_CLAIMS: dict[str, frozenset[str]] = {
    "linxiao": frozenset(
        {
            "CLM-2026-0901",
            "CLM-2026-0777",
            "CLM-2026-1842",
            "CLM-2026-1831",
        }
    ),
}


class HistoryArgs(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"policy_no": "POL-1842"}]})

    policy_no: str | None = Field(default=None, description="保单号，例如 POL-1842")
    user_id: str | None = Field(
        default=None,
        description="用户标识；不要在此字段填写保单号，应使用 policy_no",
    )


class PolicyArgs(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"policy_no": "POL-1842"}]})

    policy_no: str = Field(description="保单号")


class ClaimArgs(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"claim_id": "CLM-2026-1842"}]})

    claim_id: str = Field(description="案件号")


def tool_spec(name: str) -> dict:
    if name == "get_claim_history":
        schema = json.dumps(HistoryArgs.model_json_schema(), ensure_ascii=False)
        return {
            "name": name,
            "side_effect": "read",
            "retryable": True,
            "schema": schema,
        }
    if name == "get_policy":
        schema = json.dumps(PolicyArgs.model_json_schema(), ensure_ascii=False)
        return {
            "name": name,
            "side_effect": "read",
            "retryable": True,
            "schema": schema,
        }
    if name == "get_claim":
        schema = json.dumps(ClaimArgs.model_json_schema(), ensure_ascii=False)
        return {
            "name": name,
            "side_effect": "read",
            "retryable": True,
            "schema": schema,
        }
    if name == "search_clauses":
        schema = json.dumps(
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            ensure_ascii=False,
        )
        return {
            "name": name,
            "side_effect": "read",
            "retryable": True,
            "schema": schema,
        }
    if name == "save_draft":
        schema = json.dumps(
            {
                "type": "object",
                "properties": {"note": {"type": "string"}},
                "required": ["note"],
            },
            ensure_ascii=False,
        )
        return {
            "name": name,
            "side_effect": "draft",
            "retryable": False,
            "schema": schema,
        }
    raise KeyError(name)


def _format_tool_error(error: ToolError) -> str:
    return f"错误 {error.code}: {error.message}。建议：{error.suggestion}"


def _actor_may_view_claim(actor_id: str, claim_id: str) -> bool:
    if not actor_id:
        return True
    allowed = ACTOR_VISIBLE_CLAIMS.get(actor_id)
    if allowed is None:
        return False
    return claim_id in allowed


def get_claim_history(
    args: dict,
    world: World | None = None,
    *,
    actor_id: str = "",
) -> str | ToolError:
    del actor_id
    world = world or default_world()
    try:
        parsed = HistoryArgs.model_validate(args)
    except Exception as exc:
        return ToolError(
            code="PARAM_INVALID",
            message=str(exc),
            retryable=False,
            suggestion="请检查参数是否符合 schema。",
            kind="param",
        )

    if parsed.user_id and not parsed.policy_no:
        return ToolError(
            code="PARAM_USER_ID",
            message="user_id 不能用来传保单号。",
            retryable=False,
            suggestion="请改用 policy_no 传入保单号，例如 POL-1842。",
            kind="param",
        )

    policy_no = (parsed.policy_no or "").strip()
    if not policy_no:
        return ToolError(
            code="PARAM_MISSING",
            message="缺少 policy_no。",
            retryable=False,
            suggestion="请提供 policy_no，例如 POL-1842。",
            kind="param",
        )

    try:
        policy = world.policy_by_no(policy_no)
    except KeyError:
        return ToolError(
            code="POLICY_NOT_FOUND",
            message=f"保单 {policy_no} 不存在。",
            retryable=False,
            suggestion="请核对保单号后重试。",
            kind="execution",
        )

    others = world.other_claims_for_policy(policy_no)
    if not others:
        return f"被保险人{policy.insured_name}，保单{policy_no}无其他案件"
    details = "；".join(
        (
            f"{claim.claim_id}（{claim.policy_no}，"
            f"{claim.admission.isoformat()}，{claim.amount}元，{claim.hospital}）"
        )
        for claim in others
    )
    return f"被保险人{policy.insured_name}，保单{policy_no}的其他案件：{details}"


def get_policy(
    args: dict,
    world: World | None = None,
    *,
    actor_id: str = "",
) -> str | ToolError:
    del actor_id
    world = world or default_world()
    policy_no = str(args.get("policy_no", "")).strip()
    if not policy_no:
        return ToolError(
            code="PARAM_MISSING",
            message="缺少 policy_no。",
            retryable=False,
            suggestion="请提供 policy_no。",
            kind="param",
        )
    try:
        policy = world.policy_by_no(policy_no)
    except KeyError:
        return ToolError(
            code="POLICY_NOT_FOUND",
            message=f"保单 {policy_no} 不存在。",
            retryable=False,
            suggestion="请核对保单号。",
            kind="execution",
        )
    return (
        f"保单{policy.policy_no}，产品{policy.product}，"
        f"状态{policy.status}，限额{policy.limit_amount}元"
    )


def get_claim(
    args: dict,
    world: World | None = None,
    *,
    actor_id: str = "",
) -> str | ToolError:
    world = world or default_world()
    claim_id = str(args.get("claim_id", "")).strip()
    if not claim_id:
        return ToolError(
            code="PARAM_MISSING",
            message="缺少 claim_id。",
            retryable=False,
            suggestion="请提供 claim_id。",
            kind="param",
        )
    if actor_id and not _actor_may_view_claim(actor_id, claim_id):
        return ToolError(
            code="FORBIDDEN_CLAIM",
            message=f"当前身份无权查看案件 {claim_id}。",
            retryable=False,
            suggestion="请换有权限的专员账号或核对案件号。",
            kind="param",
        )
    try:
        claim = world.claim_of(claim_id)
    except KeyError:
        return ToolError(
            code="CLAIM_NOT_FOUND",
            message=f"案件 {claim_id} 不存在。",
            retryable=False,
            suggestion="请核对案件号。",
            kind="execution",
        )
    return (
        f"案件{claim.claim_id}，保单{claim.policy_no}，"
        f"医院{claim.hospital}，金额{claim.amount}元"
    )


def save_draft(
    args: dict,
    world: World | None = None,
    *,
    actor_id: str = "",
) -> str | ToolError:
    del world, actor_id
    note = str(args.get("note", "")).strip()
    if not note:
        return ToolError(
            code="PARAM_MISSING",
            message="缺少 note。",
            retryable=False,
            suggestion="请提供草稿正文 note。",
            kind="param",
        )
    return f"草稿已保存：{note}"


def search_clauses(
    args: dict,
    world: World | None = None,
    *,
    actor_id: str = "",
) -> str | ToolError:
    del world, actor_id
    query = str(args.get("query", ""))
    answered = answer_clause_hybrid(query)
    if answered.answer:
        return answered.answer
    if answered.clause_ids:
        return "检索到 " + " ".join(answered.clause_ids)
    return "未检索到条款"


def invoke_tool(
    name: str,
    args: dict,
    *,
    actor_id: str,
    world: World,
) -> str | ToolError:
    if name == "500":
        raise ToolFailure("500")
    registry = {
        "get_claim_history": get_claim_history,
        "get_policy": get_policy,
        "get_claim": get_claim,
        "search_clauses": search_clauses,
        "save_draft": save_draft,
    }
    fn = registry.get(name)
    if fn is None:
        return ToolError(
            code="UNKNOWN_TOOL",
            message=f"未知工具 {name}。",
            retryable=False,
            suggestion="请从工具目录中选择合法工具名。",
            kind="param",
        )
    return fn(args, world, actor_id=actor_id)


def default_tools() -> dict[str, Any]:
    """Backward-compatible toolbox for tests that call (args, world) directly."""

    def _wrap(fn):
        def caller(args: dict, world: World | None = None) -> str:
            result = fn(args, world, actor_id="linxiao")
            if isinstance(result, ToolError):
                return _format_tool_error(result)
            return result

        return caller

    return {
        "get_claim_history": _wrap(get_claim_history),
        "get_policy": _wrap(get_policy),
        "get_claim": _wrap(get_claim),
        "search_clauses": _wrap(search_clauses),
    }
