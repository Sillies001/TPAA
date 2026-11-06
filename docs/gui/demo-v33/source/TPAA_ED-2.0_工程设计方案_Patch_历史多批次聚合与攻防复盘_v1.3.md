# TPAA ED-2.0 工程设计方案 Patch
## 历史批次聚合、训练类型元数据、Weapon Event Projection 与攻防复盘服务

**Patch ID：** EDP-WE-2026-01  
**版本：** 1.3（纳入 V33 KPI 子卡片真实高度约束、底部面板空间重分配及元素级几何验收；V1.2/V1.1 内容继续有效）  
**日期：** 2026-11-05  
**适用基线：** ED-2.0 / CB-1.4.0；实施时必须与当前 Canonical、DTO、数据库迁移和 GitHub 受控基线重新核对。  
**文档性质：** 工程设计补充；不自行创建第二套 Canonical Schema 或 DTO 定义。

**修订记录：** 1.1 / 2026-11-04：补充目标/防御方单机与编队差异化可视化复盘、事件窗口甘特图唯一归属、图表证据门禁及 Master Time Cursor 联动。  
**修订记录：** 1.2 / 2026-11-05：补充 V01 历史批次聚合 Read Model、批次训练类型元数据导入合同、任务级指标与装备趋势计算门禁、统一日期范围筛选和 V32 三行布局防重叠约束。  
**修订记录：** 1.3 / 2026-11-05：明确 KPI 卡片 65px 真实盒模型、68px 父网格行、V33 第三行 192px、元素级溢出检测，以及 1600×900/1280×720 几何回归。

---

## 1. 工程目标与边界

本 Patch 将总体方案新增的批次发射事件工作流落到可实施的工程边界，覆盖：

- 武器发射事件的识别、归类、Episode/Stage 关联和 Attack Cluster 关联；
- Shooter / Target 两侧的独立证据投影；
- Individual / Team 两种 Scope；
- 独立、可重叠的事件时间窗口；
- 批次事件查询、事件窗口查询和同步回放；
- 事件缺失、时间不确定、裁决未完成和窗口未闭合的 fail-closed 行为；
- V01 历史多批次聚合查询、任务级指标趋势和装备性能趋势摘要；
- 批次训练类型元数据、导入工作台登记和历史批次筛选；
- V01 与 V26 的批次明细路由边界及三行总览布局约束。

本 Patch 不直接修改数据库字段或宣称后端已实现。字段级对象、类型、nullable、枚举和 DTO 必须由 `canonical/CORE_LOGICAL_MODEL.json`、`canonical/CROSS_LAYER_DTO_CONTRACTS.json` 及其受控迁移拥有。

---

## 2. 现有工程基线对照

### 2.1 已具备的工程基础

ED-2.0 已经定义：

- Source → Canonical → Context → Episode/Stage 的数据流程；
- validated TimeTransform、Session Time、Alignment Domain、Analysis Series；
- C/W/P/A/J/M World 产品与 Event/Relation/TPAA-M Chain；
- Event owner/state machine 唯一，Metric/Assessment 引用已有 Event；
- Application Service 是 GUI/REST 唯一业务入口；
- Master Timeline、Observer/Actor 切换、同一时间游标联动；
- Event-window Lazy Load；
- 历史 Release、as-known replay 和 retrospective revision。

### 2.2 本 Patch 明确发现的工程缺口

当前 Canonical Logical Model 的主要持久化对象包括 Training Session、Training Episode、Episode Stage、World Product/Relation、TPAA-M Chain、Evidence、Release 等；在当前对象清单中没有一个语义明确、独立命名的 `weapon_event` 持久化表/对象。

因此实施时不得直接在 UI 或业务代码中私自创造第二套 Event Schema。必须先由架构/数据治理确定：

1. Weapon Event 是否作为 World/Event product 中的规范化 Event node 表达；或
2. 是否需要在 `CORE_LOGICAL_MODEL.json` 中增加受治理的 Event/Weapon Event 持久化对象；或
3. 是否使用现有 `world.world_relation` / `world.tpaa_m_chain` 及其 properties/refs 组合表达，并补齐稳定的事件身份和唯一 owner。

无论选择哪种方案，都必须同步更新 Canonical authority、DTO contracts、schema migration、mapping/validation、fixtures、traceability 和 independent validators。不得仅在本 Patch 文档中定义字段后就开始持久化。

---

## 3. 目标架构与服务职责

### 3.1 处理链

```text
Source Artifacts / Streams
        ↓
Source Adapter + Provenance
        ↓
Clock Segmentation + Validated TimeTransform
        ↓
Session Time / Alignment Domain / Analysis Series
        ↓
Canonical Facts + Context Bindings
        ↓
C / W / P_i / A_i / J / M_i World Products
        ↓
Episode / Stage Projection
        ↓
Weapon Event Detector / Event Owner
        ↓
Event Classification + Episode/Stage Link + Attack Cluster Relation
        ↓
Shooter / Target Perspective Evidence Projection
        ↓
Side-specific Event Window Resolver
        ↓
Batch Event Query / Debrief / Replay API
        ↓
GUI: Batch Overview → Category → Individual/Team → Perspective
```

GUI 不直接读取原始文件、Canonical 表或自行运行业务事件检测器；所有事件识别和窗口解析通过 Application Service / World/Event services 完成。

### 3.2 建议服务边界

| 服务/组件 | 职责 | 不允许承担的职责 |
|---|---|---|
| `WeaponEventDetector` | 从批准的 Action/authority events 识别每次实际发射/释放 | 不直接读取源文件并计算业务结论；不把一组齐射合并为一个 WE |
| `WeaponEventIdentityService` | 为每次发射提供稳定事件身份及来源 lineage | 不用时间近似匹配覆盖官方唯一 ID |
| `WeaponEventEpisodeLinker` | 将 WE 关联到现有 Training Episode/Stage | 不创建第二套 Stage taxonomy |
| `WeaponCategoryResolver` | 按版本化武器类型规则分类，使用几何辅助校验 | 不根据 UI 当前页或字符串标题推断类别 |
| `AttackClusterResolver` | 将同一齐射/相关发射建立 Cluster Relation | 不把 Cluster 当作 Episode 或 Weapon Event |
| `PerspectiveProjectionService` | 生成 shooter、target、individual、team 的证据投影；组装目标侧可视化 read model | 不将 W 替代 P_i；不将 team 结果复制到个人；不在投影层创造事实 |
| `TargetDefenseDebriefQueryService`（候选） | 查询目标侧几何、cue、响应、遥测、成员矩阵和关系图所需的受控投影 | 不负责事件识别/裁决；不伪造缺失轨迹、通信关系或遥测 |
| `EventWindowResolver` | 独立解析 T0-S/T0-T/T1/T2/T3 和窗口状态 | 不使用上一事件结束时间 + 固定采样间隔切片 |
| `EventRelationBuilder` | 连接 PRECEDES、RESPONDS_TO、AFFECTS、EVIDENCE_FOR、ASSOCIATED_WITH/HANDOFF 等关系 | 不输出未经确认的因果结论 |
| `BatchEventQueryService` | 提供批次、类别、飞机、架次、编队、红蓝方向和裁决状态筛选 | 不在前端聚合全部高频数据 |
| `ReplayContextService` | 将选定 WE、Perspective、Time Range、Media 和 World refs 绑定到回放 | 不更改事实时间戳或裁决 |

Event detector/state machine 必须有唯一 owner；Metric/Assessment 插件只消费已经发布的事件和关系，不得重复检测同一语义事件。

---

## 4. Weapon Event 处理流程

### 4.1 事件发现

1. 从批准的 ActionWorld/authority marker 中识别训练武器发射、投放、释放等动作。
2. 按每次实际武器动作建立独立 WE 候选。
3. 记录 source artifact、stream/row ordinal、mapping manifest、measurement semantics、authority source 和时间状态。
4. 使用稳定的 aircraft/entity/mission-system identity 解析射手和目标。
5. 无法确定射手、目标或武器类型时，保留候选状态并给出 reason code，不猜测。

### 4.2 Episode / Stage 关联

- WE 必须关联到一个已验证或明确标记为候选的 Training Episode。
- 关联 Stage 必须来自 `STAGE_REGISTRY.json` 的既有 Stage identity。
- 一个 Episode 可以关联多个 WE。
- 一个 WE 可以与其他 WE 共享同一 Episode、目标或 Attack Cluster。
- 如事件跨越多个 Session，必须通过明确的跨 Session 关系/对时依据处理；不得把不同 Session 的本地时间直接比较。

### 4.3 类别解析

`WeaponCategoryResolver` 使用版本化规则：

1. 主键：规范化 weapon type / training weapon identity。
2. 辅助输入：launch geometry、Episode type、Stage、Context objective。
3. 冲突：保留原分类候选并标记 `CLASSIFICATION_EXCEPTION`，进入人工复核。
4. 未知：`UNCLASSIFIED`。
5. 人工修改：保存原类别、修改后类别、操作者、时间、原因、规则版本和 supersession/revision。

### 4.4 Attack Cluster

- 同一齐射中每枚武器均保留独立 WE。
- Cluster 作为独立 Relation/Group identity 关联多个 WE。
- Cluster 关系不改变 WE 的独立发射时间、T2、T3 或裁决状态。
- Cluster 内不同武器可以有不同终止状态和结果。

---

## 5. 双视角 Projection 规则

### 5.1 Shooter Projection

输入：射手相关 C、W、P_shooter、A_shooter、J、M 及 Event/Relation/Chain。

输出应按来源分组：

- 发射前目标信息/航迹/识别/决策；
- 实际发射动作及武器状态；
- 支持/制导/通信/团队贡献；
- 结果和 J 关联；
- coverage/confidence/provenance/data quality。

### 5.2 Target/Defender Projection

输入：目标 observer 的 P_target、A_target、目标相关 W、J、M 和事件关系。

必须独立显示：

- 目标侧发射前状态上下文；
- 首次可获得威胁信息/cue/告警；
- 信息源及来源状态；
- 防御决策的可观察代理、动作、机动/模式/反制记录；
- cue-to-response（仅当两端时间和 eligibility 均存在）；
- 武器终止、正式裁决和目标状态证据。

不允许从 shooter 的发射时间直接推断 target 的告警时间；不允许从 W 的真值反推 target 的 P_i。

### 5.3 Team Projection

- Team scope 由 Context/编队关系确定。
- 每个成员的 P_i/A_i 独立保存和展示。
- Team Shared Picture 是成员信息的一致/差异投影，不替代各成员 P_i。
- 任务分工、通信、handoff、成员动作、队形/间隔和团队结果分别显示。
- Team assessment 不等于成员分数平均。

### 5.4 Strike Projection

Strike 页面只提供 shooter perspective。目标相关信息、designation、target effect 和 approved J 作为 shooter-side attack process evidence。

若后续需要地面防空单元的目标侧评价，新增独立的防空单元 assessment scope/contract，不复用空战 target defender projection。

### 5.5 Target/Defender Visual Debrief Projection

本节定义目标/防御方视角的可视化 read model。它是现有 `PerspectiveProjectionService` 的展示投影，不是新的事实权威，也不新增一套平行 Event/Metric/Assessment 数据模型。可以由同一服务的子投影或受控 query service 组装。

**单机投影候选结构**：

- `TargetThreatGeometryProjection`：目标实体、时间游标、目标轨迹引用、来袭方位/相对几何、武器/射手关联、单位、对时状态、geometry availability/reason、source refs。只有位置/方位/时间对齐全部满足时才返回可绘制的真实几何；否则返回 `UNAVAILABLE`/`SCHEMATIC_ONLY` 和 reason code。
- `TargetThreatCueProjection`：observer identity、cue/alert event refs、source type（onboard/TDL/shared/fused/inferred）、observed_at、valid_time、source ref、quality/coverage、是否可作为 P_i。不同来源不得被 UI 合并成一个无来源的“已感知”。
- `TargetResponseProjection`：actor identity、observable action refs、机动/模式/反制等实际记录、observed_at、validity、source refs；cue-to-response 只在两端时间可比且 eligibility 通过时提供 duration。
- `TargetStateSeriesProjection`：可用的目标侧遥测序列及 unit、time base、coverage、gaps、source/provenance。UI 仅绘制存在的 series，不生成默认曲线填补缺失。
- `TargetOutcomeEvidenceProjection`：weapon terminal、approved J、target state/effect、observation closure 和 evidence completeness 分开提供。

**编队投影候选结构**：

- `TeamDefenseFormationProjection`：有效时刻的 Team Context、成员 ID、受威胁成员、成员关系有效区间、成员位置/轨迹可用性。真实位置缺失时只返回关系图所需拓扑，不伪造坐标。
- `TeamMemberThreatResponseProjection`：按成员分别返回 P_i cue、来源、时间、A_i action、时间差和 coverage；禁止用 team fused picture 填补成员个人观察。
- `TeamDefenseEventTimelineProjection`：按成员列出离散 cue/action 事件点，返回时间基准和可点击 event refs；不将每个成员的完整窗口压缩成互斥区间。
- `TeamInformationRelationProjection`：只从已验证的 communication/TDL/World Relation 生成共享关系边，包含 source member、recipient member、message/event ref、observed_at、relation type 和 provenance。缺少证据时不创建边。
- `TeamDefenseOutcomeProjection`：成员层与团队层分别提供结果/证据覆盖，不将个人裁决复制为团队裁决。

候选 DTO 名称仅作为逻辑 read model，最终字段必须经 `CROSS_LAYER_DTO_CONTRACTS.json` 和 Canonical authority 审批。

**可视化与交互规则**：

1. WVR 单机优先呈现近距目标相对态势、目标侧可获得告警、目标状态变化和防御动作；BVR 单机优先呈现远距威胁来源、信息更新时间、告警/响应顺序及目标遥测变化。具体图层由证据可用性决定。
2. WVR/BVR 编队优先呈现成员关系、被攻击成员、成员 P_i/A_i 差异、离散成员动作时序及有证据的信息共享关系。编队态势图与信息共享图必须区分 Context 成员关系和通信/信息共享关系。
3. 目标页关键事件点和成员选择驱动同一 Master Time Cursor/Observer/Actor context；相关地图、曲线、成员矩阵和回放媒体同步定位。
4. 事件时间窗口页面是 T0-S/T0-T/T1/T2/T3 多轨甘特图的唯一权威 GUI 展示位置。目标页不复制同一甘特图；目标页可提供打开事件窗口的入口。
5. 每个图表必须带图例、单位、时间基准、来源/证据入口和质量状态。Demo 的合成数据需标注示意；生产 UI 不得使用合成/默认值伪装真实测量。
6. 页面应能表达 `UNAVAILABLE`、`SCHEMATIC_ONLY`、`PARTIAL_COVERAGE`、`UNRESOLVED_ALIGNMENT` 等状态；缺失几何、缺失 cue/action 或缺失成员关系不得以视觉插值补齐。

---

## 6. Event Window Resolver 规范

### 6.1 输出时间锚点

建议 EventWindowProjection（字段名为候选概念，正式字段以 Canonical/DTO authority 为准）至少表达：

| 逻辑项 | 语义 |
|---|---|
| `shooter_window_start` | T0-S，射手侧最早关联前置证据/上下文起点 |
| `target_window_start` | T0-T，目标侧最早相关状态上下文起点；不等于首次 cue |
| `launch_time` | T1，实际发射动作的 Session Time |
| `weapon_terminal_time` | T2，权威武器终止时刻，可为空 |
| `result_observation_end` | T3，结果观察窗口结束，可为空 |
| `target_first_cue_time` | 目标侧首次可获得威胁信息/告警时刻，可为空 |
| `target_first_response_time` | 目标侧首次可观察响应时刻，可为空 |
| `adjudication_time` | J 的正式裁决时间，可晚于 T2/T3 |
| `data_coverage_end` | 当前数据覆盖边界，不代表实际事件终止 |
| `window_status` | CLOSED / PARTIAL / OPEN / UNRESOLVED / INVALID 等受控状态 |
| `time_alignment_refs` | TimeTransform、Alignment Domain、Analysis Series 和 provenance 引用 |

### 6.2 窗口解析算法

1. 读取 WE 的实际发射锚点 T1。
2. 在相同 Session/Alignment Domain 和适用 Episode/Stage 中，查找与本次 WE 存在明确 Relation/Evidence 关联的射手侧前置证据，确定 T0-S。
3. 独立查找目标侧用于重建威胁前状态的上下文证据，确定 T0-T；首次 cue/告警作为另一个 marker。
4. 从权威武器状态/终止事件解析 T2；无权威记录则保持 unknown。
5. 根据 Context-defined observation policy、结果证据和数据覆盖情况解析 T3；若只有数据覆盖截止，只能标记 `DATA_COVERAGE_END`，不得标记事件已终止。
6. J 的裁决时间单独关联，不强制作为 T3。
7. 输出每侧窗口 coverage、confidence、source refs、alignment status、reason code 和 detector/policy version。

### 6.3 区间与重叠

- 所有时间窗口采用半开区间 `[start,end)`。
- 不同 WE 窗口允许重叠。
- 不以 `previous_event.end + sample_interval` 推导下一事件起点。
- 同一原始数据片段可被多个 EventWindowProjection 引用，但底层原始事实只存储一次。
- 如窗口跨越 clock reset、Alignment Domain、Analysis Series 或 authority boundary，必须保留分段/断点信息，不得合并成看似连续的窗口。

### 6.4 事件状态分离

至少独立表达：

| 维度 | 示例状态 |
|---|---|
| Weapon terminal | TERMINAL_OBSERVED / TERMINAL_UNKNOWN |
| Adjudication | ADJUDICATED / PENDING / UNAVAILABLE / NOT_APPLICABLE |
| Observation window | CLOSED / PARTIAL / OPEN |
| Time alignment | RESOLVED / EXTRAPOLATED / UNRESOLVED / INVALID |
| Classification | CLASSIFIED / CLASSIFICATION_EXCEPTION / UNCLASSIFIED |

不得用单个 `status` 混合上述不同含义。

---

## 7. 数据模型、DTO 与 API 变更治理

### 7.1 Canonical 变更前置条件

在生产实现前，先对当前 `CORE_LOGICAL_MODEL.json` 做一次对象级核对，明确 WE 的持久化方式：

- 若 Event 是 World product 中的受控 Event node，则定义稳定 ID、唯一 owner/state machine、episode/stage refs、event type、time anchors、relations 和 provenance 的权威位置；
- 若需要独立持久化对象，则新增 schema migration 和 Canonical authority 版本，不得在 05 分册中先行“影子定义”；
- Attack Cluster、Perspective Projection、Event Window 若为派生对象，优先采用 immutable/derived projection，不在没有必要时复制事实。

### 7.2 DTO 候选

建议在 `CROSS_LAYER_DTO_CONTRACTS.json` 更新评审中考虑以下逻辑投影（不是当前已生效字段合同）：

- `BatchEventSummaryDTO`：批次事件清单和类别统计；
- `WeaponEventDetailDTO`：单个 WE 的射手、目标、Episode、Stage、Cluster、分类和裁决引用；
- `WeaponEventPerspectiveDTO`：SHOOTER / TARGET、INDIVIDUAL / TEAM 的证据投影；
- `WeaponEventWindowDTO`：T0-S/T0-T/T1/T2/T3、首次 cue/response、窗口状态、coverage、confidence、alignment/provenance；
- `EpisodeEventRelationDTO`：一个 Episode 下的 WE 与 Cluster 关系。

所有 Session Time 在 JS 可见 API 中按现有 transport rule 使用 decimal-string；DTO 字段必须经 Canonical authority 审批。

### 7.3 Application API（逻辑资源建议）

具体 REST 路径和字段由 05F / DTO authority 定义；逻辑上需要支持：

- 批次工作集内事件列表与筛选；
- 某个 Episode 的所有 WE；
- 某个 WE 的 shooter/target projection；
- 某个 WE 的 Individual/Team projection；
- 某个 WE 的 side-specific window 和相关事件；
- 同一 WE 的 replay context；
- 分类例外、人工复核和版本化修订。

GUI 不直接查询 DB，不从 UI state 反向创造 DTO。

---

## 8. GUI 与状态联动

### 8.1 共享选择状态

在 05G 既有 shared state 基础上，至少需要明确：

- selected batch workset；
- selected Session / Context / Release；
- selected Episode / Stage；
- selected Weapon Event；
- selected Attack Cluster；
- selected Scope（Individual/Team）；
- selected Perspective（Shooter/Target）；
- selected Observer / Actor / Team；
- selected Time / Time Range；
- selected Event Window / Evidence refs；
- playback state。

### 8.2 页面行为

- V05、V20、V04、V08：显示射手/目标防御方切换；切换后整页主体、图表、时间线、统计、证据和解释同步变化。
- V06、V21：隐藏目标/防御方切换，固定射手视角。
- 六个页面保留同类 WE 选择器。
- 从批次总览下钻时传递 WE ID、Scope 和默认 Perspective。
- 页面内切换 WE 时保留当前页面与 Scope，重新载入对应事件的投影和窗口。
- 返回批次总览时保留原筛选上下文和选中事件。
- 事件窗口详情采用按需加载，不一次加载整个批次的高频数据。
- V05/V04 目标单机页面使用“目标侧态势图 + 威胁信息来源卡 + 离散关键事件链 + 目标遥测/动作曲线 + 结果证据条”。WVR/BVR 的信息来源和分析重点不同，但遵循相同证据边界。
- V20/V08 目标编队页面使用“编队成员关系图 + 成员 P_i/A_i 矩阵 + 成员离散动作时序 + 信息共享关系图 + 团队/成员结果证据”。
- 目标页不显示事件窗口多轨甘特图；只保留打开独立事件时间窗口的入口。窗口页继续负责 T0-S/T0-T/T1/T2/T3 区间、重叠和 coverage boundary。
- 关键事件点点击后更新 Master Time Cursor；编队成员点击后联动成员矩阵、动作时序、关系图和相关媒体。
- 真实几何必须依赖已对时的轨迹/位置数据；缺少时使用明确的不可用状态或不按比例的关系示意。真实遥测曲线只绘制存在的数据 series。

### 8.3 Replay

Replay 以选定 WE 的 T0-S/T0-T/T1/T2/T3 及当前 Perspective 作为初始范围；时间游标仍使用同一 Master Time Cursor 联动地图、轨迹、曲线、Track、TDL、事件、媒体和 J markers。

切换 Observer 只切换 P_i；切换 Actor 只切换 A_i；W 和 Session Time 保持一致。

---

## 9. 数据充分度与 Fail-Closed

- 缺少射手侧前置证据：T0-S 标记未解析/回退窗口，不伪造首次探测时间。
- 缺少目标侧 P_i：目标侧告警/感知结论显示 unavailable，不用 W 替代。
- 缺少目标侧 A_i：不推断防御动作，不计算响应时间。
- 缺少 J：只报告 observed action/attempt，Outcome = N/A / unavailable。
- 缺少 T2：武器终止状态 unknown，窗口不能标记为已按武器终止闭合。
- 只有数据覆盖截止：标记 data coverage boundary，不当作实际事件结束。
- TimeTransform 未解决：不得发布正式统一时间窗口。
- 事件归类冲突：保留分类例外并要求复核。
- 多机实体身份不确定：显示 unresolved identity，不按临时 Track ID 建立稳定飞机主体。

---

## 10. Golden Fixture / 验收测试

### 10.1 Event identity 与 grouping

1. 一次发射生成一个 WE。
2. 同一齐射两枚武器生成两个 WE、一个 Attack Cluster。
3. 一个 Episode 包含多次 WE。
4. 一个 Episode 内的 WE 可以时间交错。
5. 不同 Session 的事件不经批准对时不能直接建立统一时间关系。

### 10.2 时间窗口

1. 两个 WE 的窗口重叠，均完整保留。
2. WE-002 的前置探测早于 WE-001 终止，不被切掉。
3. T2 已知、J 未知：显示 terminal observed / adjudication pending。
4. T2 未知、数据覆盖结束：显示 terminal unknown / window open。
5. J 时间晚于 T2/T3：仍可关联，不回写物理终止时间。
6. 目标首次 cue 晚于 T0-T：保留 cue 前目标状态上下文。
7. Clock reset / gap / Series boundary：不跨断点伪造连续窗口。
8. UNRESOLVED TimeTransform：只保留诊断信息，不发布正式统一窗口。

### 10.3 Perspective

1. WVR/BVR 单机射手与目标视角内容不同。
2. WVR/BVR 编队目标视角显示各成员 P_i/A_i，而非单一融合态势。
3. 无目标侧 P_i 时明确显示 unavailable。
4. 无目标侧 A_i 时不生成防御响应时间。
5. Strike 页面无目标/防御方切换。
6. Strike 无 J 时不推断命中/任务成功。
7. V05/V04 目标单机页有独立的几何、威胁信息、离散事件链、遥测曲线和结果证据组件；页面内不存在重复的 Event Window Gantt。
8. V20/V08 目标编队页有成员关系图、成员 P_i/A_i 矩阵、成员离散动作时序和有证据的信息共享图。
9. 目标侧真实几何缺少对时/位置证据时显示不可用/示意状态，不产生真实距离或方位数值。
10. 缺少目标遥测 series 时不绘制默认趋势线；缺少通信证据时不绘制信息共享关系边。
11. 点击关键事件点或成员后，Master Time Cursor 和相关目标侧图表/回放上下文同步更新。
12. 深色/石墨/浅色主题及 1600×900、1280×720 下目标侧可视化不遮挡、不横向溢出。

### 10.4 GUI 与回放

1. 从批次事件列表进入后 WE ID、Episode、Cluster、Scope、Perspective 一致。
2. 页面内切换 WE 后页面和 Scope 保持，事件上下文更新。
3. 事件窗口打开/关闭、相关 Episode 事件切换、返回批次总览正常。
4. Master Time Cursor 同步所有视图。
5. Event-window Lazy Load 只加载所选事件的高频窗口。
6. 1600×900、1280×720、800px 和移动窄屏布局不发生遮挡。
7. 深色、浅色、暗色战术三主题均可读。

---

## 11. 生产实现的变更闭包

在正式工程中，以下变更必须在同一个受控设计/实现批次内闭合：

1. Canonical object/field authority（如需新增）；
2. DTO contracts；
3. Event/Relation owner 与 state machine；
4. Weapon type classification rule registry/context artifact；
5. Event Window resolver 和其版本/状态语义；
6. Application Service / API；
7. Storage migration（如需要）与 backfill/replay policy；
8. Golden fixtures、property tests、cross-platform determinism；
9. Release/provenance/traceability；
10. GUI view projection、event selector、window lazy load 和 synchronized replay；
11. Target/Defender visual read model、geometry/series evidence gates、event-window Gantt 唯一归属及 cursor/member cross-highlighting；
11. Documentation/authority manifests/validators。

不允许只完成 GUI 外观，就宣称真实事件自动识别、真实时间窗口截取或真实攻防证据已实现。

---

## 12. 工程设计方案需要补充/修订的位置

| 原分册 | Patch 动作 | 补充内容 |
|---|---|---|
| 04 工程公共基线 | 补充 | Weapon Event 唯一 owner、terminal/result/window/time alignment 状态分离 |
| 05A Canonical/Context/Episode | 补充 | Episode 与多 WE 关系；批次工作集与 Session 边界；时间窗口派生产品 |
| 05B World/Event/Relation | 补充 | Weapon Event node、Attack Cluster、双侧 observer/actor relation、事件窗口解析输入 |
| 05E Storage/Release/Replay | 补充 | Event Window immutable/projection provenance、窗口重叠、as-known/revision replay |
| 05F Application/API/DTO | 补充 | BatchEvent、WeaponEvent、Perspective、Window、EpisodeEvent relation 查询/命令 |
| 05G GUI | 补充 | 双视角页面主体切换、单机/编队目标侧差异化可视化、事件窗口甘特图唯一归属、Master Time Cursor 联动、成员跨面板高亮 |
| 05I Human/Team/Mission | 补充 | 目标侧 Team 防御证据、每成员 P_i/A_i、来袭事件责任关系及信息共享边的证据来源 |
| Canonical/Validators | 评审后更新 | Event persistence authority、DTO、migration、Golden fixture 和 validators |
| 05A/05E/05F/05G V01 | 补充 | 历史批次聚合 Read Model、统一日期/机型/训练类型筛选、指标趋势与数据资格投影 |
| Import Application Service / Batch Metadata | 补充 | 显式训练类型登记、持久化、审计、导入队列状态和未分类处理 |
| 05G V01 GUI | 补充 | 三行面板顺序、10px 间距、底部面板缩减、内部滚动和无重叠回归 |

---

## 13. 依据文件

- `04_ED-2.0_工程设计公共基线.md`：Core Rules、time/provenance/scope/replay invariants。
- `05A_数据_Canonical_Context_Episode设计分册.md`：Time Alignment、Episode Detector、Stage Projector、Data Sufficiency。
- `05B_World_Stage_Event_Relation设计分册.md`：World reconstruction、Event/Relation、TPAA-M Chain、唯一 event owner。
- `05E_Storage_Release_Replay设计分册.md`：Historical Replay、immutable Release、as-known/retrospective revision。
- `05F_Application_API_DTO设计分册.md`：Application Service / DTO authority / Query-Command boundary。
- `05G_可视化_GUI设计分册.md`：Master Timeline、Observer/Actor 联动、Event-window Lazy Load。
- `05I_训练效果_Human_Team_Mission_Joint设计分册.md`：Individual/Team scope、Event Responsibility、Team composition 和成员 P_i/A_i。
- `canonical/CORE_LOGICAL_MODEL.json`、`canonical/CROSS_LAYER_DTO_CONTRACTS.json`、`canonical/CORE_RULES.json`、`canonical/STAGE_REGISTRY.json`。


---

## 14. V01 历史多批次综合总览工程设计

### 14.1 工程目标与边界

V01 应由跨批次聚合 Read Model 驱动，不得通过前端拼接各页面当前状态或把一个批次的事件明细复制到其他批次。V01 是历史统计查询入口；V26 仍是单个批次的 Weapon Event 工作台。

本节给出的服务/DTO 名称均为**候选逻辑名称**，用于表达职责，不构成 Canonical 或跨层 DTO 的新增权威定义。最终名称、字段和类型必须由现行 `CORE_LOGICAL_MODEL.json`、`CROSS_LAYER_DTO_CONTRACTS.json` 及其 authority registry 审核批准。

### 14.2 数据来源与聚合 Read Model

V01 的数据必须来自以下既有权威数据域/产品：

| 数据域 | V01 用途 | 工程约束 |
|---|---|---|
| Batch / Batch Context | 批次身份、批次日期、训练类型 | 使用稳定 Batch ID；训练类型为批次级元数据 |
| Session / Sortie | 批次包含的 Session 和飞行架次 | 按稳定 ID 去重；保留 Session 边界 |
| Episode / Stage | 交战过程数量和关联 | 不以 WE 数代替 Episode 数 |
| Weapon Event / Event / Relation | 发射事件数量和行为类别构成 | 每个独立 WE 计一次；Attack Cluster 独立统计 |
| Approved Adjudication J | 击杀、损失、结果和任务达成输入 | 未批准/缺失裁决不进入正式结果 |
| Data Qualification / Evidence | 数据资格、覆盖率和来源摘要 | 资格状态必须保留 reason code 和 provenance |
| Aircraft / Model / Configuration | 机型筛选和装备趋势分组 | 不可比构型不得混合 |
| Metric / Analysis Series | 任务级和装备性能趋势 | 使用批准的指标定义、版本、单位和输入绑定 |

候选 Read Model 可由 `HistoricalTrainingOverview`、`BatchOverviewSummary`、`TaskMetricTrendPoint`、`EquipmentMetricTrendPoint` 等逻辑产品组成；其字段必须经 DTO 权威审查，禁止 GUI 自行定义第二套数据事实。

### 14.3 查询合同

候选查询输入至少包括：

- `start_date`、`end_date`：用户指定的日期范围；
- `aircraft_model_ids` 或受控机型筛选；
- `batch_training_type`：简单对抗、混合对抗、综合对抗或全部；
- `evaluation_side`：被评估方/视角上下文（如任务级指标依赖该上下文）；
- `release_id` / `context_id` / policy version：保证历史可重现性。

所有 V01 面板必须复用同一查询上下文和同一批次集合。不能出现 KPI 使用一组批次、趋势图使用另一组批次、列表又使用第三组批次的情况。

日期筛选应以批次权威日期和项目规定的时区策略解释。起止日期在界面层按用户选定日期包含两端；内部可转换为明确的半开区间，但必须固定时区和转换规则。跨 Session 的原始时间不得因日期筛选而被直接拼接。

### 14.4 计数与聚合规则

- 批次数：按 Batch ID 去重。
- 架次数：按 Sortie ID 去重；同一架次被多个数据源引用不得重复计数。
- Episode 数：按 Episode ID 去重。
- WE 数：按 Weapon Event ID 去重；多枚齐射按多 WE 计数。
- 已裁决事件数：仅统计达到批准裁决状态的 WE/结果对象，并遵循裁决对象的实际基数。
- 数据资格通过批次数：按批次资格产品及版本统计，不得仅按文件导入成功状态统计。
- 行为类别构成：按 WE 的受控类别映射统计；未知/冲突分类必须另列，不得静默归入 WVR/BVR/Strike。
- 所有聚合必须保留过滤条件、数据版本、来源和统计截止时间。

### 14.5 任务级指标计算服务

击杀比、敌我交换比和任务达成率不得在浏览器中直接根据原始事件标签计算。生产计算必须由指标服务/批准的 Metric Definition 执行。

工程要求：

1. 每个指标定义必须提供 numerator、denominator、Scope、被评估方、时间范围、数据源、J 状态、Metric Definition Version 和资格条件。
2. 击杀和损失只使用批准裁决或批准任务结果；不能将武器终止状态、传感器观察或 Demo 标签直接升级为官方击杀。
3. 敌我交换比明确“敌方确认损失 / 被评估方确认损失”的方向；评估方变化必须触发归属重算。
4. 任务达成率从任务目标清单与正式目标状态计算，不得以击杀数代替目标完成数。
5. denominator 为 0 时返回 null/unavailable 和 reason code，不返回 Infinity、NaN 或伪零值。
6. 关键来源缺失、裁决待定或覆盖不足时返回 pending/unavailable，并保留质量状态。
7. 跨批次汇总时，只有 Metric Definition、单位、Scope 和资格条件一致的指标才可聚合；比值应由汇总后的分子/分母重新计算，不得简单平均各批次比值。
8. GUI 应显示指标名称、单位/轴、口径说明、样本批次数和演示/正式状态。

### 14.6 批次训练类型与导入工作台

批次训练类型采用受控值：简单对抗、混合对抗、综合对抗。它是 Batch Metadata，不是 Weapon Event Category，也不替代 Episode/Stage 的训练科目域。

导入流程至少包括：

1. 用户选择待导入数据并建立 Batch Registration。
2. 用户显式确认批次训练类型。
3. 校验类型值、批次日期、批次身份和关联 Context。
4. 导入队列展示训练类型和登记状态。
5. 提交后通过 Application Service 持久化批次元数据及审计信息。
6. 解析和数据资格流程完成后，V01 才能将正式数据纳入相应统计。
7. 导入失败或类型缺失时保留失败/待分类状态，不自动赋予“综合对抗”。

Demo 中当前训练类型保存在 JavaScript 运行时状态并模拟导入队列；生产系统必须通过后端/持久化服务完成，不能以页面状态作为数据事实。

### 14.7 装备性能趋势 Read Model

V01 的装备趋势属于跨批次摘要，不替代 V10～V16 专项分析。趋势数据至少绑定：

- Metric Definition ID / Version；
- 机型、机体/构型及必要的环境条件；
- 单位、时间基准和统计方法；
- 样本数量、覆盖率、数据资格和异常/缺失状态；
- Release / Context / 数据来源。

不同版本公式、单位或不可比构型的数据不得放在同一条连续趋势线上。只有当前筛选条件下存在合格样本时才绘制趋势；否则显示无可比数据。

### 14.8 历史批次索引与详细复盘路由

批次列表的每个条目必须绑定准确 Batch ID 和 Release/Context。点击批次只更新选中摘要；只有批次已加载可用的 Weapon Event 明细、数据资格满足路由条件时，才允许进入 V26。

V26 的路由上下文至少包含 Batch ID、Session refs、Release/Context、当前 WE ID、行为类别、Scope、Perspective 和筛选状态。不得在无明细批次上复用当前演示批次的 WE 列表。

### 14.9 V33 GUI 布局工程约束

V32 的根因是 KPI 子卡片的内容轨道、内边距和边框合计约 65px，而父网格行只有 55px。子卡片溢出父行并侵占 gap。V33 必须同时约束父行和子卡片，不能只设置父容器 gap。

- V01 外层网格使用 10px 行列间距；
- 网格行定义为 `36px / 68px / 168px / 168px / minmax(180px, 1fr) / 12px`；
- KPI 子卡片使用 `box-sizing:border-box`、`height=65px`、`min-height=65px`、`align-self:center`，且所有卡片边界必须位于 KPI 父行内部；
- 第一行和第二行趋势面板各 168px；
- 第三行在 1600×900 参考画布下实际 192px，较 V32 的 205px 减少 13px；
- 历史批次列表在第三行内部滚动，不允许扩大面板并覆盖第二行；
- 选中批次摘要在 1600×900 和 1280×720 下均不得发生内容裁切或溢出；
- KPI 卡片真实边框至第一行趋势面板必须有可见间隔；验收测量卡片自身 bounding box，而非只测 KPI 父容器；
- 所有布局高度按外层容器统一分配，不允许面板使用脱离网格流的绝对定位覆盖相邻行；
- 在 1600×900、1280×720 和三种主题下执行截图、子元素盒模型、行间距、内部滚动及边界相交检查。

### 14.10 V01 测试与验收

至少包括：

1. 同一查询条件下 KPI、趋势图和批次列表的 Batch ID 集合一致。
2. 日期起止边界、反向日期、空结果和时区边界测试。
3. 三种批次训练类型筛选及导入登记回写测试。
4. 批次训练类型不改变单个 WE 的 WVR/BVR/Strike 分类。
5. Episode、WE、Attack Cluster 计数基数与去重测试。
6. 无 J、未裁决、零分母和数据资格不足时的指标 fail-closed 测试。
7. 比值跨批次聚合使用分子/分母重算，不做简单平均。
8. 不可比装备指标版本、单位或构型不进入同一趋势序列。
9. 汇总批次不能进入其他批次的逐事件明细。
10. V33 KPI 卡片真实盒模型、68px 父行、65px 子卡片、192px 底行、元素级 10px 间距、内部滚动及三主题/双分辨率几何回归测试。
11. V01 改动不得影响 V04～V21、V23、V26 等既有页面的路由和主体内容。

---

## 15. 工程变更闭包与生产化门禁补充

V01 生产化必须与既有数据权威体系闭合，至少包括：

1. Batch Metadata / Training Type 的 Canonical authority 决策（如当前对象尚未覆盖）；
2. 导入 Application Service、DTO 和审计合同；
3. 历史批次聚合 Query Service / Read Model；
4. 任务级指标定义、批准裁决输入和 numerator/denominator 处理；
5. 装备指标定义版本、机型/构型可比性与数据资格；
6. 日期/时区/跨 Session 聚合规则；
7. V01 与 V26 的准确 Batch/Release/Context 导航合同；
8. Golden fixtures、零分母、缺失裁决、批次去重和跨批次聚合测试；
9. GUI 布局、主题、分辨率和无重叠回归；
10. 文档、authority manifest、validators 和 traceability 更新。

本 Patch 不表示上述后端能力已在当前 HTML Demo 中实现。Demo 的前端交互通过，只能证明信息架构和交互表达，不构成真实数据解析、持久化或正式指标计算验收。
