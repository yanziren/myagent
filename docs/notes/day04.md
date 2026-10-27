# 第 4 天笔记 · 缺材料走固定流水线

## 材料清单

| 键 | 界面中文名 |
| --- | --- |
| `application` | 申请书 |
| `invoice` | 发票 |
| `diagnosis_certificate` | 诊断证明 |

判定看 `Claim.documents` 里键是否存在且为真，**不看** `diagnosis_text` 是否为空。

## 控制流

`run_intake`：缺任一项 → `补充材料` + `AK-2024-2.1` + `missing_docs`，**不调** `evaluate_eligibility`、**不调** `model`。材料齐 → 原样返回第 3 天资格规则结果。

HTTP：`POST /claims/{id}/intake`。0777 写 `claims.status = need_docs`；0901 材料齐则进规则，status 为 `eligibility_checked`。

## 口试

1. 流水线顺序写在 `workflow/intake.py`；Agent 的下一步在运行时由模型决定——缺材料这种分支不应交给 Agent 规划。
2. 不猜诊断：缺材料时推断病名会把确定性停止点变成概率事件，错赔风险从材料口漏出。
3. OCR 若以后接入，应在「结构化进 `documents`」之后、本流水线停止点之前；停止点之后才是资格规则。
