from pathlib import Path

from fastapi.testclient import TestClient

from claimdesk.agent.desk import drain_once, handle
from claimdesk.agent.loop import format_trace
from claimdesk.api.app import create_app
from claimdesk.domain.models import DeskRequest
from claimdesk.domain.seed import default_world
from claimdesk.store.db import connect, count_jobs


def _exploding_model(_prompt: str):
    raise AssertionError("model must not be called")


def _scripted_model(prompts: list[str]):
    def model(prompt: str) -> dict:
        prompts.append(prompt)
        assert "计划" in prompt
        step = len(prompts)
        if step == 1:
            return {
                "type": "tool",
                "name": "get_claim_history",
                "args": {"policy_no": "POL-1842"},
            }
        if step == 2:
            assert "CLM-2026-1831" in prompt
            return {
                "type": "tool",
                "name": "search_clauses",
                "args": {"query": "等待期 既往住院"},
            }
        return {
            "type": "final",
            "decision": "复核",
            "clause_ids": ["AK-2024-3.1"],
        }

    return model


def test_day08_eligibility_is_zero_steps_and_zero_model_calls():
    world = default_world()
    result = handle(
        world,
        DeskRequest(claim_id="CLM-2026-0901", intent="eligibility", actor_id="linxiao"),
        _exploding_model,
    )

    assert result.steps == 0
    assert result.model_calls == 0
    assert result.suggestion.model_calls == 0
    assert result.suggestion.decision == "通过"
    assert result.job_id is None


def test_day08_unknown_intent_stops_without_a_model():
    world = default_world()
    result = handle(
        world,
        DeskRequest(claim_id="CLM-2026-0901", intent="chitchat", actor_id="linxiao"),
        _exploding_model,
    )

    assert result.stop_reason == "unknown"
    assert result.suggestion.decision == "无法判断"
    assert result.steps == 0
    assert result.model_calls == 0


def test_day08_eligibility_http_does_not_insert_a_job(tmp_path: Path):
    db_path = tmp_path / "claims.sqlite"
    client = TestClient(create_app(db_path=str(db_path)))

    response = client.post(
        "/claims/CLM-2026-0901/eligibility",
        json={"actor_id": "linxiao"},
    )
    assert response.status_code == 200
    assert response.json()["model_calls"] == 0

    conn = connect(db_path)
    try:
        assert count_jobs(conn) == 0
    finally:
        conn.close()


def test_day08_investigation_queues_then_history_before_search(tmp_path: Path):
    db_path = tmp_path / "claims.sqlite"
    prompts: list[str] = []
    client = TestClient(create_app(db_path=str(db_path), model=_exploding_model))

    response = client.post(
        "/investigations",
        json={
            "claim_id": "CLM-2026-1842",
            "actor_id": "linxiao",
            "intent": "investigate",
        },
    )
    assert response.status_code == 200
    assert list(response.json().keys()) == ["job_id"]
    job_id = response.json()["job_id"]

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, claim_id, status, intent FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        assert row is not None
        assert row["claim_id"] == "CLM-2026-1842"
        assert row["status"] == "accepted"
        assert row["intent"] == "investigate"
        assert count_jobs(conn) == 1
    finally:
        conn.close()

    result = drain_once(connect(db_path), default_world(), _scripted_model(prompts))

    names = [step["tool"] for step in result.trace]
    assert names.index("get_claim_history") < names.index("search_clauses")
    assert result.trace[0]["args"] == {"policy_no": "POL-1842"}
    assert result.trace[1]["args"] == {"query": "等待期 既往住院"}
    assert all(step.get("tool") for step in result.trace)
    rendered = format_trace(result.trace)
    assert rendered.startswith("get_claim_history:")
    assert "CLM-2026-1831" in rendered
    assert result.suggestion.decision == "复核"
    assert "AK-2024-3.1" in result.suggestion.clause_ids
    assert prompts and all("计划" in prompt for prompt in prompts)

    conn = connect(db_path)
    try:
        status = conn.execute(
            "SELECT status FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()["status"]
        assert status == "completed"
    finally:
        conn.close()


def test_day08_handle_investigate_enqueues_without_calling_the_model(tmp_path: Path):
    conn = connect(tmp_path / "jobs.sqlite")
    try:
        result = handle(
            default_world(),
            DeskRequest(
                claim_id="CLM-2026-1842",
                intent="investigate",
                actor_id="linxiao",
            ),
            _exploding_model,
            conn=conn,
        )
        assert result.steps == 0
        assert result.model_calls == 0
        assert result.job_id
        row = conn.execute(
            "SELECT status, intent FROM jobs WHERE id = ?",
            (result.job_id,),
        ).fetchone()
        assert row["status"] == "accepted"
        assert row["intent"] == "investigate"
    finally:
        conn.close()


def test_day08_simple_loop_does_not_import_langgraph():
    root = Path(__file__).resolve().parents[1] / "claimdesk" / "agent"
    for path in root.rglob("*.py"):
        assert "langgraph" not in path.read_text(encoding="utf-8").lower()
