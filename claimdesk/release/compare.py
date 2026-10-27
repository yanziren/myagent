from __future__ import annotations

from claimdesk.guards.approval import ApprovalBook


def compare(rows: list[dict]) -> dict:
    by_scenario: dict[str, dict] = {}
    for row in rows:
        slot = by_scenario.setdefault(
            row["scenario"],
            {"old_fake": 0, "new_fake": 0, "same": 0, "n": 0},
        )
        slot["n"] += 1
        if row["old"].get("fake_clause"):
            slot["old_fake"] += 1
        if row["new"].get("fake_clause"):
            slot["new_fake"] += 1
        if row["old"].get("decision") == row["new"].get("decision"):
            slot["same"] += 1
    blocked = [
        name
        for name, slot in by_scenario.items()
        if slot["new_fake"] > slot["old_fake"]
    ]
    return {"by_scenario": by_scenario, "blocked": bool(blocked), "scenarios": blocked}


def pairwise(judge, left: str, right: str) -> str:
    first = judge(left, right)
    second = judge(right, left)

    def chosen(label: str, this_left: str, this_right: str) -> str:
        return this_left if label == "left" else this_right

    picked_first = chosen(first, left, right)
    picked_second = chosen(second, right, left)
    if picked_first == picked_second == left:
        return "old"
    if picked_first == picked_second == right:
        return "new"
    return "human"


def calibrated(agreements: int, total: int = 4, threshold: float = 0.85) -> bool:
    return agreements / total >= threshold


def shadow_send(book: ApprovalBook, ticket_id: str) -> dict:
    del ticket_id
    return {"executed": False, "sent": list(book.sent)}


class ModelConfig:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id


def rollback(config: ModelConfig, previous: str) -> str:
    config.model_id = previous
    return config.model_id
