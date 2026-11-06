# TPAA G1 关闭后 GitHub 续接提示词

以下正文可直接粘贴到 ChatGPT Chat 会话窗口。粘贴后，请在 ChatGPT 中连接 GitHub 仓库 `Sillies001/TPAA`，选择分支 `codex/v33-g1-handoff-20261106`。

---

请直接接手 TPAA 软件工程项目，并通过已连接的 GitHub 仓库继续实施代码修改。请使用中文回复。

## 一、仓库与工作分支

- GitHub 仓库：`Sillies001/TPAA`
- 必须基于分支：`codex/v33-g1-handoff-20261106`
- 不要从默认分支、旧的 v19 分支或 `CB-1.4.0` 重新开始。
- 开始前先读取该分支最新提交、`git status` 等价状态和下列权威文件；不得凭本提示词替代仓库事实。

## 二、当前已完成状态

v33 重构的 G0R 与 G1 已完成本地正式关闭：

- `G0R=CLOSED_LOCAL_WITH_GATES`
- `G1=CLOSED_LOCAL_WITH_GATES`
- `G2～G12=NOT_STARTED`
- 当前状态不等于 `PRODUCT_COMPLETE`、`RELEASE_READY` 或生产部署批准。

关闭报告：

- `docs/reviews/G0R_V33_TARGET_FREEZE_CLOSURE_2026-11-06.md`
- `docs/reviews/G1_V33_MACHINE_AUTHORITY_AND_SCAFFOLD_CLOSURE_2026-11-06.md`

统一证据：

- `evidence/gui-g0-v33/g0r-v33-closure.json`
- `evidence/gui-g1-v33-closure.json`
- `evidence/gui-g1-v33-frontend-build.json`
- `evidence/gui-g1-v33-webengine-smoke.json`

## 三、唯一实施方案与输入材料

必须严格依据：

- `docs/plans/TPAA_HTML_Demo_v33驱动_GUI产品化重构与后端设计同步整改方案_2026-11-06.md`

当前 GUI 法庭记录和三份设计输入已镜像进仓库，必须按冻结哈希使用：

- `docs/gui/demo-v33/source/TPAA_训练复盘交互Demo_v33.html`
- `docs/gui/demo-v33/source/TPAA_V8.0_总体设计方案_Patch_历史多批次总览与攻防双视角_v1.3.md`
- `docs/gui/demo-v33/source/TPAA_ED-2.0_工程设计方案_Patch_历史多批次聚合与攻防复盘_v1.3.md`
- `docs/gui/demo-v33/source/TPAA_V8.0_总体与工程设计方案_Patch差距清单_v1.3.md`

R3.3 前序总体与工程设计包在：

- `docs/design/TPAA_V8.0_ED-2.0_Rebaseline_R3.3/`

关键机器权威：

- `docs/gui/demo-v33/DEMO_TARGET_BASELINE.json`
- `docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json`
- `docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json`
- `baseline/CB-1.6.0/`
- `generated/g1-cb-1.6.0/`

v19 仅为历史参考，不能再作为实现或验收目标。

## 四、从 G2 开始实施

请从方案 G2“产品 Shell、Ribbon、三主题与共享状态”开始，严格按 G2→G12 顺序实施和关闭，不要跳过阶段门禁。

G2 至少要完成：

1. 五模块 Ribbon；
2. V01～V23、V25、V26 权限化导航；
3. V24 只能从 V08 的受控入口进入，服务端与 UI 都必须拒绝非法直达；
4. 训练评估 landing 必须为 V26；
5. 26 视图 registry、返回栈、上下文状态、中文界面和公共状态页；
6. tactical / graphite / light 三主题，默认 graphite，会话级生效，不使用浏览器持久化改变业务状态；
7. 键盘、焦点、高 DPI 和 Ribbon 收起/展开；
8. 没有真实后端数据时必须显示 LOADING/EMPTY/DEGRADED/ERROR/FORBIDDEN/N_A 等明确状态，禁止用 Demo 数值、随机曲线或跨批次数据冒充真实结果。

随后按方案继续 G3～G12。前端、REST、GUI 和插件不得绕过 Application 读取原始文件或 Canonical 表；WE detector、identity/linker、Event Window resolver 必须保持单一 owner。

## 五、不可破坏的工程边界

- `CB-1.5.0` 是不可变直接父基线；不要改写它。
- `CB-1.6.0 / DB 1.10.0` 是 G1 后继候选；如后续阶段需要改变机器权威，必须形成新的受控 diff、lock、兼容性和迁移证据，不能静默改写关闭证据。
- 14 条 v33 GUI 路由在 G1 中是 `RESERVED_G1_NOT_EXPOSED`；只有真正实现权限、DTO、审计、分页/错误语义后才能逐条转为已实现，禁止先暴露占位路由。
- 任务级候选指标仍为 `NOT_ADMITTED`，独立 Metric Definition 准入前不得权威计算或展示。
- WebEngine 必须保持 exact loopback origin、原生 bearer/nonce 注入、off-the-record、无持久 Cookie、无远程资源、禁止任意导航/下载/弹窗和失败关闭。
- 保留 legacy widgets 作为 feature-flag 诊断回退，直到 G11/G12 裁决。
- 禁止生产部署；除非我后续明确授权，不要推送到默认/保护分支，也不要创建发布声明。
- 不要删除或覆盖与当前阶段无关的已有更改。

## 六、每阶段工作方式

每个阶段都应：

1. 先核对方案工作项与退出门；
2. 修改代码、机器权威、迁移、测试和设计文档；
3. 执行与风险相称的测试；
4. 生成机器可读 evidence 和中文关闭报告；
5. 只有所有退出门通过时才把阶段状态改成 `CLOSED_LOCAL_WITH_GATES`；
6. 未通过时保持 `IN_PROGRESS` 并明确剩余门禁；
7. 不得把外部 GPU、跨平台、发布或独立审批门禁伪报为已通过。

建议先复验：

```powershell
$env:POLARS_SKIP_CPU_CHECK='1'
python tools/gui/g0r_v33_verify.py
python tools/baseline/adopt_g1_successor.py --check
python tools/codegen/g1_generate.py --check
python tools/gui/g1_frontend_build.py
python tools/gui/g1_v33_verify.py
python -m ruff check src tests tools migrations
python tools/dev/tpaa_dev.py typecheck
python -m pytest tests/contract/gui_v33 tests/migration/test_g1_v33_db_1_10_0.py -q
```

Qt WebEngine 真实 loopback 烟测在受限容器中可能被 Chromium 子进程沙箱阻断；不要因此修改安全边界。应在允许本机 loopback 和 GUI 子进程的 Windows 环境执行 `python tools/gui/g1_webengine_smoke.py`。Windows 无 GLES3 共享上下文时的软件回退仍是 G11 正式门禁。

## 七、为以后回到本地保留可续接性

我会在完成一段 ChatGPT Chat 修改后回到原 Windows 本地工作空间继续。因此请：

- 将每个阶段的变更提交到明确的远端工作分支，并在回复中给出仓库、分支、提交 SHA、未提交状态和测试摘要；
- 不要强制推送、改写历史或删除 G0R/G1 证据；
- 为新增依赖提交精确 lock，不提交 `.venv`、`node_modules`、缓存、数据库、令牌或本机绝对路径配置；
- 将新阶段状态同步写回实施方案的仓库镜像；
- 结束一段工作时新增或更新 `docs/handoff/` 下的续接记录，列出下一阶段、开放门禁和精确复验命令。

现在请先检查该分支事实并汇报 G0R/G1 复验结果，然后开始 G2。能直接执行的仓库内修改和测试直接执行；需要我亲自操作或新增授权时再给出精确步骤。

---
