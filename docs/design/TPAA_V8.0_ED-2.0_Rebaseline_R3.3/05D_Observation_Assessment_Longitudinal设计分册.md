# ED-2.0 分册 D：Observation、Assessment 与 Longitudinal

**定义权声明：** 本分册只定义 Observation/Assessment/Longitudinal 的流程与约束；字段、指标、subject/lane/trend eligibility 分别引用 Core Baseline 与 Canonical artifacts，不复制字段级 schema。

## 1. Observation 三路由

Published Metric 根据 Catalog route 进入 Aircraft Capability Observation、Mission-System Performance Observation 或 Quality Evidence-only。Observation 不是第二次计算 Metric，而是把 published result 与主体、Context、Evidence、时间范围、eligibility/comparison key 绑定。

## 2. Aircraft Observation

必须证明 aircraft/model/instance/configuration snapshot/session 一致，并与 observed Metric 的 release/session/context/subject/evidence exact-match。P1 不得把 Human-Machine Episode 或 factor features 设为必填。

## 3. Mission-System Observation

必须绑定 stable mission_system_instance_id 和所属 aircraft。Reference truth/alignment uncertainty 是观测质量证据，不改变主体 identity。

## 4. Assessment

Assessment 只消费 Metric/Event/Objective/Annotation/Profile，不直接读高频 source。Critical gate、competency aggregation、qualification、diagnostic score、confidence 与 evidence package 分层；后续 Attribution 不能反写 P1 observed value。

## 5. Longitudinal Sample

P1 longitudinal sample unit 是 SESSION_CONFIG；该能力在 M4 / `WS-LONGITUDINAL` 闭合。仅 trend-eligible numeric metric 可进入。配置、semantic version、metric definition、episode/stage/maneuver、unit、sample profile 等变化必须通过 comparison key 分段。

## 6. 双主体

AIRCRAFT 与 MISSION_SYSTEM_INSTANCE 使用同一 `subject_type + subject_id` 抽象，但 configuration_key 的构造必须是主体相关的 canonical hash。不得使用含义不明的 generic `configuration_id`。

## 7. Trend

Trend 输出 observed performance 的 current value、EWMA、slope、MAD/stability 与 status；历史 trend 必须保留 input SESSION release IDs，不能被 current Catalog/Context 重新解释。

## 8. Evidence drill-down

Trend point → Sample → Observation → Published Metric → Definition/Release → Context/World/Evidence → Canonical/source lineage。该链任何一层缺失都视为合同缺陷。

## 9. Observation Builder

Builder 输入 Published Metric + immutable Definition + Release/Context + subject master + evidence。先校验 publication_route 和 subject_type，再校验 metric scope/episode/stage、subject identity、release/session/context/evidence exact-match，最后生成 Observation。禁止从 value 或 metric_code 猜 route/subject。

Aircraft Observation 需要建立 aircraft entity/instance/model/config snapshot 的一致性；Mission-System Observation 需要 stable mission_system_instance 与所属 aircraft 一致。若 subject 与 Metric Definition 不匹配，必须拒绝发布而不是标记低 confidence。

## 10. Eligibility

Eligibility 与 Metric status 分开。Metric 可以 VALID，但因为 comparison configuration unknown、reference quality 或 longitudinal profile 条件而不适合进入某种 Observation/Trend。Eligibility 输出 ELIGIBLE/EXCLUDED/REVIEW_REQUIRED 与原因码。

## 11. Comparison Key

Comparison key 至少覆盖 stable subject、configuration、metric semantic/version/definition、unit、episode/stage/maneuver、detector/profile 与影响可比性的 measurement semantics。其 canonical descriptor/hash 必须可重建，不能只存不透明字符串。

## 12. Longitudinal Sample Builder

对一个 Session Release，同 subject/configuration/metric/comparison scope 内汇总可用 Observation，使用 Catalog/default 或批准 sample profile 的 aggregation。当前基线默认 trend-eligible numeric 为 MEDIAN；任何 alternate aggregation 都必须有明确 profile/version 并导致 comparison segmentation。

Sample 保存 input Session Release、source Observation refs、coverage/confidence/status 与 sample profile。Structured composite 不允许通过 JSON path 隐式提取子字段进入 sample；如未来需要，应新增版本化 child/projection Metric。

## 13. Trend Builder

Trend 在 immutable Longitudinal Release 中对 sample 序列计算 current value、EWMA、slope、MAD/stability 等受控输出。X 轴可以是 Session Order 或 Calendar Time，但语义必须明确并可复现。缺少可信 session order/UTC 时不能擅自替换。

## 14. Lifecycle Marker

Aircraft configuration、maintenance、software/hardware 变化等 marker 用于解释和分段，不自动成为因果归因。Marker 若改变 comparison compatibility，必须切断 trend 或进入新的 configuration key；如果只是注释信息，则作为 point/context evidence。

## 15. Assessment Engine 详细边界

Assessment pipeline：Data Sufficiency → Critical Gates → Competency Aggregation → Qualification Rules → Diagnostic Score → Confidence → Evidence Package。Assessment Profile 决定规则/阈值，但不修改底层 Metric 值。教员 annotation 可以确认/补充/否决评估解释，但不能篡改历史 Metric/World facts。

## 16. Attribution

P2 之后的 Attribution 使用冻结 Factor View/Context，输出候选因素和置信度。Attribution 与 P1 Observation 分表/分产品，不把 adjusted/intrinsic result 写回 observed value。结果不足时允许多候选/unknown，不强制唯一原因。

## 17. Drill-down Contract

每个 UI Trend point 必须能定位 sample；sample 定位 source observation；observation 定位 metric_instance/evidence；metric 定位 definition/release/context/world/chain；最终可以到 Canonical/source lineage。该链应由 contract tests 自动验证。

## 18. D 分册验收

- route/subject mismatch 必须拒绝；
- structured metric 永不进入 numeric sample；
- 104 个 eligible numeric 指标的主体分布保持冻结；
- configuration/semantic 变化切断可比链；
- historical trend 读取 input Session Releases，不用 current Catalog 重解释；
- drill-down 在 current/historical release 均闭合。

## 19. P4/P5 Assessment 扩展

P4/P5 训练评价的训练类型、scope、competency、三层输出与 instructor-review 语义统一引用 `TRAINING_EVALUATION_TAXONOMY.json`；详细流程见 05I。本分册继续负责 Observation/Assessment/Longitudinal 的共用 product boundary，不在 D 内复制 05I 的训练类型规则。

Assessment 的 claim level 必须区分：Observed Evidence、Qualification、Diagnostic Competency、Instructor Judgment、Mission/Objective Assessment。`Mission Outcome` 只能作为结果维度，不自动替代人员 competency 或平台 capability。

## 20. Assessment Profile Governance

Profile 至少冻结 World/Data requirements、applicable Episode/Stage/Objectives、Metric/Event eligibility、Critical Gates、competency mapping、minimum quality、missing strategy、rubric/grade mapping、instructor-review policy、validity/version/publication。

Profile 更新不改变历史 Assessment。历史读必须绑定 exact profile/spec/release；不得以 current profile 重算后覆盖旧结果。

## 21. Instructor Annotation / Override

Annotation/Review 是正式 revisioned product。Override 需要保存 base release/product、原自动结果、reviewer、reason、rubric/Profile version 和 supersession；不修改 Metric/World facts。

一致性分析（Kappa/ICC/distribution/concordance）是独立 longitudinal/analytics product，用于标准化和内容效度，不成为简单 reviewer ranking。

## 22. Human / Team Longitudinal

人员与团队长期产品与 P1 Aircraft/System numeric trend 分开。未来至少保留 competency observation、qualification、scenario/role/team composition、World Capability、Profile/Metric versions、TP/PA/AJ/team/chain process indicators、instructor review、significant events。

Team longitudinal 必须绑定 composition；ad-hoc team 默认按 cohort 分析，除非存在稳定 team identity。

## 23. Scenario / Cohort Comparability

Longitudinal comparison key 需要覆盖 Extension Contract Registry 定义的 material factors。Cohort label 相同不自动证明统计可比；群体进出、来源变化、算法/Profile 变化和 World Capability 变化都要显式解释。

M8 中 P4/P5 纵向评价的首个受控实现可以使用中位数、分位数、经验 percentile；高级 mixed-effects/Bayesian/difficulty model 属于新 model/spec，需要单独验证，不在 D 分册内硬编码。

## 24. Course / Unit Feedback

课程/单位层分析消费已发布 individual/team products 和 cohort metadata，用于发现群体 competency/objective/data-quality/instructor-rubric 等系统性模式。它不回写 individual assessment，也不把 pre/post observation difference 自动声明为因果训练收益。

## 25. P2/P3 衔接

P2/P3 详细设计见 05J。D 分册保证：

- P1 Observation 是 immutable 输入；
- Attribution/Adjusted Estimate 使用独立 product identity；
- capability estimate/twin/model profile 不写回 Observation；
- Longitudinal UI/API 能同时区分 observed、adjusted、reference-condition estimate；
- lifecycle marker 是 evidence/segmentation，不自动成为因果结论。

## 26. Knowledge-time Longitudinal

Trend/assessment history 需要能够区分按当时信息的产品和后来补充信息形成的 retrospective revision。后补 Context、maintenance、configuration、instructor label、official adjudication 只能产生新 revision/release；不能静默改变旧 longitudinal point。

## 27. D 分册扩展验收

- Profile/Instructor/Assessment 历史 exact-binding；
- Human/Team 与 Aircraft/System longitudinal 产品不混 lane；
- team composition/change 可追踪；
- cohort 不可比时不连接趋势；
- group/course analytics 不回写个人结果；
- P2/P3 estimate 与 P1 Observation 保持 claim-level 隔离；
- as-known 与 retrospective revision 可区分。
