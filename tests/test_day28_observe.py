import pytest

from claimdesk.observe.feedback import Feedback, slice_by_intent, slice_success
from claimdesk.observe.probes import Probe, rag_dims
from pathlib import Path

NOTE = Path(__file__).resolve().parents[1] / "docs" / "dumber-note.md"


def test_feedback_without_a_trace_is_rejected():
    box = Feedback()
    with pytest.raises(ValueError):
        box.accept("变笨了")
    box.accept("变笨了", trace_id="tr-15")
    assert box.rows == [{"text": "变笨了", "trace_id": "tr-15"}]


def test_hard_cases_are_visible_under_a_green_average():
    rows = [{"difficulty": "easy", "ok": True} for _ in range(90)]
    rows.extend({"difficulty": "hard", "ok": True} for _ in range(2))
    rows.extend({"difficulty": "hard", "ok": False} for _ in range(8))
    report = slice_success(rows)
    assert report["global"] == 0.92
    assert report["by_difficulty"]["hard"] == 0.2
    note = NOTE.read_text(encoding="utf-8")
    assert "92%" in note
    assert "20%" in note
    assert "切片" in note

    jobs = [{"intent": "eligibility", "ok": True} for _ in range(9)]
    jobs.append({"intent": "investigate", "ok": False})
    sliced = slice_by_intent(jobs)
    assert sliced["global"] > sliced["by_intent"]["investigate"]
    assert sliced["by_intent"]["investigate"] == 0


def test_probe_alerts_when_the_model_id_changes():
    probe = Probe()

    def answer(_question: str) -> str:
        return "自投保日起 30 日内为等待期。[AK-2024-3.1]"

    first = probe.run_probe("claim-model-2026-10-01", answer)
    second = probe.run_probe("claim-model-2026-10-18", answer)
    assert first["alert"] is False
    assert second["alert"] is True


def test_each_bad_session_knocks_out_one_rag_dimension():
    recall = rag_dims(
        {
            "question": "等待期是多少天",
            "expected_clause": "AK-2024-3.1",
            "context": "",
            "answer": "自投保日起 30 日内为等待期。[AK-2024-3.1]",
            "broken": "recall",
        }
    )
    precision = rag_dims(
        {
            "question": "等待期是多少天",
            "expected_clause": "AK-2024-3.1",
            "context": "AK-2024-3.1",
            "answer": "自投保日起 30 日内为等待期。[AK-2024-3.1]",
            "relevant_blocks": 1,
            "irrelevant_blocks": 3,
            "broken": "precision",
        }
    )
    relevance = rag_dims(
        {
            "question": "等待期是多少天",
            "expected_clause": "AK-2024-3.1",
            "context": "AK-2024-3.1",
            "answer": "床位费限额 300 元/日。[AK-2024-7.1]",
            "broken": "relevance",
        }
    )
    assert recall["recall"] is False
    assert precision["precision"] is False
    assert relevance["relevance"] is False
    assert recall["precision"] is True
    assert precision["recall"] is True
    assert relevance["recall"] is True
