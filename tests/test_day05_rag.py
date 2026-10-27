import pytest

from claimdesk.rag.naive import DISTINCTION_QUESTION, answer_clause

CORE_CASES = [
    ("V3 等待期是多少天", "AK-2024-3.1"),
    ("既往症除外是什么意思", "AK-2024-5.1"),
    ("等待期除外和既往症除外有什么不同", ("AK-2024-3.1", "AK-2024-5.1")),
    ("定点医院有哪些", "AK-2024-8.1"),
    ("住院医疗年限额是多少", "AK-2024-7.1"),
    ("材料不齐结论是什么", "AK-2024-2.1"),
    ("先天性疾病是不是一律不赔", "AK-2024-6.1"),
    ("保障范围内住院医疗怎么赔", "AK-2024-4.2"),
]

FAIL_COLLOQUIAL = "等了多久才能报"
FAIL_CROSS_POLICY = "周启明在同一家医院的其他保单"


def test_day05_distinction_question_cites_both_clauses():
    result = answer_clause(DISTINCTION_QUESTION)
    assert result.ok is True
    assert result.retrieval_count == 2
    assert "AK-2024-3.1" in result.clause_ids
    assert "AK-2024-5.1" in result.clause_ids
    assert len(result.retrieval_log) == 2
    assert "AK-2024-3.1" in result.answer
    assert "AK-2024-5.1" in result.answer


@pytest.mark.parametrize("question,expected", CORE_CASES)
def test_day05_core_questions_retrieve_once(question, expected):
    if question == DISTINCTION_QUESTION:
        pytest.skip("covered by distinction test")
    result = answer_clause(question)
    assert result.retrieval_count == 1
    assert result.ok is True
    assert result.clause_ids
    if isinstance(expected, tuple):
        for clause_id in expected:
            assert clause_id in result.clause_ids
    else:
        assert expected in result.clause_ids
    assert len(result.retrieval_log) == 1
    assert expected in result.answer or expected.split("-")[0] in result.answer


def test_day05_colloquial_waiting_question_still_fails():
    result = answer_clause(FAIL_COLLOQUIAL)
    assert result.ok is False
    assert result.retrieval_count == 1
    assert len(result.retrieval_log) == 1
    log = result.retrieval_log[0]
    assert log.query == FAIL_COLLOQUIAL
    assert log.clause_ids == [] or "AK-2024-3.1" not in result.clause_ids


def test_day05_cross_policy_question_still_fails():
    result = answer_clause(FAIL_CROSS_POLICY)
    assert result.ok is False
    assert result.retrieval_count == 1
    log = result.retrieval_log[0]
    assert log.query == FAIL_CROSS_POLICY
    assert log.clause_ids == []
