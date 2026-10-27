from __future__ import annotations

from claimdesk.domain.models import Claim, Policy, Suggestion


def evaluate_eligibility(
    claim: Claim,
    policy: Policy,
    waiting_days: int,
    model=None,
) -> Suggestion:
    del model

    if policy.status != "active" or policy.product != claim.product:
        return Suggestion(
            decision="拒绝",
            clause_ids=["AK-2024-4.2"],
            rule_ids=["R-POLICY-INACTIVE"],
            rationale="保单无效或产品与案件不匹配。",
        )

    elapsed = (claim.admission - policy.issue_date).days
    if elapsed < waiting_days:
        return Suggestion(
            decision="拒绝",
            clause_ids=["AK-2024-3.1"],
            rule_ids=["R-WAITING-PERIOD"],
            rationale=(
                f"入院日距投保日 {elapsed} 日，未满等待期 {waiting_days} 日。"
            ),
        )

    if claim.hospital not in policy.hospitals:
        return Suggestion(
            decision="拒绝",
            clause_ids=["AK-2024-8.1"],
            rule_ids=["R-HOSPITAL"],
            rationale=f"医院 {claim.hospital} 不在保单定点医院列表内。",
        )

    if claim.amount > policy.limit_amount:
        return Suggestion(
            decision="拒绝",
            clause_ids=["AK-2024-7.1"],
            rule_ids=["R-LIMIT"],
            rationale=(
                f"申请金额 {claim.amount} 元超过保单限额 {policy.limit_amount} 元。"
            ),
        )

    return Suggestion(
        decision="通过",
        clause_ids=["AK-2024-4.2"],
        rule_ids=["R-ELIGIBLE"],
        rationale="保单有效，已过等待期，定点医院且未超限额。",
    )
