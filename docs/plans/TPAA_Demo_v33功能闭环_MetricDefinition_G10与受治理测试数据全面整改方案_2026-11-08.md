# TPAA Demo v33 功能闭环、三项 Metric Definition、G10 与受治理测试数据全面整改方案

> 文档状态：`ACTIVE / 当前功能整改实施权威`
>
> 制定日期：2026-11-08
>
> 适用工作树：当前本地 TPAA v33 工作树；禁止据此推送、发布或生产部署
>
> 直接父基线：`CB-1.17.0`（不可变）
>
> 计划后继候选：`CB-1.18.0-candidate`；如数据库模型发生本方案所列变更，则候选数据库版本为 `DB 1.11.0-candidate`

## 0. 文档关系、目标与裁决

本方案是 `docs/plans/TPAA_G6至G12关闭后复核缺口全面整改与再关闭方案_2026-11-08.md` 的功能实现专项方案，细化并接管其中 R2、R3、R4、R5、R6、R7 的后续实施；原方案 R8（安装、跨平台、SBOM、漏洞和目标 workload）及 R9 最终发布裁决继续保留，但按用户要求暂缓，不作为本波次开始开发的前置条件。

本方案的直接结果是：

1. 为 `KILL_RATIO`、`EXCHANGE_RATIO`、`MISSION_COMPLETION_RATE` 起草三份完整、可执行、可审计的候选 Metric Definition，并交付实现、测试、准入包和业务审批材料；
2. 消除 G10 的“受控不可用”占位，把 Demo v33 中已经展示的功能落实为后端读写模型、API、权限、审计、持久化和真实 GUI 交互；
3. 生成一套可导入、可复现、可回放、覆盖 26 视图的测试数据与媒体包，供自动测试和用户实机操作；
4. 使 GUI 的内容、层级、控件、布局、主题和任务流以冻结的 `TPAA_训练复盘交互Demo_v33.html` 为目标，同时由正式 Application/Canonical 链路提供数据；
5. 到三项指标业务批准、媒体策略确认和人工视觉/角色任务验收节点时，输出逐项操作清单，不提前把这些人工决定伪报为通过。

本方案不扩展到 Demo 未展示的战术决策替代、武器包线推荐、命中概率战术优化、自动因果结论或生产发布能力。为支持 Demo 能力所必需的安全、审计、来源、质量与治理设施属于本方案范围。

## 1. 不可突破的真实性与安全边界

### 1.1 “真实样本”的准确含义

用户要求直接构建用于测试的软件输入文件。本方案将交付**真实存在、可由正式导入器读取、可驱动完整业务链路的测试文件**；这些文件的数据内容是确定性生成的合成场景，不是部队、装备或生产运行的真实记录。因此必须统一标记为：

- `data_classification=SYNTHETIC_TEST_FIXTURE`；
- `authority_level=TEST_ONLY`；
- `source_kind=DERIVED` 或 `INSTRUCTOR`，不得标记为 `OFFICIAL`；
- `production_eligible=false`；
- `release_claim=false`。

任何文件名、界面标签、导出报告、证据或关闭报告不得把它们描述为“实装数据”“生产实测”“正式裁决数据”。这一区分不妨碍它们作为软件功能和 GUI 实机测试的完整输入。

### 1.2 测试数据隔离

- 只有显式 `--fixture-profile GUI_V33_FULL_V1` 或 `TPAA_TEST_FIXTURE_MODE=1` 才能导入该数据包；
- 正常 Desktop、Service 和生产配置禁止扫描、自动选择或回退到 fixture；
- GUI 顶部状态区和所有导出物必须显示“合成测试数据”；
- 数据库中的 batch、release、context、evidence、report revision 均携带 fixture lineage；
- fixture 数据不得参与生产 W9、性能基准、业务准入或发布声明；
- 无正式数据时，生产界面继续呈现 `EMPTY/N_A/INSUFFICIENT/DEGRADED/ERROR`，不得自动装载 fixture 以制造 READY。

### 1.3 指标候选与正式批准分离

三项指标先以 `CANDIDATE_TEST_ONLY` 状态实现和验证。代码可计算候选值，GUI 在测试模式可明确显示“候选定义”；只有用户完成第 14.1 节业务确认后，新的批准 authority 才允许把状态切换为 `ADMITTED`。开发完成不等于业务批准，测试通过也不等于指标正式准入。

### 1.4 既有基线与工程边界

- 不修改 `baseline/CB-1.17.0/` 的任何字节；
- 通过 successor 工具从父基线生成 `CB-1.18.0-candidate`，所有差异进入 machine-readable diff 和 lock；
- 不修改既有 P1 116 项指标的语义、编号或定义；三项任务级指标使用独立的 Assessment Metric 权威；
- 前端、REST、GUI 和插件不得直接读取原始文件、Canonical JSON 或数据库表，必须经 Application owner；
- 精确 `batch_id/session_id/release_id/context_id/evaluated_side` 全链路绑定，禁止 latest 回退和跨批次借数；
- 权限、审计、CSP、loopback origin、bearer/nonce、off-the-record 和 V24 条件入口不得放宽。

## 2. 当前事实与缺口

### 2.1 三项指标

`baseline/CB-1.17.0/canonical/GUI_TASK_METRIC_ADMISSION_AUTHORITY.json` 仍为 `NOT_ADMITTED`。当前 `src/tpaa_application/historical_overview.py` 仅使用通用 `G6-TASKMETRIC-1.0.0` 和 Demo 口径，缺少逐指标的：

- 定义身份、版本、适用范围、评价方和时间范围；
- 分子/分母事件集合及去重规则；
- J 状态、质量覆盖、缺失值和零分母语义；
- 数据绑定、来源 lineage、证据引用和算法哈希；
- 跨批次可比性、聚合规则、权限和审计；
- 正式准入决定。

### 2.2 G10

当前 `GUI_P3_PROFILE_AUTHORITY.json`、`GUI_REPORT_REVISION_AUTHORITY.json` 和 `GUI_GOVERNANCE_AUTHORITY.json` 均为 `NOT_ADMITTED`；`frontend/gui-v33/src/main.ts` 对 V07、V11～V15、V18、V22 等仍以“读模型未准入/受控不可用”呈现。G10 关闭契约甚至把 `NOT_ADMITTED` 当作预期状态，不能满足“Demo 页面中的能力可实际使用”的目标。

### 2.3 数据与回放

现有工程已经具备 Weapon Event、Attack Cluster、部分世界关系、P3 persistence、回放上下文等底座，但缺少一套同时覆盖以下事实的正式 Canonical 输入契约与完整样本：

- 非发射行为和基本飞行片段；
- 感知、航迹关联、交战几何和攻击支援；
- 任务目标计划、最终裁决损失和三项指标所需集合；
- 可回放的 WGS84/Session Time 轨迹；
- 与轨迹严格对时的媒体、字幕、游标和证据；
- P3 装备剖面、趋势、告警、报告 revision 与治理记录。

### 2.4 GUI

冻结权威为：

- `docs/gui/demo-v33/DEMO_TARGET_BASELINE.json`；
- `docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json`；
- `docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json`；
- `docs/gui/demo-v33/source/TPAA_训练复盘交互Demo_v33.html`。

Demo 数值仅用于解释布局，不能复制为产品事实；但其 26 个视图的信息架构、控件、版式、交互入口、三主题和视觉层级是验收目标。

## 3. 后继基线与 Canonical/数据库设计

### 3.1 后继候选

新增：

- `tools/baseline/adopt_demo_function_successor.py`；
- `baseline/CB-1.18.0-candidate/`；
- `generated/demo-function-cb-1.18.0/manifest.json`；
- `docs/compliance/CB_1_18_0_DEMO_FUNCTION_DIFF.json`；
- 相应 `BASELINE_LOCK.json`、来源清单和兼容性矩阵。

successor 工具必须支持 `--check`，确认父基线字节不变、父链闭合、所有新增 authority 被 lock 覆盖、schema 与 DTO/codegen 同步。候选未获准前不得覆盖活动基线指针。

### 3.2 新增独立 Assessment Metric 模型

不把三项任务指标塞进 P1 `metric.metric_definition`。在 `DB 1.11.0-candidate` 中新增：

1. `assessment.task_metric_definition`
   - `definition_id`、`semantic_id`、`definition_version`、`algorithm_id/version`；
   - `name_zh/name_en`、`value_kind`、`unit`、`direction`；
   - `scope_contract`、`input_binding`、`numerator_rule`、`denominator_rule`；
   - `missing_rule`、`zero_denominator_rule`、`aggregation_rule`；
   - `qualification_rule`、`comparison_key_fields`、`definition_sha256`；
   - `admission_status`、`approved_by/at`（候选阶段为空）。
2. `assessment.task_metric_result`
   - 精确 scope、评价方、definition identity；
   - decimal-string numerator/denominator/value；
   - `READY/PENDING/N_A/INSUFFICIENT/INVALID/ERROR`；
   - reason code、coverage、J state、source/evidence refs、computed_at、algorithm hash。
3. `assessment.mission_objective_plan`
   - mission、objective code、required/optional、weight、有效时间、取消状态、版本和来源；
   - 与 `assessment.objective_result` 一一可追踪，不以命中数替代任务目标。
4. `assessment.adjudicated_loss`
   - 稳定 `loss_id`、subject、side、scope、final J status、effective time、cause refs、supersession、source/evidence；
   - 用于跨多个 Weapon Event 去重，禁止把发射次数当损失次数。
5. `assessment.engagement_episode`
   - 稳定 `engagement_id`、类别、参与方、半开时间窗、资格、scope 和证据；
   - 仅合格空战交战进入 Kill Ratio 分母。

迁移必须包括 upgrade、downgrade/回滚验证、父数据库建库后升级、现有数据根复用、唯一性/外键/索引和并发幂等测试；不可用“无迁移”绕开模型变化。

### 3.3 世界关系类型权威

新增 `WORLD_RELATION_TYPE_AUTHORITY.json`，至少定义并版本化：

- `MANEUVER_SEGMENT`；
- `BASIC_FLIGHT_DEVIATION`；
- `FORMATION_RELATION`；
- `PERCEPTION_EVENT`；
- `SENSOR_TRACK_ASSOCIATION`；
- `ENGAGEMENT_GEOMETRY`；
- `ATTACK_SUPPORT_RELATION`；
- 既有 `WEAPON_EVENT`、`ATTACK_CLUSTER` 与 supersession 关系。

每类必须定义 subject/object 类型、属性 JSON Schema、允许来源、时间语义、坐标参考系、质量字段和单一 owner。时间窗统一为半开区间 `[start, end)`；几何数据只能支持“观察到的相对关系”，不得自动生成因果结论。

### 3.4 外部研究与标准映射

- 轨迹访问、按时刻取点、子轨迹和轨迹间关系参考 [OGC Moving Features Access 1.0](https://docs.ogc.org/is/16-120r3/16-120r3.html)；
- lineage 的 Entity/Activity/Agent 映射参考 [W3C PROV-O](https://www.w3.org/TR/prov-o/)；
- 媒体字节范围使用 [RFC 9110 HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) 的 Range、206 和 416 语义；
- 完整表示与响应内容校验使用 [RFC 9530 Digest Fields](https://www.rfc-editor.org/rfc/rfc9530.html) 的 `Repr-Digest`/`Content-Digest`；
- V16 的 EWMA 递推、控制限和参数含义参考 [NIST EWMA Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)，具体参数必须由 authority 固定，不能由页面任意修改；
- 测试媒体只使用 [FFmpeg Filters](https://ffmpeg.org/ffmpeg-filters.html) 的 `testsrc`/`sine` 等确定性源或仓库自有素材，不引入第三方受版权限制内容。

## 4. 三份候选 Metric Definition

三份定义分别以独立 JSON 文件存放在 `baseline/CB-1.18.0-candidate/canonical/task-metrics/`，并以对应 Markdown 作为业务可读版本。JSON 是机器权威，Markdown 由 codegen 生成，禁止手工形成双源。

### 4.1 `TPAA-TASK-KILL-RATIO-1.0.0-candidate`

| 字段 | 候选定义 |
|---|---|
| 中文名 | 击落比（任务评估） |
| 值类型/单位/方向 | decimal ratio / `1` / 越高越好 |
| 评价主体 | `evaluated_side` 或明确的 force/team；不得省略 |
| Scope | 精确 batch、session、release、context、任务阶段、时间窗和对抗双方 |
| 分子 | 合格交战集合内，最终裁决为确认损失、属于对方、且可归因于评价方参与交战的唯一 `adjudicated_loss.loss_id` 数量 |
| 分母 | 同一精确 Scope 内，评价方与对方共同参与、类别为 BVR/WVR、裁决已终结且满足数据资格的唯一 `engagement_episode.engagement_id` 数量 |
| 公式 | `unique_confirmed_opponent_losses / unique_eligible_air_engagements` |
| 去重 | 以稳定 loss/engagement identity 去重；协同攻击多个 WE 只能产生一个确认损失；superseded 记录不计 |
| 排除 | Strike、训练取消、未知阵营、跨批次、未终结裁决、资格不足、Demo 标签和发射次数 |
| 零分母 | `N_A / ZERO_ELIGIBLE_ENGAGEMENTS`，不得显示 0、无穷大或沿用旧值 |
| 缺失/J 状态 | 未终结裁决为 `PENDING`；关键来源缺失为 `INSUFFICIENT`；冲突为 `INVALID` |
| 跨批次 | 只允许 definition identity、评价方语义、类别集合和质量门相同；先合计分子/分母再相除，禁止简单平均各批次比值 |
| 证据 | loss、engagement、world relation、adjudication、release/context 和 evidence set 引用完整列出 |

### 4.2 `TPAA-TASK-EXCHANGE-RATIO-1.0.0-candidate`

| 字段 | 候选定义 |
|---|---|
| 中文名 | 交换比（任务评估） |
| 值类型/单位/方向 | decimal ratio / `1` / 越高越好 |
| 评价主体 | 必填 `evaluated_side`；切换红/蓝视角必须重新计算分子分母，不能只交换标签 |
| Scope | 与击落比相同的精确 batch/session/release/context/阶段/时间窗 |
| 分子 | Scope 内对方最终确认损失的唯一 `loss_id` 数量 |
| 分母 | Scope 内评价方最终确认损失的唯一 `loss_id` 数量 |
| 公式 | `unique_confirmed_opponent_losses / unique_confirmed_evaluated_side_losses` |
| 去重 | 以最终未被 supersede 的损失 identity 去重；多来源证据合并而不重复计数 |
| 零分母 | `N_A / ZERO_EVALUATED_SIDE_CONFIRMED_LOSS`；不得输出 infinity 或任意上限替代值 |
| 缺失/J 状态 | 任一侧存在影响结果的 pending adjudication 时为 `PENDING`；来源覆盖不足为 `INSUFFICIENT` |
| 跨批次 | 仅在比较键完全一致时，分别合计两侧损失再相除；禁止简单平均 |
| 证据 | 双方 loss、adjudication、scope、source/evidence 和 definition hash |

### 4.3 `TPAA-TASK-MISSION-COMPLETION-RATE-1.0.0-candidate`

| 字段 | 候选定义 |
|---|---|
| 中文名 | 任务完成率 |
| 值类型/单位/方向 | decimal percentage / `%` / 越高越好；内部保留 0～1，DTO 输出 decimal-string 与显示百分数 |
| 评价主体 | mission + evaluated side/formation；必须绑定冻结的任务目标计划 revision |
| 分母 | 任务开始时有效、标记为 required、未在生效前取消的唯一 `mission_objective_plan.objective_id` 数量 |
| 分子 | 分母集合中，最终批准 `objective_result.achieved=true` 的唯一目标数量 |
| 公式 | `achieved_required_objectives / eligible_planned_required_objectives * 100` |
| optional/权重 | 1.0.0 不把 optional 目标计入；不使用权重。加权口径如需引入必须升定义版本 |
| 未知结果 | required 目标存在 pending/unknown 时整体为 `PENDING`，不得按未完成处理；数据缺失为 `INSUFFICIENT` |
| 零分母 | `N_A / ZERO_ELIGIBLE_REQUIRED_OBJECTIVES` |
| 排除 | 命中数、发射数、临时 UI 勾选、任务开始后无受控 revision 的目标增删 |
| 跨批次 | 仅相同 definition、任务类型、目标计划语义、评价方和质量门可聚合；先合计 achieved/eligible 再计算 |
| 证据 | plan revision、每个 objective result、批准状态、release/context、evidence set 与 definition hash |

### 4.4 三项共同机器字段与准入包

每份定义必须包含：`semantic_id`、`definition_version`、`algorithm_id/version`、`definition_sha256`、适用训练类型、评价方、精确 Scope、输入契约、分子/分母选择器、去重键、J/质量/覆盖门、缺失与零分母规则、跨批次比较键、显示小数位、方向、证据要求、权限、审计事件、状态和变更历史。

准入包新增：

- `TASK_METRIC_CATALOG.json`；
- `TASK_METRIC_INPUT_AUTHORITY_MATRIX.json`；
- `GUI_TASK_METRIC_ADMISSION_AUTHORITY.json` 的 successor 版本；
- `TASK_METRIC_COMPARABILITY_AUTHORITY.json`；
- `TASK_METRIC_ALGORITHM_TEST_VECTORS.json`；
- `TASK_METRIC_ADMISSION_CHECKLIST.md`；
- `TASK_METRIC_BUSINESS_DECISION_TEMPLATE.md`；
- 三份定义 JSON、生成的 Markdown 和 SHA-256 清单；
- migration、DTO、API、权限、审计与追踪矩阵。

候选包在自动门全部通过后状态仍为 `CANDIDATE_AWAITING_BUSINESS_APPROVAL`；第 14.1 节签署后，生成单独的不可变 admission decision，不改写候选历史。

## 5. 指标实现、API 与测试

### 5.1 单一 owner 与代码组织

新增：

- `src/tpaa_assessment/task_metrics/definitions.py`：解析并校验机器定义；
- `src/tpaa_assessment/task_metrics/selection.py`：构建 loss、engagement 和 objective 集合；
- `src/tpaa_assessment/task_metrics/engine.py`：纯计算、状态机和跨批次聚合；
- `src/tpaa_application/task_metric_application.py`：权限、Scope、查询、审计和 DTO；
- `src/tpaa_runtime/durable_task_metrics.py`：只负责持久化适配，不重复业务公式；
- `tools/codegen/task_metric_generate.py`：定义校验、DTO/TS/文档/测试向量生成；
- `frontend/gui-v33/src/services/task-metrics.ts`：仅消费生成 DTO。

`historical_overview.py` 删除通用 Demo 公式，改为调用 `TaskMetricApplication`；V01/V02/V09/V18 共享同一个定义身份和结果服务。

### 5.2 API

最终路径以机器路由 authority/codegen 为准，至少提供：

- `GET /api/v1/gui/task-metrics/definitions`；
- `GET /api/v1/gui/task-metrics/results?batch_id=&release_id=&context_id=&evaluated_side=`；
- `POST /api/v1/gui/task-metrics/compare`（请求体显式列出 batch/release/context，服务端检查可比性）；
- `GET /api/v1/gui/task-metrics/{semantic_id}/evidence`。

权限至少拆分为 `task_metric.definition.read`、`task_metric.result.read`、`task_metric.compare`、`task_metric.admission.read`；准入 mutation 不暴露给普通 GUI。所有拒绝、跨批次/跨定义比较、候选展示和导出均写结构化审计。

### 5.3 必测项

- 每份定义的正例、零分母、pending J、覆盖不足、冲突、supersession 和非法评价方；
- 同一损失由多个 WE/传感器证据引用时只计一次；
- 协同攻击、红蓝视角交换、Strike 排除、目标计划 revision；
- 跨批次合计分子/分母后计算，证明不进行 ratio simple average；
- definition version/hash 不同必须 `INCOMPARABLE`；
- decimal-string、舍入、排序、分页、权限、审计、损坏 JSON 和并发幂等；
- API 直连负测和 GUI 候选标签；
- 父 DB 建库→迁移→查询→回滚→再升级的一致性。

## 6. G10 未准入能力的完整实现

### 6.1 准入原则

G10 不再以 `NOT_ADMITTED` 页面作为“关闭”结果。后继 authority 必须先声明真实 owner、输入、DTO、权限、审计、持久化、失败语义和测试，再由对应实现把 capability 从 `PLANNED` 变为 `ACTIVE_TESTED`；只有业务/安全决定通过后才变为 `ADMITTED`。

必须修改 `tests/contract/gui_v33/test_g10_v33_view_closure_contract.py` 和 `tools/gui/g10_v33_close.py`：

- 不再断言三个 authority 为 `NOT_ADMITTED`；
- 不再把“没有新增路由”当通过条件；
- 路由总数从 route authority 计算，不硬编码 `103`；
- 逐路由核对 owner、permission、audit、DTO、错误语义、分页和直接 API 负测；
- 逐视图确认不再出现 `G10_NOT_ADMITTED` 等占位原因码。

### 6.2 逐视图实现矩阵

| 视图 | 必须实现的 Demo 能力 | Application/Canonical owner | 关键退出门 |
|---|---|---|---|
| V02 架次综合复盘 | 架次头、阶段/事件时间线、任务与装备指标、关键事件、质量、证据下钻、报告入口 | `SortieDebriefApplication`，复用指标/WE/assessment/quality owner | exact sortie/release/context；指标证据可回溯；不得拼接其他批次 |
| V07 基本飞行·单机 | 航迹、姿态/高度/速度/航向曲线、机动片段、偏差与质量状态 | `BasicFlightApplication` + `MANEUVER_SEGMENT/BASIC_FLIGHT_DEVIATION` | 独立于 WE；缺源显式四态；轨迹与时序同轴 |
| V09 分类长期成长 | 按训练类别/主体/机型/时间筛选的趋势、样本量、可比性断点 | `LongitudinalApplication`，复用 task metric 和 P3 result | 不可比 definition/profile 断线；禁止 simple average |
| V10 型号与机体性能总览 | 型号/机体/config profile、样本范围、资格、关键剖面与趋势入口 | `P3ProfileApplication`，复用 `p3_persistence.py`/durable repo | profile/version/config 精确绑定；模型总体与单机不混用 |
| V11 机动包线 E-M | 受观测数据支持的能量/机动分箱、包络、样本密度、资格与证据 | P3 profile 中 `maneuver_profile` owner | 只呈现观测域；外推禁用；低样本格显式不足 |
| V12 探测性能 | 探测机会、实际探测、距离/方位/高度等条件分层、覆盖和置信信息 | P3 `detection_profile` + `PERCEPTION_EVENT/SENSOR_TRACK_ASSOCIATION` | 分母为合格探测机会；缺真值不得计算命中率 |
| V13 告警性能 | 合格威胁机会、告警、延迟、漏警/误警、条件分层 | P3 `warning_profile` + perception/official adjudication | 威胁机会定义版本化；pending 不计 false |
| V14 攻击系统性能 | 合格发射、terminal/J 状态、作用结果、条件分层和证据 | P3 `weapon_profile`，复用唯一 WE owner | 不生成战术推荐/命中概率承诺；三维状态独立 |
| V15 条件因子分离 | 因子切片、配对样本、效应差/区间、覆盖和限制说明 | `ConditionalFactorApplication` | 页面和 DTO 强制 `NON_CAUSAL_ASSOCIATION`；无因果措辞 |
| V16 性能趋势与告警 | profile 版本序列、EWMA/CUSUM、控制限、漂移事件、确认/解除记录 | `PerformanceDriftApplication` | lambda、基线窗、阈值由 authority 固定；版本断点不跨越 |
| V17 数据质量与资格 | 来源覆盖、时钟/缺失/冲突、资格门、影响视图/指标、证据 | `DataQualityApplication`，复用 qualification owner | 损坏数据为 DEGRADED/ERROR，不得静默 EMPTY |
| V18 报告：架次复盘 | 预览、生成、不可变 revision、差异、下载、引用 release/context/metric/evidence | `ReportRevisionApplication` | append-only；旧 revision 不覆盖；PDF/JSON hash 可验 |
| V19 基本飞行·编队 | 编队航迹、间隔/相对位置、队形变化、单机对照、质量 | BasicFlight + `FORMATION_RELATION` | formation identity 和成员时间有效性；缺成员不补值 |
| V22 管理与版本治理 | 基线/定义/来源/作业/审计只读视图；受控 mutation 的申请、审批、执行和回滚 | `GovernanceApplication`，复用 `governance_registry.py` | read/mutate/approve 分权；自批禁止；全量审计 |
| V23 数据管理与批次导入 | 来源矩阵、文件预检、导入队列、错误定位、覆盖、fixture 显式导入 | `SourceCoverageApplication` + 既有 batch import owner | 路径不可穿越；重复/篡改检测；fixture/production 隔离 |

V01、V03～V06、V08、V20、V21、V24、V25、V26 已有实现不另建 owner；本波次将其接入同一测试数据根并补齐感知/几何/支援、真实轨迹媒体和三项候选指标，以验证 26 视图形成一个 exact-context 产品闭环。

### 6.3 建议 API 面

最终 URI 和方法由 route authority/codegen 生成，至少覆盖：

- `GET /api/v1/gui/sorties/{sortie_id}/debrief`；
- `GET /api/v1/gui/basic-flight/{session_id}` 与 `/formation`；
- `GET /api/v1/gui/longitudinal/trends`；
- `GET /api/v1/gui/equipment/profiles`、`/{profile_id}`；
- `GET /api/v1/gui/equipment/{profile_id}/maneuver|detection|warning|weapon|factors|drift`；
- `GET /api/v1/gui/data-quality/{batch_id}`；
- `POST /api/v1/gui/reports`、`GET /api/v1/gui/reports/{report_id}/revisions`、`GET .../{revision_id}/export`；
- `GET /api/v1/gui/governance/baselines|authorities|audit|jobs`；
- 受控 `POST /api/v1/gui/governance/changes`、`.../approve`、`.../execute`、`.../rollback`；
- `GET /api/v1/gui/source-coverage/{batch_id}` 与导入队列读模型。

每条路由都必须有生成 DTO、精确 permission、审计事件、分页上限、422/403/404/409/429/5xx 语义和 OpenAPI/契约测试。写操作必须幂等或携带 `Idempotency-Key`，报告生成和治理变更不得由 GET 触发。

### 6.4 权限最小集

新增并由角色矩阵显式分配：

- `sortie.debrief.read`、`basic_flight.read`、`longitudinal.read`；
- `p3.profile.read`、`p3.factor.read`、`p3.drift.read`；
- `quality.read`；
- `report.read`、`report.revision.create`、`report.export`；
- `governance.audit.read`、`governance.change.propose`、`governance.change.approve`、`governance.change.execute`、`governance.change.rollback`；
- `source.coverage.read`、`source.import.submit`；
- `media.ticket.issue`、`media.read`。

分析员、教员、数据管理员、治理审批员、审计员的权限互斥和组合由机器角色矩阵控制；前端隐藏按钮不能替代服务端拒绝。

## 7. 受治理的完整测试数据包

### 7.1 目录与生成器

新增根目录：

```text
fixtures/gui-v33/DEMO_V33_FULL_FUNCTION_V1/
├── manifest.json
├── lineage.json
├── README.md
├── source/
│   ├── flight/
│   ├── bus/
│   ├── acmi/
│   ├── scenario/
│   └── media/
├── canonical/
│   ├── batches/ sessions/ releases/ contexts/
│   ├── episodes/ world_relations/ adjudications/
│   ├── objectives/ task_metrics/ quality/
│   ├── p3_profiles/ reports/ governance/
│   └── trajectory_media/
├── expected/
│   ├── api/ views/ metrics/ hashes/
│   └── negative_cases/
└── corrupt/
    ├── bad_digest/ cross_batch/ clock_drift/
    └── invalid_relation/ unauthorized_media/
```

新增 `tools/testing/build_gui_v33_full_fixture.py`，要求：

- 固定 seed、固定基准时间、UUIDv5 namespace、canonical JSON 排序和 SHA-256；
- 连续两次生成的 manifest、Canonical 文本和媒体 hash 完全一致；
- 支持 `--check`、`--output` 和 `--include-media`；
- 输出前清空仅由它拥有且已验证位于 fixture 根下的 staging，不触碰用户数据；
- 不依赖网络，生成过程记录 Python/FFmpeg 版本和命令摘要；
- schema、lineage、referential integrity、时间单调性、坐标范围和 expected result 全部自校验。

### 7.2 场景覆盖

V1 包至少包含 12 个确定性批次，覆盖：

- BVR、WVR、Strike、基本飞行单机、基本飞行编队和混合科目；
- 蓝/红双方、2 个模型、多个机体/config、单机与编队；
- Weapon Event、Attack Cluster、非发射行为、感知、航迹关联、交战几何、攻击支援和 formation relation；
- 正常终结、`TERMINAL_UNKNOWN`、J pending、insufficient coverage、superseded 和冲突样本；
- 有损失/无损失、有交战/零交战、分母为零、目标全部完成/部分完成/pending/零 eligible；
- 同定义可比、definition/version/profile 不可比、跨批次越权、损坏 JSON；
- 详细数据批次与仅摘要批次，验证 UI 不把 summary-only 冒充明细；
- 报告 revision 1/2、治理提案/审批/回滚和导入失败队列；
- 轨迹间隙、乱序、时钟漂移、媒体缺失、无权限票据和过期票据负例。

每个场景在 `manifest.json` 中声明它驱动的视图、API、状态分支和期望断言；不得存在“页面看起来有数据但 expected 未定义”的自由样本。

### 7.3 来源与 lineage

fixture 的每个 Canonical 实体记录：

- source artifact digest、生成活动、软件 agent 和参数；
- batch/session/release/context、有效时间和 Session Time；
- classification、authority level、quality/coverage、schema version；
- 上游 Entity/Activity/Agent 关系；
- supersession 和 derivation 边。

`V23` 可显示这些来源覆盖，但必须同时显示“合成测试数据”；`V17` 使用同一 lineage 生成质量结果，不能另造页面专用数据。

### 7.4 测试 profile 的导入和清理

新增：

- `tools/testing/load_gui_v33_fixture.py --profile GUI_V33_FULL_V1 --database-url ...`；
- `tools/testing/verify_gui_v33_fixture.py --database-url ...`；
- `tools/testing/remove_gui_v33_fixture.py --fixture-id ...`。

加载器使用正式 Application/Storage 导入路径，不直写表；幂等重放结果一致。清理器只能删除带相同 fixture lineage 的对象，执行前列出精确目标并校验数据库不是生产 profile。测试代码使用临时数据库/对象根，不污染默认用户数据。

## 8. 轨迹、媒体与票据传输

### 8.1 轨迹

- 坐标使用 WGS84，经度、纬度、高度、姿态、速度及质量位显式给出；
- 时间同时提供 source time 和单调 Session Time，映射包含 drift/offset 证据；
- 2D/3D 读取同一 trajectory owner，按时间取点和子轨迹切片；
- 前端不得从静态 Demo 曲线构造轨迹；缺点/断点可见，不插值跨越不允许的 gap；
- 每个轨迹分片带 dataset manifest、series locator、schema、范围和 digest。

### 8.2 媒体样本

生成最小但完整的自有测试媒体：

- 2 段确定性 MP4 或 WebM 视频（含可识别时间码/色条，不模拟真实作战画面）；
- 1 段 WAV 测试音频；
- VTT 字幕/事件标记；
- thumbnail、duration、timebase、codec、size、SHA-256；
- 与 Session Time、trajectory 和 WE 锚点的映射。

如本机有锁定版本 FFmpeg，由生成器使用 `testsrc` 和 bit-exact `sine` 生成；无 FFmpeg 时保留已校验的小型仓库资产并由 `--check` 验 hash。媒体不得从互联网下载。

### 8.3 候选媒体票据策略

新增 `MEDIA_TICKET_TRANSFER_AUTHORITY.json` 和 `MediaTicketApplication`：

1. `POST /api/v1/gui/media/{media_id}/tickets`：校验 principal、role、exact session/release/context、媒体分类、允许 MIME/size/range，返回不透明随机 ticket；
2. `GET /api/v1/gui/media/stream?ticket=...`：只由服务端 ticket 解析媒体对象，客户端不得提交本机路径、任意 URI 或对象根 key；
3. ticket 绑定 principal、origin、media id、representation digest、允许范围和用途，默认 60 秒、一次性或有限次使用；
4. 支持 HEAD、单一 byte range、`Accept-Ranges: bytes`、206、416、ETag、`Repr-Digest`/`Content-Digest`；拒绝重叠多 range 和大量小 range；
5. 票据签发、读取、范围拒绝、过期、重放和 digest 失败全部审计；
6. 保持 exact loopback origin、native bearer/nonce 注入、无远程导航和无任意下载；
7. 测试媒体策略可先以 `CANDIDATE_TEST_ONLY` 激活，正式策略须由第 14.2 节确认。

### 8.4 回放闭环

V03 必须实现：播放/暂停、速度、时间轴、逐事件跳转、2D/3D、媒体/轨迹/指标/证据联动；深链携带 exact release/context/WE/perspective，返回 V26 或专项页时不丢上下文。媒体缺失时轨迹仍可用并显示 `MEDIA_EMPTY`；轨迹缺失时不得用媒体帧推造 Canonical 轨迹。

## 9. 前端重构与 Demo v33 忠实度

### 9.1 页面实现规则

- 26 个视图只从 `V33_FINAL_VIEW_REGISTRY.json` 注册；V24 不进入普通 Ribbon；
- 将 `main.ts` 的单文件条件渲染拆分为 `views/V01...V26`、共享 panel/chart/table/state 组件和 typed stores；
- 所有视图使用生成的 gateway/DTO，不解析 Canonical 文件；
- 保留 tactical、graphite、light 三主题，默认 graphite，会话级切换；
- 中文为主，必要缩写（BVR/WVR/E-M/EWMA/CUSUM/WE）首次出现给出中文解释或 tooltip；
- `LOADING/EMPTY/PENDING/N_A/INSUFFICIENT/DEGRADED/INVALID/ERROR/FORBIDDEN` 有统一组件和 reason code；
- fixture 模式显示持续可见但不遮挡内容的“合成测试数据”标识；
- V15 显著标注“条件关联，不代表因果关系”；V16 显示参数版本和基线窗；
- Demo 中的示例数值不得硬编码进产品 bundle。

### 9.2 视觉契约

逐视图建立 `DEMO_V33_VIEW_FIDELITY_MATRIX.json`，记录：

- Ribbon 分组、命令和选中态；
- 页面标题/副标题、筛选栏、主网格、卡片、图表、表格、详情抽屉、状态区；
- typography、spacing、radius、border、color、elevation、density token；
- 1600×900 基准布局和 1280×720、1366×768、1920×1080 reflow；
- 100%/150% DPI、三主题、Ribbon 展开/收起、键盘焦点顺序；
- 与 Demo 的允许差异及原因（安全/数据真实性/桌面容器限制）。

自动视觉工具必须在截图前断言 `data-current-view`、标题、主题、角色和 fixture ID；禁止因错误导航采集到另一个视图。相同图像 hash 仅在明确豁免时允许。

## 10. 设计文档同步

代码实施同时更新 R3.3 总体/工程设计包，不等到最后补文档：

- 总体设计：三项任务指标、G10 功能边界、测试数据分类、26 视图信息流；
- 工程设计：DB 1.11.0、world relation 类型、owner、DTO、API、权限、审计、媒体票据、失败语义；
- GUI 分册：每个视图的真实数据绑定、状态、交互和 Demo 差异；
- 接口分册：路由、分页、错误、Range/digest；
- 数据分册：fixture schema、lineage、time/CRS、质量和清理；
- 验证分册：测试向量、角色任务、视觉矩阵和证据；
- 追踪矩阵：需求→设计→authority→代码→测试→证据 hash。

任何设计更新都必须引用 successor authority，不回写或伪造 CB-1.17.0 的历史决定。

## 11. 分阶段实施顺序与退出门

### F0：状态冻结与基线脚手架

工作：保存当前 dirty-tree 清单和 hash；建立本方案状态 JSON、successor/codegen 框架、差异清单；确认 CB-1.17.0 不变。

退出门：父基线全字节 hash 一致；新计划与状态源可读；未执行 git 写操作、推送或部署。

### F1：Canonical、Metric Definition 与 DB 1.11.0

工作：完成三份机器定义、世界关系 authority、五张 Assessment/关系支撑表（按最终归一化裁决）、迁移、DTO/codegen 和准入包骨架。

退出门：schema/authority/lock/codegen `--check`；三定义 schema 和测试向量通过；升级/回滚/复升通过；候选状态诚实保持待业务批准。

### F2：确定性 fixture factory

工作：实现完整场景、lineage、negative/corrupt 集、导入/验证/清理工具和 expected outputs。

退出门：两次构建 hash 一致；正式导入链路成功；幂等重放；生产 profile 拒绝 fixture；12 批次覆盖矩阵无缺项。

### F3：三项指标闭环与 V01/V02/V09/V18 接入

工作：实现 selector/engine/application/durable/API/前端，替换 Demo 公式；生成候选报告与业务审批材料。

退出门：第 5.3 节全部自动门通过；四个视图展示 definition/version/evidence/状态；仍显示“候选定义”。到此触发第 14.1 节人工确认，而不是擅自 ADMITTED。

### F4：非发射行为、感知、几何与攻击支援

工作：实现 relation adapters/query services，完成 V07/V19、补齐 V04～V08/V20/V21/V24 感知—攻击与几何面板。

退出门：单一 owner、半开区间、三维状态、红蓝视角、跨批次拒绝、缺源四态、V08→V24 受控入口和负测通过。

### F5：轨迹、媒体、票据与 V03

工作：生成轨迹/媒体，完成 MediaTicket、Range/digest、安全审计和 2D/3D 同步回放。

退出门：正常/范围/过期/重放/越权/路径注入/digest 失败测试通过；媒体与轨迹 exact-context；触发第 14.2 节策略确认。

### F6：P3 装备视图 V10～V16

工作：在现有 P3 persistence/durable owner 上增加 profile projection、条件分层和 drift；实现页面与 API。

退出门：三个 G10 authority successor 不再是占位；V10～V16 无硬编码值；版本/config/样本/资格可追踪；V15 非因果、V16 参数冻结测试通过。

### F7：质量、报告、治理和数据管理

工作：完成 V17、V18、V22、V23；报告 revision append-only；治理四眼分权；source coverage 与导入队列。

退出门：损坏数据不静默 EMPTY；revision hash 与差异可验；自批/越权/重复执行/回滚负测通过；fixture 清晰标识。

### F8：26 视图功能与视觉整合

工作：拆分前端组件，按 Demo 完成布局/样式/控件，三主题、高 DPI、键盘、焦点、角色和全部状态矩阵。

退出门：26×3 主题×2 Ribbon 状态机器视觉矩阵采集正确；所有页面实际 view id 正确；自动布局检查通过；随后进入第 14.3 节人工视觉/角色任务验收。

### F9：功能波次复核与设计封板

工作：运行全量门禁、同步设计/追踪矩阵、生成函数级和 GUI 证据、记录开放人工项。

退出门：F0～F8 自动门无失败；三项人工节点有真实结论；若业务或视觉未确认则状态保持 `FUNCTIONAL_IMPLEMENTATION_COMPLETE_AWAITING_ACCEPTANCE`，不得伪写正式关闭。

### F10：暂缓的交付门

Windows/Linux Desktop/Service、安装包、SBOM、许可证、漏洞、目标 workload 和正式发布裁决不在本波次执行。它们仍保留在原方案 R8/R9，状态保持 OPEN；不得因功能波次完成而设置 `PRODUCT_COMPLETE=true` 或 `RELEASE_READY=true`。

## 12. 测试体系

### 12.1 自动测试层次

1. 定义/schema/codegen contract；
2. 纯领域单元测试：selector、去重、状态机、聚合、关系和 drift；
3. Application：权限、Scope、审计、错误映射；
4. Storage/migration：PostgreSQL、并发、幂等、升级/回滚；
5. API：DTO、分页、direct negative、媒体 Range/digest；
6. fixture：确定性、lineage、referential integrity、corrupt cases；
7. 前端：TypeScript、gateway、组件/状态、a11y；
8. WebEngine E2E：26 视图任务、V24 条件入口、回放、报告和治理；
9. 视觉：三主题、DPI、viewport、Ribbon 和角色矩阵；
10. 设计追踪：authority/实现/测试/evidence hash 一致。

### 12.2 通用复验命令

```powershell
$env:POLARS_SKIP_CPU_CHECK='1'

python -m ruff check src tests tools migrations
python tools/dev/tpaa_dev.py typecheck
python -m pytest tests/contract/gui_v33 -q
python -m pytest tests/unit/application tests/unit/api tests/unit/runtime tests/unit/storage tests/unit/gui -q

python tools/baseline/adopt_demo_function_successor.py --check
python tools/codegen/task_metric_generate.py --check
python tools/testing/build_gui_v33_full_fixture.py --check
python tools/testing/verify_gui_v33_fixture.py --fixture-root fixtures/gui-v33/DEMO_V33_FULL_FUNCTION_V1

Push-Location frontend/gui-v33
npm ci
npm run typecheck
npm run test:gateway
npm run build
Pop-Location

python tools/gui/g1_frontend_build.py
```

阶段专属 migration、PostgreSQL、WebEngine、媒体和视觉命令在实现时加入 `tools/testing/demo_function_gate.py`，runner 必须记录命令、exit code、耗时、stdout/stderr 摘要和产物 hash；脚本内预填 `PASS` 无效。

### 12.3 负面测试必备清单

- 错 batch/release/context、latest 回退、跨批次引用；
- definition/version/hash、评价方和 profile 不可比；
- pending J、零分母、损坏 JSON、缺轨迹、缺媒体、时钟漂移；
- V24 直达、伪造 grant、Strike target、跨角色越权；
- 报告覆盖旧 revision、治理自批、重复 execute、无批准 rollback；
- fixture 在生产 profile 导入、导出漏标 classification；
- 媒体路径注入、任意 URI、过期/重放 ticket、超范围、错误 digest；
- V15 因果措辞、V16 跨 profile 版本连续计算；
- GUI 页面错配、文字/控件裁切、键盘陷阱和错误截图。

## 13. 主要文件清单

### 13.1 新增

- `baseline/CB-1.18.0-candidate/` 及 task metric、relation、P3、report、governance、media authorities；
- `migrations/versions/*db_1_11_0*` 与 authority 快照；
- `src/tpaa_assessment/task_metrics/`；
- `src/tpaa_application/{task_metric,sortie_debrief,basic_flight,longitudinal,p3_profile,conditional_factor,performance_drift,data_quality,report_revision,source_coverage,media_ticket}_application.py`；
- 对应 durable adapters、API routers、generated DTO/gateway；
- `fixtures/gui-v33/DEMO_V33_FULL_FUNCTION_V1/`；
- fixture/build/load/verify/remove、successor、codegen 和 gate 工具；
- `frontend/gui-v33/src/views/` 与共享组件；
- 各层 unit/contract/integration/e2e/visual 测试；
- 设计增补、准入包、人工验收清单和 evidence。

### 13.2 修改

- `src/tpaa_application/historical_overview.py` 和相关 durable/API；
- `src/tpaa_application/p3_persistence.py`、`governance_registry.py`、`replay_context.py`（只扩展边界，不复制 owner）；
- `frontend/gui-v33/src/main.ts`、`style.css`、themes/icons/charts/gateway；
- G6～G12 successor/activation/closure 工具中硬编码基线与预填 PASS；
- `CROSS_LAYER_DTO_CONTRACTS.json`、API/permission/audit authorities、conformance matrix；
- R3.3 总体/工程/GUI/接口/数据/验证文档。

## 14. 必须由用户确认或亲自验收的节点

自动开发和测试推进到以下节点时，交付一份独立、逐项可勾选的中文操作清单；在此之前不要求用户反复介入。

### 14.1 三项 Metric Definition 业务确认

用户需逐项确认：

1. Kill Ratio 分母是否确认为“合格空战交战次数”，而不是发射次数；
2. Exchange Ratio 在评价方零损失时是否接受 `N_A`，而不是 infinity；
3. Mission Completion Rate 是否只计 required 目标，1.0.0 不加权；
4. pending/unknown 是否保持 pending 而不是按失败计；
5. 跨批次是否接受“先合计分子/分母再计算”；
6. 评价方、训练类型、显示精度和角色可见范围；
7. 三份候选是否批准生成 `ADMITTED` decision。

届时提供：候选定义摘要、fixture 计算示例、边界样例、变更影响和“批准/退回修改”签署模板。

### 14.2 媒体票据策略确认

用户需确认：ticket 默认 60 秒、一次性/有限重放、允许 MIME/最大文件/单 range、导出与流式读取权限，以及正式环境是否允许媒体落盘缓存。未确认前仅在测试 profile 使用候选策略。

### 14.3 GUI 实机视觉与角色任务验收

届时操作清单至少包含：

1. 启动隔离数据库并导入 `GUI_V33_FULL_V1`；
2. 以分析员、教员、数据管理员、治理审批员、审计员逐一登录；
3. 按 V01→V26 的规定任务链操作全部 26 视图；
4. 验证 V08→V24 正向入口和 V24 直达拒绝；
5. 操作 V03 媒体、2D/3D、时间轴和证据联动；
6. 核对三主题、Ribbon 两态、100%/150% DPI、1280×720 与 1600×900；
7. 全键盘走查焦点、弹窗、表格、筛选和返回栈；
8. 核对 fixture 水印、候选指标标签、空/错/降级/无权状态；
9. 生成报告 revision、执行治理提案/审批/回滚的分权任务；
10. 逐视图与 Demo 对照并记录 PASS/FAIL、截图和备注。

自动截图只能作为辅助证据，不能替代用户对产品观感、信息密度和实际任务可用性的最终判断。

### 14.4 当前不要求用户执行的交付门

安装包、Linux/Service、SBOM、许可证、漏洞、目标 workload 和生产发布验收暂缓。功能实现期间只保持清晰开放项，不用这些门阻塞 F0～F9，也不伪造完成结论。

## 15. 风险、回滚与完成语义

### 15.1 主要风险

- **定义风险**：指标业务口径未确认。控制：候选/正式状态分离，结果带 definition hash；
- **数据冒充风险**：fixture 被误当生产数据。控制：profile、classification、水印、导出标签和生产拒绝；
- **双 owner 风险**：G10 新服务重复既有 P3/WE/quality owner。控制：Application facade 复用底层 owner，架构契约扫描；
- **模型漂移风险**：DB、Canonical、DTO、前端不一致。控制：单源 codegen、lock、migration 和追踪矩阵；
- **视觉表面完成风险**：页面像 Demo 但没有业务闭环。控制：角色任务和 API/证据下钻同时验收；
- **安全回退风险**：为媒体/fixture 放宽路径或 origin。控制：opaque ticket、exact context、生产拒绝和负测。

### 15.2 回滚

- 活动基线在正式批准前保持 CB-1.17.0；candidate 激活失败直接恢复活动指针；
- DB migration 必须可回滚，回滚前验证无 candidate-only 数据或导出隔离快照；
- fixture 使用独立数据根/数据库，按 fixture lineage 精确删除；
- 前端新视图由 feature capability 控制，但不可用时显示诚实状态，不回退到 Demo 假数据；
- 媒体 ticket authority 可整体撤销，已有 ticket 立即失效并审计。

### 15.3 状态定义

本方案 F0～F9 全部自动门通过但人工确认未完成时，只能记录：

`FUNCTIONAL_IMPLEMENTATION_COMPLETE_AWAITING_ACCEPTANCE`

三项指标获准、媒体策略获准、真实角色视觉验收通过后，可记录：

`DEMO_V33_FUNCTIONAL_SCOPE_CLOSED_LOCAL_WITH_GATES`

由于交付门暂缓，即使达到后一状态，仍必须保持：

- `G12=IN_PROGRESS_EXTERNAL_DOORS_OPEN`；
- `W9=NO_GO`；
- `PRODUCT_COMPLETE=false`；
- `RELEASE_READY=false`。

只有原方案 R8/R9 的安装、跨平台、供应链、安全、目标 workload 和独立发布裁决真实完成后，才可另行改变这些状态。

## 16. 立即执行顺序

本方案批准后按 `F0 → F1 → F2 → F3 → F4 → F5 → F6 → F7 → F8 → F9` 连续实施。能在本机完成的代码、迁移、fixture、自动测试、WebEngine 与截图直接执行；到第 14 节三个节点再向用户提交精确操作清单。全程禁止推送和生产部署，禁止改写现有提交历史，禁止删除或覆盖与本方案无关的工作树修改。
