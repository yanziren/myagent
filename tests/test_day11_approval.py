from __future__ import annotations

from pathlib import Path

import pytest

from claimdesk.app.http_api import post_json
from claimdesk.guards.approval import ApprovalBook, ApprovalRequired, approval_view
from claimdesk.store.db import connect, count_audit, insert_job


def test_send_sms_without_ticket_raises():
    book = ApprovalBook()
    with pytest.raises(ApprovalRequired):
        book.send_sms(None)


def test_linxiao_sms_story_reject_then_approve_edited_body():
    book = ApprovalBook()
    revised = "请补充诊断证明，此为补件不是拒赔"

    with pytest.raises(ApprovalRequired):
        book.send_sms(None)

    bad = book.propose_sms(
        recipient="13800000000",
        body="您已被拒赔",
        reason="补件提醒",
        amount=18600,
        claim_id="CLM-2026-1842",
    )
    assert bad.status == "pending"
    book.reject(bad.id)
    assert book.sent == []

    good = book.propose_sms(
        recipient="13800000000",
        body="您已被拒赔",
        reason="补件提醒",
        amount=18600,
        claim_id="CLM-2026-1842",
    )
    book.edit(good.id, revised)
    book.approve(good.id, "zhouheng")

    assert book.sent == [revised]
    assert "您已被拒赔" not in book.sent

    view = post_json("/approvals", {"ticket_id": good.id}, book)
    assert view["amount"] == 18600
    assert revised in view["body"]
    assert set(view) >= {"recipient", "body", "reason", "amount"}


def test_finalize_18600_does_not_write_core():
    book = ApprovalBook()
    ticket = book.finalize("CLM-2026-1842", 18600)
    assert ticket.status == "pending"
    assert book.core_writes == []


def test_save_draft_audited_without_pending():
    book = ApprovalBook()
    ticket = book.save_draft(
        body="内部备注：措辞待改",
        claim_id="CLM-2026-1842",
        actor_id="linxiao",
    )
    assert ticket.status == "audited"
    assert len(book.audit) == 1
    assert book.audit[0]["action"] == "save_draft"
    assert book.sent == []


def test_approval_view_keys():
    book = ApprovalBook()
    ticket = book.propose_sms(
        recipient="13800000000",
        body="test",
        reason="r",
        amount=100,
        claim_id="CLM-2026-0901",
    )
    view = approval_view(ticket)
    assert set(view) >= {"recipient", "body", "reason", "amount"}


def test_propose_sms_blocks_job_and_writes_audit(tmp_path: Path):
    db_path = tmp_path / "claims.sqlite"
    conn = connect(db_path)
    insert_job(conn, job_id="job-1", claim_id="CLM-2026-1842", intent="investigate")

    book = ApprovalBook()
    ticket = book.propose_sms(
        recipient="13800000000",
        body="您已被拒赔",
        reason="补件",
        amount=18600,
        claim_id="CLM-2026-1842",
        job_id="job-1",
        conn=conn,
    )
    assert ticket.job_id == "job-1"

    row = conn.execute(
        "SELECT status FROM jobs WHERE id = ?",
        ("job-1",),
    ).fetchone()
    assert row["status"] == "blocked"
    assert count_audit(conn) >= 1

    book.approve(ticket.id, "zhouheng", conn=conn)
    row = conn.execute(
        "SELECT status FROM jobs WHERE id = ?",
        ("job-1",),
    ).fetchone()
    assert row["status"] == "accepted"
    conn.close()


def test_edit_after_approve_is_rejected():
    book = ApprovalBook()
    ticket = book.propose_sms(
        recipient="13800000000",
        body="draft",
        reason="r",
        amount=100,
        claim_id="CLM-2026-0901",
    )
    book.approve(ticket.id, "zhouheng")
    with pytest.raises(ValueError):
        book.edit(ticket.id, "changed")
