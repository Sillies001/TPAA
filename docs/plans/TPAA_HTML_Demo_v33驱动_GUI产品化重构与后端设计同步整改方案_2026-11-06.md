# TPAA HTML Demo v33 驱动的 GUI 产品化重构、后端补齐与设计同步整改方案

> 文档状态：`IN_PROGRESS_V33 / G0R～G5 已本地关闭；G6～G11 处于关闭后整改；G12 外部门开放`
> 编制日期：2026-11-06  
> 当前工作指令：2026-11-08 关闭后复核否决 G6～G11 的既有关闭声明；严格执行 `TPAA_G6至G12关闭后复核缺口全面整改与再关闭方案_2026-11-08.md`，不得以占位页、NOT_ADMITTED 或硬编码 PASS 冒充关闭。
> 替代关系：本文件替代 `TPAA_HTML_Demo驱动_GUI产品化重构与后端设计同步整改方案_2026-10-29.md` 作为后续 GUI 产品化工作的唯一实施方案。  
> 目标对象：TPAA Desktop GUI、面向 GUI 的 Application/API 投影、必要领域/存储能力、总体与工程设计后继基线。  
> 发布边界：只允许本地修改和验证；禁止推送、签名和生产部署。W9 继续保持 `NO_GO`。

---

## 1. 执行结论

v33 不是 v19 的简单样式迭代。除保留三主题、Ribbon、回放和既有专项页面外，它把产品主线扩展为：

1. V01 从单一当前批次总览改为**跨历史多批次训练综合态势与趋势入口**；
2. 新增 V26“**批次发射事件总览**”，以每枚武器发射事件（Weapon Event，WE）为独立复盘对象；
3. 明确 Training Episode、Weapon Event、Attack Cluster 三层对象及其基数；
4. 为 V04/V05/V08/V20 增加同一 WE 下的射手与目标/防御方双视角，并区分单机与编队目标侧可视化；
5. 建立 T0-S、T0-T、T1、T2、T3 及 cue/response/J 的独立事件窗口语义，允许不同 WE 窗口重叠；
6. 将“简单对抗/混合对抗/综合对抗”定义为 Batch Metadata，与 WVR/BVR/Strike WE 类别及训练科目域严格分离；
7. 增加红蓝阵营、编队成员、独立目标、CSV 导入导出等管理交互，但生产实现不得沿用 Demo 的 `localStorage`；
8. V01 新增击杀比、敌我交换比、任务达成率等任务级趋势示意，但这些不自动成为 P1 正式指标。

因此，原 v19 方案的“换壳 + 组合查询”范围不足。v33 实施必须同时完成视觉层、Application Query、领域事件投影、Canonical/DTO/权限/审计、历史聚合、事件窗口、设计文档和重新资格。

目标技术路线仍优先采用：

- PySide6 Desktop 宿主；
- Qt WebEngine 本地模块化前端；
- 精确同源的本地 FastAPI；
- Application Service 作为唯一业务入口；
- 机器权威生成 DTO、OpenAPI、前端类型和路由权限；
- QML 只作为 WebEngine 关键门失败时的替代 presentation runtime。

但 v19 的 G0 架构结论不能直接视为 v33 已通过。新版必须以 V01、V03、V04 目标视角和 V26 重新执行安全、视觉、性能、离线与打包样板。

Demo 只拥有**视觉、布局、控件和交互目标权**。Canonical、DTO、数据库、指标、权限、审计、裁决和发布语义以批准的机器权威与设计基线为准。Demo 中的合成数据、固定种子随机数、浏览器存储、前端业务公式和静态裁决不得进入生产路径。

---

## 2. v33 输入基线冻结

### 2.1 文件身份

以下四个文件共同构成本方案的输入，不得只读取 HTML 而忽略三份设计补丁：

| 文件 | 字节数 | SHA-256 | 用途 |
|---|---:|---|---|
| `TPAA_V33与三份文档更新/TPAA_训练复盘交互Demo_v33.html` | 575155 | `7AA5FF433FCAA49C3A54AC592ACB43C42EE98FD944D4FB66DE6E75BAC2401A9A` | 视觉、控件、交互和布局目标 |
| `TPAA_V33与三份文档更新/TPAA_V8.0_总体设计方案_Patch_历史多批次总览与攻防双视角_v1.3.md` | 35300 | `ABC6B000B846DBE2E367CB5AF67EFE7F152EBEF1A26AB0FC104918A7B37DE3BB` | 总体语义与产品边界 |
| `TPAA_V33与三份文档更新/TPAA_ED-2.0_工程设计方案_Patch_历史多批次聚合与攻防复盘_v1.3.md` | 38685 | `26BE99DB27D726BD25830281DA0023202BCB7B048BE1D02AC81278265666890F` | 服务、投影、DTO/API、窗口和验收候选设计 |
| `TPAA_V33与三份文档更新/TPAA_V8.0_总体与工程设计方案_Patch差距清单_v1.3.md` | 21594 | `402C3941C9BE625B488C8E3425ED8FEE7D0C3BA78F4084471E17688F231A6896` | O-GAP-01～19、E-GAP-01～后续项及生产闭包 |

任何文件发生字节变化，都必须建立新的 Demo/补丁版本、哈希和差异报告，不能继续沿用 `GUI-DEMO-V33-2026-11-05` 标识。

### 2.2 基线优先级

冲突时按以下顺序裁决：

1. 已锁定机器权威、Core Rules、安全/权限/审计和发布门；
2. 经本波次批准的后继 Canonical、DTO、route、state/reason、metric authority；
3. 三份 v1.3 设计补丁中不违反上两项的业务语义与工程规则；
4. v33 HTML 的最终有效定义（后定义覆盖前定义）；
5. 旧 v19 Demo 和 2026-10-29 方案，仅作为历史对照。

视觉冲突以 v33 最终渲染为目标；业务字段、算法、权限和数据真实性冲突不得以“严格照 Demo”为由绕过机器权威。

### 2.3 v33 文件内部不一致的裁决

v33 是多轮补丁叠加的单文件原型，存在必须在生产化前消除的内部不一致：

| 不一致 | 证据 | 生产裁决 |
|---|---|---|
| HTML `<title>` 仍写 V30 | 文件第 1 行 | 文件名、SHA 和 `window.TPAA_V33.version` 决定目标版本；生产构建信息统一为 v33 基线标识 |
| `TPAA_V33.preservedPages` 漏列 V25 | 文件尾部元数据 | V25 实际有标题、路由和页面函数，必须保留；最终目标为 V01～V26 共 26 个视图 |
| V04～V21 存在多次标题/函数覆盖 | 多轮 patch | 只采纳最后一次生效定义；G0R 生成最终 DOM/路由清单，不按首次声明实现 |
| 红蓝/编队关系写入 `localStorage` | 关系配置补丁 | 生产改为受控 Context/Batch 配置、版本、权限和审计；浏览器存储禁止作为业务事实 |
| 大量固定种子随机/合成曲线 | `R/G/rg` 及页面 fixture | 只用于视觉；生产 DTO 缺失时显示不可用，不在前端补造曲线 |
| V01 任务级指标使用演示公式 | v29～v33 代码和补丁文档 | 先经 Metric Authority 准入；未批准时显示“演示口径/正式指标未配置”或隐藏正式结论 |

### 2.4 v19 基线和已产生资产的处置

以下本地资产保留，统一标记为 `SUPERSEDED_BY_GUI_DEMO_V33`，不得删除，也不得继续作为关闭依据：

- `docs/gui/demo-v19/`；
- `docs/compliance/GUI_DEMO_CONFORMANCE_MATRIX.json`（v19 25 页矩阵）；
- `evidence/gui-g0/` 中 v19 的 75 张 WebEngine 和 9 张 QML 样板截图；
- `ADR-GUI-001/002/003` 的 v19 结论。

新版 G0R 必须新增 `docs/gui/demo-v33/` 和 v33 矩阵/证据。若 ADR 技术结论不变，仍需发布带 v33 样板证据的新修订，不能只改文件日期。

---

## 3. 当前代码与工作树保护

代码仓库仍位于：

`2_SoftwareDevelopment/TPAA_AUDIT_a00ed06/TPAA-a00ed06f8ef862ad28ad7c7e1197a99ade8c7713`

检查时分支为 `local-r8-review`，HEAD 为 `b113a172004c9698924fd53c14723f93670eee8a`。工作树包含关闭后整改、中文化和 v19 G0 的未提交修改。新版实施必须：

1. 先记录现有 dirty paths、diff stat、未跟踪文件和关键文件 hash；
2. 不执行 `reset --hard`、`checkout --` 或覆盖式复制；
3. 以最小补丁区分“W0～W9/关闭后整改”“v19 G0 历史资产”“v33 新波次”；
4. 不把 v19 资产删除来制造干净状态；
5. 新波次形成可独立审查的本地提交前，不运行要求 clean tree 的发布打包器；
6. 所有版本升级只发生在后继目录，不原位修改 R3.3、CB-1.4.0 或 CB-1.5.0。

当前代码搜索未发现正式的 `WeaponEvent`、`AttackCluster`、`EventWindowProjection`、`HistoricalTrainingOverview` 或双视角 read model。已有 `training_type`/`training_type_set` 主要用于 BASIC/WVR/BVR/STRIKE 科目/纵向样本，不能直接等同于 v33 的 Batch 级“简单/混合/综合对抗”。这必须使用不同字段名和受控枚举，避免语义冲突。

---

## 4. v33 最终产品信息架构

### 4.1 五模块 Ribbon 与 26 个视图

| 一级模块 | 分组/入口 | 目标视图 |
|---|---|---|
| 总览 | 历史综合入口 | V01 训练与装备数据总览 |
| 训练评估 | 架次综合 | V02 架次综合复盘 |
| 训练评估 | 单机专项 | V07 基本飞行、V05 视距内空战、V04 超视距空战、V06 对地攻击 |
| 训练评估 | 编队专项 | V19 基本飞行编队、V20 视距内编队、V08 超视距编队、V21 对地攻击编队 |
| 训练评估 | 多架次 | V09 多架次综合分析 |
| 回放 | 战术回放工作台 | V03 |
| 装备性能 | 总体/分项/趋势 | V10～V16 |
| 数据与系统 | 质量、报告、管理、导入、主题 | V17、V18、V22、V23、V25 |
| 条件下钻 | V08 协同攻击 | V24，只能从满足条件的 V08 事件进入 |
| 条件下钻 | V01 已加载批次 | V26 批次发射事件总览，只能携带 exact Batch/Release/Context 进入 |

V25 虽未出现在 v33 尾部 `preservedPages` 数组中，但实际可达且页面定义完整，因此属于目标范围。V26 是新增受控下钻页，不得把 V01 中仅有汇总样例或未解析批次错误路由到当前演示批次的明细。

### 4.2 公共 Shell 与交互骨架

必须保留并产品化：

- 五模块主菜单、分组 Ribbon、展开/收起；
- Graphite、Tactical、Light 三主题，默认 Graphite；
- 全局 Batch/Session/Release/Context、当前 WE、Perspective、Scope、时间游标和证据游标；
- 级联筛选、下钻、返回栈、精确时刻跳转；
- 键盘可达、焦点可见、表格/图表 tooltip、中文标签与必要缩写说明；
- 加载、空、部分覆盖、不可用、待确认、无权限、错误、系统错误等显式状态；
- 1600×900 参考几何、1280×720 与高 DPI 下受控滚动/局部重排；
- 主题、Ribbon 和页面切换不得改变业务 payload、权限或资格状态。

### 4.3 V01 历史多批次训练综合总览

V01 回答“历史训练如何变化”，不承担单批次全过程复盘。统一筛选上下文包括：

- 起始日期；
- 结束日期；
- 机型；
- Batch 训练类型（全部、简单对抗、混合对抗、综合对抗）。

同一 Batch 集合必须驱动所有 KPI、趋势图、列表和摘要。页面信息架构冻结为：

1. 顶部六张 KPI：历史批次数、飞行架次数、Episode 数、WE 数、已正式裁决事件数、数据资格摘要；
2. 第一行：任务级指标趋势、历史训练活动趋势；
3. 第二行：训练结果与裁决状态趋势、WVR/BVR/Strike 行为类别构成、装备性能历史趋势；
4. 第三行：历史训练批次列表、选中批次摘要；
5. 已加载且 exact 明细可用的批次才显示“进入 V26”；仅有汇总/待解析批次保持不可进入；
6. V09/V16 作为深度趋势入口，V01 不复制其全部分析。

V33 参考几何：外层 `top=166px`、`height=694px`，网格行为 `36 / 68 / 168 / 168 / minmax(180,1fr) / 12px`，gap 10px；KPI 子卡 `height=min-height=65px` 且在 68px 行中居中。参考画布下第三行约 192px，批次列表内部滚动。验收必须测量真实子元素 bounding box，而不是只测父容器。

### 4.4 V26 批次发射事件总览

V26 绑定一个 exact Batch/Release/Context，并提供：

- 被评估方（蓝方/红方）主视角；
- 行为类别 WVR/BVR/Strike；
- 飞机/目标、架次、编队、裁决状态、发射方向筛选；
- WE、Attack Cluster、已裁决、待确认等不同基数统计；
- 全批次发射事件时间线；
- 每枚武器独立 WE 清单，齐射只通过 Attack Cluster 关联；
- 未发射行为的独立列表，不创建虚假 WE；
- 单机/编队复盘、事件窗口和精确回放入口；
- 红蓝/编队关系配置入口，但生产配置由 Context 服务、权限和审计拥有。

V26 不直接读取原始文件或数据库，也不自行识别/合并事件。所有列表、类别、关系、窗口、裁决和状态由 Application/World/Event/Evidence 服务投影。

### 4.5 双视角专项页面

同一个 WE ID 下：

- V05：WVR 单机；V04：BVR 单机；
- V20：WVR 编队；V08：BVR 编队；
- 均支持 `shooter` 与 `target/defender` 视角；
- V06/V21 Strike 只支持 shooter 视角；
- V07/V19 基本飞行不是 WE 强制入口；
- Perspective 只改变投影和界面，不改变事件、射手、目标和正式裁决事实。

单机目标侧页面必须包含：目标侧来袭态势、威胁信息来源、离散告警—响应—结果事件链、目标动作/遥测变化、结果与证据条。编队目标侧页面必须包含：成员关系/受威胁成员、成员 P_i/A_i 矩阵、成员动作时序、信息共享关系、团队/成员结果证据。

目标页不得重复独立 Event Window 的多轨甘特图。目标页只显示离散过程节点，并提供“打开事件窗口”入口。

### 4.6 Event Window

每个 WE 独立表达：

| 锚点/状态 | 含义 |
|---|---|
| T0-S | 射手侧相关上下文/前置证据起点 |
| T0-T | 目标侧威胁前上下文起点，不等同首次 cue |
| T1 | 实际发射/释放 Session Time |
| T2 | 权威武器终止时刻；未知则保持未知 |
| T3 | 结果观察结束或当前数据覆盖边界 |
| cue/alert | 目标侧首次可获得威胁信息 |
| response | 首次可观察防御响应 |
| J time | 批准裁决时间，可晚于 T2 |

窗口采用半开区间 `[start,end)`；不同 WE 可重叠，不允许以“上一事件结束 + 一个采样间隔”强制切片。Weapon terminal、Adjudication、Observation-window 必须是三个独立状态维度。

### 4.7 V23 批次登记与数据导入

导入工作台必须新增 Batch 训练类型显式确认，并完成：登记、持久化、审计、解析、归并、资格和 V01 纳入条件。训练类型未知时保持 `UNCLASSIFIED/PENDING_CONFIRMATION`，不得默认综合对抗。文件/目录选择、CSV 和本地导出通过受控 Desktop ticket/bridge，不把任意路径暴露给 Web 前端。

### 4.8 V25 主题管理

保留 Tactical/Graphite/Light 预览和应用。默认 Graphite，主题只影响表现。除非后续 ADR 明确批准，主题仅会话内生效；不得进入业务 Release，也不得使用浏览器 localStorage 保存跨用户偏好。

---

## 5. v19→v33 变更矩阵

| 领域 | v19 方案 | v33 新目标 | 方案影响 |
|---|---|---|---|
| 视图数 | V01～V25 | V01～V26 | 所有 registry、导航、视觉矩阵和 DoD 改为 26 页 |
| V01 | 当前训练/装备概览 | 跨历史 Batch 聚合与趋势 | 新增历史 Query Service、Batch 元数据、任务/装备趋势 |
| V26 | 无 | 单 Batch WE 工作台 | 新增 WE/Cluster/Window/Perspective 主线 |
| 事件对象 | 以页面/架次事件为主 | 每枚武器一个稳定 WE | 需要 Event owner、去重、identity、关系和状态合同 |
| 齐射 | 未独立定义 | WE 独立、Cluster 关联 | 统计/裁决不得按 Cluster 代替 WE |
| 双视角 | 以射手/评估页为主 | WVR/BVR 单机与编队射手/目标双投影 | 新增 observer/actor-specific DTO 和可视化 |
| 时间窗口 | 回放/事件轨 | side-specific T0-S/T0-T/T1/T2/T3 | 新增 Resolver、重叠查询、状态/reason、懒加载 |
| 批次类型 | 未定义 | 简单/混合/综合对抗 Batch Metadata | Canonical/Import/审计/筛选全链路 |
| 红蓝/编队 | 页面示意 | 时变 Context，带管理入口 | 禁止 localStorage；需版本、有效时间、权限和审计 |
| 任务级指标 | 无正式 V01 趋势 | 击杀比、敌我交换比、任务达成率示意 | 独立 Metric 准入；未批准不得正式展示 |
| 视觉门 | 25×3×Ribbon | 26×3×Ribbon，另含 V01 两分辨率盒模型和双视角状态 | 全量基线作废重建 |

---

## 6. 不可破坏的业务与工程不变量

1. W 不替代 P_i；目标侧只能显示当时可获得的信息或明确标注的 retrospective/inferred 信息。
2. Action 不替代 J；没有批准 J 时不得推断官方命中、损失、任务完成或成功防御。
3. Weapon terminal、Adjudication、Observation-window 分开；数据到末尾不等于武器终止。
4. Team 结果不复制给个人，个人结果不平均制造 Team 能力。
5. 一个 Episode 可包含多个 WE；每枚实际发射一个 WE；Attack Cluster 只表达关系。
6. 批次训练类型、WE 行为类别和 Episode/Stage 训练科目域为三个不同维度。
7. Batch 聚合不拼接跨 Session 原始时间轴；跨 Session 只聚合 exact refs 和批准产品。
8. 所有时间使用权威 Session Time、TimeTransform、clock segment 和 Alignment Domain；`UNRESOLVED/INVALID` 不进入正式统一窗口。
9. 历史页面必须 exact Batch/Session/Release/Context/Policy/Catalog/Model 绑定，不允许 latest/current 回退。
10. GUI 不检测 WE、不分类武器、不计算任务比值、不推断根因、不重算装备性能。
11. 缺失、未知、不适用、数据不足、部分覆盖、未闭合、待裁决、无权限和系统错误分别呈现。
12. Demo 合成值不得成为后端 fixture 之外的产品默认值。
13. 权限必须由服务端 route→permission→audit 门执行；隐藏按钮不是授权。
14. P1 116 项指标和 661 项输入绑定不因 v33 自动改变；新任务级指标需单独治理。
15. R3.3、CB-1.4.0、CB-1.5.0 字节保持不变。

---

## 7. 目标运行架构与安全边界

### 7.1 拓扑

```text
TPAA Desktop Host (PySide6)
  ├─ Window / lifecycle / crash fallback / DPI / native dialogs
  ├─ Off-the-record QWebEngineProfile
  ├─ Exact-origin request interceptor
  ├─ Minimal file/print ticket bridge
  └─ Local Backend Controller
       └─ 127.0.0.1:<owned-random-port>
            ├─ Authenticated FastAPI
            ├─ GUI Static Dist
            ├─ GUI Query/Application APIs
            └─ Existing governed product APIs
```

前端只访问精确 origin。Bearer 与 Desktop nonce 由宿主拦截器注入，JavaScript 不得读取。Profile 必须 off-the-record，禁用持久 Cookie/缓存/密码/Service Worker、任意下载和远程调试。生产静态资源只来自带 hash 的本地 `dist`，禁止 CDN 和 dev server。

### 7.2 单一路由权威

`API_ROUTE_AUTHORITY` 是 route_id、method、path、permission、audit、profile exposure 的唯一权威。Desktop policy、middleware、WebEngine interceptor 和 Python adapter 都引用 route_id，不维护平行 allowlist。新 GUI mutation 默认拒绝，只有批准 route 才能开放。

### 7.3 文件、CSV、报告和媒体

- 文件选择由宿主返回不透明短期 ticket；
- 上传按 ticket 和 route permission 执行；
- CSV 模板/导出、报告 PDF、媒体 Range 均需显式 content type、大小、范围和审计策略；
- 不允许前端接收任意本地绝对路径；
- 不允许 Blob 下载绕过 Desktop 下载门；
- renderer crash、宿主退出和后端退出不得遗留孤儿进程或跨用户缓存。

### 7.4 前端工程

采用 TypeScript + Vite 的模块化生产构建，建议目录：

```text
frontend/
  app/           # 启动、路由、错误边界
  registry/      # Ribbon、V view、permission/feature 映射
  state/         # DomainSelection、Batch、WE、Replay、Presentation
  services/      # 生成类型的 API client、取消、缓存、range
  components/    # shell、筛选、panel、chart、timeline、evidence、status
  views/         # V01 ... V26
  themes/        # tactical/graphite/light semantic tokens
  generated/     # 由 machine authority 生成，禁止手改
```

生产包只包含确定性构建的 hashed dist；必须验证两次干净构建 hash 一致并写入 package manifest/SBOM。

---

## 8. P 语义、V 视图与权限边界

P01～P13/P1～P6 继续表达后端能力、数据产品和治理语义；V01～V26 只表达用户任务视图。V 页面可以组合多个 P 投影，但不能重定义 P 指标或发布语义。

新增机器权威 `GUI_VIEW_CONTRACT` 至少包含：

- view_id、title、module、entry type；
- required context、allowed predecessor、return target；
- P capability dependencies；
- query route_ids、mutation route_ids；
- required permissions、feature gates；
- loading/empty/degraded/error/forbidden/N_A states；
- replay/deep-link contract；
- visual baseline ids。

V24 只能由合格 V08 协同事件进入；V26 只能由已加载 exact Batch 进入。V04/V05/V08/V20 的 target perspective 必须同时满足对应 WE、目标身份和目标侧投影可用性；V06/V21 target perspective 永远 fail-closed 为不适用。

---

## 9. 领域、Application 与存储整改

### 9.1 先裁决、后实现的对象

| 概念 | 所有者与生命周期 | 必须裁决的问题 | 禁止做法 |
|---|---|---|---|
| `BatchWorkset` | Application 查询上下文，可临时组合 exact refs | 是否仅为 read scope；如何绑定 Session/Release/Context | 把临时筛选对象直接当持久化 Batch |
| `BatchRegistration/BatchMetadata` | 导入登记和审计持久对象 | 稳定 ID、日期、训练类型、状态、来源、修改审计 | 只保存在浏览器状态或从 WE 类别猜测 |
| `WeaponEvent` | 唯一 Event owner 发布的事件或受控事件投影 | 复用既有 Event node 还是新增持久对象 | GUI/Metric 插件各自重新检测 |
| `AttackCluster` | WE 之间的关系/分组 | 关系类型、稳定性、人工修订和 provenance | 合并多枚 WE 为一个事件 |
| `EventWindowProjection` | 可重建、版本化的 side-specific 投影 | 是否持久缓存；resolver/version/reason/coverage | 用 UI 刷选范围当权威窗口 |
| `PerspectiveProjection` | 同一 WE 的 shooter/target、individual/team read model | P_i/A_i/J/geometry/series 权限和缺失语义 | 用 W 或另一方证据填补 |
| `Force/Formation Context` | 有效时间 Context artifact | 红蓝阵营、成员、独立目标、变更版本和审计 | localStorage 作为业务事实 |
| `HistoricalOverview` | 跨 Batch 聚合 read model | exact batch set、分页、可比性、统计截止 | 前端拼接页面当前状态 |
| `TaskMetricDefinition` | Metric Authority | 候选指标是否准入及正式公式 | 把 Demo 公式直接写入前端/服务 |

G1 必须分别形成 capability admission。若 `WeaponEvent` 可由既有 Event/Relation 模型完整表达，则优先使用后继 authority 的受控 subtype/relations，避免平行表；若无法满足身份、状态、索引或审计要求，再批准新持久对象与 migration。`BatchWorkset` 与 `BatchRegistration` 必须分开，不能用一个含混的 `Batch` 同时承担临时查询和长期业务身份。

### 9.2 建议服务边界

以下为逻辑职责名，不是绕过 authority 的固定 Python 类名：

| 服务 | 唯一职责 | 关键输出 |
|---|---|---|
| `BatchRegistrationService` | 登记稳定 Batch、训练类型、日期、Context 和导入来源 | BatchMetadata revision + audit |
| `HistoricalTrainingOverviewQuery` | 在同一 query context 下聚合 V01 | KPI、趋势、列表、摘要、可进入 V26 标志 |
| `WeaponEventDetector` | 从批准事实源检测候选发射 | 候选 event + provenance |
| `WeaponEventIdentityService` | 去重并生成稳定 WE ID | identity/revision/supersession |
| `WeaponEventEpisodeLinker` | 将 WE 关联 exact Episode/Stage | relation + reason/confidence |
| `WeaponCategoryResolver` | 按版本规则分类 WVR/BVR/Strike/Unknown | category、rule version、exception |
| `AttackClusterResolver` | 建立齐射/关联攻击关系 | cluster relations，不改变 WE 基数 |
| `EventWindowResolver` | 解析 T0-S/T0-T/T1/T2/T3 与状态 | side windows、coverage、reason、version |
| `PerspectiveProjectionService` | 生成 shooter/target、individual/team 投影 | P_i/A_i/J/geometry/series/relation read models |
| `TargetDefenseDebriefQuery` | 组装目标侧视觉 DTO | 单机/编队目标页投影 |
| `BatchEventQueryService` | V26 筛选、统计、列表、分页 | summary/list/timeline/availability |
| `ReplayContextService` | 将 WE/视角映射到 exact replay | Release/Context/time/ranges/media refs |
| `TaskMetricTrendService` | 依据批准定义计算跨批次任务趋势 | numerator/denominator/status/quality |
| `EquipmentTrendQuery` | 返回可比装备指标摘要 | metric version/unit/config/sample/eligibility |

GUI、REST 和 Metric/Assessment 插件不得绕过这些 Application 边界读取原始文件或 Canonical 表。Detector 和状态机只能有一个 owner；其他模块消费已发布事件。

### 9.3 WE 发现、身份和修订

实现合同至少包括：

1. 事件源优先级、发射/释放触发条件和 source provenance；
2. 稳定 ID 生成材料及冲突处理；
3. 幂等重放、重复源记录合并和 late-arriving data；
4. detected/validated/published/revised/superseded 等状态；
5. Episode/Stage 关联基数和未关联 reason；
6. 武器类型原值、规范值、类别规则版本、几何校验和分类例外；
7. 人工分类修订保留旧值、新值、操作者、时间、原因和 supersession；
8. J 晚到、T2/T3 更新和窗口重算不得覆盖历史 revision。

### 9.4 Event Window Resolver

Resolver 必须：

- 分别解析 shooter/target 起点，不将首次 cue 当作 T0-T；
- 保存 observed/configured/inferred 的证据类别；
- 允许同 Episode/Cluster 的窗口重叠；
- 处理 clock reset、gap、series boundary、authority switch 和 alignment failure；
- 将 `TERMINAL_UNKNOWN`、`RESULT_PENDING`、`WINDOW_OPEN/PARTIAL/CLOSED`、`ALIGNMENT_UNRESOLVED` 分开；
- 以 release/event/perspective/window-resolver-version 作为缓存键；
- 只在打开 WE 时懒加载高频序列；默认列表只加载摘要；
- 对历史 revision 可重现，不受当前规则静默影响。

### 9.5 目标/防御方 read model

候选投影及最低字段组：

| 投影 | 最低内容 |
|---|---|
| `TargetThreatGeometryProjection` | geometry kind、time、frame、position/heading/range（可用时）、source、quality、schematic flag |
| `TargetThreatCueProjection` | cue type、source entity/type、first available time、observed/inferred、evidence refs |
| `TargetResponseProjection` | observable action、start/end、actor、source、confidence、reason |
| `TargetStateSeriesProjection` | parameter、unit、time base、points/ranges、gaps、coverage、LOD |
| `TargetOutcomeEvidenceProjection` | terminal state、J state/revision、target state、mission effect、evidence refs |
| `TeamDefenseFormationProjection` | effective-time membership、threatened member、real/schematic geometry |
| `TeamMemberThreatResponseProjection` | member P_i/A_i first times、source、status、response interval |
| `TeamDefenseEventTimelineProjection` | member discrete events，非窗口区间 |
| `TeamInformationRelationProjection` | timestamped communication/TDL/Relation evidence；无证据不画边 |
| `TeamDefenseOutcomeProjection` | member/team result separation、coverage、quality |

任何图表数据必须携带 unit、time base、source、coverage、gap、provenance 和 reason code。缺真实几何显示 `UNAVAILABLE/SCHEMATIC_ONLY`；缺曲线不画默认趋势；缺通信证据不生成共享方向。

### 9.6 Batch 训练类型与导入

为避免与现有 BASIC_FLIGHT/WVR/BVR/STRIKE `training_type` 混淆，后继 authority 应使用明确名称，例如 `batch_training_type`。候选枚举：

- `SIMPLE_OPPOSITION` / 简单对抗；
- `MIXED_OPPOSITION` / 混合对抗；
- `COMPREHENSIVE_OPPOSITION` / 综合对抗；
- `UNCLASSIFIED` / 未分类。

登记流程：创建 Batch Registration → 用户显式确认类型 → 验证日期/身份/Context → 审计提交 → 解析/归并 → 数据资格 → 纳入 V01。不得以默认下拉值代替确认，失败/缺失保持待处理。修改训练类型必须创建 revision 与审计事件。

### 9.7 V01 聚合和任务级指标

同一查询请求应生成可追踪的 `query_context_id` 和 exact Batch ID 集合。所有面板引用该集合。计数规则：

- Batch、Sortie、Episode、WE 分别按稳定 ID 去重；
- WE 按每枚发射计数，不按 Cluster；
- 已裁决仅统计批准状态；
- WVR/BVR/Strike 未分类/冲突单列；
- 导入成功不等于数据资格通过；
- 聚合记录过滤、authority version、统计截止和来源。

击杀比、敌我交换比、任务达成率只能在 Metric Authority 批准后由服务计算。每个结果返回 numerator、denominator、scope、evaluated side、J authority、definition version、sample count、eligibility、status/reason。分母 0 返回 null + reason；跨 Batch 比值由汇总分子/分母重算，不简单平均。

### 9.8 红蓝、编队和独立目标

Context 必须支持有效时间成员关系：

- formation_id、side、member aircraft、independent target；
- valid_from/valid_to 与 source；
- 同一时刻一个 aircraft 不得属于两个编队；
- 未分配/冲突显式状态；
- CSV 预检、dry-run、提交和 revision；
- 修改权限、操作者、原因和审计；
- 切换被评估方只改变投影，不改写原始 WE/J。

---

## 10. DTO、API、权限与审计方案

### 10.1 候选 DTO

Machine Authority First 评审至少覆盖：

- `GuiCatalogDTO`、`GuiBootstrapDTO`、`GuiSelectorDTO`；
- `HistoricalTrainingOverviewDTO`；
- `BatchOverviewSummaryDTO`、`BatchListItemDTO`；
- `TaskMetricTrendDTO`、`EquipmentMetricTrendDTO`；
- `BatchEventSummaryDTO`、`WeaponEventListItemDTO`；
- `WeaponEventDetailDTO`；
- `WeaponEventPerspectiveDTO`；
- `WeaponEventWindowDTO`；
- `EpisodeEventRelationDTO`；
- 9.5 节的目标单机/编队可视化投影 DTO；
- `BatchRegistrationDTO`、`BatchTrainingTypeRevisionDTO`；
- `ForceFormationContextDTO`、`ContextRevisionDTO`；
- `ReplayContextDTO`、`SeriesRangeDTO`、`MediaManifestDTO`；
- `UnavailableStateDTO` 与统一 reason/coverage/provenance 结构。

JS 可见 Session Time 继续按现有 transport rule 使用 decimal string，禁止浮点微秒。所有 enum、nullable、oneOf、分页和兼容策略进入 `CROSS_LAYER_DTO_CONTRACTS`，再生成 Python/TypeScript 类型。

### 10.2 候选逻辑资源

下表只定义资源需求，G1 批准后才冻结真实 route：

| 逻辑资源 | 主要消费者 | 关键约束 |
|---|---|---|
| GUI catalog/bootstrap/selectors | Shell/全部视图 | role/feature/route id、精确默认原因 |
| historical overview | V01 | 同一 query context、cursor pagination、exact batch set |
| batches list/detail | V01/V26 | Release/Context/qualification/availability |
| batch registration/training-type revision | V23 | mutation、idempotency、audit、revision |
| batch weapon-events | V26 | filters、cursor、summary、WE/Cluster 基数 |
| episode weapon-events | V26/Event Window | exact Episode/Release |
| weapon-event detail | V04～V08/V20/V21/V26 | stable WE revision |
| weapon-event perspective | 双视角页 | shooter/target、individual/team、permission |
| weapon-event window | 独立窗口 | side、resolver version、overlap、reason |
| replay context/range/media | V03/专项页 | exact Release、range、LOD、ticket |
| force/formation context | V23/V26 | effective time、revision、audit |
| category exception review | V22/V26 | reviewer permission、old/new/rule version |
| task/equipment trends | V01/V09/V16 | metric authority、comparability、eligibility |

### 10.3 权限矩阵

至少区分：

- 历史 Batch 列表/明细可见范围；
- V26 WE 摘要与证据详情；
- shooter 与 target perspective；
- 原始/敏感几何、媒体和通信证据；
- Batch Training Type 创建/修改；
- Force/Formation Context 修改；
- WE 分类例外复核；
- Attack Cluster/关系人工修订；
- J revision 和正式报告/证据导出；
- 系统治理和审计检索。

每个 route authority 记录 resource scope、permission、audit event、read/write、profile exposure 和 ownership/classification。未知 mutation fail-closed。测试必须证明直接调用 API 仍被拒绝，不能只验证按钮隐藏。

### 10.4 审计事件

必须审计：

- Batch 登记和训练类型 revision；
- Context/红蓝/编队成员 revision；
- WE 分类例外确认/修订；
- Cluster/Relation 人工修订；
- Window resolver/backfill/replay 版本切换；
- J/Metric Definition revision；
- 敏感 evidence/media 读取和导出；
- 正式报告创建、审批、导出；
- GUI 管理 mutation 的失败和拒绝。

审计记录不得包含 Bearer、Desktop nonce、未脱敏绝对路径或超出策略的敏感 payload。

### 10.5 分页、性能和取消

G0R/G1 先测量，G11 冻结正式数值。架构必须预留：

- V01 Batch cursor pagination；
- V26 WE cursor pagination/virtualization；
- Event Window overlap index；
- Series range + max points + LOD，并保留 extrema/event anchors；
- 请求取消、去重、超时、stale response 丢弃；
- release/event/perspective/version 隔离缓存；
- 背景预取只限当前允许资源；
- 大批次、成员、事件和媒体的资源上限与明确降级状态。

---

## 11. 后继机器权威与版本策略

### 11.1 版本建议

| 维度 | 建议 | 理由/条件 |
|---|---|---|
| Overall | TPAA V8.0 | 方法与产品主版本不变 |
| Engineering Design | ED-2.1 | GUI runtime、WE/Window、历史聚合和安全拓扑均超出纯 Patch |
| Design Rebaseline | R3.4 | R3.3 字节冻结，建立后继完整包 |
| Core Baseline | CB-1.6.0 | 新 route/DTO/state/reason/可能的 logical model |
| DB schema | 先保持 1.9.0，持久对象批准时升 1.10.0 | 只有 projection-only 时不应无故升级；Batch/WE/Context 新持久对象需要 migration |
| API | v1 additive | 不重定义现有 route；破坏性变更另行升 major |
| GUI View Contract | 1.0.0-v33 | 首次冻结 V01～V26 |
| Cross-layer DTO | 后继 1.1.0 候选 | 以 authority diff 决定正式版本 |
| P1 Metric Catalog | 1.14.0 起步 | 任务级指标未批准前不增加；批准后独立升级 |

三份 v1.3 Patch 声称适用 ED-2.0/CB-1.4.0，而当前仓库已经使用 CB-1.5.0。实施前必须先对齐 CB-1.5.0 的 route、DTO、model 和 source provenance，再构造 CB-1.6.0；不得从 CB-1.4.0 分叉或覆盖 CB-1.5.0。

### 11.2 Machine Authority First 顺序

1. 冻结 v33 view/control/interaction registry；
2. 批准 BatchWorkset/BatchMetadata、WE、Cluster、Window、Perspective 的能力准入；
3. 更新 Core Logical Model/Relation/Context/State/Reason authorities；
4. 更新 DTO contracts；
5. 更新 route/permission/audit authority；
6. 需要持久化时新增 schema migration、backfill/replay 和 rollback；
7. 任务级指标通过 Metric Definition 准入；
8. 生成 OpenAPI、Python DTO/model、TypeScript types、catalog；
9. authority diff、hash、lock、compatibility 和 validator 全通过；
10. 才允许实现 Application/API/GUI。

### 11.3 后继锁绑定

后继 `BASELINE_LOCK`、`SOURCE_PROVENANCE`、`PACKAGE_MANIFEST` 必须绑定：

- R3.3 package manifest hash；
- CB-1.4.0 和 CB-1.5.0 locks；
- v33 HTML hash；
- 三份 v1.3 Patch hash；
- 本整改方案 hash；
- frontend lock/dist hash；
- migration、OpenAPI、generated types、SBOM 和 closure evidence。

v19 SHA 作为历史 lineage 保留，但不再是当前 GUI target hash。

---

## 12. 总体与工程设计同步范围

三份 Patch 是输入材料，不是可直接替换 R3.3 的最终包。G1/G12 必须同步：

| 文档/权威 | 必修订内容 |
|---|---|
| 03 总体方案 | V01 历史入口、V26 单批次主线、WE/Cluster、双视角、窗口、Batch 类型、26 视图 |
| 03A 训练效果 | Episode 多 WE、任务级指标准入、P_i/A_i/J、Individual/Team 边界 |
| 04 工程公共基线 | Event owner、身份、状态分离、时间/缺失/provenance、依赖方向 |
| 05A 数据/Canonical/Context/Episode | Batch Metadata、有效时间 Force/Formation、TimeTransform、迁移 |
| 05B World/Stage/Event/Relation | WE subtype/对象、Cluster、Episode 关系、状态机、Target relations |
| 05E 指标计算 | 任务指标定义、跨 Batch 聚合、Series/LOD/quality |
| 05F Application/API/DTO | 全部 query/command、DTO、分页、权限、审计、reason |
| 05G GUI | v33 26 视图、V01 几何、V26、双视角、独立窗口、状态/键盘/主题 |
| 05H 部署/性能/安全 | WebEngine、CSP、static dist、缓存、性能、renderer 恢复、SBOM |
| 05I Human/Team/Mission/Joint | 成员 P_i/A_i、编队防御、任务目标/J、scope |
| 06/07 追溯与验证 | O-GAP/E-GAP、route/DTO/model/test/evidence 双向映射 |
| 09 发布包 | 从后继 authority 重新生成，不手工拼接 |
| Machine authorities | model/DTO/route/permission/audit/state/reason/metric/rule/migration |

05G 必须包含 v33 最终 DOM/控件清单和允许视觉偏差；不能只放截图。设计文件不得声明 Demo 合成指标已经成为正式能力。

---

## 13. 前端状态、导航与组件整改

### 13.1 状态分层

```text
DomainSelection
  Batch / Session refs / Release / Context / Policy
  Sortie / Episode / Stage / WE / Cluster
  Perspective / Scope / evaluated side / formation / member

ReplayState
  exact replay context / cursor / brush / ranges / media / transcript

NavigationState
  current view / approved predecessor / return stack / deep-link

PresentationState
  theme / ribbon / panel expansion / report zoom / local table layout
```

业务选择必须可序列化为受控 deep-link，并在授权/可用性变化时 fail-closed。PresentationState 不进入业务 Release。页面内切换 WE 时保留当前允许的 view/scope/perspective，并重新加载对应投影；切换 Batch 必须清除不属于新 Batch 的 WE、cursor 和 evidence selection。

### 13.2 公共组件

至少实现：

- ProductShell/Ribbon/ContextBar/StatusBar；
- SelectorCascade、BatchFilter、EventSelector、PerspectiveSwitch；
- Loading/Empty/Partial/Unavailable/Forbidden/Error panels；
- Metric/Evidence cards、Quality badges、Reason tooltip；
- TimeAxis、DiscreteEventChain、EventWindowDialog；
- Track/Geometry canvas、Series chart、Member matrix、Relation graph；
- Cursor/brush/hover/highlight linked interaction；
- Virtualized table/list、internal scroll container；
- Report viewport、file ticket picker、governed download；
- keyboard/focus/accessible name/live region support。

### 13.3 前端禁止项

- 不使用 localStorage 保存 Batch/Context/关系/权限或业务结果；
- 不在页面函数中计算 WE 分类、J、任务比值、装备可比性或窗口边界；
- 不用随机/默认曲线填满空状态；
- 不把 GraphQL/REST 原始错误直接显示给用户；
- 不以字符串标题判断权限或类别；
- 不使用 latest/current 隐式 fallback；
- 不将 URL 查询参数未经验证直接变成文件路径或 SQL/filter 表达式。

---

## 14. 分阶段实施计划

阶段状态只允许 `NOT_STARTED`、`IN_PROGRESS`、`CLOSED_LOCAL_WITH_GATES`。只有 G12 满足全部正式条件后才可声明 `PRODUCT_COMPLETE`；它仍不等于 `RELEASE_READY`。

### G0R：v33 目标重开、资产冻结与架构复验

工作：冻结 v33 和三份 Patch 的 hash；建立 `docs/gui/demo-v33`、26 视图符合性矩阵、v19→v33 差异和失效说明；生成 26×3 Demo 截图；V01/V04/V08/V26 做 WebEngine/QML 样板；V01 额外验证 1600×900、1280×720 子元素盒模型；修订 ADR-GUI-001/002/003；记录前序 manifest/hash。

退出门：26 个视图及所有控件入矩阵；V25 元数据遗漏和 V30 标题完成裁决；v19 资产仅作历史；运行时 ADR 以 v33 证据重新批准；R3.3/CB 前序未变。

### G1：语义裁决、后继机器权威与工程脚手架

工作：裁决 BatchWorkset/BatchMetadata、WE/Cluster/Window/Perspective 持久化；批准版本；更新 model/DTO/state/reason/route/permission/audit/rule/metric authorities；需要时 migration/backfill/rollback；生成 OpenAPI/Python/TypeScript；建立 WebEngine 安全壳、Vite 离线确定性构建和 feature flag。

退出门：authority diff/lock/compatibility/validator、生成物零漂移、静态构建双 hash 一致、空壳启动/关闭/后端降级通过。

### G2：产品 Shell、Ribbon、三主题与共享状态

工作：五模块 Ribbon；V01～V23/V25/V26 权限导航；V24 条件入口；训练评估 landing=V26；26 视图 registry；状态分层、返回栈、中文/缩写、主题和公共状态页。

退出门：导航/返回/权限/主题/键盘/高 DPI 无假数据且 fail-closed。

### G3：异步 Gateway 与 GUI 组合读模型

工作：生成型 client；取消、去重、超时、分页、缓存隔离；catalog/bootstrap/selectors；统一 error/reason/provenance；range/LOD/media ticket。

退出门：stale response 不覆盖当前状态；缓存不跨 principal/release；大结果分页/取消/错误门通过。

### G4：Batch 登记、V23 导入与质量闭环

工作：稳定 Batch ID；训练类型显式确认、持久化和审计；文件/目录 ticket；解析、归并、资格状态机；Force/Formation Context revision；未分类和失败重试。

退出门：V23→Batch Registration→解析/资格→V01 的真实闭环；默认值不代替确认；修改可追溯。

### G5：WE、Attack Cluster、Event Window 与 Perspective 底座

工作：唯一 detector/identity/linker/category/cluster/window owner；重叠窗口；状态分离；side-specific projection；Golden fixtures；migration/backfill（若需）。

退出门：一发一 WE、齐射多 WE+Cluster、Episode 多/交错 WE、缺 P/A/J/T2、clock reset/gap/alignment 等正负用例通过。

### G6：V01 历史聚合与任务/装备趋势

工作：统一 query context；六 KPI、两+三+二面板；Batch 列表/摘要；任务指标 authority；装备可比性；V01→V09/V16/V26 精确路由；v33 几何。

退出门：所有面板 Batch 集合一致；零分母/缺 J/不可比 fail-closed；两分辨率三主题盒模型无重叠。

### G7：V26 单批次发射事件工作台

工作：全部筛选、统计、时间线、WE/非发射行为列表、Cluster、分类例外、单机/编队/窗口/回放 deep-link、Context 管理入口。

退出门：exact Batch/Release/Context/WE；无明细 Batch 禁止借用其他批次；分页和权限负面用例通过。

### G8：专项页双视角、V24 与独立事件窗口

工作：V04/V05/V08/V20 双视角；V06/V21 shooter-only；单机/编队目标侧差异化组件；独立 Window；V24 条件协同；Master Cursor 联动。

退出门：缺几何/共享/series 不造图；目标页不重复窗口甘特；Strike target 入口服务端和 UI 均拒绝。

### G9：V03 精确回放与深链

工作：WE→exact replay；二维/三维、事件、曲线、HUD/媒体/转写同步；range/LOD；brush/cursor；历史 Release 禁 latest fallback。

退出门：V26/专项/窗口/V03 往返保持 exact 上下文；媒体/时间漂移和缺失显式。

### G10：其余视图、P3 Model Profile、报告与治理

工作：V02、V07、V09～V23、V25 全部产品化；V10～V16 P3 Profile；V18 ReportRevision/PDF；V22 结构化治理；V25 会话主题。

退出门：26 页功能闭合；P3 未准入时只允许受控不可用；报告不可变 revision；治理 mutation 全部权限/审计。

### G11：性能、安全、可访问性与跨平台硬化

工作：CSP/origin/nonce/token/file ticket/下载；renderer/backend crash；分页/索引/cache/LOD；WCAG、键盘、中文；Windows/Linux Desktop/Service profiles；SBOM/license/vulnerability。

退出门：安全负面、目标 workload、故障恢复、无孤儿进程、安装包 smoke 和可访问性通过；阈值来自实测 authority。

### G12：设计封版、全量资格与切换

工作：同步 03/03A/04/05A/B/E/F/G/H/I、06/07/09；生成后继 lock/provenance/manifest；26×3×Ribbon 两态视觉；角色任务；迁移/升级/回滚；重新聚合 W9。

退出门：本文件第 19 节 DoD 全部满足。任何正式外部门未完成时 W9 保持 `NO_GO`。

---

## 15. 文件级改造清单

候选新增模块（最终名称以 authority/code architecture 审查为准）：

```text
src/tpaa_domain/batch_metadata.py
src/tpaa_domain/weapon_event.py
src/tpaa_domain/attack_cluster.py
src/tpaa_domain/event_window.py

src/tpaa_application/historical_overview.py
src/tpaa_application/batch_registration.py
src/tpaa_application/batch_events.py
src/tpaa_application/event_windows.py
src/tpaa_application/perspective_projection.py
src/tpaa_application/task_metric_aggregation.py

src/tpaa_api/gui_catalog.py
src/tpaa_api/gui_historical.py
src/tpaa_api/gui_batch_events.py
src/tpaa_api/gui_event_windows.py
src/tpaa_api/gui_static.py

src/tpaa_gui/web_host.py
src/tpaa_gui/web_security.py
src/tpaa_gui/gui_state.py
src/tpaa_gui/file_tickets.py

frontend/app frontend/registry frontend/state frontend/services
frontend/components frontend/views frontend/themes frontend/generated

tests/fixtures/gui_v33 tests/fixtures/weapon_events
tests/contract/gui_v33 tests/golden/weapon_event tests/visual/gui_v33
docs/gui/demo-v33 docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json
```

现有 `shell.py`、`local_backend.py`、`security.py`、`desktop.py`、`product_shell.py`、`design_system.py` 只做最小增量；旧 P shell 保留为 feature-flag 诊断回退。migration 仅在 G1 批准新持久对象时新增。

---

## 16. 测试与证据矩阵

必须覆盖：

1. 基线：v33/三 Patch hash、26 view registry、v19 supersession、前序字节不变。
2. Authority：model/DTO/OpenAPI/types/route-permission-audit exact parity。
3. WE：一发一 WE、齐射、Episode 多发、交错、late data、supersession。
4. Window：重叠、缺 T2/T3/J、coverage end、clock reset/gap、UNRESOLVED alignment。
5. Perspective：四空战页双视角、Strike 单视角、P_i/A_i/J fail-closed。
6. V01：同一 Batch 集、日期/时区/空/反向范围、去重、零分母、比值重算、装备可比性。
7. V23：训练类型确认/持久化/审计/未分类/解析前不入统计。
8. 路由：汇总 Batch 不得进入其他 Batch V26；所有 deep-link exact。
9. 安全：origin/CSRF/nonce/token、direct API denial、file ticket、CSP、下载、缓存隔离。
10. 视觉：三主题×26 页×Ribbon 两态；V01 双分辨率元素几何；双视角、V24/V26/V25 重点全 DPI。
11. 可访问性：键盘、焦点、accessible name、对比度、非纯颜色状态、最小可读字号。
12. 性能：历史分页、WE 大列表、重叠窗口查询、Series LOD、切页、播放、内存、CPU/GPU。
13. 稳定性：renderer/backend crash、重启、关闭、重复启动、无孤儿进程。
14. 角色任务：教员 V01→V26→双视角→Window→V03→V18；数据管理员 V23→资格→V01；管理员 Context/分类/审计。

所有自动视觉差异还需产品所有者人工确认；实现团队不得自行降低阈值。

---

## 17. 迁移、兼容与回滚

1. 新 GUI 置于 feature flag 后，旧 P shell 保持可启动。
2. API v1 只做 additive；旧 route 语义不变。
3. 新字段先 nullable/显式 unavailable，并由 backfill 产生 provenance；不得伪造历史。
4. WE/Cluster/Window backfill 必须可重复、幂等、版本化、可回滚。
5. Batch Training Type 未知保持未分类，不批量猜测。
6. 历史 relation/context 绑定历史 revision，不用当前关系反推。
7. migration 提供 forward/rollback、空库和升级库验证。
8. 前端 dist 与后端 schema/DTO 通过 compatibility manifest 绑定。
9. 切换前同时跑旧/新只读投影对比；mutation 不双写，除非有批准的事务/一致性方案。
10. 生产切换和旧壳移除必须另行授权；本方案不授权部署。

---

## 18. 主要风险

| 风险 | 处置 |
|---|---|
| v33 多轮覆盖取错中间版本 | G0R 执行最终 DOM/route 抽取和 26 页截图 |
| V25 元数据遗漏 | 机器 registry 明确纳入 V25，增加契约测试 |
| Batch 类型与 WVR/BVR/Strike 混淆 | 不同字段/枚举/owner，交叉测试 |
| WE/Episode/Cluster 基数混淆 | identity/relationship authority 与 Golden fixtures |
| 用 W 替代目标 P_i | DTO 分层、provenance、负面 fixture |
| 合成趋势/几何变生产值 | 生产禁 random/default，缺失 fail-closed |
| 窗口重叠造成错误互斥切片 | interval model/index/overlap tests |
| 任务比值零分母或简单平均 | Metric service 返回 numerator/denominator/reason |
| localStorage 成业务存储 | Context service + revision + audit；浏览器存储契约禁止 |
| v19 证据误用于 v33 | superseded manifest 与 gate 拒绝旧 target hash |
| WebEngine 攻击面/包体 | G0R/G11 安全、离线、SBOM、crash 门；失败转 QML |
| 脏工作树覆盖用户改动 | 工作树基线、最小补丁、禁止 reset/checkout |

---

## 19. 正式完成定义

- v33 HTML 与三份 Patch SHA 已冻结并写入后继 provenance；
- 26 个视图、五模块 Ribbon、V24/V26 条件下钻和三主题完整；
- V25 元数据遗漏与 V30 标题已裁决；v19 资产明确 superseded；
- V01、V26、四个双视角页、两个 Strike shooter-only、独立 Event Window 全部完成；
- Batch Metadata、WE、Cluster、Window、Perspective、权限/审计均有机器权威；
- 生产页面无合成 Batch、曲线、裁决、几何或前端业务计算；
- terminal/adjudication/window/alignment/classification 状态独立；
- overlapping windows、exact replay、Release/Context/Catalog/Model 绑定通过；
- V01 所有面板同一 Batch 集，任务指标和装备可比性 fail-closed；
- V23 训练类型持久化、revision 和审计闭合；
- route-permission-audit 100% 映射，direct API 负面测试通过；
- 三主题×26 页、交互、角色任务、可访问性、性能、安全、跨平台和安装包门通过；
- 03～09、后继 lock/manifest/SBOM/source provenance/closure evidence 可复验；
- R3.3、CB-1.4.0、CB-1.5.0 字节不变；
- 当前工作树改动归属清晰，无用户修改丢失；
- 未推送、未部署，除非后续另有明确授权；
- `PRODUCT_COMPLETE` 不等于 `RELEASE_READY`；W9 只有同一候选满足全部正式证据才可由 `NO_GO` 变为 `GO`。

---

## 20. 首个实施批次

本方案批准后只先执行 G0R，不直接编写 26 页或后端业务对象：

1. 冻结 v33/三 Patch/工作树/前序 hashes；
2. 标记 v19 目标资产 superseded；
3. 建立 v33 view/control/conformance matrix；
4. 生成 26×3 参考截图和 V01/V04/V08/V26 双路线样板；
5. 完成 V01 元素级几何与 Demo 最终覆盖验证；
6. 修订 ADR 和版本决策；
7. 形成 G0R 关闭报告；
8. G0R 关闭后再进入 G1 Machine Authority First。

---

## 21. 方案状态

本方案已覆盖 v33 基线、三份 Patch、26 视图、V01/V26、WE/Cluster/Window、双视角、后端/API/DTO、版本、设计同步、分阶段实施、测试、迁移、风险和 DoD。

执行状态（2026-11-08 关闭后复核）：`G0R～G5=CLOSED_LOCAL_WITH_GATES`；`G6～G11=IN_PROGRESS_REMEDIATION`；`G12=IN_PROGRESS_EXTERNAL_DOORS_OPEN`；`W9=NO_GO`；`PRODUCT_COMPLETE=false`；`RELEASE_READY=false`。G6～G12 的本地实现与历史证据保留作为整改输入，但旧关闭声明不再构成当前阶段关闭依据。阻断项包括任务/装备指标与多项视图能力未准入、V03/V11/V18/V22 等页面不完整、V24/V26 真实布局和交互缺陷、回放精确上下文丢失、视觉矩阵错误映射/重复截图、关闭器未实际运行所声明门禁，以及安装包、Linux/Service、SBOM/许可证/漏洞、目标 workload 和人工角色视觉门开放。唯一整改方案为 `docs/plans/TPAA_G6至G12关闭后复核缺口全面整改与再关闭方案_2026-11-08.md`。


### G2 安全授权整改增量（2026-11-06）

已完成并关闭：scope_match 与授权 scope 解耦；非全局 wildcard scope 默认拒绝；security/session 业务权限与 GUI 权限字段分离；前端仅消费 gui_permissions；所有 business-Permission API 授权决策在 handler 前写去标识化审计并对审计写失败 fail-closed。已由项目所有者批准并仅在本地激活 API_ROUTE_SECURITY_AUTHORITY，冻结 Service/Desktop 的 G2 运行时并集 86 条路由的 stable route ID、permission 与 audit 语义；历史构建器改为从冻结输入重建，不会吸收 G3 新路由。未知路由默认拒绝；G3 仅激活三条基础读取路由，其余 12 条 GUI business routes 继续不暴露。禁止推送、生产部署和发布声明的边界保持不变。

### G3 异步 Gateway 与组合读模型关闭增量（2026-11-06）

已完成并关闭：CB-1.8.0 以不可变 CB-1.7.0 为直接父基线，DB schema 保持 1.10.0；`GUI_ASYNC_GATEWAY_AUTHORITY`、跨层 DTO、API 路由与安全权威同步激活。Desktop/Service 共用 Application Gateway；UI/REST 不读取原始文件或 Canonical 表。前端通过 bootstrap 获取经角色过滤的 catalog 和 GUI 权限，主体标识不回传，缓存分区键仅以不可逆摘要传输。三条基础路由采用 `AUTHENTICATED_GUI_PERMISSION`，统一守卫实际校验 `gui.view` 并写稳定 route ID 审计，避免业务权限误绑导致学员角色被提前拒绝。取消、超时、去重、stale 丢弃、双分区缓存、游标循环/篡改、分页、统一错误、range/LOD、媒体 ticket 和真实 WebEngine 门均通过。G4 尚未启动；Batch 登记、导入、训练类型修订和其他真实业务投影不得在 G4 机器权威与退出门完成前开放。

### G4 批次登记、V23 导入与质量闭环关闭增量（2026-11-07）

已完成并关闭：G5 在 CB-1.10.0 下激活 WE detector/identity/episode linker/category/Attack Cluster、Event Window、Perspective 和三条只读 API。三次以上源修订形成线性 supersession 链；Cluster 仅为关系且 ID 只由排序后的 WE ID 集合派生；terminal/adjudication/window 三维状态独立；T2 缐失保持 `TERMINAL_UNKNOWN`；Strike target 视角恒失败关闭。运行时能力不再按目录名字符串激活，G4 在 CB-1.9.0/CB-1.10.0 均保持有效。剩余 `gui.overview`、`gui.batch.events`、`gui.replay` 继续保留给 G6/G7/G9，G5 不得冒充后续页面已经完成。
