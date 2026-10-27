from __future__ import annotations

import threading
import time

FIRST_FEEDBACK_MS = 2000
SIMPLE_DONE_MS = 20000
STEP_NAMES = ("route", "retrieve", "model", "tool", "generate")


class TimeLine:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self.marks: list[tuple[str, float]] = []

    def mark(self, name: str) -> None:
        self.marks.append((name, (time.perf_counter() - self._t0) * 1000))

    def report(self, samples: list[float] | None = None) -> dict:
        offsets: dict[str, float] = {}
        for name, ms in self.marks:
            offsets.setdefault(name, ms)
        raw = list(samples or [])
        ordered = sorted(raw)

        def pick(pct: float) -> float:
            if not ordered:
                return 0.0
            index = int((pct / 100) * (len(ordered) - 1))
            return ordered[min(len(ordered) - 1, max(0, index))]

        return {
            "offsets": offsets,
            "samples": raw,
            "p50": pick(50),
            "p95": pick(95),
            "p99": pick(99),
        }


def emit(events: list[dict]) -> dict:
    progress = next(event for event in events if event["kind"] == "progress")
    final = next(event for event in events if event["kind"] == "final")
    return {
        "progress_before_final": progress["t"] < final["t"],
        "progress_ms": progress["t"],
    }


def within_budget(events: list[dict]) -> bool:
    final = next(event for event in events if event["kind"] == "final")
    progress = next((event for event in events if event["kind"] == "progress"), None)
    if progress is not None and progress["t"] > FIRST_FEEDBACK_MS:
        return False
    return final["t"] <= SIMPLE_DONE_MS


def parallel_reads(durations_ms: list[int]) -> float:
    start = time.perf_counter()
    threads = [
        threading.Thread(target=time.sleep, args=(duration / 1000,))
        for duration in durations_ms
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return (time.perf_counter() - start) * 1000


def claim_batch(conn, n: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, claim_id, status, intent
        FROM jobs
        WHERE status = 'accepted'
        ORDER BY rowid
        LIMIT ?
        """,
        (n,),
    ).fetchall()
    return [dict(row) for row in rows]
