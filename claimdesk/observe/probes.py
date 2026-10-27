from __future__ import annotations

from claimdesk.rag.ground import answer_grounded

PROBE_QUESTION = "等待期是多少天"
PROBE_CLAUSE = "AK-2024-3.1"


class Probe:
    def __init__(self) -> None:
        self.last_model_id: str | None = None

    def run_probe(self, model_id: str, answer_fn) -> dict:
        answer = answer_fn(PROBE_QUESTION)
        changed = self.last_model_id is not None and model_id != self.last_model_id
        alert = changed or "30" not in answer or PROBE_CLAUSE not in answer
        self.last_model_id = model_id
        return {"alert": alert, "model_id": model_id, "answer": answer}


def rag_dims(case: dict) -> dict:
    context = case.get("context", "")
    expected = case.get("expected_clause", "")
    question = case.get("question", "")
    answer = case.get("answer", "")
    relevant_blocks = case.get("relevant_blocks", 1)
    irrelevant_blocks = case.get("irrelevant_blocks", 0)
    recall = bool(expected) and expected in context
    precision = not (irrelevant_blocks > relevant_blocks)
    grounded = answer_grounded(question or PROBE_QUESTION, answer)
    faithfulness = grounded.decision != "无法判断" and expected in grounded.clause_ids
    relevance = not ("等待期" in question and "床位费" in answer and "等待期" not in answer)
    forced = case.get("broken")
    result = {
        "recall": recall,
        "precision": precision,
        "faithfulness": faithfulness,
        "relevance": relevance,
    }
    if forced in result:
        result[forced] = False
    return result
