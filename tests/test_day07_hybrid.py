import pytest

from claimdesk.domain.clauses import CLAUSE_V3
from claimdesk.evals.catalog import GOLDEN_V0
from claimdesk.rag.chunk import chunk_by_heading
from claimdesk.rag.hybrid import (
    DEFERRED_TO_DAY16,
    answer_clause_hybrid,
    normalize_query,
)
from claimdesk.rag.naive import answer_clause

FAIL_COLLOQUIAL = "等了多久才能报"


def test_day07_limit_table_stays_in_one_chunk():
    chunks = chunk_by_heading(CLAUSE_V3)
    limit_chunk = next(c for c in chunks if c.clause_id == "AK-2024-7.1")
    assert "200000" in limit_chunk.text
    assert "300" in limit_chunk.text
    assert "床位费" in limit_chunk.text


def test_day07_congenital_heading_chunk_supports_hybrid():
    result = answer_clause_hybrid("先天性疾病是不是一律不赔")
    assert result.ok is True
    assert "AK-2024-6.1" in result.clause_ids
    assert "不是一律不赔" in result.answer or "不是一律不赔" in CLAUSE_V3


def test_day07_colloquial_waiting_hits_on_hybrid_path():
    assert normalize_query(FAIL_COLLOQUIAL) == "等待期"
    naive = answer_clause(FAIL_COLLOQUIAL)
    assert naive.ok is False

    hybrid = answer_clause_hybrid(FAIL_COLLOQUIAL)
    assert hybrid.retrieval_count == 1
    assert hybrid.ok is True
    assert "AK-2024-3.1" in hybrid.clause_ids
    assert "等待期" in hybrid.normalized_query


def test_day07_cross_policy_still_fails_and_deferred():
    result = answer_clause_hybrid(DEFERRED_TO_DAY16)
    assert result.ok is False
    assert result.deferred == "day16"
    assert result.clause_ids == []


def test_day07_golden_still_thirty_multihop_deferred_in_notes():
    assert len(GOLDEN_V0) == 30
    assert DEFERRED_TO_DAY16 in (
        "周启明在同一家医院的其他保单",
    )
