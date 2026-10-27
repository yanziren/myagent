from pathlib import Path

from claimdesk.graph.hops import PAIRS, answer_hops, graph_wins
from claimdesk.rag.hybrid import answer_clause_hybrid


def test_zhou_qiming_other_policy_is_reached_in_two_hops():
    answer = answer_hops("周启明名下其他保单有没有在市三医院就诊")
    assert "POL-ZHOU-2" in answer.text
    assert any("holds" in edge or "has_claim" in edge for edge in answer.edges)


def test_graph_wins_at_least_three_multihop_questions():
    assert graph_wins(PAIRS) >= 3
    hospital = answer_hops("市三医院上还有哪张保单")
    assert "POL-ZHOU-2" in hospital.text
    sibling = answer_hops("和 CLM-2026-1842 同一被保险人的另一张案件")
    assert "CLM-2026-1831" in sibling.text


def test_clause_question_does_not_use_the_graph():
    answered = answer_clause_hybrid("先天性疾病是不是一律不赔")
    assert "投保前已患" in answered.answer
    hybrid_source = (
        Path(__file__).resolve().parents[1] / "claimdesk" / "rag" / "hybrid.py"
    ).read_text(encoding="utf-8")
    assert "answer_hops" not in hybrid_source
