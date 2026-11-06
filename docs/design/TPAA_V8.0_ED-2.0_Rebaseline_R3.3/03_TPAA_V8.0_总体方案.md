# 飞机机载数据评估系统总体方案 TPAA V8.0

**基线：** CB-1.4.0  
**工程实现基线：** ED-2.0  
**重构轮次：** Rebaseline R3.1 — Knowledge Fidelity + Cross-Platform Contract  
**日期：** 2026-09-19

## 1. 文档定位

本总体方案定义系统目标、业务语义、评价边界、总体架构、训练评价框架、能力演进路线和系统级约束。它**不定义数据库字段、DTO nullability、REST payload 字段或物理表结构**；字段级事实由 Core Baseline 指向的 machine-readable authority 唯一控制。

本版与 R1 的根本差异是：总体方案不再只把 P1 Observed Performance 写深，而是把 R39 中已经形成且仍有效的 **Basic / WVR / BVR / Strike、Individual / Team / Package / Joint-LVC、P2/P3 Capability Intelligence、P4/P5 Training Assessment、Instructor Review、Longitudinal、Debrief、Course/Unit Analytics 与 P6 扩展边界**全部纳入统一路线，以便后续按成熟度激活而不重新定义体系。

## 1A. 文档体系与方法权威

系统级总体边界由本文定义；完整训练效果评价方法、四类训练业务逻辑、Qualification/Competency/Evidence、教员融合、长期训练与 P2~P6 方法边界由 `03A_整体训练效果评估方案_TPAA_V8.0.md` 作为方法论权威。字段级定义仍由 Core Baseline 的 Canonical artifacts 唯一拥有。

因此总体方案不再用“压缩方法内容”来换取一致性：本文给出总体框架，03A 给出完整方法链，05A~05J 给出工程实现。三者职责不同，不是三套互相竞争的定义。

## 2. 建设目标

系统面向训练、试验和工程数据的可追溯评估，形成从原始数据到 Canonical Facts、Context、Episode/Stage、C+TPAA-M World、Event/Relation/Chain、Metric、Observation、Assessment、Capability Estimate、Longitudinal Product 与 Debrief/Analytics 的确定性链路。

系统必须同时满足：

- **证据可追溯**：任何评价、估计和趋势能回到 World/Metric/原始 lineage；
- **语义可分离**：事实、成员可见信息、动作、官方裁决、机器状态、评价、估计和预测不互相冒充；
- **版本可重放**：历史产品按原 Context/Catalog/Profile/Release/Model 重放，不依赖 current/latest；
- **单机到联合可扩展**：核心对象不因人数、机数、任务群或 LVC 扩展而重建数据库；
- **长期可比较**：比较显式受构型、场景、角色、团队构成、World Capability 和算法/Profile 版本约束；
- **P 能力分层成熟**：P1～P6 有明确 admission boundary，设计合同冻结不等于实现或适用用途已验证。

## 3. 评价边界与成熟度

### 3.1 P1 — Observed Performance

形成 **Aircraft** 与 **Mission-System Instance** 两条工程观测性能主体链，包括 Metric、Observation、Evidence 与数值长期趋势。P1 不把人员、环境、任务难度等因素剥离后宣称为 intrinsic capability。

### 3.2 P2 — Context Attribution & Normalization

在冻结的 P1 Observation、Factor View、Reference Condition 与 Cohort 上进行条件调整/因素关联。允许输出 `NOT_IDENTIFIABLE`；不得为了获得一个数值而强制调参。因素贡献默认是模型条件下的关联解释，不自动具有因果或责任含义。

### 3.3 P3 — Reference-condition Capability / Aircraft Twin

形成受治理的能力模型、能力曲面、单架飞机 Twin Revision、参考条件下的长期性能估计与型号画像。默认术语是“参考条件下长期性能估计”；只有在测量对象、可识别性和独立验证充分时，才可另行主张 intrinsic capability。

### 3.4 P4 — Human-Machine / Individual Training Assessment

基于 C/W/P_i/A_i/J/M_i、Metric/Event/Evidence 和 Assessment Profile 形成 Qualification、Diagnostic Competency 与 Evidence 三层输出。更高层的理解、预测和判断不得仅因 P_i 可获得而自动认定，需要经验证代理指标或教员 rubric。

### 3.5 P5 — Team / Package / Mission Assessment

面向多成员、多机、团队、任务群和总体任务目标进行共享态势、角色、信息收敛、通信、任务交接、动作同步、间隔/解冲突与 Objective 评价。团队能力不是成员平均值；团队结果也不复制为个人结果。

### 3.6 P6 — Forecast / Counterfactual / Closed Loop

形成 Forecast、Counterfactual、Training Recommendation 与 Intervention Outcome 等产品。此类产品必须在存储、API、UI 和审计上与事实/历史回放物理隔离，并显式展示假设、模型、验证状态和批准状态。

### 3.7 安全边界

系统不得自动推导现实武器性能包线、最佳发射/释放几何、命中概率模型、战术优化或作战建议。WVR/BVR/Strike 中涉及的 weapon/engagement 仅表达训练规则、训练动作和经批准外部裁决证据。

## 4. 核心语义对象

系统级对象包括：Training Session、Evaluation Context、Episode、Episode Stage、Entity/Aircraft/Aircraft Instance、Mission-System Instance、World Product、Event/Relation/TPAA-M Chain、Metric Definition/Published Metric、Observation、Assessment、Evidence、Annotation、Analysis Release、Longitudinal Product，以及 P2～P6 的 Attribution、Capability Estimate/Model/Twin/Profile、Forecast/Counterfactual/Recommendation 等受治理产品。

对象字段、枚举和 nullability 不在本文件重复定义；训练类型、评价域和 World Capability 的语义权威分别由 Core Baseline registry 控制。

## 5. 总体处理链

```text
Source Artifacts
→ Registry / Provenance
→ Quality + Time Alignment + Entity Resolution
→ Canonical Facts
→ Immutable Evaluation Context
→ Episode Detection / Validation
→ Episode Stage Projection
→ C + W/P/A/J/M Reconstruction
→ Event / Relation / TPAA-M Chain
→ Metric Engine
→ P1 Observation
→ P2 Attribution / Context Adjustment
→ P3 Capability Model / Twin / Model Profile
→ P4 Individual / Human-Machine Assessment
→ P5 Team / Package / Mission Assessment
→ Debrief / Longitudinal / Course-Unit Analytics
→ P6 Forecast / Counterfactual / Recommendation (when admitted)
→ Versioned Release / Historical Replay
```

业务 Metric 不直接读取 source-specific raw records。只有 Data Quality、Canonicalization、World Reconstruction 和 Audit 边界可以解释 source-specific facts。P2～P6 只能消费已发布的上游产品，不能回写上游事实。

## 6. C + TPAA-M 统一语义

- **C / Context**：Scenario、Objective、Role、Rule、Reference、Training Standard、Assessment Profile 等规范与解释条件；
- **W / Ground Truth or Reference World**：在声明 authority 下的事实/参考状态；
- **P_i / Perception**：对 observer i 客观可获得的信息，不等于主观理解；
- **A_i / Action**：actor i 的控制、模式、任务、通信或训练动作；
- **J / Adjudication**：经批准 authority 的正式训练裁决；
- **M_i / Machine Capability/State Evidence**：机器/平台状态与能力供给证据，不等于长期能力估计。

C 不混入 W/P/A/J/M；Assessment 不写回 World；P2/P3 Estimate 不写回 M；P6 Prediction 不写回历史事实。

## 7. World Capability 与可评价性

“有文件”不等于“能评价”。系统同时报告 Source availability、World Capability、Data Sufficiency、Coverage 与质量/不确定性证据。

受控 World Capability 至少包括：BASIC_CORE、WVR_CORE、WVR_INFO、WVR_FULL、BVR_PROCESS、BVR_FULL、STRIKE_CORE、STRIKE_INFO、STRIKE_FULL。具体 required/optional worlds 由 `WORLD_CAPABILITY_REGISTRY` 唯一控制。

共同降级规则：

- 缺 P：不得用后台 W 代替成员当时可见信息；
- 缺 J：可以评价过程/动作，但官方结果为 N/A/NOT_ADJUDICATED；
- 缺 M：可保留适用的人/任务子集，但不得生成平台能力 Observation；
- 缺版本化 C：依赖规范判断的指标/Assessment 降为 DESCRIPTIVE 或 fail-closed；
- mandatory world/data 缺失：相关结论为 N_A/INSUFFICIENT_DATA，而不是 0 分。

## 8. Episode 与 Stage

Episode 是可解释的训练/评估语义单元；Stage 是 Episode 内正式、版本化、可修订、可回放的子对象。Stage 只由 Stage Registry 定义，Metric、UI 和训练插件不得维护另一套“当前 Stage”。

当前参考 profile：

| Training type | Reference profile | Stage chain |
|---|---|---|
| Basic Flight | BASIC_FLIGHT_V1 | SETUP_ENTRY → EXECUTION → STABILIZATION_RECOVERY → COMPLETION |
| WVR | WVR_ENGAGEMENT_V1 | MERGE → POSITION_ADVANTAGE → MANEUVER → WEAPON_ENVELOPE → LAUNCH → KILL_ASSESSMENT |
| BVR | BVR_KILL_CHAIN_V1 | DETECTION → TRACK → IDENTIFICATION → DECISION → WEAPON_EMPLOYMENT → ASSESSMENT |
| Strike | STRIKE_MISSION_V1 | MISSION_SETUP → ROUTE_TASK_EXECUTION → TARGET_INFORMATION_AVAILABLE → TARGET_ASSOCIATION → DESIGNATION_TRACK → TRAINING_ATTACK_EVENT → RANGE_SIM_ADJUDICATION → POST_EVENT_TASK_TRANSITION → RECOVERY |

Stage 规则由 immutable Context artifact 选择。模型推断和人工修正必须保留来源、confidence、revision/supersession。

## 9. P1 指标体系

P1 冻结 116 项指标；R3.2 保持其公式、semantic/algorithm identity、input fields 与 661 binding tuples 不变，仅将旧进度元数据迁移为 M/WS 语言。R3.3 进一步增加 `05C1_116指标设计意图_适用边界_区别联系与计算方法说明.md`，用于解释每项指标的设计原因、适用产品层和相邻指标关系；可执行公式仍只由 Catalog 定义。系统级分布：

**指标族适用性说明：** SNS 在当前基线中特指 RADAR 探测/测量层；PSV=IRST/EO，ESM=RWR/ESM，DL=DATALINK，FUS=FUSION；TRK/ID 是产品处理层而不是物理传感器类型。

| 维度 | 数量 |
|---|---:|
| REFERENCE_TRUTH | 3 |
| TIME_ALIGNMENT | 5 |
| AIRCRAFT_FLIGHT | 20 |
| AIRCRAFT_ENERGY | 8 |
| AIRCRAFT_CONTROL_RESPONSE | 4 |
| AIRCRAFT_HANDLING | 4 |
| AIRCRAFT_PERSISTENCE | 3 |
| SENSOR_DETECTION | 4 |
| SENSOR_ACCURACY | 17 |
| TRACK_PERFORMANCE | 7 |
| ASSOCIATION_IDENTIFICATION | 12 |
| PASSIVE_SENSOR | 7 |
| RWR_ESM | 6 |
| DATALINK | 8 |
| SENSOR_FUSION | 8 |

P1 指标开发采用受控 M/WS 交付映射：M2 / `P1_FOUNDATION_32` 完成 32 项 foundation batch，M3 / `P1_REMAINDER_84` 完成其余 84 项；M4 / `WS-LONGITUDINAL` 仅把 104 个 trend-eligible NUMERIC 指标送入长期数值趋势。P4/P5 的训练评价指标和 P2/P3 的能力估计指标**不复用或改写这 116 项定义权**，而是在其上建立独立版本化合同。

## 10. P1 双主体与长期基础

### 10.1 Aircraft Lane

Aircraft master/instance/configuration → aircraft metric → CAP-L1 observation → longitudinal sample/trend。

### 10.2 Mission-System Lane

Stable mission_system_instance → system metric → system performance observation → longitudinal sample/trend。

两条 lane 不混合成一个“平台总能力分”；TARGET_PAIR 只作为 reference/evaluation quality evidence。P2/P3 可以消费这些 Observation，但不改变其值和历史语义。

## 11. 评价输出三层结构

训练评价统一分为三层：

1. **Qualification**：由 Critical Gate、mandatory evidence 和 Profile 规则控制；
2. **Diagnostic Competency**：按受治理的能力域、Metric/Event Evidence 与 Profile 聚合；
3. **Evidence**：事件、关系、时间窗、轨迹、曲线、World、媒体、版本与 provenance。

缺 mandatory evidence 时不是简单降低置信度；Qualification/Competency 必须明确进入 INSUFFICIENT_DATA/N_A 等状态。安全 gate 先于普通加权聚合。

## 12. 人员能力域

P4 通用 competency 域为：Safety & Discipline、Aircraft Control、Flight/Task Execution、Information & System Management、Situational Awareness Evidence、Decision & Task Management、Communication、Team Coordination、Training Engagement Execution、Mission Outcome Evidence。

Mission Outcome 是结果证据，不替代能力。SA 自动评价只覆盖可观察的信息可达、关联、响应和经验证行为代理；更高层理解、预测、判断需独立验证或教员 rubric。

## 13. 多层级评价对象

- **Level A / Individual**：pilot/crew、aircraft、human-machine link；
- **Level B / Team**：element/flight/team；
- **Level C / Package/Mission Group**：多个团队、C2、UAS、地面/海上或 virtual/constructive entities；
- **Level D / Joint/LVC**：通过 Entity/Relation/Source/Plugin 扩展接入，不重建核心评价语义。

个人、团队、任务群、联合/LVC 始终保留独立 scope 和 identity。

## 14. Event Graph、Relation 与责任边界

复杂任务把散乱时序转换成 Event Graph；边可表达 PRECEDES、RESPONDS_TO、AFFECTS、EVIDENCE_FOR、候选原因等受控关系。Event/Relation 用于测量时间、定位断点、建立 TPAA-M chain、自动复盘和解释评分。

多机事件应保留 actor、owner、affected entity、team、controllability 与 contribution confidence。TDL 中断、range truth 缺失、sensor log gap、clock/sync 等系统或数据问题不得自动归因给个人。

## 15. 根因候选而非过度因果断言

自动系统输出 Root-cause Candidate，不输出未经确认的唯一因果结论。候选类别包括 Flight Control、Information Availability、Track/Association、Procedure、Decision/Task Management、Communication、Team Coordination、Training System、Data Quality、External/Scenario、Instructor Determination。

P2 Attribution 也遵守同一原则：模型因素效应默认不是人员责任判决、故障诊断或因果证明。

## 16. 数据质量、充分度与置信度

每个 Session/Episode 需要 Data Quality / Sufficiency 证据，包括时间单调/采样/gap/duplicate、单位/坐标、valid flag、同步/漂移/残差、entity matching、Context/Profile 完整性、构型/主体身份、World coverage、重复观察与独立性风险。

`confidence` 默认是经验质量指数/等级，不自动表示“结论正确概率”。Coverage、测量不确定性、模型不确定性、identifiability 和 evidence independence 分开表达。

## 17. Basic Flight 总体评价（扩充）

Basic Flight 的目标不是单一飞行总分，而是把 **C 定义的课目要求、W 中的实际飞行状态、A 中的控制/任务动作、M 中的平台状态与可选 P/J 证据**组织为可回放的 Episode/Stage 评价。

### 17.1 主要评价域

- Safety & Discipline：空域/高度/速度/程序限制、告警和 Critical Gate；
- Aircraft Control：姿态、航向、高度、速度、载荷/过载、操纵响应；
- Flight/Task Execution：课目轨迹、Stage、任务完成与 reference comparison；
- Handling & Stability：capture、settling、oscillation、control reversal、jerk 等证据；
- Energy/Performance：能量、加减速、爬升、恢复、燃油等 P1 Observation；
- Human-Machine（P4）：信息/模式利用、动作时序、程序符合性与可观察行为；
- Longitudinal：同构型/同课目/cohort 下的重复性、稳定性、趋势与近期有效暴露。

### 17.2 C+TPAA-M 使用方式

BASIC_CORE 要求 C+W+A+M；P/J 是独立可用能力。P 不存在时不能产生依赖 cockpit information 的结论；J 不存在时不能产生官方 outcome。平台 P1 指标和 P4 人员训练评价保持两条解释链，避免把人员操纵差异直接写成飞机固有能力，也避免把平台/数据问题直接扣给人员。

### 17.3 Stage 与 Evidence

Reference stage 为 `SETUP_ENTRY → EXECUTION → STABILIZATION_RECOVERY → COMPLETION`。每个 Stage 可关联 objective、metric window、quality gap、event、annotation、trajectory/series evidence。具体课目扩展必须形成新的版本化 Stage Profile/Context artifact。

### 17.4 输出

单架次输出至少包含 Qualification、关键 competency/evidence、P1 Aircraft/Mission-System Observation、Data/World Capability、关键事件、教员标注和长期可比性状态；不得只输出一个总分。


### 17.5 评价逻辑链

Basic Flight 不以单次结果代替飞行控制能力。评价从 C 中的 maneuver objective/reference/tolerance 出发，以 W 中实际状态、A 中操纵/模式、M 中系统可用能力为证据，先识别 maneuver/stage，再计算偏差、稳定性、驻留、capture/settling、限制接近和重复性。Safety/limitation 作为 Gate；数据缺失产生 N/A/INSUFFICIENT_DATA，而非 0 分。P4 人员评价只有在具备人员可控性和行为证据时才从飞机表现证据向 Human-Machine Competency 推进。

### 17.6 复盘使用

复盘必须同时显示 Context reference band、实际轨迹/参数、Stage、关键 Event、Metric/Evidence 和数据质量，使教员能够区分“飞机未达到参考”“参考/场景改变”“系统能力受限”和“人员动作差异”。详细方法见 03A §9 与第二编 Basic Flight。

## 18. WVR 总体评价（扩充）

WVR 评价围绕相对几何、控制/能量、成员可见信息、训练动作、团队过程和批准裁决构成证据链，不搜索或推荐现实作战最优机动。

### 18.1 World Capability 层级

- WVR_CORE = C+W+A+M：几何、控制、能量与动作；
- WVR_INFO = C+W+P+A+M：增加 Track/Cue/SA Evidence/Response/Team information process；
- WVR_FULL = C+W+P+A+J+M：增加 approved training outcome linkage。

无 P 不产生 SA/Track 类结论；Truth 不得代替 P。

### 18.2 相对状态与 Episode 链

WVR 由 W/Reference World 派生训练需要的相对状态与几何 evidence；Stage reference 为 `MERGE → POSITION_ADVANTAGE → MANEUVER → WEAPON_ENVELOPE → LAUNCH → KILL_ASSESSMENT`。WEAPON_ENVELOPE 只代表训练规则定义的 opportunity/condition window。

### 18.3 评价内容

- Safety & Flight Control；
- Geometry Evidence 与状态驻留；
- Energy/State Evidence；
- Information/SA Evidence（仅 WVR_INFO/FULL）；
- Cue-to-Response 与 Mode/Task evidence；
- Team coordination/communication（P5）；
- Training Engagement Action 与 Official J 分离；
- Process–Outcome divergence：过程良好但结果较差，或过程不足但外部结果偶然良好，均需分别呈现。

### 18.4 长期评价

长期比较至少受 aircraft/configuration、training type、role、scenario/difficulty、team composition、World Capability、Profile/Metric version 控制；几何/信息/响应/团队趋势不应被一个 WVR 总分掩盖。


### 18.5 评价逻辑链

WVR 评价采用“相对状态 → Engagement Stage/Event → Geometry/Energy/Information/Action → Outcome”的过程链。几何优势、能量管理、信息可获得性、反应时延、团队协同与官方训练结果分别保留，禁止用最终胜负覆盖过程表现。信息/SA 结论只能基于可证实 `P_i` 与行为证据，不能从 W 的全知真值反推人员当时必然知道什么。

### 18.6 复盘使用

3D/2D relative replay、Geometry State Ribbon、Energy/State、Cue–Response、Team coordination 和 J markers 应在同一 Master Timeline 上联动。详细方法见 03A §10/第二编 WVR 与 05G。

## 19. BVR 总体评价（扩充）

BVR 是 C+TPAA-M 语义最完整的训练类型之一，重点评价 **信息建立 → 关联/识别 → 任务响应 → 团队协同 → 训练动作 → approved adjudication** 的证据链。

### 19.1 六世界边界

C 定义 relevant entities、任务、角色、规则与标准；W 表示 authority truth/reference；P_i 表示每个 observer 当时可获得的信息；A_i 表示任务、模式、通信和 engagement action；J 表示批准裁决；M_i 表示传感器/数据链/融合/任务系统状态与能力供给证据。

后台已知 Truth 不等于成员当时知道；系统状态异常不自动归因人员。

### 19.2 Kill Chain Stage

Reference profile 为 `DETECTION → TRACK → IDENTIFICATION → DECISION → WEAPON_EMPLOYMENT → ASSESSMENT`。Stage 下可以保留更细的 event-state vocabulary，但不得形成第二套 current Stage authority。

### 19.3 评价内容

- Track availability、continuity、age 与 reacquisition；
- Truth–Perception association 与 identification evidence；
- Cue-to-response、task lifecycle 与 role compliance；
- Team shared picture、perception divergence、communication、task handoff；
- P–A response 与 process bottleneck；
- A–J Link：training action 与 official result 的可追溯关联；
- M evidence：Radar/IRST/EO/RWR/ESM/TDL/Fusion 等系统供给与 degradation；
- Root-cause candidates 与 instructor confirmation；
- Team/Package objective 和 Process–Outcome divergence。

### 19.4 输出与长期

输出不仅包含 Qualification/Competency，还保留 TP gap、PA response、AJ link、team divergence、chain completeness 与 World Capability。长期趋势按 actor/team/mission-system/aircraft 等不同 subject lane 分开，不能将 BVR mission outcome 直接变成人员或平台能力。


### 19.5 BVR 证据推理链

BVR 的核心不是单一命中结果，而是 `C → W → P_i → A_i → J (+M)` 的信息—动作—裁决链。Track Availability、Continuity、Age、Truth-to-Track Association、Classification/Identification、Cue-to-Response、Team Shared Picture、Task/Role、Communication 和 Post-event 必须分别形成证据，并通过 Relation/Gap 解释偏差发生在哪一环。

### 19.6 评价边界

Truth 不等于 Crew Available；共享链路存在不等于某成员已获得信息；动作发生不等于动作合理；J 的官方结果不等于过程能力；M 的可用能力不等于人员实际使用。详细方法见 03A §11/第二编 BVR 和 05G BVR 工作台。

## 20. 空对面/Strike 训练总体评价

Strike 采用与真实武器性能无关的训练评价框架，包括对地/对海面等场景。系统不生成最优攻击航线、真实释放包线或武器性能结论。

### 20.1 C+TPAA-M 使用方式

C：planned route/profile、assigned/eligible target、task/role、training/range/safety rules、Objective/Profile；W：truth target、平台和环境事实；P_i：target/track/TDL/cue/designation information；A_i：target selection/association/designation/mode/communication/training trigger/release/post-event task；J：approved range/simulator valid/invalid、official miss/score/result；M_i：平台/传感器/任务系统状态。

### 20.2 Stage

`MISSION_SETUP → ROUTE_TASK_EXECUTION → TARGET_INFORMATION_AVAILABLE → TARGET_ASSOCIATION → DESIGNATION_TRACK → TRAINING_ATTACK_EVENT → RANGE_SIM_ADJUDICATION → POST_EVENT_TASK_TRANSITION → RECOVERY`。

### 20.3 主要评价域

- Safety & Rule Compliance；
- Mission Route/Profile Execution；
- Target Information & Association；
- Designation Continuity/Stability；
- Training Attack Action 与 J 官方裁决严格分离；
- Multi-aircraft assignment、sequencing、deconfliction、shared target picture；
- Process–Outcome separation。

若无 J，只报告 action/attempt，不推断 official hit/result。approved J 提供的训练命中偏差只用于训练统计，不反推真实武器性能。

## 21. 四类训练统一适用框架

Basic/WVR/BVR/Strike 共享同一 C+TPAA-M spine、Episode/Stage、Event/Relation、Metric、Assessment、Evidence、Release 与 longitudinal 机制；差异由版本化 Context/World policy/Stage profile/Metric set/Assessment profile 表达。

新增训练类型遵循 Training Plugin composition：Context Applicability → World Policy → Stage/Objective Projector → TPAA-M Chain → Event/Relation/Compliance → Metric Set → Assessment Profile。禁止绕开 World 主干直接从源文件计算业务评分。

## 22. Team / Package / Joint-LVC 评价

### 22.1 Team

独立评价 shared picture、information convergence、role/task execution、handoff、communication、action synchronization、spacing/separation 与 team objective。成员构成必须进入长期解释。

### 22.2 Package / Mission Group

支持多个团队、C2、UAS、virtual/constructive entities 和跨域参与者；评价 cross-team information consistency、task handoff、cross-domain timing 与 package objective，而不是强行把全部对象压成一个 cockpit world。

### 22.3 Joint / LVC

通过新 EntityType、RelationType、Data Source Adapter、Training Plugin、Scenario Objective 和 Assessment Profile 扩展。TENA/HLA/DIS 等协议必须经 Gateway→Canonical/World 接入；核心逻辑不依赖具体协议。

## 23. Assessment Profile、Qualification 与聚合

Profile 至少声明 training type、platform/scenario family、syllabus/standard、stage/event rules、World requirements、Metric versions、thresholds、critical gates、competency weights、minimum quality/confidence、missing policy、instructor policy、validity 和 publication rule。

Metric algorithm 产生物理/统计值；Profile 负责业务映射。阈值/Profile 变化通常升级 Profile；公式、eligibility、filter 或 measurement semantics 改变必须升级 Metric/Algorithm semantic contract。

Optional evidence 是否允许重归一化必须显式配置；mandatory 缺失不能被“权重重归一化”掩盖。

## 24. 教员评价、Annotation 与一致性

自动系统擅长时间、轨迹、状态、事件、数据一致性和可观察行为；教员更适合高阶意图、战术背景、不可观测判断、正确替代动作和根因确认。

Instructor Grade/Event Tag/Root-cause confirmation 与自动结果分开保存。Override 是 revision：保留原结果、修改人、时间、理由、rubric/Profile version。教员一致性可以使用 Cohen/Fleiss Kappa、固定类型 ICC、grade distribution 和 concordance trend，用于 rubric 标准化；不得把一致性指标简单变为教员排名。

## 25. 长期训练与能力体系

长期库不能只保存总分。至少保留 metric/competency/qualification、scenario/role/team composition、data/world capability、Context/Profile/Metric versions、objective result、TPAA chain coverage、TP/PA/AJ/team/chain process trends、significant events、instructor review，以及飞机/任务系统主体链。

### 25.1 人员与团队

支持 competency distribution、EWMA、trend slope、MAD/variance、P10/P50/P90、comparable cohort percentile、recent valid exposure、time since last valid training 和 decline/retraining evidence。团队趋势必须绑定成员构成。

### 25.2 飞机与任务系统

P1 observed trend 与 P2/P3 adjusted/estimate product 分层显示；维护、构型、软件、换件、校准等 lifecycle marker 可以分段趋势，但不自动构成因果证据。

### 25.3 场景可比性

Cohort 至少覆盖 model/block/configuration、training/episode/stage、scenario/mission/role/team size、difficulty/altitude/speed/range/load、weather/threat/EW、World Capability、Assessment/Metric/Attribution version。不可比较点不画成同一连续趋势。

### 25.4 知识时间与独立性

纵向解释区分按观察次数、日历时间或使用量；区分 event/valid time、record/revision time 和 information-available/as-of time。后补标签可以形成 retrospective revision，但不能冒充当时已知。记录数、Observation 数、独立 subject 数和有效证据量必须分别解释。

## 26. P2/P3 Aircraft Capability Intelligence

完整演进链为：

```text
P1 Observation
→ Factor Feature Set
→ Attribution Run
→ Context-adjusted Estimate
→ Capability Model / Surface
→ Aircraft Twin Revision
→ Reference-condition Longitudinal Estimate
→ Aircraft / Model Capability Profile
```

### 26.1 Attribution

输入包括 Observation、Human/Platform/Environment feature、reference condition、cohort、质量和独立性信息。输出允许 Human/Platform/Environment candidate effects、unexplained component、adjusted value、uncertainty 和 identifiability。不能把可加性或兼容代码直接画成 100% 因果占比。

### 26.2 Twin

Aircraft Twin 是单架飞机的已发布能力 read model：Identity + Configuration Timeline + Lifecycle/Maintenance/Calibration + Published Capability + Trend/Change Point + Confidence/Evidence。它不是实时飞参镜像，不是单次分数，也不作为同 Episode 的 W/M truth。

### 26.3 Model Profile

按 aircraft type/block/configuration/cohort 聚合 aircraft-level estimates，并同时报告 aircraft_count、episode/evidence counts、中心值、分布、percentile、trend、batch/config differences 和异常。禁止用大量 Episode 冒充大量独立飞机。

## 27. Debrief、Evidence 与数据产品

每个 Episode 的复盘产品应包含 Header、Context/World Capability/Version、Qualification/Safety/Objective、Competency/P1 Observations、Key Review Events、TPAA-M Chain、Attribution Candidate（若成熟度允许）、Evidence Package、Instructor Review 和 Longitudinal Context。

自动 Debrief Priority 综合 Safety、Objective Impact、Anomaly、Team Disagreement、Adjudication、Machine Degradation、Capability Change 与 Confidence；同时保留 Positive Event。点击事件应能同步 Timeline、轨迹、曲线、World/Action、Metric、媒体和 provenance。

Audio/Video/Transcript 与 Session Time 同步；Bookmark/Debrief Point 只保存可重放视图状态，不复制事实数据。

## 28. Course / Unit / Training-System Feedback

长期数据还用于评价训练体系本身，例如：某 competency 在多数人员中长期偏低、某 scenario failure 异常、某数据源持续退化、不同 rubric/instructor group 的系统性差异、训练前后观察变化等。

此类分析是组织/课程层反馈，不自动构成个人责任判断，也不把“观察到的训练前后差”称为因果训练收益，除非另有合格研究设计。

## 29. 总体架构与服务边界

逻辑层次：

1. Unified Input / Registry / Provenance；
2. Quality / Time / Entity；
3. Canonical Fact Store；
4. Context / Master Data；
5. Episode / Stage；
6. C+TPAA-M World Reconstruction；
7. Projection / Relation / Chain / Event；
8. Metric / P1 Observation；
9. Assessment / Longitudinal；
10. P2 Attribution / P3 Capability Intelligence；
11. P4/P5 Training Assessment；
12. Application/API / Debrief / Analytics / Visualization；
13. P6 Intelligence products（受 feature/maturity gate）；
14. Storage / Release / Audit / Governance。

禁止 Raw/Canonical 旁路到业务 Metric、Reference/Rule 写入 W、Truth 无证据替代 P、Internal Assessment 写入 J、Estimate 回流同 Episode M/Observation、Frontend 自行融合源数据或重算业务算法。

## 30. 用户界面总体要求

UI 以 Session/Episode/Stage/Scope/Subject/Time/Evidence 为骨架，而非以总分为唯一中心。P1 Aircraft/Mission-System、P4 Individual、P5 Team/Package、P2/P3 Capability Intelligence 和 P6 Forecast/Counterfactual 必须使用明确不同的页面语义与 maturity badge。

关键视图包括 Timeline、2D/3D trajectory、World/Action curves、Data Quality、Metric/Observation Detail、BVR Truth–Perception/Track、Team Shared Picture、Strike Route/Target/Designation、Evidence/Root-cause Candidate、Human/Team longitudinal、Capability Separation/Twin/Model Profile、Course/Unit analytics、Governance/Release。未实现/未验证 P 能力 不得在 UI 上看起来已经可用。

## 31. 外部接口、插件与集成边界

外部集成分为数据导入、Context/标准配置、外部裁决、媒体、互操作和结果导出。所有源格式由 Source Adapter 解释；Context Provider、World Reconstruction、Stage/Objectives、Event/Relation/Compliance、Metric、Assessment 等插件拥有明确语义边界。

新增课目通过 Training Plugin 组合现有 spine；不得让插件直接读取未登记文件路径、让 GUI 直接写数据库，或以外部协议对象绕过 Canonical/World identity。

## 32. 版本、历史重放与治理

Published Product 必须可回答所用 Catalog、Metric/Assessment/Attribution/Model Definition、Context revision/artifact、World products、Evidence、subject identity、configuration、build/compute version、input/logical hash 和 Release。

系统区分产品版本、DB schema、Core Baseline、Catalog、Metric/Stage/Profile、Context artifact、World policy、Attribution/Capability model、API、Build/SBOM。历史读取按 exact ID/version/hash；current/latest 只可用于用户导航，不得改变历史解释。

## 33. 验证与验收

验证分为：

- 技术正确性：时间同步、entity resolution、World/Stage/Event detector、Metric determinism、replay；
- 内容效度：训练/平台/航电/数据/教员专家确认能力域、观察资格、归因边界；
- Golden Dataset：四类训练及正常/边界/gap/clock/entity/P/J/M 缺失、构型切换、重复观察、不可识别等；
- 评分/教员一致性：algorithm-vs-instructor、instructor-vs-instructor、rubric version；
- 能力估计：data leakage、independence、identifiability、model validation、as-of lifecycle；
- UI：semantic separation、missing-data、traceability、multi-aircraft、instructor workflow；
- 运维/安全/性能：目标硬件 workload、安全策略、备份恢复、manifest/cold-start。

“设计合同冻结”“实现已验证”“预期用途已验证”是不同状态，任何文档通过不得冒充实现/适用用途已验证。

## 34. P 能力成熟度路线与总体验收

P1 当前拥有完整算法机器权威和工程合同；P2～P6 在 CB-1.4.0 中冻结扩展语义合同，后续实施不得重新发明对象边界。

P 能力成熟度顺序为：P1 observed-performance → P2 attribution/normalization → P3 capability model/twin → P4 individual/human-machine → P5 team/package/mission → P6 Joint/LVC + forecast/counterfactual。该顺序表达能力依赖，不表达项目日程；项目进度只使用 M0～M9。每个 P 能力层必须按 `CAPABILITY_PHASE_REGISTRY` 的 admission order 消费已发布上游产品，不通过回写上游“补齐”结果。

总体验收分为设计合同、实现合同、算法/Golden、数据治理、历史 replay、模型验证、工作负载/性能、发布配置和预期用途验证。只有相应证据闭合后，某一成熟度能力才可从 `DESIGN_CONTRACT_FROZEN` 升级为可部署/可使用状态。


## 35. Windows/Linux 跨平台运行与可移植性

TPAA 软件采用**一套源码/一套业务语义、多平台运行制品**。Windows 与 Linux 是当前强制支持的操作系统 family；Desktop、Local Backend、Worker、CLI 与 Service/API 的公共业务能力不得依赖单一 OS。生产环境可以指定推荐部署平台，但推荐平台不得演变为业务核心的平台绑定。

### 35.1 系统级跨平台原则

1. Canonical/Domain、C+TPAA-M reconstruction、Episode/Stage/Event/Relation、Metric Engine、Observation/Assessment、Longitudinal、P2~P6 产品逻辑和 Release/Replay 为 OS-neutral core；
2. 文件系统、进程/服务生命周期、文件锁与原子替换、临时目录、本地凭据、安装包、GPU/驱动/媒体编解码等差异通过 Platform Adapter 隔离；
3. PySide6 Desktop GUI 在 Windows/Linux 共享同一界面和业务投影代码，不建立长期并行的 Windows GUI 与 Linux GUI 产品线；
4. Source/Hardware Adapter 可因第三方驱动形成平台限制，但必须在 manifest 中声明支持 profile，并在不可用时显式降级/禁用；不得让该限制改变核心评价语义；
5. 路径、大小写、编码、locale/timezone、文件锁、process spawn、native dependency 等平台差异必须作为工程验收项，不得依靠开发者环境偶然成立。

### 35.2 跨平台逻辑等价

相同冻结 Input Artifact、Core Baseline、Catalog/Profile/Stage/Model、Context/World Policy 和依赖锁在 Windows 与 Linux 上执行时，应产生等价业务结果：

- stable ID、Episode/Stage 边界、Event/Relation 状态、reason code、Metric 状态/value kind、N_A/INSUFFICIENT_DATA、Qualification/Assessment 状态和 Release 逻辑成员必须精确一致；
- 数值结果使用同一算法版本和 Golden acceptance tolerance；若算法定义规定 quantization/rounding，则发布值在该规则后应精确一致；
- native package bytes、绝对本地路径、临时文件名、PID、非业务日志时间戳等允许不同，但不得进入业务 logical content hash。

### 35.3 支持与验收矩阵

正式基线至少认证 Windows Desktop、Linux Desktop、Windows Service 和 Linux Service 四类运行 profile。每次发布必须在 Windows/Linux CI 上执行 unit、contract、Golden、Replay、跨平台 logical-equivalence 比较，并对 Desktop GUI 与 Service/API 完成 clean-install/start/stop/upgrade/rollback smoke。

具体平台 profile、适配边界、CI/Packaging 规则和验收证据由 `canonical/PLATFORM_COMPATIBILITY_REGISTRY.json` 唯一控制，工程细节见 04 与 05H。


## 36. P / M / WS / Stage 项目语言治理

为避免“Phase/阶段”同时表示能力、开发进度和训练过程，本项目自 R3.2 起只保留以下四类受控语言：

- **P — Capability Phase / 能力成熟度**：P1～P6，只回答“系统可以发布/主张到什么能力层”。
- **M — Development Milestone / 项目里程碑**：M0～M9，只回答“软件项目开发到哪个可验收节点”。
- **WS — Engineering Workstream / 工程工作流**：`WS-*`，只回答“哪条横向工程工作流负责完成任务”。
- **Stage — Episode Stage / 训练过程 Stage**：只回答“一次 Training Episode 内当前处于哪个训练过程子区间/状态”。

四者正交。**M3 不等于 P3；P3 也不表示第三个开发里程碑。** 一个 P 能力可以跨多个 M 完成，一个 M 也可以同时推进多个 WS；Stage 与项目进度完全无关。

### 36.1 M0～M9 总体项目路线

```text
M0 Engineering Bootstrap
 → M1 P1 Minimum Vertical Slice
 → M2 P1 Basic Flight Complete
 → M3 P1 Four-Training-Type Complete
 → M4 P1 Longitudinal & Debrief Closure
 → M5 P1 Product Qualification & Release
 → M6 P2 Attribution Activation
 → M7 P3 Capability/Twin Activation
 → M8 P4/P5 Training Assessment Activation
 → M9 P6 Joint/LVC & Predictive Activation
```

M0～M5 主要用于把 P1 从工程骨架逐步做成正式产品；因此“开发到了 M3”绝不等于“系统进入 P3”。M6～M9 才分别对 P2～P6 执行受控准入。

### 36.2 WS 横向组织

工程任务必须标识所属 M 和 WS，例如 `M3 / WS-METRIC / BVR / TrackContinuity`。当前受控 WS 由 `ENGINEERING_WORKSTREAM_REGISTRY.json` 定义，涵盖 Core、Data、World、Metric、Observation、Longitudinal、Assessment、Capability、Storage、API、GUI、Test、Platform、Security、Performance、DevOps、Interop 与 Governance。

### 36.3 术语权威与迁移

`TERMINOLOGY_REGISTRY.json` 是术语唯一权威；`DEVELOPMENT_MILESTONE_REGISTRY.json` 定义 M；`ENGINEERING_WORKSTREAM_REGISTRY.json` 定义 WS；`CAPABILITY_PHASE_REGISTRY.json` 定义 P；`STAGE_REGISTRY.json` 定义 Stage。旧 1A～1G/1C/1D/1E 仅作为历史迁移标签保留，不再用于当前计划、Issue、文档章节或验收状态。
