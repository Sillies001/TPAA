# ED-2.0 分册 J：Context Attribution、Capability Intelligence、Digital Twin 与 Model Profile

**定义权声明：** 本分册定义 P2/P3 能力智能的处理链、数学/统计边界与发布治理；字段级 schema 由 `CORE_LOGICAL_MODEL.json` 控制，P 能力合同由 `EXTENSION_CONTRACT_REGISTRY.json` 控制。本分册不把“设计合同已冻结”表述成算法已实现、已验证或已证明因果/固有能力。

## 1. 分册职责

承接 R39 中 Aircraft Capability Intelligence、CAP-L2/CAP-L3、Attribution Engine、Capability Estimate、Aircraft Digital Twin、Aircraft Model Capability Profile、lifecycle/change-point 与能力可视化等此前 R1 承接过浅的知识。

## 2. 完整链路

```text
P1 Published Observation
→ Eligibility / Independence / Cohort
→ Factor Feature Set
→ Attribution Run
→ Context-adjusted Estimate (P2)
→ Capability Model / Surface
→ Aircraft Twin Revision
→ Reference-condition Longitudinal Estimate (P3)
→ Aircraft History / Model Profile
```

任何下游步骤不得覆盖 P1 Observation；所有产品都有独立 ID、version、Evidence 与 Release。

## 3. Capability Observation 输入原则

P2 只消费已发布 P1 Observation，不从 raw/canonical 重新算一份“更方便”的 P1 value。Observation 必须带 stable subject、configuration、Episode/Stage、Context/World/Evidence、coverage/quality、correlation/independence hints 和 release provenance。

样本排除必须保留 reason，不静默删除。

## 4. Factor Feature Set

Factor View 可包含：Human、Platform/Configuration、Environment/Scenario、Mission/Role、Lifecycle、Data Quality 等受控 features。每个 feature 有 spec/version、as-of/validity、missing mask、source observation/evidence。

标签完整不代表因素可识别；同一物理记录的多种表达不重复计权。

## 5. Attribution Run

### 5.1 输入

Observation IDs、target subject/capability、reference condition、factor feature sets、cohort、minimum sample/independence policy、attribution specification/model plugin、training/validation cutoff。

### 5.2 输出

至少表达：

- context-adjusted value 或 no-estimate status；
- factor effects / candidate contributions；
- unexplained component/residual；
- uncertainty；
- identifiability；
- diagnostics/validation；
- evidence/version/model artifact。

### 5.3 强制边界

- `NOT_IDENTIFIABLE` 是正常结果；
- association 不自动等于 causation；
- contribution 不自动等于 responsibility；
- non-share semantics 不显示成 100% stacked percentage；
- future information/same-Episode leakage 禁止；
- train/validate/publish snapshot 可追溯；
- aircraft/pilot/scenario/configuration grouping 正确；
- correlated evidence 不能因来源多就视作独立。

## 6. P2 Context-adjusted Estimate

P2 输出面向明确 reference condition。展示时必须同时给出：Observed P1 value、Adjusted estimate/status、Reference Condition、Uncertainty、Identifiability、Factor Evidence、Attribution Run/Spec Version。

若 reference condition 超出支持域、features 共线或样本不足，输出 NOT_IDENTIFIABLE/INSUFFICIENT_DATA，不进行隐式 extrapolation。

## 7. P3 Capability Model

Capability Model 使用冻结 training dataset snapshot、model specification/plugin 和 validation evidence。Model artifact/hash、validity domain、validation metrics、status、publish/supersede 都受治理。

模型可以按 subject-specific 或 cohort 方式训练，但不能用“模型存在”替代独立验证。

## 8. Capability Surface

Capability Surface 表示在明确 axes/condition domain 上的能力估计/不确定性数据产品。axes、surface semantics、validity domain、dataset hash 全部版本化；超出 validity domain 必须 fail-closed 或显式 OOD，不隐式外推。

## 9. Aircraft Digital Twin

Twin 是单架飞机的**发布型能力 read model**，包含：

```text
Identity
+ Configuration Timeline
+ Flight/Usage Context
+ Maintenance/Fault/Calibration/Lifecycle Events
+ Published Capability Model/Estimate Refs
+ Trend / Change Point
+ Confidence/Uncertainty/Evidence
+ As-of Data Time / Revision / Publication Status
```

Twin 不是实时 aircraft_state 镜像，不等于一次 Episode 分数，不可作为同一 Episode 的 Ground Truth/Machine World 回流计算。

## 10. Reference-condition Longitudinal Estimate

P3 默认输出名称为“参考条件下的长期性能估计”。发布至少需要受控 minimum evidence、coverage/quality、identifiability、configuration/context comparability、validation status 和无 unresolved duplication/leakage issue。

长期积累不能自动消除系统偏差，也不能因为代码名含 `INTRINSIC` 就证明固有性。

## 11. Aircraft Model Capability Profile

型号画像按 aircraft type/block/configuration/cohort 聚合 aircraft-level estimates，不直接把大量 Episode 当独立样本。

至少同时报告：aircraft_count、episode/evidence count、mean/median、dispersion、P10/P90、trend、block/configuration difference、outlier aircraft rate、validation/version。

必须保留单机差异和样本代表性说明。

## 12. Lifecycle / Change Point

维护、换件、软件、硬件/构型、传感器校准、数据/算法口径变化形成 lifecycle marker。Marker 可以用于趋势分段/候选解释，但 pre/post difference 只是关联证据，不自动证明维护或软件变化导致结果改变。

## 13. Knowledge Time / As-of

能力历史至少区分：

- 事件/有效时间；
- 记录/修订时间；
- information available / data cutoff；
- publication/as-of time。

“按当时信息重现”和“用后来信息回溯修订”是两类产品。后补维护/构型/标签不冒充当时已知。

## 14. Evidence Independence

分别报告：raw record count、metric/observation count、independent episode count、independent aircraft count、effective evidence volume。去重成功不等于统计独立；共同测量源/模型产生的多个产品不能伪装为多份独立验证。

## 15. P2/P3 Longitudinal

飞机长期族可覆盖 current estimate、trend slope、stability、change point、pre/post maintenance/software difference、freshness、independent evidence count。

P1 Observed Trend、P2 Adjusted Trend、P3 Reference-condition Estimate 必须视觉/数据对象分离，不能在一条曲线上无标记混合。

## 16. Human-Machine Capability Boundary

HMI 指标或 P4 actor assessment 不直接汇总进 aircraft intrinsic/reference capability。只有在 P2/P3 specification 明确 subject、因素分离与验证边界时，才可作为 factor/evidence 使用。

## 17. Model Validation

验证至少包括：

- data cutoff/leakage；
- duplicate/correlation/independence；
- train/validation split；
- reference-condition support；
- identifiability/OOD；
- uncertainty calibration（如适用）；
- lifecycle/configuration as-of correctness；
- reproducibility/model artifact hash；
- independent review and intended-use limits。

## 18. Release / Withdrawal / Supersession

Model、Estimate、Twin Revision、Model Profile 都通过 immutable release/publish lifecycle。Withdrawn 不作为 current view，但历史可查；Supersession 不覆盖旧字节和 provenance。

## 19. Application/API Requirements

未来 API 至少暴露：Observation Eligibility、Factor/Attribution Result、Adjusted Estimate、Capability Model/Surface Metadata、Aircraft Twin Revision、Aircraft/Model Capability History/Profile、Lifecycle Markers、Validation/Release Metadata。

API 不允许前端根据 current model 对历史 observation 重新归因；历史查询必须返回当时的 model/spec/release refs。

## 20. GUI Requirements

至少预留：

- Capability Separation View：Observed vs Adjusted vs Estimate；
- Aircraft Capability Twin；
- Capability Evolution / Lifecycle Tree；
- Model Profile / distribution；
- block/configuration compare；
- Attribution Candidate / Identifiability；
- validity-domain/OOD；
- Evidence drill-down。

非占比因素效应不得使用误导性的 100% 堆叠图。

## 21. P Capability Admission Gate

P2/P3 功能只有在 Core contract、数据依赖、Golden/validation fixture、算法实现、模型验证与 UI semantic separation 同时闭合后才能从 `DESIGN_CONTRACT_FROZEN` 升级。仅存在 DB table、API stub 或模型 notebook 不视为 P capability admission。

## 22. 分册验收

- P1 Observation byte/value 不被 P2/P3 覆盖；
- NOT_IDENTIFIABLE 可端到端传输/UI 显示；
- factor effect 不自动因果化/责任化；
- as-of/knowledge-time 无 future leakage；
- Twin 不回流为同 Episode truth；
- aircraft_count 与 episode_count 分开；
- lifecycle marker 不自动因果；
- model artifact/hash/validation/release 可追踪；
- observed/adjusted/reference-condition products 在 API/UI 中可区分。

## 26. R3 Capability 方法保真约束

P2/P3 必须保持 03A 第二编的产品演进逻辑：Observed Performance 是证据；Attribution/Normalization 只能在可辨识条件下产生条件化估计；Reference-condition Estimate/Twin/Model Profile 是版本化模型产品，不是 Ground Truth。五个能力域、L1/L2/L3 层级、evidence independence、knowledge time、configuration/cohort applicability、change point 和 release/withdrawal 都必须在后续实现中可追溯。

本分册冻结方法与工程边界，不得把 `DESIGN_CONTRACT_FROZEN` 描述成已通过真实数据验证的能力结论。
