def gate(
    spent: float,
    soft: float = 50.0,
    hard: float = 80.0,
    no_progress: bool = False,
) -> str:
    if spent >= hard or no_progress:
        return "suspend"
    if soft <= spent < hard:
        return "converge"
    return "run"
