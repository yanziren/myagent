from __future__ import annotations

from claimdesk.tools.schemas import tool_spec

_TOOL_SUMMARIES: dict[str, str] = {
    "get_claim_history": "按保单号查询同一被保险人的其他案件（只读）。",
    "get_policy": "按保单号查询保单摘要（只读）。",
    "get_claim": "按案件号查询案件摘要（只读，受专员权限约束）。",
    "search_clauses": "混合检索条款片段（只读）。",
}


def list_tools_for_intent(intent: str) -> list[dict]:
    if intent == "eligibility":
        return [{"note": "资格路径不注册协查工具。"}]
    if intent == "investigate":
        return [
            {"name": name, "description": desc}
            for name, desc in _TOOL_SUMMARIES.items()
        ]
    return []


def expand_tool(name: str) -> dict:
    return tool_spec(name)
