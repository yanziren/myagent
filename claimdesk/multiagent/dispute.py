from __future__ import annotations

import threading
import time

SHORT = "无异常。。"
FULL_DOCS = [SHORT * 600, "条款原文。" * 600, "判例原文。" * 600]
SUMMARIES = [
    {"owner": "medical", "evidence_id": "E-MED", "finding": "异常", "text": "医学摘要：异常"},
    {"owner": "clause", "evidence_id": "E-CL", "finding": "通过", "text": "条款摘要：建议通过"},
    {"owner": "precedent", "evidence_id": "E-PR", "finding": "复核", "text": "判例摘要：复核"},
]


def single_agent_report() -> dict:
    text = "".join(FULL_DOCS)
    return {"tokens": len(text), "text": text, "decision": "通过"}


def should_start_workers(case_id: str) -> bool:
    return case_id == "2208"


def run_parallel(functions: list) -> tuple[list, int]:
    overlap = {"current": 0, "max": 0}
    lock = threading.Lock()
    results: list = [None] * len(functions)

    def run_one(index: int, fn) -> None:
        with lock:
            overlap["current"] += 1
            overlap["max"] = max(overlap["max"], overlap["current"])
        try:
            results[index] = fn()
        finally:
            with lock:
                overlap["current"] -= 1

    threads = [
        threading.Thread(target=run_one, args=(index, fn))
        for index, fn in enumerate(functions)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results, overlap["max"]


def _worker(summary: dict):
    def run() -> dict:
        time.sleep(0.05)
        return dict(summary)

    return run


def handle_case(intent: str) -> dict:
    if intent != "dispute":
        return {"workers": 0, "tokens": 0, "decision": "", "findings": [], "overlap": 0}
    findings, overlap = run_parallel([_worker(item) for item in SUMMARIES])
    values = {item["finding"] for item in findings}
    decision = "复核" if len(values) > 1 else findings[0]["finding"]
    tokens = sum(len(item["text"]) for item in SUMMARIES)
    return {
        "workers": 3,
        "tokens": tokens,
        "decision": decision,
        "findings": findings,
        "overlap": overlap,
    }
