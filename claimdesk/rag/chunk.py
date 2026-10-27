from __future__ import annotations

import re
from dataclasses import dataclass

from claimdesk.domain.clauses import CLAUSE_V3

# Day 6 instrument: fixed-width split (Day 7 adds chunk_by_heading).
CONGENITAL_CHUNK_WINDOW = 14
CONGENITAL_CHUNK_STRIDE = 7

_HEADING = re.compile(r"^## (AK-2024-\d+\.\d+)\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class HeadingChunk:
    clause_id: str
    title: str
    text: str


def chunk_by_heading(clause_doc: str) -> list[HeadingChunk]:
    matches = list(_HEADING.finditer(clause_doc))
    chunks: list[HeadingChunk] = []
    for index, match in enumerate(matches):
        clause_id = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(clause_doc)
        )
        body = clause_doc[start:end].strip()
        chunks.append(
            HeadingChunk(clause_id=clause_id, title=title, text=f"{title}\n{body}")
        )
    return chunks


def chunk_fixed_width(text: str, *, window: int, stride: int) -> list[str]:
    compact = re.sub(r"\s+", "", text)
    if window <= 0 or stride <= 0 or len(compact) < window:
        return [compact] if compact else []
    chunks: list[str] = []
    for start in range(0, len(compact) - window + 1, stride):
        chunks.append(compact[start : start + window])
    if not chunks:
        chunks.append(compact)
    return chunks


def extract_clause_body(clause_doc: str, clause_id: str) -> str:
    matches = list(_HEADING.finditer(clause_doc))
    for index, match in enumerate(matches):
        if match.group(1) != clause_id:
            continue
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(clause_doc)
        )
        return clause_doc[start:end].strip()
    raise KeyError(clause_id)


def congenital_clause_body() -> str:
    return extract_clause_body(CLAUSE_V3, "AK-2024-6.1")
