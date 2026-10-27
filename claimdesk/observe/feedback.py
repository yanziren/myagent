from __future__ import annotations


class Feedback:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def accept(self, text: str, trace_id: str | None = None) -> None:
        if not trace_id:
            raise ValueError("反馈必须带 trace_id")
        self.rows.append({"text": text, "trace_id": trace_id})


def slice_success(rows: list[dict]) -> dict:
    global_rate = sum(bool(row["ok"]) for row in rows) / len(rows)
    hard = [row for row in rows if row["difficulty"] == "hard"]
    return {
        "global": global_rate,
        "by_difficulty": {
            "hard": sum(bool(row["ok"]) for row in hard) / len(hard),
        },
    }


def slice_by_intent(jobs: list[dict]) -> dict:
    grouped: dict[str, list[bool]] = {}
    for job in jobs:
        grouped.setdefault(job["intent"], []).append(bool(job["ok"]))
    by_intent = {
        intent: sum(flags) / len(flags) for intent, flags in grouped.items()
    }
    everything = [flag for flags in grouped.values() for flag in flags]
    return {
        "global": sum(everything) / len(everything),
        "by_intent": by_intent,
    }
