from claimdesk.guards.approval import ApprovalBook, ApprovalRequired
from claimdesk.store.db import complete_idempotency, connect, insert_idempotency_intended
from claimdesk.traces.resume import (
    SmsLog,
    reconcile,
    remaining_side_effects,
    restore,
    resume_if_not_done,
    resume_send,
    save_checkpoint,
)
import pytest


def test_already_sent_intent_is_not_sent_again():
    log = SmsLog()
    log.write_intent("sms-1", "13800000000", "请补充诊断证明", "CLM-2026-1842")
    calls = {"n": 0}
    resume_send(log, "sms-1", lambda: calls.__setitem__("n", calls["n"] + 1), lambda _idem: True)
    assert calls["n"] == 0
    assert log.rows["sms-1"]["result"] == "sent"

    fresh = SmsLog()
    fresh.write_intent("sms-2", "13800000000", "请补充诊断证明", "CLM-2026-1842")
    resume_send(fresh, "sms-2", lambda: calls.__setitem__("n", calls["n"] + 1), lambda _idem: False)
    assert calls["n"] == 1
    resume_send(fresh, "sms-2", lambda: calls.__setitem__("n", calls["n"] + 1), lambda _idem: False)
    assert calls["n"] == 1


def test_done_idempotency_and_checkpoint_skip_completed_keys(tmp_path):
    conn = connect(tmp_path / "resume.sqlite")
    insert_idempotency_intended(conn, "sms-done")
    complete_idempotency(conn, "sms-done", "sent")
    other = connect(tmp_path / "resume.sqlite")
    calls = {"n": 0}
    assert resume_if_not_done(other, "sms-done", lambda: calls.__setitem__("n", calls["n"] + 1)) is False
    assert calls["n"] == 0
    save_checkpoint(other, "job-1", 2, ["sms-done"])
    assert remaining_side_effects(other, "job-1", ["sms-done", "sms-new"]) == ["sms-new"]


def test_restore_drops_full_history_and_reconcile_on_version_drift():
    restored = restore(
        {
            "goal": "复核",
            "plan": "先查历史",
            "done": ["history"],
            "recent": ["摘要"],
            "full_history": "长" * 10000,
        }
    )
    assert "full_history" not in restored
    assert set(restored) == {"goal", "plan", "done", "recent"}
    same = reconcile("先查历史", 30, 30)
    assert same == "先查历史"
    changed = reconcile("先查历史", 90, 30)
    assert "重新观察" in changed
    assert "90" in changed


def test_resume_does_not_bypass_approval():
    book = ApprovalBook()
    with pytest.raises(ApprovalRequired):
        book.send_sms(None)
    log = SmsLog()
    resume_send(log, "missing", book.send_sms, lambda _idem: False)
    assert book.sent == []
