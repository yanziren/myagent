from claimdesk.store.db import connect
from claimdesk.traces.store import TraceStore, score_outcome, trajectory_violations


def test_yesterday_trace_replays_without_calling_live_tools(tmp_path):
    conn = connect(tmp_path / "trace.sqlite")
    store = TraceStore(conn)
    trace_id = store.start()
    assert trace_id == "tr-1"
    calls = {"n": 0}

    def live():
        calls["n"] += 1
        return "live"

    store.note_intent(trace_id, "get_claim_history", {"policy_no": "POL-1842"})
    assert store.intents(trace_id) == ["get_claim_history"]
    assert calls["n"] == 0

    store.record(
        trace_id,
        tool="get_claim_history",
        args={"policy_no": "POL-1842"},
        result={"claims": ["CLM-2026-1831"]},
        reason="先查历史就诊",
        context_before="完整历史很长",
        context_after="摘要：已查历史",
    )
    store.record(
        trace_id,
        tool="search_clauses",
        args={"query": "等待期"},
        result={"clause_ids": ["AK-2024-3.1"]},
        reason="再用历史结果查条款",
        context_before="摘要：已查历史",
        context_after="摘要：已查条款",
    )
    store.checkpoint(trace_id, {"step": 2, "claim_id": "CLM-2026-1842"})

    fresh = TraceStore(connect(tmp_path / "trace.sqlite"))
    first = fresh.events(trace_id)[0]
    assert first["context_before"] != first["context_after"]
    assert fresh.replay(trace_id, live) == ["get_claim_history", "search_clauses"]
    assert calls["n"] == 0
    assert fresh.checkpoints(trace_id) == [{"step": 2, "claim_id": "CLM-2026-1842"}]
    divergence = fresh.first_divergence(
        trace_id, ["get_claim_history", "get_policy"]
    )
    assert divergence["index"] == 1
    assert divergence["actual"] == "search_clauses"


def test_outcome_score_does_not_hide_trajectory_violations():
    assert score_outcome("通过", "通过") is True
    marks = trajectory_violations(
        [
            {"tool": "send_sms", "approved": False},
            {"fingerprint": "same", "tool": "get_claim_history"},
            {"fingerprint": "same", "tool": "get_claim_history"},
            {"fingerprint": "same", "tool": "get_claim_history", "decision": "通过", "evidence_ids": []},
        ]
    )
    assert marks == {"unauthorized", "loop", "no_evidence"}
