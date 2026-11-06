# W8 运维、恢复与目标环境验收手册

## 1. 运行时状态

读取：

`GET /runtime/operations`

响应必须为 `TPAA_W8_OPERATIONS_STATUS_V1`，并包含：

- 权威、baseline lock、workload、performance 和 recovery profile 的 SHA-256；
- 冻结 workload 数量、并发度与性能/资源阈值；
- RPO/RTO 和禁止 partial cross-store restore 的规则；
- 固定四 profile 的六类证据状态；
- `production_activation_allowed` 与 `formal_release_claimed`。

本地候选的正常值是 `production_activation_allowed=false`、`target_environment_acceptance_claimed=false`、`formal_release_claimed=false`。不得通过修改 HTTP 响应或 GUI 文案绕过该门禁。

## 2. Service 恢复控制顺序

1. `WRITE_DRAIN / MANAGED_WRITES_BLOCKED`：获取 PostgreSQL managed-write 排他门禁并记录 watermark。
2. `SNAPSHOT / VERIFIED`：生成数据库与对象存储的一致性快照及 SHA-256 清单。
3. `RESTORE_STAGING / VERIFIED_NOT_ACTIVATED`：只恢复到已确认干净的 staging 目标；任何一字节损坏在目标变更前失败。
4. `ACTIVATE / ACTIVATED_PENDING_HEALTH`：目标保持 writes disabled，切换受控流量。
5. `HEALTH_CHECK / READY`：同一 snapshot 的健康检查通过后才能报告成功。
6. 任一激活后健康失败必须执行 `ROLLBACK / PRIOR_TARGET_RESTORED`；回滚失败属于阻断性事故，不得继续发布。

每个 receipt 的 `snapshot_sha256` 必须一致，审计记录使用 `TPAA_W8_SERVICE_CONTROL_AUDIT_V1`。成功结果为 `TPAA_W8_SERVICE_CONTROL_RESULT_V1 / ACTIVATED_READY`。

## 3. 目标 profile 验收

四个 profile 必须分别完成以下六类证据，缺一不可：

1. `HARDWARE_WORKLOAD_PERFORMANCE`
2. `POSTGRES_SECURITY_LIFECYCLE`
3. `OBJECT_STORE_SECURITY_LIFECYCLE`
4. `RECOVERY_RPO_RTO_FAILURE_INJECTION`
5. `OBSERVABILITY_EXPORTER_SLO_ALERT`
6. `PACKAGE_INSTALL_UPGRADE_ROLLBACK`

只有六类全部 `PASS`，且记录受控 `endpoint_ref` 与验收包 SHA-256，profile 才能成为 `ACCEPTED`。四 profile 全部接受之前禁止生产激活。

批准的部署配置加载器应使用 `build_w8_operations_status(authority, records)` 构建状态，不得直接拼接 HTTP 响应。该构造器严格验证 profile 顺序、证据类别集合、状态、endpoint 和 evidence hash；当前生产组合有意只装配 `local_closed()`，在目标配置加载器经过独立评审之前没有激活旁路。

## 4. 最低目标环境检查

- 硬件满足受控 M5 target hardware profile，按冻结 workload 完整执行并记录 wall time、query latency/throughput、RSS、CPU 和磁盘增长。
- PostgreSQL 使用 TLS、最小权限、备份账号隔离、审计和凭据轮换；对象存储使用 TLS、服务端加密/KMS、versioning、retention/lifecycle 和最小权限策略。
- 注入数据库不可达、对象损坏、对象存储不可达、进程终止、健康检查失败和 current pointer 损坏；验证无静默部分恢复。
- Prometheus 抓取 exporter，在持续 workload 下验证 SLO 和告警路由，并由值班接收方确认告警闭环。
- 在干净目标安装/启动/停止/卸载；验证离线性、SBOM/许可证/原生依赖、包 manifest hash；执行失败安装回滚。存在同 profile 的前一受理版本后，必须执行真实升级与回滚。
- 目标证据不得含 token、password、cookie、authorization、private key 或连接串。

## 5. 当前本地候选边界

当前候选仅完成本地主机与隔离 Docker/HTTP 服务可执行部分。目标 endpoint、TLS/KMS、组织告警路由、现场硬件、四 profile 安装和生产签名未配置，因此必须保持 `LOCAL_VERIFIED_TARGET_PENDING`。W9 还需把全部证据绑定到同一不可变候选 hash、protected-main exact SHA 和 Hosted CI。
