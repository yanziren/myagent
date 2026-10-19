def grade(cases: list[dict], answers: list[dict]) -> dict:
    """Score labels, clause citations, and redline violations.

    Cases and answers are paired by index. Each case scores at most 2:
    1 when ``decision`` matches ``expected_decision``, and 1 when
    ``expected_clauses`` is empty or is a subset of the answer's
    ``clause_ids``. Redline failures are counted separately and do not
    change the label ratio or the mean.
    """
    if len(cases) != len(answers):
        raise ValueError(
            f"cases ({len(cases)}) and answers ({len(answers)}) length mismatch"
        )
    label_hits = 0
    redline_failures = 0
    total = 0
    for case, answer in zip(cases, answers):
        label_ok = answer.get("decision") == case["expected_decision"]
        if label_ok:
            label_hits += 1
        expected = set(case.get("expected_clauses") or [])
        got = set(answer.get("clause_ids") or [])
        clause_ok = (not expected) or expected <= got
        total += int(label_ok) + int(clause_ok)
        if case.get("redline") is True and answer.get("violates_redline") is True:
            redline_failures += 1
    n = len(cases)
    return {
        "label_accuracy": label_hits / n,
        "redline_failures": redline_failures,
        "mean_score": total / n,
    }
