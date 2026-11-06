# TPAA G2 阶段 GitHub 续接记录

- 日期：2026-11-06
- 仓库：`Sillies001/TPAA`
- 工作分支：`codex/v33-g1-handoff-20261106`
- G2 开工基线：`b92229da8dcc23f433ab7fc87f7210adbf32485e`
- G2 前端修复快照：`4b5e51f2abfc3aaea63c287a94d26a4b092f3155`
- Python 质量工具 fallback 修复：`b7d2d6b4067b4e265a11d3ae5122c6ccd058c092`
- 当前阶段：`G2=IN_PROGRESS`
- 前置阶段：`G0R=CLOSED_LOCAL_WITH_GATES`，`G1=CLOSED_LOCAL_WITH_GATES`
- 后续阶段：`G3～G12=NOT_STARTED`

## 本轮变更

G2 已建立 v33 产品 Shell 的源代码框架：五模块 Ribbon、25 个常规视图导航、machine-authority 驱动的 view contract / permission checks、V24 双端直接访问拒绝、三主题、共享导航/领域/回放/呈现状态、会话权限读取和无假数据状态面板。Windows 本地已报告 npm ci、TypeScript typecheck、Vite build、G1 前端双构建确定性门禁和 G2 静态 verifier 通过；G2 仍为 IN_PROGRESS。

本轮没有重建 `src/tpaa_gui/web_dist`。必须在原 Windows 工作空间使用锁定的 Node 依赖执行 Vite 构建，不能手工伪造 dist 或修改 G1 确定性构建门禁。

## 下一步必须执行

确认工作区没有其他未提交更改、且本地已快进到本记录对应提交后，在仓库根目录：

```powershell
$env:POLARS_SKIP_CPU_CHECK='1'
Push-Location frontend/gui-v33
npm ci
npm run typecheck
npm run build
Pop-Location

python tools/gui/g1_frontend_build.py
python tools/gui/g2_v33_verify.py
python tools/dev/tpaa_dev.py lint
python tools/dev/tpaa_dev.py typecheck
uv run --frozen --with pytest==9.0.2 pytest tests/contract/gui_v33/test_g2_v33_shell_contract.py tests/unit/api/test_g2_v33_conditional_view_guard.py -q

python tools/gui/g0r_v33_verify.py
python tools/baseline/adopt_g1_successor.py --check
python tools/codegen/g1_generate.py --check
python tools/gui/g1_v33_verify.py
```

随后在 Windows 本机执行 `python tools/gui/g1_webengine_smoke.py`，并对三主题、Ribbon 两态、V24 非法直达、键盘焦点和 DPI 布局进行实机检查。

## 未关闭门禁

- Vite typecheck / build / web_dist 同步：Windows 已通过，需将生成的 dist 产物纳入最终 G2 代码提交；
- Python Ruff / mypy / pytest：工具 fallback 修复已提交，等待本地复验；
- G0R/G1 复验脚本本机执行；
- WebEngine 实机与视觉检查；
- 实际桌面 principal / permission matrix 评审。

在这些门禁通过前，不得将 G2 标记为 `CLOSED_LOCAL_WITH_GATES`，不得启动 G3，不得修改默认/保护分支，不得部署或发布。


## Windows 本地验证反馈（2026-11-06）

用户报告在本地 HEAD `3bb9d4b3486bed92c2dd63353c57f9533d5f3add`：
- `npm ci`：PASS；npm audit 报告 1 项 high severity，未执行自动修复。
- `npm run typecheck`：PASS。
- `npm run build`：PASS；生成新的 `src/tpaa_gui/web_dist` 资源。
- `python tools/gui/g1_frontend_build.py --output %TEMP%\paa-g1-frontend-build-recheck.json`：PASS，4 个文件，两次干净构建及当前 dist 一致。
- `python tools/gui/g2_v33_verify.py --output %TEMP%\paa-g2-v33-progress-recheck.json`：返回 IN_PROGRESS，符合阶段未关闭预期。
- 本地 git status 仅报告 web_dist manifest/index/hashed assets 的生成变更；不得丢弃，应在受控提交中保留。
- 直接 `python -m ruff` 因当前全局 Python 环境未安装 Ruff 而未执行。
- `python tools/dev/tpaa_dev.py typecheck` 触发 uv 的 `--locked --with mypy` 锁更新冲突。
- 直接 `python -m pytest` 使用了全局 pytest 8.4.1，低于项目要求 9.0.2。

根因及修复：`tools/dev/tpaa_dev.py` 使用 `uv run --locked --with <pinned-tool>`，但 Ruff/mypy/pytest 是 TOOLCHAIN.json 中固定的临时质量工具，并未列入运行时 `uv.lock`。uv 的 `--locked` 因临时 `--with` 依赖要求锁文件更新而失败。提交 `b7d2d6b4067b4e265a11d3ae5122c6ccd058c092` 将其改为 `uv run --frozen --with <exact-version>`，保留 canonical uv.lock 不变，并更新合同测试。该修复尚待 Windows 复验。

下一次本地同步后，执行：
```powershell
git fetch origin
git pull --ff-only origin codex/v33-g1-handoff-20261106
python tools/dev/tpaa_dev.py lint
python tools/dev/tpaa_dev.py typecheck
uv run --frozen --with pytest==9.0.2 pytest tests/contract/gui_v33/test_g2_v33_shell_contract.py tests/unit/api/test_g2_v33_conditional_view_guard.py -q
```


## Mypy 复验反馈与 G2 验证器修复（2026-11-06）

用户报告：
- `python tools/dev/tpaa_dev.py lint`：PASS。
- `python tools/dev/tpaa_dev.py typecheck`：Mypy 在 `tools/gui/g2_v33_verify.py` 报告 3 处类型错误：`contract_views` / V24 的动态 JSON 列表可能为 None，且 `reserved_routes` 可能为 None。

修复方案：新增 `_object_list(value: object, label: str) -> list[dict[str, Any]]`，对 registry.views、contract.views、registry.modules、routes.reserved_routes 和 permissions.permissions 进行运行时对象数组校验；对 null、非数组、非对象成员 fail-closed 报错。V24 和保留路由循环现在只消费经过校验的对象列表。新增合同测试覆盖正常对象数组、null 和非法成员。

当前结果：Ruff 用户报告 PASS；本次 Mypy 修复尚未在 Windows 复验。G2 继续保持 `IN_PROGRESS`。


## G2 Python 质量门禁反馈与 CSS 合同断言修正（2026-11-06）

用户在 Windows 本地确认：
- `python tools/dev/tpaa_dev.py typecheck`：PASS，549 个 source files 无 Mypy 问题。
- G2 定向 Pytest：5 passed、1 failed。
- 唯一失败是合同测试硬编码要求 CSS 包含 `@media (prefers-reduced-motion:reduce)`，但真实 `style.css` 经压缩后合法形式为 `@media(prefers-reduced-motion:reduce)`。CSS 中确实存在 prefers-reduced-motion 规则，属于测试断言格式过严，不是产品 CSS 功能缺失。

修复：将测试改为 whitespace-tolerant regex `@media\\s*\\(prefers-reduced-motion\\s*:\\s*reduce\\)`，保留对 reduced-motion 语义的检查，同时接受压缩和格式化 CSS。没有修改 CSS 产物，也没有放宽其他 G2 合同断言。修复提交后需重新运行定向 pytest。


CSS 合同断言已在提交 `8abd5b48df4010127314be0bc5745e2e47709be8` 进一步修正为单反斜杠的 Python raw regex（`@media\s*\(prefers-reduced-motion\s*:\s*reduce\)`），以匹配 minified CSS。等待用户重新执行定向 Pytest。


## 2026-11-06：G2 定向测试通过、权限门禁审查

用户在 Windows 指定工作分支执行：
- `uv run --frozen --with pytest==9.0.2 pytest tests/contract/gui_v33/test_g2_v33_shell_contract.py tests/unit/api/test_g2_v33_conditional_view_guard.py -q`：`6 passed, 2 warnings`。
- Ruff：PASS。
- Mypy：`Success: no issues found in 549 source files`。

进一步静态审查发现 G2 尚有关键权限门禁缺口：
- `baseline/CB-1.6.0/canonical/GUI_VIEW_CONTRACT.json` 中 26 个视图的 `required_permissions` 全部为空。
- 前端原逻辑使用 `required_permissions.every(...)`，空数组会真空成立；V25 还曾被显式放行。因此“任何已认证角色可打开所有视图”，并非真正的权限化导航。
- `GUI_PERMISSION_AUDIT_AUTHORITY.json` 定义 11 个 default-deny GUI permission IDs，但没有 per-view binding，也没有映射到现有 `TPAA_SECURITY_POLICY_V1.json` 权限的机器权威。
- 不能静默编辑 G1 的 CB-1.6.0；必须通过受控后继 authority diff/lock/compatibility/migration 完成映射后再开放视图。

已提交的下一步安全修正：
- 前端新增 `hasViewPermissions`；会话未 READY、视图权限列表为空/缺失、权限未在 catalog 中 default-deny 或会话未授予时全部拒绝。
- 删除 V25 的无条件授权捷径。
- V24 受控入口同样检查 V24 的明确权限。
- G2 静态 verifier 将列出无权限绑定视图并标记 `BLOCKED_MISSING_VIEW_PERMISSION_BINDINGS`，而不是把空数组当作 permission gate 通过。
- G1 WebEngine smoke 新增可选 `--output`，默认行为不变；G2 复验可写入 TEMP，不覆盖 `evidence/gui-g1-v33-webengine-smoke.json`。

G2 仍为 `IN_PROGRESS`。本轮新增权限安全修正待 Windows npm build、Mypy、Ruff、定向 Pytest 和 G2 verifier 复验。


## Latest remote revision and Windows test status (2026-11-06)

- Latest code revision: `55a59a661b1929aa80888b0afb82b7c0e99e7274`.
- User-confirmed previous revision checks: Ruff PASS; Mypy PASS (549 source files); targeted G2 tests `6 passed, 2 warnings`.
- After that pass, an additional fail-closed permission correction was committed: no view (including V25) is navigable unless the session is READY and the authoritative view contract contains a non-empty permission list; V24 also requires its view permissions.
- The G2 verifier now explicitly reports all views lacking permission bindings and records the gate as `BLOCKED_MISSING_VIEW_PERMISSION_BINDINGS`.
- The G1 WebEngine smoke tool now accepts `--output` so a fresh smoke can write to TEMP without overwriting the original G1 closure evidence.
- The new permission correction, verifier, tests and smoke CLI have not yet been rerun on Windows. The earlier 6-pass result applies to the previous code revision only.
- Exact next step: sync branch and run the consolidated command block in the latest ChatGPT handoff. Do not mark G2 closed.


## WebEngine smoke failure investigation (2026-11-06)

User reran G0R/G1 checks successfully and G2 verifier remains IN_PROGRESS. The G1 WebEngine smoke failed at LocalBackendController.start() with CONTROL_CHANNEL_CLOSED before receiving LISTENING. Inspection found stderr was hardwired to DEVNULL, so the child startup traceback was hidden. A narrowly scoped diagnostic change was made: LocalBackendController gains an optional child_stderr stream, defaulting to DEVNULL (production behavior unchanged); the G1 smoke explicitly passes child_stderr=None to inherit the PowerShell console stderr. This should expose the actual child-side exception on rerun. No runtime root cause is asserted until that traceback is observed.


## WebEngine child import-path root cause and correction (2026-11-06)

The inherited-stderr rerun exposed the actual child exception: the interpreter could not resolve tpaa_api.local_backend_child because src had been added only to the parent's in-memory sys.path. A new Python process does not inherit that mutation. The correction passes the package root (the parent of tpaa_gui) through the child environment's PYTHONPATH, on Windows and POSIX, while preserving existing entries. Windows venv redirector bypass and __PYVENV_LAUNCHER__ handling remain intact. Local Windows runtime verification is pending.