# Core Baseline CB-1.4.0

**适用：** TPAA V8.0 / ED-2.0  
**状态：** FROZEN FOR REBASELINE R3.3 — METRIC DESIGN INTENT & APPLICABILITY  
**数据库目标：** schema 1.6.0  
**日期：** 2026-09-19

## 1. 基线定位

Core Baseline 是总体方案与全部工程设计分册共同的唯一事实源。CB-1.4.0 在不改变 P1 116 项指标算法语义与 661 项输入绑定的前提下，补齐 R39 中 P2～P6、四类训练、人员/团队/任务与能力智能的扩展语义合同。任何文档冲突时，不以“哪份 Word/Markdown 更新”判断，而以 `canonical/SCHEMA_AUTHORITY_REGISTRY.json` 指向的权威 artifact 为准。

## 2. 定义权分配

| 领域 | 唯一权威 artifact |
|---|---|
| logical persistence objects | CORE_LOGICAL_MODEL.json |
| cross-layer DTO field contracts | CROSS_LAYER_DTO_CONTRACTS.json |
| Episode Stage taxonomy/method | STAGE_REGISTRY.json |
| P capability maturity semantics (P1～P6) | CAPABILITY_PHASE_REGISTRY.json |
| M development milestone semantics (M0～M9) | DEVELOPMENT_MILESTONE_REGISTRY.json |
| WS engineering workstream semantics | ENGINEERING_WORKSTREAM_REGISTRY.json |
| P/M/WS/Stage terminology separation | TERMINOLOGY_REGISTRY.json |
| P1 metric algorithms/semantic identities/structured schemas | P1_METRIC_CATALOG.json |
| P1 metric input binding authority | METRIC_INPUT_AUTHORITY_MATRIX.json |
| cross-cutting invariants | CORE_RULES.json |
| training/evaluation taxonomy | TRAINING_EVALUATION_TAXONOMY.json |
| world-capability / conclusion eligibility | WORLD_CAPABILITY_REGISTRY.json |
| P2～P6 extension semantic contracts | EXTENSION_CONTRACT_REGISTRY.json |
| extension metric-family reservations | EXTENSION_METRIC_FAMILY_REGISTRY.json |
| Windows/Linux runtime compatibility | PLATFORM_COMPATIBILITY_REGISTRY.json |

## 3. 强制不变量

| ID | 规则 | 约束 |
|---|---|---|
| CR-001 | Single Definition Authority | Every field-level fact has exactly one machine-readable authority artifact. Human documents may not create a second current-looking schema. |
| CR-002 | Identifier Stability | Published subject, context, metric definition, release, episode and stage identities are immutable; correction is by supersession/versioning. |
| CR-003 | Session Time | Computation uses authoritative Session Time; source clocks require explicit TimeTransform; JS-visible int64 time transports as decimal string. |
| CR-004 | Half-open Interval | All windows use [start,end); gaps, validity, source/clock/configuration boundaries split windows. |
| CR-005 | Missing Is Not Zero | Missing prerequisite data yields N_A or INSUFFICIENT_DATA with reason code; never fabricate zero. |
| CR-006 | Context Immutability | Historical computation/read uses exact immutable context_id and exact bound artifacts; no current/latest fallback. |
| CR-007 | Release Immutability | Published result is release-bound; historical replay resolves immutable definition/catalog/context/world/evidence provenance. |
| CR-008 | Typed Metric Value | value_kind determines one legal value slot; STRUCTURED is object and binds exactly one executable structured schema. |
| CR-009 | Stable Subjects | P1 primary subjects are AIRCRAFT and MISSION_SYSTEM_INSTANCE; TARGET_PAIR is reference/evaluation quality only and never a longitudinal subject. |
| CR-010 | Observation Lanes | AIRCRAFT_CAP_L1_OBSERVATION, SYSTEM_PERFORMANCE_OBSERVATION and QUALITY_EVIDENCE_ONLY are mutually governed publication lanes. |
| CR-011 | Longitudinal Compatibility | Only trend-eligible NUMERIC metrics enter numeric longitudinal_sample; comparison keys segment semantic/configuration/profile changes. |
| CR-012 | No Future Leakage | As-of joins are causal; state/config uses backward validity, command-response uses forward causal windows, and nearest is only explicit-policy. |
| CR-013 | Evidence First | Every metric/observation/assessment must retain evidence and provenance anchors sufficient for deterministic drill-down. |
| CR-014 | Safety Boundary | System does not derive weapon performance envelopes, best launch/release geometry, probability-of-kill models, tactical optimization or combat recommendations. |
| CR-015 | Change Closure | Authority artifact + dependent contracts + migrations + fixtures + traceability + validators change atomically; otherwise baseline build fails. |
| CR-016 | Semantic Product Separation | Fact/World/Metric/Observation/Assessment/Estimate/Forecast are distinct product classes; downstream interpretation never rewrites upstream fact. |
| CR-017 | Scope Separation | Individual、Team、Package/Mission、Joint-LVC scopes remain explicit; team result is not copied to individuals and member scores are not averaged to manufacture team capability. |
| CR-018 | World Capability Gate | Conclusions are gated by C/W/P/A/J/M availability; W never substitutes P and missing J never becomes inferred official outcome. |
| CR-019 | Instructor Revision Integrity | Instructor override is revisioned and preserves the original automatic product, reviewer, reason and rubric/Profile version. |
| CR-020 | Attribution Identifiability | Attribution may legitimately return NOT_IDENTIFIABLE; factor effects are model-conditioned and not default causal/blame statements. |
| CR-021 | Cohort Comparability | Longitudinal comparison requires explicit material cohort/comparison keys; incompatible observations are segmented. |
| CR-022 | Knowledge-Time Integrity | As-known replay and retrospective revision are distinct; later labels/configuration do not masquerade as contemporaneous knowledge. |
| CR-023 | Evidence Independence | Record count、Observation count、independent subject count、effective evidence volume are distinct; dedup/source multiplicity does not prove independence. |
| CR-024 | Dormant Future Contracts | P2～P6 design contracts may be frozen before implementation, but unimplemented/unvalidated capability must remain feature-gated. |
| CR-025 | External Interoperability Boundary | External simulation/interoperability protocols enter via governed adapters; core logic remains protocol-independent. |
| CR-026 | Training Plugin Composition | New training types compose the C+TPAA-M spine; no source-specific business-score bypass is allowed. |
| CR-027 | Platform-Neutral Business Core | Windows/Linux 平台差异不得改变 Domain/Application/World/Stage/Metric/Assessment/Release 业务语义。 |
| CR-028 | Cross-Platform Logical Equivalence | 同一冻结输入在 Windows/Linux 上产生等价逻辑产品。 |
| CR-029 | Controlled Progress/Layer Vocabulary | 进度/层级语言只允许 P、M、WS 与 Episode Stage 四类受控命名。 |
| CR-030 | P/M/WS/Stage Orthogonality | P=能力成熟度，M=项目里程碑，WS=工程工作流，Stage=训练过程；四者不得互相替代。 |


## 4. P / M / WS / Stage 统一语言

### 4.1 P — Capability Phase / 能力成熟度

P1～P6 只描述系统能够发布哪一层级的评价/能力产品，不描述项目开发进度。

| P | 名称 | 基线状态 | 边界 |
|---|---|---|---|
| P1 | Observed Performance | CURRENT_BASELINE | Aircraft/Mission-System Observation + Evidence + numeric trend；不做条件归因或固有能力主张。 |
| P2 | Context Attribution & Normalization | DESIGN_CONTRACT_FROZEN | Factor View / reference condition / identifiability / adjusted estimate；不得覆盖 P1。 |
| P3 | Reference-condition Capability / Aircraft Twin | DESIGN_CONTRACT_FROZEN | Capability model/surface、Twin revision、model profile；固有性措辞需独立证据。 |
| P4 | Human-Machine / Individual Assessment | DESIGN_CONTRACT_FROZEN | Qualification + Diagnostic Competency + Evidence；教员修订和 SA 边界显式。 |
| P5 | Team / Package / Mission Assessment | DESIGN_CONTRACT_FROZEN | Team/package objectives、shared picture、handoff、communication、composition-aware longitudinal。 |
| P6 | Joint/LVC + Forecast / Counterfactual / Closed Loop | DESIGN_CONTRACT_FROZEN | 联合/LVC、Forecast/Counterfactual/Recommendation 与事实物理和视觉隔离。 |

机器权威：`CAPABILITY_PHASE_REGISTRY.json`。P 代码一旦用于产品语义，不因 M 里程碑推进而重命名。

### 4.2 M — Development Milestone / 项目里程碑

M0～M9 只描述项目交付与验收进度。一个 P 能力通常跨越多个 M 才能完成。

| M | 里程碑 | 主要 P 关系 |
|---|---|---|
| M0 | Engineering Bootstrap | 建立工程底座，不单独准入任何 P 能力 |
| M1 | P1 Minimum Vertical Slice | P1 最小端到端闭环 |
| M2 | P1 Basic Flight Complete | P1 Basic + foundation metric batch |
| M3 | P1 Four-Training-Type Complete | P1 Basic/WVR/BVR/Strike + 116 metrics |
| M4 | P1 Longitudinal & Debrief Closure | P1 trend/replay/debrief 闭环，不启用 P4 |
| M5 | P1 Product Qualification & Release | P1 Windows/Linux、性能、安全、发布资格 |
| M6 | P2 Attribution Activation | P2 准入 |
| M7 | P3 Capability/Twin Activation | P3 准入 |
| M8 | P4/P5 Training Assessment Activation | P4/P5 分别通过门禁后准入 |
| M9 | P6 Joint/LVC & Predictive Activation | P6 准入 |

机器权威：`DEVELOPMENT_MILESTONE_REGISTRY.json`。旧 1A～1G 不再是当前开发语言。

### 4.3 WS — Engineering Workstream / 工程工作流

WS 是横向工程组织，例如 `WS-DATA`、`WS-WORLD`、`WS-METRIC`、`WS-GUI`、`WS-TEST`、`WS-PLATFORM`。WS 可跨多个 M 和 P，不具有顺序含义。机器权威：`ENGINEERING_WORKSTREAM_REGISTRY.json`。

### 4.4 Stage — 训练过程内部 Stage

Stage 仅表示 Training Episode 内的正式、版本化子区间/状态，例如 WVR 的 MERGE、MANEUVER 或 BVR 的 TRACK。Stage 不用于项目进度，也不用于 P 能力成熟度。机器权威：`STAGE_REGISTRY.json`。

### 4.5 Legacy 进度标签迁移

旧 1A～1G、1C/1D/1E 只保留在迁移追踪中：1A/1B→M0；1C 的 32 项 foundation batch→M2/WS-METRIC；1D 的 84 项 remainder batch→M3/WS-METRIC；1E longitudinal→M4/WS-LONGITUDINAL；1F/1G→M5。当前文档、计划、Issue、验收和发布记录不得再使用旧标签作为现行进度编号。

## 5. Episode Stage 唯一方法

Stage 不是由各 Metric 自己切片，而是一个正式、版本化、可修订、可回放的 Episode 子对象。Stage 候选按以下优先级解析：

1. Context official definition / approved marker；
2. 已标准化 authority event；
3. Context-defined rule + World 派生；
4. Model inference（必须保留 confidence）；
5. Manual review/correction。

发布对象固定使用 `episode.episode_stage` 的字段定义；Stage 时间为 `[start,end)`，必须完全落在所属 Episode 内。四套当前参考 profile 为 BASIC_FLIGHT_V1、WVR_ENGAGEMENT_V1、BVR_KILL_CHAIN_V1、STRIKE_MISSION_V1。旧 WVR/BVR 状态机词汇只能作为 event/analysis vocabulary，不能再形成第二套 current stage code。

### 5.1 当前 Stage Profiles

| Profile | Episode | Ordered stages |
|---|---|---|
| BASIC_FLIGHT_V1 | BASIC_FLIGHT | SETUP_ENTRY → EXECUTION → STABILIZATION_RECOVERY → COMPLETION |
| WVR_ENGAGEMENT_V1 | WVR_ENGAGEMENT | MERGE → POSITION_ADVANTAGE → MANEUVER → WEAPON_ENVELOPE → LAUNCH → KILL_ASSESSMENT |
| BVR_KILL_CHAIN_V1 | BVR_KILL_CHAIN | DETECTION → TRACK → IDENTIFICATION → DECISION → WEAPON_EMPLOYMENT → ASSESSMENT |
| STRIKE_MISSION_V1 | STRIKE_MISSION | MISSION_SETUP → ROUTE_TASK_EXECUTION → TARGET_INFORMATION_AVAILABLE → TARGET_ASSOCIATION → DESIGNATION_TRACK → TRAINING_ATTACK_EVENT → RANGE_SIM_ADJUDICATION → POST_EVENT_TASK_TRANSITION → RECOVERY |

## 6. 116 项指标冻结

指标算法权威仍是精确携带的 `P1_METRIC_CATALOG.json`。文档重构不改变算法 identity、公式、输入、structured schema 或 trend eligibility。

| 统计项 | 冻结值 |
|---|---|
| Metric count | 116 |
| Input bindings | 661 |
| M2 / P1_FOUNDATION_32 | 32 |
| M3 / P1_REMAINDER_84 | 84 |
| AIRCRAFT | 40 |
| MISSION_SYSTEM_INSTANCE | 72 |
| TARGET_PAIR | 4 |
| NUMERIC | 107 |
| STRUCTURED | 9 |
| M4 P1 longitudinal eligible | 104 |

### 6.1 Metric Family

| Family | 数量 | Subject 分布 |
|---|---|---|
| AIRCRAFT_FLIGHT | 20 | AIRCRAFT:20 |
| SENSOR_ACCURACY | 17 | MISSION_SYSTEM_INSTANCE:17 |
| ASSOCIATION_IDENTIFICATION | 12 | MISSION_SYSTEM_INSTANCE:12 |
| AIRCRAFT_ENERGY | 8 | AIRCRAFT:8 |
| DATALINK | 8 | MISSION_SYSTEM_INSTANCE:8 |
| SENSOR_FUSION | 8 | MISSION_SYSTEM_INSTANCE:8 |
| PASSIVE_SENSOR | 7 | MISSION_SYSTEM_INSTANCE:7 |
| TRACK_PERFORMANCE | 7 | MISSION_SYSTEM_INSTANCE:7 |
| RWR_ESM | 6 | MISSION_SYSTEM_INSTANCE:6 |
| TIME_ALIGNMENT | 5 | MISSION_SYSTEM_INSTANCE:2, TARGET_PAIR:2, AIRCRAFT:1 |
| AIRCRAFT_CONTROL_RESPONSE | 4 | AIRCRAFT:4 |
| AIRCRAFT_HANDLING | 4 | AIRCRAFT:4 |
| SENSOR_DETECTION | 4 | MISSION_SYSTEM_INSTANCE:4 |
| AIRCRAFT_PERSISTENCE | 3 | AIRCRAFT:3 |
| REFERENCE_TRUTH | 3 | TARGET_PAIR:2, MISSION_SYSTEM_INSTANCE:1 |

## 7. Core Logical Model 规则

`canonical/CORE_LOGICAL_MODEL.json` 是字段名、类型、nullability 的唯一 current persistence authority。任何工程文档只能引用对象名和业务用途；若需要显示字段表，只能由该 JSON 生成并标注 GENERATED PROJECTION。

优先级最高的对象包括：`registry.training_session`、`context.evaluation_context`、`registry.context_artifact`、`context.context_artifact_binding`、`episode.training_episode`、`episode.episode_stage`、`master.mission_system_instance`、`metric.metric_definition`、`metric.metric_instance`、Aircraft/System Observation、Longitudinal Scope/Sample/Trend、`registry.analysis_release`。

## 8. Context 与 Release

- Context 可 revision，但历史读取按 exact `context_id`。
- Session 不持有业务意义上的“当前 Context”指针。
- Context 所使用的 Scenario/Profile/Rule/Reference 等配置必须绑定 immutable artifact + sealed object/hash。
- SESSION Release 冻结其实际 Context bindings；LONGITUDINAL Release 引用 immutable SESSION Releases，不回头重新 resolve Context。
- 任何 historical read 的 artifact 缺失或 schema 不支持必须 fail-closed。

## 9. DTO 与传输

Critical DTO 字段权威为 `canonical/CROSS_LAYER_DTO_CONTRACTS.json`。Session Time 对 JS-visible API 必须使用 decimal-string；STRUCTURED Metric 使用 object；API DTO 和 UI View Projection 不得互相充当定义权。


## 10. P2～P6 与训练评价扩展权威

CB-1.4.0 继承并继续冻结四个**语义级** machine authority，不与 `CORE_LOGICAL_MODEL.json` 争夺字段定义权：

- `TRAINING_EVALUATION_TAXONOMY.json`：四类训练、Individual/Team/Package/Joint-LVC scope、人员 competency domains、Qualification/Diagnostic/Evidence 三层输出、候选根因、教员 review 与 Training Plugin composition；
- `WORLD_CAPABILITY_REGISTRY.json`：BASIC/WVR/BVR/STRIKE 的 C/W/P/A/J/M capability 与降级规则；
- `EXTENSION_CONTRACT_REGISTRY.json`：P2 Attribution、P3 Capability/Twin、P4 Human-Machine、P5 Team/Mission、P6 Forecast/Counterfactual 的稳定输入/输出/边界与纵向可比规则。
- `EXTENSION_METRIC_FAMILY_REGISTRY.json`：保留 R39 中非 P1 指标/指标族知识的语义命名与用途边界，但明确标记为不可执行的 future family reservation，不与 116 项 Catalog 竞争。

这些 registry 的目的不是宣称 P2～P6 已实现，而是**冻结未来扩展的语义尺寸**：后续实现可以新增 schema migration、DTO 与算法，但不能重新定义“Observation 是什么、Attribution 是否能覆盖 observed value、Team 是否等于成员均值、Twin 是否是实时 W、Forecast 是否能当历史事实”等根边界。

Core Logical Model 中已经存在 P2～P6 的部分 reserved product tables；进入具体 P 能力实施前，若需要新增 participant/team/package/media/profile 等持久化对象，应通过新 schema migration + Core model version 完成，而不是在分册中先写第二套字段表。

## 11. R39 全量知识承接原则

R39 中有效知识按四类处理：

1. **algorithm-semantic carry-forward**：116 Metric 的公式/语义/输入和 661 binding tuple 保持不变；R3.2 迁移旧进度元数据；R3.3 在不改公式/输入的前提下补充 family applicability 与完整设计解释；
2. **machine-semantic refreeze**：Stage、P Capability、Training/Assessment taxonomy、World Capability、P2～P6 extension contracts、Core Rules；
3. **explanatory redesign**：总体方案与专业分册中的 Basic/WVR/BVR/Strike、Instructor、Longitudinal、Twin、Debrief、Course/Unit、Joint/LVC 等；
4. **historical-only**：重复 current-looking schema、legacy code、审查补丁正文，不再作为 current authority。

任何“原方案有、新方案没写”的内容，只有在确认仍符合当前安全/语义边界后才承接；承接后必须能在 `TRACEABILITY_MATRIX.json` 中找到总体方案、machine authority、工程分册与验证 Gate。

## 12. 变更控制

任何 Core 变更必须同时更新：authority artifact、依赖契约、迁移/兼容策略、Golden/contract fixture、traceability、validator、Baseline Lock。缺一即不得发布新基线。


## Knowledge Fidelity Authority（R3）

`03A_整体训练效果评估方案_TPAA_V8.0.md` 是训练评价方法论权威；`05G_可视化_GUI设计分册.md` 是可视化工作流权威；`canonical/KNOWLEDGE_FIDELITY_MATRIX.json` 是 R39 方法/可视化知识迁移的验证证据。三者均不得覆盖 Canonical schema/DTO/Metric/Stage 的字段级定义权。


## 13. 跨平台运行与逻辑一致性权威

`canonical/PLATFORM_COMPATIBILITY_REGISTRY.json` 是 Windows/Linux 运行支持、平台适配边界、CI 认证矩阵与跨平台逻辑等价规则的唯一机器权威。Windows 与 Linux 是强制支持的 OS family；未来可增加其他 OS/CPU profile，但不得因此改写 Canonical、Stage、Metric、Assessment、Release 或训练评价语义。

跨平台设计遵循两个 Core 不变量：

- **CR-027 Platform-Neutral Business Core**：Domain/Application/World/Stage/Event/Metric/Assessment/Longitudinal/Capability/Release 核心不得按操作系统分叉；OS 差异只存在于 FileSystem、Process、Lock、Packaging、Credential、Hardware/Codec 等显式 Platform Adapter。
- **CR-028 Cross-Platform Logical Equivalence**：同一冻结输入、同一 Core/Catalog/Profile/Model/Context/World policy 在 Windows 与 Linux 上必须形成等价逻辑产品。ID、Stage/Event、状态、N/A/Qualification 等离散语义精确一致；数值结果遵守同一 Golden tolerance/确定性 rounding 规则。native package bytes、临时路径、PID 等物理差异不得进入业务 logical hash。

强制认证至少覆盖 Windows Desktop、Linux Desktop、Windows Service、Linux Service 四类 profile。PySide6 GUI、Local Backend、Worker、CLI 和业务投影必须共享代码基线；允许 vendor driver/GPU/codec 等 OS-specific adapter，但其不支持状态必须显式、可审计且不得污染业务核心。

## 14. P1 指标设计意图与 Family Applicability 权威

P1 116 项指标的可执行公式仍由 `canonical/P1_METRIC_CATALOG.json` 唯一拥有。R3.3 新增 `05C1_116指标设计意图_适用边界_区别联系与计算方法说明.md` 作为**解释性设计权威**：它回答每项指标“评什么、为什么设计、适用什么系统/产品层、怎样与相邻指标区分、结果怎样解释”，但不拥有可执行字段/公式定义权。

CB-1.4.0 新增 **CR-031 Metric Family Applicability and Product-Layer Separation**。其中：

- `P1-SNS-*` = **RADAR sensor detection/measurement**，`system_type=RADAR`；
- `P1-PSV-*` = IRST/EO 被动传感器；
- `P1-ESM-*` = RWR/ESM emitter sensing；
- `P1-DL-*` = DATALINK transport/remote-track delivery；
- `P1-FUS-*` = FUSION product；
- `P1-TRK-*` / `P1-ID-*` 按受治理的 Track / Association-Identification product capability 适用，不把原始 sensor measurement、remote track 或 fused track 混为同一层。

上述适用性由 `P1_METRIC_CATALOG.json` 的 `family_applicability_contracts` 与 common rules 机器冻结。R3.3 不改变 116 项 metric code、semantic/algorithm identity、formula、input_fields，也不改变 661 个 `(metric_code,input_field)` 绑定。
