# W3 身份、安全、隐私与职责分离关闭报告

日期：2026-10-21
状态：`CLOSED_LOCAL / PASS / NOT_PUSHED / NOT_DEPLOYED / NOT_PRODUCTION_READY`

## 1. 关闭结论

W3 计划范围内的角色权限、身份生命周期、API 授权、资源范围、职责分离、隐私导出、留存冲突、审计和 Desktop 本地身份已经形成可执行实现与自动化证据。权限策略版本为 `1.0.0`，规范化策略 SHA-256 为 `1afd326f3a008cdc9bccdb08c39c214777db9855b92d49232e4b4dd59bc87fbc`。

本关闭只证明本地候选达到 W3 阶段退出条件，不代表已经连接生产 IdP/CA/secret manager，不代表生产插件 trust root 已配置，也不解除 W4～W9、签名发布、现场容量和生产部署门禁。

## 2. 实现范围

| 子项 | 结果 | 主要落点 |
|---|---|---|
| W3-A 权限策略 | 9 个业务角色、默认拒绝、资源 scope/ownership 和 4 个高风险权限已冻结 | `src/tpaa_security/TPAA_SECURITY_POLICY_V1.json`、`permissions.py`、`policy.py` |
| W3-B Service 身份 | OIDC RS256/JWKS rotation、mTLS 链与 SPIFFE、token-certificate binding、撤销和 secret-manager port 已实现 | `identity.py`、`secrets.py`、`tpaa_runtime/federated_identity.py` |
| W3-C 统一授权 | Desktop/Service 共用路由授权分类、负面授权与持久化安全审计；未知路由/角色/权限失败关闭 | `tpaa_security/api.py`、`tpaa_api/unified.py`、`tpaa_runtime/security_audit.py` |
| W3-D 隐私治理 | purpose-bound HMAC 去标识、minimum necessary、导出 manifest、媒体脱敏状态及留存冲突决策已实现 | `tpaa_security/privacy.py` |
| W3-E 职责分离 | maker/checker、审批待办、精确目标散列、过期与一次性消费、重启恢复、break-glass 限制已实现 | `tpaa_security/approval.py`、`tpaa_runtime/approval_repository.py`、`tpaa_api/security.py` |
| W3-F Desktop 身份 | loopback bearer 仅作为通道秘密；业务路由另需绑定 OS account/device 的签名身份 | `tpaa_security/desktop_identity.py`、`tpaa_desktop/__init__.py`、`tpaa_admin/__main__.py` |

公开 Service 入口现只接受 `TPAA_RUNTIME_CONFIG_FILE`，并要求 `identity.mode=OIDC_MTLS`。旧静态 bearer fingerprint 仅保留为内部资格夹具兼容路径，不再是公开 Service 配置入口。Desktop 身份可由 `tpaa-admin identity-issue` 签发短期 assignment；身份缺失、过期、签名错误或 account/device 不符时，业务路由拒绝访问。

## 3. 验证证据

- W3 安全专项：`16 passed`。
- 全量单元测试：`748 passed`，仅 2 条第三方 Starlette/httpx 弃用告警。
- 集成测试：`2 passed / 3 skipped`；跳过项分别需要外部 Prometheus、S3 和 PostgreSQL 环境变量，不属于 W3 本地退出门。
- 全量 Ruff：通过。
- mypy：`516 source files`，零问题。
- Python `compileall`：通过。
- Wheel 构建：通过；已确认 `tpaa_security/TPAA_SECURITY_POLICY_V1.json` 进入 wheel。
- 完整契约测试：`818 passed`，仅 2 条第三方 Starlette/httpx 弃用告警。提交前暴露的身份夹具、旧依赖锁散列、Windows 临时 Git maintenance 竞态和非干净工作树门禁均已修复或在干净候选上按设计通过。
- 干净工作树开发打包：`PASS`；打包器的 clean-tree 门禁未放宽。

## 4. 失败关闭与负面路径

自动化测试覆盖未知角色/权限、scope 不匹配、缺少审批、自批、目标篡改、审批重放、过期 token、错误 issuer/audience、未知或轮换 `kid`、token/certificate 绑定不一致、撤销 token/证书、损坏撤销文件、Desktop 身份缺失/篡改、越权导出、媒体未脱敏、legal hold 和 Release 引用阻止物理删除。

审批事件复用 DB 1.9 的追加式 `audit.audit_log`；重建服务后仍可恢复待办、决定和已消费状态。审计适配器对主体和 API path 做稳定散列，不记录 bearer、JWT、证书、secret、直接人员标识或业务 payload。

## 5. 未解除的生产门禁

1. 由组织安全负责人批准并配置真实 IdP issuer/audience、CA、SPIFFE namespace、role/scope claim 发行规则。
2. 在目标 ingress 验证不可伪造的 TLS client certificate ASGI 扩展；普通 HTTP 证书头继续禁止信任。
3. 接入 Vault/KMS/平台 secret manager，建立轮换、撤销、审计和应急流程。
4. 配置真实 Ed25519 插件 trust root；插件完整安装、隔离与回滚仍属于后续插件阶段。
5. 完成 W4～W9、同一候选签名、外部环境集成、容量/灾备、GUI 角色任务和人工安全验收。

本轮未推送远端、未签名发布、未执行生产部署。
