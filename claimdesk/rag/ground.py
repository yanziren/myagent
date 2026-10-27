from __future__ import annotations

import re

from claimdesk.domain.clauses import CLAUSE_V3
from claimdesk.domain.models import Suggestion
from claimdesk.rag.chunk import chunk_by_heading
from claimdesk.rag.naive import _bigram_score

_CITE = re.compile(r"([^\[\]]+?)\[(AK-[^\]]+)\]")
_INSUFFICIENT = "资料不足，缺少可引用条款。"


def answer_grounded(question: str, draft: str) -> Suggestion:
    chunks = chunk_by_heading(CLAUSE_V3)
    best = 0.0
    bodies = {chunk.clause_id: chunk.text for chunk in chunks}
    for chunk in chunks:
        best = max(best, _bigram_score(question, chunk.text))
    if best <= 0:
        return Suggestion(
            decision="无法判断",
            clause_ids=[],
            rationale=_INSUFFICIENT,
        )

    kept: list[str] = []
    clause_ids: list[str] = []
    for match in _CITE.finditer(draft):
        sentence = match.group(1).strip(" 。，")
        clause_id = match.group(2)
        body = bodies.get(clause_id, "")
        if sentence and sentence in body:
            kept.append(sentence)
            clause_ids.append(clause_id)
    if not kept:
        return Suggestion(
            decision="无法判断",
            clause_ids=[],
            rationale=_INSUFFICIENT,
        )
    return Suggestion(
        decision="答复",
        clause_ids=clause_ids,
        rationale="。".join(kept),
    )
