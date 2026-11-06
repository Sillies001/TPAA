# G2 v33 产品 Shell、Ribbon、主题与共享状态阶段进展报告

- 日期：2026-11-06
- 阶段：G2
- 状态：`IN_PROGRESS`
- 基线分支：`codex/v33-g1-handoff-20261106`
- 基线提交：`b92229da8dcc23f433ab7fc87f7210adbf32485e`
- G2 初始实现代码快照：`6eb4522b55ab3c1768565803e65ff11b50c618d7`
- TypeScript TS18047 修复提交：`4b5e51f2abfc3aaea63c287a94d26a4b092f3155`
- 发布声明：无；本报告不代表 G2 关闭、产品完成、发布就绪或部署批准。

## 1. 本轮实施范围

本轮从 G1 安全空壳开始实现 G2 产品导航框架，未进入 G3 及后续阶段。

1. 前端直接导入 v33 Final View Registry、CB-1.6.0 GUI_VIEW_CONTRACT 和 GUI_PERMISSION_AUDIT_AUTHORITY；启动时核验 26 个 View ID、五个模块和 V26 训练评估 landing。
2. 实现五模块 Ribbon、按模块生成的视图子导航、返回栈和共享上下文条；V24 不进入普通导航列表。
3. 导航授权读取现有 `/security/session` 会话投影，并按机器权威的 `required_permissions` 检查权限；未知权限默认拒绝。当前 GUI_VIEW_CONTRACT 的逐视图 `required_permissions` 为空，本阶段不自行发明角色—视图权限映射；数据 API 仍由后端既有授权机制保护。
4. V24 UI 直接 query/hash 入口拒绝；V08 入口要求精确 BVR、Release、Context、Weapon Event、Attack Cluster 和 Formation 授权上下文。G2 没有真实 WE 查询，因此入口保持禁用，不伪造事件或授权。
5. Desktop FastAPI middleware 增加 V24 直接 path/query 拒绝，不新增或暴露 G1 的 14 条预留 GUI API 路由。
6. 实现 tactical / graphite / light 三主题、默认 graphite、内存会话状态、Ribbon 收起/展开、键盘模块快捷键、返回快捷键、焦点可见性和响应式布局。
7. 非 V25 视图没有真实业务读模型时显示 LOADING、FORBIDDEN、DEGRADED、ERROR 或 N_A；不生成随机曲线、合成批次、虚构裁决或跨批次结果。

## 2. 新增测试与验证工具

- `tests/contract/gui_v33/test_g2_v33_shell_contract.py`
- `tests/unit/api/test_g2_v33_conditional_view_guard.py`
- `tools/gui/g2_v33_verify.py`
- `evidence/gui-g2-v33-progress.json`

验证脚本只报告静态合同检查和仍未完成的门禁，不会把未运行的测试或构建标记为 PASS。

## 3. G2 当前验证状态

| 检查 | 当前状态 |
|---|---|
| G0R/G1 已存证据复核 | PASS_STATIC_REVIEW |
| 26 View / 五模块 / V26 landing 权威一致性 | 已实现，待运行 G2 verifier |
| V24 UI 直接访问保护 | 已实现，待浏览器测试 |
| V24 服务端 path/query 保护 | 已实现，待 pytest |
| 三主题与共享状态 | 已实现，待 TypeScript / Vite 构建 |
| TypeScript typecheck | NOT_RUN |
| Vite 确定性双构建 | PENDING |
| `src/tpaa_gui/web_dist` 同步 | PENDING；本轮没有用非 Vite 方式伪造构建产物 |
| Python Ruff / pytest | NOT_RUN |
| WebEngine 实机、键盘、焦点、高 DPI 和视觉检查 | PENDING |

## 4. 尚未关闭的门禁

1. 在 Windows 工作空间执行 `npm ci`、`npm run typecheck`、`npm run build`，由 Vite 正式生成并同步 `src/tpaa_gui/web_dist`。
2. 运行 `python tools/gui/g1_frontend_build.py`，确认双构建字节一致、dist 与当前源代码一致且无远程资源。
3. 运行新增加的 Ruff / pytest 测试及 G0R/G1 全部复验命令。
4. 在真实 Windows WebEngine 环境验证精确 loopback、权限会话、V24 负面路径、三主题、键盘焦点、Ribbon 两态和高 DPI。
5. 评审实际桌面 principal / permission matrix。当前逐视图权限列表为空，不得把前端可见性当作服务端授权。

## 5. 工程边界确认

- CB-1.5.0 未修改；CB-1.6.0 及其 G1 锁和关闭证据未修改。
- G1 的 14 条 GUI 路由继续保持 `RESERVED_G1_NOT_EXPOSED`。
- 任务级指标继续保持 `NOT_ADMITTED`。
- WebEngine exact loopback、bearer/nonce 原生注入、off-the-record、无持久 Cookie 和失败关闭代码未修改。
- 未推送默认分支、未创建发布声明、未生产部署。
- G2 未满足全部退出门，必须保持 `IN_PROGRESS`；G3 不得提前启动。


## 6. Windows 首轮构建反馈与修复（2026-11-06）

用户在指定工作分支同步后执行 `npm ci` 成功；`npm run typecheck` 和 `npm run build` 均因同一组 12 处 TypeScript TS18047 失败。问题定位为 `document.querySelector("#app")` 的可空类型在 `render()` 闭包中未保留非空收窄。

已在提交 `4b5e51f2abfc3aaea63c287a94d26a4b092f3155` 修复：将元素查询结果命名为 `rootElement`，执行 fail-fast 空值检查后，显式建立 `const root: HTMLDivElement = rootElement`；并增加 G2 合同测试断言。没有关闭 strictNullChecks、没有使用 `@ts-ignore`，也没有修改依赖版本。

修复后的 Windows typecheck / Vite build 尚待用户重新执行。npm audit 同时报告 1 项 high severity vulnerability；尚未执行 `npm audit fix` 或 `--force`，待取得 `npm audit --json` 并评估依赖影响后再决定处理。


## 7. Windows 本地验证与质量工具链修复（2026-11-06）

用户已在 Windows 指定工作分支报告以下通过结果：
- `npm ci`、`npm run typecheck`、`npm run build` 均通过。
- `tools/gui/g1_frontend_build.py --output <TEMP>` 通过，4 个文件，两次干净构建及当前 dist 一致。
- `tools/gui/g2_v33_verify.py --output <TEMP>` 返回 `status=IN_PROGRESS`，静态检查成功且未关闭阶段。
- 前端构建更新了 `src/tpaa_gui/web_dist` 的 manifest、index、JS/CSS hashed assets；这些变更是正式构建产物，不得清理或丢弃。

Python 门禁未通过启动：
- Ruff 不在用户当前全局 Python 环境。
- 全局 pytest 为 8.4.1，低于冻结的 9.0.2。
- `tpaa_dev.py typecheck` 原 fallback 使用 `uv run --locked --with`，与未列入运行时 `uv.lock` 的临时 pinned quality tool 冲突。

已提交 `b7d2d6b4067b4e265a11d3ae5122c6ccd058c092`：fallback 改为 `uv run --frozen --with <exact-version>`，不会要求改写 canonical uv.lock；更新 `tests/contract/test_m0_dev_toolchain.py` 的期望命令。待用户同步并复验 lint/mypy/pytest。

npm audit 仍报告 1 项 high severity；尚未获得 `npm audit --json`，不得盲目升级依赖。


## 8. Mypy 严格类型检查反馈及修复（2026-11-06）

用户在 Windows 执行 `python tools/dev/tpaa_dev.py lint` 成功；`typecheck` 报告 3 处错误，全部位于 `tools/gui/g2_v33_verify.py`，根因是从 JSON `dict.get` 取出的数组值未先校验为非空对象数组。

已提交修复（提交 `c5df327b6ed42f7f06c3d8d079f52ed63c36856a`）：新增 `_object_list(value: object, label: str) -> list[dict[str, Any]]`，明确校验值为数组、成员为字符串键 JSON 对象；将 registry.views、contract.views、registry.modules、routes.reserved_routes、permissions.permissions 全部通过该 helper 验证后再迭代。新增 G2 合同测试覆盖有效数组、null 和非对象成员。此修复仍待 Windows Mypy / pytest 复验，不得标记为 PASS。


## 9. Mypy 通过与 G2 CSS 合同测试误报修正（2026-11-06）

用户确认 Mypy：`Success: no issues found in 549 source files`。定向 Pytest 结果为 5 passed、1 failed。失败仅来自合同测试对 reduced-motion media query 的空格格式假设；真实 CSS 是有效的 minified 形式 `@media(prefers-reduced-motion:reduce)`，语义规则存在。

已修正测试为 whitespace-tolerant regex，要求仍然存在 `prefers-reduced-motion: reduce` media query，但不再绑定 minifier 的空格输出格式。此项仅改测试断言，未改 CSS 或弱化无障碍要求。等待 Windows 重跑确认。


CSS media-query 合同断言最终正则已在 `8abd5b48df4010127314be0bc5745e2e47709be8` 校正为有效 Python raw regex；本次仍只修复测试的空白容忍，不修改产品 CSS。等待定向 Pytest 复验。


## 10. 定向测试通过后的权限模型审查（2026-11-06）

用户确认定向 Pytest `6 passed, 2 warnings`，Ruff 和 Mypy 已通过。

静态 authority review 发现：CB-1.6.0 的 GUI_VIEW_CONTRACT 26 个 `required_permissions` 全为空；GUI_PERMISSION_AUDIT_AUTHORITY 虽有 11 个 default-deny permission IDs，但没有 per-view bindings，也没有与 TPAA_SECURITY_POLICY_V1 中实际角色权限的机器映射。前端原 `[].every(...)` 为空数组真空成立，且 V25 存在无条件放行，因此不能声称权限化导航已实现。

已实施 fail-closed 修正：所有视图（包括 V25）必须处于 READY 会话并拥有非空显式权限绑定；V24 还必须满足受控 grant 和权限；G2 verifier 将记录全部缺失绑定并维持 IN_PROGRESS。后续需形成新的受控 authority successor diff、lock、兼容性与迁移证据，不得修改已关闭的 G1 CB-1.6.0。


## 11. Latest G2 security correction and revalidation state (2026-11-06)

Remote implementation revision: `55a59a661b1929aa80888b0afb82b7c0e99e7274`.

Windows results on the preceding revision: Ruff PASS, Mypy PASS (549 files), G2 targeted tests 6 passed / 2 warnings. A subsequent fail-closed correction now denies navigation for any view whose machine contract has an empty or missing `required_permissions`, removes the V25 bypass, and requires V24 permission bindings in addition to its controlled grant. The verifier reports all unbound views and retains G2 as IN_PROGRESS. The G1 WebEngine smoke script gained an optional output path so the G1 closure evidence file is not overwritten during rechecks.

This latest correction is not yet Windows-verified. The prior 6-pass test result must not be attributed to this new revision. A controlled G2 successor authority diff is required before populating view permissions; CB-1.6.0 must remain unchanged.


## 12. WebEngine smoke startup failure triage (2026-11-06)

The latest Windows rerun passed Ruff, Mypy (549 files), 7 targeted tests, G0R, G1 successor, G1 codegen, G1 frontend build and G1 static verification. The WebEngine smoke failed before LISTENING with `CONTROL_CHANNEL_CLOSED`. The child process stderr was redirected to DEVNULL, preventing root-cause visibility. A diagnostic-only injection point was added to LocalBackendController: default remains DEVNULL; G1 smoke inherits stderr to console. Next action is rerun and inspect the first child traceback. No assumption about a runtime defect has been made.


## 13. Confirmed child import-path failure and fix (2026-11-06)

The diagnostic smoke rerun surfaced ModuleNotFoundError: No module named 'tpaa_api' from the base interpreter. The source root was present in the smoke parent's in-memory sys.path, but not in the child process environment. The lifecycle controller now propagates the package root through PYTHONPATH for every child launch, preserving any existing PYTHONPATH entries. The Windows base-interpreter/venv launcher logic is retained. Unit/contract tests were added for both same-interpreter and Windows venv-redirector cases. Windows end-to-end smoke verification remains pending.