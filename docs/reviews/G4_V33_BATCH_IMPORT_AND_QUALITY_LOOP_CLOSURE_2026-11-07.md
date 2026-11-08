# G4 v33 批次登记、导入与质量闭环正式关闭报告

> 日期：2026-11-07
> 阶段状态：`CLOSED_LOCAL_WITH_GATES`
> 实现工作树基准提交：`e0a9677090ea6249c4883e6d503035aea9cd801a`
> 核心基线：`CB-1.9.0 / DB 1.10.0`
> 边界：仅本地关闭；禁止推送、生产部署和发布声明

## 1. 关闭结论

G4 已完成并通过机器权威、代码生成、Application/Runtime/API、V23 原生安全导入、V01 合格批次列表、训练类型修订、Force/Formation Context 有效时修订、前端构建、真实 Windows WebEngine 和回归测试门禁。统一证据为 `evidence/gui-g4-v33-closure.json`，结果为：

- `status=PASS`；
- `phase_status=CLOSED_LOCAL_WITH_GATES`；
- `open_gates=[]`；
- `release_claim=false`。

本结论只关闭 G4，不表示产品完成、可发布或可生产部署。G5～G12 仍未启动。

## 2. 受控后继与权威

`baseline/CB-1.9.0/` 以不可变 `CB-1.8.0` 为直接父基线，DB schema 保持 `1.10.0`。G4 新增并激活：

- `G4_BATCH_IMPORT_APPROVAL`；
- `GUI_BATCH_IMPORT_AUTHORITY`；
- Batch、Training Type Revision、Force/Formation Context 与 Import Ticket 的跨层 DTO；
- 7 条 `IMPLEMENTED_G4` 路由及对应安全、权限和强制审计记录。

运行时安全路由由 89 条增加到 96 条；剩余 6 条 G5+ 路由继续保持 `RESERVED_G4_NOT_EXPOSED`，没有提前注册或暴露。生成式 Python/TypeScript 客户端与 CB-1.9.0 受控输入复验零漂移。

## 3. 领域与数据闭环

G4 实现的状态链为：

`PENDING_CONFIRMATION → PARSING → QUALIFIED | FAILED`

关键约束如下：

- Batch ID 使用 `UUID5(actor, idempotency_key)`，重试保持同一业务身份；
- 禁止默认训练类型；未确认时只能进入 `UNCLASSIFIED / PENDING_CONFIRMATION`；
- V01 只展示 `QUALIFIED` 批次；
- 失败解析可在不可变清单约束下重试；
- 训练类型采用追加式审计修订；
- Force/Formation Context 采用带生效时间的追加式审计修订；
- UI、REST 不直接读取原始文件或 Canonical 表，业务读写统一经过 Application；
- 无真实数据时不生成 Demo 数值、随机曲线或跨批次替代值。

## 4. V23 原生导入安全

文件与目录选择由 Qt 原生选择器完成。前端只发起受控 same-origin native action；原生层读取有界字节并向 exact-loopback Import Ticket 端点上传，前端和 REST 响应均不暴露本机路径。Ticket 仅保存在进程内，具备 600 秒 TTL 和 64 MiB 上限。任意外部导航、非法 action 或缺少 bridge 的请求均失败关闭。

真实桌面验收覆盖 V23 选择、登记、解析、资格化、跳转 V01、训练类型修订和 Force/Formation Context 修订；100% 与 150% 缩放均验证 `off-the-record=true`、`native_path_exposed=false`、`shutdown_state=EXITED`。

## 5. 验证结果

| 门禁 | 结果 |
|---|---|
| CB-1.8.0 历史后继复验 | PASS |
| CB-1.9.0 successor/codegen | PASS，零漂移 |
| G4 Python/Application/Runtime/API/GUI/Storage/Contract 专项 | PASS |
| TypeScript typecheck / gateway 动态测试 | PASS |
| 确定性双构建、离线资源、已签入 web_dist | PASS |
| Ruff：`src tests tools migrations` | PASS |
| Mypy/typecheck | PASS，573 个源文件零错误 |
| Windows WebEngine 100% / 150% | PASS / PASS |
| V23→V01、修订闭环、本机路径禁止 | PASS |
| 排除洁净树打包套件后的全量回归 | `1723 passed / 3 skipped / 0 failed` |

3 项跳过分别需要外部 Prometheus image、S3 endpoint 和 PostgreSQL conninfo，不属于 G4 本地退出门。Windows pytest 临时目录清理权限提示和一个 GBK 解码 warning 不改变测试退出码。

开发打包器继续按设计拒绝有已跟踪修改的工作树；门禁没有被放宽。`tests/contract/test_m0_dev_toolchain.py` 必须在后续本地候选提交形成洁净工作树后复验，属于候选整理/打包动作，不是 G4 功能关闭缺口。

## 6. 证据与后续阶段

- 统一关闭证据：`evidence/gui-g4-v33-closure.json`
- WebEngine 100%：`evidence/gui-g4-v33-webengine-100.json`
- WebEngine 150%：`evidence/gui-g4-v33-webengine-150.json`
- 设计增补：`docs/design/TPAA_V8.0_ED-2.0_Rebaseline_R3.3/G4_v33_批次登记导入与质量闭环设计增补_2026-11-07.md`
- 受控后继：`baseline/CB-1.9.0/`

下一阶段为 G5：历史多批次聚合、WE/Cluster/Window resolver、V02/V03/V04/V22 及相关真实读模型。G5 启动前应重新核对方案工作项与退出门；继续禁止推送、生产部署、发布声明和提前暴露未实现路由。
