from claimdesk.gateway.model_gateway import online_answer
from claimdesk.guards.approval import ApprovalBook
from claimdesk.release.compare import (
    ModelConfig,
    calibrated,
    compare,
    pairwise,
    rollback,
    shadow_send,
)
from claimdesk.store.db import connect


def _row(scenario: str, old: dict, new: dict) -> dict:
    return {"scenario": scenario, "old": old, "new": new}


def test_cite_regression_blocks_even_when_the_total_looks_fine():
    rows = [
        _row("waiting", {"decision": "复核", "clause_ids": ["AK-2024-3.1"], "fake_clause": False}, {"decision": "复核", "clause_ids": ["AK-2024-3.1"], "fake_clause": False})
        for _ in range(10)
    ]
    rows.append(
        _row("cite", {"decision": "复核", "fake_clause": False}, {"decision": "通过", "fake_clause": True})
    )
    rows.append(
        _row("cite", {"decision": "复核", "fake_clause": False}, {"decision": "通过", "fake_clause": True})
    )
    report = compare(rows)
    assert report["blocked"] is True
    assert "cite" in report["scenarios"]
    same = report["by_scenario"]["waiting"]["same"]
    assert same / report["by_scenario"]["waiting"]["n"] == 1


def test_position_biased_judge_is_sent_to_a_human():
    def always_left(_left, _right):
        return "left"

    assert pairwise(always_left, "old-text", "new-text") == "human"
    assert calibrated(4) is True
    assert calibrated(2) is False


def test_shadow_does_not_send_and_rollback_restores_the_pinned_model(tmp_path):
    book = ApprovalBook()
    ticket = book.propose_sms(
        recipient="13800000000",
        body="请补充材料",
        reason="补件",
        amount=18600,
        claim_id="CLM-2026-1842",
    )
    ticket.status = "approved"
    assert book.sent == []
    assert shadow_send(book, ticket.id) == {"executed": False, "sent": []}
    assert book.sent == []

    config = ModelConfig("claim-model-2026-10-18")
    assert rollback(config, "claim-model-2026-10-01") == "claim-model-2026-10-01"
    assert config.model_id == "claim-model-2026-10-01"

    conn = connect(tmp_path / "shadow.sqlite")
    visible = online_answer("AK-2024-3.1", "AK-FAKE", conn)
    assert visible["clause_ids"] == ["AK-2024-3.1"]
    assert "AK-FAKE" not in visible["decision"]
    phase = conn.execute(
        "SELECT phase, payload FROM audit WHERE phase = 'shadow'"
    ).fetchone()
    assert phase["phase"] == "shadow"
    assert phase["payload"] == "AK-FAKE"
