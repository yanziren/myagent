import inspect

from claimdesk.agent import loop
from claimdesk.multiagent.merge_graph import build_merge_app


def test_simple_loop_source_does_not_mention_langgraph():
    assert "langgraph" not in inspect.getsource(loop).lower()


def test_workers_append_evidence_and_merge_interrupts():
    app = build_merge_app()
    config = {"configurable": {"thread_id": "1842"}}
    initial = {"evidences": [], "decision": "", "conflicts": [], "review_queue": []}
    app.invoke(initial, config)
    paused = app.get_state(config)
    assert paused.next == ("merge",)
    assert len(paused.values["evidences"]) >= 2

    app.invoke(None, config)
    finished = app.get_state(config).values
    notes = "".join(item["note"] for item in finished["evidences"])
    assert "条款" in notes
    assert "市三医院" in notes
    assert finished["decision"] == "复核"
    assert "通过/复核" in finished["conflicts"]
    assert finished["review_queue"] == ["CLM-2026-1842"]
    owners = {item["owner"] for item in finished["evidences"]}
    assert owners == {"clause", "fraud"}
