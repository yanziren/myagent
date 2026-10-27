# 第 5 天笔记 · 传统检索只查一次

## 机制

- 知识源：[`claimdesk/domain/clauses.py`](../claimdesk/domain/clauses.py) 的 `CLAUSE_V3`。
- 入口：[`claimdesk/rag/naive.py`](../claimdesk/rag/naive.py) 的 `answer_clause(question)`。
- 打分：字符二元组重叠 `_bigram_score`；每个问句 **只检索一次**（区别类固定拆两个子问句 → `retrieval_count=2`）。
- **无** HTTP、**无** `cache`、**无** `jobs`、**无** LLM 生成。

## 故意保留的失败样本（今天不修）

### 1. 口语：「等了多久才能报」

- 原因：措辞与条款里的「等待期」字面重叠低，传统一次检索 **召回为空**（不是库里没有等待期）。
- 示例 log：`query=等了多久才能报`, `clause_ids=[]`, `top_score≈0`（低于 `MIN_SCORE`）。
- Day 7 用 **术语表**（写死的「等待期」）在混合路径修；Day 5 的 `answer_clause` 路径保持失败。

### 2. 跨保单：「周启明在同一家医院的其他保单」

- 原因：答案依赖 **保单/图多跳**（POL-ZHOU-2、CLM-2026-1831），`CLAUSE_V3` 里没有保单号。
- 示例 log：`clause_ids=[]`, `top_score` 低。
- Day 16 用内存小图 `answer_hops`；今天 **不加** 提示词硬编。

## 区别类问句

「等待期除外和既往症除外有什么不同」→ 固定子问句 `等待期除外` / `既往症除外`，各检索一次，答案须同时含 **AK-2024-3.1** 与 **AK-2024-5.1**。

## 口试

1. **检索时机**：传统 RAG 由开发者在 `answer_clause` 里写死「查几次、查什么」；Agentic 把「要不要查、查什么、再查不查」交给模型（Day 8 协查，不用于 FAQ）。
2. **为何留失败样本**：先暴露固定流水线的失败模式，避免分不清是切分/措辞问题还是模型决策问题。
3. FAQ **只查一次** vs 开放协查 **多轮**：前者便宜可回归；后者只给 1842 类开放问题。
