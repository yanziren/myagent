import sqlite3

import pytest
from fastapi.testclient import TestClient

from claimdesk.api.app import create_app
from claimdesk.domain.seed import default_world
from claimdesk.rules.eligibility import evaluate_eligibility
from claimdesk.store.db import connect, count_claims


def _exploding_model(_prompt: str) -> str:
    raise AssertionError("model must not be called for eligibility rules")


def test_day03_small_clear_case_approves_without_a_model():
    world = default_world()
    claim = world.claim_of("CLM-2026-0901")
    policy = world.policy_of("CLM-2026-0901")

    suggestion = evaluate_eligibility(
        claim,
        policy,
        waiting_days=world.active_waiting_days(),
        model=_exploding_model,
    )

    assert suggestion.model_calls == 0
    assert suggestion.decision == "通过"
    assert "R-ELIGIBLE" in suggestion.rule_ids
    assert "AK-2024-4.2" in suggestion.clause_ids


def test_day03_waiting_period_rejects_with_rule_id():
    world = default_world()
    claim = world.claim_of("CLM-2026-1842")
    policy = world.policy_of("CLM-2026-1842")

    suggestion = evaluate_eligibility(
        claim,
        policy,
        waiting_days=30,
        model=_exploding_model,
    )

    assert suggestion.model_calls == 0
    assert suggestion.decision == "拒绝"
    assert "R-WAITING-PERIOD" in suggestion.rule_ids
    assert "AK-2024-3.1" in suggestion.clause_ids
    assert "13" in suggestion.rationale
    assert "30" in suggestion.rationale


def test_day03_eligibility_http_persists_claim_without_model(tmp_path):
    db_path = tmp_path / "claims.sqlite"
    app = create_app(db_path=str(db_path))
    client = TestClient(app)

    response = client.post(
        "/claims/CLM-2026-0901/eligibility",
        json={"actor_id": "linxiao"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_calls"] == 0
    assert body["decision"] == "通过"
    assert "R-ELIGIBLE" in body["rule_ids"]

    conn = connect(db_path)
    try:
        assert count_claims(conn) == 1
        row = conn.execute(
            "SELECT claim_id, actor_id, model_calls FROM claims WHERE claim_id = ?",
            ("CLM-2026-0901",),
        ).fetchone()
        assert row is not None
        assert row["claim_id"] == "CLM-2026-0901"
        assert row["actor_id"] == "linxiao"
        assert row["model_calls"] == 0
    finally:
        conn.close()
