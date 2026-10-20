# W3 身份、安全、隐私与职责分离基线

状态：`APPROVED_LOCAL_BASELINE / DEFAULT_DENY / NOT_PRODUCTION_DEPLOYED`

权威机器可读工件为 `src/tpaa_security/TPAA_SECURITY_POLICY_V1.json`。运行时按规范化 JSON 计算 SHA-256，并把该 hash 写入授权决定、审批事件和导出 manifest；未知角色、权限、字段或缺失策略均失败关闭。

## 决策冻结

- 业务角色：Trainee、Instructor、Evaluator、Training Manager、Unit Analyst、Maintenance/Engineering、Data Engineer、Administrator、Model Reviewer；旧五角色仅作为 P4/P5/P6 视图投影。
- 四项高风险权限：`MODEL_RELEASE`、`PRODUCT_PUBLISH`、`PUBLICATION_OVERRIDE`、`PLUGIN_INSTALL`。
- 高风险动作必须采用不同主体 maker/checker、明确理由、精确目标 hash、有效期和一次性消费；自批、篡改目标、过期、重复使用均拒绝。
- break-glass 仅 Administrator 可申请，最长 30 分钟，必须有 ticket 和理由；不得绕过插件 trust root，所有事件写入审计。
- Service 身份为短期 OIDC RS256 access token + mTLS client certificate binding。校验 issuer、audience、exp、iat、jti、kid、JWKS rotation、SPIFFE scope、证书链和动态撤销文件。
- Desktop loopback token 只保护本地 HTTP 通道。用户身份来自绑定 OS account/device 的短期签名 assignment；身份缺失时业务角色路由关闭。
- operational/sensitive 人员、团队与媒体数据按 purpose 做 HMAC-SHA256 去标识；导出执行 minimum necessary，记录 policy hash、payload hash、redaction、retention 和 media redaction 状态。
- legal hold 或历史 Release 引用阻止物理删除；系统返回 KEEP/ARCHIVE 决定，不静默破坏历史可解释性。
- 外部插件仍需部署提供 Ed25519 trust root；未签名插件禁止。完整插件安装、隔离、回滚在后续插件阶段实现，本阶段只冻结权限和 trust-root 门。

## 审计边界

授权拒绝以及身份读取、导出、重标识、高风险和撤回动作进入 `audit.audit_log`。主体采用稳定散列 key，API path 采用散列对象 ID，审计记录不保存 bearer、JWT、证书、secret、直接人员标识或业务 payload。

审批 inbox 复用 DB 1.9 追加式审计账本，因此 Desktop/Service 都具备重启后可重建的请求、决策和消费状态，不新增旁路数据库表。

## 本地关闭边界

W3 本地关闭证明代码合同、负面授权、身份生命周期、审批、去标识导出、留存冲突和审计实现通过。它不证明目标 IdP、CA、TLS termination、HSM/secret manager、网络边界、组织人员授权或生产插件 trust root 已部署；这些仍是生产部署门禁。
