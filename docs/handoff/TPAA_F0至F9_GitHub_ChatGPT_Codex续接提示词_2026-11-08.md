# TPAA Demo v33 F0～F9 GitHub / ChatGPT Codex 续接提示词

以下正文可直接粘贴到 ChatGPT 的新会话。请在具备仓库写入、终端和测试能力的 Codex/agent 环境中使用；如果当前会话只有 GitHub 搜索/只读能力，必须先明确告知，不得假装已经修改或运行测试。

---

请直接接手 TPAA 软件工程项目，通过已连接的 GitHub 仓库严格实施 Demo v33 功能闭环的 F0～F9 阶段。请全程使用中文回复。

## 一、仓库、基准分支与事实核验

- GitHub 仓库：`Sillies001/TPAA`
- 必须以分支 `codex/v33-f0-f9-handoff-20261108` 为起点。
- 本地移交快照提交：`270ee15344dd2ebbbbd86ec5323a8e171c453811`
- 该提交必须是当前远端分支 HEAD 的祖先；不要从默认分支、旧 G1 分支、v19 分支或早期 CB 基线重新开始。
- 推荐在 Codex worktree 中从上述分支创建新的实施分支，例如 `codex/v33-f0-f9-implementation-20261108`，避免与原 Windows 本地工作树争用同一分支。

开始前必须先执行或完成等价核验：

```powershell
git status --short --branch
git branch --show-current
git log -3 --format="%H %s"
git merge-base --is-ancestor 270ee15344dd2ebbbbd86ec5323a8e171c453811 HEAD
git remote -v
```

只有 `merge-base` 成功且工作树状态明确后才能开始。不得 reset、rebase、force-push 或覆盖当前历史；如果远端已有其他后续提交，先保留双方历史并说明整合方案。

## 二、唯一功能实施方案

F0～F9 必须严格依据：

- `docs/plans/TPAA_Demo_v33功能闭环_MetricDefinition_G10与受治理测试数据全面整改方案_2026-11-08.md`

上位复核与交付门方案：

- `docs/plans/TPAA_G6至G12关闭后复核缺口全面整改与再关闭方案_2026-11-08.md`

二者关系已经在文档中裁决：功能范围以 F0～F9 专项方案为准；安装、跨平台、SBOM、漏洞、目标 workload 和最终发布裁决仍以上位方案 R8/R9 为准，当前暂缓。

不要用本提示词替代仓库事实。必须完整读取方案、相关 machine authority、代码、测试和设计文档后再修改。

## 三、冻结的产品目标与设计输入

GUI 产品目标：

- `docs/gui/demo-v33/source/TPAA_训练复盘交互Demo_v33.html`
- `docs/gui/demo-v33/DEMO_TARGET_BASELINE.json`
- `docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json`
- `docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json`

设计输入：

- `docs/gui/demo-v33/source/TPAA_V8.0_总体设计方案_Patch_历史多批次总览与攻防双视角_v1.3.md`
- `docs/gui/demo-v33/source/TPAA_ED-2.0_工程设计方案_Patch_历史多批次聚合与攻防复盘_v1.3.md`
- `docs/gui/demo-v33/source/TPAA_V8.0_总体与工程设计方案_Patch差距清单_v1.3.md`
- `docs/design/TPAA_V8.0_ED-2.0_Rebaseline_R3.3/`

Demo v33 是页面结构、布局、控件、交互、三主题和任务流目标；Demo 中的数字、曲线和临时浏览器状态不是业务权威，禁止复制为产品事实。

## 四、当前工程事实

- `CB-1.17.0` 是当前不可变父基线，不得改写其任何字节。
- 方案要求创建受控后继候选 `CB-1.18.0-candidate`；发生数据库模型变更时使用 `DB 1.11.0-candidate`。
- 当前旧记录中的 G6～G11 视为 `IN_PROGRESS_REMEDIATION`。
- G12 为 `IN_PROGRESS_EXTERNAL_DOORS_OPEN`。
- W9 为 `NO_GO`。
- `PRODUCT_COMPLETE=false`。
- `RELEASE_READY=false`。
- 旧 G6～G12 关闭报告保留为历史记录，不得作为当前正式关闭依据。
- 当前工作只允许开发、测试、文档和受控工作分支推送；禁止生产部署和发布声明。

本次移交包含 G4～G12 的代码、CB-1.9.0～CB-1.17.0 successor、生成 DTO、测试和视觉 evidence。现有证据中可能记录 Windows 本机绝对路径，这是历史证据属性，不要为了美化路径静默改写证据或哈希；新证据应优先采用仓库相对路径和环境元数据分离。

## 五、F0～F9 的强制实施顺序

必须按以下顺序推进，不得跳过阶段或提前宣称完成：

1. `F0`：状态冻结、dirty-tree/基线快照、CB-1.18.0 successor 与 codegen 脚手架；
2. `F1`：Canonical、三份 Metric Definition、world relation authority、DB 1.11.0 migration、DTO/codegen 和准入包；
3. `F2`：确定性 `GUI_V33_FULL_V1` fixture factory、导入/验证/清理、负面与损坏样本；
4. `F3`：三项任务指标 engine/Application/API/GUI，接入 V01/V02/V09/V18；
5. `F4`：非发射行为、基本飞行、感知、几何、攻击支援及 V07/V19/V24 等页面闭环；
6. `F5`：WGS84 轨迹、测试媒体、媒体 ticket、Range/digest、安全审计和 V03 2D/3D 同步回放；
7. `F6`：P3 装备视图 V10～V16，包含 E-M、探测、告警、攻击系统、非因果条件分离和 EWMA/CUSUM；
8. `F7`：V17 数据质量、V18 不可变报告 revision、V22 治理、V23 来源覆盖与导入队列；
9. `F8`：26 视图前端组件化、Demo v33 布局/样式/控件、三主题、高 DPI、键盘、焦点、角色和视觉矩阵；
10. `F9`：全量功能复核、设计同步、追踪矩阵、证据和人工开放项登记。

每阶段开始前先列出工作项和退出门；完成后运行该阶段全部自动门，生成机器可读 evidence 和中文复核记录，单独提交并推送。只有退出门真实通过才能进入下一阶段。

## 六、三项候选 Metric Definition

必须实现并独立版本化：

- `KILL_RATIO`
- `EXCHANGE_RATIO`
- `MISSION_COMPLETION_RATE`

具体分子、分母、Scope、评价方、去重、J 状态、零分母、缺失、跨批次聚合和证据规则以专项方案第 4、5 节为准。

关键红线：

- Kill Ratio 分母不是发射次数；
- 一个损失由多个 WE/证据引用时只能计一次；
- Exchange Ratio 评价方零损失时保持 `N_A`，不得伪造 infinity；
- Mission Completion Rate 来自冻结的 required objective plan，不用命中数替代；
- pending/unknown 不得按失败或 0 处理；
- 跨批次先合计分子/分母再计算，禁止简单平均 ratio；
- 三项指标先以 `CANDIDATE_TEST_ONLY` 实现，自动测试通过后仍为 `CANDIDATE_AWAITING_BUSINESS_APPROVAL`；未经用户业务确认不得改成 `ADMITTED`。

三项指标必须使用独立 Assessment Metric authority，不得修改或冒充 P1 116 项指标。

## 七、测试数据与真实性边界

请生成真实存在、可由正式导入路径读取、可计算和可回放的测试文件，但其内容必须明确为确定性合成测试场景：

- `data_classification=SYNTHETIC_TEST_FIXTURE`
- `authority_level=TEST_ONLY`
- `production_eligible=false`
- `release_claim=false`

不得把它们描述为真实装备数据、生产实测数据或正式裁决数据。

要求：

- 只有显式 `--fixture-profile GUI_V33_FULL_V1` 或 `TPAA_TEST_FIXTURE_MODE=1` 才可加载；
- 正常/生产 profile 必须拒绝自动回退到 fixture；
- GUI 和导出物持续显示“合成测试数据”；
- fixture 覆盖至少 12 个批次、26 视图、红蓝双方、BVR/WVR/Strike/基本飞行、单机/编队、正常/空/待定/不足/损坏/越权状态；
- 固定 seed、时间和 UUIDv5，重复构建 hash 一致；
- 使用正式 Application/Storage 导入，不直写数据库表；
- 清理工具只删除带精确 fixture lineage 的对象。

## 八、G10 与 GUI 红线

- G10 不得继续以 `NOT_ADMITTED` 占位页面冒充完成；
- V02、V07、V09～V19、V22、V23 按方案第 6 节逐项实现 owner、Canonical、DTO、API、权限、审计、持久化和 GUI；
- G10 路由数量从 authority/codegen 计算，不硬编码旧的 103；
- V15 必须标注 `NON_CAUSAL_ASSOCIATION`，不得输出因果结论；
- V16 的 EWMA/CUSUM 参数由 authority 冻结，不能由页面随意改变；
- V24 只能从 V08 的受控 BVR 协同攻击入口进入，直达、伪 grant、跨批次和 Strike target 必须失败关闭；
- 所有视图必须绑定 exact batch/session/release/context/evaluated_side，禁止 latest 回退或跨批次借数据；
- 前端、REST、GUI 和插件不得绕过 Application 读取原始文件、Canonical JSON 或数据库表；
- 生产无数据时显示真实的 `LOADING/EMPTY/PENDING/N_A/INSUFFICIENT/DEGRADED/INVALID/ERROR/FORBIDDEN`，不得用 Demo 数值或随机曲线填充。

## 九、媒体与安全边界

- 媒体只使用仓库自有或 FFmpeg `testsrc`/`sine` 确定性生成素材；不得下载第三方媒体；
- 媒体 ticket 必须绑定 principal、origin、media、session/release/context、digest、允许范围和用途；
- 客户端不得提交本机绝对路径、任意 URL 或对象存储 key；
- 实现 HEAD、单 byte range、206、416、ETag、`Repr-Digest`/`Content-Digest`；
- 保持 exact loopback origin、native bearer/nonce、off-the-record、无持久 Cookie、无任意导航/下载/弹窗；
- ticket 默认策略在用户确认前只允许 `CANDIDATE_TEST_ONLY`。

## 十、设计同步与代码所有权

实现必须同时更新总体设计、工程设计、GUI、接口、数据和验证分册，以及需求→设计→authority→代码→测试→证据追踪矩阵。

复用既有唯一 owner：Weapon Event、Event Window、Perspective、P3 persistence、quality、governance、batch import、replay context。新增 G10 Application 可以作为 facade/query owner，但不得复制底层领域公式或形成第二套 Canonical 真相源。

## 十一、每阶段必须执行的基础门禁

在 Windows PowerShell 中优先使用仓库 `.venv` 和 `npm.cmd`：

```powershell
$env:POLARS_SKIP_CPU_CHECK='1'

.\.venv\Scripts\python.exe -m ruff check src tests tools migrations
.\.venv\Scripts\python.exe tools/dev/tpaa_dev.py typecheck
.\.venv\Scripts\python.exe -m pytest tests/contract/gui_v33 tests/unit/application tests/unit/api tests/unit/runtime tests/unit/storage tests/unit/gui -q

# 运行当前和新增 successor/codegen 的 --check
.\.venv\Scripts\python.exe tools/baseline/adopt_demo_function_successor.py --check
.\.venv\Scripts\python.exe tools/codegen/task_metric_generate.py --check

Push-Location frontend/gui-v33
npm.cmd ci
npm.cmd run typecheck
npm.cmd run test:gateway
npm.cmd run build
Pop-Location

.\.venv\Scripts\python.exe tools/gui/g1_frontend_build.py
```

还必须运行阶段专属 migration、PostgreSQL、API 负测、fixture、媒体、WebEngine 和视觉门。测试 runner 记录命令、exit code、耗时和产物 hash；脚本内预填 `PASS` 无效。

移交快照的已验证结果，仅用于复验起点，不代表 F0～F9 已完成：

- Ruff：PASS；
- Mypy：`644 source files`，PASS；
- GUI contract + application/API/runtime/storage/GUI 单测：`559 passed`；
- G4～G12 successor `--check`：9/9 PASS；
- G4～G9 codegen `--check`：6/6 PASS；
- 前端 TypeScript：PASS；
- gateway tests：7/7 PASS；
- Vite build：PASS；
- `g1_frontend_build.py`：PASS。

## 十二、人工确认节点

自动开发推进到以下节点时停止改变正式状态，向用户提交逐项中文操作清单：

1. 三项 Metric Definition 业务口径批准；
2. 媒体 ticket 传输策略批准；
3. 26 视图、三主题、角色任务、键盘、高 DPI 和 Demo 对照的人工实机验收。

安装包、Windows/Linux Desktop/Service、SBOM、许可证、漏洞、目标 workload 和正式发布验收当前暂缓，不阻塞 F0～F9 开发，但必须保持 OPEN，不能伪造证据。

## 十三、Git 和交接纪律

- 每个阶段单独提交，提交信息明确 `F0`～`F9`；
- 只推送工作分支，禁止默认/保护分支和生产部署；
- 禁止 force push、reset、rebase 已共享历史或删除既有 G0R～G12 证据；
- 不提交 `.venv`、`node_modules`、`.tmp`、缓存、数据库、令牌、私钥和本机配置；
- 大型生成媒体必须遵守仓库大小政策，必要时使用 Git LFS 或确定性生成脚本；
- 每阶段结束更新 `docs/handoff/`，写明分支、提交 SHA、测试摘要、开放门禁和下一阶段；
- 回复中必须报告远端分支、最新提交 SHA、工作树状态、测试结果和未完成事项；
- 如果遇到需要业务授权或当前执行环境无法完成的真实外部门，保持 `IN_PROGRESS` 并给出用户可执行步骤，不得降低门禁。

现在请先核验仓库和快照事实，完整读取专项方案，汇报 F0 输入与退出门，然后从 F0 开始连续实施。能直接执行的代码、迁移、fixture、测试和文档修改直接执行；只有到上述人工节点或需要新增高风险授权时才请求用户参与。

---

## 使用说明

在 ChatGPT 桌面端或支持 Codex 的界面中，选择 Codex，并以 `codex/v33-f0-f9-handoff-20261108` 作为 worktree 起始分支。确认仓库工具具备写入和终端能力后，再粘贴上述正文。普通只读 GitHub 搜索连接只能用于复核，不足以完成 F0～F9 实施。
