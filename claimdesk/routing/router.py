from __future__ import annotations

_PRICES = {"none": 0.0, "small": 0.00002, "large": 0.0001}


def route(
    step: str,
    confidence: float | None = None,
    complained: bool = False,
    *,
    _via_gateway: bool = False,
) -> str:
    if not _via_gateway:
        from claimdesk.gateway.model_gateway import complete

        return complete(step, confidence=confidence, complained=complained)["tier"]
    if step in {"eligibility", "intake"}:
        return "none"
    if step in {"plan", "dispute"}:
        return "large"
    if step in {"summarize", "extract"}:
        if complained or confidence is None or confidence < 0.8:
            return "large"
        return "small"
    return "large"


def charge(path: str, tokens: int, price: float, ledger: dict[str, float]) -> None:
    ledger[path] = ledger.get(path, 0.0) + tokens * price


def price_for(tier: str) -> float:
    return _PRICES[tier]
