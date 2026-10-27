from auditdesk.evals.catalog import load_cases
from auditdesk.rules.review import Checklist, review_contract


def test_golden_set_has_40_hand_labeled_cases() -> None:
    cases = load_cases()
    assert len(cases) == 40
    assert len({case["id"] for case in cases}) == 40


def test_every_golden_case_matches_decision_rules_and_quotes() -> None:
    for case in load_cases():
        result = review_contract(case["text"])
        assert result.model_calls == 0
        assert result.decision == case["expected_decision"], case["id"]
        assert result.rule_ids == case["expected_rule_ids"], case["id"]
        assert [finding.rule_id for finding in result.findings] == result.rule_ids
        for finding in result.findings:
            if finding.quote:
                assert finding.quote in case["text"], case["id"]
            else:
                assert finding.rule_id.startswith("R-MISSING-")


def test_second_customer_reuses_the_same_checker() -> None:
    text = next(case["text"] for case in load_cases() if case["id"] == "G26")
    first = review_contract(text)
    assert first.decision == "review"
    assert first.checklist_name == "服务合同"

    second = review_contract(
        text,
        checklist=Checklist(name="服务合同", amount_review_from=100_000),
    )
    assert second.decision == "pass"
    assert second.rule_ids == ["R-ELIGIBLE"]
    assert second.checklist_name == "服务合同"
