from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


class DisputeState(TypedDict):
    evidences: Annotated[list[dict], operator.add]
    decision: str
    conflicts: list[str]
    review_queue: list[str]


def clause(_state: DisputeState) -> dict:
    return {
        "evidences": [
            {
                "owner": "clause",
                "note": "条款倾向给付",
                "leaning": "通过",
                "evidence_id": "E-CL",
            }
        ]
    }


def fraud(_state: DisputeState) -> dict:
    return {
        "evidences": [
            {
                "owner": "fraud",
                "note": "市三医院短期多次就诊",
                "leaning": "复核",
                "evidence_id": "E-HOSP",
            }
        ]
    }


def merge(state: DisputeState) -> dict:
    leanings = {item["leaning"] for item in state["evidences"]}
    if "通过" in leanings and "复核" in leanings:
        return {
            "decision": "复核",
            "conflicts": ["通过/复核"],
            "review_queue": ["CLM-2026-1842"],
        }
    return {"decision": "", "conflicts": [], "review_queue": []}


def build_merge_app():
    graph = StateGraph(DisputeState)
    graph.add_node("clause", clause)
    graph.add_node("fraud", fraud)
    graph.add_node("merge", merge)
    graph.add_edge(START, "clause")
    graph.add_edge(START, "fraud")
    graph.add_edge("clause", "merge")
    graph.add_edge("fraud", "merge")
    graph.add_edge("merge", END)
    return graph.compile(checkpointer=MemorySaver(), interrupt_before=["merge"])
