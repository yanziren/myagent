def gate(report: dict) -> str:
    if report.get("smoke_redline_failures", 0) > 0 or report.get("full_redline_failures", 0) > 0:
        return "red"
    if report.get("cost_ratio", 0) >= 1.4 and not report.get("waiver"):
        return "red"
    return "green"
