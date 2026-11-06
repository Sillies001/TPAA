# G2 v33 产品 Shell、Ribbon、主题与共享状态阶段进展报告

- 日期：2026-11-06
- 阶段：G2
- 状态：`IN_PROGRESS`
- 基线分支：`codex/v33-g1-handoff-20261106`
- 基线提交：`b92229da8dcc23f433ab7fc87f7210adbf32485e`
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
