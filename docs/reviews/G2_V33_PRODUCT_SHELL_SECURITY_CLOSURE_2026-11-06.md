# G2 v33 产品 Shell、GUI 权限与路由安全正式关闭报告

> 日期：2026-11-06  
> 阶段状态：`CLOSED_LOCAL_WITH_GATES`  
> 实现提交：`f7bd46e02ee9542ddc43bb031d6955082040b005`  
> 核心基线：`CB-1.7.0 / DB 1.10.0`  
> 发布声明：无；禁止推送、禁止生产部署，本报告不代表 `PRODUCT_COMPLETE` 或 `RELEASE_READY`

## 1. 关闭结论

G2 已按项目所有者对 CB-1.7.0 候选的明确授权，在本地完成批准、激活、运行时接线、真实 WebEngine 验收和正式关闭。统一机器证据 `evidence/gui-g2-v33-closure.json` 返回：

- `status=PASS`；
- `phase_status=CLOSED_LOCAL_WITH_GATES`；
- `source_revision=f7bd46e02ee9542ddc43bb031d6955082040b005`；
- `open_gates=[]`；
- `release_claim=false`。

G3～G12 尚未启动。G2 的关闭不放宽任何生产、发布、跨平台或 GPU 资格门禁。

## 2. 权威激活结果

项目所有者批准记录已经受控写入 `baseline/CB-1.7.0/canonical/G2_GUI_SECURITY_APPROVAL.json`：

- 决策：`APPROVED_LOCAL`；
- 激活：`ACTIVE`；
- 范围：GUI 权限、角色/视图矩阵、API 路由安全权威与 G2 本地关闭；
- 限制：`push=false`、`production_deployment=false`、`release_claim=false`。

CB-1.7.0 可由 `tools/baseline/adopt_g2_successor.py` 从不可变父基线 CB-1.6.0 确定性重建，目录摘要为：

`7f207bff8ed6661ee270acabf3b6c55512b906862a321e95677c15615f1be9da`

运行时安全模块由 `tools/codegen/g2_security_generate.py` 生成，复验无漂移。DB schema 继续为 1.10.0，本阶段无迁移和回填。

## 3. 路由与审计闭环

显式路由安全表覆盖 Service 与 Desktop FastAPI 路由并集：

| 项目 | 结果 |
|---|---:|
| 运行时路由总数 | 86 |
| 业务权限路由 | 75 |
| 认证状态/静态壳路由 | 11 |
| 重复 route_id | 0 |
| 未登记路由策略 | `DENY` |
| 业务路由审计 | `ALWAYS` |

运行时不再用 path 字符串启发式推断权限。每条已登记路由都通过稳定 route ID、method/path 模板、业务权限和 audit mode 精确匹配；未登记 route 以 `ROUTE_NOT_AUTHORIZED` 拒绝并记录去标识化审计。

14 条 G1 预留 GUI API 仍未实现、未注册、未暴露。CB-1.7.0 的激活没有把占位接口伪装成可用功能。

## 4. GUI 权限与角色矩阵

`/security/session` 已把既有业务 `permissions` 与 GUI `gui_permissions` 分离，前端只消费后者。九角色运行时派生结果与批准矩阵逐项一致：

| 角色 | 可进入视图数 |
|---|---:|
| TRAINEE | 23 |
| INSTRUCTOR | 25 |
| EVALUATOR | 25 |
| TRAINING_MANAGER | 25 |
| UNIT_ANALYST | 23 |
| MAINTENANCE_ENGINEERING | 25 |
| DATA_ENGINEER | 25 |
| ADMINISTRATOR | 26 |
| MODEL_REVIEWER | 23 |

所有 26 个视图均有非空权限绑定；未知角色、未知 GUI 权限、未绑定视图、会话未就绪和不满足 exact scope 时均默认拒绝。GUI 授权不代替 API 的独立授权、审批和审计。

## 5. Shell、主题、键盘、焦点与 V24

真实 Windows Qt WebEngine 验收在 100% 和 150% 缩放各执行一次，结果均为 PASS：

- 五模块 Ribbon 和 26 视图 registry 正常；训练评估 landing 为 V26；
- `graphite` 为默认主题，`tactical / graphite / light` 三主题均实际切换并留存截图；
- Ribbon 收起/展开状态、`aria-expanded` 和子导航状态一致；
- Alt+2 进入 V26，Alt+1 返回 V01；
- 页面切换后的焦点恢复事务通过；
- 1280×720 下无水平溢出、主内容越界或按钮文字裁切；
- V24 在 UI 中不可直达，只能从 V08 受控进入；服务端直接请求返回 403；
- WebEngine 保持 exact loopback origin、off-the-record、原生 bearer/nonce 注入和干净退出。

六张主题/DPI 截图保存在 `evidence/gui-g2-v33/screenshots/`，其 SHA-256 在两份 WebEngine 证据中锁定。

## 6. 质量门禁

| 门禁 | 结果 |
|---|---|
| `adopt_g2_successor.py --check` | PASS，CB-1.7.0 可重复 |
| `g2_security_generate.py --check` | PASS，86 条路由，零漂移 |
| 确定性 Vite 双构建与 `web_dist` 一致性 | PASS，4 个产物，无远程资源 |
| TypeScript typecheck / production build | PASS |
| `npm audit --json` | PASS，0 个漏洞 |
| Ruff：`src tests tools migrations` | PASS |
| Mypy / typecheck | PASS，555 个源文件零错误 |
| G2 GUI/API/security 回归 | PASS，43 项 |
| G2 WebEngine 100% / 150% | PASS / PASS |
| G2 统一关闭器 | PASS，`open_gates=[]` |

Pytest 有 2 条 Starlette/httpx/anyio 弃用警告；测试退出码为 0。退出后的 Windows 临时目录清理权限提示发生在测试全部通过之后，不是产品失败。Chromium 的 GLES3 共享上下文/软件回退仍属于 G11 正式门禁，本阶段未伪报为 GPU 资格通过。

## 7. 证据与后续边界

- 统一关闭证据：`evidence/gui-g2-v33-closure.json`
- 前端确定性构建：`evidence/gui-g2-v33-frontend-build.json`
- 100% WebEngine：`evidence/gui-g2-v33-webengine-100.json`
- 150% WebEngine：`evidence/gui-g2-v33-webengine-150.json`
- 设计增补：`docs/design/TPAA_CB-1.7.0_G2_GUI权限与API路由安全设计增补_2026-11-06.md`
- 受控后继：`baseline/CB-1.7.0/`

下一阶段为 G3。启动 G3 前应按实施方案重新核对工作项与退出门，并继续保留：禁止推送、禁止生产部署、禁止提前暴露未实现路由、禁止用 Demo/随机数据冒充业务结果。
