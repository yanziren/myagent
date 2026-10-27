from __future__ import annotations

import hashlib
import sqlite3

from claimdesk.rag.chunk import chunk_by_heading
from claimdesk.rag.naive import _bigram_score
from claimdesk.store.db import append_audit, connect, get_cache, put_cache


def expected_waiting_days(version: str) -> str:
    if version == "V4":
        return "90"
    if version == "V3":
        return "30"
    raise KeyError(version)


class KnowledgeBase:
    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self.conn = conn if conn is not None else connect(":memory:")
        self.chunks: dict[tuple[str, str], list] = {}
        self.pointer: dict[str, str] = {}
        self.version_date: dict[tuple[str, str], str] = {}
        self.kb_version = 0
        self.answer_cache: dict[tuple[int, str], str] = {}

    def upsert(self, doc_id: str, text: str, version: str, version_date: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.chunks[(doc_id, version)] = chunk_by_heading(text)
        self.pointer[doc_id] = version
        self.version_date[(doc_id, version)] = version_date
        self.kb_version += 1
        return digest

    def _current_chunks(self) -> list:
        found = []
        for doc_id, version in self.pointer.items():
            found.extend(self.chunks.get((doc_id, version), []))
        return found

    def search(self, query: str) -> str:
        chunks = self._current_chunks()
        if not chunks:
            return ""
        best = max(chunks, key=lambda chunk: _bigram_score(query, chunk.text))
        return best.text

    def answer(self, query: str) -> str:
        key = (self.kb_version, query)
        cached = self.answer_cache.get(key)
        if cached is not None:
            return cached
        doc_id = next(iter(self.pointer))
        version = self.pointer[doc_id]
        version_date = self.version_date[(doc_id, version)]
        body = self.search(query)
        if version_date not in body:
            body = f"{body}\n版本日期：{version_date}"
        self.answer_cache[key] = body
        put_cache(self.conn, clause_version=version, query=query, value=body)
        append_audit(
            self.conn,
            action="answer",
            amount=0,
            target=query,
            approver="index",
            version=version,
            payload=body,
        )
        return body
