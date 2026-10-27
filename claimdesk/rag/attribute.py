from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from claimdesk.domain.clauses import CLAUSE_V3
from claimdesk.rag.chunk import (
    CONGENITAL_CHUNK_STRIDE,
    CONGENITAL_CHUNK_WINDOW,
    chunk_fixed_width,
    congenital_clause_body,
    extract_clause_body,
)
from claimdesk.rag.naive import _bigram_score

CONGENITAL_QUESTION = "先天性疾病是不是一律不赔"
CONGENITAL_CLAUSE_ID = "AK-2024-6.1"
ANCHOR_PHRASE = "先天性疾病不是一律不赔"
WRONG_DRAFT = "先天性疾病一律不赔"
DEFAULT_TOP_K = 3


class RecalledChunk(BaseModel):
    clause_id: str
    text: str
    score: float = 0.0


class AttributionResult(BaseModel):
    stage: Literal["retrieval", "generation"]
    subreason: str
    question: str
    draft: str
    recalled_chunks: list[RecalledChunk] = Field(default_factory=list)
    notes: str = ""


def phrase_in_recall(phrases: list[str], chunks: list[RecalledChunk]) -> bool:
    union = "".join(chunk.text for chunk in chunks)
    return any(phrase in union for phrase in phrases)


def recall_fixed_chunks(
    question: str,
    clause_id: str = CONGENITAL_CLAUSE_ID,
    *,
    window: int = CONGENITAL_CHUNK_WINDOW,
    stride: int = CONGENITAL_CHUNK_STRIDE,
    k: int = DEFAULT_TOP_K,
) -> list[RecalledChunk]:
    body = extract_clause_body(CLAUSE_V3, clause_id)
    windows = chunk_fixed_width(body, window=window, stride=stride)
    ranked = sorted(
        windows,
        key=lambda text: _bigram_score(question, text),
        reverse=True,
    )
    return [
        RecalledChunk(
            clause_id=clause_id,
            text=text,
            score=_bigram_score(question, text),
        )
        for text in ranked[:k]
    ]


def attribute_rag(
    question: str,
    draft: str,
    recalled_chunks: list[RecalledChunk],
    *,
    anchor_phrases: list[str] | None = None,
) -> AttributionResult:
    anchors = anchor_phrases or [ANCHOR_PHRASE]
    if not phrase_in_recall(anchors, recalled_chunks):
        if all(phrase in CLAUSE_V3 for phrase in anchors):
            subreason = "chunking"
            notes = "条款原文在知识库中，但固定窗切分后 top-k 未包含完整条件句。"
        else:
            subreason = "missing"
            notes = "知识库中未找到锚点句。"
        return AttributionResult(
            stage="retrieval",
            subreason=subreason,
            question=question,
            draft=draft,
            recalled_chunks=recalled_chunks,
            notes=notes,
        )

    if ANCHOR_PHRASE in draft or "不是一律不赔" in draft:
        return AttributionResult(
            stage="generation",
            subreason="ok",
            question=question,
            draft=draft,
            recalled_chunks=recalled_chunks,
            notes="草稿与锚点句一致，无需归因失败。",
        )

    return AttributionResult(
        stage="generation",
        subreason="ignore",
        question=question,
        draft=draft,
        recalled_chunks=recalled_chunks,
        notes="召回已含完整条件句，草稿仍答成一律不赔，属生成侧忽略正确片段。",
    )


def attribute_congenital_chunked_case(
    *,
    question: str = CONGENITAL_QUESTION,
    draft: str = WRONG_DRAFT,
) -> AttributionResult:
    recalled = recall_fixed_chunks(question)
    return attribute_rag(question, draft, recalled)


def attribute_congenital_generation_control(
    *,
    question: str = CONGENITAL_QUESTION,
    draft: str = WRONG_DRAFT,
) -> AttributionResult:
    full_body = congenital_clause_body()
    recalled = [
        RecalledChunk(
            clause_id=CONGENITAL_CLAUSE_ID,
            text=full_body,
            score=1.0,
        )
    ]
    return attribute_rag(question, draft, recalled)
