from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from claimdesk.agent.memory import EntitySidecar, load_facts
from claimdesk.tools.catalog import expand_tool, list_tools_for_intent

MAX_CONTEXT_CHARS = 1800
MAX_OBS = 160


class Task(BaseModel):
    claim_id: str
    product: str
    plan: str
    goal: str


def _header_fields(
    task: Task,
    *,
    conn: sqlite3.Connection | None,
    tenant_id: str | None,
    sidecar: EntitySidecar | None,
) -> tuple[str, str, str, str]:
    claim_id = task.claim_id
    product = task.product
    policy_no = ""
    clause_version = ""
    if conn is not None:
        facts = load_facts(claim_id, conn=conn, tenant_id=tenant_id)
        claim_id = facts.get("claim_id") or claim_id
        product = facts.get("product") or product
        policy_no = facts.get("policy_no", "")
        clause_version = facts.get("clause_version", "")
    elif sidecar is not None:
        claim_id = sidecar.claim_id
        product = sidecar.product
        policy_no = sidecar.policy_no
        clause_version = sidecar.clause_version
    return claim_id, product, policy_no, clause_version


def _observation_lines(observations: list[dict]) -> list[str]:
    if len(observations) > 2:
        older = observations[:-2]
        recent = observations[-2:]
        names = "、".join(str(item["tool"]) for item in older)
        lines = [f"较早观察摘要: {names}"]
    else:
        recent = observations
        lines = []
    for item in recent:
        text = str(item["text"])[:MAX_OBS]
        lines.append(f"观察 {item['tool']}: {text}")
    return lines


def render_context(
    task: Task,
    observations: list[dict],
    *,
    intent: str = "investigate",
    expanded_tools: set[str] | None = None,
    tool_round: int = 1,
    conn: sqlite3.Connection | None = None,
    tenant_id: str | None = None,
    sidecar: EntitySidecar | None = None,
) -> str:
    claim_id, product, policy_no, clause_version = _header_fields(
        task,
        conn=conn,
        tenant_id=tenant_id,
        sidecar=sidecar,
    )
    lines = [
        f"案件：{claim_id}",
        f"产品：{product}",
        f"计划：{task.plan}",
        f"目标：{task.goal}",
    ]
    if policy_no:
        lines.append(f"保单：{policy_no}")
    if clause_version:
        lines.append(f"条款版本：{clause_version}")

    expanded = expanded_tools or set()
    catalog = list_tools_for_intent(intent)
    if intent == "investigate":
        lines.append("工具目录：")
        for entry in catalog:
            lines.append(f"- {entry['name']}：{entry['description']}")
        if tool_round >= 2:
            for name in sorted(expanded):
                try:
                    spec = expand_tool(name)
                except KeyError:
                    continue
                lines.append(f"工具 schema {name}：{spec['schema']}")
    elif catalog:
        lines.append(catalog[0].get("note", ""))

    lines.extend(_observation_lines(observations))
    rendered = "\n".join(lines)
    if len(rendered) > MAX_CONTEXT_CHARS:
        rendered = rendered[:MAX_CONTEXT_CHARS]
    return rendered
