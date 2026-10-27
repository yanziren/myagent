from claimdesk.domain.clauses import CLAUSE_V3
from claimdesk.domain.clauses_v4 import CLAUSE_V4
from claimdesk.rag.index import KnowledgeBase, expected_waiting_days
from claimdesk.store.db import get_cache


def test_waiting_days_follow_the_active_version():
    assert expected_waiting_days("V3") == "30"
    assert expected_waiting_days("V4") == "90"


def test_switch_to_v4_hides_the_cached_thirty_day_answer():
    kb = KnowledgeBase()
    kb.upsert("waiting", CLAUSE_V3, "V3", "2025-11-01")
    first_version = kb.kb_version
    first = kb.answer("等待期是多少天")
    assert "30" in first
    assert "2025-11-01" in first

    kb.upsert("waiting", CLAUSE_V4, "V4", "2026-03-15")
    assert ("waiting", "V3") in kb.chunks
    second = kb.answer("等待期是多少天")
    third = kb.answer("等待期是多少天")
    assert second == third
    assert "90" in second
    assert "2026-03-15" in second
    assert "30" not in second

    old = kb.answer_cache[(first_version, "等待期是多少天")]
    assert "30" in old
    assert "30" in get_cache(kb.conn, clause_version="V3", query="等待期是多少天")
    assert "30" not in get_cache(kb.conn, clause_version="V4", query="等待期是多少天")

    versions = [
        row["version"]
        for row in kb.conn.execute("SELECT version FROM audit").fetchall()
    ]
    assert "V3" in versions
    v3_payload = kb.conn.execute(
        "SELECT payload FROM audit WHERE version = ?",
        ("V3",),
    ).fetchone()["payload"]
    assert "30" in v3_payload
