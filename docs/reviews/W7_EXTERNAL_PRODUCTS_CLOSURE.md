# W7 P11、P6、媒体与外部能力本地关闭记录

日期：2026-10-25
候选分支：`local-r8-review`
边界：本地整改；禁止推送；禁止生产部署

## 1. 关闭结论

W7 本地范围状态为：

`CLOSED_LOCAL_WITH_EXTERNAL_GATES / PASS / NOT_PUSHED / NOT_DEPLOYED / NOT_PRODUCTION_READY`

该结论包含两类不同结果：

1. P11、本地精确产品读取、P6 分层呈现和审批、媒体索引/时间线/书签/播放列表/比较、Model Registry 证据读取已经实现并通过本地验证；
2. 真实 Joint/LVC 在线连接、外部插件执行、媒体对象交付/导出、模型在线 monitoring/rollback 没有批准的 staging/生产端点，因此保持运行时硬门禁，动作不可用。

第二类能力不是“已实现占位”，也不构成真实外部系统验收。运行时只在同时存在精确 endpoint reference 和 64 位小写 SHA-256 验收证据时允许状态成为 `AVAILABLE`；本地组合固定为 `NOT_CONFIGURED`。

## 2. 实施结果

| W7 子项 | 状态 | 实现与证据 | 未越过的边界 |
|---|---|---|---|
| W7-A P11 Course/Unit/Joint-LVC & Planning | `CLOSED_PASS_LOCAL` | P11 改为四工作区产品页；Course/Unit 强制聚合和小样本抑制；Joint/LVC 只展示精确冻结映射快照 | 快照不宣称 live gateway |
| W7-B Forecast/Counterfactual/Recommendation | `CLOSED_PASS_LOCAL` | Actual、Forecast、Counterfactual、Recommendation 使用四种永久视觉语义；加载 exact workspace；Recommendation 使用现有 M9 不可变审批迁移 | GUI 不重算、不把 projection 升格为 fact |
| W7-C media/transcript/time/redaction/export | `CLOSED_PASS_LOCAL_GATED_EXPORT` | 精确 MEDIA_DEBRIEF、master session time、semantic layer、managed URI、transcript availability、artifact hash 可审阅 | 对象获取、redaction policy 和 export 在无端点时禁用 |
| W7-D bookmark/playlist/compare | `CLOSED_PASS_LOCAL` | 展示冻结 bookmark/playlist 引用；支持 absolute session time 与 stage-aligned 两种比较意图，比较绑定两个 exact snapshot | 不解析 mutable current/latest，不复制业务数据 |
| W7-E 真实 Joint/LVC Gateway | `FEATURE_GATED_NOT_CONFIGURED` | 现有 lossless mapping、fact/projection separation 和 non-operational-optimization 契约继续验证；新增机器可读运行时门禁 | 无批准 staging endpoint，未宣称真实互操作验收 |
| W7-F 外部插件安装/签名/隔离/回滚 | `FEATURE_GATED_NOT_CONFIGURED` | 保留 builtin frozen、baseline-authorized 组合；运行时明确要求 trust root 与 sandbox | 未提供动态 import/install/enable 路由，避免无信任根执行代码 |
| W7-G Model Registry/validation/monitoring/rollback | `CLOSED_PASS_LOCAL_GATED_ONLINE` | M9 exact model API 增加原始 validation/applicability/calibration 状态；P11 显示 artifact hash、plugin identity 和 release state | 在线 monitoring/rollback 需要端点和独立审批，按钮禁用 |

## 3. 关键失败关闭规则

- upper product 必须使用 UUID exact snapshot，拒绝 `current/latest`；
- upper product 必须 `frozen=true` 且 `mutable_alias_resolution=false`；
- Joint/LVC 必须同时满足 external boundary、LVC、lossless mapping、fact/projection separation 和禁止 operational optimization；
- 外部能力的 `AVAILABLE` 必须同时具有 endpoint reference 与 acceptance evidence SHA-256；
- 非 `AVAILABLE` 状态禁止携带伪 endpoint/evidence；
- P6 模型资格状态由 Application 原样投影，GUI 不从指标推断；
- 外部插件、模型回滚和媒体导出在本地候选中没有可调用动作路径。

## 4. 主要代码证据

- `src/tpaa_gui/w7_pages.py`
- `src/tpaa_gui/w7_projection.py`
- `src/tpaa_application/w7_external.py`
- `src/tpaa_application/m9_workspace.py`
- `src/tpaa_api/runtime.py`
- `src/tpaa_gui/product_shell.py`
- `tests/unit/gui/test_w7_p11_workflows.py`
- `docs/compliance/W7_COMPLIANCE_MATRIX.json`
- `docs/operator/W7_P11_EXTERNAL_CAPABILITIES.md`

## 5. 验证与声明边界

本轮验证已经完成：W7/相关契约定向测试 `39 PASS`，全量单元测试 `768 PASS`，全量 contract `818 PASS`，全仓 Ruff 通过，mypy `301 source files` 通过，`compileall` 通过。clean-worktree 开发打包门禁未放宽并已通过；与最终关闭提交对应的包 SHA-256 和 summary SHA-256 记录在工作空间总整改方案的 W7 关闭章节。Windows 上执行 Polars 相关测试仍需使用项目既有兼容设置 `POLARS_SKIP_CPU_CHECK=1`；pytest cache 的 `WinError 5` 警告不改变业务断言结果。

W7 关闭不解除以下门禁：真实外部 endpoint 接入验收、组织审批、生产 trust root、对象存储安全、在线模型监控、W8 性能/灾备/部署、W9 同候选综合资格、签名、protected-main 合入和生产发布。

