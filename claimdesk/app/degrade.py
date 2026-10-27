from __future__ import annotations

from claimdesk.domain.seed import World
from claimdesk.rules.eligibility import evaluate_eligibility
from claimdesk.store.db import append_audit


def on_model_timeout(primary, backup):
    calls = {"primary": 0, "backup": 0}
    try:
        calls["primary"] += 1
        result = primary()
    except TimeoutError:
        calls["backup"] += 1
        result = backup()
    return result, calls


def on_retrieve_down(claim_id: str, known_facts: list[str]) -> dict:
    materials = [fact for fact in known_facts if fact]
    handoff = f"案件{claim_id} 材料:{'、'.join(materials)}"
    text = "资料不足，无法判断。"
    allowed = set(known_facts)
    for phrase in ("保单有效", "等待期已过"):
        if phrase not in allowed:
            text = text.replace(phrase, "")
    return {"decision": "无法判断", "handoff": handoff, "text": text}


def on_overload() -> dict:
    return {"mode": "rules-only"}


def handle_step(mode: str, step: str, route_fn, world: World, claim_id: str):
    if mode == "rules-only" and step != "eligibility":
        return {"skipped": True, "decision": "无法判断"}
    if step == "eligibility":
        claim = world.claim_of(claim_id)
        return evaluate_eligibility(
            claim,
            world.policy_of(claim_id),
            world.active_waiting_days(),
        )
    return route_fn(step)


def complete_with_fallback(conn, primary, backup) -> str:
    try:
        return primary()
    except TimeoutError:
        append_audit(
            conn,
            action="fallback",
            amount=0,
            target="model",
            approver="",
            phase="fallback",
            payload="Fallback",
        )
        return backup()
