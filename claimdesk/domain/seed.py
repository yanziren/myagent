from __future__ import annotations

from datetime import date

from claimdesk.domain.models import PRODUCT_AKANG, Claim, Policy

HOSPITALS = ("市一医院", "市三医院")


def _policies() -> dict[str, Policy]:
    return {
        "POL-0901": Policy(
            policy_no="POL-0901",
            status="active",
            product=PRODUCT_AKANG,
            issue_date=date(2025, 6, 1),
            hospitals=list(HOSPITALS),
            limit_amount=20_000,
            insured_name="林小满",
        ),
        "POL-0777": Policy(
            policy_no="POL-0777",
            status="active",
            product=PRODUCT_AKANG,
            issue_date=date(2025, 8, 1),
            hospitals=list(HOSPITALS),
            limit_amount=20_000,
            insured_name="陈可",
        ),
        "POL-1842": Policy(
            policy_no="POL-1842",
            status="active",
            product=PRODUCT_AKANG,
            issue_date=date(2026, 3, 20),
            hospitals=list(HOSPITALS),
            limit_amount=200_000,
            insured_name="周启明",
        ),
        "POL-ZHOU-2": Policy(
            policy_no="POL-ZHOU-2",
            status="active",
            product=PRODUCT_AKANG,
            issue_date=date(2024, 5, 1),
            hospitals=list(HOSPITALS),
            limit_amount=200_000,
            insured_name="周启明",
        ),
    }


def _claims() -> dict[str, Claim]:
    return {
        "CLM-2026-0901": Claim(
            claim_id="CLM-2026-0901",
            policy_no="POL-0901",
            product=PRODUCT_AKANG,
            admission=date(2026, 2, 1),
            discharge=date(2026, 2, 5),
            hospital="市一医院",
            amount=800,
            documents={
                "application": True,
                "invoice": True,
                "diagnosis_certificate": True,
            },
            diagnosis_text="急性阑尾炎",
        ),
        "CLM-2026-0777": Claim(
            claim_id="CLM-2026-0777",
            policy_no="POL-0777",
            product=PRODUCT_AKANG,
            admission=date(2026, 1, 10),
            hospital="市一医院",
            amount=1200,
            documents={
                "application": True,
                "invoice": True,
            },
            diagnosis_text="",
        ),
        "CLM-2026-1842": Claim(
            claim_id="CLM-2026-1842",
            policy_no="POL-1842",
            product=PRODUCT_AKANG,
            admission=date(2026, 4, 2),
            discharge=date(2026, 4, 7),
            hospital="市三医院",
            amount=18_600,
            documents={
                "application": True,
                "invoice": True,
                "diagnosis_certificate": True,
            },
            diagnosis_text="住院医疗",
        ),
        "CLM-2026-1831": Claim(
            claim_id="CLM-2026-1831",
            policy_no="POL-ZHOU-2",
            product=PRODUCT_AKANG,
            admission=date(2026, 3, 22),
            hospital="市三医院",
            amount=420,
            documents={
                "application": True,
                "invoice": True,
                "diagnosis_certificate": True,
            },
            diagnosis_text="门诊",
        ),
    }


class World:
    def __init__(self) -> None:
        self._policies = _policies()
        self._claims = _claims()
        self.clause_version = "V3"

    def claim_of(self, claim_id: str) -> Claim:
        return self._claims[claim_id]

    def policy_of(self, claim_id: str) -> Policy:
        claim = self.claim_of(claim_id)
        return self._policies[claim.policy_no]

    def policy_by_no(self, policy_no: str) -> Policy:
        return self._policies[policy_no]

    def other_claims_for_policy(self, policy_no: str) -> list[Claim]:
        insured = self.policy_by_no(policy_no).insured_name
        same_person = {
            policy.policy_no
            for policy in self._policies.values()
            if policy.insured_name == insured
        }
        return [
            claim
            for claim in self._claims.values()
            if claim.policy_no in same_person and claim.policy_no != policy_no
        ]

    def active_waiting_days(self) -> int:
        if self.clause_version == "V4":
            return 90
        return 30


def default_world() -> World:
    return World()
