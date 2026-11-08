# TPAA G4 关闭后 Kimi Code 续接提示词

以下正文可直接粘贴到 VS Code 中的 Kimi Code 插件。Kimi Code 使用的就是当前已打开的 Windows 工作区，必须自行在工作区内定位 TPAA 仓库根目录；不要从 GitHub 重新克隆，也不要用远端分支覆盖本地文件。

---

请直接接手 TPAA 软件工程项目，在 VS Code 当前打开的 Windows 工作区中继续实施 v33 GUI 产品化重构。请先自行定位真正的 Git 仓库根目录和 v33 Demo，不要要求我重复提供路径。请始终使用中文回复，能安全执行的本地代码修改和验证直接执行；只有必须由我人工操作 GUI、提供外部基础设施或扩大授权范围时，才给我精确步骤。

## 一、自动定位仓库和当前事实

当前 VS Code 工作区可能包含设计源文件、历史 Demo 和嵌套的软件仓库，当前活动文件所在目录不一定是 Git 根目录。请在工作区内查找同时包含下列特征的目录：

```text
.git/
pyproject.toml
frontend/gui-v33/
baseline/CB-1.9.0/
docs/plans/TPAA_HTML_Demo_v33驱动_GUI产品化重构与后端设计同步整改方案_2026-11-06.md
```

找到候选目录后，使用 `git -C "<候选目录>" rev-parse --show-toplevel` 验证，并把返回目录作为后续全部 Git、Python、npm 和测试命令的仓库根目录。不要因为终端初始目录不是仓库就重新克隆。

当前事实基线：

- 分支：`codex/v33-g1-handoff-20261106`
- 当前 HEAD：`e0a9677090ea6249c4883e6d503035aea9cd801a`
- 远端：`origin = https://github.com/Sillies001/TPAA.git`
- `G0R～G4=CLOSED_LOCAL_WITH_GATES`
- `G5～G12=NOT_STARTED`
- 当前受控后继：`CB-1.9.0 / DB 1.10.0`
- G4 运行时安全路由：96 条，其中 7 条为 `IMPLEMENTED_G4`
- 6 条 G5+ GUI 路由仍为 `RESERVED_G4_NOT_EXPOSED`
- G4 统一证据：`evidence/gui-g4-v33-closure.json`
- G4 关闭报告：`docs/reviews/G4_V33_BATCH_IMPORT_AND_QUALITY_LOOP_CLOSURE_2026-11-07.md`
- G4 本地续接记录：`docs/handoff/TPAA_G4关闭后本地续接记录_2026-11-07.md`
- 当前工作树包含尚未提交的 G2～G4 实现、证据和文档；这些变更是本次续接的基础，不是垃圾文件。
- 已有 `stash@{0}: pre-g2-sync-local-web-dist-2026-11-06`，它不属于当前阶段，禁止改动或弹出。

定位成功后，必须在仓库根目录执行只读检查：

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git remote -v
git stash list
```

必须以当前本地工作树为事实来源。不要因为 HEAD 仍是旧提交，就认为 G2～G4 不存在；它们当前主要存在于未提交工作树中。

## 二、绝对禁止的操作

在我另行明确授权前：

- 禁止 `git reset --hard`、`git clean`、批量 `git restore`、`git checkout --`；
- 禁止覆盖、丢弃、暂存弹出或重写当前本地修改；
- 禁止直接 `git pull`、rebase、merge、切换到远端旧状态或重新克隆覆盖；
- 禁止 push、force-push、创建 PR、创建 release 或修改保护分支；
- 禁止生产部署、生产数据迁移、真实业务数据写入和发布就绪声明；
- 禁止删除 G0R～G4 的基线、证据、关闭报告和历史生成物；
- 禁止提交 `.venv`、`node_modules`、`.tmp`、缓存、数据库、令牌、密钥或本机绝对路径配置；
- 禁止为通过测试而放宽权限、安全、审计、数据真实性或洁净工作树门禁。

如远端与本地不同，不得擅自选边、重置或覆盖；保留双方历史并先汇报差异。

## 三、唯一实施方案与设计输入

必须严格依据仓库内文件：

```text
docs/plans/TPAA_HTML_Demo_v33驱动_GUI产品化重构与后端设计同步整改方案_2026-11-06.md
```

GUI 法庭记录与设计输入：

```text
docs/gui/demo-v33/source/TPAA_训练复盘交互Demo_v33.html
docs/gui/demo-v33/source/TPAA_V8.0_总体设计方案_Patch_历史多批次总览与攻防双视角_v1.3.md
docs/gui/demo-v33/source/TPAA_ED-2.0_工程设计方案_Patch_历史多批次聚合与攻防复盘_v1.3.md
docs/gui/demo-v33/source/TPAA_V8.0_总体与工程设计方案_Patch差距清单_v1.3.md
docs/design/TPAA_V8.0_ED-2.0_Rebaseline_R3.3/
```

关键机器权威：

```text
docs/gui/demo-v33/DEMO_TARGET_BASELINE.json
docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json
docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json
baseline/CB-1.9.0/
generated/g4-cb-1.9.0/
```

用户工作区中的原始视觉目标通常位于：

```text
TPAA_V33与三份文档更新/TPAA_训练复盘交互Demo_v33.html
```

请自行在当前工作区定位该文件，并与仓库镜像 `docs/gui/demo-v33/source/TPAA_训练复盘交互Demo_v33.html` 计算 SHA-256、核对内容。若二者不同，不得静默选择或覆盖：先报告差异，以用户工作区中的 v33 Demo 作为最新视觉意图，并通过受控设计变更同步仓库镜像、目标基线、符合性矩阵和相关设计文档。

v33 是唯一实现和验收目标；v19 只允许作为历史参考，不得重新成为布局或功能目标。

## 四、强制执行 v33 Demo 前端忠实度复核和整改

当前软件前端与 `TPAA_训练复盘交互Demo_v33.html` 在视觉、布局和控件完整度上仍可能明显不一致。不得把“路由能打开、接口能返回、页面有几个卡片”视为 GUI 已完成，也不得继续沿用通用后台模板或简化占位页面代替 Demo 设计。

在继续 G5 业务能力前，必须先完成一次“G4 关闭后、G5 开始前”的前端忠实度审计，并把共享 Shell、Ribbon、主题和公共组件的明显偏差作为 G5 前置整改。此整改不得篡改既有 G4 关闭证据；应新增独立的审计记录、差距清单和后继验证证据，并在实施方案中说明它是关闭后纠偏增量。

必须完整读取 v33 Demo 的 HTML、CSS 和 JavaScript，而不是只看首屏截图。至少建立并逐项核对以下清单：

- 窗口整体结构、顶部标题/状态区、五模块 Ribbon、Ribbon 分组和按钮层级；
- 26 个视图的导航关系、页面标题、工具条、筛选区、主次面板、分栏比例和滚动行为；
- 卡片、表格、时间线、图表、地图/态势、详情抽屉、状态条、弹窗、标签和表单控件；
- 字体族、字号、字重、行高、间距、对齐、边框、圆角、阴影、图标、颜色和状态色；
- graphite、tactical、light 三主题的变量、对比度和组件状态，默认主题仍为 graphite；
- Ribbon 展开/收起、页面跳转、筛选、选中、hover、focus、disabled、loading、empty、error、forbidden、N/A 等交互状态；
- Demo 中已有的中文文案、必要缩写、信息密度、视觉层级和操作顺序；
- 目标分辨率、100%/150% DPI、窗口缩放以及键盘和焦点行为。

实现目标是：在桌面产品技术边界允许的范围内，页面内容、区域顺序、几何比例、控件种类、视觉样式和交互行为与 v33 Demo 保持像素级或近像素级一致。只有操作系统原生窗口装饰、安全状态和真实数据状态等确有技术依据的内容可以不同，并且每一项差异都必须在差距清单中说明原因和批准状态。

不得：

- 把 Demo 的复杂页面简化成通用卡片、纯文本列表或空白大面板；
- 用浏览器默认控件样式、随意间距或临时颜色代替 Demo 样式；
- 只实现当前阶段的后端接口，却把对应页面视觉整改推迟到 G12；
- 为追求截图相似而填入虚假业务数据、随机曲线或跨批次数据；
- 通过隐藏 Demo 中的关键控件、面板或交互来规避后端能力缺口。

如果 Demo 中的控件或交互缺少后端支持，应同步补齐领域模型、Application、DTO、REST、权限、审计、分页和真实状态语义；不能删除前端设计来迁就当前后端。若能力属于后续阶段，应保留与 Demo 一致的结构，并以明确、受控的不可用状态展示，不能伪造可用结果。

视觉验收必须采用可复核证据：

1. 为 Demo 和实际软件建立同分辨率、同主题、同 Ribbon 状态的截图基线；
2. 至少覆盖设计规定的目标分辨率、100%/150% DPI、三主题和 Ribbon 两态；
3. 对共享 Shell 及当前已实现页面进行并排、叠加或图像差异比较；
4. 为每个不一致项记录 Demo 位置、实际位置、严重度、整改文件、验证截图和剩余理由；
5. 后续 G5～G12 每完成一个页面，都必须同时完成其 Demo 对照，不得只做功能测试；
6. G12 最终执行完整的 `26 视图 × 3 主题 × Ribbon 两态` 视觉矩阵和角色任务验收。

## 五、先复验 G4，不要重复实现

使用仓库虚拟环境执行：

```powershell
$env:POLARS_SKIP_CPU_CHECK='1'
$env:UV_CACHE_DIR=(Resolve-Path '.tmp').Path+'\uv-cache'

.\.venv\Scripts\python.exe tools/baseline/adopt_g4_successor.py --check
.\.venv\Scripts\python.exe tools/codegen/g4_batch_generate.py --check
.\.venv\Scripts\python.exe -m ruff check src tests tools migrations
.\.venv\Scripts\python.exe tools/dev/tpaa_dev.py typecheck
.\.venv\Scripts\python.exe tools/gui/g4_v33_close.py
```

预期：Ruff 通过；Mypy 573 个源文件零错误；G4 关闭器返回 `CLOSED_LOCAL_WITH_GATES`。若失败，先判断是否为环境问题、当前工作树漂移或真实回归，不要删除现有实现重做。

开发打包器会按设计拒绝当前非洁净工作树。不得放宽此规则，也不得把该预期拒绝报告为 G4 功能失败。只有我以后授权本地候选整理和提交后，才执行洁净树零失败打包验证。

## 六、按 G5→G12 严格顺序推进

不得跳阶段，不得在前一阶段退出门未通过时把后续阶段标记为关闭。

### G5：WE、Attack Cluster、Event Window 与 Perspective 底座

完成唯一 detector、identity、linker、category、cluster、window owner；处理重叠窗口、状态分离、side-specific projection、Golden fixtures 以及必要 migration/backfill。

退出门至少覆盖：一发一 WE、齐射多 WE+Cluster、Episode 多/交错 WE、缺 P/A/J/T2、clock reset、gap、alignment 等正负用例。不得出现多个 owner 或由 GUI/REST 重复推导。

### G6：V01 历史聚合与任务/装备趋势

完成统一 query context、六 KPI、两+三+二面板、Batch 列表/摘要、任务指标 authority、装备可比性、V01→V09/V16/V26 精确路由及 v33 几何。

所有面板必须使用同一 Batch 集合；零分母、缺 J 和不可比情况必须 fail-closed；三主题和目标分辨率不得重叠。

### G7：V26 单批次发射事件工作台

完成筛选、统计、时间线、WE/非发射行为列表、Cluster、分类例外、单机/编队/窗口/回放 deep-link 和 Context 管理入口。

必须保持 exact Batch/Release/Context/WE；无明细批次禁止借用其他批次数据；分页与权限负面用例必须通过。

### G8：专项页双视角、V24 与独立事件窗口

完成 V04/V05/V08/V20 双视角、V06/V21 shooter-only、单机/编队目标侧差异化组件、独立 Window、V24 条件协同和 Master Cursor 联动。

缺几何、共享或 series 时禁止造图；目标页不得重复窗口甘特；V24 Strike target 非法直达必须由服务端与 UI 同时拒绝。

### G9：V03 精确回放与深链

完成 WE→exact replay、二维/三维、事件、曲线、HUD/媒体/转写同步、range/LOD、brush/cursor；历史 Release 禁止 latest fallback。

V26、专项页、窗口与 V03 往返必须保持 exact 上下文；媒体缺失与时间漂移必须显式呈现。

### G10：其余视图、P3 Model Profile、报告与治理

产品化 V02、V07、V09～V23、V25；完成 V10～V16 P3 Profile、V18 ReportRevision/PDF、V22 结构化治理和 V25 会话主题。

26 页必须功能闭合；P3 未准入时只能显示受控不可用；报告 revision 不可变；所有治理 mutation 都必须权限控制和审计。

### G11：性能、安全、可访问性与跨平台硬化

完成 CSP/origin/nonce/token/file ticket/下载防护、renderer/backend crash 恢复、分页/索引/cache/LOD、WCAG/键盘/中文、Windows/Linux Desktop/Service profiles、SBOM/license/vulnerability。

安全负面、目标 workload、故障恢复、无孤儿进程、安装包 smoke 和可访问性必须通过。性能阈值必须来自实测 authority，不得凭空填写。

### G12：设计封版、全量资格与切换

同步总体与工程设计 03/03A/04/05A/B/E/F/G/H/I、06/07/09，生成后继 lock/provenance/manifest，完成 26×3×Ribbon 两态视觉、角色任务、迁移/升级/回滚以及 W9 重新聚合。

必须满足实施方案第 19 节全部 DoD。任何正式外部门未完成时，W9 继续保持 `NO_GO`，禁止声明 `PRODUCT_COMPLETE`、`RELEASE_READY` 或批准生产部署。

## 七、不可破坏的架构和数据边界

- 前端、REST、GUI 与插件不得绕过 Application 直接读取原始文件、数据库表或 Canonical 表；
- WE detector、identity/linker、Attack Cluster 和 Event Window resolver 必须各自保持唯一 owner；
- 所有新增 API 必须先有 DTO、权限、稳定 route ID、审计、分页/错误/来源语义和机器权威，再注册暴露；
- 未实现或未授权路由必须保持未注册并 fail-closed；
- 没有真实后端数据时只能显示 `LOADING/EMPTY/DEGRADED/ERROR/FORBIDDEN/N_A` 等明确状态；
- 禁止用 Demo 数值、随机曲线、固定假数据或其他批次数据冒充真实结果；
- historical/exact 请求禁止回退到 latest；Batch、Release、Context、WE、Perspective、Window 必须端到端保持精确身份；
- WebEngine 保持 exact loopback origin、原生 bearer/nonce、off-the-record、无持久 Cookie、无远程资源、禁止任意导航/下载/弹窗并失败关闭；
- 三主题默认 graphite，只允许会话级切换；不得使用浏览器持久化改变业务状态；
- legacy widgets 在 G11/G12 正式裁决前只作为 feature-flag 诊断回退保留；
- 数据库或基线变化必须形成新的受控后继、直接父关系、lock、兼容性、migration/backfill/rollback 和证据，不得静默修改 CB-1.9.0 或历史关闭证据。

## 八、每一阶段的完成方式

每个阶段都必须：

1. 先读取方案对应工作项、退出门及相关设计章节；
2. 建立新的不可变后继机器权威，不得覆写历史基线；
3. 同步实现领域、Application、Runtime、REST、GUI、生成式 client 和必要存储迁移；
4. 同步更新总体/工程设计增补、权威矩阵与实施方案状态；
5. 对照 v33 Demo 同步完成本阶段页面的布局、样式、控件和交互，不得以功能可用代替视觉符合；
6. 编写正向、负向、权限、身份、数据真实性、迁移和回归测试；
7. 执行 Ruff、Mypy、前端 typecheck/build、专项 pytest 和与风险相称的回归；
8. 在真实 Windows Qt WebEngine 中执行 100%/150% DPI、三主题、键盘、焦点、退出、Demo 截图对照和关键角色任务验收；
9. 生成机器可读 evidence、截图、视觉差异记录和中文关闭报告；
10. 只有功能门和对应页面的 Demo 忠实度门都通过时，才标记 `CLOSED_LOCAL_WITH_GATES`；否则保持 `IN_PROGRESS` 并列出开放门禁；
11. 每阶段结束更新 `docs/handoff/` 续接记录，列出变更、测试、视觉证据、下一阶段和精确复验命令。

不要通过修改历史测试断言来掩盖真实回归。后继基线导致历史契约需要更新时，必须证明后向不变量仍成立，并将“完全相等”改为“受控后继包含”之类的变更限定在确有阶段演进依据的场景。

## 九、人工参与与最终回审准备

需要我人工参与时，只给出：当前阶段、目的、准确命令或点击路径、预期结果、失败时需提供的信息。不要让我重复执行你能在本机自动完成的动作。

我会在剩余阶段完成后回到 Codex 进行独立审核。因此，在你停止工作或完成 G12 时，必须新增最终回审交接文档，至少记录：

- 实际完成到哪个阶段及每阶段状态；
- 当前分支、HEAD、完整 `git status --short` 和 stash 状态；
- 所有新增/修改的基线、迁移、路由、DTO、设计、证据和关闭报告；
- v33 Demo 与实际 GUI 的逐页差距清单、截图矩阵、已批准差异和未解决视觉缺口；
- 全量测试命令、通过/跳过/失败数量及环境限制；
- 未通过门禁、已知风险、外部门和 W9 判定；
- 是否存在未提交修改；
- 供 Codex 从 G4 关闭状态逐阶段审计的精确文件清单和复验命令。

现在请先在 VS Code 当前工作区中自行定位 TPAA 仓库根目录和 `TPAA_训练复盘交互Demo_v33.html`，核对当前本地工作树与 G4 关闭事实，然后完整审查 Demo 与现有 GUI 的差异。先形成并向我汇报前端忠实度差距清单，同时直接整改共享 Shell/Ribbon/三主题/公共组件，再从 G5 开始按 G5→G12 顺序推进；每个阶段都必须同时完成对应页面的 Demo 对照。禁止推送和生产部署。

---
