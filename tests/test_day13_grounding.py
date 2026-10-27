from claimdesk.rag.ground import answer_grounded


def test_fake_clause_and_industry_custom_are_refused():
    result = answer_grounded(
        "行业惯例的观察期是不是90天",
        "根据行业惯例，观察期一般为 90 天。[AK-FAKE]",
    )
    assert result.decision == "无法判断"
    assert result.clause_ids == []
    assert "行业惯例" not in result.rationale
    assert "AK-FAKE" not in result.rationale
    assert result.rationale == "资料不足，缺少可引用条款。"


def test_waiting_period_sentence_is_kept():
    result = answer_grounded(
        "等待期是多少天",
        "自投保日起 30 日内为等待期。[AK-2024-3.1]",
    )
    assert result.decision != "无法判断"
    assert result.decision == "答复"
    assert "AK-2024-3.1" in result.clause_ids
    assert "30" in result.rationale


def test_unrelated_question_discards_the_draft():
    draft = "根据行业惯例，观察期一般为 90 天。[AK-2024-3.1]"
    result = answer_grounded("zzzzqqqq完全无关", draft)
    assert result.decision == "无法判断"
    assert result.clause_ids == []
    assert "行业惯例" not in result.rationale
    assert "90" not in result.rationale
    assert draft not in result.rationale
