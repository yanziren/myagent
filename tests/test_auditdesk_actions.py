from fastapi.testclient import TestClient

from auditdesk.api.app import create_app
from auditdesk.evals.catalog import load_cases


def _client(tmp_path):
    app = create_app(db_path=str(tmp_path / "audit.sqlite"))
    return TestClient(app)


def test_formal_opinion_requires_a_different_approver(tmp_path) -> None:
    client = _client(tmp_path)
    text = next(case["text"] for case in load_cases() if case["id"] == "G01")
    created = client.post("/reviews", json={"contract_text": text, "actor_id": "lin"})
    assert created.status_code == 200
    trace_id = created.json()["trace_id"]
    assert created.json()["decision"] == "pass"
    assert created.json()["model_calls"] == 0

    blocked = client.post(
        f"/traces/{trace_id}/actions",
        json={"action": "issue_formal", "actor_id": "lin"},
    )
    assert blocked.status_code == 403

    same_person = client.post(
        f"/traces/{trace_id}/actions",
        json={"action": "send_counterparty", "actor_id": "lin", "approver_id": "lin"},
    )
    assert same_person.status_code == 403

    draft = client.post(
        f"/traces/{trace_id}/actions",
        json={"action": "draft_note", "actor_id": "lin"},
    )
    assert draft.status_code == 200
    assert draft.json()["status"] == "recorded"

    approved = client.post(
        f"/traces/{trace_id}/actions",
        json={
            "action": "issue_formal",
            "actor_id": "lin",
            "approver_id": "zhou",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "recorded"


def test_replay_returns_the_stored_review(tmp_path) -> None:
    client = _client(tmp_path)
    case = next(item for item in load_cases() if item["id"] == "G26")
    created = client.post(
        "/reviews",
        json={"contract_text": case["text"], "actor_id": "lin"},
    )
    body = created.json()
    replay = client.get(f"/traces/{body['trace_id']}")
    assert replay.status_code == 200
    stored = replay.json()
    assert stored["decision"] == "review"
    assert stored["rule_ids"] == case["expected_rule_ids"]
    assert stored["contract_text"] == case["text"]
    assert stored["actions"] == []


def test_override_without_approval_is_rejected(tmp_path) -> None:
    client = _client(tmp_path)
    text = next(case["text"] for case in load_cases() if case["id"] == "G15")
    trace_id = client.post(
        "/reviews", json={"contract_text": text, "actor_id": "lin"}
    ).json()["trace_id"]
    denied = client.post(
        f"/traces/{trace_id}/actions",
        json={"action": "override_decision", "actor_id": "lin"},
    )
    assert denied.status_code == 403


def test_desk_page_shows_the_three_decisions(tmp_path) -> None:
    client = _client(tmp_path)
    page = client.get("/")
    assert page.status_code == 200
    html = page.text
    assert "通过" in html
    assert "补材料" in html
    assert "人工复核" in html
    assert "出具正式意见" in html

    samples = client.get("/samples")
    assert samples.status_code == 200
    ids = {item["id"] for item in samples.json()}
    assert {"G01", "G15", "G26"} <= ids
