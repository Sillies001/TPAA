# TPAA CB-1.8.0 G3 异步 Gateway 与 GUI 组合读模型设计增补

> 日期：2026-11-06
> 状态：`APPROVED_LOCAL / ACTIVE`
> 适用阶段：v33 GUI 产品化 G3
> 直接父基线：`CB-1.7.0`
> 后继基线：`CB-1.8.0 / DB 1.10.0`
> 边界：禁止推送、禁止生产部署、无发布声明

## 1. 设计裁决

G3 将 GUI 基础读取链路收敛为：

`Qt WebEngine / Vite UI → 生成型 TypeScript client → exact-loopback REST → ApplicationService → GuiGatewayService → 机器权威或后续 Application Query`

前端、REST、桌面壳和插件不得绕过 Application 读取原始文件、数据库表或 Canonical 表。G3 仅开放 catalog、bootstrap 和 selector 三条基础读取路由；Batch、Weapon Event、历史聚合等真实业务投影由 G4 以后逐阶段准入。

## 2. 机器权威与版本

- `CB-1.7.0` 保持不可变，G3 通过 `tools/baseline/adopt_g3_successor.py` 确定性生成 `baseline/CB-1.8.0/`。
- DB schema 保持 `1.10.0`，G3 不引入 migration、backfill 或 rollback。
- `GUI_ASYNC_GATEWAY_AUTHORITY` 定义请求、缓存、分页、range/LOD、媒体 ticket 和错误策略。
- `CROSS_LAYER_DTO_CONTRACTS` 新增或补齐 `GuiCatalogDTO`、`GuiBootstrapDTO`、`GuiSelectorDTO`、`GuiGatewayErrorDTO`、`GuiCursorPageDTO`、`SeriesRangeDTO` 和 `MediaTicketDTO`。
- Python 运行时权威、Application 常量和 TypeScript client 常量由 `tools/codegen/g3_gateway_generate.py` 生成；手工修改生成物属于漂移并拒绝关闭。

## 3. 路由与权限模型

G3 激活：

| route ID | 方法与路径 | 授权 | 审计 |
|---|---|---|---|
| `api.route.087` | `GET /api/v1/gui/bootstrap` | 已认证且 `gui.view` | `ALWAYS` |
| `api.route.088` | `GET /api/v1/gui/catalog` | 已认证且 `gui.view` | `ALWAYS` |
| `api.route.089` | `GET /api/v1/gui/selectors/{selector_id}` | 已认证且 `gui.view` | `ALWAYS` |

GUI 基础读取不是业务 `DERIVED_DATA_READ` 的替代品，也不应被错误绑定到该业务权限。统一 API 守卫先完成身份/角色裁决，再从批准的 GUI 权限权威派生 `gui.view`；缺失、未知或审计写失败均默认拒绝。这样既允许获得 G2 批准视图的学员角色启动 Shell，又不扩大任何业务读取权限。

其余 12 条 GUI 业务路由标记为 `RESERVED_G3_NOT_EXPOSED`，既不注册 FastAPI handler，也不进入运行时安全表。直接请求由未知路由默认拒绝机制拦截。

## 4. Bootstrap、Catalog 与 Selector

Bootstrap 返回：当前角色、GUI 权限、资源 scope 数量、经授权过滤的 catalog、selector 定义、机器来源和主体缓存分区摘要。它不得返回主体 ID、原始资源 scope、凭据或本机路径。

Catalog 只包含当前角色拥有全部 required permissions 的视图。批准矩阵下，`TRAINEE=23`、`ADMINISTRATOR=26`；其他角色继续由同一权威动态派生，不在 UI 中硬编码。

Selector 分两类：

- `modules`、`views`：只读机器权威，可立即分页返回；
- `releases`、`contexts`、`batches`、`weapon_events`、`perspectives`：依赖真实 Application Query。G4 前返回空集合和 `CONTEXT_REQUIRED`，禁止用 Demo、随机或跨批次数据填充。

## 5. 并发、取消、超时与 stale 响应

- 同一缓存分区内，方法、URL、规范化 query 和 body 相同的在途请求只执行一次；
- 同一交互 channel 的新请求取消旧请求；即使底层 transport 忽略取消，generation 校验仍将旧响应标记为 `STALE_RESPONSE`，不得写回当前状态；
- 默认超时 8 秒、最大 30 秒；超时与用户取消分别映射为 `TIMEOUT` 和 `ABORTED`；
- 不自动重试不安全方法；G3 三条路由均为 GET。

## 6. 缓存隔离

缓存仅存在于当前 WebEngine 会话内存，不写 Cookie、localStorage、IndexedDB 或磁盘。键空间至少包含：

`principal_cache_key + release_id + method + URL/query + canonical body`

主体或 release 变化时立即取消全部在途请求、清空缓存和 generation。`principal_cache_key` 是主体/角色/scope 的 SHA-256 分区摘要，不是可回传的身份标识。跨主体与跨 release 命中均为禁止行为。

## 7. 游标分页、range/LOD 与媒体 ticket

- 游标为带版本、selector、query context、offset 和校验值的不透明字符串；篡改、跨主体、跨 release 或跨 selector 复用返回 `CURSOR_INVALID`。
- 默认页大小 50，最大 100，单次聚合最大 100 页；重复游标返回 `CURSOR_LOOP`。
- session time 以十进制字符串传输，避免 JavaScript 整数精度损失；LOD 仅允许 `SUMMARY/BALANCED/DETAIL`，最多 10,000 点。
- 媒体访问只接受短期不透明 ticket；必须带 content type、size、range support 和 expiry；绝对路径、过期 ticket 或缺失元数据默认拒绝。

## 8. 错误、原因与来源

统一错误码覆盖 `ABORTED`、`TIMEOUT`、`STALE_RESPONSE`、`CURSOR_INVALID`、`CURSOR_LOOP`、`CONTEXT_REQUIRED`、`FORBIDDEN`、`NOT_FOUND`、`BACKEND_UNAVAILABLE`、`INVALID_RESPONSE` 和 `SYSTEM_ERROR`。响应必须带 request ID、reason code、retryable 和 `GUI_ASYNC_GATEWAY_AUTHORITY / 1.0.0 / CB-1.8.0` 来源；未知错误按 `SYSTEM_ERROR_FAIL_CLOSED` 处理。

## 9. 验收与后续边界

G3 关闭要求同时通过：基线与 codegen 零漂移、路由/角色/DTO 契约、Python API 动态测试、TypeScript 并发与缓存动态测试、确定性离线构建，以及 100%/150% DPI 下真实 Qt WebEngine exact-loopback、原生 bearer/nonce 注入、off-the-record 和干净退出。

G3 关闭不代表业务页面完成。G4 才能引入 Batch 登记、V23 导入、训练类型修订及相应持久化/审计；任何新增业务路由必须形成新的受控 authority diff、DTO、权限、审计和迁移证据。
