import inspect
import os

from claimdesk.guards.approval import ApprovalBook
from claimdesk.rag.ground import answer_grounded
from claimdesk.sandbox.execute import execute_python, sum_invoices

INVOICES = [120, 80, 45, 200, 15, 60, 33, 18, 90, 70, 25, 44]


def test_twelve_invoices_sum_to_800_without_a_model_loop():
    assert sum(INVOICES) == 800
    result = sum_invoices(INVOICES)
    assert result["ok"] is True
    assert result["total"] == 800


def test_sandbox_rejects_loop_import_and_metadata(monkeypatch):
    monkeypatch.setenv("CLAIMDESK_SECRET", "super-secret-value")
    looped = execute_python("while True:\n    pass", INVOICES)
    assert looped["ok"] is False
    assert looped["reason"] == "timeout"
    imported = execute_python('__import__("os").environ["CLAIMDESK_SECRET"]', INVOICES)
    assert imported["ok"] is False
    assert imported["reason"] == "import"
    assert "super-secret-value" not in str(imported)
    networked = execute_python('"http://169.254.169.254/"', INVOICES)
    assert networked["ok"] is False
    assert networked["reason"] == "network"
    assert os.environ["CLAIMDESK_SECRET"] not in str(networked)


def test_sms_stays_json_and_total_still_needs_a_real_clause():
    book = ApprovalBook()
    signature = inspect.signature(book.propose_sms)
    assert "code" not in signature.parameters
    ticket = book.propose_sms(
        recipient="13800000000",
        body="请补充诊断证明",
        reason="补件",
        amount=800,
        claim_id="CLM-2026-1842",
    )
    assert isinstance(ticket.body, str)
    assert book.sent == []
    grounded = answer_grounded(
        "票据合计是多少",
        "合计 800 元所以通过。[AK-FAKE]",
    )
    assert grounded.decision != "通过"
    assert "AK-FAKE" not in grounded.rationale
    assert execute_python("total = sum(invoices)", INVOICES)["total"] != "通过"
