# W7 P11 与外部能力操作边界

## P11 使用顺序

1. 在 `Course / Unit & Joint-LVC` 中刷新冻结快照并选择 exact UUID；Joint/LVC 快照仅证明适配映射，不代表实时连接。
2. 在 `P6 Planning & Approval` 中先刷新 Recommendation 历史；Forecast 和 Counterfactual exact ID 由 Recommendation 的不可变来源引用带出。
3. 检查 Actual、Forecast、Counterfactual、Recommendation 四个视觉区后，审批人填写原因并创建新的不可变审批 revision。
4. 在 `Media / Transcript / Compare` 中选择 primary 和 comparison exact snapshot；比较模式只能为 `ABSOLUTE_SESSION_TIME` 或 `STAGE_ALIGNED`。
5. 在 `Model Registry & Gates` 中读取 exact model 资格证据，并刷新运行时外部能力门禁。

## 外部能力激活合同

运行时端点为：

`GET /runtime/external-capabilities`

四项能力必须按固定顺序完整返回：

1. `JOINT_LVC_LIVE_GATEWAY`
2. `EXTERNAL_PLUGIN_EXECUTION`
3. `MEDIA_OBJECT_DELIVERY_EXPORT`
4. `MODEL_ONLINE_MONITORING_ROLLBACK`

允许状态为 `NOT_CONFIGURED`、`DEPENDENCY_MISSING`、`NOT_ACCEPTED`、`UNAVAILABLE`、`AVAILABLE`。只有 `AVAILABLE` 可以令 `action_enabled=true`，且必须同时配置：

- 非空、环境管理的 `endpoint_ref`；
- 对应批准验收记录的 64 位小写 `acceptance_evidence_sha256`；
- 非空 `reason_code`。

任何非 `AVAILABLE` 状态都禁止携带 endpoint/evidence，以防把未验收连接展示成可用能力。

## 本地候选状态

本地 Desktop/Service 组合使用 `W7ExternalCapabilityRegistry.local_closed()`，四项均为 `NOT_CONFIGURED`。因此以下动作按设计不可用：

- live Joint/LVC 连接；
- 外部插件安装/执行/回滚；
- 媒体对象导出；
- 模型在线 monitoring/rollback。

要在后续 staging 激活，必须由受控配置加载器构造完整四项 registry，并将 endpoint 验收记录纳入 W9 同候选证据。不得修改 GUI 文案或直接启用按钮绕过 Application runtime gate。

