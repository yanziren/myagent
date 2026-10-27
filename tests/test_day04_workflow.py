import sqlite3

import pytest
from fastapi.testclient import TestClient

import claimdesk.workflow.intake as intake_module
from claimdesk.api.app import create_app
from claimdesk.domain.seed import default_world
from claimdesk.store.db import connect
from claimdesk.workflow.intake import run_intake


def _exploding_model(_prompt: str) -> str:
    raise AssertionError("model must not be called on intake missing-docs path")


def test_day04_missing_docs_stops_before_eligibility(monkeypatch):
    def _must_not_run(*_args, **_kwargs):
        raise AssertionError("evaluate_eligibility must not run when docs are missing")

    monkeypatch.setattr(intake_module, "evaluate_eligibility", _must_not_run)

    world = default_world()
    suggestion = run_intake(world, "CLM-2026-0777", model=_exploding_model)

    assert suggestion.decision == "补充材料"
    assert "AK-2024-2.1" in suggestion.clause_ids
    assert "diagnosis_certificate" in suggestion.missing_docs
    assert suggestion.model_calls == 0
    assert "推断" in suggestion.rationale


def test_day04_complete_materials_reach_eligibility_rules():
    world = default_world()
    suggestion = run_intake(world, "CLM-2026-0901", model=_exploding_model)

    assert suggestion.decision == "通过"
    assert "R-ELIGIBLE" in suggestion.rule_ids
    assert suggestion.model_calls == 0


def test_day04_intake_http_0777_persists_need_docs(tmp_path):
    db_path = tmp_path / "claims.sqlite"
    client = TestClient(create_app(db_path=str(db_path)))

    response = client.post(
        "/claims/CLM-2026-0777/intake",
        json={"actor_id": "linxiao"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "补充材料"
    assert "diagnosis_certificate" in body["missing_docs"]

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT status, decision FROM claims WHERE claim_id = ?",
            ("CLM-2026-0777",),
        ).fetchone()
        assert row is not None
        assert row["status"] == "need_docs"
        assert row["decision"] == "补充材料"
    finally:
        conn.close()


def test_day04_intake_http_0901_approves_via_rules(tmp_path):
    db_path = tmp_path / "claims.sqlite"
    client = TestClient(create_app(db_path=str(db_path)))

    response = client.post(
        "/claims/CLM-2026-0901/intake",
        json={"actor_id": "linxiao"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "通过"
    assert "R-ELIGIBLE" in body["rule_ids"]

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM claims WHERE claim_id = ?",
            ("CLM-2026-0901",),
        ).fetchone()
        assert row is not None
        assert row["status"] == "eligibility_checked"
    finally:
        conn.close()
