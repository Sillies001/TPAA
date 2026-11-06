# ED-2.0 分册 A：数据、Canonical Model、Context 与 Episode

**定义权声明：** 本分册只定义工程流程与实现约束；字段级事实由 `canonical/CORE_LOGICAL_MODEL.json`、Stage 语义由 `canonical/STAGE_REGISTRY.json` 唯一定义。

## 1. 职责

本分册定义 Source→Canonical→Context→Episode/Stage 的工程流程，不另建字段权威。所有 persistence 字段引用 `CORE_LOGICAL_MODEL.json`。

## 2. Source / Provenance

原始 artifact 不覆盖；Adapter 输出保留 source artifact、stream ordinal、row ordinal、mapping manifest、measurement semantics 等 lineage。Adapter 只做格式、单位、基础状态、来源保持型转换，不实现训练业务指标。

## 3. Time Alignment

固定顺序：physical artifact order → stream ordinal → clock reset/segment → validated TimeTransform → Session Time → Alignment Domain → Analysis Series。未解决的步骤不得“尽力拼接”。

Time status：RESOLVED 可用于正式产品；EXTRAPOLATED 仅 diagnostic/optional enrichment；UNRESOLVED 保留证据但不进入正式统一时间轴；INVALID 拒绝。

## 4. Entity / Aircraft / Mission-System Identity

Entity resolution 优先使用官方共同 ID，再使用已批准映射，最后才允许带 confidence 的时空推断。Aircraft instance 与 Mission-System Instance 是 stable subject chain 的基础。Mission-System identity-affecting configuration hash 改变时创建新 instance，而非在原主体上偷换配置。

## 5. Context

Context 是 Session 内按 Session Time 生效的 immutable-revision object。Scenario/Profile 可按 Core schema 合法为空；不得在 Session/Episode 上再复制一套可变 current Context。所有配置引用通过 context_artifact binding 固定 object/hash。

## 6. Episode

Episode detector 只使用 Canonical/Context/World 允许的数据与 approved markers。Episode correction 使用 supersession，不原地覆盖。Episode persisted core 不冗余 Scenario；Scenario 从 exact Context 解释。

## 7. Stage

Stage 由 `STAGE_REGISTRY.json` 管理。`stage_id` 是 World/Metric/API 的唯一 Stage identity；Stage 不能由各插件自由创造。

## 8. Performance Window

Performance Window 是 Stage 内或 Episode 内的观察窗口标签，可携带 maneuver/condition tags，但 P1 不以这些标签自动宣称完成因素剥离。

## 9. 数据质量与可计算性

Schema、数值范围、clock/time、entity、gap、coverage、configuration、measurement-semantics 均形成可计算性证据。缺 mandatory input 时 Metric 输出受控状态，不允许静默补值。

## 10. 测试

Golden 至少覆盖 clock rollback、respawn、source switch、configuration boundary、measurement semantics change、Context revision overlap、Stage precedence conflict、manual supersession、artifact missing fail-closed。

## 11. Canonical Domain 划分

Canonical 层按 Registry/Provenance、Master Identity、Time/Quality、Aircraft Kinematic/Dynamic/Control/Propulsion/Configuration/System、Environment、Episode/Stage/Series 等领域组织。高频事实与低频 master/config 分离，避免把版本/配置重复写入每一采样行，同时确保每个采样能通过 stable identity 与有效期追踪到配置。

## 12. Source Adapter 合同

Adapter 至少提供 inspect、normalize 和 lineage。normalize 输出必须是 schema-versioned Canonical Dataset，且包含稳定 source row 定位与 Mapping Manifest。单位换算、状态正规化、合法的基础字段派生可以在 Adapter 中完成；任何课目/训练评价逻辑、Stage 判定、Metric 计算必须留在上层。

Adapter 对时间回跳的处理必须保留物理行顺序证据，先标记 source clock segment，再做 segment-local sort/normalization。禁止全局按 timestamp 排序后才检测 reset。

## 13. TimeTransform 与 Alignment Domain

单源 TimeTransform 是从 source clock 到 Session Time 的显式映射，保存模型、参数、残差、状态与版本。多源 Alignment Domain 证明多个 source 在某一重构区间可以共同参与融合/比较。不同 source 不要求具有相同 clock segment ID；它们必须分别完成映射并共同属于可证明的 alignment domain。

## 14. Analysis Series

Series 是数值连续性的一级对象。Gap、clock reset、instance reset、authority switch、关键 configuration/measurement semantic change都会结束当前 Series。所有 derivative、rolling window、sustain/settling、interpolation 和 correlation 默认不得跨 Series。

## 15. Context Resolver 算法

Context Resolver 输入 Session ID + Session Time/interval，查询 ACTIVE/历史 Context revisions 的有效区间并按受控规则选择 exact context_id。发布时把实际解析结果写入 Release context binding；历史读取直接使用 binding，不重新运行 Resolver。

若同一 Session Time 有多个互相冲突的 ACTIVE candidate，Resolver 不按“最大 revision”静默选择，而返回冲突/复核状态。Context correction 产生新 revision/supersession，不覆盖旧 context row 或绑定 artifact。

## 16. Context Artifact Bundle

Scenario、Assessment Profile、Syllabus、Role Model、Reference Set、Rule Set、Metric Profile、Longitudinal Profile 等均以 immutable artifact 登记。Bundle projection 只能从 exact `context_id → binding → artifact → sealed object` 读取，并按受控顺序输出。历史 artifact 缺失或 reader 不支持旧 schema 时 fail-closed。

## 17. Episode Detector

Detector 输出 Episode candidate 的 type、time range、subject scope、context、quality、detector version 与 evidence。验证步骤检查时间完全处于 Session、Context 适用性、subject identity、必要 World capability 和 source sufficiency。修订以 supersession 表达。

Episode 生命周期在业务上可经历 DETECTED、VALIDATED、WORLD_RECONSTRUCTED、METRICS_READY、ASSESSED、ATTRIBUTED、PUBLISHED，并允许 PARTIAL/REVIEW_REQUIRED/INVALID；持久化字段以 Core Model 为准。

## 18. Stage Projector 详细流程

1. 读取 Episode 对应 exact Context 和选定 Stage Profile；
2. 收集 official marker / authority event / rule-derived / inference / manual candidates；
3. 规范化为 Session Time 半开区间；
4. 剔除越过 Episode 边界的 candidate；
5. 按 precedence 解决重叠，保留低优先级 candidate 作为 evidence；
6. 计算 coverage/confidence/status；
7. 稳定排序并赋 stage_order；
8. 发布新 Stage revision；
9. 生成 Stage manifest/hash，供 World/Metric/API 引用。

任何 Stage correction 都不得直接改已发布 Stage 的时间或 code。

## 19. Performance Window 与 Stage 的关系

Stage 是课目/过程语义步骤，Performance Window 是计算观察片段。一个 Stage 可以有多个窗口；一个窗口可附 maneuver/condition tags。窗口 detector version 与 comparison key 必须可追踪，避免 detector 变化后长期趋势仍被误认为完全可比。

## 20. 数据充分度

每个计算请求在进入 WRE/Metric 前形成 Data Sufficiency 检查：required fields、time alignment status、identity status、coverage、gap、configuration、Context、required World capability。检查结果以结构化 reason code 输出，避免插件自行决定不同的缺失策略。

## 21. A 分册验收

- 任一 Canonical value 可追到 source artifact/row/mapping；
- clock reset 不因排序被抹去；
- Context history 不发生 latest fallback；
- Episode/Stage correction 可 replay；
- Stage precedence 同输入同版本产生确定性结果；
- Mission-System stable identity 不从临时 track 猜测；
- 任何缺失输入均产生受控 sufficiency/status。

## 22. R39 全量来源与能力映射承接

Source 类型至少覆盖 Flight、Mission/Avionics、TDL、Range/ACMI、Scenario/Context、Audio/Video，以及后续经治理引入的仿真/互操作/人工审核来源。Source presence 只描述输入可用性，不能直接转换成业务评价资格；评价资格由 World Capability + Context Capability + Data Sufficiency 决定。

Source Adapter 必须输出 provenance、schema/parser/mapping version、time basis、source/entity references 和 quality evidence；只有 Canonical/World 层解释 source-specific semantics，上层训练插件不得依赖文件名或原字段。

## 23. Episode 类型与 Scope 扩展

当前语义至少包括 `BASIC_FLIGHT`、`WVR_ENGAGEMENT`、`BVR_KILL_CHAIN`、`STRIKE_MISSION` 四类 reference Episode。`subject_scope` 需要承载 Individual/Team/Package 等业务范围，但具体持久化枚举由 Core model/migration 在对应 M 里程碑中受控扩展。

P4/P5 进入实施时，应显式建立 participant/role/observer/actor/machine-subject 关系或等价投影，不能只依赖 `primary_*` 字段推断全部参与者。若新增 `episode_participant` / human-machine-link 等对象，必须先进入 Core Logical Model authority，而不是在本分册定义字段表。

## 24. Master Data 与未来扩展尺寸

Entity/aircraft/mission-system 主数据是 P1～P6 共用身份 spine。后续 Team、Package、C2、UAS、virtual/constructive participant、Instructor Station 等对象优先通过通用 Entity/Relation 语义扩展；需要稳定跨 Session 身份的对象再引入受治理 master identity。

Role、任务、side/assignment 等训练语义优先属于 Context/Projection，而不是写成 entity 永久固有属性。

## 25. Knowledge Time / Bitemporal 约束

除 Session Time 和业务 valid time 外，涉及后补构型、维护、人员/团队、Scenario 标签、官方裁决等资料时，要区分记录/修订时间与“何时可获得该信息”。

系统支持两种受控读取：

- as-known replay：只使用当时可获得资料；
- retrospective revision：明确使用后来补充/纠正资料并产生新 revision/release。

不能因为当前数据库已有完整标签，就把它冒充成历史时点已经已知。

## 26. Media / External Artifact 语义

Audio/Video/Transcript 等媒体首先作为 registered artifact + time alignment product 管理；业务复盘通过 Media/Evidence service 引用，不由 GUI 直接读取任意路径。媒体缺失不应使非媒体 mandatory 条件失效，但依赖通信/语音证据的指标或教员 workflow 应明确降级。

## 27. A 分册扩展验收

- 四类 training Episode 可以使用统一 Context/Episode/Stage spine；
- source availability 与 World Capability 不混为一类字段/状态；
- participant/team/package 扩展不会依赖 primary_* 猜测；
- retrospective labels 不污染 as-known replay；
- media/external artifacts 具备 registry/time/provenance 边界；
- 新对象进入实现前必须先修改 Core Logical Model authority。
