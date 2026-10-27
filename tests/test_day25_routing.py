from claimdesk.gateway.model_gateway import complete
from claimdesk.routing.router import charge, price_for, route
from claimdesk.store.db import connect
import pytest


def test_steps_pick_none_small_or_large():
    assert route("eligibility") == "none"
    assert route("intake") == "none"
    assert route("summarize", confidence=0.9) != "large"
    assert route("summarize", confidence=0.9) == "small"
    assert route("summarize", confidence=0.2) == "large"
    assert route("summarize", confidence=0.9, complained=True) == "large"
    assert route("plan") == "large"
    assert route("dispute") == "large"
    skipped = complete("eligibility")
    assert skipped["entered_gateway"] is False
    assert skipped["yuan"] == 0


def test_low_confidence_writes_two_usage_rows_and_limit_stops(tmp_path):
    conn = connect(tmp_path / "usage.sqlite")
    escalated = complete("summarize", confidence=0.2, conn=conn)
    assert escalated["tier"] == "large"
    assert escalated["usage_rows"] == 2
    rows = conn.execute("SELECT path FROM usage").fetchall()
    assert [row["path"] for row in rows] == ["small", "large"]
    limited = complete("plan", day_tokens=100_001, limit=100_000)
    assert limited["limited"] is True


def test_daily_ledger_keeps_paths_separate_and_under_fifty():
    ledger: dict[str, float] = {}
    for _ in range(100):
        charge("none", 50, price_for("none"), ledger)
    for _ in range(50):
        charge("small", 200, price_for("small"), ledger)
    for _ in range(2):
        charge("large", 2000, price_for("large"), ledger)
    assert ledger["none"] == 0
    assert ledger["small"] == pytest.approx(50 * 200 * 0.00002)
    assert ledger["large"] == pytest.approx(2 * 2000 * 0.0001)
    assert sum(ledger.values()) < 50
    assert ledger["small"] != ledger["large"]
