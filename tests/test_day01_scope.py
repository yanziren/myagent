from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _scope() -> str:
    return (ROOT / "docs" / "scope.md").read_text(encoding="utf-8")


def test_day01_scope_defines_suggestion_not_payment():
    text = _scope()
    for phrase in (
        "安澜财险",
        "核赔台",
        "安康住院2024",
        "成都",
        "决定权在核赔人",
        "不打款",
        "不写核心系统",
        "不对外发送",
        "无法判断",
        "错赔大约 4200 元",
        "错拒会变成投诉",
        "试用 10 名专员",
        "每天接口费用不超过 50 元",
    ):
        assert phrase in text, phrase
    assert "建议您考虑" not in text
    assert "比较合适" not in text


def test_day01_three_cases_are_labels_and_clause_ids_only():
    text = _scope()
    for line in (
        "CLM-2026-0901 通过 AK-2024-4.2",
        "CLM-2026-0777 补充材料 AK-2024-2.1",
        "CLM-2026-1842 复核 AK-2024-3.1",
    ):
        assert line in text
    assert "建议您考虑" not in text
    assert "比较合适" not in text
    assert "CLM-2026-1842 拒绝" not in text
