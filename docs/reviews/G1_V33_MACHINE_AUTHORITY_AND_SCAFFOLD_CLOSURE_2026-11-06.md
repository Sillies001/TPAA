# G1 v33 机器权威与工程脚手架关闭报告

> 日期：2026-11-06  
> 阶段状态：`CLOSED_LOCAL_WITH_GATES`  
> 适用目标：`GUI-DEMO-V33-2026-11-05`  
> 发布声明：无；本报告不代表生产资格、发布就绪或部署批准。

## 1. 关闭结论

G1 已在本地按《TPAA_HTML_Demo_v33驱动_GUI产品化重构与后端设计同步整改方案》完成正式关闭。机器权威、版本和兼容性、受控迁移、候选生成物、离线前端构建、安全 WebEngine 空壳及失败关闭路径均已形成可复验的代码与证据。

G1 只批准并冻结后续实现所需合同，不伪造业务功能：14 条 v33 GUI 逻辑路由均标记为 `RESERVED_G1_NOT_EXPOSED`，当前 OpenAPI 不包含这些未实现路由；任务级候选指标保持 `NOT_ADMITTED`。

## 2. 语义与持久化裁决

| 概念 | G1 裁决 |
|---|---|
| BatchWorkset | Application 查询作用域，不持久化 |
| BatchRegistration / BatchMetadata | 审计化、修订化持久对象 |
| WeaponEvent | 复用现有 Event subtype/relations，不建平行事实表 |
| AttackCluster | 复用现有 Relation subtype |
| EventWindow | 可重建、带 resolver 版本的投影，不持久化 |
| Perspective | 授权化 read model，不持久化 |
| Force / Formation Context | 有效时间修订对象，持久化并审计 |
| HistoricalOverview | exact Batch set 聚合 read model，不持久化 |
| TaskMetricDefinition | 独立指标准入前不得权威计算或展示 |

单一 owner 规则同时冻结：WE detector 与 Event Window resolver 由 Application 层唯一拥有；浏览器业务持久化和 GUI 业务重算均禁止。

## 3. 后继权威与迁移

- 直接父基线：`CB-1.5.0`，锁哈希 `ecdb68d0aa17ad49b2b0b3bdbad0e82559cd455725a0eb2a2a4855feba99edab`；原文件未被改写。
- 后继候选：`CB-1.6.0 / DB 1.10.0 / ED-2.1 / R3.4`。
- 受控 artifact：42 个，全部通过锁字节、数量、core compatibility 和 loader 验证。
- 新持久关系：`registry.batch_registration`、`registry.batch_training_type_revision`、`context.force_formation_context_revision`、`context.force_formation_member`。
- SQLite 迁移已验证 `1.9.0 → 1.10.0 → 1.9.0` 空表回滚；非空新增关系按设计拒绝降级并保持 `1.10.0`。
- API 兼容策略保持 v1 additive；没有重定义既有 route。

## 4. 确定性生成与前端空壳

- CB-1.6.0 连续重建目录摘要一致。
- Python/OpenAPI/TypeScript 候选连续生成摘要一致，且与签入候选零漂移。
- Vite 7.2.2 / TypeScript 5.9.3 使用精确 lock；两次干净 production build 字节清单一致。
- `web_dist` 共 4 个文件，脚本和样式采用内容哈希文件名，不包含远程资源引用。
- WebEngine 使用严格 loopback origin、原生 bearer/nonce 注入、off-the-record profile、内存缓存、禁持久 Cookie、禁本地文件/远程跳转/下载/弹窗，并在后端不可用或 renderer 终止时 fail-closed。
- 安全空壳真实启动、`/ui` 加载、关闭与后端不可用降级均通过；受限执行沙箱会阻断 Chromium 子进程 loopback，故该烟测在授权的本机真实环境执行。

Windows 当前环境未建立 GLES3 共享上下文时会进入软件渲染路径。该现象未被伪报为 GPU 资格通过，正式 GPU/软件回退、跨平台和 renderer recovery 仍属于 G11。

## 5. 验证结果

| 门禁 | 结果 |
|---|---|
| `tools/baseline/adopt_g1_successor.py --check` | PASS |
| `tools/codegen/g1_generate.py --check` | PASS |
| `tools/gui/g1_frontend_build.py` | PASS，双构建一致 |
| `tools/gui/g1_webengine_smoke.py` | PASS，真实 loopback 生命周期 |
| `tools/gui/g1_v33_verify.py` | PASS，统一关闭证据已生成 |
| Ruff（`src tests tools migrations`） | PASS |
| mypy / typecheck | PASS，548 个源文件零问题 |
| G1/GUI/API/迁移/运行入口回归 | PASS，47 项 |

唯一非产品告警为 Starlette/httpx 弃用提示；不影响本阶段结果。pytest 退出后的 Windows 临时目录清理权限提示发生在测试已返回成功之后，不属于产品失败。

## 6. 证据与后续边界

- 统一证据：`evidence/gui-g1-v33-closure.json`
- WebEngine 生命周期：`evidence/gui-g1-v33-webengine-smoke.json`
- 前端构建：`evidence/gui-g1-v33-frontend-build.json`
- 候选基线：`baseline/CB-1.6.0/`
- 候选生成物：`generated/g1-cb-1.6.0/`

G1 关闭后进入 G2。仍未关闭的正式门包括：G2～G10 产品功能、G11 性能/安全/可访问性/跨平台硬化、G12 设计封版与独立发布批准。当前仍禁止推送、生产部署和发布声明。
