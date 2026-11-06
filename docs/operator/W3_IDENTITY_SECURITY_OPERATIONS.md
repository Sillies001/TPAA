# W3 身份与安全运维手册

## Service 配置

Public Service 必须通过 `TPAA_RUNTIME_CONFIG_FILE` 加载 `TPAA_RUNTIME_CONFIG_V1`。`identity` 必须为：

```json
{
  "mode": "OIDC_MTLS",
  "issuer": "https://identity.example.mil",
  "audience": "tpaa-service",
  "jwks_uri": "https://identity.example.mil/.well-known/jwks.json",
  "ca_bundle": "/etc/tpaa/trust/client-ca.pem",
  "allowed_spiffe_prefixes": ["spiffe://tpaa/service/"],
  "revocation_file": "/etc/tpaa/revocations.json"
}
```

ASGI/TLS termination 必须把已协商的叶证书以 `extensions.tls.client_cert_chain` 传入应用。应用不信任普通 HTTP 证书头。JWT 必须包含 `iss/sub/aud/exp/iat/jti/tpaa_roles/tpaa_scopes/cnf.x5t#S256`。

撤销文件格式：

```json
{
  "schema": "TPAA_REVOCATION_REGISTRY_V1",
  "revoked_tokens": [{"issuer": "https://identity.example.mil", "jti": "..."}],
  "revoked_certificates": [{"fingerprint": "...", "serial_number": 123}],
  "issuer_not_before": {"https://identity.example.mil": 1792569600}
}
```

每次鉴权重新读取撤销文件；格式损坏或文件不可读时失败关闭。JWKS 按 TTL 缓存，遇到未知 `kid` 强制刷新一次，支持无停机 key rotation。

## Secret 与轮换

配置只允许 secret reference，不允许明文。当前提供 `EnvironmentSecretManager` 作为 Desktop/开发适配器和可注入的 `SecretManager` port；生产部署应由 Vault/KMS/平台 secret provider 实现该 port，并提供 key id、version、not-before、expiry 和 revocation。任何无 active version 的解析均失败关闭。

## 审批操作

- `POST /security/approvals`：maker 为精确 API path 建立请求；
- `GET /security/approvals`：checker 查看与自身角色匹配的待办；
- `POST /security/approvals/{id}/decision`：不同主体批准或拒绝；
- 执行高风险 API 时传 `X-TPAA-Approval-Id`；授权中间件在分派前校验并一次性消费。

审批失败不会降级为普通写入。若业务处理在审批消费后失败，必须重新申请，以避免批准凭据重放。

## Desktop

使用 `tpaa-admin identity-issue` 生成 `<data-root>/desktop-identity.json`，再设置 `TPAA_DESKTOP_IDENTITY_FILE` 与 `TPAA_DESKTOP_IDENTITY_KEY_REF`。assignment 到期、签名不符、账号或设备不符时，业务路由返回 `DESKTOP_LOCAL_IDENTITY_REQUIRED`；health/readiness 保留用于排障。

## 生产启用前检查

1. 组织安全负责人批准 IdP issuer/audience、CA、SPIFFE namespace、role claim 和 scope 发放规则；
2. 用目标 ingress 验证 ASGI TLS 扩展，禁止可伪造的 client-cert header；
3. 执行 token expiry、wrong issuer/audience、JWKS rotation、jti revoke、issuer not-before、证书 revoke/rotation 测试；
4. 验证 approval、break-glass、导出和拒绝事件进入集中审计且不含直接身份或 secret；
5. 配置真实 secret manager 和插件 Ed25519 trust root；
6. 在同一候选构建完成备份恢复、负载、GUI 角色任务和发布签名门禁。
