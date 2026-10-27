import pytest

from claimdesk.multiagent.tasks import (
    ALLOWED_STATES,
    assemble,
    claim_job,
    default_cards,
    handoff,
    run_medical,
    transition,
)
from claimdesk.store.db import connect


def test_unknown_state_is_rejected_and_cards_have_distinct_owners():
    with pytest.raises(ValueError):
        transition("guessing")
    cards = default_cards()
    assert [card.task_id for card in cards] == ["T-MED", "T-CL", "T-PR"]
    assert len({card.owner for card in cards}) == 3
    assert {card.owner for card in cards} == {"medical", "clause", "precedent"}
    assert all(card.budget == 200 for card in cards)
    assert all(card.state == "assigned" for card in cards)
    assert all(card.output_schema == {"finding": "str"} for card in cards)
    assert ALLOWED_STATES == {
        "assigned",
        "running",
        "blocked",
        "completed",
        "failed",
        "timeout",
        "cancelled",
    }


def test_two_workers_cannot_both_claim_the_same_job(tmp_path):
    conn = connect(tmp_path / "jobs.sqlite")
    conn.execute(
        """
        INSERT INTO jobs (id, claim_id, status, intent, owner, lease_until)
        VALUES ('job-2208', 'CLM-2026-2208', 'accepted', 'dispute', NULL, 0)
        """
    )
    conn.commit()
    first = claim_job(conn, "job-2208", "medical", 100, 200)
    second = claim_job(conn, "job-2208", "clause", 100, 300)
    assert first + second == 1
    owner = conn.execute("SELECT owner FROM jobs WHERE id = 'job-2208'").fetchone()
    assert owner["owner"] == "medical"


def test_missing_heartbeat_does_not_invent_a_normal_finding():
    cards = default_cards()
    medical = cards[0]
    assert run_medical(medical, False) is None
    assert medical.state == "timeout"
    report = assemble(cards)
    assert report["state"] == "failed"
    assert report["owner"] == "medical"
    assert "医学" in report["text"]
    assert "无异常" not in report["text"]
    assert report["text"] == "无法完成：缺少医学意见"


def test_unconfirmed_handoff_keeps_the_owner():
    card = default_cards()[0]
    same = handoff(card, "clause", False)
    assert same.owner == "medical"
    changed = handoff(card, "clause", True)
    assert changed.owner == "clause"
    assert changed.state == "assigned"
