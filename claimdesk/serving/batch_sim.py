from __future__ import annotations


def _prepare(arrivals: list[dict]) -> list[dict]:
    prepared = []
    for index, item in enumerate(arrivals):
        prepared.append(
            {
                "index": index,
                "prefill_ms": item["prefill_ms"],
                "remaining": item["tokens"],
                "ttft": None,
                "started": False,
            }
        )
    return prepared


def simulate(arrivals: list[dict], batch_cap: int) -> dict:
    pending = _prepare(arrivals)
    everyone = list(pending)
    active: list[dict] = []
    now = 0.0
    tpots: list[float] = []
    while pending or any(item["remaining"] > 0 for item in active):
        active = [item for item in active if item["remaining"] > 0]
        while len(active) < batch_cap and pending:
            active.append(pending.pop(0))
        if not active:
            break
        for item in active:
            if not item["started"]:
                item["ttft"] = now + item["prefill_ms"]
                item["started"] = True
        tpot = 1 + len(active) * 0.2
        tpots.append(tpot)
        now += tpot
        for item in active:
            item["remaining"] -= 1
    finished = sorted(everyone, key=lambda item: item["index"])
    return {
        "mean_tpot": sum(tpots) / len(tpots) if tpots else 0.0,
        "ttft_ms": [item["ttft"] for item in finished],
    }


def static_batch(arrivals: list[dict]) -> list[float]:
    prefill = max(item["prefill_ms"] for item in arrivals)
    return [prefill for _ in arrivals]
