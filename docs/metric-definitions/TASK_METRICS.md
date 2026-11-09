# 任务评估指标候选定义

> 本文由 Canonical 自动生成。当前三个定义均为候选口径，不构成业务批准、正式裁决或发布声明。

| 指标 | 候选版本 | 适用训练 | 状态 |
|---|---|---|---|
| 击落比（任务评估）（KILL_RATIO） | 1.0.0 | BVR、WVR | CANDIDATE_TEST_ONLY |
| 交换比（任务评估）（EXCHANGE_RATIO） | 1.0.0 | BVR、WVR | CANDIDATE_TEST_ONLY |
| 任务完成率（MISSION_COMPLETION_RATE） | 1.0.0 | BVR、WVR、STRIKE、BASIC_FLIGHT、MIXED | CANDIDATE_TEST_ONLY |

## 口径冻结约束

- **击落比**：分子是对手方最终确认损失的唯一 loss_id；分母是符合准入条件的唯一 BVR/WVR 交战事件。发射次数不是分母。
- **交换比**：分子是对手方最终确认损失数，分母是评价方最终确认损失数。评价方零损失时结果为 N_A，不得输出 infinity。
- **任务完成率**：只统计任务开始时冻结的 required objective plan；分子是已最终确认完成的 required objective，分母是有效 required objective。optional objective 不进入分母。
- **去重**：同一损失即使关联多个 Weapon Event 或证据引用，也只能按一个 loss_id 计一次。
- **J 状态**：pending/unknown 不得按失败或 0 处理；冲突必须显式返回 INVALID。
- **跨批次聚合**：先合计分子和分母，再计算比值；禁止对各批次 ratio 做简单算术平均。
- **范围**：每个结果绑定精确 batch/session/release/context/evaluated_side/phase/time window；禁止 latest 回退和跨批次借数。
- **独立性**：这三项属于 Assessment Metric authority，不修改、不冒充 P1 116 项指标。
