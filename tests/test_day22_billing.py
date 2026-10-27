from pathlib import Path

from claimdesk.billing.attribute import StepBill, attribute, record_usage, sum_yuan
from claimdesk.billing.budget import gate
from claimdesk.store.db import connect

NOTE = Path(__file__).resolve().parents[1] / "docs" / "billing-note.md"
CONCLUSION = "70% 以上的 token 来自第 3 步之后的历史全文重试，缓存未命中。"


def _replay() -> list[StepBill]:
    steps = [
        StepBill(ts=10, prompt_tokens=100, piece="system", new_evidence=True, tool="search"),
        StepBill(ts=20, prompt_tokens=100, piece="system", new_evidence=True, tool="search"),
    ]
    steps.extend(
        StepBill(
            ts=30 + index,
            prompt_tokens=200_000,
            tool="get_claim_history",
            new_evidence=False,
            cache_hit=False,
            piece="history",
        )
        for index in range(4)
    )
    return steps


def test_history_retries_dominate_and_match_the_note():
    report = attribute(_replay(), price_per_token=0.0001)
    assert report["later_ratio"] > 0.7
    assert report["behavior"] == "no_progress"
    assert report["largest_piece"] == "history"
    assert report["step_count"] == 6
    assert report["conclusion"] == CONCLUSION
    assert NOTE.read_text(encoding="utf-8").strip() == CONCLUSION


def test_usage_flags_a_dispute_that_breaks_fifty(tmp_path):
    conn = connect(tmp_path / "usage.sqlite")
    record_usage(conn, "eligibility", 100, 3.0, "2026-10-26")
    record_usage(conn, "dispute", 1000, 60.0, "2026-10-26")
    report = sum_yuan(conn, "2026-10-26")
    stored = conn.execute(
        "SELECT yuan FROM usage WHERE path = 'eligibility'"
    ).fetchone()
    assert stored["yuan"] == 0
    assert report["over_soft"] is True
    assert report["flagged"] is True


def test_budget_gate_soft_hard_and_no_progress():
    assert gate(49) == "run"
    assert gate(60) == "converge"
    assert gate(80) == "suspend"
    assert gate(10, no_progress=True) == "suspend"
