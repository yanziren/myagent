from fastapi.testclient import TestClient

from claimdesk.api.app import create_app
from claimdesk.app.latency import (
    FIRST_FEEDBACK_MS,
    SIMPLE_DONE_MS,
    STEP_NAMES,
    TimeLine,
    claim_batch,
    emit,
    parallel_reads,
    within_budget,
)
from claimdesk.guards.injection import stateless_gate
from claimdesk.serving.batch_sim import simulate, static_batch
from claimdesk.store.db import connect, insert_job


def _exploding(_prompt: str):
    raise AssertionError("model must not be called")


def test_progress_arrives_before_the_final_and_within_two_seconds():
    early = [{"t": 100, "kind": "progress"}, {"t": 800, "kind": "final"}]
    shown = emit(early)
    assert shown["progress_before_final"] is True
    assert shown["progress_ms"] <= FIRST_FEEDBACK_MS
    assert within_budget(early) is True
    late = [{"t": 100, "kind": "progress"}, {"t": 25000, "kind": "final"}]
    assert late[-1]["t"] > SIMPLE_DONE_MS
    assert within_budget(late) is False
    assert FIRST_FEEDBACK_MS == 2000
    assert SIMPLE_DONE_MS == 20000
    assert STEP_NAMES == ("route", "retrieve", "model", "tool", "generate")


def test_job_status_is_visible_before_the_model_runs(tmp_path):
    client = TestClient(create_app(db_path=str(tmp_path / "jobs.sqlite"), model=_exploding))
    response = client.post(
        "/investigations",
        json={"claim_id": "CLM-2026-1842", "actor_id": "linxiao", "intent": "investigate"},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    viewed = client.get(f"/jobs/{job_id}")
    assert viewed.status_code == 200
    body = viewed.json()
    assert body["status"] in {"accepted", "progress"} or body["progress"] in {"accepted", "progress"}


def test_readonly_tools_run_together_and_batch_claim_is_one_query(tmp_path):
    assert stateless_gate("get_policy", 0, "POL-1842") == "allow"
    assert stateless_gate("send_sms", 18600, "13800000000") != "allow"
    elapsed = parallel_reads([300, 800])
    assert elapsed >= 750
    assert elapsed < 1100
    conn = connect(tmp_path / "batch.sqlite")
    for index in range(5):
        insert_job(conn, job_id=f"j{index}", claim_id="CLM-2026-1842", intent="investigate")
    assert len(claim_batch(conn, 3)) == 3


def test_continuous_batch_does_not_make_short_requests_wait_for_long_prefill():
    arrivals = [{"prefill_ms": 10, "tokens": 2} for _ in range(8)]
    small = simulate(arrivals, batch_cap=1)["mean_tpot"]
    wide = simulate(arrivals, batch_cap=8)["mean_tpot"]
    assert small < wide
    mixed = [
        {"prefill_ms": 10, "tokens": 2},
        {"prefill_ms": 500, "tokens": 2},
        {"prefill_ms": 10, "tokens": 2},
    ]
    continuous = simulate(mixed, batch_cap=1)["ttft_ms"]
    waiting = static_batch(mixed)
    assert continuous[0] < waiting[0]
    assert continuous[2] < waiting[2]


def test_timeline_keeps_first_offset_and_raw_samples():
    line = TimeLine()
    line.mark("route")
    report = line.report([10, 20, 30, 40])
    assert "route" in report["offsets"]
    assert report["samples"] == [10, 20, 30, 40]
    assert report["p50"] == 20
