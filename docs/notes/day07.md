# 第 7 天笔记 · 切分、混合检索和术语归一

## 切分

- `chunk_by_heading`：以 `## AK-2024-` 为界，**一节一块**（含 7.1 限额两行在同一块）。
- Day 6 的 `chunk_fixed_width` 仍保留，用于切分归因实验，不用于混合 FAQ。

## 混合检索（一次调用）

- 术语表（Workflow）：`等了多久才能报` → 检索词含 `等待期`（字典替换，非模型）。
- BM25（字 token）+ 字面 bigram 分 → `rrf.reciprocal_rank_fusion`，禁止 raw 相加。
- top-8 后可接 **Rerank 桩**（默认原序）。
- `answer_clause_hybrid`：`retrieval_count=1`，低分不再查第二轮。

## 两条路径对照

| 问句 | Day 5 naive | Day 7 hybrid |
| --- | --- | --- |
| 等了多久才能报 | 失败 | 命中 AK-2024-3.1 |
| 周启明…其他保单 | 失败 | 仍失败，`deferred=day16` |

## Recall@K（口试备忘）

- 分子：相关片段出现在 top-K 中的次数；分母：相关问句数。
- 多跳跨保单：**不上 Agentic RAG**，第 16 天用边 `answer_hops`。

## 口试

1. 0901 资格可穷举 → 规则 Workflow，零模型；0777 材料分支写死 → 流水线。
2. 先天性疾病答错：第一眼看 **召回片段正文**（Day 6 attribute）。
3. 术语归一是写死表；Agentic 改写把决策交给模型。
4. 值得建图：实体关系多跳；今天 `周启明…其他保单` 属于此类。
