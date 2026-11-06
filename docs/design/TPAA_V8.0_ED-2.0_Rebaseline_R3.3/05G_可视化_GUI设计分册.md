# ED-2.0 分册 G：可视化、训练复盘与 GUI 完整设计

**工程基线：CB-1.4.0**  
**内容基线：R39 前版《训练评估结果可视化方案》经冲突消解后的全量保真重构**

> **定义权声明：** 本分册拥有可视化信息架构、页面工作流、视觉语义、交互联动、性能策略和 GUI 验收要求的设计权；不拥有数据库、REST/DTO、Stage、Metric Catalog 的字段级定义权。所有字段/类型/nullability/枚举引用 `canonical/*` 与 05F。旧版中与当前 Canonical 冲突的 DTO 字段表已转换为“语义需求 + Canonical 引用”，其余不矛盾的页面、交互、视觉编码和验收设计全部保留并纳入本分册。

## 0. 视觉设计目标与保真规则

**可视化安全边界：** 页面可以呈现训练规则、信息链、协同、飞行/任务过程、平台/任务系统观测与官方训练裁决，但不得以图形、推荐或交互方式输出现实武器性能包线、最佳攻击参数、Pk 或战术优化。

可视化不是“把结果画出来”，而是训练评估证据链的交互入口。界面必须让用户从 Qualification/Competency/Outcome 回到 Context、Stage、Event、W/P/A/J/M、Metric、Evidence、Media 和历史版本，并能够区分事实、感知代理、动作、官方裁决、机器能力估计、Assessment、Forecast/Counterfactual。

本分册遵循四条保真规则：

1. 旧方案所有不与 CB-1.4.0 冲突的页面/交互/视觉语义均保留；
2. 旧 DTO/schema 只保留语义要求，不复制字段表；
3. R2 新增的 P2/P3/P6、knowledge-time、publication、instructor revision 等边界叠加到旧完整工作流；
4. 页面目录 P01~P13 是导航/产品族，不取代训练专项工作台；二者并存。

# 第一编：完整训练复盘与长期评价可视化基线
## 1. 可视化的核心任务

训练评估可视化不是普通 BI Dashboard。

它要同时支持四种认知任务：

1.  **快速判断**：这次训练总体结果如何，有没有 Critical 问题；
2.  **事实重构**：到底发生了什么；
3.  **原因复盘**：问题出在哪个 Stage、哪个事件、哪条信息链；
4.  **长期发展**：个人、团队和课程是否在持续改善。

因此，界面应遵循：

``` text
Overview
  ↓
Key Events
  ↓
Evidence
  ↓
Root-cause Candidates / Instructor Review
  ↓
Longitudinal Context
```

而不是：

``` text
很多仪表盘
+ 很多折线图
+ 一个总分
```

------------------------------------------------------------------------

## 2. 总体可视化原则

### 2.1 总分不是视觉中心

首页首先显示：

-   Qualification；
-   Safety Gate；
-   Mission Objectives；
-   Data Confidence；
-   关键能力；
-   关键事件。

0\~100 分只作为诊断信息之一。

### 2.2 证据优先

任何能力/分数都必须支持：

``` text
Score
→ Metrics
→ Events
→ Time Range
→ Trajectory / Data / Media
```

用户点击评分即可一路下钻到原始证据。

### 2.3 时间轴是"主控制器"

所有动态视图共享：

``` text
Master Time Cursor
```

拖动时间：

-   3D/2D飞机位置变化；
-   Flight 参数游标同步；
-   Sensor/TDL track 同步；
-   Event 状态同步；
-   Audio/Video 同步；
-   Scenario Stage 同步。

### 2.4 Context、TPAA 与 Assessment 必须视觉分区

全系统使用三类视觉语义：

``` text
CONTEXT / STANDARD   C        “要求什么”
TRUTH                W        “实际发生什么”
AVAILABLE INFO       P_i      “成员 i 客观可获得什么”
ACTION               A_i      “成员/系统做了什么”
ADJUDICATION         J        “外部权威系统如何裁决”
ASSESSMENT           Result   “本评估系统得出什么结论”
```

强制规则：

-   Reference/Profile/Rule 不得与 Truth 使用同一 lane/颜色/图标；
-   Truth 不得被画成 cockpit perception；
-   Action marker 与 official adjudication marker 必须不同；
-   Qualification/Diagnostic Score 属于 Assessment panel，不得使用 J 的
    official-result 视觉编码。

### 2.5 不确定性必须可视

低质量 world/context/association 使用明确文字、虚线和 warning badge，并允许查看 provenance；降低透明度不得损害可读性，质量等级不冒充统计概率。

### 2.6 单机、团队和任务群视图分层

同一 Session 支持 Individual / Team / Package；多机 Perception/Action
始终带 observer/actor 维度。

### 2.7 训练标准和数据事实分开表达

参考带、目标值、规则边界一律标 `CONTEXT`；实际轨迹/状态标
`TRUTH/ACTUAL`。如果界面叠加 reference 与
actual，图例必须同时标明二者来源。

## 2A. Context + TPAA 全局视觉语法

  --------------------------------------------------------------------------------------------------------------
  语义                 标准标签               视觉对象                              必要交互
  -------------------- ---------------------- ------------------------------------- ----------------------------
  Evaluation Context   `CONTEXT / STANDARD`   reference band、rule                  查看 context/profile/rule
                                              boundary、objective ribbon            version

  GroundTruthWorld     `TRUTH`                actual trajectory/state/truth entity  查看 authority/confidence

  CrewAvailableWorld   `AVAILABLE INFO`       observer-specific track/cue/card      切换 observer/source

  ActionWorld          `ACTION`               action marker/task swimlane/control   查看 actor/trigger/evidence
                                              event                                 

  AdjudicationWorld    `OFFICIAL RESULT`      独立 adjudication marker/result card  查看
                                                                                    adjudicator/reason/version

  Assessment           `ASSESSMENT`           qualification/competency/diagnostic   查看 metric/profile/evidence
  --------------------------------------------------------------------------------------------------------------

所有 TPAA
联动选择应携带：`session_id + context_id + context_version + revision_no + time range + truth_entity + observer + actor + tpaa_chain_id + adjudication_id`。`context_id` 是历史读取主键；`context_version/revision_no` 只用于显示/筛选，不得替代精确 ID。

## 3. 信息架构

建议系统一级导航：

``` text
训练架次
训练复盘
个人能力
团队能力
课程/单位分析
数据质量
评价规则/版本
```

其中"训练复盘"是核心工作区。

------------------------------------------------------------------------

## 4. 单架次页面的信息层级

建议从上到下分为五层。

### Layer A：Mission Header

显示：

-   Session ID；
-   日期时间；
-   训练类型；
-   Scenario；
-   Aircraft / Pilot / Team / Role；
-   World Capability；
-   Context Version；
-   Profile Version；
-   Data Confidence。

示例：

``` text
BVR Training / Scenario-023 / Role: Lead
World Capability: LEGACY_BVR-FULL
Data Quality: HIGH
Profile: BVR_STD_V8.0
```

------------------------------------------------------------------------

### Layer B：Outcome & Qualification Summary

推荐四个主要状态卡：

``` text
QUALIFICATION        SAFETY GATE
Q-                   PASS

MISSION OBJECTIVES   DATA CONFIDENCE
4 / 5                HIGH
```

不要在首屏使用十几个 KPI 卡。

------------------------------------------------------------------------

### Layer C：Competency Profile

推荐优先使用：

-   水平条形图；
-   bullet chart；
-   competency matrix。

而不是只用雷达图。

原因：

-   条形图便于精确比较；
-   可同时显示 score、baseline、confidence；
-   更适合不同训练类型能力数量变化。

建议：

``` text
Aircraft Control          88  ████████████████
Flight/Task Execution     84  ███████████████
Track Management          76  █████████████
SA Evidence               73  ████████████
Team Coordination         81  ██████████████
Mission Outcome           ✓
```

旁边显示：

-   本人最近同类中位数；
-   同类场景 percentile；
-   Confidence。

------------------------------------------------------------------------

### Layer D：Key Review Events

以事件卡列表呈现：

``` text
HIGH   12:44:31  Track continuity issue
HIGH   12:51:04  Team picture divergence
MED    12:56:22  Flight path deviation
INFO   13:03:11  Official training adjudication
```

支持：

-   按 priority；
-   按 Stage；
-   按 competency；
-   按 entity；
-   按 source；
-   仅显示 instructor-tagged。

点击事件：

-   时间轴定位；
-   地图/3D 跳转；
-   曲线缩放到事件窗口；
-   右侧打开 Evidence Panel。

------------------------------------------------------------------------

### Layer E：Longitudinal Context

首屏只显示少量摘要：

``` text
Track Management: improving
Comparable percentile: 72nd
Recent valid sessions: 6
```

完整长期分析进入专用页面。

------------------------------------------------------------------------

## 5. 核心训练复盘工作台

推荐桌面端主布局：

``` text
┌─────────────────────────────────────────────────────────────┐
│ Mission Header / Qualification / Current Stage             │
├──────────────────────────────┬──────────────────────────────┤
│                              │ Evidence / Event Detail      │
│  3D / 2D Tactical Replay     │                              │
│                              │ Event Card                   │
│                              │ Metrics                      │
│                              │ Data Confidence              │
│                              │ Instructor Notes             │
├──────────────────────────────┴──────────────────────────────┤
│ Unified Mission Timeline                                    │
├─────────────────────────────────────────────────────────────┤
│ Linked Plots / Track / TDL / Flight Parameters              │
└─────────────────────────────────────────────────────────────┘
```

其中：

-   中央空间视图负责"在哪里"；
-   时间轴负责"什么时候"；
-   曲线负责"数值怎样变化"；
-   Evidence Panel 负责"为什么被这样评价"。

------------------------------------------------------------------------

## 6. Master Timeline 设计

这是整个系统最重要的可视化控件。

### 6.1 多轨时间轴

建议固定显示：

``` text
PHASE       ───── Setup ───── Mission ───── Reset ─────

OBJECTIVE   ███████████       █████████████████

SAFETY                       !

TRACK        +──────×──+──────────────

TDL          ━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMM             │  │      │       │

TASK          A────ACK──START────DONE

WEAPON/TRAINING                 ★

ADJUDICATION                        ✓
```

### 6.2 时间轴交互

-   drag cursor；
-   click event；
-   zoom in/out；
-   brush select 时间区间；
-   "前一个/后一个关键事件"；
-   playback speed；
-   event-only jump；
-   synchronized media seek。

### 6.3 时间轴层级缩放

#### 全架次

只显示：

-   Stage；
-   critical events；
-   major objectives。

#### Engagement/Objective

增加：

-   track；
-   task；
-   comm；
-   adjudication。

#### 秒级事件

增加：

-   cue；
-   track state；
-   mode；
-   pilot/system actions。

防止全架次把事件挤成一团。

------------------------------------------------------------------------

## 7. 3D / 2D 飞行轨迹视图

### 7.1 基本元素

-   terrain/map（若允许）；
-   flight path；
-   aircraft marker；
-   vertical position；
-   training area / geofence；
-   objective/target area；
-   event markers；
-   time tail；
-   current-state labels。

### 7.2 2D/3D 切换

2D 适合：

-   route；
-   area；
-   target assignment；
-   package overview。

3D 适合：

-   vertical geometry；
-   WVR；
-   formation；
-   altitude profile；
-   event reconstruction。

两者共享同一时间游标。

### 7.3 轨迹视觉编码

建议不把颜色用来表示所有事情。

推荐层次：

-   Entity：固定类别色/符号；
-   Selection：高亮；
-   Confidence：透明度/线型；
-   Event：图标；
-   Stage：背景/轨迹段强调。

避免使用连续"红黄绿"给整条轨迹着色造成视觉噪声。

### 7.4 轨迹分段

可选显示：

-   full trail；
-   last N seconds；
-   selected event window；
-   Stage only。

------------------------------------------------------------------------

## 8. World State / Action 参数曲线区

不建议默认同时画 30 条参数。

### 8.1 参数组 Preset

#### Flight Control

``` text
ALT
IAS/Mach
Pitch/Roll
AOA
Nz
```

#### Handling

``` text
Stick X/Y
Rudder
Throttle
p/q/r
```

#### Safety

``` text
IAS/Mach
AOA
Nz
Warning states
```

#### Mission Profile

``` text
route error
altitude error
speed error
Stage
```

### 8.2 Context Reference Band

-   `ACTUAL / W`：实线；
-   `REFERENCE / C`：细线；
-   `TOLERANCE / C`：半透明带；
-   `VIOLATION EVENT`：由 C--W comparison 产生的事件标记。

图例必须显示 Context/Profile version；不得把 reference route/target
state 存入或标成 Truth。

例如：

``` text
Altitude
             actual ─────╮___
reference  ────────────────
            [ tolerance ]
```

------------------------------------------------------------------------

## 9. 指标解释组件

每个 metric 支持统一详情模板。

``` text
Metric: TRACK_CONTINUITY
Value: 0.89
Score: 76
Confidence: HIGH
Coverage: 96%

Definition:
有效航迹连续时间占相关窗口比例……

Evidence:
3 track gaps
Longest gap: ...
Related event: E017

Score mapping:
Assessment Profile BVR_STD_V8.0
```

用户必须能够区分：

``` text
Raw Metric Value
vs
Mapped Score
```

------------------------------------------------------------------------

## 10. 数据质量可视化

Data Quality 不应藏在设置页。

### 10.1 首屏 Badge

``` text
Data Confidence: HIGH
```

点击进入详情。

### 10.2 Source Coverage Matrix

  Source       Coverage   Sync   Entity Status
  ---------- ---------- ------ -------- --------
  Flight          99.8%   High     High ✓
  Mission         96.2%   High     High ✓
  TDL             89.1%    Med     High !
  Range            100%   High     High ✓
  Scenario         100%    ---      --- ✓
  Audio             78%    Med      --- !

### 10.3 Data Gap Timeline

把 gap 画在统一时间轴下方。

这样用户看到某次 Track Drop 时，能立刻知道是不是数据断流。

------------------------------------------------------------------------

## 11. 基本飞行训练可视化

基本飞行页面应突出"参考动作 vs 实际动作"。

### 11.1 Maneuver Card

每个训练动作一张卡：

``` text
Steep Turn #2
Qualification: Q
Altitude dwell: 92%
Speed dwell: 88%
Bank P95 error: ...
Capture time: ...
Control reversal: ...
```

### 11.2 Stage-aligned Overlay

对于重复动作，把时间归一化到：

``` text
0% → 100% maneuver progress
```

多次动作叠加：

-   altitude error；
-   speed error；
-   roll；
-   control input。

用于看重复性。

### 11.3 Repeatability View

箱线图/分布图显示：

-   本架次多次重复；
-   最近多架次。

### 11.4 Capture/Settling Visualization

在曲线上明确标：

``` text
command
capture
overshoot
stable
```

比只给 `settling_time=5.2s` 更利于教学。

------------------------------------------------------------------------

### 11.5 基本飞行 Context + TPAA Evidence Strip

基础飞行默认采用轻量证据带：

``` text
CONTEXT/REFERENCE C ━━━ ACTUAL/TRUTH W ━━━ AVAILABLE INFO P* ━━━ ACTION A ━━━ OFFICIAL J* ┃ ASSESSMENT
```

其中 `P*`、`J*` 为可选。典型高度控制显示：

``` text
C:  reference altitude / tolerance
W:  actual altitude
A:  control input / configuration action
P:  warning/mode cue（若记录）
J:  external lesson result（若存在）
Assessment: altitude-control grade / qualification
```

禁止使用 `REFERENCE/TRUTH` 合并标签，也禁止把本系统 Qualification 画进
OFFICIAL J lane。

## 12. 基本飞行多机/编队视图

### 12.1 Relative Position Plot

将 Leader 设为局部坐标原点：

``` text
x = relative longitudinal
 y = relative lateral
 z = relative vertical
```

显示：

-   desired region；
-   actual relative position cloud；
-   current relative state。

训练区域来自 Profile。

### 12.2 Formation Error Over Time

分别画：

-   longitudinal error；
-   lateral error；
-   vertical error。

并显示 tolerance band。

------------------------------------------------------------------------

## 13. WVR 复盘可视化

WVR核心是空间关系随时间变化。

### 13.1 3D Relative Replay

突出：

-   ownship；
-   other participant；
-   trails；
-   altitude；
-   selected event window。

### 13.2 Relative Geometry Panel

建议显示：

``` text
Range
Vertical Separation
Relative Bearing
Relative Heading
Closure
LOS rate（若启用）
Relative energy evidence
```

只展示训练事实和 Profile 状态，不绘制真实武器最优区。

### 13.3 Geometry State Ribbon

``` text
NEUTRAL ─── ADV ─── UNSTABLE ─── DISADV ─── RECOVERED
```

状态名称和判定完全来自 Profile。

### 13.4 Energy/State View

推荐：

-   双方 Es 时间序列；
-   ΔEs；
-   altitude/speed 联动。

不要把"更高/更低"直接渲染成红绿优劣，除非训练 Profile 明确这样定义。

### 13.5 Training Engagement Markers

官方事件用清晰标记：

``` text
Attempt
Valid
Invalid
Official Result
```

"按钮动作"和"官方训练事件"用不同图标。

------------------------------------------------------------------------

### 13.6 WVR Context + TPAA Overlay

WVR 主界面仍以轨迹/相对几何为主，但顶部/侧边必须存在 Context Rail：

-   C：Stage、role、geometry-state definition、安全/间隔 rule；
-   W：双方实际 truth TSPI；
-   P：选中 observer 的 track/cue（若有）；
-   A：选中 actor 的操纵/通信/training action；
-   J：官方模拟裁决（若有）；
-   Assessment：单独显示能力/资格结论。

缺 P 时 UI 显示 `Perception layer unavailable` 并隐藏 SA 类视图；缺 J
时显示 `Official adjudication unavailable`，保留
attempt/action，不生成官方结果。

## 14. BVR 核心工作台：Context + TPAA + Assessment

BVR 使用“W/P/A/J/M 五个运行时产品 + 一条 Context Rail + 独立 Assessment Panel”，与 C 合计构成六世界：

``` text
CONTEXT C: objective / role / Stage / rule / required response
─────────────────────────────────────────────────────────────
GROUND TRUTH W(t)
      ↓ compare T–P
CREW-AVAILABLE WORLD P_i(t)
      ↓ compare P–A
ACTION WORLD A_i(t)
      ↓ link A–J
ADJUDICATION WORLD J(t)
─────────────────────────────────────────────────────────────
ASSESSMENT: competency / qualification / confidence / evidence
```

Context 不应视觉上"流入" W，而应作为各层的解释/参考 rail；Assessment
也不应成为 J 的下一条"官方状态"，而是系统输出区域。

## 15. BVR Truth View

Truth View 只展示 W 的实际事实：

-   truth entity / entity type；
-   actual position/state；
-   actual active/inactive；
-   truth authority / confidence；
-   actual environment/system facts（若属于 W）。

`role`、`relevance window`、`objective applicability` 必须显示在独立
**Context Projection** 叠加层：

``` text
CONTEXT:
  Role assignment: Lead
  Objective relevance: 12:44:20–12:45:10
  Rule: ...
        │ applies-to
        ▼
TRUTH:
  Entity T07
  Actual state / position
```

禁止把 assigned role 或 relevance 画成 W 的固有属性。

## 16. BVR CrewAvailableWorld / Perceived World View

针对选中飞机/成员显示：

-   onboard track；
-   TDL track；
-   fused information；
-   track quality；
-   track age；
-   classification；
-   source。

### 16.1 Source Encoding

建议：

``` text
Sensor    ○
TDL       ◇
Fused     ●
Inferred  dashed
```

真实部署可替换为设计系统图标。

### 16.2 Track 生命周期

一条 track 在时间轴上显示：

``` text
Acquire ━━━━━ Drop ┄┄ Reacquire ━━━━━ Classification change
```

------------------------------------------------------------------------

## 17. BVR ActionWorld View

对选中 actor 显示 (A_i(t))：

-   physical/HOTAS input；
-   sensor/track select & designate；
-   mode change；
-   communication；
-   task acknowledge/start/complete；
-   training engagement action；
-   team handoff/action contribution。

推荐两种互补视图。

### 17.1 Action Timeline

``` text
TRACK_SELECT ─ DESIGNATE ─ COMM_TX ─ TASK_ACK ─ TRAINING_EVENT
```

每个 action marker 点击后显示：

-   trigger / linked perception evidence；
-   actor；
-   source；
-   controllability；
-   confidence；
-   linked adjudication（若有）。

### 17.2 Perception--Action Pair View

``` text
Information eligible   12:34:10.2
        │ 3.4 s
Observed action        12:34:13.6
```

无动作时显示 `NO OBSERVED ACTION`，但只有当 P 层满足 `response_required`
eligibility 时才作为训练证据。

------------------------------------------------------------------------

## 18. BVR AdjudicationWorld View

只显示官方/批准 authority 进入的 (J(t))：

-   VALID / INVALID；
-   official training result；
-   objective result；
-   range/simulator scoring；
-   reason code；
-   adjudicator version/source。

**Action marker 与 Adjudication marker 必须分开。** 用户应能根据标签区分：

``` text
ACTION OBSERVED      ≠      OFFICIAL VALID EVENT
TRAINING ATTEMPT     ≠      OFFICIAL SUCCESS
```

推荐 `Action–Adjudication Link Card`：

``` text
Action:        TRAINING_EVENT #23
Actor:         Aircraft 2
Time:          12:35:02.1
Official link: ADJ #91
Result:        VALID / ...
Reason:        ...
Authority:     Range system
Confidence:    HIGH
```

若没有官方裁决：显示
`ADJUDICATION UNAVAILABLE`，不得用灰色失败图标暗示"失败"。

## 19. Truth--Track Matching Matrix

非常适合用于分析复杂多目标 BVR。

纵轴：Truth Entity。\
横轴：Cockpit/TDL Track。

单元格编码：

-   associated；
-   duplicate；
-   unknown；
-   conflicting；
-   low confidence。

例如：

  Truth   Track 12   Track 23   Track 31
  ------- ---------- ---------- -------------
  T-01    ✓                     
  T-02               !          ! duplicate
  T-03                          ?

点击单元格显示 association timeline。

------------------------------------------------------------------------

## 20. Track Availability / Continuity View

建议对每个由 C→W projection 判定为 eligible/relevant 的 truth entity
显示一组横带：

``` text
Context relevance (C→W) █████████████████████████
P: Sensor-source info      ████████  ███████████████
P: TDL-source info         █████████████████████████
P: Crew-available fused    █████████████████████████
```

应能通过标签和图例辨认：

-   Sensor drop；
-   TDL 是否仍然可用；
-   Fused information 是否真正中断。

这比一个 89% 的数字更有教学价值。

------------------------------------------------------------------------

## 21. Track Age 可视化

使用 line/area：

``` text
Track Age
↑
│     /\        /\
│____/  \______/  \__
└────────────────────→ time
```

Profile 允许的话可以显示"stale threshold"，但阈值来源必须明确。

------------------------------------------------------------------------

## 22. Classification / Identification Timeline

对单个 Truth Entity：

``` text
UNKNOWN ───── ADVERSARY ─ UNKNOWN ─ ADVERSARY
```

叠加：

-   ground truth identity/class；
-   sensor source；
-   association confidence。

用户可看出"最终正确，但中间反复变化"。

------------------------------------------------------------------------

## 23. Cue--Response 可视化

事件卡应展示完整链：

``` text
Cue Available       12:34:10.2
       │  3.4 s
Observed Action     12:34:13.6
       │
Task Completed      12:34:18.1
```

如果无响应：

``` text
Cue Available
       ↓
NO OBSERVED RESPONSE
```

同时显示：

-   rule；
-   response window；
-   confidence；
-   data availability。

------------------------------------------------------------------------

## 24. BVR Team Shared Picture

### 24.1 Team Matrix

行：Team members。\
列：Relevant entities。

单元格显示每个成员当前：

``` text
✓ consistent
? unknown
! conflict
— no information
```

例如：

         Entity A   Entity B   Entity C
  ------ ---------- ---------- ----------
  Lead   ✓          ✓          ?
  Wing   ✓          !          ?
  #3     ✓          ✓          ✓
  #4     ---        ✓          ✓

### 24.2 Agreement Trend

\[ A\_{team}(t) \]

画成 0\~100% 时间序列。

关键 divergence 事件标到时间轴。

### 24.3 Convergence Event

显示：

``` text
C→W relevance active
     ↓
Lead track
     ↓
Wing track
     ↓
Team consistent picture

Convergence time = ...
```

------------------------------------------------------------------------

## 25. BVR Task / Role Coordination View

推荐使用泳道图：

``` text
TIME →

Lead     ASSIGN ─── ACK ───── ACTION ─── COMPLETE
Wing             ACK ─────── ACTION ─── COMPLETE
#3                     TASK-B ────────── COMPLETE
#4               UPDATE ────────────────
```

优点：

-   能显示 task ownership；
-   能显示 handoff；
-   能显示并行任务；
-   能显示 delayed/missing event。

------------------------------------------------------------------------

## 26. BVR 信息链 Sankey/Flow 的使用限制

Sankey 可以用于**架次总结**：

``` text
Relevant Entities
→ Cued
→ Tracked
→ Correctly Associated
→ Required Response
→ Official Outcome
```

但不适合秒级复盘，因为它会丢失时间顺序。

因此：

-   Summary 可用；
-   Event Debrief 不用 Sankey 代替 Timeline。

------------------------------------------------------------------------

## 26A. 空对面 Context + TPAA Chain View

每个 target / training attack objective 显示：

``` text
CONTEXT C
planned route / assigned target / objective / range rule
          │
          ├──── compare ────► W actual platform + truth target
          │                         ↓ T–P
          │                   P_i available target info
          │                         ↓ P–A
          │                   A_i association/designation/action
          │                         ↓ A–J
          └──────────────────► J official range/simulator result
                                    │
                                    ▼
                              ASSESSMENT PANEL
```

这样可以明确视觉区分：标准不满足、目标信息缺失、动作问题、外部结果不佳、本系统最终评价，避免把
planned route 当 truth 或把 score 当 adjudication 输入。

## 27. 空对面训练可视化

### 27.1 Mission Route View

2D 地图显示：

-   planned route；
-   actual route；
-   assigned corridor；
-   Stage markers；
-   target area；
-   training event；
-   official scoring point（若靶场提供）。

不要绘制系统自行计算的现实"最佳攻击路线"。

### 27.2 Route Error Panel

同步显示：

-   cross-track error；
-   altitude error；
-   speed error；
-   timing error。

### 27.3 Target Association View

``` text
CONTEXT C
Assigned / eligible target
          │
          ▼
GROUND TRUTH W
Truth target
          ↕ association
CREW-AVAILABLE P_i
Available target representation
          │
          ▼
ACTION A_i
Select / associate / designate
```

明确显示：

-   W↔P association confidence；
-   correct/conflicting/unknown association；
-   target switch；
-   P information loss 与 A designation loss 的区别；
-   C-assigned target 与实际 A action 的一致性。

前端不得显示"Mission Track vs Scenario
Truth"作为数据接口；Mission/Scenario 只是 World Reconstruction 上游
provenance。

### 27.4 Designation Timeline

``` text
C target relevance ███████████████████
Information      ███████████████████
Designation          █████  ██ █████
Training event                  ★
Official score                     ✓
```

### 27.5 Official Scoring View

只有 `AdjudicationWorld J` 中存在 approved official scoring result
时才显示：

-   target-centered 2D official scoring scatter；
-   official radial miss distance；
-   repetition dispersion；
-   valid/invalid + reason；
-   adjudicator/version/provenance。

坐标和结果只来自 J。若 J 不可用：

``` text
Official adjudication unavailable
Training action retained in A
Official score = N/A
```

不得由前端或 Metric 根据 Range/trajectory
自行重建命中结果，也不得叠加真实武器杀伤模型。

## 28. 多机空对面任务视图

推荐显示：

### Assignment Matrix

  Aircraft   Assigned Target   Observed Target   Result
  ---------- ----------------- ----------------- --------
  A1         T1                T1                ✓
  A2         T2                T2                ✓
  A3         T3                T2                !

### Task Swimlane

用于：

-   assignment；
-   acknowledgment；
-   target information；
-   designation；
-   official training event；
-   post-event transition。

### Spatial Deconfliction

只显示训练 Scenario 给出的 safety/task separation rule
违反事件，而不生成战术建议。

------------------------------------------------------------------------

## TPAA Relation / Gap 长期趋势视图

长期页面除 competency trend 外，增加四类小图：

-   Truth--Perception Gap dwell / coverage；
-   Perception--Action latency / completion；
-   Action--Adjudication link rate / unlinked action；
-   Process--Outcome Divergence（单独标志，不与 AJ Link 混为一项）；
-   Team perception divergence / convergence。

所有趋势必须按 comparable cohort 过滤，并显示 data/world-product
confidence。

## 28A. World Capability / Context Capability 可视化

每个 Session/课目首屏显示 Context 与 World availability：

``` text
Context   ✓ BVR_CTX_V8.0
W         ✓ High
P         ✓ Medium / Observer-specific
A         ✓ High
J         — Unavailable
```

统一 capability code：

-   `LEGACY_BASIC-CORE = C + W + A + M`，另显示 `P_AVAILABLE / J_AVAILABLE` flags；
-   `LEGACY_WVR-CORE = C + W + A + M`；
-   `LEGACY_WVR-INFO = C + W + P + A + M`；
-   `LEGACY_WVR-FULL = C + W + P + A + J + M`；
-   `LEGACY_BVR-PROCESS = C + W + P + A + M`；
-   `LEGACY_BVR-FULL = C + W + P + A + J + M`；
-   `LEGACY_SURF-CORE = C + W + A + M`；
-   `LEGACY_SURF-INFO = C + W + P + A + M`；
-   `LEGACY_SURF-FULL = C + W + P + A + J + M`。

例如：

``` text
LEGACY_WVR-INFO available
SA Evidence available
Official adjudication unavailable
```

能力标签只使用上述 World Capability taxonomy，不再使用旧版 Lx 编号体系。

## 29. 个人长期能力页面

长期评价不能只是折线总分。

### 29.1 Competency Trend Small Multiples

每项能力一张小趋势图：

``` text
Aircraft Control      ─╮__╭───
Track Management      __╭──────
SA Evidence           _╭─╯╭────
Team Coordination     ──╮_╭────
```

每张同时显示：

-   raw score；
-   EWMA；
-   confidence；
-   session marker。

### 29.2 Scenario Comparable Percentile

比 raw score 更适合长期比较：

``` text
This session           76th percentile
Recent median          68th
```

明确显示 cohort 定义。

### 29.3 Stability View

展示：

-   median；
-   IQR；
-   MAD；
-   worst recent observations。

用于区分：

``` text
平均水平高但波动大
vs
平均水平略低但非常稳定
```

### 29.4 Training Exposure Calendar

显示：

-   training type；
-   valid exposure；
-   role；
-   evidence quality。

不要把"多久没练"直接视觉化为"能力衰减百分比"。

------------------------------------------------------------------------

## 30. 能力热图

适合查看长期多能力：

纵轴：Competency。\
横轴：Session/Month。

``` text
                 S1 S2 S3 S4 S5 S6
Aircraft Control ██ ██ ██ ██ ██ ██
Track Management ▒▒ ▓▓ ▓▓ ██ ██ ██
SA Evidence       ▒▒ ▒▒ ▓▓ ▓▓ ██ ██
Team Coord        ▓▓ ▒▒ ▓▓ ██ ▓▓ ██
```

但必须：

-   显示 N/A；
-   不把低 confidence 当低 score；
-   支持点击到架次证据。

------------------------------------------------------------------------

## 31. 团队长期能力页面

### 31.1 Team Composition Context

始终显示成员构成。

### 31.2 Team Metrics

重点：

-   Shared Picture Agreement；
-   Task Completion；
-   Handoff；
-   Communication；
-   Team Objective Completion。

### 31.3 Composition Change Marker

团队成员变化时，在趋势图上标记：

``` text
▲ team composition changed
```

避免把成员变化误认为能力突变。

------------------------------------------------------------------------

## 32. Package / 联合训练视图

未来扩展多平台时，建议使用两种互补视图。

### 32.1 Entity--Relation Graph

节点：

-   aircraft；
-   team；
-   package；
-   airborne/ground C2；
-   virtual entity；
-   surface target。

边：

-   MEMBER_OF；
-   ASSIGNED_TO；
-   COMMUNICATES_WITH；
-   SHARES_TRACK_WITH；
-   SUPPORTS；
-   TRACKS。

使用 Entity Graph 中已有 relation，不在前端临时猜关系。

### 32.2 Mission Objective Tree

``` text
Package Objective
├── Team A Objective
│   ├── A1 Task
│   └── A2 Task
└── Team B Objective
    ├── B1 Task
    └── B2 Task
```

每层显示：

-   complete；
-   partial；
-   failed；
-   N/A；
-   confidence。

------------------------------------------------------------------------

## 33. 课程/单位分析页面

该页面是训练管理，不是单次复盘。

### 33.1 Competency Distribution

箱线图/violin/直方图：

-   按课程；
-   按 Stage；
-   按角色；
-   按 cohort。

### 33.2 Objective Failure Matrix

行：Objective。\
列：Scenario family / Course Stage。

显示失败/需改进频率。

### 33.3 Data Quality Trend

监控数据系统本身：

-   source coverage；
-   sync quality；
-   data gap；
-   entity resolution。

### 33.4 Instructor Concordance

展示：

-   Kappa/ICC；
-   分布；
-   能力域差异。

用途是 rubric 标准化，不应把页面设计成"教员排行榜"。

------------------------------------------------------------------------

## 34. 场景难度与可比性页面

### 34.1 Scenario Cohort Definition

必须明确：

``` text
Platform
Training Type
Scenario Family
Role
Team Size
Difficulty Bucket
Profile Version
```

### 34.2 Raw vs Normalized

并列显示：

``` text
Raw Score: 82
Comparable Scenario Percentile: 76th
```

### 34.3 Scenario Distribution

用分布图显示当前训练位于同类样本什么位置。

------------------------------------------------------------------------

## 35. 评价置信度可视化规范

每个 score 必须有 Confidence。

建议：

-   High：正常实线；
-   Medium：明确“中等质量”文字或图标，保持可读对比度；
-   Low：明确“低质量”文字 + warning icon，不靠淡化关键内容表达；
-   N/A：空心/斜纹；
-   Inferred：虚线。

不要用红色表示"低置信度"，因为红色应优先保留给严重训练/安全事件。

------------------------------------------------------------------------

## 36. 颜色语义规范

建议全系统固定语义：

``` text
Critical / Safety Failure   红色
Warning / Review Required  橙/琥珀
Qualified / Complete       绿色（适量）
Neutral Information        蓝/中性色
Unknown / N/A              灰色
Inferred / Low confidence  虚线/明确文字；保持可读对比度
Selection                  UI Accent
```

注意：

-   不依赖颜色作为唯一编码；
-   同时使用图标、线型、标签；
-   兼顾色觉缺陷；
-   深色/浅色模式均需保持对比度。

------------------------------------------------------------------------

## 37. Event Severity 视觉规范

  Severity   表现
  ---------- ------------------------------------
  CRITICAL   强图标 + 明确文字 + 时间轴醒目标记
  HIGH       高优先事件卡
  MEDIUM     普通事件卡
  LOW        默认折叠
  INFO       仅作为上下文

避免所有事件都使用红色感叹号。

------------------------------------------------------------------------

## 38. Evidence Panel

点击任何 Event/Metric/Score，右侧统一显示：

``` text
Title
Status / Severity
Time Range
Subject / Target / Team
Stage / Objective

Why it matters
Raw metric
Mapped score
Confidence
Data coverage
Controllability

Evidence
- trajectory
- parameter series
- track state
- communication
- video/audio

Assessment rule
Profile version

Instructor annotation
```

这是"可解释性"的核心组件。

------------------------------------------------------------------------

## 39. Root-cause Candidate 可视化

不要自动显示：

``` text
CAUSE = Pilot Error
```

应显示候选链：

``` text
Objective not achieved
        ↓
Training event unsuccessful
   ┌────┴────┐
Information  Observable response
unavailable  delayed
   │             │
TDL gap       Review event E17
```

每条边有：

-   evidence；
-   confidence；
-   source。

教员可以：

-   confirm；
-   reject；
-   add cause。

------------------------------------------------------------------------

## 40. Audio/Video 联动

本工作流统一称为 **Audio/Video/Transcript** 联动：音频、视频、转写文本与 Session Time/Event/Evidence 使用同一选择状态。

### 40.1 Media Panel

媒体不是独立播放器，而是和 Master Time 联动。

点击：

``` text
COMM_ACK_LATENCY event
```

自动定位对应音频片段。

### 40.2 Transcript

若有 transcript：

-   当前语句高亮；
-   speaker；
-   timestamp；
-   link to task/event。

机器转录内容需要显示 confidence/人工审核状态。

------------------------------------------------------------------------

## 41. 事件对比模式

训练复盘常需要比较：

-   同一架次两次动作；
-   本次 vs 上次；
-   Pilot A vs Pilot B；
-   Team A vs Team B。

建议支持 `Compare Mode`。

### 41.1 Stage-aligned Compare

两个事件都映射到：

``` text
0% Event Start → 100% Event End
```

比较：

-   errors；
-   track state；
-   control；
-   task timeline。

### 41.2 Absolute-time Compare

只适合同一次多机事件，共享 Master Time。

------------------------------------------------------------------------

## 42. 单机与多机切换逻辑

选择层级：

``` text
Session
├── Package
├── Team
└── Individual
```

当切换：

-   Competency Profile 更新；
-   Event filter 更新；
-   timeline 保持同一时间；
-   3D selected entity 改变；
-   Evidence Panel 更新。

不要重新加载完全不同页面导致用户丢失上下文。

------------------------------------------------------------------------

## 43. Bookmark / Debrief Point

教员应能保存：

``` text
Debrief Point
- timestamp / range
- selected entities
- active plots
- camera position
- comment
- related competency
```

这样训练后可直接形成复盘讲评顺序。

------------------------------------------------------------------------

## 44. 自动生成 Debrief Playlist

系统根据 ReviewPriority 生成：

``` text
1. Safety-critical event
2. Objective failure event
3. Major information discontinuity
4. Team disagreement
5. Significant positive performance
```

教员可调整顺序。

复盘不是只有"找错"，也应保留优秀表现事件。

------------------------------------------------------------------------

## 45. Positive Event 可视化

需要和问题事件并列：

``` text
SIGNIFICANT_POSITIVE
```

例如：

-   stable maneuver；
-   successful recovery；
-   strong team convergence；
-   complete task chain。

长期训练更需要知道"什么值得保持"。

------------------------------------------------------------------------

## 46. 搜索与过滤

至少支持：

``` text
Event Type
Competency
Severity
Entity
Team
Stage
Objective
Data Source
Confidence
Instructor Tag
```

对于大型联合训练，必须再支持：

``` text
Platform Type
Role
Package
Domain
```

------------------------------------------------------------------------

## 47. 可视化数据接口（Canonical 投影规则）

前端不得自行融合六类 source，也不得拥有第二套数据库/API schema。所有页面只消费 Context/World/Chain/Metric/Observation/Assessment/Capability/Application Service 提供的版本化 DTO 或只读 View Projection。

字段级唯一合同位于：

- `canonical/CROSS_LAYER_DTO_CONTRACTS.json`：Cross-layer DTO 名称、字段、类型、nullability；
- `canonical/CORE_LOGICAL_MODEL.json`：persisted logical model；
- `canonical/SCHEMA_AUTHORITY_REGISTRY.json`：定义权归属；
- `05F_Application_API_DTO设计分册.md`：API/Application 行为、错误语义和投影规则。

本可视化分册只规定**页面需要什么语义信息、如何联动和怎样显示**，不重复列 `EvaluationContextDTO`、`MetricDetailDTO` 等字段表。

### 47.1 Context/World/Chain 语义需求

UI 必须能够取得冻结的 Context identity/version/revision、Context artifact provenance、W/P/A/J/M 快照或时间序列、Relation/Gap、TPAA-M Chain、World Provenance 与数据质量。历史 Release 必须按其冻结的 context/release/catalog 读取，禁止回退到 current/latest。

### 47.2 Session/Timeline/Trajectory 语义需求

Session Summary 必须支持多 Context revision/time segment；Timeline 必须能同时呈现 Context ribbons、Stage/Event、World/Action/Adjudication、Assessment markers 与 Media；Trajectory 的实际航迹属于 W，参考航线/容差带属于 C，二者视觉上可叠加但语义不可合并。

### 47.3 Metric/Observation/Assessment 语义需求

Metric Detail 必须返回历史解释所需的 metric definition/catalog/version、typed value、subject、scope、coverage/confidence、evidence 和 world requirements；Observation/Assessment 页面只能按 immutable identity 回钻，禁止用 metric code + current catalog 猜历史定义。

### 47.4 Team/Capability 语义需求

团队共有态势必须保留各 observer 的 `P_i` 与 agreement/divergence，不得只显示融合后的单一 team picture。P2/P3 页面必须使用正式 Attribution/Estimate/Twin/Model Profile 产品，不允许前端自行重跑归因或跨构型聚合。

## 48. 前端联动事件总线

共享状态至少包含：

``` text
selectedSession
selectedContextId
selectedContextVersion
selectedContextRevisionNo
selectedScope
selectedSubjectType
selectedAircraft
selectedMissionSystemInstance
selectedTruthEntity
selectedObserver
selectedActor
selectedTeam
selectedObjective
selectedEvent
selectedMetric
selectedWorldLayer
selectedContextProjection
selectedTPAARelation
selectedTPAAChain
selectedAdjudication
selectedTime
selectedTimeRange
playbackState
```

P02/P09 的 subject selector 必须直接驱动 `selectedSubjectType`。当选择 `MISSION_SYSTEM_INSTANCE` 时，`selectedMissionSystemInstance` 必须来自 `SessionDTO.mission_system_instances` / Mission-System stable master API；不得从 sensor track、entity 或 Observation display row 临时生成主体。Metric Detail 对 Mission-System 结果必须显示并传递同一 `mission_system_instance_id`。Selector 事件流固定为 `subject selector → selectedSubjectType → (AIRCRAFT: selectedAircraft | MISSION_SYSTEM_INSTANCE: selectedMissionSystemInstance) → reload 对应 Observation/Trend lane`；切换 subject type 时不得把另一 lane 的 UUID 复用为当前主体。

核心联动：

``` text
Context rule/reference click
→ highlight applicable time/entity
→ show C–W/A/J comparison

Observer change
→ switch P_i only
→ keep W and time fixed

Actor change
→ switch A_i only

TPAA chain click
→ seek all panels to same evidence window

Assessment click
→ open metric → context/world evidence
```

## 49. 性能策略

训练数据可能高频且多机。

### 49.1 多分辨率数据

按 zoom level 提供：

-   overview downsample；
-   Stage resolution；
-   raw/high-frequency event window。

### 49.2 服务端预计算

预先计算：

-   Stage；
-   event；
-   metric；
-   trajectory LOD；
-   track segments；
-   data gap segments。

前端不要实时重新跑评估算法。

### 49.3 Event-window Lazy Load

默认只加载全局摘要；进入秒级事件时再加载高频数据。

------------------------------------------------------------------------

## 50. 大规模多机的视觉降噪

当参与者很多时：

-   默认只突出 selected team/entity；
-   其他实体降透明度；
-   通过 role/package filter 控制；
-   label collision control；
-   支持 trail length 限制；
-   支持 group cluster；
-   event-related entities 自动高亮。

不要同时显示所有实体的长轨迹和标签。

------------------------------------------------------------------------

## 51. 联合/LVC可视化扩展

未来 Entity Type 增加后，核心可视化仍使用：

``` text
Entity
Relation
Event
Objective
Metric
Assessment
```

新平台只需要：

-   icon/symbol；
-   applicable state panel；
-   relation style；
-   metric widget plugin。

因此界面不会和某一机型绑定。

------------------------------------------------------------------------

## 52. 插件式可视化组件

建议建立：

``` text
VisualizationPlugin
```

输入：

-   applicable training type；
-   required data；
-   metric/event types。

示例：

``` text
BasicManeuverWidget
FormationRelativePositionWidget
WVRGeometryWidget
BVRTrackContinuityWidget
BVRSharedPictureWidget
SurfaceTargetAssociationWidget
OfficialAdjudicationScoringWidget
LongitudinalCompetencyWidget
```

新增训练课目不重写整个前端。

------------------------------------------------------------------------

## 53. 推荐页面清单

**审查03修订**：本节是现行页面的详细展开，页面权威目录见第二编第3.2节。旧编号不作为独立路由或验收对象；下表只用于查阅历史引用。

| 历史编号及含义 | V8.0 对应页面 |
|---|---|
| 旧 P06：个人长期 | P10 的个人视图 |
| 旧 P07：团队长期 | P10 的团队视图 |
| 旧 P08：课程/单位 | P11 |
| 旧 P09：数据质量 | P12 |
| 旧 P10：规则审计 | P13 |

原P01—P05继续对应现行同号页面；P06—P09按现行目录使用新的明确含义。

### P01 Training Session List

- 搜索/筛选、导入状态、训练/数据类型；
- P1 显示 Observation/Release/Data Quality 状态；P4+ 再显示 Qualification。

### P02 Session/Episode & Platform Performance Overview

- Session→Episode/Performance Window；
- P1 平台观察指标与 evidence summary；
- P4+ 增加训练 objective/assessment summary。

### P03 Interactive Evidence / Episode Debrief

- 2D/3D、timeline、plots、evidence、media；
- P1 用于技术观察回放；P4+ 扩展为训练复盘。

### P04 Individual Training Assessment

- **P4 起启用**；Basic/Safety/Qualification、个体指标、教员评价、Human–Machine 解释。

### P05 Team / Package / Mission Assessment

- **P5 起启用**；team picture、task swimlanes、role/objective matrix、个人/团队证据分离。

### P06 Aircraft Capability Digital Twin

- **P3 起启用**；单架飞机 Twin revision、as-of、validity domain、生命周期。

### P07 Aircraft Model Capability Profile

- **P3 起启用**；型号/Block/构型的 capability surface、分布与发布版本。

### P08 Context Adjustment / Capability Separation

- **P2 起启用**；因素、可比条件、归因/条件调整、Human/Platform/Environment/Residual 的证据化分离。

### P09 Aircraft / Mission-System Observed Trend / Capability Evolution

- **Canonical page name（P09）**：`Aircraft / Mission-System Observed Trend / Capability Evolution`。Overall 与 Engineering 的 P09 标题、页面目录和导航契约必须 exact-match；不得退回 Aircraft-only 页面名。
- **P1 即启用 observed trend**；分别提供 `AIRCRAFT` 与 `MISSION_SYSTEM_INSTANCE` longitudinal lane；P3 升级显示 CAP-L2/L3/Twin 演化；不同 subject/layer 不得混线。

**P09 `ObservedTrendDTO` canonical contract（Overall/Engineering exact parity）**：

```yaml
longitudinal_release_id: UUID
longitudinal_scope_id: UUID
subject_type: AIRCRAFT|MISSION_SYSTEM_INSTANCE
subject_id: UUID
metric_code: string
metric_semantic_id: string
metric_semantic_version: int
metric_version: string
trend_semantics: OBSERVED_PERFORMANCE
session_order_scope_id: UUID?
comparison_key_hash: string
comparison_key: {}
points:
  - sample_id: UUID
    input_session_release_id: UUID
    session_id: UUID
    session_order: string?              # JS-visible Int64 decimal string
    occurred_at_utc: timestamp UTC?
    value: float?
    status: VALID | N_A | INSUFFICIENT_DATA | FAILED | REVIEW_REQUIRED
    configuration_key: string           # canonical subject-specific key，非裸 configuration_id
summary:
  current_value: float?
  ewma: float?
  slope: float?
  mad: float?
  count: int
  status: string
segments:
  - start_session_order: string?        # decimal string
    end_session_order: string?          # decimal string
    start_occurred_at_utc: timestamp UTC?
    end_occurred_at_utc: timestamp UTC?
    configuration_key: string?
    reason: CONFIG_CHANGE | METRIC_SEMANTIC_CHANGE | MANUAL
trend_bridge_ids: [UUID]
lifecycle_markers: []
```

`subject_type + subject_id` 是 UI/REST/DB 共用的稳定趋势主体解释对。`configuration_key` 必须按 subject-specific canonical projection 生成；P09 禁止把 Mission-System stable instance 当 Aircraft configuration，也禁止使用含义不明的 `configuration_id` alias。`metric_version` 必须来自历史 trend series 的 immutable `metric_definition_id`，point 的 input Session release/configuration 必须来自 frozen sample，禁止 current/latest Catalog 回解释。

### P10 Longitudinal Human / Team

- **P4/5 起启用**；人员/团队趋势、稳定性、exposure、可比场景。

### P11 Course / Unit / Joint-LVC & Planning

- P5：课程/单位分布、objective trends、教员一致性；
- P6：Joint/LVC 任务群、Forecast/Counterfactual/Training Planning；Projection 必须显式标记。

### P12 Data Quality & Observation Eligibility

- **P1 起启用**；source matrix、sync/alignment、gap、entity resolution、World/Observation eligibility。

### P13 Profile / Version / Publication / Model Governance

- **P1 起启用**；Context/Metric/Release 审计；P2+ 增加 Attribution/Model/Twin/Forecast governance。

------------------------------------------------------------------------

## 54. 不同用户角色的默认视图

### Trainee

重点：

-   本次训练；
-   关键事件；
-   能力变化；
-   教员反馈。

### Instructor

重点：

-   Interactive Debrief；
-   Event Evidence；
-   annotation；
-   Compare Mode。

### Evaluator

重点：

-   Qualification；
-   profile rules；
-   critical evidence；
-   audit trail。

### Training Manager

重点：

-   cohort trends；
-   curriculum effectiveness；
-   unit/team capability。

### Data Engineer

重点：

-   source coverage；
-   sync；
-   parser/schema version；
-   quality events。

------------------------------------------------------------------------

## 55. 报告导出方案

交互界面与静态报告应共用同一数据对象。

### 静态 PDF/HTML 报告建议章节

1.  Session Summary；
2.  Qualification & Safety；
3.  Objectives；
4.  Competency Profile；
5.  Key Events；
6.  Selected Evidence Plots；
7.  Team Assessment；
8.  Official Outcome；
9.  Longitudinal Context；
10. Data Quality；
11. Instructor Comments；
12. Profile / Algorithm Version。

静态报告中必须保留 Event ID，方便回到交互系统。

------------------------------------------------------------------------

## 56. 可视化中的数值精度

不要展示伪精确：

``` text
SA Evidence = 76.43821
```

推荐：

``` text
SA Evidence = 76
Confidence = Medium
```

原始物理指标可按传感器/算法精度显示合理小数位。

------------------------------------------------------------------------

## 57. N/A、Unknown 与 Failure 的视觉区别

必须严格区分：

``` text
FAIL
N/A
UNKNOWN
INSUFFICIENT DATA
NOT ADJUDICATED
```

例如：

-   FAIL：训练结果；
-   N/A：不适用；
-   Unknown：状态未知；
-   Insufficient Data：数据不足；
-   Not Adjudicated：官方系统未裁决。

不允许统一显示为灰色"---"而失去语义。

------------------------------------------------------------------------

## 58. 按 P 能力启用的可视化（V8.0）

### P1

- P01 Session List；P02 Platform Performance Overview；P03 Evidence/Replay；
- P09 Aircraft / Mission-System Observed Trend；P12 Data Quality；P13 Release/Audit。

### P2

- 增加 P08 Context Adjustment / Capability Separation；
- P09 可叠加 CAP-L1 与 CAP-L2，但必须明确层级和版本。

### P3

- 增加 P06 Aircraft Twin、P07 Model Capability；
- P09 展示 Observation→Adjusted→Twin evolution，不允许把模型值画成事实轨迹。

### P4

- 增加 P04 Individual Training Assessment、P10 Individual；
- P02/P03 增加 Basic/Safety/Qualification/Annotation/Report 入口。

### P5

- 增加 P05 Team/Mission、P10 Team、P11 Course/Unit；
- 按 WVR→BVR→空对面逐级打开相应 widget，不因页面存在而提前开放未验证算法。

### P6

- P11 增加 Joint/LVC 任务群与 Forecast/Counterfactual/Training Planning；
- Actual、Official Adjudication、Forecast、Counterfactual 必须有永久可见的视觉语义区分。

------------------------------------------------------------------------

## 59. 可视化验收标准

### 59.1 Traceability Test

**审查19修订**：主要交互及四次目标的计数口径统一引用第二编第27节；此处为待验证目标，路径描述不代表已通过。

随机选择任意一个 score，用户必须能在有限步骤内到达对应 evidence。

建议目标：

``` text
Assessment → Metric → Relation/Event → Context/World Evidence → Provenance/Canonical
```

不超过 4 次主要交互。

### 59.2 Time Synchronization Test

同一时间游标在：

-   map；
-   plots；
-   events；
-   media；

必须一致。

### 59.3 Missing-data Test

缺失 mandatory P/J World 时：

-   对应 BVR/WVR/SURF 信息或官方结果视图显示 unavailable；
-   不显示误导性 0 分；
-   World Capability 自动降级；
-   Source Coverage 仅用于解释"为什么 World 构建失败"。

### 59.4 Multi-aircraft Scalability Test

2、4、8、更多实体时界面仍可通过过滤/聚合保持可读。

### 59.5 Instructor Workflow Test

教员应能完成：

``` text
发现关键事件
→ 跳转证据
→ 添加标注
→ 比较事件
→ 保存 Debrief Point
```

无需离开复盘工作台。

------------------------------------------------------------------------

## 60. 推荐整体界面原型

``` text
┌──────────────────────────────────────────────────────────────────────────┐
│ BVR / Scenario / Role        Qualification Q-   Safety PASS   Data HIGH │
├──────────────────────────────────────────────────────────────────────────┤
│ Objectives 4/5     Aircraft 88   Track 76   SA 73   Team 81            │
├─────────────────────────────────────────────┬────────────────────────────┤
│                                             │ EVENT E017                 │
│        3D / 2D Mission Replay               │ Track continuity issue     │
│                                             │ 12:44:31–12:44:38          │
│                                             │ Confidence HIGH            │
│                                             │                            │
│                                             │ Sensor: lost               │
│                                             │ TDL: available             │
│                                             │ Fused: available           │
│                                             │ Action: observed           │
├─────────────────────────────────────────────┴────────────────────────────┤
│ PHASE     ─ Setup ────── Mission ───────────────── Reset ─              │
│ TRACK       █████ × ███████████████                                     │
│ TDL         ███████████████████████                                     │
│ COMM             │       │         │                                    │
│ EVENT                      ★      !                                      │
│                    ▲ Master Time Cursor                                  │
├──────────────────────────────────────────────────────────────────────────┤
│ ALT / IAS / Nz / Track Age / Agreement / Selected Metrics              │
└──────────────────────────────────────────────────────────────────────────┘
```

这一界面结构可以根据训练类型换插件，但不改变基本工作流。

------------------------------------------------------------------------

## 61. 四种训练的视觉重点总结

  -----------------------------------------------------------------------------------------
  训练类型          第一视觉对象      第二视觉对象        核心下钻
  ----------------- ----------------- ------------------- ---------------------------------
  基本飞行          Context Reference 参数曲线/动作 Stage   C--W 与 A--W 证据
                    vs W Actual + A                       

  WVR               Context +         Geometry/State +    几何、P--A、团队关系
                    multi-aircraft    TPAA relation       
                    W/A，按 INFO/FULL timeline            
                    叠加 P/J                              

  BVR               Context +         P track/TDL/team    信息链、任务链、AJ Link
                    complete TPAA     picture + A/J       
                    Chain                                 

  空对面            Context + target  Training action +   目标关联、指定、过程---结果分离
                    W/P/A/J/M chain     official J          
  -----------------------------------------------------------------------------------------

四类训练使用同一语义图例和同一 World Capability 体系，只改变业务组件。

## 62. 可视化最终原则

``` text
Overview before detail.
Events before raw data.
Evidence before interpretation.
Truth separate from perception.
Outcome separate from competency.
Individual separate from team.
Score always carries confidence.
Missing data is visible.
Time is the common interaction axis.
Every assessment is traceable.
Longitudinal comparison is scenario-aware.
```

训练评估可视化的最终目标不是让界面"看起来复杂和专业"，而是让教员和训练人员能够用最短路径回答：

``` text
发生了什么？
为什么系统这样评价？
证据在哪里？
这是个人问题、团队问题、系统问题还是数据问题？
和过去相比是否真的进步？
```

------------------------------------------------------------------------

## 63. V8.0 可视化验收不变量

1.  Context 与 Truth 永远分区；
2.  Reference 不得被标为 actual/truth；
3.  Perception 必须 observer-specific；
4.  Action 必须 actor-specific；
5.  Official J 与 Assessment 使用不同视觉语义；
6.  缺 P/J 时明确降级，不用 W/Assessment 代替；
7.  所有 Metric/Assessment 可点击回到 context + world evidence；
8.  空对面/WVR/BVR/Basic 均使用同一语义图例；
9.  长期趋势同时显示 Context cohort 与 world confidence；
10. 前端不自行重建 TPAA；不得以 Mission/Range/Scenario 等
    source-specific 数据替代 W/P/A/J/M。
11. role/relevance/objective applicability 只通过 Context Projection
    展示，不作为 Truth 属性。
12. AJ Link 与 Process--Outcome Divergence 使用不同视觉对象。

# 第二编：Episode 与飞机能力智能可视化

## 0. 可视化任务

界面必须支持六种认知任务：

1. 快速判断本次 Episode 的资格、安全、目标、数据和能力观察状态；
2. 复原 C/W/P/A/J/M 下“发生了什么”；
3. 定位事件链断点和候选原因；
4. 分离 Observed Performance 中的 Human/Platform/Environment 与残差；
5. 查看单架飞机数字能力孪生、构型/维护和长期趋势；
6. 比较同型号飞机的分布、个体差异和变化。

标准下钻路径：

```text
Overview
→ Episode/Capability Event
→ Metric/Observation/Attribution
→ TPAA-M Chain
→ World/Context/Configuration/Lifecycle Evidence
→ Provenance
```

---

## 1. 全局视觉语义

| 域 | 标准标签 | 含义 | 典型对象 |
|---|---|---|---|
| C | CONTEXT / STANDARD | 要求什么、对谁、何时适用 | reference band、rule、objective ribbon |
| W | TRUTH | 实际发生什么 | actual trajectory/state/entity |
| P_i | AVAILABLE INFO | observer i 可获得什么 | track、cue、warning、display |
| A_i | ACTION | actor i 做了什么 | control、mode、task、comm、training action |
| J | OFFICIAL RESULT | 外部批准系统如何裁决 | validity、score、result marker |
| M_i | MACHINE CAPABILITY WORLD | 当前证据支持的状态、声明或条件化估计 | availability、degradation、capability state；注明实测/声明/推断/未观察 |
| Assessment | ASSESSMENT | 本系统如何评价 | qualification、competency、diagnostic |
| Estimate | CAPABILITY ESTIMATE | 归因后的 L2/L3 能力 | interval、trend、release |

强制规则：

- C reference 与 W actual 不使用相同编码；
- W 不画成 P；P 始终带 observer；A 始终带 actor；M 始终带 aircraft/configuration；
- Action 与 Official J 分开；Assessment 与 J 分开；
- L1 Observed、L2 Adjusted、L3 Reference-condition Longitudinal Estimate 使用不同标签；
- Inferred、low confidence、N/A、not adjudicated 与 failure 不混同；
- 维护/软件/构型变更必须作为趋势分段标记。

---

## 2. 颜色、图形与状态规范

<a id="v7-accessibility"></a>
**审查09、19修订**：confidence 显示为质量指数/等级；概率含义未经支持时不显示“正确率”。低质量数据仍保持可读，不能只用淡色或透明度表达。关键状态同时提供文字和非颜色编码。

通用界面采用WCAG 2.2适用条款作为无障碍设计依据，覆盖颜色、文本及非文本对比度、键盘访问、可见焦点和图表文字替代。具体适用性及符合性由界面验证记录确认，本版不声称已经通过无障碍验收。

```text
Critical / Safety Failure     红色 + 强图标
Warning / Review Required    琥珀色
Qualified / Published        绿色，适量
Neutral Information          蓝/中性色
Unknown / N/A                灰色/空心/斜纹
Inferred / Low Confidence    虚线/明确文字；保持可读对比度
Machine Degraded             紫/琥珀组合 + DEGRADED 标签
Selection                    UI Accent
```

颜色不是唯一编码，必须配合图标、线型和文字；满足色觉缺陷与深浅色模式对比度。

状态必须明确显示：

```text
PASS / FAIL
N/A
UNKNOWN
INSUFFICIENT DATA
NOT ADJUDICATED
NOT IDENTIFIABLE
REVIEW REQUIRED
DRAFT / PUBLISHED / WITHDRAWN
```

不得统一显示为 `---`。

---

## 3. 信息架构与页面清单

### 3.1 一级导航

```text
训练架次
Episode 复盘
人员能力
团队能力
飞机能力
型号能力
课程/单位分析
数据质量
规则与版本
```

### 3.2 页面

<a id="v7-pages"></a>
**现行页面目录（审查03）**：P01—P13以本表为唯一编号定义。第一编第53节的个人/团队长期内容是P10的两种视图，不是另两个页面。

| ID | 页面 | 主要用途 / 首次启用 P 能力 |
|---|---|---|
| P01 | Training Session List | Session/导入/状态；P1 |
| P02 | Session/Episode & Platform Performance Overview | P1 Observation；P4+ Assessment 摘要 |
| P03 | Interactive Evidence / Episode Debrief | P1 evidence/replay；P4+ training debrief |
| P04 | Individual Training Assessment | Basic/Human–Machine；P4 |
| P05 | Team/Package/Mission Assessment | WVR→BVR→Strike；P5 |
| P06 | Aircraft Capability Digital Twin | CAP-L3/Twin；P3 |
| P07 | Aircraft Model Capability Profile | Model/Block/Config；P3 |
| P08 | Context Adjustment / Capability Separation | Attribution/Normalization/CAP-L2；P2 |
| P09 | Aircraft / Mission-System Observed Trend / Capability Evolution | Observed Trend P1 → CAP/Twin evolution P3 |
| P10 | Longitudinal Human/Team | Individual P4 / Team P5 |
| P11 | Course/Unit/Joint-LVC & Planning | Course/Unit P5；Joint/LVC + Forecast/What-if P6 |
| P12 | Data Quality & Observation Eligibility | P1 |
| P13 | Profile/Version/Publication/Model Governance | P1+ |

---

## 4. Session 与 Episode 总览

### 4.1 Mission Header

显示：Session ID、Episode ID/Type、时间、Scenario、Mission、Aircraft/Pilot/Team/Role、Aircraft Configuration、World Capability、Context/Profile/World Version、Data Confidence。

### 4.2 状态卡

首屏最多保留以下核心状态：

```text
QUALIFICATION      SAFETY GATE
MISSION OBJECTIVES DATA CONFIDENCE
EPISODE STATUS     OBSERVATION ELIGIBILITY
```

总分不是视觉中心。

### 4.3 Session→Episode Navigator

```text
Session S-2026-001
├── Basic Flight E-01  09:01–09:08
├── WVR E-02           09:20–09:24
├── WVR E-03           09:27–09:31
└── Recovery E-04      09:44–09:51
```

显示 Episode 自动检测/人工修正状态、重叠关系和 revision。点击后所有视图切换到 Episode 范围。

### 4.4 Competency 与 Observation 摘要

人员能力优先使用水平条/bullet chart；平台 L1 Observation 使用单独卡组，不与人员分合并：

```text
HUMAN / TEAM                  PLATFORM OBSERVED (L1)
Aircraft Control  88          Energy Retention   value + CI
Track Management  76          Detection Range    value + condition
SA Evidence       73          Track Stability    value + condition
```

每项显示 baseline、confidence、status 和 evidence count。

### 4.5 Key Review Events

按 Safety、Objective Impact、Capability Degradation、Team Disagreement、Adjudication、Attribution Review、Confidence 排序。支持按 Episode Stage、Competency、Capability、Entity、Source、Instructor Tag 筛选。

---

## 5. Interactive Episode Debrief 工作台

```text
┌────────────────────────────────────────────────────────────────────┐
│ Session / Episode / Stage / Configuration / Status                │
├────────────────────────────────────┬───────────────────────────────┤
│ 2D/3D Replay                       │ Evidence / Event / Observation│
│ C reference + W truth              │ Metric / Attribution Candidate│
│ P observer + A actor + M aircraft  │ Confidence / Provenance       │
├────────────────────────────────────┴───────────────────────────────┤
│ Master Timeline: C | Stage | W | P | A | J | M | Event | Observe │
├────────────────────────────────────────────────────────────────────┤
│ Linked Plots / Track / TDL / Flight / Machine State / Media       │
└────────────────────────────────────────────────────────────────────┘
```

共享状态包括 selectedSession/Episode/Stage、ContextVersion、TruthEntity、Observer、Actor、Aircraft、Configuration、Objective、Event、Metric、Observation、Attribution、Relation、Chain、Time/Range 和 Playback。

---

## 6. Master Timeline

### 6.1 固定轨道

```text
CONTEXT/OBJECTIVE  █████████████████
EPISODE/STAGE      Setup ─ Detection ─ Track ─ ...
TRUTH W            actual/relevance events
PERCEPTION P_i     acquire ━ drop ┄ reacquire
ACTION A_i         select │ designate │ task │ training action
OFFICIAL J         ★ valid/result
MACHINE M_i        available ━ degraded ┄ unavailable
SAFETY/EVENT       !
OBSERVATION        ◇ eligible / excluded / review
MAINT/CONFIG       ▲ change boundary
```

### 6.2 交互

- Master Time Cursor 同步地图、曲线、P/A/J/M、媒体和证据；
- 支持 Session、Episode、Stage、秒级事件三级缩放；
- 点击 C 高亮适用实体/时间和 C–World comparison；
- 切换 observer 只切 P_i，保持 W/时间不变；
- 切换 actor 只切 A_i；切换 aircraft/configuration 只切 M_i；
- 点击 Aircraft Observation 必须携带 `observed_metric_instance_id` 回钻 immutable Metric Detail/Evidence，并高亮其 exact window 与 correlation group；不得以 current Catalog 或仅 metric_code 重建历史结果；
- 低同步/缺失区间以背景带显示。

---

## 7. 2D/3D、曲线与指标解释

### 7.1 Trajectory

`TrajectoryDTO` 只承载 W actual trajectory；C reference route/profile 作为独立叠加层。显示 entity、team、selected、truth quality 和轨迹分段。

### 7.2 参数 Preset

- Flight Control：stick/rudder/throttle、pitch/roll/yaw；
- Handling：altitude/speed/AoA/Nz/energy；
- Safety：限制与告警；
- Mission Profile：route/altitude/speed/reference；
- Sensor：mode/track quality/age/availability；
- Machine：subsystem state、capability availability、degradation；
- Attribution Window：observed metric、factor feature、adjusted result。

### 7.3 Context Reference Band

参考带标 `CONTEXT`，实际曲线标 `TRUTH/ACTUAL`；图例显示 Context/World version。

### 7.4 Metric Detail

**审查09—10、18修订**：物理值、映射分数、经验质量及区间分别命名；区间注明类型、水平、对象与方法。有效权重或质量口径变化时解释不可比性，不把聚合分数变化直接标为进步。未说明的范围标“区间含义待确认”。

```text
Metric Name / Code / Version
Physical Value / Unit / Value Kind
Structured Schema / Structured Fields（若适用）
Mapped Score / Profile
Status / Coverage / Confidence
Episode / Stage / Subject
Required C/W/P/A/J/M
Observation Eligibility
Evidence / Relation / Chain
```

STRUCTURED 指标（当前 9 项）在 Metric Detail / P02 / P12 中显示 schema-defined 字段、null/status 语义和 Evidence，不强制压成单一数值卡；P09 仅接受 Catalog 标记 `p1_longitudinal_trend_eligibility=true` 的 NUMERIC sample。若未来需要 STRUCTURED 子字段趋势，必须发布独立 versioned component Metric/Projection Contract，UI 不得自行选择 JSON path。Mission-System Observation 以 `mission_system_instance_id` 分 lane，不能并入 Aircraft CAP-L1。

---

## 8. 数据质量与观察资格

### 8.1 首屏 Badge

显示 overall data quality、World Capability、M coverage、Observation Eligibility 和关键缺口。

### 8.2 Source/World Coverage Matrix

行是 source/world，列是 Episode Stage；显示 coverage、sync、authority、version。Source 只解释 World 构建情况，不授权前端直接计算业务指标。

### 8.3 Data Gap Timeline

与 Master Timeline 同步，区分源 gap、World gap、M gap、Context/config tag gap。

### 8.4 Observation Eligibility Panel

**审查05、11—12修订**：除合格观察外，解释全部记录、进入分析及被排除的记录和原因；区分未观察、未完成、断流和不适用。标签缺失说明信息依赖，去重状态不能显示为统计独立已证实。

```text
Metric valid                 ✓
Episode/Stage valid          ✓
Aircraft configuration       ✓
Pilot factor tags            REVIEW
Machine World coverage       ✓
TPAA-M chain                 ✓
Duplication risk             LOW
Final eligibility            REVIEW_REQUIRED
```

排除观察仍可查看原因，不从 UI 消失。

---

## 9. Basic Flight 可视化

### 9.1 Maneuver Card

科目、Stage、参考、实际、操纵、M flight state、安全、人员指标和平台 L1 Observation 分区展示。

### 9.2 Stage-aligned Overlay

多次动作按 Entry/Execution/Stabilization/Recovery 对齐，用于重复性比较。跨不同构型或 Context 的曲线明确标记，不默认叠加。

配套 `Repeatability View` 以 small multiples 和误差带展示同课目重复执行；样本不足、Context 不同或同一物理事件重复切片时禁止给出稳定性结论。

### 9.3 Capture/Settling

显示 C target band、W actual、A input、M availability、capture/overshoot/settling event 和置信度。

### 9.4 Human vs Aircraft Handling

左右并列：

```text
Human Evidence                 Aircraft Evidence
control timing                 response gain/delay
reversal/smoothness            energy/acceleration
procedure                      flight-control/engine state
```

归因不可识别时显示 `JOINT HUMAN-MACHINE OBSERVATION`，不强拆。

### 9.5 多机/编队

Relative Position Plot、Formation Error Over Time、member availability 和 role/task，保留 V5 编队视图。

---

## 10. WVR 可视化

### 10.1 3D Relative Replay

显示 W 多机真实轨迹、相对几何和能量；按选择叠加 P、A、J、M。Context Rail 显示 Stage、role、几何状态定义和安全规则。

### 10.2 Geometry/State

- Relative Geometry Panel；
- Geometry State Ribbon；
- Energy/State View；
- Merge→Position→Maneuver→Envelope→Launch→Assessment Stage 链；
- Training Action 与 Official Adjudication 不同 marker。

### 10.3 Platform Capability Overlay

显示瞬态/持续机动、能量保持、传感/火控支持的 L1 Observation window。平台限制与人员动作同时存在时，使用候选归因卡而非直接标“平台问题”。

### 10.4 缺层处理

缺 P 显示 `Perception layer unavailable` 并隐藏 SA 相关视图；缺 J 显示 `Official adjudication unavailable`；缺 M 保留几何/人员复盘但隐藏平台能力发布入口。

---

## 11. BVR 核心工作台

### 11.1 六世界链

```text
CONTEXT C: objective / role / Stage / rule / condition
──────────────────────────────────────────────────────
GROUND TRUTH W
AVAILABLE INFO P_i
ACTION A_i
OFFICIAL RESULT J
MACHINE CAPABILITY M_i
──────────────────────────────────────────────────────
ASSESSMENT / OBSERVATION / ATTRIBUTION
```

C 是参考 rail，不视觉“流入” W；Assessment/Estimate 不作为 J 的后续官方状态。

### 11.2 Truth View

只显示实际实体、位置、状态、authority 和 confidence。Role/relevance/objective 通过 Context Projection 叠加。

### 11.3 Perception View

Sensor `○`、TDL `◇`、Fused `●`、Inferred `dashed`；显示 track 生命周期、quality、age、classification、source。按 observer 切换。

### 11.4 Action View

Action Timeline 显示 select、designate、mode、communication、task、training action。Perception–Action Pair 展示 eligible time、latency、observed action 或 no response。

### 11.5 Adjudication View

只显示 approved J：validity/result/score/reason/authority/version。Action–Adjudication Link Card 明确 `ATTEMPT ≠ OFFICIAL SUCCESS`。

### 11.6 Machine Capability View

按 aircraft 展示 Sensor/EW/Weapon capability availability、mode/configuration、degradation、limitation、evidence 和 M version。M 与 P 并列：M 可用不保证信息已进入 P。

### 11.7 Truth–Track Matrix

纵轴 Truth Entity，横轴 observer 的 Sensor/TDL/Fused Track，单元格显示 associated/duplicate/unknown/conflicting/low confidence，点击进入 association timeline。

### 11.8 Track 与 ID

保留 V5 的 Availability/Continuity、Track Age、Classification Timeline、Cue–Response、Team Shared Picture、agreement/convergence/divergence 和 Task/Role Swimlane。

### 11.9 BVR Attribution Matrix View

```text
Kill-chain Stage / Breakpoint
├── Context & Environment Evidence
├── Perception Evidence
├── Action Evidence
├── Machine Capability Evidence
├── Official Adjudication Evidence
└── Candidate Attribution + Confidence + Review
```

未发现、未建航、识别失败、决策延迟、攻击无效、结果缺失使用不同规则卡。教员可确认/修改，保留原候选。

### 11.10 Flow/Sankey 限制

Sankey 只用于汇总信息链流量或事件数量，不表达未经验证的因果、平台性能或“最佳路径”。

---

## 12. Strike Mission 可视化

### 12.1 Context + TPAA-M Chain

显示 Planning→Navigation→Target Detection→Weapon Delivery→Damage Assessment；C target/route/rule 与 W/P/A/J/M 分区。

### 12.2 Mission Route

W actual route 与 C planned route 分层；Route Error、Profile Altitude/Speed 和 Mission Timing 联动。

### 12.3 Target Association

Truth target、available target info、association/designation、training action、official result 分层，禁止前端从 Mission/Range 自行匹配。

### 12.4 Designation Timeline

显示 acquire/designate/drop/reacquire/switch，并叠加 M sensor/fire-control capability state。

### 12.5 Official Scoring

独立 J 卡显示 validity、score/miss distance/result、authority/version；与人员/平台能力分开。

### 12.6 多机任务

Assignment Matrix、Task Swimlane、Spatial Deconfliction、member P_i/A_i/M_i 和 Team Objective Tree。

---

## 13. Aircraft Capability Digital Twin View

### 13.1 页面目标

回答：这架飞机当前能提供什么能力、证据有多新、随生命周期如何变化、哪些变化与维护/构型/软件事件同时发生。

### 13.2 Header

```text
Aircraft ID / Model / Block
Current Configuration / Software
Flight Hours / Last Maintenance
Twin As-of Time / Release Version
Overall Confidence / Data Freshness
```

### 13.3 Current Capability

**审查04、07修订**：默认标题为“参考条件下的长期性能估计”，同时标参考条件、证据截止范围及适用数据环境。兼容字段或代码含 intrinsic 不作为用户可见的固有性能认证。仅有状态声明或未观察项时，不绘制为实测性能。

按 Flight、Sensor、EW/Defensive、Weapon/Offensive 四域使用 bullet chart/small multiples。每项显示 L3 estimate、interval、reference context、independent episodes、last evidence、status。

HMI 作为单独标签页，不混入平台长期估计总览；不以分开展示证明人员因素已被因果剥离。

### 13.4 History

折线/区间带显示 Published Estimate；背景标：Configuration、Software、Maintenance、Fault、Part Replacement、Calibration。重大边界前后分段拟合。

### 13.5 Evidence Drill-down

```text
Twin value
→ Capability Estimate
→ Attribution Run / Result
→ Capability Observations
→ Episode / Stage / TPAA-M Chain
→ Evidence
```

### 13.6 Freshness 与 Forecast

**审查13—15修订**：说明时间尺度及按当时信息重现/按最新信息修订的口径；历史证据、当前估计和未来预测分别标明。仿真条件下结果不以样式或名称冒充现实设备性能。

观察历史、当前发布值和预测使用不同样式。预测必须显示 horizon、interval、model version，不足数据时显示 `FORECAST UNAVAILABLE`。

---

## 14. Aircraft Model Capability Profile View

### 14.1 Cohort Header

Aircraft Model、Block、Configuration、Mission/Scenario/Environment cohort、As-of time、Profile version。

### 14.2 分布

**审查12—13、18修订**：同时解释独立对象数、观察数及有效证据量的差别；群体进出与参照版本变化须可见。分位范围、对象离散和总体估计区间不可使用同一未说明的“置信带”。

箱线/violin/直方图显示 aircraft-level estimates；必须同时显示 `aircraft_count` 和 `independent_episode_count`。

### 14.3 单机分布与异常

点图显示每架飞机和区间，支持型号→单机 Twin 下钻。异常仅标 `OUTLIER/REVIEW`，不自动判故障。

### 14.4 趋势

显示型号 mean/median/dispersion/trend；Block、构型和口径变化用分面或变更线，不默认连成一条同质趋势。

### 14.5 批次/构型比较

只在 cohort/版本可比时并列；不满足时显示 `INCOMPARABLE` 与原因。

---

## 15. Capability Separation View

### 15.1 主视图

```text
Observed Performance (L1)
→ Human Contribution
→ Platform Contribution
→ Environment Contribution
→ Unexplained Component
→ Context-adjusted Result (L2)
```

### 15.2 表达规则

**审查06、08修订**：显示“模型条件下的关联解释”及其假设；因果解释须另有依据。不能因存在因素标签就画成已完成因果剥离；残差不是责任主体，也不能为了满格而强行缩放。

- `ADDITIVE_SHARE`：先说明原尺度、基线、符号和残差；只有03规定的占比解释条件成立时才使用100%堆叠，否则展示原尺度及不确定性；
- `EFFECT_SIZE`：零线两侧点区间图；
- `STANDARDIZED_VALUE`：Observed vs Adjusted 并列区间；
- `NOT_IDENTIFIABLE`：禁止绘制确定贡献，用原因卡替代。

### 15.3 下钻

贡献→factor feature set→source refs/Observation→Episode evidence。敏感人员特征按权限显示分组标签，不暴露无必要明细。

### 15.4 比较

支持同一飞机不同 Episode、同一 Episode 不同飞机、同型号 cohort，但必须固定 capability type、reference context、spec version 和 scale。

---

## 16. Capability Evolution Tree

```text
Aircraft F-001
├── Flight
│   ├── Control Response
│   ├── Maneuver
│   └── Energy
├── Sensor
│   ├── Detection
│   ├── Track
│   └── Multi-target
├── EW / Defensive
│   ├── Threat Warning
│   └── Defensive Support
└── Weapon / Offensive
    ├── Fire Control
    └── Weapon Interface
```

节点显示 current、trend、confidence、freshness、evidence count。展开后显示 L1→L2→L3 演化和生命周期变更点；节点点击进入 Twin/Estimate/Observation。

树用于层级导航，不用面积或颜色暗示无定义的能力权重。

---

## 17. 人员与团队长期视图

### 17.1 个人

Competency Trend Small Multiples、Comparable Scenario Percentile、Stability、Training Exposure Calendar、TP/PA Gap Trend。显示 role、scenario、profile、World Capability。

### 17.2 团队

显示 Shared Picture、Task Completion、Handoff、Communication、Team Objective、composition context 和 change marker。成员变化大时不把跳变解释为团队能力变化。

### 17.3 能力热图

纵轴 Competency/Capability，横轴 Session/Month；N/A、low confidence 和低 score 使用不同编码，点击到 Episode 证据。

### 17.4 暴露与衰减

“距上次训练”只作为 exposure，不直接显示为能力衰减百分比。Decline Evidence 需满足指标规格的样本和置信度门槛。

### 17.5 TPAA Relation 与 World Capability 趋势

长期页保留 TP/PA/AJ、team relation、TPAA-M chain coverage 和 World Capability/optional flag 的趋势。World Capability 变化首先解释“本次能评价什么”，不得直接渲染成能力升降。

---

## 18. Package、联合/LVC 与课程/单位

### 18.1 Entity–Relation Graph

节点为 aircraft/team/package/C2/virtual/surface target；边直接消费 MEMBER_OF、ASSIGNED_TO、COMMUNICATES_WITH、SHARES_TRACK_WITH、SUPPORTS、TRACKS，不由前端猜测。

### 18.2 Mission Objective Tree

Package→Team→Member Task，显示 complete/partial/failed/N/A/confidence。

### 18.3 课程/单位分析

- Competency/Capability Distribution；
- Objective Failure Matrix；
- Data Quality/World/M Coverage Trend；
- Observation Eligibility Trend；
- Instructor Kappa/ICC；
- Aircraft/Model evidence coverage；
- curriculum effectiveness。

教员一致性不设计成排行榜。

---

## 19. 场景可比性页面

**审查13修订**：百分位标明参照群体及版本；前后差不默认命名为因果收益。口径或样本构成变化时说明限制，缺少可比证据时保留空缺，差值箭头与连续趋势均不得暗示已证明改善。

Cohort Definition 显示 Model/Block/Configuration、Training/Episode/Stage、Scenario、Role、Team Size、Difficulty、Weather/Threat/EW、Profile/Metric/Attribution Version 和 World Capability。

并列显示 raw/observed、context-adjusted、intrinsic estimate 和 comparable percentile。不可比项不给差值箭头。

---

## 20. Evidence Panel 与根因候选

### 20.1 Evidence Panel

**审查14、17修订**：来源、修订状态、测量质量和独立性分别解释。可以追溯到来源不等于事实无误；多个来源共享原始测量或模型时不显示为独立验证。后补资料与当时已知资料保持明确区分。

```text
Title / Status / Severity
Session / Episode / Stage / Subject
Context / Objective / Rule
Metric / Observation / Estimate
Raw Value / Adjusted Value / Interval
Coverage / Confidence / Identifiability
Controllability / Candidate Attribution
W/P/A/J/M Evidence
Trajectory / Series / Media
Configuration / Lifecycle Event
Profile / Algorithm / Release Version
Instructor Annotation / Audit
```

### 20.2 Root-cause Candidate

以证据图显示多候选分支，每条边有 evidence、confidence 和 source。禁止直接显示无依据的 `CAUSE = Pilot Error` 或 `CAUSE = Aircraft Fault`。

### 20.3 Instructor Workflow

发现事件→跳转证据→确认/修改候选→添加标注→比较 Episode→保存 Debrief Point。人工修改产生 revision，不覆盖自动结果。

---

## 21. Audio/Video、对比和播放列表

媒体面板与 Master Time 同步；转写按 speaker/channel/time 显示，并标自动/人工来源。

比较模式：

- Stage-aligned：相同课目 Stage 对齐；
- Absolute-time：同一多机 Episode；
- Capability-conditioned：固定构型和 context cohort 比较 Observation。

自动 Debrief Playlist 按 Safety、Objective、Anomaly、Team、J、M Degradation、Capability Change、Confidence 排序，同时保留 Positive Event。

### 21.1 Bookmark / Debrief Point

用户可保存带 `episode_id + time range + selected layers/entities + event/metric/observation refs + note` 的复盘书签。书签不复制数据，只保存可重放的视图状态；导出报告保留 bookmark ID。

### 21.2 搜索与过滤

全局支持 Session/Episode/Aircraft/Pilot/Team/Model/Scenario/Capability/Event/Status 搜索；局部支持 Stage、World Layer、Observer、Actor、Aircraft、Confidence、Eligibility、Attribution Review、Version 过滤。过滤条件必须可见且可一键清除，避免用户误把过滤后的子集当作全量。

### 21.3 Positive Event

正向事件与问题事件使用同一证据标准。不得只自动挑选失败片段；显著恢复、稳定高质量执行、有效协同和平台能力恢复可以进入播放列表。

---

## 22. 数据接口（复用 Canonical，不重建 DTO）

第二编所有页面的数据接口严格复用 §47 的 Canonical 投影规则。Episode、World、Machine Capability、TPAA-M Chain、Metric、Capability Observation、Attribution Result、Capability Estimate、Aircraft Twin、Model Profile、Capability Evolution 等对象的字段合同以 `canonical/CROSS_LAYER_DTO_CONTRACTS.json` 和 `05F` 为准。

可视化层只冻结以下语义要求：

- 每个对象必须带可追溯 identity、release/version/provenance 和 evidence refs；
- 历史页面按冻结 Release/Context/Catalog/Model 解释，不使用 current/latest 回填；
- Int64 时间、typed value、N/A/Unknown/Failure、coverage/confidence 必须保持语义；
- P2/P3/P6 产品必须显示 identifiability/applicability/freshness/knowledge time 与 publication status；
- 前端不得自行重算归因、Twin、跨构型聚合、Team→Individual 分摊或 Counterfactual。

## 23. 前端联动事件总线

```text
selectedSession / Episode / Stage
selectedContextId / ContextVersion / ContextRevisionNo / Scope / Objective
selectedTruthEntity / Observer / Actor / Aircraft / Configuration
selectedWorldLayer / Relation / TPAA-M Chain
selectedEvent / Metric / Observation / Attribution / Estimate
selectedCapability / Cohort / Release
selectedTime / TimeRange / PlaybackState
```

关键联动：

```text
Estimate click → Attribution → Observations → Episode windows
Observation click → timeline/trajectory/P/A/M/evidence synchronize
Lifecycle marker click → split capability trend at effective time
Observer change → only P_i changes
Aircraft change → M_i and aircraft-scoped products change
Context rule click → applicable entity/time + C comparison
```

单机/多机切换只改变 scope 和聚合层：Individual 保留所选 P_i/A_i/M_i；Team 展开全部成员并派生 P–P/A–A；Package 再聚合 Objective/Relation。切换不得丢失原有 observer/actor 维度。

---

## 24. 性能和大规模视觉降噪

- 轨迹/曲线多分辨率；
- 服务端预计算 summary、tile、decimation；
- Event-window lazy load；
- 多机按 team/role/relevance 聚合，选中后展开；
- 长期页按 as-of/cohort 查询，避免一次加载全部 Observation；
- 大分布优先服务端聚合，但保留可下钻的 source estimate refs。

插件式组件至少包括 Trajectory、Timeline、Metric、Evidence、Track、Team Picture、Official J、Machine Capability、Observation、Attribution、Twin、Model Profile、Evolution 和 Longitudinal Widget。

---

## 25. 用户角色默认视图

| 角色 | 默认重点 |
|---|---|
| Trainee | 本次 Episode、关键事件、人员能力、教员反馈 |
| Instructor | Interactive Debrief、证据、候选归因、标注、比较 |
| Evaluator | Qualification、Critical evidence、Profile/Audit |
| Maintenance/Platform Analyst | Twin、M degradation、生命周期、能力证据 |
| Training Manager | cohort、课程、人员/团队/型号趋势 |
| Unit Analyst | 型号分布、构型差异、证据覆盖 |
| Data Engineer | source/world/M coverage、sync、schema、quality |
| Administrator | 权限、发布、版本和审计 |

敏感能力、人因和平台数据按权限裁剪 DTO 和导出。

---

## 26. 报告导出

静态 PDF/HTML 与交互界面共用 DTO。建议章节：

1. Session/Episode Summary；
2. Qualification & Safety；
3. Objectives & Stages；
4. Human/Team Competency；
5. Platform L1 Observations；
6. Key Events & TPAA-M Evidence；
7. Attribution（若可识别）；
8. Official Outcome；
9. Aircraft/Model Longitudinal Context；
10. Data Quality/Eligibility；
11. Instructor Comments；
12. Context/World/Metric/Attribution/Release Version。

静态报告保留 Episode/Event/Observation/Estimate ID 以返回交互系统。数字精度与测量/估计不确定性匹配，禁止伪精确。

---

## 27. 可视化验收

<a id="v7-ui-validation"></a>
**审查16、19修订**：本节为待实施验收，不是通过记录。报告说明验证环境、数据版本、用户任务、实际结果、误读及局限；包括键盘操作、焦点、文本替代和深浅色模式可读性。

“主要交互”指用户为进入下一信息对象主动执行的一次点击、键盘确认或等效操作；展开层级及跳转均计数，不将一次路径图箭头视为已实现的快捷入口。四次以内为既有设计目标，需从声明的起点逐路径实测；不满足时记录实际次数和未满足项，不能以层级图代替验证。

### 27.1 Traceability

任一 Assessment 或 Published Capability 在不超过四次主要交互内到达 Episode/World Evidence/Provenance。

### 27.2 Time Synchronization

同一时间游标在地图、曲线、P/A/J/M、事件和媒体一致。

### 27.3 Missing Data

缺 P/J/M/Context/Configuration 时显示正确状态、World Capability 降级和原因，不出现误导性 0 分或失败。

### 27.4 Semantic Separation

验收任务中，用户应能依据标签和图例指出 C、W、P、A、J、M、Assessment 及 L1/L2/L3 的含义，并区分事实、声明、推断和估计；记录误读与原因。Action 不等于 Official Result，M 不等于长期 Estimate；本条是待验证目标。

### 27.5 Multi-aircraft

2/4/8/更多实体可通过过滤、聚合和 observer/actor/aircraft 切换保持可读。

### 27.6 Capability Intelligence

- Twin value 可下钻至 Observation/Episode；
- 型号视图同时显示 aircraft_count 与 episode_count；
- 构型/维护变更点正确分段；
- 无占比语义的 Attribution 不显示百分比；可加性或 ADDITIVE_SHARE 代码不能单独作为百分比依据；
- NOT_IDENTIFIABLE 不绘制确定贡献；
- withdrawn release 不作为当前值但历史可查。

### 27.7 Instructor Workflow

教员可发现→复核→标注→比较→保存，且人工修改保留审计。

---

## 28. MVP 路线

| MVP | 可视化 |
|---|---|
| 1 | Session/Episode Overview、Timeline、Trajectory、Flight Plot、Event/Metric/Evidence、DQ，支持 Basic |
| 2 | 多机/WVR、相对几何、团队、M flight、官方 J |
| 3 | BVR 六世界、Track/ID、Shared Picture、Task、Attribution Matrix、Sensor/EW/Weapon M |
| 4 | Strike route/target/designation/official scoring/M overlay |
| 5 | Observation Eligibility、Capability Separation、Aircraft Twin、Evolution |
| 6 | Model Profile、人员/团队/飞机长期、课程/单位、Package/LVC |

---

## 29. 最终原则

```text
Overview before detail.
Episode before isolated event.
Evidence before interpretation.
Context separate from truth.
Truth separate from perception.
Machine capability separate from action and estimate.
Official outcome separate from assessment.
Observed separate from adjusted and intrinsic.
Individual separate from team; aircraft separate from model.
Score and estimate always carry confidence.
Missing and not-identifiable are visible.
Time and evidence are common interaction axes.
Every published capability is traceable.
Longitudinal comparison is context/configuration/version aware.
```


## V8.0 P1 Aircraft / Mission-System Observed Performance 可视化收口

P1 UI 在不增加页面编号的前提下扩展现有 P02/P03/P09/P12：

- **P02 Session / Aircraft Detail**：新增 `Aircraft Performance`、`Mission-System Performance`、`Reference Truth Quality` 三组子视图。飞机侧展示 Turn/Roll/Nz/AoA/Energy/Ps/Acceleration/Climb/Fuel；任务系统侧按 Radar/IRST/EO/RWR/ESM/TDL/Fusion family 展示。
- **P03 Evidence / Replay**：允许同时叠加 Ownship、Target Reference Trajectory、Sensor Measurement/Track、Fused Track；误差图必须同时显示 residual 与 reference/alignment uncertainty，不得只画“sensor error”。
- **P09 Observed Trend**：明确分成 `AIRCRAFT` 与 `MISSION_SYSTEM_INSTANCE` 两条 subject lane。任务系统趋势不得与 Aircraft CAP-L1 混成一条能力曲线。
- **P12 Data Quality**：新增 Ownship/Target INS 时间不确定度、Sensor Time Offset、Sensor-to-INS Latency、Interpolation Age、Reference Truth Uncertainty、Association Coverage。
- **P13 Governance**：显示 Catalog Version、Metric Semantic Version、evaluation profile、reference-truth profile、sensor installation/alignment profile 与 Golden status。

Mission-System 页面只呈现工程观测和证据，不显示武器发射包线、最佳攻击几何、Pk 或战术推荐。

## ED-2.0 Evidence UI Alignment

Identification 结果详情必须展示 reference classification authority、taxonomy id/version/hash 与 canonical normalization；Mission-System accuracy 详情必须展示 reference-match-quality profile id/version/hash、accepted/rejected sample count 和 N/A reason。禁止 UI 只展示最终分数而隐藏 reference eligibility provenance。

<!-- IR-HARDENING-OVERALL-UI -->
## ED-2.0 Primary Subject-Lane Clarification

P02 必须将 **Aircraft Performance** 与 **Mission-System Performance** 作为并列可选择主体，Reference Truth Quality 作为质量/证据 lane；P09 必须分别提供 `AIRCRAFT` 与 `MISSION_SYSTEM_INSTANCE` longitudinal lane。Engineering 主 API/workflow 必须在正文主合同中直接暴露二者，不得依赖读者发现后置补丁章节。

# 第三编：R3 Canonical 对齐与高级产品隔离

## 28. P6 Forecast / Counterfactual / Recommendation 专用视觉隔离

P6 产品类型在界面与接口语义中显式标记 `FORECAST` / `COUNTERFACTUAL` / `RECOMMENDATION`。

预测、反事实、推荐和模拟结果必须使用与历史事实不同的区域、标题和状态标识，并显示 model/spec version、knowledge time、input cutoff、applicability、confidence/interval 与 publication status。任何预测曲线不得覆盖或伪装成已发生航迹、已观察 Metric 或官方 J 结果。

## 29. Publication / Release / Historical Replay 可视化

所有可发布结果页面必须能显示 Release 状态（PUBLISHED/WITHDRAWN/SUPERSEDED 等）、历史版本来源和回放锚点。打开历史结果时 UI 必须加载与该 Release 绑定的 Context/Catalog/World/Model artifact；若 artifact 缺失或 schema reader 不支持，应 fail closed，并明确显示“历史解释不可用”，禁止用最新配置静默替换。

## 30. Knowledge-time 与数据泄漏防护

Longitudinal、Cohort、Attribution、Twin 和 Forecast 页面必须能够区分：事件发生时间、数据可用时间、模型知识截止时间和发布版本。用于历史评估的模型/参考数据不得包含当时不可获得的未来信息；如果页面展示“按当前模型重算”的分析，必须与“历史已发布结果”并列而不是覆盖。

## 31. Instructor Revision 与自动结果双轨显示

自动 Assessment、教员 Annotation/Revision/Override、最终发布结论是三种不同产品。界面必须保留原自动结果及其证据，展示 revision reason、author、time、rubric/profile version 和影响范围；不得以人工修订直接重写原自动记录。教员一致性页面按可比 cohort 计算并显示样本量/置信度。

## 32. GUI 知识保真验收

除传统 Traceability/Time/Missing-data/Scalability/Instructor tests 外，R3 新增：

- **Workflow Fidelity Test**：原可视化方案的 Mission Header、五层信息层级、Master Timeline、Trajectory、World/Action curves、Metric Detail、Data Quality、Basic/WVR/BVR/Strike、Longitudinal、Team/Package/Joint、Evidence、Media、Compare、Bookmark/Playlist、Role views、P01~P13 必须都有明确承载；
- **Semantic Separation Test**：C/W/P/A/J/M/Assessment/P2-P3 Estimate/P6 Forecast 不得混色或混层；
- **Historical Replay Test**：历史页面不得 fallback 到 current/latest；
- **Field Authority Test**：本分册不得出现第二套完整 DTO 字段合同；
- **N/A/Unknown/Failure Test**：缺失、不确定、不适用、失败、未评价具有不同视觉语义；
- **Team-to-Individual Isolation Test**：团队/任务群结果不得通过默认 UI 聚合成个人分数。
