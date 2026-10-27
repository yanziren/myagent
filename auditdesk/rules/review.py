from __future__ import annotations

import re

from pydantic import BaseModel, Field


class Checklist(BaseModel):
    name: str = "服务合同"
    amount_review_from: int = 50_000


class Finding(BaseModel):
    rule_id: str
    quote: str = ""


class ContractReview(BaseModel):
    decision: str
    rule_ids: list[str]
    findings: list[Finding]
    model_calls: int = 0
    checklist_name: str
    rationale: str


_AMOUNT = re.compile(r"合同金额[:：]\s*(\d+)\s*元")
_TERM = re.compile(r"有效期[:：]\s*(\d+)\s*个月")
_ATTACHMENT_REF = re.compile(r"见附件|详见附件")
_UNCAPPED = ("无限责任", "不设上限", "全部损失")
_SCOPE = ("服务内容", "交付内容", "工作内容")

_ORDER = [
    "R-MISSING-PARTY",
    "R-MISSING-AMOUNT",
    "R-MISSING-SIGN",
    "R-MISSING-ATTACHMENT",
    "R-MISSING-PAYMENT",
    "R-MISSING-SCOPE",
    "R-MISSING-LIABILITY",
    "R-MISSING-CONFIDENTIAL",
    "R-MISSING-DISPUTE",
    "R-MISSING-TERM",
    "R-AMOUNT-REVIEW",
    "R-LIABILITY-UNCAPPED",
    "R-DISPUTE-CONFLICT",
    "R-TERM-CONFLICT",
    "R-AMOUNT-CONFLICT",
    "R-ELIGIBLE",
]

_RATIONALE = {
    "pass": "必备条款齐全，金额未过复核线。",
    "need_docs": "材料或必备条款缺失，先补齐再审。",
    "review": "条款触发人工复核，不能直接出具通过。",
}


def _line_with(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return line.strip()
    return ""


def _first_amount_line(text: str) -> str:
    for line in text.splitlines():
        if _AMOUNT.search(line):
            return line.strip()
    return ""


def review_contract(
    text: str,
    checklist: Checklist | None = None,
) -> ContractReview:
    checklist = checklist or Checklist()
    fired: dict[str, str] = {}

    has_a = "甲方：" in text or "甲方:" in text
    has_b = "乙方：" in text or "乙方:" in text
    if not has_a or not has_b:
        fired["R-MISSING-PARTY"] = ""

    amounts = [int(value) for value in _AMOUNT.findall(text)]
    if not amounts:
        fired["R-MISSING-AMOUNT"] = ""
    else:
        if len(set(amounts)) > 1:
            fired["R-AMOUNT-CONFLICT"] = _first_amount_line(text)
        if any(amount >= checklist.amount_review_from for amount in amounts):
            fired["R-AMOUNT-REVIEW"] = _first_amount_line(text)

    if "签字" not in text and "盖章" not in text:
        fired["R-MISSING-SIGN"] = ""

    if _ATTACHMENT_REF.search(text) and "附件：" not in text and "附件:" not in text:
        fired["R-MISSING-ATTACHMENT"] = ""

    if "付款" not in text:
        fired["R-MISSING-PAYMENT"] = ""

    if not any(label in text for label in _SCOPE):
        fired["R-MISSING-SCOPE"] = ""

    if "违约" not in text:
        fired["R-MISSING-LIABILITY"] = ""
    else:
        for needle in _UNCAPPED:
            quote = _line_with(text, needle)
            if quote:
                fired["R-LIABILITY-UNCAPPED"] = quote
                break

    if "保密" not in text:
        fired["R-MISSING-CONFIDENTIAL"] = ""

    has_court = "人民法院" in text
    has_arb = "仲裁" in text
    if has_court and has_arb:
        fired["R-DISPUTE-CONFLICT"] = _line_with(text, "争议解决") or _line_with(
            text, "人民法院"
        )
    elif not has_court and not has_arb:
        fired["R-MISSING-DISPUTE"] = ""

    terms = _TERM.findall(text)
    if not terms:
        fired["R-MISSING-TERM"] = ""
    elif len(set(terms)) > 1:
        fired["R-TERM-CONFLICT"] = _line_with(text, "有效期")

    missing = [rule_id for rule_id in _ORDER if rule_id.startswith("R-MISSING-") and rule_id in fired]
    review = [
        rule_id
        for rule_id in _ORDER
        if rule_id in fired and not rule_id.startswith("R-MISSING-")
    ]
    if missing:
        decision = "need_docs"
        rule_ids = missing + review
    elif review:
        decision = "review"
        rule_ids = review
    else:
        decision = "pass"
        rule_ids = ["R-ELIGIBLE"]
        fired["R-ELIGIBLE"] = _first_amount_line(text)

    return ContractReview(
        decision=decision,
        rule_ids=rule_ids,
        findings=[Finding(rule_id=rule_id, quote=fired.get(rule_id, "")) for rule_id in rule_ids],
        model_calls=0,
        checklist_name=checklist.name,
        rationale=_RATIONALE[decision],
    )
