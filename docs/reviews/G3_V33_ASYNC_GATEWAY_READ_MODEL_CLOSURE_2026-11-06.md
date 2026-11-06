# G3 v33 异步 Gateway 与 GUI 组合读模型正式关闭报告

> 日期：2026-11-06
> 阶段状态：`CLOSED_LOCAL_WITH_GATES`
> 实现候选：`b29d456b67727fa04b4ef67e00c4d147437ee5c6`
> 核心基线：`CB-1.8.0 / DB 1.10.0`
> 发布边界：禁止推送、禁止生产部署；本报告不代表 `PRODUCT_COMPLETE` 或 `RELEASE_READY`

## 1. 关闭结论

G3 已在本地完成机器权威、生成型 client、Application 组合读模型、REST 接线、前端异步网关、动态门、真实 Qt WebEngine 验收和设计同步。统一证据 `evidence/gui-g3-v33-closure.json` 返回：

- `status=PASS`；
- `phase_status=CLOSED_LOCAL_WITH_GATES`；
- `source_revision=b29d456b67727fa04b4ef67e00c4d147437ee5c6`；
- `open_gates=[]`；
- `release_claim=false`。

G4～G12 仍为 `NOT_STARTED`。G3 没有实现或伪造 Batch、Weapon Event、历史聚合等后续业务数据。

## 2. 后继基线与生成物

`baseline/CB-1.8.0/` 由 `tools/baseline/adopt_g3_successor.py` 从不可变直接父基线 CB-1.7.0 确定性生成，目录摘要为：

`d1409006850dcb5aebff8d0dbc70730a4d64da76c5768e9951166dd474ce7d7e`

DB schema 保持 1.10.0，因此 G3 无 migration、backfill 和 rollback。新增 `GUI_ASYNC_GATEWAY_AUTHORITY` 与七类跨层 DTO；Python 安全权威、Application 常量和 TypeScript client 由 `g3_gateway_generate.py` 生成，复验零漂移。

G2 历史重建器已改为使用冻结的 G2 输入和追加路由清单，不会因当前运行时增加 G3 路由而重写 CB-1.7.0。G2 successor 与 codegen 仍能独立通过复验。

## 3. 运行时架构

G3 读取链路为：

`WebEngine UI → AsyncGateway/generated client → REST → ApplicationService → GuiGatewayService`

GUI 和 REST 不直接读取原始文件、数据库表或 Canonical 表。Application Gateway 提供：

- 经角色和 GUI 权限过滤的 catalog；
- 不泄露 subject/scope 内容的 bootstrap；
- 机器权威 selector 与真实 Application Query selector 的统一入口；
- request ID、reason code 和 provenance 的稳定响应语义。

动态业务 selector 在 G4 前返回 `items=[] / reason_code=CONTEXT_REQUIRED`，从而明确表达“未接入”，而不是展示 Demo、随机或其他批次数据。

## 4. 权限、路由与审计

运行时安全表由 86 条增加到 89 条，仅新增：

| route ID | 路径 | 授权模式 | 审计 |
|---|---|---|---|
| `api.route.087` | `/api/v1/gui/bootstrap` | `AUTHENTICATED_GUI_PERMISSION / gui.view` | `ALWAYS` |
| `api.route.088` | `/api/v1/gui/catalog` | `AUTHENTICATED_GUI_PERMISSION / gui.view` | `ALWAYS` |
| `api.route.089` | `/api/v1/gui/selectors/{selector_id}` | `AUTHENTICATED_GUI_PERMISSION / gui.view` | `ALWAYS` |

首轮动态验证发现三条路由若同时绑定 `DERIVED_DATA_READ`，会让按 G2 矩阵应能进入 23 个视图的 TRAINEE 在 handler 前被错误拒绝。整改后，统一守卫实际派生并校验 `gui.view`，不再借用业务读取权限；API 审计仍使用稳定 route ID 并对写失败 fail-closed。管理员和学员实测分别得到 26/23 个批准视图。

剩余 12 条 GUI 业务路由全部为 `RESERVED_G3_NOT_EXPOSED`；请求未注册路径时由 `ROUTE_NOT_AUTHORIZED` 默认拒绝。

## 5. 异步与数据安全门

前端网关现具备：

- 同键在途请求去重；
- 同 channel 新请求取消旧请求；
- transport 忽略取消时仍以 generation 拒绝 stale response；
- 默认 8 秒、最大 30 秒超时；
- principal 摘要与 release 双分区内存缓存，分区变化时取消在途请求并清空；
- 最大 100 条/页、100 页聚合、游标循环与篡改拒绝；
- `SUMMARY/BALANCED/DETAIL` LOD、十进制字符串时间和最多 10,000 点校验；
- 只接受短期不透明媒体 ticket，绝对路径、过期或缺少 range/content type/size 的 ticket 拒绝。

七项 TypeScript 动态测试覆盖去重、取消/超时区分、stale 丢弃、双分区缓存、250 项分页/循环、统一错误和 range/media 校验，全部通过。

## 6. 验收结果

| 门禁 | 结果 |
|---|---|
| CB-1.7.0 历史 successor/codegen | PASS，86 路由零漂移 |
| CB-1.8.0 successor/codegen | PASS，89 路由、3 条 G3 route |
| G3 Python/API/contract 专项 | PASS，14 项 |
| G3 TypeScript 动态门 | PASS，7 项 |
| Ruff：`src tests tools migrations` | PASS |
| Mypy/typecheck | PASS，563 个源文件零错误 |
| TypeScript typecheck / Vite build | PASS |
| 确定性双构建 / 离线资源 | PASS，4 个产物、0 远程资源 |
| Qt WebEngine 100% / 150% | PASS / PASS |
| exact-loopback / 原生 bearer+nonce / off-the-record / shutdown | PASS |
| 开发打包器干净工作树门 | PASS（候选提交后复验） |

全仓回归使用 `--import-mode=importlib`，以避开仓库既有的 contract/unit 同名模块收集冲突。首次结果为 `1716 passed / 3 skipped / 2 failed`：一项是打包器按设计拒绝提交前脏工作树，提交后已通过；另一项是 G1 后 `run_desktop` 新增 `config` 参数而旧测试桩未同步，更新测试桩后通过。三项跳过分别需要外部 Prometheus image、S3 endpoint 和 PostgreSQL conninfo，不属于 G3 本地退出门。

Windows 临时 pytest 目录在测试全部完成后出现清理权限提示，不改变测试退出结果。Chromium 报告 GLES3 上下文不可用并回退 GLES2；G3 的 100%/150% 网关和 Shell 验收已通过，但 GPU/renderer recovery 仍留在 G11，不在本阶段伪报关闭。

## 7. 证据与下一阶段

- 统一关闭：`evidence/gui-g3-v33-closure.json`
- 前端构建：`evidence/gui-g3-v33-frontend-build.json`
- WebEngine 100%：`evidence/gui-g3-v33-webengine-100.json`
- WebEngine 150%：`evidence/gui-g3-v33-webengine-150.json`
- 设计增补：`docs/design/TPAA_CB-1.8.0_G3_异步Gateway与GUI组合读模型设计增补_2026-11-06.md`
- 受控后继：`baseline/CB-1.8.0/`

下一阶段是 G4：Batch 登记、V23 导入、训练类型显式确认/修订、解析资格状态机、Force/Formation Context revision 和失败重试。G4 启动前应重新核对其工作项与退出门，并继续禁止推送、生产部署、发布声明和提前暴露未实现路由。
