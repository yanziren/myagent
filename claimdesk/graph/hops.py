from __future__ import annotations

from dataclasses import dataclass

from claimdesk.rag.hybrid import answer_clause_hybrid
from claimdesk.rag.naive import answer_clause

EDGES: list[tuple[str, str, str]] = [
    ("person:周启明", "holds", "policy:POL-1842"),
    ("person:周启明", "holds", "policy:POL-ZHOU-2"),
    ("person:林小满", "holds", "policy:POL-0901"),
    ("person:陈可", "holds", "policy:POL-0777"),
    ("policy:POL-1842", "has_claim", "claim:CLM-2026-1842"),
    ("policy:POL-ZHOU-2", "has_claim", "claim:CLM-2026-1831"),
    ("policy:POL-0901", "has_claim", "claim:CLM-2026-0901"),
    ("policy:POL-0777", "has_claim", "claim:CLM-2026-0777"),
    ("claim:CLM-2026-1842", "at", "hospital:市三医院"),
    ("claim:CLM-2026-1831", "at", "hospital:市三医院"),
    ("claim:CLM-2026-0901", "at", "hospital:市一医院"),
    ("claim:CLM-2026-0777", "at", "hospital:市一医院"),
]

PAIRS = [
    ("周启明名下其他保单有没有在市三医院就诊", "POL-ZHOU-2"),
    ("市三医院上还有哪张保单", "POL-ZHOU-2"),
    ("和 CLM-2026-1842 同一被保险人的另一张案件", "CLM-2026-1831"),
]


@dataclass(frozen=True)
class HopAnswer:
    text: str
    edges: list[str]


def _nodes_in(question: str) -> list[str]:
    found: list[str] = []
    for source, _rel, target in EDGES:
        for node in (source, target):
            label = node.split(":", 1)[1]
            if label in question and node not in found:
                found.append(node)
    return found


def _person_for_claim(claim_node: str) -> str | None:
    policy = None
    for source, rel, target in EDGES:
        if rel == "has_claim" and target == claim_node:
            policy = source
    if policy is None:
        return None
    for source, rel, target in EDGES:
        if rel == "holds" and target == policy:
            return source
    return None


def _walk(starts: list[str], depth: int = 2) -> tuple[set[str], list[str]]:
    seen = set(starts)
    frontier = list(starts)
    used: list[str] = []
    for _ in range(depth):
        nxt: list[str] = []
        for node in frontier:
            for source, rel, target in EDGES:
                pair = None
                if source == node:
                    pair = target
                elif target == node:
                    pair = source
                if pair is None:
                    continue
                rendered = f"{source} -{rel}-> {target}"
                if rendered not in used:
                    used.append(rendered)
                if pair not in seen:
                    seen.add(pair)
                    nxt.append(pair)
        frontier = nxt
    return seen, used


def answer_hops(question: str) -> HopAnswer:
    starts = _nodes_in(question)
    linked = list(starts)
    for node in starts:
        if node.startswith("claim:"):
            person = _person_for_claim(node)
            if person and person not in linked:
                linked.append(person)
    seen, edges = _walk(linked, 2)
    labels = []
    for node in seen:
        if node.startswith("policy:") or node.startswith("claim:"):
            labels.append(node.split(":", 1)[1])
    return HopAnswer(text=" ".join(labels), edges=edges)


def graph_wins(pairs: list[tuple[str, str]] = PAIRS) -> int:
    wins = 0
    for question, expected in pairs:
        graph_text = answer_hops(question).text
        naive_text = answer_clause(question).answer
        if expected in graph_text and expected not in naive_text:
            wins += 1
    return wins
