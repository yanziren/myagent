import json
from pathlib import Path

from claimdesk.domain.seed import default_world
from claimdesk.evals.tool_metrics import summarize, summarize_audit
from claimdesk.store.db import append_audit, connect
from claimdesk.tools.schemas import get_claim_history

REGRESS = Path(__file__).resolve().parents[1] / "claimdesk" / "evals" / "regress_tools.jsonl"


def _history_case() -> list[dict]:
    events = [{"tool": "other", "model": "small", "kind": "ok"} for _ in range(90)]
    events.extend(
        {"tool": "get_claim_history", "model": "small", "kind": "ok"} for _ in range(6)
    )
    events.extend(
        {"tool": "get_claim_history", "model": "small", "kind": "param"} for _ in range(4)
    )
    return events


def test_global_rate_does_not_hide_history_param_errors():
    report = summarize(_history_case())
    assert report["global_success"] == 0.96
    history = report["by_tool"]["get_claim_history"]
    assert history["calls"] == 10
    assert history["param_error_rate"] == 0.4
    assert report["by_model"]["small"]["success"] == 0.96


def test_audit_slice_shows_history_worse_than_global(tmp_path):
    conn = connect(tmp_path / "audit.sqlite")
    for _ in range(90):
        append_audit(
            conn,
            action="tool",
            amount=0,
            target="eligibility",
            approver="metrics",
            tool="eligibility",
            payload=json.dumps({"kind": "ok", "model": "none"}),
        )
    for _ in range(4):
        append_audit(
            conn,
            action="tool",
            amount=0,
            target="history",
            approver="metrics",
            tool="get_claim_history",
            payload=json.dumps({"kind": "param", "model": "small"}),
        )
    report = summarize_audit(conn)
    history_success = 1 - report["by_tool"]["get_claim_history"]["param_error_rate"]
    assert report["global_success"] > history_success


def test_user_id_regression_stays_a_single_param_error():
    row = json.loads(REGRESS.read_text(encoding="utf-8").strip())
    calls = {"n": 0}

    def once(args, world):
        calls["n"] += 1
        return get_claim_history(args, world)

    result = once(row["args"], default_world())
    assert calls["n"] == 1
    assert result.kind == row["expect_kind"]
    assert result.code == row["expect_code"]
    assert calls["n"] == 1
