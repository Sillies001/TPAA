# TPAA V8.0 总体设计与 ED-2.0 工程设计 Patch 差距清单

**对应 Patch：** ODP-WE-2026-01 v1.3 / EDP-WE-2026-01 v1.3
**修订记录：** 2026-11-04，增加目标/防御方可视化复盘的信息架构、read model、甘特图去重及数据真实性门禁差距。  
**修订记录：** 2026-11-05，增加 V01 历史多批次训练总览、批次训练类型元数据、任务级指标趋势、日期范围筛选、装备趋势 Read Model 及 V32 布局防重叠差距。  
**修订记录：** 2026-11-05，增加 V32 KPI 卡片盒模型溢出根因、V33 父子尺寸约束、底部面板二次压缩和双分辨率元素级验收。  
**基线：** 资料库中的 TPAA V8.0 总体方案、03A、ED-2.0 04/05A–05J 及 Canonical artifacts。  
**说明：** 本清单区分“原方案已经有原则/组件”和“原方案没有把本次需求细化成可实施规则”。不能把已有的 Event Graph、Master Timeline、P_i/A_i、Event-window Lazy Load 等说成原方案完全没有考虑。

---

## 1. 原方案已经覆盖的内容

| 主题 | 原方案已有设计 | 本 Patch 的处理 |
|---|---|---|
| Session / Episode / Stage | Episode 是训练评价语义单元，Stage 是版本化子对象，四类训练有参考 Stage Profile | 保留，不新建第二套 Episode/Stage |
| Event / Relation / Chain | 有 Event Graph、PRECEDES、RESPONDS_TO、AFFECTS、EVIDENCE_FOR、CANDIDATE_CAUSE 等关系；Event owner/state machine 唯一 | 将 Weapon Event 和 Attack Cluster 落到现有 Event/Relation 主干 |
| W/P/A/J/M | 已定义 Truth、observer-specific P_i、actor-specific A_i、approved J、M_i | 用相同边界分别构造射手和目标侧投影 |
| WVR/BVR/Strike | 已有完整四类训练评价方法、Stage、指标和结果边界 | 不重做专项页面主体，只补充双视角和事件导航 |
| Individual / Team / Package | 已有不同 Scope、Team shared picture、task/role/communication、team composition | 为目标侧编队防御补齐可视化投影 |
| Master Timeline | 已有多轨时间轴、点击事件、刷选、缩放、同步媒体和轨迹 | 增加 WE 双侧窗口和重叠窗口显示 |
| Event-window Lazy Load | 05G 已明确默认加载摘要，进入秒级事件再加载高频数据 | 补充窗口边界、side-specific resolver 和缓存/查询契约 |
| Historical Replay | 已有 immutable Release、as-known 与 retrospective revision | 确保 WE/窗口/关系引用绑定历史 Release/Context/Policy |
| 数据质量和缺失 | 已有 Data Sufficiency、coverage/confidence、Missing Is Not Zero、缺失 J 不推断官方结果 | 增加 T0/T2/T3 缺失和窗口状态的专门 reason code |
| 目标侧可视化复盘 | 已有 Master Timeline、BVR Perceived World、Team Shared Picture、Observer/Actor 语义 | 补充目标侧态势图、威胁来源可视化、离散事件链、目标遥测曲线、成员矩阵/泳道/信息共享关系图；明确与事件窗口甘特图分工 |

---

## 2. 总体设计方案中没有明确细化的内容

以下不是说原方案没有相关概念，而是缺少面向“混合批次 + 每次发射 + 攻防双视角”的明确产品规则。

| 编号 | 未明确/不足之处 | 需要补充的内容 | 影响 |
|---|---|---|---|
| O-GAP-01 | 没有把批次发射事件设为混合对抗演习的统一导航入口 | Batch Workset → 全批次 WE 时间线 → WVR/BVR/Strike → 单机/编队 → 单次 WE | 混合科目下反复切页，事件定位不连续 |
| O-GAP-02 | “一次发射”没有明确作为独立复盘对象 | 每枚实际发射武器一个 WE ID；齐射每枚独立 | 多弹齐射被错误合并，事件数和结果失真 |
| O-GAP-03 | 没有明确区分 Training Episode、Weapon Event、Attack Cluster | Episode 容纳多个 WE；Attack Cluster 只负责齐射/关联分组 | 事件层级和关系基数容易混乱 |
| O-GAP-04 | 没有把同一 WE 的射手与目标/防御方设计成两套完整复盘投影 | 同一 WE ID、两侧独立 P_i/A_i/J 证据；四个空战页面双视角 | 只复盘射手，遗漏被攻击方 |
| O-GAP-05 | 目标侧窗口起点没有定义 | 区分目标侧上下文起点 T0-T 与首次 cue/告警时间 | 无法复盘告警前状态，也容易把“首次告警”误当窗口起点 |
| O-GAP-06 | 没有明确给出 T0-S/T0-T/T1/T2/T3 时间锚点 | 射手起点、目标起点、发射、终止、结果观察结束分开 | 发射前感知/识别/决策证据容易丢失 |
| O-GAP-07 | 没有明确允许不同发射事件窗口重叠 | 每个 WE 独立解析窗口；批次数据不做互斥切片 | 连续/并行攻击时事件窗口会错误截断 |
| O-GAP-08 | 武器终止、裁决完成、观察窗口闭合没有分开 | 三个状态维度分别表达 | “已终止”被误当“已裁决”或“事件结束” |
| O-GAP-09 | Strike 目标侧的界面语义未明确 | Strike 仅射手视角；目标信息/目标效果/J 仍是攻击过程证据 | 避免把地面目标误做成空战防御飞机 |
| O-GAP-10 | 无发射行为与发射事件的关系没有细化到攻防事件 | 有来袭 WE 时挂接目标侧；无 WE 时留在批次/ Episode 时间线，不建虚假 WE | 告警/规避/接敌行为易被遗漏或错误评分 |
| O-GAP-11 | 红蓝/编队关系没有明确作为时变 Context 投影 | 编队阵营、成员有效时间、独立目标阵营、未分配状态 | 编队变更或多编队批次时归属可能错误 |
| O-GAP-12 | 批次总览结果统计未区分事件数、攻击簇数、分类状态和裁决状态 | 各统计口径分开 | 统计口径混淆 |
| O-GAP-13 | 目标/防御方页面的可视化信息架构未细化，容易退化为文字卡片，且重复显示事件窗口甘特图 | 单机/编队差异化可视化布局；态势、P_i、A_i、J、成员关系与信息共享分别呈现；甘特图唯一归属事件窗口页 | 可视化复盘可读性差、页面重复、事件窗口职责混乱 |

---

## 3. 工程设计方案中没有明确细化的内容

| 编号 | 未明确/不足之处 | 工程补充 | 需要修改的权威/组件 |
|---|---|---|---|
| E-GAP-01 | 没有明确的 Weapon Event detector / 唯一 owner 实现合同 | 定义事件来源、触发条件、去重、稳定 ID、状态机和 provenance | 05B、Event owner contract、Golden fixtures |
| E-GAP-02 | 当前 Canonical 对象清单未见独立命名的 Weapon Event 持久化对象 | 先决定 Event node 是否由 World/Event product 表达，或需要新增 Canonical 对象；禁止 UI 私建 schema | CORE_LOGICAL_MODEL、SCHEMA_AUTHORITY_REGISTRY |
| E-GAP-03 | 没有 WE 与 Episode/Stage/Attack Cluster 的字段/关系基数合同 | 一 Episode 多 WE；多 WE 同 Cluster；每 WE 独立状态 | CORE_LOGICAL_MODEL、CROSS_LAYER_DTO_CONTRACTS、05B |
| E-GAP-04 | 没有 side-specific EventWindow resolver | 分别解析 T0-S/T0-T/T1/T2/T3、cue、response、J time | 05A/05B/05E、EventWindowProjection |
| E-GAP-05 | 没有明确的窗口重叠查询/索引策略 | 区间重叠查询、同 Episode/Cluster 关联查询、按需加载 | Storage/Query/API/05G |
| E-GAP-06 | 终止/裁决/窗口闭合可能被一个状态字段混合 | 独立状态维度与 reason code | DTO、World/Event product、validators |
| E-GAP-07 | 目标侧 observer-specific P_i 和 A_i 的页面投影未落到服务/API | ShooterPerspectiveDTO、TargetPerspectiveDTO、TeamPerspectiveProjection（候选名） | 05F、CROSS_LAYER_DTO_CONTRACTS |
| E-GAP-08 | Team 目标视角缺少成员级告警/动作数据的聚合显示合同 | 保留每个成员 P_i/A_i、shared picture agreement/divergence 和 communication relation | 05I、05G |
| E-GAP-09 | Weapon type → WVR/BVR/Strike 规则未明确为版本化 registry | 规则版本、例外、人工修订、未知类型处理 | Context artifact / Rule Registry / 05A/05B |
| E-GAP-10 | T0 的证据关联与回退策略未定义 | 优先关联真实前置事件；回退窗口必须标记 configured/inferred，不冒充 observed | 05A/05B、Data Sufficiency |
| E-GAP-11 | T2/T3 缺失、J 延迟到达和数据覆盖截止未分开 | OPEN/PARTIAL/CLOSED；TERMINAL_UNKNOWN；RESULT_PENDING；DATA_COVERAGE_END | EventWindow DTO、Release/Replay、validators |
| E-GAP-12 | 跨 Session/多架次批次事件对时边界未明确 | 批次只聚合 exact Session refs；跨 Session 必须显式 TimeTransform/Alignment Domain/Relation | 05A、05F、05E |
| E-GAP-13 | 事件窗口与高频数据的加载策略未细化 | 摘要默认加载；打开 WE 后加载两侧窗口；缓存按 release/event/perspective/window version | 05G、Query Service |
| E-GAP-14 | 缺少针对窗口重叠和攻防双侧的 Golden fixtures | 覆盖同 Episode 多发、齐射、交错发射、缺 P/A/J、无 T2、时钟重置、窗口重叠 | 05H/WS-TEST、validators |
| E-GAP-15 | UI deep-link / return context 没有绑定完整 WE/Perspective/Scope 状态 | 页面切换保持 event ID、Scope、Perspective、筛选上下文和 replay cursor | 05F、05G |
| E-GAP-16 | 目标侧态势图、cue 来源图、遥测曲线、成员矩阵/泳道和信息共享关系图缺少受控 read model/DTO | 定义 geometry/cue/response/series/member/relation/outcome projection；来源、单位、时间基准、coverage 和 reason code 必须随图表数据返回 | 05B、05E、05F、05G、05I、DTO contracts |
| E-GAP-17 | 目标页与事件窗口页重复使用同一多轨甘特图，职责边界不清 | 多轨窗口甘特图只由 Event Window 详情提供；目标页改用离散事件链和成员动作时序，并共享 Master Time Cursor | 05G、ReplayContextService、GUI state contract |
| E-GAP-18 | 目标侧几何、成员关系和信息共享边的真实性门禁未细化 | 几何要求有效轨迹/时间对齐；成员关系要求 Context；信息共享边要求通信/TDL/Relation 证据；缺失时显式 unavailable | 05A、05B、05I、validators |
| E-GAP-19 | 目标侧曲线/图表的单位、来源、数据缺口和 synthetic/demo 状态没有统一显示合同 | series DTO 携带 unit/time base/source/coverage/gaps；UI 标注示意数据，禁止用默认曲线填补生产数据缺失 | 05E、05F、05G、05H |

---

## 4. 本次 Demo 已表达、但仍未成为生产后端能力的内容

| Demo 内容 | 当前状态 | 生产化还需要什么 |
|---|---|---|
| 批次发射事件总览 | HTML 模拟数据和交互 | Batch Query Service、真实 WE detector、release-bound event list |
| WVR/BVR/Strike 分类 | Demo 规则映射 | 版本化 weapon-type registry、source mapping、例外复核 |
| 红蓝/编队关系 | Demo 拖拽配置和 CSV | Scenario Context artifact、有效时间成员关系、导入校验、审计 |
| 射手/目标视角 | Demo 页面内容切换 | 真实 P_i/A_i/J 证据 projection 和 DTO/API |
| V27 目标侧可视化复盘 | Demo 目标侧态势图、威胁信息来源卡、离散事件链、合成遥测趋势、编队关系/矩阵/动作时序/共享关系图 | 真实 geometry/cue/action/series/relation projection、单位/来源/coverage、Master Time Cursor 联动、缺失数据 fail-closed；当前示意曲线和相对几何不能作为真实证据 |
| 每枚导弹独立事件、Attack Cluster | Demo fixture | 真实发射记录去重、稳定 WE identity、cluster relation |
| T0-S/T0-T/T1/T2/T3 | Demo 时间样例 | TimeTransform、EventWindowResolver、数据充分度和状态 reason code |
| 重叠窗口 | Demo 样例和窗口展示 | 区间查询、Series boundary handling、缓存/性能测试 |
| Strike 单视角 | Demo 交互 | 生产 UI contract 和 target effect/J evidence integration |

---

## 5. 建议的文档修改顺序

1. 先批准本 Patch 的总体语义：WE、Episode、Attack Cluster、双视角、窗口重叠和 T0/T1/T2/T3。
2. 再更新 Canonical authority 决策：Event/Weapon Event 的持久化表达、关系和窗口 projection。
3. 更新 DTO contracts 与 05A/05B/05E/05F/05G/05I。
4. 更新 Stage/World Capability/Training Evaluation taxonomy 的引用关系；不创建第二套 Stage。
5. 建立 Golden fixtures 和独立 validators。
6. 冻结目标侧可视化 read model、事件窗口甘特图唯一归属和 Master Time Cursor 联动合同。
7. 最后进入 Runtime、API、GUI 和真实数据接入。

---

## 6. 明确不属于本 Patch 的内容

- 不修改 P1 116 项指标的算法定义和输入绑定。
- 不启用尚未通过 maturity gate 的 P2–P6 产品。
- 不把 Demo 模拟时间、告警、动作或裁决当成真实飞行数据。
- 不根据真实武器性能或战术最优原则推导攻击建议。
- 不把“没有记录”解释为“没有发生”。
- 不把“窗口已到数据末尾”解释为“武器已终止”。
- 不把 Demo 中的相对方位/距离、成员信息共享连线和航向/高度/速度曲线当作真实飞行证据；它们仅用于验证页面布局和交互。


---

## 7. V01 历史多批次训练综合总览：新增/未明确细化的差距

### 7.1 原方案已有基础，不应误判为完全缺失

总体方案及 ED-2.0 已经包含长期趋势、指标治理、历史 Release、数据资格、装备性能和训练效果分析等基础能力。因此，本次差距不是“TPAA 完全没有历史趋势设计”，而是原有能力尚未明确组合成一个面向多个历史批次的 V01 产品页面，也没有把批次训练类型、任务级汇总指标、导入元数据和统一筛选上下文落实为完整的页面与服务合同。

| 主题 | 原方案已有基础 | 本次仍需明确/补充的内容 |
|---|---|---|
| 历史趋势 | 长期趋势、指标产品、历史数据分析原则 | V01 作为跨多个 Batch 的综合入口；与 V26 单批次复盘明确分工 |
| 批次/架次 | Session、Episode、Sortie 和历史 Release | 多批次列表、选中批次摘要、准确 Batch/Release/Context 导航 |
| 行为类别 | WVR/BVR/Strike 等训练科目与 Weapon Event 分类 | 与 Batch 级简单/混合/综合训练类型分离 |
| 指标 | P1 指标和训练评价方法 | 击杀比、敌我交换比、任务达成率作为任务级趋势的统计口径与授权边界 |
| 装备性能 | 装备性能和长期趋势 | V01 跨批次摘要所需的可比性、单位、Metric Version、样本数与资格门禁 |
| 导入 | 数据导入、批次/数据源处理原则 | 导入时显式选择批次训练类型，并持久化至 Batch Metadata |
| 日期筛选 | 时间基准和历史数据查询基础 | V01 起止日期筛选的包含边界、时区、空结果和跨 Session 语义 |
| GUI | Ribbon、页面和图表组件 | V01 三行布局的面板顺序、垂直空间分配、间距和无重叠验收 |

### 7.2 总体设计层差距

| 编号 | 未明确/不足之处 | 需要补充的内容 | 影响 |
|---|---|---|---|
| O-GAP-14 | 历史趋势能力未明确形成 V01 多批次综合总览产品 | 定义 V01 跨 Batch 统计入口，并与 V26 单 Batch 发射事件复盘分工 | 用户无法从历史批次层面统一查看训练活动和长期变化 |
| O-GAP-15 | Batch 级训练类型与 Weapon Event 行为类别容易混淆 | 将简单对抗/混合对抗/综合对抗定义为 Batch Metadata；WVR/BVR/Strike 仍是 WE 行为类别 | 批次筛选会错误替代发射事件分类，混合批次无法正确表达 |
| O-GAP-16 | 任务级趋势指标的业务含义和权威输入未冻结 | 对击杀比、敌我交换比、任务达成率明确 Scope、被评估方、分子/分母、J 来源和零分母规则 | 演示比值可能被误认为正式指标或错误汇总 |
| O-GAP-17 | 日期范围筛选的统计边界未细化 | 起止日期、时区、跨 Session 聚合和无效范围处理 | 不同面板可能使用不同统计样本 |
| O-GAP-18 | 批次列表与详细复盘的能力边界未明确 | 选中批次摘要、汇总数据状态、逐事件明细可用性及 V26 路由条件 | 汇总样例或未解析批次可能错误跳转到其他批次明细 |
| O-GAP-19 | V01 多面板的垂直布局与空间分配未形成验收要求 | 明确三行面板顺序、行间距、底部列表内部滚动和无重叠要求 | KPI 卡片行、趋势面板和历史批次面板容易相互干涉 |

### 7.3 工程设计层差距

| 编号 | 未明确/不足之处 | 工程补充 | 需要修改的权威/组件 |
|---|---|---|---|
| E-GAP-20 | 缺少 V01 跨批次聚合 Query Service / Read Model 合同 | 统一输入筛选上下文，聚合 Batch、Sortie、Episode、WE、J、Data Qualification、Aircraft/Model 和 Metric | 05F、05E、05G、DTO contracts |
| E-GAP-21 | Batch 训练类型缺少持久化元数据与导入合同 | 受控枚举、导入显式选择、持久化、审计、未分类/待解析状态 | CORE_LOGICAL_MODEL、05A、05F、Import Service、DTO contracts |
| E-GAP-22 | 任务级比值指标缺少正式计算合同 | numerator/denominator、Scope、J authority、被评估方、zero denominator、缺失状态、跨批次重算 | 03A、Metric Registry、05F、05I、validators |
| E-GAP-23 | 起止日期筛选缺少统一时区与边界合同 | 统一批次日期解释、包含边界、空结果、反向日期和跨 Session 语义 | 05A、05E、05F、05G |
| E-GAP-24 | 装备历史趋势缺少可比性 Read Model | Metric Definition Version、单位、机型/构型、条件、样本数、覆盖率和资格状态随数据返回 | 05E、05F、05G、Metric Registry |
| E-GAP-25 | 数据资格摘要的批次聚合口径未明确 | 区分文件导入成功、解析完成、数据资格通过和正式指标可用 | 05A、05E、05F、05G |
| E-GAP-26 | V01 与 V26 的准确批次导航状态合同不足 | 路由绑定 Batch ID、Session refs、Release/Context、WE ID；无逐事件明细时禁止跳转 | 05F、05G、ReplayContextService |
| E-GAP-27 | V01 布局的防重叠与分辨率验收不足 | 明确三行网格、10px 间距、趋势行高度、底部面板收缩/内部滚动和几何边界测试 | 05G、GUI regression fixtures |
| E-GAP-28 | 任务指标、活动趋势和类别趋势可能使用不同批次集合 | 所有面板共享同一 query context、过滤条件和数据版本 | 05F、05G、Read Model validators |

---

## 8. V29～V33 Demo 已表达、但尚未成为生产后端能力的内容

| Demo 内容 | 当前 Demo 表达 | 生产化仍需要什么 |
|---|---|---|
| V01 历史多批次总览 | 多批次 KPI、历史列表、选中批次摘要和趋势图 | 真实 Batch Query Service、跨批次 Read Model、数据版本和权限边界 |
| 批次训练类型 | 简单/混合/综合标签和导入工作台选择器 | Batch Metadata Canonical authority、持久化、审计和迁移（如需要） |
| 自定义日期范围 | 起始/结束日期控件 | 正式时区、批次日期来源、边界与跨 Session 查询规则 |
| 任务级指标趋势 | 击杀比、敌我交换比、任务达成率合成曲线 | 正式 Metric Definition、Approved J、任务目标清单、分母和缺失处理 |
| 历史活动趋势 | WE 和 Episode 数量合成曲线 | 真实事件查询、去重、批次归属和历史 Release |
| 训练结果与裁决状态趋势 | 合成结果/待裁决分布 | 批准裁决数据、状态机和正式结果统计服务 |
| 行为类别构成 | WVR/BVR/Strike 合成发射数量 | 版本化 Weapon Type Registry 和真实 WE 记录 |
| 装备性能历史趋势 | 盘旋角速度、R50、告警响应时间示意曲线 | 真实指标序列、Metric Version、机型/构型可比性、样本和资格门禁 |
| 导入工作台训练类型 | 当前浏览器运行时状态、模拟队列和批次登记 | 后端持久化、事务、审计、幂等导入和解析状态机 |
| V33 三行布局 | 10px 行间距、趋势面板加高、底部批次面板压缩 | 实际 GUI 布局实现、不同分辨率/主题的长期回归测试 |
| V26 详细复盘入口 | 仅当前带逐事件明细的演示批次允许进入 V26 | 真实 Batch/Release/Context 路由、数据资格检查和权限校验 |

### 8.1 V32 间距修复未闭合的根因与 V33 最终修正

V33 只修复 V01 页面 KPI 子卡片的实际高度溢出及垂直空间分配，不改变统计口径、训练类型、日期筛选、导入流程、V26 入口或其他专项页面。

- V31 将 KPI 父行定义为 55px；KPI 卡片自身按 14px + 25px + 12px 内容轨道、12px 上下 padding 和 2px 边框计算，实际需要约 65px。
- V32 虽将外层 gap 增至 10px，但未同步增加 KPI 父行高度。卡片向下溢出约 10px，导致真实卡片边框仍侵占父行与第一行趋势面板之间的 gap。V32 原有的父容器间距检查没有发现这个子元素溢出，是此前验收不足之处。
- V33 将 KPI 父行提高到 68px，并显式将六张 KPI 卡片约束为 `box-sizing:border-box; height:65px; min-height:65px; align-self:center`，使子卡片完全处于父行内。
- V33 保持外层 gap 10px、第一/第二趋势行各 168px；第三行改为 `minmax(180px,1fr)`，在 1600×900 参考画布下实际 192px，比 V32 的 205px 再缩减 13px。
- 1600×900 下实测 KPI 卡片边框至第一行趋势面板约 11.5px；1280×720 缩放画布下约 8px。各后续行及页脚同样保持缩放后的可见间隔。
- 历史训练批次表格在内部滚动；选中批次摘要在 1600×900 和 1280×720 下均完整适配，无内容裁切。
- V33 自动化验收直接测量每张 KPI 卡片和父行的 bounding box、卡片内部 scroll/client 高度、行间距和底部摘要内容，而不只检查 DOM 顺序或父容器间距。
