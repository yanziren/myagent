"""40 synthetic service contracts with hand-written expected labels.

These are practice documents, not anyone's real contract. The expected
decision is fixed here so the checker cannot grade itself.
"""

from __future__ import annotations


def service_contract(
    *,
    party_a: str | None = "甲公司",
    party_b: str | None = "乙公司",
    scope_line: str | None = "服务内容：按月提供系统维护。",
    amounts: tuple[str, ...] = ("12000",),
    amount_lines: list[str] | None = None,
    payment: bool = True,
    terms: tuple[str, ...] = ("12",),
    liability: str | None = "违约金不超过合同金额的20%。",
    confidential: bool = True,
    dispute: str | None = "提交甲方所在地人民法院。",
    signed: str = "both",
    attachment: str | None = None,
) -> str:
    lines = ["服务合同"]
    if party_a is not None:
        lines.append(f"甲方：{party_a}")
    if party_b is not None:
        lines.append(f"乙方：{party_b}")
    if scope_line is not None:
        lines.append(scope_line)
    if amount_lines is not None:
        lines.extend(amount_lines)
    else:
        lines.extend(f"合同金额：{amount}元" for amount in amounts)
    if payment:
        lines.append("付款：验收后十个工作日内支付。")
    lines.extend(f"有效期：{term}个月" for term in terms)
    if liability is not None:
        lines.append(f"违约：{liability}")
    if confidential:
        lines.append("保密：双方对商业秘密保密。")
    if dispute is not None:
        lines.append(f"争议解决：{dispute}")
    if attachment == "missing":
        lines.append("交付清单见附件。")
    elif attachment == "present":
        lines.append("交付清单见附件。")
        lines.append("附件：报价单，共一页。")
    if signed == "both":
        lines.append(f"签字：{party_a or '甲公司'}")
        lines.append(f"盖章：{party_b or '乙公司'}")
    elif signed == "stamp":
        lines.append("盖章：乙公司")
    elif signed == "sign":
        lines.append("签字：甲公司")
    elif signed != "none":
        raise ValueError(signed)
    return "\n".join(lines) + "\n"


def load_cases() -> list[dict]:
    rows: list[dict] = []

    def add(case_id: str, decision: str, rule_ids: list[str], **kwargs: object) -> None:
        rows.append(
            {
                "id": case_id,
                "text": service_contract(**kwargs),  # type: ignore[arg-type]
                "expected_decision": decision,
                "expected_rule_ids": rule_ids,
            }
        )

    add("G01", "pass", ["R-ELIGIBLE"])
    add("G02", "pass", ["R-ELIGIBLE"], amounts=("3000",), dispute="提交北京仲裁委员会。")
    add("G03", "pass", ["R-ELIGIBLE"], amounts=("49999",))
    add(
        "G04",
        "pass",
        ["R-ELIGIBLE"],
        party_a="星河科技",
        party_b="北岸咨询",
        amounts=("8000",),
    )
    add("G05", "pass", ["R-ELIGIBLE"], scope_line="工作内容：驻场支持。", amounts=("15000",))
    add("G06", "pass", ["R-ELIGIBLE"], scope_line="交付内容：交付维护报告。", amounts=("22000",))
    add("G07", "pass", ["R-ELIGIBLE"], signed="stamp", amounts=("18000",))
    add("G08", "pass", ["R-ELIGIBLE"], attachment="present", amounts=("9000",))
    add("G09", "pass", ["R-ELIGIBLE"], amounts=("25000",))
    add("G10", "pass", ["R-ELIGIBLE"], terms=("6",), amounts=("6000",))

    add("G11", "need_docs", ["R-MISSING-PARTY"], party_b=None)
    add("G12", "need_docs", ["R-MISSING-PARTY"], party_a=None)
    add("G13", "need_docs", ["R-MISSING-AMOUNT"], amount_lines=["合同金额：待定元"])
    add("G14", "need_docs", ["R-MISSING-AMOUNT"], amount_lines=[])
    add("G15", "need_docs", ["R-MISSING-SIGN"], signed="none")
    add("G16", "need_docs", ["R-MISSING-ATTACHMENT"], attachment="missing")
    add("G17", "need_docs", ["R-MISSING-PAYMENT"], payment=False)
    add("G18", "need_docs", ["R-MISSING-SCOPE"], scope_line=None)
    add("G19", "need_docs", ["R-MISSING-LIABILITY"], liability=None)
    add("G20", "need_docs", ["R-MISSING-CONFIDENTIAL"], confidential=False)
    add("G21", "need_docs", ["R-MISSING-DISPUTE"], dispute=None)
    add("G22", "need_docs", ["R-MISSING-TERM"], terms=())
    add(
        "G23",
        "need_docs",
        ["R-MISSING-SIGN", "R-AMOUNT-REVIEW"],
        signed="none",
        amounts=("80000",),
    )
    add(
        "G24",
        "need_docs",
        ["R-MISSING-ATTACHMENT", "R-MISSING-CONFIDENTIAL"],
        attachment="missing",
        confidential=False,
    )

    add("G25", "review", ["R-AMOUNT-REVIEW"], amounts=("50000",))
    add("G26", "review", ["R-AMOUNT-REVIEW"], amounts=("80000",))
    add("G27", "review", ["R-AMOUNT-REVIEW"], amounts=("200000",))
    add("G28", "review", ["R-LIABILITY-UNCAPPED"], liability="不设上限。")
    add("G29", "review", ["R-LIABILITY-UNCAPPED"], liability="构成无限责任。")
    add("G30", "review", ["R-LIABILITY-UNCAPPED"], liability="赔偿全部损失。")
    add(
        "G31",
        "review",
        ["R-DISPUTE-CONFLICT"],
        dispute="提交甲方所在地人民法院，或提交北京仲裁委员会。",
    )
    add("G32", "review", ["R-TERM-CONFLICT"], terms=("12", "24"))
    add("G33", "review", ["R-AMOUNT-CONFLICT"], amounts=("12000", "15000"))
    add(
        "G34",
        "review",
        ["R-AMOUNT-REVIEW", "R-LIABILITY-UNCAPPED"],
        amounts=("80000",),
        liability="不设上限。",
    )
    add(
        "G35",
        "review",
        ["R-AMOUNT-REVIEW", "R-DISPUTE-CONFLICT"],
        amounts=("60000",),
        dispute="提交甲方所在地人民法院，或提交北京仲裁委员会。",
    )
    add(
        "G36",
        "review",
        ["R-TERM-CONFLICT", "R-AMOUNT-CONFLICT"],
        terms=("12", "24"),
        amounts=("12000", "15000"),
    )

    add(
        "G37",
        "pass",
        ["R-ELIGIBLE"],
        amounts=("1000",),
        terms=("3",),
        dispute="提交北京仲裁委员会。",
    )
    add("G38", "need_docs", ["R-MISSING-AMOUNT"], amount_lines=["合同金额：元"])
    add(
        "G39",
        "review",
        ["R-AMOUNT-REVIEW", "R-LIABILITY-UNCAPPED"],
        amounts=("50000",),
        liability="构成无限责任。",
    )
    add("G40", "pass", ["R-ELIGIBLE"], signed="sign", amounts=("11000",))
    return rows
