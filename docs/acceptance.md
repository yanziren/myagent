# 验收

第 13 天到第 29 天的测试已经写完，并放进下面这条命令。

```bash
pytest tests/test_day01_scope.py tests/test_day03_rules.py tests/test_day08_agent.py tests/test_day13_grounding.py tests/test_day17_multi.py tests/test_day29_gate.py tests/test_day21_metrics.py tests/test_day22_billing.py tests/test_day23_resume.py tests/test_day24_latency.py tests/test_day25_routing.py tests/test_day26_sandbox.py tests/test_day27_release.py tests/test_day28_observe.py -v
```

镜像：`docker build -f deploy/Dockerfile .`。队列是 SQLite，没有 Kubernetes，没有独立消息中间件。
