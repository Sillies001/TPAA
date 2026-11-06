# ED-2.0 分册 B：World Reconstruction、Stage Projection 与 Event/Relation

**定义权声明：** 本分册不创建第二套 Stage/schema；Stage 只引用 `canonical/STAGE_REGISTRY.json`，跨领域不变量只引用 Core Baseline。

## 1. 职责

构建 C+W/P/A/J/M 的可追溯产品，形成 Stage/Event/Relation/TPAA-M Chain，向 Metric Engine 提供 source-independent 语义产品。

## 2. WRE 输入

WorldBuildRequest 绑定 Session/Release candidate、exact Context refs、Canonical dataset refs、policy/profile versions、requested worlds 和 as-of boundaries。不得直接读取 UI state。

## 3. Authority Resolution

字段组（Position/Velocity/Attitude/Control/Propulsion 等）每一时刻只能有一个批准 authority source 或一个版本化 fusion product；输出保存 authority signature。

## 4. Series Boundary

Gap、clock reset、aircraft instance reset、authority switch、关键 configuration/measurement semantic change均切分 Series。任何 derivative/rolling/statistic 不跨 Series 边界。

## 5. Stage Projection

Stage projector 只消费 exact Context、World refs 和 approved authority events；优先级完全服从 `STAGE_REGISTRY.json`。Model inference 只能作为低优先级候选，并保存 confidence。

## 6. W/P/A/J/M

- W：批准 truth/reference authority；
- P：observer-specific available information；
- A：actor-specific observed action；
- J：批准 external adjudication；
- M：machine state/capability evidence；
- C：独立 Context，不混入上述事实世界。

## 7. Event / Relation

Event detector 不直接解释 source-specific records；它消费 World products。Relation 显式连接 W↔P、P↔A、A↔J、P↔P、A↔A、C↔World 的证据关系。

## 8. Canonical shared events

Opportunity、Detection Confirmation、Fusion Handover 等拥有唯一 upstream state/event authority；Metric plugin 只能消费冻结事件，不重复运行 owning state machine。

## 9. TPAA-M Chain

Chain 是 Episode/Stage 内可追踪的 process-evidence chain，API 使用受控 TPAAChainDTO。缺环节必须显示 break reason/coverage/confidence，不得为了“完整链”伪造节点。

## 10. 确定性与恢复

Job 采用 QUEUED→RUNNING→STAGING→VALIDATING→COMMITTING→SUCCEEDED；cancel/failure 不发布 current pointer。Retry 复用 request hash；跨平台比较 logical values/hash，不要求 Parquet 字节完全相同。

## 11. Golden

至少覆盖 clock rollback、future leakage、source switch、respawn、Context/Stage revision、W/P separation、J missing、shared-event single authority、crash at staging/commit。

## 12. 组件分解

WRE 建议由 Request Validator、Input Snapshot Builder、Time/Series Resolver、Context Resolver、Stage Projector、Authority Resolver、W/P/A/J/M Builders、Relation Linker、TPAA-M Chain Builder、Coverage/Confidence Evaluator、Publisher、Checkpoint/Recovery 组成。每个组件使用显式版本，形成 build manifest。

## 13. WorldBuildRequest / Result 语义

Request 必须冻结输入 Release/candidate、Session、subject scope、Context refs、requested world types、Stage/episode范围、policy/profile versions、input dataset/object hashes。Result 不只返回“成功文件”，还要返回 World manifests、series IDs、coverage/confidence、reason codes、lineage 和 logical hashes。

## 14. W Builder

W Builder 依据 approved truth/reference authority 生成事实/参考世界。若多个来源竞争同一 field group，先由 Authority Resolver 选择或使用版本化 fusion product；Builder 不做隐式 source preference。Reference truth 的不确定性必须与比较证据一起保留。

## 15. P Builder

P_i 只包含 observer i 在当时客观可获得的信息。后台 truth、事后数据、其他成员私有信息不得自动进入 P_i。多个 perception source 的融合必须由明确 policy/version 控制，并保留来源/age/quality。

## 16. A Builder

A_i 规范化 flight-control、mode/select/designate、task/ack、communication、training engagement 等动作。连续状态和离散事件分开建模；command→response 关系必须满足因果方向，response 不得早于 command。

## 17. J Builder

J 只接收批准的 external adjudication authority。系统内部 Qualification/Score/Competency 不属于 J。若 J 不可用，World/Metric 可以继续处理过程，但涉及 official outcome 的产品必须 N/A。

## 18. M Builder

M 表达 machine state/capability evidence，不把 P1 Observed Performance 直接提升为 intrinsic capability。P1 的 M 主要用于状态、可用性、构型、响应/限制等证据；后续 P3 通过受控 Twin/Capability projection 扩展。

## 19. Relation Linker

Relation 记录 source world refs、target world refs、relation type、时间范围、算法/policy identity、coverage/confidence 与 evidence。典型包括 truth-perception association/gap、perception-action response、action-adjudication link、team perception divergence、team action synchronization、Context compliance。

## 20. TPAA-M Chain Builder

Chain 以 Episode/Stage 为 scope，把 C/W/P/A/J/M 与关系节点组织为解释链。Chain 的 completeness 是证据质量，不是强制“补齐”缺失节点。Chain break reason 对 MetricDetail/UI 必须可见。

## 21. Coverage / Confidence

Coverage 应由有效时间/机会区间计算，不能用简单 record count 替代。Confidence 可以组合时间同步、reference quality、identity、association、coverage、source authority 等组件，但组合方法必须版本化并可解释。

## 22. Publisher

Publisher 先验证 staging manifests、logical hashes、foreign/stable IDs 和 Context/Stage refs，再 seal payload 和登记 Release 产品。只有验证通过的产品才能进入 current pointer；cancel/failed job 不得泄漏 staging row/object。

## 23. Replay 与 Projection 隔离

Replay 读取历史 fact/world product；Projection/Forecast/Counterfactual 必须使用独立 product type/namespace，不得覆盖 W，也不得在 UI 中以相同视觉编码伪装为事实轨迹。所有 projection 必须带 model/version/as-of provenance。

## 24. B 分册验收

W/P separation、authority switch、Series boundary、causal join、Stage version、shared event authority、J missing、chain break、checkpoint/crash recovery、cross-platform logical determinism 均须有 Golden fixture。

## 25. World Capability Registry 集成

B 分册不再通过“某数据源存在”推断业务能力，而直接消费 `WORLD_CAPABILITY_REGISTRY.json`。World builder/publisher 需要产生足够 evidence 证明 C/W/P/A/J/M 的 required/optional 状态、coverage/quality 和版本；Assessment/Metric 只按 declared capability 判断是否可计算。

必须保留以下边界：Truth 不代替 Perception；Action 不代替 Adjudication；Machine State 不代替 Capability Estimate；Assessment/Estimate/Forecast 不回写 World。

## 26. Strike World / Stage / Chain

`STRIKE_MISSION_V1` 是 Strike 当前 reference stage profile。对应 Chain 的典型节点：

```text
C assigned route/target/rule
→ W target/platform/environment fact
→ P_i target/track/cue/designation information
→ A_i association/designation/training action
→ J approved range/simulator adjudication
→ Assessment
```

M_i 贯穿系统/平台状态证据。无 J 时 chain 允许终止于 Action，但不得生成 official outcome link。

## 27. Event Graph

复杂任务使用正式 Event/Relation product 组织证据。至少支持以下语义类别：

- PRECEDES / FOLLOWS；
- RESPONDS_TO；
- AFFECTS；
- EVIDENCE_FOR；
- ASSOCIATED_WITH / HANDOFF；
- CANDIDATE_CAUSE（仅候选关系，不等于已证实因果）。

Event owner/state machine 必须唯一；Metric/Assessment 只能引用已有 event，不为便利重复检测同一语义。

## 28. 四类训练典型 Event Chain

### 28.1 Basic

Entry/Setup → Execution → Recovery/Stabilization → Completion，可叠加 Warning、Procedure/Compliance、Control/Response 等 event。

### 28.2 WVR

Contact/Merge → Geometry/Position evolution → Maneuver → Training opportunity/action → Approved adjudication → Reset/Recovery。旧状态词可以作为 event-state vocabulary，但不取代 Stage Registry。

### 28.3 BVR

Relevant Entity → Cue/Detection → Track → Correlation/Identification → Decision/Task → Action/Engagement → Team Coordination → Adjudication → Post-event。

### 28.4 Strike

Target Relevant → Target Information → Association → Designation → Training Attack Event → Official Scoring/Adjudication → Post-event Task → Recovery。

## 29. Compliance / Training Standard Rule

Training standard/rule 应通过 Context-bound immutable artifact/DSL 或等价版本化规则表达。规则可以定义 applicability、World requirement、event trigger、measurement window、reference/threshold source 和 output semantic，但不得把 source field name 直接写成业务真值。

示例语义：

```text
WHEN TrackDrop in applicable Stage
AND context relevance active
AND required worlds available
MEASURE until TrackReacquire
OUTPUT governed metric/event semantic
```

规则/阈值来自训练标准/Context；算法不自行创造规范。

## 30. Relation 与 Team/Package 扩展

P5 使用 participant-specific P_i/A_i/M_i 与 Entity/Relation 构建 Team/Package products。支持 role/task assignment、shared picture agreement/divergence、handoff、communication、separation/deconfliction、objective dependency 等关系。

Relation 的 subject/object、time window、source/method/evidence 必须明确；Team/Package 聚合不能抹掉 participant identity。

## 31. Root-cause Candidate Evidence Graph

B 分册只负责生成/连接可观察 evidence 与 candidate relation，不做最终责任判断。Candidate cause 可以引用 Information Availability、Data Quality、Machine Degradation、Procedure、Task/Communication 等类别；Instructor Review 在上层确认/修订。

## 32. External/LVC Reconstruction

Live/Virtual/Constructive 或 TENA/HLA/DIS 等参与者通过 Adapter/Gateway 进入统一 Time/Entity/Canonical/World。仿真状态和现实 authority 必须保留来源类型；virtual/constructive truth 不自动提升为现实验证证据。

## 33. B 分册扩展验收

- World Capability 由 registry 驱动；
- Strike profile/chain 可重放；
- Event semantic 只有一个 owner；
- rule/DSL 版本化并绑定 Context；
- Team/Package relation 不提前融合 participant worlds；
- Candidate cause 不升级为未经证实因果；
- LVC source 与现实 source/provenance 可区分。
