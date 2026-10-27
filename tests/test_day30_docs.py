from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_capability_lists_what_the_desk_can_and_cannot_do():
    text = (ROOT / "docs" / "capability.md").read_text(encoding="utf-8")
    assert "## 能做" in text
    assert "## 不能做" in text
    for phrase in ("资格", "补充材料", "条款释义", "开放协查", "证据包", "打款", "写核心", "无法判断"):
        assert phrase in text
    assert "SQLite" in text
    assert "Kubernetes" in text
    assert "docker build -f deploy/Dockerfile ." in text


def test_three_months_and_known_non_goals_are_written():
    nxt = (ROOT / "docs" / "next.md").read_text(encoding="utf-8")
    assert "第一个月" in nxt
    assert "第二个月" in nxt
    assert "第三个月" in nxt
    known = (ROOT / "docs" / "known-issues.md").read_text(encoding="utf-8")
    assert "不上全库图谱" in known
    assert "不自建 GPU 集群" in known
    assert "不是 microVM" in known


def test_dockerfile_starts_uvicorn_from_the_app_module():
    docker = (ROOT / "deploy" / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12" in docker
    assert "uvicorn" in docker
    assert "claimdesk.api.app:app" in docker
    acceptance = (ROOT / "docs" / "acceptance.md").read_text(encoding="utf-8")
    assert "tests/test_day13_grounding.py" in acceptance
    assert "tests/test_day29_gate.py" in acceptance
    assert "pytest" in acceptance
