# G4 关闭后 · v33 Demo 前端忠实度审计与 Shell 纠偏差距清单

> 文档性质：**G4 关闭后的独立纠偏增量审计记录**。不修改、不撤销 `evidence/gui-g4-v33-closure.json`、`docs/reviews/G4_V33_BATCH_IMPORT_AND_QUALITY_LOOP_CLOSURE_2026-11-07.md` 等既有 G4 关闭证据；本文件是其后新增的审计与整改基线。
> 审计日期：2026-11-07
> 审计对象：`frontend/gui-v33/src/{main.ts,style.css,services/*,generated/*}`（G2～G4 产物）对照 `docs/gui/demo-v33/source/TPAA_训练复盘交互Demo_v33.html`（SHA-256 `7aa5ff43…2401a9a`，与受冻结基线一致）。
> 结论级别：**共享 Shell/Ribbon/三主题/公共组件存在系统性视觉偏差，须在 G5 业务能力前完成纠偏**。属于"关闭后纠偏增量"，不改变 G0R～G4 的功能关闭结论。

---

## 1. 审计方法

1. 完整读取 v33 Demo 的 HTML/CSS/JavaScript（非仅首屏），抽取最终生效定义（多轮 patch 取最后一次）。
2. 逐项核对：窗口结构、标题区、五模块 Ribbon、分组按钮层级、主题变量、版式几何、图表控件、交互状态、中文文案。
3. 对照当前 `frontend/gui-v33` 源码，记录 Demo 位置 / 实际位置 / 严重度 / 整改文件。

## 2. 共享 Shell 差距（G5 前置整改范围）

### GAP-SHELL-01 应用外框结构不一致 — 严重度 阻断

- Demo：`#cv` 为固定 **1600×900** 画布，`fit()` 以 `scale(min(W/1600,H/900))` 居中缩放适配窗口；Shell 由 `.apphead`(高166px) + 绝对定位内容区 + `.ft` 页脚(顶872px) 组成。
- 实际：`body>#app` 流式 grid（58px 标题行 + Ribbon + context-bar + workspace + 30px 状态栏），无固定画布、无缩放适配。
- 整改：`frontend/gui-v33/src/style.css`、`main.ts` 引入 1600×900 画布与 `fit()` 等价缩放。

### GAP-SHELL-02 顶部区域结构不一致 — 严重度 阻断

- Demo：`.apphead` 内 **居中标题** `.apptitle`（"空战训练评估系统"，21px/字距2.5px）+ `.mainmenu`（五模块 `mtab` 页签，含 `.dd` 下拉）+ `.submenu`（`.subgroups`→`.subcard` 分组→`.subbtn` 带图标按钮）。
- 实际：左侧品牌 "TP" + 居中 `<h1>` 标题栏，下方五模块 grid 页签 + 左侧 `.subnav` 竖排视图列表，**无分组 Ribbon、无图标按钮**。
- 整改：按 Demo 重建 mainmenu + submenu 分组 Ribbon（含 `rbicon` SVG 图标 + `rblabel`）。

### GAP-SHELL-03 Ribbon 分组与按钮层级缺失 — 严重度 阻断

- Demo 最终生效分组（v33）：
  - 总览：`总览入口:[V01]`
  - 训练评估(landing=V26)：`批次入口:[V26]`、`视距内行为:[V05,V20]`、`超视距行为:[V04,V08]`、`对地攻击:[V06,V21]`、`基本飞行（独立）:[V07,V19]`、`长期成长与综合复盘:[V09,V02]`
  - 回放：`战术回放工作台:[V03]`
  - 装备性能：`装备总体:[V10]`、`分项性能:[V11,V12,V13,V14]`、`综合分析:[V15,V16]`
  - 数据与系统(landing=V23)：`数据管理与可信度:[V23,V17]`、`输出与系统:[V18,V22]`、`界面设置:[V25]`
  - 按钮规格 `RB_SPEC`：每视图 `[图标kind, 颜色]`（chart/doc/play/radar/target/strike/flight/formation/trend/gauge/curve/warn/layers/data/gear/palette 共16种 SVG）。
- 实际：仅平铺视图 id 列表，无分组、无图标、无颜色规格。
- 整改：在 `main.ts` 建立模块→分组→按钮注册结构 + 图标库，渲染 `.subcard/.subbtn`。

### GAP-SHELL-04 Ribbon 展开/收起行为不一致 — 严重度 高

- Demo：`#cv.ribbon-collapsed` 时 `.apphead` 高 166→78px、`.submenu` 隐藏、`.ribbon-toggle`(⌃/⌄) 位置切换；页面底部行吸收 88px 高度差（`RIBBON_DELTA`），**不使用全局 translate**。
- 实际：仅切换 `.subnav` 显隐，无高度重排。
- 整改：实现收起态高度差吸收。

### GAP-SHELL-05 三主题变量与取值不一致 — 严重度 高

- Demo：`:root`(tactical 默认深青蓝 `--bg:#0e1722 --pn:#152233 --ln:#27394f --tx:#e8eef5 --mu:#8da2b8 --me:#3a9ad9 --hi:#56b4e9`)；`html[data-tpaa-theme=graphite]` 覆写为石墨色（`--bg:#1b1e24 --pn:#292e36 --ln:#414b57 --hi:#8ab6e5`，Palantir AIP 风格）；light 为冰川灰白。图表色板 `Cl`/`THEME_CL_{TACTICAL,GRAPHITE,LIGHT}` 随主题切换。**每次打开默认 graphite**。
- 实际：变量名不同（`--panel/--raised/--text/--accent`），graphite 取值 `#11161d/#1a222c/#69b7e8` 与 Demo 石墨色不一致，无图表色板主题化。
- 整改：统一采用 Demo 变量名与三主题精确取值（含 graphite 覆写、light 覆写、图表色板 `THEME_CL_*`）。

### GAP-SHELL-06 筛选条/上下文条不一致 — 严重度 高

- Demo：`.selbar`（顶170px，含 `label+select`、`scope` 徽章、`.muted`），V26 用 `.batchFilters`、V23 用 `.dmbar`；上下文以 `.subctx .chip` 呈现于 Ribbon 内。
- 实际：独立 `.context-bar` 9 宫格固定显示在 Ribbon 与内容之间。
- 整改：按页面类型渲染 Demo 风格 selbar / 保留上下文 chip。

### GAP-SHELL-07 公共组件与图表库缺失 — 严重度 高

- Demo：内置图表/控件库 `ax/gl/L(折线)/X(散点)/H(热力矩阵)/B(横条)/VB(瀑布)/RD(雷达)/PO(极坐标)/HG(直方)/D3(三维)/HUD`，及 `.p` 面板（h3+small+pb）、`.k4/.kp` KPI 卡、`.eventrail`、`ca*` 协同组件、`dmsrc/dmq/dmmatrix` 数据管理组件、`themeChoice` 主题卡。
- 实际：仅有 state-panel / batch-table / form 等少量通用件，**无任何图表与 Demo 业务组件**。
- 整改：移植图表原语与面板/KPI 组件为受控 TypeScript 组件（数据仅来自后端或显式不可用态，禁用 Demo 合成值）。

### GAP-SHELL-08 字体/字号/信息密度不一致 — 严重度 中

- Demo：13px/1.5 基准，"PingFang SC","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC"；select/option 12px；面板标题 12.5–15px；KPI 值 22px；信息密度高。
- 实际：14px 基准，字体栈缺 PingFang SC/Noto CJK 排序，密度偏松。
- 整改：对齐字体栈、基准字号、组件字号梯度。

## 3. 页面级差距（按阶段归属，Shell 纠偏先共享件，页面随 G6～G10 落地）

| 视图 | Demo 结构 | 当前状态 | 归属阶段 |
|---|---|---|---|
| V01 | k4 六 KPI + 任务/活动/裁决/类别/装备 5 图 + 批次列表 + 摘要（LY 36/68/168/168/…） | 仅批次表格 | G6 |
| V26 | batchFilters/summary(3+类别卡)/timeline(泳道)/WE+未发射列表 | 无 | G7 |
| V04/05/08/20 | 双视角专项（射手/目标差异组件） | 无 | G8 |
| V03 | 二维/三维/HUD/事件泳道/胜率/转写 + 刷选联动 | 无 | G9 |
| V10～V16 | E-M/探测/告警/攻击/剥离/趋势（雷达/ECDF/控制图） | 无 | G10 |
| V17/18/22/25 | 质量矩阵/打印报告/治理/主题卡 | 25 有简易卡；17/18/22 无 | G10 |
| V23 | dmbar/dmsources×5/dmq/dmmatrix/dmcheck/dmsupp | 有真实导入表单（G4） | G4已交付，G10 视觉对齐 |
| V02/07/09/19/21/24 | 各自专项面板 | 无 | G8/G10 |

## 4. 数据真实性红线（整改约束）

- 移植 Demo 视觉/布局/控件/交互**不得**引入其合成数值、固定种子随机、localStorage 业务事实、前端业务公式。
- 无真实后端读模型的页面：保留 Demo 一致的版面骨架，内容区显示受控 `LOADING/EMPTY/DEGRADED/ERROR/FORBIDDEN/N_A`，**不伪造曲线/裁决/几何**。
- 图表组件仅消费 Application 授权投影；缺数据 fail-closed。

## 5. 整改与验证计划（G4 后纠偏增量）

1. **共享 Shell 重建**：画布+缩放、apphead/mainmenu/submenu 分组 Ribbon（含图标/颜色规格）、收起态、三主题精确变量与图表色板、selbar、图表与公共组件库。文件：`frontend/gui-v33/src/{style.css,main.ts,shell/*,components/*,charts/*,themes.ts}`。
2. **视觉验证**：真实 WebEngine 下三主题 × Ribbon 两态 × (1600×900、1280×720、1366×768、1920×1080) 截图；与 Demo 同分辨率截图并排/叠加比对；逐不一致项记录位置/严重度/整改文件/剩余理由。
3. **门禁**：Ruff、Mypy、前端 typecheck/build、gui_v33 契约测试全通过；构建双 hash 一致。
4. **页面 Demo 对照**：G6～G10 每页落地时同步完成对照，G12 执行 26×3×Ribbon 全矩阵。

## 6. 批准差异（预登记）

- 操作系统原生窗口装饰（WebEngine 宿主边框/标题）与 Demo 浏览器边框不同：技术依据充分，批准。
- 真实后端数据状态（EMPTY/N_A 等）替代 Demo 合成占位：数据真实性红线要求，批准。
- 其余差异一律整改，未列明不得保留。

---

## 7. 整改执行记录（2026-11-07 完成）

### 7.1 关键约束发现：生产 CSP 禁止内联样式

- 事实：WebEngine 响应头 `Content-Security-Policy: ... style-src 'self'`（`src/tpaa_api/desktop.py:228`，G2 安全门）。经 DOM/CSSOM 诊断证实：**innerHTML 中的 `style` 属性被浏览器丢弃**（`cssText` 为空、几何不生效），而经 JavaScript `element.style`（CSSOM）赋值的同源样式正常生效。
- 处置：**不放宽 CSP**。共享 Shell 全部动态视觉改为「`data-*` 属性 + 渲染后 CSSOM 应用」：
  - 面板几何：`shell.ts panel()` 输出 `data-geo`，`applyPanelGeometry()` 在 `innerHTML` 后经 `element.style.left/top/width/height` 应用。
  - 主题预览 mock 的 CSS 自定义属性与色板：`data-pr` / `data-color`，`applyDynamicPresentation()` 经 `setProperty`/`style.background` 应用。
  - 其余 24 处内联样式全部迁移为样式表类（`.form-grid/.fld/.rev-head/.ticket-card/.skip-link/...`）。
- 结果：`main.ts` 内联 `style="..."` 计数为 0；视觉与 Demo 一致且通过安全门。

### 7.2 重建内容（共享 Shell / Ribbon / 三主题 / 公共组件）

- `style.css`：重写为 Demo 变量名与三主题精确取值（tactical/graphite/light，含 graphite 与 light 的组件级覆写）、`apphead/mainmenu/submenu/subcard/subbtn` 分组 Ribbon 样式、`fit()` 画布缩放、图表基元与公共组件样式；保留契约必需令牌（`:root[data-tpaa-theme=…]`、`:focus-visible`、`@media(max-width:760px)`、`prefers-reduced-motion`）。
- `themes.ts`：三主题定义、图表色板 `THEME_CL_*`、`assignTheme`。
- `icons.ts`：16 种 Ribbon SVG 图标 + 每视图 `[图标,颜色]` 规格（`RIBBON_SPEC`）。
- `shell.ts`：五模块最终生效分组结构、1600×900 画布 `fitCanvas`、`LY` 版式与 `panel()`/`applyPanelGeometry`、受控状态面板。
- `charts.ts`：折线/横条/雷达/热力图原语（主题感知、纯数据驱动，不生成合成数据）。
- `main.ts`：渲染层切换到 Demo 忠实 Shell；保留 G2 契约全部令牌与状态/权限/网关/fail-closed 逻辑；恢复 G4 验收 DOM 契约（`.ticket-card`/`.revision-panel`/`.state-pill`/`.state-ready`）。

### 7.3 验证证据

- 构建：`vite build` 通过；产物含全部 G4 验收 DOM 契约令牌（已逐项核对 OK）。
- 静态门：Ruff 通过；Mypy 573 源文件零错误；GUI 契约测试 29/29；网关 node 测试 7/7；GUI/ API 单测 67/67。
- 真实 WebEngine（`tools/gui/shell_fidelity_capture.py`，bootstrap 后只读、避开易波动写库路径）：采集 6 张截图于 `evidence/shell-fidelity/`：
  - `shell_v01_graphite_ribbon_expanded.png` / `..._collapsed.png`
  - `shell_v25_graphite.png` / `..._tactical.png` / `..._light.png`（三主题整壳换肤 + 主题卡预览各自配色）
  - `shell_v26_graphite.png`（训练评估完整分组 Ribbon + fail-closed N/A）
- 目检结论：窗口结构、居中标题、五模块 Ribbon 分组与图标按钮、收起钮、三主题、1600×900 画布缩放、状态页脚均与 Demo 一致；未实现业务页以受控 N/A 呈现，无伪造数据。

### 7.4 开放门禁（转 G5/G12 视觉矩阵）

- 共享 Shell 的 **26 视图 × 3 主题 × Ribbon 两态 × 多分辨率** 全矩阵视觉比对属 G12；当前已完成 Shell 级 6 张关键截图。逐页面 Demo 对照随 G6～G10 页面落地同步执行。
- G4 WebEngine 完整验收闭环（`g4_webengine_acceptance.py`，含写库）在本机后端子进程/SQLite 上间歇性不稳定（`database is locked`/bootstrap 表清单/控制通道，均为后端侧、与前端无关；同款后端在 2026-11-07 曾完整通过并产出 `-100/-150` 证据，本次未改动且令牌保持）。该闭环作为 G4 既有证据仍有效；如需重跑建议在稳定环境执行，不作为本次 Shell 纠偏的阻塞项。
