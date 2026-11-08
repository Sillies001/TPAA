# TPAA G5 关闭后 Kimi Code G6～G12 完整交接提示词

以下正文可直接粘贴到 VS Code 中的 Kimi Code 插件。Kimi Code 使用当前已打开的 Windows 工作区，必须自行定位仓库根目录和 v33 Demo，不要重新克隆仓库，也不要用远端代码覆盖本地工作树。

---

请直接接手 TPAA 软件工程项目，从已经正式本地关闭的 G5 状态继续推进 v33 GUI 产品化重构与后端/设计同步整改。此次把 **G6～G12 的本地代码整改工作完整交给你**：请持续、自主、按顺序实施、测试、留证和关闭各阶段，不需要每完成一个阶段就停下来等待我确认。只有遇到必须由我人工操作 GUI、提供外部基础设施、批准新的产品/治理决策或扩大授权范围的真实阻断时，才暂停并给出精确步骤。

请始终使用中文回复。能在当前工作区安全执行的代码修改、依赖构建、数据库兼容验证、前端构建、自动化测试、截图和文档更新均直接执行。

## 一、先自行定位仓库，不要从活动文件路径作错误推断

当前 VS Code 工作区包含设计源文件、历史 Demo 和嵌套的软件仓库；活动文件所在目录不一定是 Git 根目录。请在工作区中寻找同时具备以下特征的目录：

```text
.git/
pyproject.toml
frontend/gui-v33/
baseline/CB-1.10.0/
docs/plans/TPAA_HTML_Demo_v33驱动_GUI产品化重构与后端设计同步整改方案_2026-11-06.md
evidence/gui-g5-v33-closure.json
```

使用下列命令验证候选目录，并将返回目录作为后续所有 Git、Python、npm、测试和文档操作的仓库根目录：

```powershell
git -C "<候选目录>" rev-parse --show-toplevel
```

不要因为终端初始目录不在仓库根目录就重新克隆。定位后先执行只读盘点：

```powershell
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
git stash list
```

当前交接时记录的定位事实如下，但必须以你实际读取到的工作树为准：

- 分支：`codex/v33-g1-handoff-20261106`
- HEAD：`e0a9677090ea6249c4883e6d503035aea9cd801a`
- 远端：`origin = https://github.com/Sillies001/TPAA.git`
- 本地分支相对远端 ahead 5；不因此执行 push、pull、merge 或 rebase。
- 工作树包含大量 G2～G5 的未提交源代码、权威、生成物、测试、证据和设计文档，它们是当前实施事实，不是垃圾文件。
- 已有 `stash@{0}: pre-g2-sync-local-web-dist-2026-11-06`，禁止改动、弹出或删除。
- 当前 HEAD 不能代表全部实现；**本地未提交工作树才是本次续接的事实来源**。

## 二、当前唯一有效阶段事实

当前阶段状态：

```text
G0R～G5 = CLOSED_LOCAL_WITH_GATES
G6～G12 = NOT_STARTED
```

G5 的有效关闭事实来自：

```text
docs/reviews/G5_V33_WEAPON_EVENT_WINDOW_PERSPECTIVE_CLOSURE_2026-11-07.md
evidence/gui-g5-v33-closure.json
tools/gui/g5_v33_close.py
baseline/CB-1.10.0/
generated/g5-cb-1.10.0/
```

关键事实：

- G5 受控后继为 `CB-1.10.0`，直接父基线为不可变 `CB-1.9.0`，DB schema 仍为 1.10.0。
- G5 baseline lock SHA-256 为 `a4864b36ef571b3582c97606ca33a3bd633e0561f776ad4383c9ff6a14dac3d0`。
- 当前安全路由为 99 条；G5 三条已激活路由是 `api.route.097～099`。
- G5 的 detector、identity/linker、category、Attack Cluster、Event Window、Perspective、精确作用域、Canonical 读适配、DTO 双端生成、持久审计、原子激活和直接 API 负测均已关闭。
- `gui.overview`、`gui.batch.events`、`gui.replay` 仍分别保留给 G6、G7、G9；不得提前注册或以占位响应冒充实现。
- G5 关闭时 Ruff、Mypy（588 个源文件）、G4/G5 successor/codegen、329 项 Python 回归、69 项 G5 定向测试、前端 typecheck/build、资源一致性和双基线存储兼容均通过。
- 旧文件 `docs/handoff/TPAA_G5底座续接记录_2026-11-07.md` 中的 `G5=IN_PROGRESS` 和“激活待续”是关闭前历史记录，已经过时；不得据此回退或重复实现 G5。以上述关闭报告、机器证据和当前方案状态为准。
- 当前不等于 `PRODUCT_COMPLETE`、`RELEASE_READY`，也没有生产部署许可；W9 仍应保持 `NO_GO`，除非未来同一候选满足所有正式外部门并获得另行授权。

开始 G6 前，必须先验证上述事实没有回归。不得修改历史关闭证据来掩盖失败；发现真实回归时，以最小增量修复并记录为关闭后纠偏。

## 三、唯一实施方案、视觉目标与设计输入

必须严格依据仓库中的唯一实施方案：

```text
docs/plans/TPAA_HTML_Demo_v33驱动_GUI产品化重构与后端设计同步整改方案_2026-11-06.md
```

当前 GUI 的唯一产品视觉与交互目标是 v33，不是 v19，也不是通用后台模板：

```text
docs/gui/demo-v33/source/TPAA_训练复盘交互Demo_v33.html
docs/gui/demo-v33/DEMO_TARGET_BASELINE.json
docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json
docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json
```

设计输入：

```text
docs/gui/demo-v33/source/TPAA_V8.0_总体设计方案_Patch_历史多批次总览与攻防双视角_v1.3.md
docs/gui/demo-v33/source/TPAA_ED-2.0_工程设计方案_Patch_历史多批次聚合与攻防复盘_v1.3.md
docs/gui/demo-v33/source/TPAA_V8.0_总体与工程设计方案_Patch差距清单_v1.3.md
docs/design/TPAA_V8.0_ED-2.0_Rebaseline_R3.3/
```

工作区外层通常还有用户提供的原始视觉目标：

```text
TPAA_V33与三份文档更新/TPAA_训练复盘交互Demo_v33.html
```

请自行定位外层原始 Demo，并与仓库镜像计算 SHA-256、核对内容。若两者不同，禁止静默覆盖或自行选边：先记录差异，以用户工作区中的 v33 Demo 作为最新视觉意图，再通过受控设计变更同步仓库镜像、目标基线、符合性矩阵和设计文档。

v19 文件只允许作为历史参考，禁止重新成为实现或验收目标。

## 四、绝对禁止的操作和不可扩大授权的边界

在我另行明确授权前：

- 禁止 `git reset --hard`、`git clean`、批量 `git restore`、`git checkout --`；
- 禁止丢弃、覆盖、暂存弹出或重写现有本地修改；
- 禁止直接 `git pull`、merge、rebase、切换到远端旧状态或重新克隆覆盖；
- 禁止 Git commit、push、force-push、创建 PR、创建 release、打 tag 或修改保护分支；
- 禁止生产部署、生产数据迁移、真实业务数据写入和发布就绪声明；
- 禁止修改或删除 G0R～G5 的不可变基线、关闭证据和历史生成物；
- 禁止提交 `.venv`、`node_modules`、缓存、临时数据库、令牌、密钥或本机绝对路径配置；
- 禁止为通过测试而放宽权限、安全、审计、数据真实性、exact identity、迁移、回滚或洁净工作树门禁；
- 禁止把 Demo 数值、随机曲线、固定假数据、其他 Batch/Release/Context/WE 数据或前端计算冒充真实后端结果；
- 禁止把“代码已写”“页面能打开”或“自动测试通过”直接等同于产品阶段关闭。

如果远端与本地不同，保留双方历史并只报告差异；不得擅自同步或覆盖。

## 五、先复验 G5，不要重复实现或篡改关闭事实

优先使用仓库现有 `.venv`；若解释器路径不同，自行探测有效环境。PowerShell 中 npm 应使用 `npm.cmd`，避免执行策略拦截 `npm.ps1`。设置：

```powershell
$env:POLARS_SKIP_CPU_CHECK='1'
$env:UV_CACHE_DIR=(Resolve-Path '.tmp').Path+'\uv-cache'
```

至少执行：

```powershell
.\.venv\Scripts\python.exe tools/baseline/adopt_g4_successor.py --check
.\.venv\Scripts\python.exe tools/baseline/adopt_g5_successor.py --check
.\.venv\Scripts\python.exe tools/codegen/g4_batch_generate.py --check
.\.venv\Scripts\python.exe tools/codegen/g5_weapon_event_generate.py --check
.\.venv\Scripts\python.exe -m ruff check src tests tools migrations
.\.venv\Scripts\python.exe tools/dev/tpaa_dev.py typecheck
.\.venv\Scripts\python.exe tools/gui/g5_v33_close.py

Push-Location frontend/gui-v33
npm.cmd ci
npm.cmd run typecheck
npm.cmd run build
Pop-Location

.\.venv\Scripts\python.exe tools/gui/g1_frontend_build.py
```

对 Windows 下的 pytest，使用工作区内较短的 `--basetemp`，避免路径长度和临时目录锁误报。若发生已知的瞬态 Windows `os.replace` 文件锁，先保留首次输出，再仅重跑失败用例确认；不得把稳定复现的失败标为环境问题。

若 G5 复验通过，直接进入 G6。若失败，先区分环境问题、生成物漂移和真实回归；只修复真实问题，不删除已有实现重做。

## 六、G6～G12 必须按顺序持续推进

阶段状态只允许：`NOT_STARTED`、`IN_PROGRESS`、`CLOSED_LOCAL_WITH_GATES`。前一阶段未满足全部退出门时，后一阶段不得标记关闭。可以为避免返工做后续接口预留，但不得提前暴露路由、伪造能力或把预留项声称为已完成。

### G6：V01 历史聚合与任务/装备趋势

完整实现统一 query context、六 KPI、“两 + 三 + 二”面板、Batch 列表和摘要、任务指标 authority、装备可比性，以及 V01→V09/V16/V26 的 exact 路由。实现 `gui.overview` 时必须先具备 DTO、稳定 route ID、权限、GUI permission、审计、分页/错误/来源语义、生成式 client 和机器权威，再受控注册。

所有 KPI、面板、图表和表格必须使用同一精确 Batch workset。比值必须由分子/分母重新聚合，禁止简单平均；零分母、缺 J、时区/日期反向、不可比较装备、无数据和权限不足必须 fail-closed，并呈现明确状态。不得用合成趋势填满页面。

V01 必须严格复刻 v33 Demo 的内容层级、Ribbon、筛选条、KPI 几何、两/三/二面板、表格、间距、字体、颜色、交互和下钻。至少完成两目标分辨率、100%/150% DPI、graphite/tactical/light 三主题、Ribbon 展开/收起的截图与盒模型无重叠验收。

### G7：V26 单批次发射事件工作台

实现全部筛选、统计、时间线、WE/非发射行为列表、Cluster、分类例外、单机/编队/独立 Window/V03 回放 deep-link 和 Context 管理入口；受控实现 `gui.batch.events`。

Batch、Release、Context、WE、Perspective 和 Window 必须端到端 exact。没有明细的 Batch 只能诚实显示 EMPTY/DEGRADED 等状态，禁止借用其他批次。分页、取消、缓存隔离、权限、direct API、未知 ID、错误 perspective 和跨批次负面用例必须通过。页面结构、筛选密度、时间线、列表、状态标记和交互必须与 v33 Demo 对齐。

### G8：专项页双视角、V24 与独立事件窗口

完成 V04/V05/V08/V20 的 shooter/target 双视角，V06/V21 shooter-only，单机/编队目标侧差异化组件，独立 Event Window，V24 条件协同和 Master Cursor 联动。

缺几何、共享数据或 series 时禁止造图；目标页不得重复生成 Window 甘特；Strike target 视角必须恒拒绝。V24 只能从 V08 的合法受控入口进入，服务端和 UI 都必须拒绝非法直达、伪造状态和错误角色。完成页面级视觉、交互、三主题、DPI 和 exact deep-link 证据。

### G9：V03 精确回放与深链

完成 WE→exact replay、二维/三维、事件、曲线、HUD/媒体/转写同步、range/LOD、brush/cursor；受控实现 `gui.replay`。历史 Release 禁止 latest fallback。

V26、专项页、独立窗口和 V03 的往返必须保持 exact Batch/Release/Context/WE/Perspective/Window；媒体缺失、时间漂移、对齐状态和不可用原因必须显式呈现。不得使用伪造航迹、几何或媒体占位冒充真实结果。

### G10：其余视图、P3 Model Profile、报告与治理

产品化 V02、V07、V09～V23、V25，完成 V10～V16 P3 Model Profile、V18 ReportRevision/PDF、V22 结构化治理和 V25 会话主题，使 26 个视图功能闭合。

P3 未准入时只能显示受控不可用，禁止计算或展示未准入任务指标；报告 revision 必须不可变；所有治理 mutation 必须具备精确权限、审计、冲突、幂等、错误与回滚语义。每个页面都必须按 v33 Demo 实现实际布局、控件和交互，不能用同一个通用卡片页复制 26 次。

### G11：性能、安全、可访问性与跨平台硬化

完成 CSP、exact origin、nonce、token、file ticket、下载保护、renderer/backend crash 恢复、分页/索引/cache/LOD、WCAG、全键盘/焦点/中文、高 DPI、Windows/Linux Desktop/Service profiles、SBOM、license 和 vulnerability 门。

执行安全负面测试、目标 workload、故障恢复、重复启动/退出、无孤儿进程、安装包 smoke 和可访问性验收。性能阈值必须来自真实实测 authority，禁止凭空填写。Qt WebEngine 必须继续保持 exact loopback origin、原生 bearer/nonce 注入、off-the-record、无持久 Cookie、无远程资源、禁止任意导航/下载/弹窗和失败关闭。无 GLES3 时的软件回退必须按正式门验证，不能靠降低安全边界解决。

### G12：设计封版、全量资格与切换准备

同步并封版总体/工程设计 03、03A、04、05A/B/E/F/G/H/I、06、07、09，生成受控后继 lock/provenance/manifest；完成 26 视图 × 3 主题 × Ribbon 两态视觉矩阵、角色任务、迁移/升级/回滚、旧/新只读投影对比和 W9 重新聚合。

必须满足实施方案第 19 节全部 DoD 才能把 G12 标为 `CLOSED_LOCAL_WITH_GATES`，并且只有本地证据覆盖范围内才可声明 `PRODUCT_COMPLETE`。`PRODUCT_COMPLETE` 仍不等于 `RELEASE_READY`。任何正式外部门、人工视觉批准、跨平台门、安全门或发布审批未完成时，必须保持相应阶段 `IN_PROGRESS`、W9=`NO_GO`，明确列出阻断；不得虚假关闭。

生产切换、旧壳移除、推送、发布和生产部署仍需用户另行明确授权，本提示词不包含这些授权。

## 七、v33 Demo 前端忠实度是每个阶段的硬退出门

不要把“路由能打开、接口有返回、页面有卡片”视为前端完成。必须完整读取 v33 Demo 的 HTML、CSS 和 JavaScript，并逐视图建立元素级对照。实现目标是在桌面产品技术边界允许范围内，使内容、区域顺序、几何比例、控件种类、视觉样式、信息密度、文案和交互行为与 Demo 达到像素级或近像素级一致。

每阶段至少核对并落实：

- 顶部标题/状态区、五模块 Ribbon、组和按钮层级；
- 页面标题、工具条、筛选区、主次面板、分栏比例、滚动、抽屉和弹窗；
- 卡片、表格、时间线、图表、地图/态势、详情、状态条、标签和表单；
- 字体、字号、字重、行高、间距、对齐、边框、圆角、阴影、图标和状态色；
- graphite、tactical、light 三主题，默认 graphite；主题只在会话级生效；
- 展开/收起、跳转、筛选、选择、hover、focus、disabled、loading、empty、degraded、error、forbidden、N/A；
- 100%/150% DPI、目标分辨率、窗口缩放、键盘导航、焦点顺序和 accessible name；
- Demo 中已有中文文案和必要缩写；除必要缩写外，用户可见界面使用中文。

不得用浏览器默认控件、任意间距、临时配色或通用后台模板代替 Demo；不得隐藏关键控件来迁就后端缺口。缺少后端能力时，应补齐 Domain/Application/DTO/API/权限/审计/分页/状态；若能力属于后续阶段，则保留正确结构并显示诚实、受控的不可用状态。

每完成一个视图，都要生成同分辨率、同主题、同 Ribbon 状态的 Demo/实际软件对照截图，记录差异、严重度、整改文件、证据和剩余原因。所有自动视觉差异仍需产品所有者最终人工确认；你不能自行降低阈值或代替用户做主观批准。

## 八、不可破坏的架构、数据和安全不变量

- 前端、REST、GUI、插件不得绕过 Application 直接读取原始文件、数据库表或 Canonical 表。
- WE detector、identity/linker、Attack Cluster、Event Window resolver 和 Perspective projection 必须保持唯一 owner；GUI/REST 不得重复推导。
- 新 API 必须先有 DTO、稳定 route ID、权限、GUI permission、审计、分页、错误/来源语义和机器权威，再注册暴露。
- 未实现、未授权或能力未激活的路由必须保持未注册并 fail-closed。
- 没有真实数据时只显示 `LOADING/EMPTY/DEGRADED/ERROR/FORBIDDEN/N_A` 等明确状态。
- historical/exact 请求禁止回退 latest；Batch、Release、Context、WE、Perspective、Window 必须保持精确身份。
- terminal、adjudication、window、alignment、classification 状态彼此独立，禁止互相冒充。
- Cluster 只是关系；不得把 Cluster 当成 WE 或改变“一发一 WE”基数。
- Strike target 视角恒拒绝；V24 受控入口和路由守卫不能只做前端隐藏。
- 浏览器持久化不得成为业务状态源；Context、主题和治理状态遵循已批准 owner 和会话边界。
- API v1 只能 additive 演进，旧路由语义不得静默改变。
- 新字段先 nullable/明确 unavailable，并由有 provenance 的 backfill 产生；禁止猜测历史值。
- migration/backfill 必须可重复、幂等、版本化、可验证回滚；数据根 manifest 不得被静默改写。
- 任何后继 baseline 都必须有直接父关系、受控 diff、lock、compatibility、migration/backfill/rollback 和证据。CB-1.10.0 及此前基线保持字节不变。
- legacy widgets 在 G11/G12 正式裁决前只作为 feature-flag 诊断回退保留，不得提前删除。

## 九、每个阶段必须完成的工程闭环

对 G6～G12 每个阶段都执行以下流程：

1. 读取实施方案对应工作项、退出门、设计章节、现有权威与前阶段关闭证据。
2. 将阶段标记为 `IN_PROGRESS`，列出可验证工作包和不可破坏不变量。
3. 若机器权威发生变化，建立不可变受控后继；禁止直接改写 CB-1.10.0 或任何历史基线。
4. 同步实现 Domain、Application、runtime、REST、GUI、生成式 client、存储/迁移和权限审计，不允许跨层旁路。
5. 同步更新总体/工程设计增补、authority/conformance matrix、实施方案状态和迁移/回滚说明。
6. 完成本阶段所有页面与 v33 Demo 的布局、样式、控件和交互对照，不以功能可用代替视觉符合。
7. 增加正向、负向、权限、精确身份、数据真实性、分页、取消、迁移、回滚、兼容和回归测试。
8. 执行 Ruff、Mypy、前端 typecheck/build、生成物零漂移、阶段专项 pytest 和风险相称的回归。
9. 在真实 Windows Qt WebEngine 中执行 100%/150% DPI、三主题、Ribbon 两态、键盘、焦点、启动/退出、Demo 截图对照和关键角色任务验收；能自动化的不要交给我。
10. 生成机器可读 evidence、截图/差异记录、中文关闭报告和 `docs/handoff/` 续接记录。
11. 只有全部功能门、设计门、数据门、安全门和本阶段 GUI 忠实度门通过时，才标记 `CLOSED_LOCAL_WITH_GATES`；否则保持 `IN_PROGRESS` 并列出开放门禁。
12. 一个阶段真实关闭后直接进入下一阶段，直到 G12 或遇到真实外部阻断，不必等待我的逐阶段批准。

不要修改历史测试断言来掩盖回归。若后继演进使历史契约需要升级，必须证明后向不变量仍成立，并以新增版本化契约表达受控包含关系。

## 十、测试和证据最低要求

除阶段专项测试外，持续保持以下总门：

- baseline/authority：v33/三 Patch hash、26 view registry、v19 supersession、直接父基线和历史字节不变；
- route/DTO：OpenAPI/Python/TypeScript/route-permission-GUI permission-audit exact parity；
- G5 回归：WE、Cluster、Window、Perspective、supersession、跨批次拒绝、四态和 exact scope；
- V01：同一 Batch 集、范围/时区/空值/去重/零分母/比值重算/装备可比性；
- V23：训练类型确认、持久化、revision、审计、未分类和解析前不入统计；
- 路由：聚合 Batch 不进入其他 Batch V26；所有 deep-link exact；
- 安全：origin、CSRF/nonce/token、direct API denial、file ticket、CSP、下载和缓存隔离；
- 视觉：3 主题 × 26 页 × Ribbon 两态；重点视图覆盖目标分辨率与 100%/150% DPI；
- 可访问性：键盘、焦点、accessible name、对比度、非纯颜色状态、最小可读字号；
- 性能：历史分页、WE 大列表、重叠窗口、Series LOD、切页、播放、内存和 CPU/GPU；
- 稳定性：renderer/backend crash、重启、关闭、重复启动和无孤儿进程；
- 角色任务：教员 V01→V26→双视角→Window→V03→V18；数据管理员 V23→资格→V01；管理员 Context/分类/审计。

测试运行的结果必须记录精确命令、通过/失败/跳过数量、警告和环境限制。不能执行的跨平台、GPU、安装包、人工视觉或外部安全门必须诚实留作开放门禁，不能写成 PASS。

## 十一、需要我人工参与时的报告格式

仅在确实需要我参与时暂停，并一次性给出：

1. 当前阶段和未通过门禁；
2. 为什么无法由你自动完成；
3. 准确命令或 GUI 点击路径；
4. 预期看到的结果；
5. 失败时需要我回传的截图、日志或文件；
6. 该结果会影响哪一项关闭判定。

不要让我重复运行你能在当前机器自动完成的操作。

## 十二、完成 G12 或停止工作时必须留下的回审材料

我之后会回到 Codex 做独立审查。因此，无论完成到哪个阶段，停止前都必须新增或更新最终回审交接文档，至少列明：

- G0R～G12 每阶段的实际状态和关闭证据；
- 当前分支、HEAD、完整 `git status --short --branch` 和 stash 状态；
- 所有新增/修改的 baseline、authority、migration、route、DTO、设计、证据和关闭报告；
- v33 Demo 与实际 GUI 的逐页差异清单、截图矩阵、批准差异和未解决视觉缺口；
- 全量测试命令、通过/失败/跳过数量、警告和环境限制；
- 未通过门禁、技术债、外部门、W9 判定和回滚方法；
- 是否存在未提交修改；明确说明没有执行 push 或生产部署；
- 供 Codex 从 G5 关闭状态开始逐阶段审计的精确文件清单和复验命令。

现在请先在当前 VS Code 工作区自行定位 TPAA 仓库根目录和 v33 Demo，读取本地工作树，复验 `G5=CLOSED_LOCAL_WITH_GATES`，核对 Demo 镜像与外层原始文件，然后直接从 G6 开始持续推进到 G12。严格按 G6→G12 顺序实施；每个阶段同步完成后端、前端、设计、测试、视觉证据和关闭材料。禁止推送、禁止生产部署、禁止 Git 写操作，禁止虚假关闭。

---
