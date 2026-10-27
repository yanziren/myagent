from __future__ import annotations

from claimdesk.domain.models import Suggestion
from claimdesk.domain.seed import World
from claimdesk.rules.eligibility import evaluate_eligibility

REQUIRED_DOCS = ("application", "invoice", "diagnosis_certificate")

DOC_LABELS = {
    "application": "申请书",
    "invoice": "发票",
    "diagnosis_certificate": "诊断证明",
}


def _missing_required(claim) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_DOCS:
        if not claim.documents.get(key):
            missing.append(key)
    return missing


def run_intake(world: World, claim_id: str, model=None) -> Suggestion:
    claim = world.claim_of(claim_id)
    missing = _missing_required(claim)
    if missing:
        labels = [DOC_LABELS.get(key, key) for key in missing]
        return Suggestion(
            decision="补充材料",
            clause_ids=["AK-2024-2.1"],
            missing_docs=missing,
            rationale=(
                f"缺少必交材料：{', '.join(missing)}"
                f"（{', '.join(labels)}）。"
                "未根据病名或诊断正文做推断。"
            ),
        )

    return evaluate_eligibility(
        claim,
        world.policy_of(claim_id),
        world.active_waiting_days(),
        model=model,
    )
