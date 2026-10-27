# 核赔台

核赔台是一个健康险协查建议系统，场景是安澜财险成都理赔中心，产品只做「安康住院2024」。它给核赔专员建议和条款号，不打款、不写核心系统、不代替核赔人签字。

这是一份 30 天的智能体工程实现。每天留下一个可以用 pytest 证明的机制：规则分流、检索、有界协查、审批、轨迹、费用、模型路由和故障门禁。模型通过函数参数注入，评估默认使用桩和录像，不依赖供应商在线。

## 能力

能做：

- 资格判断。走规则，模型调用次数为 0。
- 缺材料时停在补充材料，不根据诊断正文推断病名。
- 条款释义。混合检索，回答带版本日期和条款号。
- 开放协查建议。手写循环，先查历史，再查条款。
- 争议案证据包。只有争议案启动工人；证据冲突时结论不能是通过。

不能做：

- 打款。
- 写核心系统。
- 未经批准对外发送。短信必须经过审批才离开系统。
- 资料不足时硬答。此时必须返回无法判断。

队列、缓存、审计和用量都在 SQLite。没有 Kubernetes，也没有独立的消息中间件。

三件贯穿案的期望输出：

| 案件 | 标签 | 条款 |
| --- | --- | --- |
| CLM-2026-0901 | 通过 | AK-2024-4.2 |
| CLM-2026-0777 | 补充材料 | AK-2024-2.1 |
| CLM-2026-1842 | 复核 | AK-2024-3.1 |

## 环境

- Python 3.11 及以上。教程和镜像使用 3.12。
- 依赖见 `pyproject.toml`：FastAPI、Pydantic、httpx、rank-bm25、uvicorn、langgraph。

## 安装与测试

```bash
./scripts/test.sh
./scripts/test.sh tests/test_day01_scope.py
```

脚本会在需要时创建 `.venv`，以可编辑方式安装本项目和 pytest，然后运行测试。

也可以手动安装。`pyproject.toml` 没有开发依赖组，pytest 需要单独安装：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e . pytest
pytest tests/ -v
```

## 运行

核赔台 HTTP 服务：

```bash
source .venv/bin/activate
uvicorn claimdesk.api.main:app --reload --port 8000
```

数据库路径默认是 `data/claims.sqlite`，可用环境变量 `CLAIMDESK_DB` 覆盖。

镜像：

```bash
docker build -f deploy/Dockerfile .
```

镜像里的启动命令是 `uvicorn claimdesk.api.app:app --host 0.0.0.0 --port 8000`。

同仓库里的 `auditdesk` 是另一套合同审核服务，默认端口 8765：

```bash
python -m auditdesk
```

## 目录

```text
claimdesk/
  api/          HTTP：协查入队、任务查询
  rules/        资格规则
  workflow/     材料完整性
  rag/          检索、依据校验、条款版本
  agent/        有界协查循环
  tools/        工具契约与白名单
  guards/       审批门、材料与规则分隔
  graph/        十几条边的多跳
  multiagent/   争议案工人、任务所有权、合并图
  traces/       录像与恢复
  billing/      按步归因和预算闸
  routing/      按步骤选择模型档位
  gateway/      模型网关：档位、限流、用量
  store/        SQLite
deploy/Dockerfile
docs/days/      第 1 天到第 30 天
tests/          按天验收
```

LangGraph 只用于 `claimdesk/multiagent/merge_graph.py` 的争议合并。普通协查循环不依赖它。

## 文档

- [30 天教程](docs/核赔台-30天实战教程.md)：每天的任务、约束和验收。
- [范围](docs/scope.md)：红线和贯穿案。
- [能力边界](docs/capability.md)：现在能做和明确不做的事。
- `docs/days/`：单日说明。阅读顺序从 `01-场景收敛与红线.md` 开始。
