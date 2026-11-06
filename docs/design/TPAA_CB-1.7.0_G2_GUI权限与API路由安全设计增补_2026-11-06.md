# TPAA CB-1.7.0 G2 GUI 权限与 API 路由安全设计增补

> 日期：2026-11-06  
> 状态：`APPROVED_LOCAL / ACTIVE_LOCAL_ONLY`  
> 适用阶段：v33 GUI 重构 G2  
> 上位输入：TPAA V8.0、ED-2.1、R3.3 设计包及 v33 三份 Patch  
> 发布边界：禁止推送、禁止生产部署、禁止据此声明发布就绪

## 1. 增补目的

本增补记录项目所有者对 `CB-1.7.0` G2 GUI 权限与 API 路由安全候选的本地批准及运行时落地方式。它不改写已冻结的 R3.3、CB-1.5.0 或 CB-1.6.0，而是以可重建后继基线、生成式运行时权威和关闭证据补齐以下设计缺口：

- GUI 视图权限与既有业务权限缺少可执行映射；
- Service 与 Desktop 的实际 FastAPI 路由图缺少逐路由稳定 ID、权限和审计语义；
- `/security/session` 中业务权限与 GUI 展示权限未形成明确边界；
- V24 条件入口需要 UI 与服务端双重拒绝；
- 三主题、键盘、焦点和高 DPI 需要真实 WebEngine 验收证据。

## 2. 后继基线与机器权威

`baseline/CB-1.7.0/` 是 `CB-1.6.0` 的受控后继，DB schema 继续为 `1.10.0`，不新增迁移或数据回填。其新增或替换的关键权威为：

- `G2_GUI_SECURITY_APPROVAL.json`：项目所有者本地批准记录；
- `GUI_VIEW_CONTRACT.json`：V01～V26 的非空权限绑定和 V24 条件入口；
- `GUI_PERMISSION_AUDIT_AUTHORITY.json`：12 个 GUI 权限、业务权限绑定、scope 和审计规则；
- `GUI_ROLE_VIEW_ACCESS_MATRIX.json`：9 个已知角色对 26 个视图的可复验矩阵；
- `API_ROUTE_SECURITY_AUTHORITY.json`：Service/Desktop 路由并集的逐路由安全绑定。

后继基线由 `tools/baseline/adopt_g2_successor.py` 确定性重建；运行时代码由 `tools/codegen/g2_security_generate.py` 生成。手工编辑生成模块或静默修改关闭后的基线均不允许。

## 3. 权限边界

GUI 权限只决定“界面能力是否可见/可进入”，不能替代 API 授权。运行时遵循以下顺序：

1. 桌面身份解析为一个或多个已知 `SecurityRole`；未知或空角色拒绝；
2. 既有安全策略派生业务 `Permission`；
3. CB-1.7.0 绑定把业务权限投影为 `gui_permissions`；
4. 前端要求目标视图全部 `required_permissions` 同时满足；
5. API 再独立执行逐路由业务权限、exact resource scope、审批和审计判断。

多角色语义为显式角色授权并集。非全局角色不得用 wildcard scope 绕过 exact-resource 判断；仅 `ADMINISTRATOR` 可按既有策略获得全局 scope，且该 scope 只跳过资源所有权匹配，不跳过路由权限、审批或审计。

## 4. 路由安全权威

运行时安全表覆盖 `create_unified_service_app` 与 `create_desktop_app` 的 FastAPI `APIRoute` 并集，共 86 条：

- 75 条业务权限路由：每条均有稳定 `route_id`、显式 `Permission` 和 `audit_mode=ALWAYS`；
- 11 条认证状态/静态壳路由：无业务权限，但仍要求既有桌面认证边界；
- 未登记的 method/path：默认 `DENY`，不得回退到字符串启发式分类；
- 14 条 G1 预留 GUI API：未实现前继续不注册、不暴露，不因本次激活自动上线。

授权审计在 handler 前完成，主体使用哈希去标识化；令牌、nonce、绝对路径等禁止字段不得进入审计载荷。敏感读和 mutation 的审计写失败必须 fail-closed。

## 5. V24 条件入口

V24 不是普通直达页面：

- 唯一允许的前序视图为 V08；
- 前端需要 V24 权限、V08 当前上下文和受控入口状态同时满足；
- Ribbon/子导航不得提供非法直达；
- `/ui?view=V24` 等服务端直达返回 403 和 `V24_REQUIRES_V08_CONTEXT`；
- 返回目标固定为 V08。

UI 隐藏或禁用不能替代服务端拒绝，两侧必须同时成立。

## 6. 会话主题、键盘、焦点与 DPI

- 默认主题为 `graphite`，另有 `tactical`、`light`；主题只在会话内生效，不把业务状态写入浏览器持久化存储；
- Alt 数字键按五模块导航，训练评估模块 landing 固定为 V26；
- Ribbon 支持收起/展开，并维持 `aria-expanded` 与子导航可见性一致；
- 页面切换后按受控事务恢复焦点，保留 `:focus-visible` 和 reduced-motion；
- 1280×720 视口在 100% 与 150% 缩放下不得出现水平溢出、主内容越界或按钮文字裁切。

真实 WebEngine 继续采用 exact loopback origin、原生 bearer/nonce 注入、off-the-record profile、无远程资源和失败关闭。GLES3/软件回退及跨平台 GPU 资格仍属于 G11，不在 G2 中伪报通过。

## 7. 关闭与后续变更规则

G2 的机器关闭证据为 `evidence/gui-g2-v33-closure.json`。关闭只表示本增补覆盖的本地阶段门禁通过；G3～G12 仍须按实施方案逐阶段推进。

后续若改变角色、GUI 权限、视图绑定、路由集合、路由权限或审计语义，必须建立新的后继 authority diff、lock、代码生成物、兼容性/迁移说明和回归证据，不能直接改写本次批准记录或历史关闭证据。
