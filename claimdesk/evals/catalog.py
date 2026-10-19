import json
from pathlib import Path

_GOLDEN_PATH = Path(__file__).with_name("golden_v0.jsonl")


def load_golden(path: Path = _GOLDEN_PATH) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


GOLDEN_V0 = load_golden()
