from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from claimdesk.domain.clauses import CLAUSE_V3
from claimdesk.rag.chunk import HeadingChunk, chunk_by_heading
from claimdesk.rag.naive import _bigram_score
from claimdesk.rag.rrf import reciprocal_rank_fusion

TERM_MAP: dict[str, str] = {
    "等了多久才能报": "等待期",
}

DEFERRED_TO_DAY16 = "周启明在同一家医院的其他保单"
HYBRID_TOP_K = 8
RRF_K = 60
MIN_SCORE = 0.05

RerankFn = Callable[[str, list[HeadingChunk]], list[HeadingChunk]]


class HybridAnswer(BaseModel):
    answer: str
    clause_ids: list[str] = Field(default_factory=list)
    retrieval_count: int = 1
    normalized_query: str = ""
    ok: bool = True
    deferred: Literal["day16"] | None = None
    notes: str = ""


def normalize_query(question: str) -> str:
    normalized = question
    for spoken, canonical in TERM_MAP.items():
        if spoken in normalized:
            normalized = normalized.replace(spoken, canonical)
    return normalized


def _char_tokens(text: str) -> list[str]:
    return list(re.sub(r"\s+", "", text))


def _bm25_ranking(query: str, chunks: list[HeadingChunk]) -> list[str]:
    corpus = [_char_tokens(chunk.text) for chunk in chunks]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_char_tokens(query))
    ranked = sorted(
        range(len(chunks)),
        key=lambda index: scores[index],
        reverse=True,
    )
    return [chunks[index].clause_id for index in ranked]


def _overlap_ranking(query: str, chunks: list[HeadingChunk]) -> list[str]:
    ranked = sorted(
        chunks,
        key=lambda chunk: _bigram_score(query, chunk.text),
        reverse=True,
    )
    return [chunk.clause_id for chunk in ranked]


def _default_rerank(_question: str, chunks: list[HeadingChunk]) -> list[HeadingChunk]:
    return chunks


def _format_answer(chunks: list[HeadingChunk]) -> str:
    parts: list[str] = []
    for chunk in chunks[:3]:
        snippet = chunk.text.replace("\n", " ").strip()
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        parts.append(f"{snippet} [{chunk.clause_id}]")
    return " ".join(parts)


def answer_clause_hybrid(
    question: str,
    *,
    rerank: RerankFn | None = None,
) -> HybridAnswer:
    if question == DEFERRED_TO_DAY16:
        return HybridAnswer(
            answer="",
            clause_ids=[],
            retrieval_count=1,
            normalized_query=question,
            ok=False,
            deferred="day16",
            notes="跨保单多跳留到第 16 天小图，今天不建 GraphRAG。",
        )

    normalized = normalize_query(question)
    chunks = chunk_by_heading(CLAUSE_V3)
    by_id = {chunk.clause_id: chunk for chunk in chunks}

    fused_ids = reciprocal_rank_fusion(
        [
            _bm25_ranking(normalized, chunks),
            _overlap_ranking(normalized, chunks),
        ],
        k=RRF_K,
    )
    top_chunks = [by_id[clause_id] for clause_id in fused_ids[:HYBRID_TOP_K]]
    rerank_fn = rerank or _default_rerank
    top_chunks = rerank_fn(normalized, top_chunks)

    hits = [
        chunk
        for chunk in top_chunks
        if _bigram_score(normalized, chunk.text) >= MIN_SCORE
        or _bigram_score(question, chunk.text) >= MIN_SCORE
    ]
    if not hits and top_chunks:
        hits = [top_chunks[0]]

    clause_ids = [chunk.clause_id for chunk in hits]
    top_score = max(
        (_bigram_score(normalized, chunk.text) for chunk in hits),
        default=0.0,
    )
    ok = bool(clause_ids) and top_score >= MIN_SCORE

    return HybridAnswer(
        answer=_format_answer(hits) if ok else "",
        clause_ids=clause_ids,
        retrieval_count=1,
        normalized_query=normalized,
        ok=ok,
        notes="",
    )
