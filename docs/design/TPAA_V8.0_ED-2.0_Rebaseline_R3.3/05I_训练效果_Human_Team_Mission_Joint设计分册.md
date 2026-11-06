# ED-2.0 分册 I：训练效果、Human-Machine、Team、Mission 与 Joint/LVC

**定义权声明：** 本分册定义 P4/P5 训练评价流程、对象关系与工程边界；训练类型、scope、competency、World Capability、Stage 和字段级 schema 分别引用 `TRAINING_EVALUATION_TAXONOMY.json`、`WORLD_CAPABILITY_REGISTRY.json`、`STAGE_REGISTRY.json` 与 `CORE_LOGICAL_MODEL.json`，不复制第二套 current schema。

## 1. 分册职责

本分册承接原 R39《整体训练效果评估方案》和系统架构中此前在 Rebaseline R1 仅保留框架的训练评价知识，覆盖：

- Basic / WVR / BVR / Strike 四类训练的 P4/P5 评价；
- Individual / Human-Machine / Team / Package / Mission / Joint-LVC；
- Qualification / Diagnostic Competency / Evidence；
- Assessment Profile、Critical Gate、缺失策略；
- Event responsibility、Root-cause Candidate、Instructor Review；
- 人员/团队长期评价、场景可比性、课程/单位反馈；
- 训练插件组合与联合/LVC 扩展。

本分册**不改变 P1 的 116 项算法及 Observed Performance 数值**。

## 2. P4/P5 输入边界

P4/P5 只消费已经版本化的：

```text
Evaluation Context C
+ Episode / Stage / Objective
+ W / P_i / A_i / J / M_i
+ Event / Relation / TPAA-M Chain
+ Published Metric / Observation
+ Data/World Capability / Evidence
+ Assessment Profile
+ Instructor Annotation / Review
```

禁止 Assessment 直接重读高频 source 或自行重构 Truth/Perception；禁止使用 current/latest Profile 解释历史 Release。

## 3. 四类训练统一 Assessment Spine

所有训练类型遵循：

```text
Context Applicability
→ World Capability Gate
→ Episode/Stage/Objectives
→ Event/Relation/Chain
→ Metric/Evidence Eligibility
→ Critical Gates
→ Competency Diagnostics
→ Qualification
→ Evidence Package
→ Instructor Review
→ Longitudinal Observation
```

训练类型只通过 Context/World policy/Stage profile/Metric set/Assessment Profile 变化，不改变上述骨架。

## 4. Basic Flight P4 设计

### 4.1 评价对象

- 个体飞行控制与程序执行；
- Human-Machine information/mode/action link；
- 安全与训练纪律；
- 飞行课目 objective；
- 与 P1 Aircraft/Mission-System Observed Performance 的证据关联。

### 4.2 主要 competency

Safety & Discipline、Aircraft Control、Flight/Task Execution、Information/System Management、Decision/Task Management。仅当 P/world capability 充分时才启用 SA Evidence。

### 4.3 平台与人员分离

同一操纵结果可同时包含 P1 aircraft response evidence 与 P4 actor assessment，但两者 subject、claim level、profile、release product 不同。平台响应异常、传感器降级或数据 gap 不自动扣 actor 分。

## 5. WVR P4/P5 设计

### 5.1 P4 Individual/HM

评价训练定义的 geometry/state control、energy management、information availability、cue-response、training action 和 rule compliance。

### 5.2 P5 Team

评价 shared picture、role/task coordination、communication、action synchronization、separation、team objective。Truth 只用于 W–P evidence，不可替代成员 P_i。

### 5.3 Process–Outcome

Training Engagement Action 与 J 官方结果分离。系统同时保留 process quality 与 official outcome，禁止用一个结果反推全部 competency。

## 6. BVR P4/P5 设计

### 6.1 Individual/HM

核心链：

```text
W relevant entity
→ P_i detection/track/ID information
→ A_i decision/task/mode/communication/engagement action
→ M_i system availability/degradation
→ J approved adjudication (if available)
```

评价 Track/Association/Identification、Cue-to-Response、Information/System Management、Decision/Task Management 和 Training Engagement Execution。

### 6.2 Team/Mission

团队层评价：

- Shared Picture Agreement / Divergence；
- 信息收敛和冲突；
- Task/Role assignment、acknowledgement、handoff；
- Communication completion；
- 多机动作时序与 deconfliction；
- Team/Package objective；
- Process–Outcome Divergence。

### 6.3 多 observer/actor 规则

P_i/A_i/M_i 保持 participant-specific，不允许在 World Reconstruction 前提前融合成一个“唯一座舱世界”。Team product 只能在 P5 层基于显式 relation/aggregation 生成。

## 7. Strike P4/P5 设计

### 7.1 P4

评价 route/task execution、target information、association、designation continuity、procedure/safety、training attack action 与 post-event task。

### 7.2 P5 多机 Strike

评价 target assignment consistency、task acknowledgement、duplicate/conflicting assignment、sequencing、separation/deconfliction、shared target picture、team completion 与 approved package outcome。

### 7.3 J 边界

没有 approved J 时，训练 attack event 只是一项 observed action。不得推导 official hit、mission success 或真实武器效能。

## 8. Assessment Profile

Profile 至少声明：

- training type / platform/scenario family；
- syllabus/training-standard refs；
- applicable Episode/Stage/Objectives；
- required/optional World Capability；
- Metric/Event/Relation eligibility；
- Critical Gates；
- competency mapping/weight/minimum evidence；
- missing strategy；
- grade/qualification mapping；
- instructor review/override policy；
- validity/version/publication policy。

Profile 参数变化不改 Metric 物理值；公式/eligibility/filter 改变应升级对应 Metric/algorithm semantic contract。

## 9. Qualification / Diagnostic / Evidence

### 9.1 Qualification

先执行 Data Sufficiency 与 Critical Gate。mandatory evidence 缺失时为 INSUFFICIENT_DATA/N_A；critical safety/rule gate 失败时按 Profile 限制 qualification。

### 9.2 Diagnostic Competency

只聚合 eligible evidence。Optional 缺失是否可重归一化必须由 Profile 明确；不得为了获得总分而隐式补零或无条件 renormalize。

### 9.3 Evidence

每项 Qualification/Competency 能回钻到 Event/Relation/Metric/World/Context/Series/Media/Release。Evidence 是正式输出层，而不是 UI 附件。

## 10. Situational Awareness Evidence 边界

P_i 只证明“信息客观可获得”。自动系统可评价：

- information availability / continuity；
- truth–perception association；
- classification/ID evidence；
- cue/response；
- team picture agreement/divergence；
- observable task/action behavior。

“理解是否正确、预测是否合理、为什么做出某决策”等高层判断必须使用经过验证的 observable proxy 或 instructor rubric；不得从 P_i 直接推出主观认知。

## 11. Event Responsibility 与 Controllability

事件责任语义至少覆盖 actor、owner、affected entity、team、controllability、contribution confidence。P5 Attribution/Assessment 根据这些关系解释“谁受到影响/谁可控制/谁提供证据”，但不把系统因素、数据质量、外部场景自动转化为个人责任。

典型 System/Data Issue：TDL 大范围中断、truth 缺失、sensor log gap、clock/sync、配置身份不确定、external range fault。

## 12. Root-cause Candidate

自动系统输出候选原因树和 evidence，而不是唯一原因：

- Flight Control；
- Information Availability；
- Track/Association；
- Procedure；
- Decision/Task Management；
- Communication；
- Team Coordination；
- Training System；
- Data Quality；
- External/Scenario；
- Instructor Determination。

候选原因可以由教员确认、修改或标记 false positive；修改产生 revision，不覆盖自动 evidence graph。

## 13. Instructor Review

### 13.1 自动与人工分离

自动 Assessment、Instructor Competency Grade、Event Tag、Correct Alternative Action、Root Cause Confirmation、Free Annotation 分开保存。

### 13.2 Override

Override 必须保留 base product/release、原结果、reviewer、时间、理由、rubric/Profile version、revision/supersedes。禁止更新原 Metric/World facts。

### 13.3 一致性

支持 Cohen Kappa、Fleiss Kappa、固定版本 ICC、grade distribution、severity/leniency/concordance trend。该类指标用于 rubric calibration，不自动做教员排名或责任评价。

## 14. Team / Package / Mission Assessment

### 14.1 Team

Team assessment 以 team identity/composition + participant P_i/A_i/M_i + relations + objectives 为输入。输出 shared picture、role/task、handoff、communication、synchronization、separation 和 team objective evidence。

### 14.2 Package

Package/Mission Group 允许多个 Team/C2/UAS/virtual/constructive entities。评价 cross-team information consistency、task handoff、cross-domain timing 与 package objective。

### 14.3 Scope 不混写

Team=85 不意味着成员都=85；Individual score 的平均也不自动形成 Team capability。UI/API/longitudinal 必须显式保留 scope 和 composition。

## 15. Joint / LVC 扩展

Joint/LVC 保持相同 Core spine，只扩展：EntityType、RelationType、Source Adapter、Training Plugin、Scenario/Objective、Assessment Profile。TENA/HLA/DIS 等外部协议经 Gateway/Adapter 进入 Canonical；核心 Domain 不依赖协议对象。

LIVE、SIM、LVC 环境必须随结论显示；仿真内部一致性不自动证明现实适用性。

## 16. 人员长期能力

每个 competency observation 保留 Episode、role、scenario/cohort、team composition、Profile/Metric versions、World Capability、confidence/quality、Evidence、Instructor Review。

长期产品可包含 EWMA、trend slope、stability/MAD/variance、P10/P50/P90、comparable cohort percentile、recent valid exposure、time since last valid exposure、decline/retraining evidence。长期统计不能替代当次资格判定。

## 17. 团队长期能力

区分 stable team、ad-hoc team、flight/section、package。长期指标包括 Shared Picture、Task Coordination、Communication、Role Compliance、Objective Completion 等；必须绑定成员构成和 scope。

成员组合变化时应分段或作为 cohort factor，不能把 composition change 误判为“团队能力突变”。

## 18. TPAA-M 长期过程指标

除 competency/score 外，长期应保留：

- Truth–Perception Gap trend；
- Perception–Action latency/response trend；
- Action–Adjudication link trend；
- Machine availability/degradation trend；
- Human-Machine effectiveness trend；
- Team perception divergence trend；
- TPAA-M chain completeness trend；
- Process–Outcome divergence trend。

这些产品需要单独 semantic/version contract，不能从总分反推。

## 19. Scenario Cohort 与可比性

Cohort minimum key 由 Extension Contract Registry 控制，至少包含平台/构型、training/episode/stage、scenario/role/team size、difficulty/environment、World Capability 和 Profile/Metric/Attribution version。

同类 cohort 在 M8 的首个受控 P4/P5 实现中使用描述统计/经验百分位；后续 mixed-effects、hierarchical Bayesian 或 difficulty model 可以替换实现，但必须保持输出 contract、验证并明确不确定性。

## 20. Course / Unit Analytics

课程/单位层产品可以发现：

- 某 competency 在群体中长期偏低；
- 某 scenario/objective 异常困难；
- 数据源/训练设备质量持续退化；
- 不同 rubric/instructor group 的系统差异；
- 训练前后观察差异；
- team/package 过程的共性断点。

群体反馈不得自动转换为个人责任；观察到的 pre/post difference 不自动称为因果 training gain。

## 21. Training Plugin Contract

每类训练插件必须组合：

```text
ContextApplicabilityProfile
+ WorldReconstructionPolicySet
+ Stage/Objectives Projector
+ TPAA-M Chain Builder
+ Event/Relation/Compliance Detectors
+ MetricSet
+ AssessmentProfile
```

Source Adapter 和 World Reconstruction 是唯一能解释 source-specific 记录的业务下层；Metric/Assessment plugin 不得读取任意原文件绕过主干。

## 22. Application/API Requirements

P4/P5 API 至少需要概念级资源：Actor Assessment、Competency Observation、Mission/Team Assessment、Objective Result、Instructor Annotation/Review、Cohort/Longitudinal、Root-cause Candidate/Evidence Graph。字段合同在进入对应 M 里程碑实施时从 Core/DTO machine authority 生成，不在本分册手写。

历史读取必须绑定 exact Release/Profile/Context；current Profile 只可显示比较状态，不能覆盖历史 assessment semantics。

## 23. GUI Requirements

需要支持：

- Individual Training Assessment；
- Team/Package/Mission Assessment；
- BVR Team Shared Picture / Task Swimlane；
- Strike Assignment/Designation/Official Scoring；
- Competency Profile + Qualification；
- Evidence / Root-cause Candidate；
- Instructor Review workflow；
- Human/Team longitudinal；
- Course/Unit analytics；
- Joint/LVC entity-relation graph / objective tree。

所有视图共享 Session Time、Release、Context、scope 和 Evidence selections。

## 24. Validation

Golden set 至少覆盖四类训练、Individual/Team/Package、P/J/M 缺失、系统故障不归因个人、team composition change、mandatory metric 缺失、critical gate、instructor override revision、SA 边界、process–outcome divergence、Joint/LVC adapter fixture。

内容效度必须由训练/教员专家确认 competency、Profile、objective、root-cause category 和 training-standard 语义；文档存在不代表用于资格评估的适用性已经验证。

## 25. 分册验收

- 四类训练均有 P4/P5 设计路径；
- Individual/Team/Package/Joint-LVC scope 不混写；
- Qualification/Diagnostic/Evidence 三层可追踪；
- W 不替代 P、Action 不替代 J；
- system/data issue 不自动归因 individual；
- instructor override 不修改 immutable Metric/World；
- team longitudinal 保存 composition；
- cohort 不可比较时分段/fail-closed；
- P4/P5 未实现时 UI/API feature-gated。

## 26. R3 方法论保真约束

本分册的工程实现必须保持 `03A_整体训练效果评估方案_TPAA_V8.0.md` 的完整评价链，而不是只实现对象名：五个核心问题、结果≠能力、安全 Gate、缺失≠0、C+TPAA-M、Data Quality/Confidence、Qualification/Competency/Evidence、四类训练专项逻辑、责任/可控性、Event Graph/候选根因、Instructor 双轨、Longitudinal/Cohort/Debrief 都是验收语义。

当 03A 与本分册表达粒度不同：方法意图以 03A 为准，字段/类型/枚举以 Canonical 为准，工程流程以本分册为准；不得通过删减方法层来“解决”冲突，应修正工程映射。
