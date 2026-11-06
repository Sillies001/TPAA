# G2 v33 GUI 权限映射候选审查记录（2026-11-06）

**候选：CB-1.7.0；父基线：CB-1.6.0；决策：G2-V33-GUI-PERMISSION-MAPPING-CANDIDATE-2026-11-06**

状态：**PROPOSED / NOT APPROVED**；运行激活：**INACTIVE**；Release claim：`false`。

## 权限事实源
- 九种角色：`src/tpaa_security/permissions.py::SecurityRole`。
- 角色业务权限：`src/tpaa_security/TPAA_SECURITY_POLICY_V1.json#role_permissions`。
- 业务权限枚举：`src/tpaa_security/permissions.py::Permission`。
- GUI 权限只映射现有业务权限，不增加业务角色/业务权限。
- `gui.view` 是认证后已知角色的入口门，不授予数据/API 权限。
- 多角色按现有授权并集；未知角色/权限/上下文默认拒绝；projection role mapping 不反向推导授权。

## GUI 权限映射
| GUI 权限 | 业务权限 | 授予角色 |
|---|---|---|
| gui.view | 已认证且属于九种已知角色 | 九种角色 |
| batch.history.read | DERIVED_DATA_READ | 九种角色 |
| batch.read | DERIVED_DATA_READ | 九种角色 |
| batch.register | SOURCE_IMPORT | INSTRUCTOR、DATA_ENGINEER、ADMINISTRATOR |
| batch.training_type.revise | CONFIGURATION_WRITE | INSTRUCTOR、TRAINING_MANAGER、DATA_ENGINEER、ADMINISTRATOR |
| context.force_formation.read | DERIVED_DATA_READ | 九种角色 |
| context.force_formation.revise | CONFIGURATION_WRITE | INSTRUCTOR、TRAINING_MANAGER、DATA_ENGINEER、ADMINISTRATOR |
| replay.read | RAW_DATA_READ | INSTRUCTOR、EVALUATOR、TRAINING_MANAGER、MAINTENANCE_ENGINEERING、DATA_ENGINEER、ADMINISTRATOR |
| weapon_event.perspective.read | DERIVED_DATA_READ | 九种角色 |
| weapon_event.read | DERIVED_DATA_READ | 九种角色 |
| weapon_event.window.read | RAW_DATA_READ | INSTRUCTOR、EVALUATOR、TRAINING_MANAGER、MAINTENANCE_ENGINEERING、DATA_ENGINEER、ADMINISTRATOR |
| governance.audit.read | SECURITY_AUDIT_READ | ADMINISTRATOR |

## 九角色 × 26 视图
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

- 九种角色均具备入口权限：V01, V02, V04, V05, V06, V07, V08, V09, V10, V11, V12, V13, V14, V15, V16, V17, V18, V19, V20, V21, V23, V25, V26。
- RAW_DATA_READ 限制入口：V03, V24，仅六种 RAW 角色。
- SECURITY_AUDIT_READ 限制入口：V22，仅 ADMINISTRATOR。
- V04/V05/V06/V08/V20/V21/V26 的 event-window 与 replay deep-link 是可选能力。
- V23 register/type-revise 分别要求 batch.register/batch.training_type.revise；V24 formation revise 要求 context.force_formation.revise。
- V24 保持 V08-only，携带 exact Release/Context/WE/Cluster/Formation；V06/V21 保持 shooter-only。
- 完整逐视图、逐角色、能力和动作矩阵以 `GUI_ROLE_VIEW_ACCESS_MATRIX.json` 为机器权威。

## 资源范围与审计
`DERIVED_DATA_READ` 与 `RAW_DATA_READ` 均属于现有 ownership-required 权限。所有读取必须携带 exact ResourceContext；非全局角色必须匹配精确 scope key；历史批次集合逐个授权，任一不匹配则整次拒绝。管理员全局范围只豁免 ownership match，不豁免资源标识、分类和审计。

候选明确枚举敏感读与 mutation 的 ALWAYS-audit 触发，审计粒度为每个 API 操作一次，不按结果行记录。禁止记录 authorization、bearer、desktop_nonce、absolute_path。

## 激活前阻断项
1. `GET /security/session` 只返回业务 `permissions`；缺少服务端派生的 `gui_permissions`。
2. 前端目前把 `payload.permissions` 当 GUI 权限；必须新增独立字段，不能混用两套 ID。
3. `UnifiedPrincipal` 将 `scope_match=true` 转成 `*`，而 AuthorizationService 接受 wildcard；非全局角色精确 scope 负面门禁尚未实现。
4. `ApiAuthorizationGuard` 尚不能证明所有敏感读取和 mutation 均 ALWAYS audit。
5. 71 条 API route 记录缺少稳定 route_id、permission、audit 绑定；GUI query/mutation route IDs 仍为空。
6. 安全/治理正式审批未完成。

## 兼容性与迁移
DB schema 保持 1.10.0；无持久化对象变化，不需要 migration/backfill。API v1 仅规划 additive Session DTO 扩展，尚未实现。CB-1.6.0 不修改，候选 overlay 可直接撤除。

**在上述阻断项和正式审批关闭前，不得激活候选、放行视图、关闭 G2 或启动 G3。**


## 7. G2 安全授权运行时代码硬化批次

本批修改已经进入工作分支，但候选仍为 `PROPOSED_NOT_APPROVED / INACTIVE`：

1. `scope_match` 继续只用于 M8/M9 的冻结领域视图语义，不再自动变成授权 `*`。非全局角色显式携带 `*` 时，ownership-required 权限返回 `RESOURCE_SCOPE_WILDCARD_DENIED`。
2. `GET /security/session` 保留原业务 `permissions` 语义，新增独立 `gui_permissions`、GUI authority id/version/status。候选未激活时 `gui_permissions=[]`，前端因此默认拒绝业务视图。
3. 前端只使用 `gui_permissions` 做视图权限判断，不再把业务 Permission ID 当 GUI Permission ID。
4. 所有经过 W3 business Permission 的 API 请求均在 handler 前记录授权审计；subject 在 security 边界内先做 SHA-256 去标识化。
5. 持久化审计 sink 写失败时 guard 返回 `AUDIT_WRITE_FAILED`，下游 handler 不执行。生产仍使用 SQLite/PostgreSQL SecurityAuditSink 写既有 `audit.audit_log`，没有引入 InMemory 生产适配或影子 schema。
6. 新增未激活的 `API_ROUTE_SECURITY_AUTHORITY.json`，为冻结的 71 条运行路由建立 stable route ID、明确 permission/audit 语义，并原样保留 14 条 GUI reserved routes。运行时仍使用旧 classifier，正式切换需要审批和注册路由 parity 门禁。

这些改动不等于激活 CB-1.7.0，也不构成 G2 关闭。
