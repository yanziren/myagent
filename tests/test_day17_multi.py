from pathlib import Path

from claimdesk.multiagent.dispute import (
    FULL_DOCS,
    SUMMARIES,
    handle_case,
    should_start_workers,
    single_agent_report,
)

DAY_DOC = Path(__file__).resolve().parents[1] / "docs" / "days" / "17-只有争议案启动工人.md"


def test_single_agent_swallows_both_findings_at_9000_tokens():
    report = single_agent_report()
    assert report["tokens"] == 9000
    assert report["tokens"] == sum(len(doc) for doc in FULL_DOCS)
    assert "无异常" in report["text"]
    assert "异常" in report["text"]
    assert report["decision"] == "通过"
    lesson = DAY_DOC.read_text(encoding="utf-8")
    assert "9000" in lesson
    assert "23" in lesson


def test_only_dispute_starts_three_workers_and_conflict_is_review():
    eligibility = handle_case("eligibility")
    assert eligibility["workers"] == 0

    dispute = handle_case("dispute")
    assert dispute["workers"] == 3
    assert dispute["overlap"] == 3
    assert {item["finding"] for item in dispute["findings"]} == {"异常", "通过", "复核"}
    for item in dispute["findings"]:
        assert {"owner", "evidence_id", "finding", "text"} <= set(item)
    assert dispute["decision"] == "复核"
    assert dispute["decision"] != "通过"
    assert dispute["tokens"] == 23
    assert dispute["tokens"] == sum(len(item["text"]) for item in SUMMARIES)
    assert dispute["tokens"] < 9000


def test_workers_start_only_for_dispute_2208():
    assert should_start_workers("2208") is True
    assert should_start_workers("0901") is False
    assert should_start_workers("1842") is False
