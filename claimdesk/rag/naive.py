from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from claimdesk.domain.clauses import CLAUSE_V3

DISTINCTION_QUESTION = "等待期除外和既往症除外有什么不同"
MIN_SCORE = 0.08
TOP_K = 3

_HEADING = re.compile(r"^## (AK-2024-\d+\.\d+)\s+(.+)$", re.MULTILINE)


class RetrievalLogEntry(BaseModel):
    query: str
    clause_ids: list[str] = Field(default_factory=list)
    top_score: float = 0.0


class ClauseAnswer(BaseModel):
    answer: str
    clause_ids: list[str] = Field(default_factory=list)
    retrieval_count: int = 0
    retrieval_log: list[RetrievalLogEntry] = Field(default_factory=list)
    ok: bool = True


@dataclass(frozen=True)
class _Section:
    clause_id: str
    title: str
    text: str


def _parse_sections(clause_doc: str) -> list[_Section]:
    sections: list[_Section] = []
    matches = list(_HEADING.finditer(clause_doc))
    for index, match in enumerate(matches):
        clause_id = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clause_doc)
        body = clause_doc[start:end].strip()
        sections.append(_Section(clause_id=clause_id, title=title, text=f"{title}\n{body}"))
    return sections


def _bigrams(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 2:
        return set()
    return {compact[i : i + 2] for i in range(len(compact) - 1)}


def _bigram_score(question: str, text: str) -> float:
    query_bigrams = _bigrams(question)
    if not query_bigrams:
        return 0.0
    text_bigrams = _bigrams(text)
    overlap = len(query_bigrams & text_bigrams)
    return overlap / len(query_bigrams)


def _retrieve_once(
    question: str,
    sections: list[_Section],
    *,
    k: int = TOP_K,
) -> tuple[list[_Section], RetrievalLogEntry]:
    ranked = sorted(
        sections,
        key=lambda section: _bigram_score(question, section.text),
        reverse=True,
    )
    scored = [(section, _bigram_score(question, section.text)) for section in ranked]
    top_score = scored[0][1] if scored else 0.0
    hits = [section for section, score in scored[:k] if score >= MIN_SCORE]
    log = RetrievalLogEntry(
        query=question,
        clause_ids=[section.clause_id for section in hits],
        top_score=top_score,
    )
    return hits, log


def _format_answer(hits: list[_Section]) -> str:
    parts: list[str] = []
    for section in hits:
        snippet = section.text.replace("\n", " ").strip()
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        parts.append(f"{snippet} [{section.clause_id}]")
    return " ".join(parts)


def answer_clause(question: str) -> ClauseAnswer:
    sections = _parse_sections(CLAUSE_V3)
    logs: list[RetrievalLogEntry] = []
    retrieval_count = 0

    if question == DISTINCTION_QUESTION:
        all_hits: list[_Section] = []
        seen: set[str] = set()
        for sub_query in ("等待期除外", "既往症除外"):
            hits, log = _retrieve_once(sub_query, sections)
            logs.append(log)
            retrieval_count += 1
            for section in hits:
                if section.clause_id not in seen:
                    seen.add(section.clause_id)
                    all_hits.append(section)
        clause_ids = [section.clause_id for section in all_hits]
        ok = (
            "AK-2024-3.1" in clause_ids
            and "AK-2024-5.1" in clause_ids
            and all(log.top_score >= MIN_SCORE for log in logs)
        )
        return ClauseAnswer(
            answer=_format_answer(all_hits) if ok else "",
            clause_ids=clause_ids,
            retrieval_count=retrieval_count,
            retrieval_log=logs,
            ok=ok,
        )

    hits, log = _retrieve_once(question, sections)
    logs.append(log)
    retrieval_count = 1
    clause_ids = [section.clause_id for section in hits]
    ok = bool(clause_ids) and log.top_score >= MIN_SCORE
    return ClauseAnswer(
        answer=_format_answer(hits) if ok else "",
        clause_ids=clause_ids,
        retrieval_count=retrieval_count,
        retrieval_log=logs,
        ok=ok,
    )
