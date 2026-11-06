# W8 性能、灾备、部署与可观测性本地关闭记录

日期：2026-10-25

候选分支：`local-r8-review`

边界：本地整改；禁止推送；禁止生产部署

## 1. 关闭结论

W8 本地工程范围状态为：

`CLOSED_LOCAL_WITH_TARGET_ENVIRONMENT_GATES / PASS / NOT_PUSHED / NOT_DEPLOYED / NOT_PRODUCTION_READY`

该状态正式关闭 W8 的本地代码、控制面、机器门禁和可在当前主机执行的基础设施验证，但不冒充原整改方案所要求的四目标 profile 现场验收。`WINDOWS_DESKTOP_X64`、`LINUX_DESKTOP_X64`、`WINDOWS_SERVICE_X64`、`LINUX_SERVICE_X64` 在获得目标端点和完整验收证据前均保持 `LOCAL_VERIFIED_TARGET_PENDING`，生产激活恒为禁止。

## 2. 实施结果

| W8 子项 | 状态 | 实现与证据 | 保留门禁 |
|---|---|---|---|
| W8-A Workload Envelope | `CLOSED_PASS_LOCAL` | `/runtime/operations` 直接投影受控 M5 Authority 的 workload、性能阈值和 hash，不在代码或 GUI 另造参数 | 阈值扩展必须走新的受控权威变更 |
| W8-B PostgreSQL/S3 生命周期 | `CLOSED_PASS_LOCAL_TARGET_PENDING` | PostgreSQL 16 真实 write-drain/backup/staging restore 通过；S3 adapter 真实 HTTP 往返、seal/verify/list 通过 | 目标环境 TLS、KMS、retention、生命周期和凭据轮换尚未验收 |
| W8-C Service 控制面 | `CLOSED_PASS_LOCAL` | 严格执行 write-drain → snapshot → verified staging restore → activate → health；健康失败自动 rollback，所有 receipt 绑定同一 snapshot SHA-256 | 目标编排器和流量切换端点尚未验收 |
| W8-D RPO/RTO 与恢复 | `CLOSED_PASS_LOCAL_TARGET_PENDING` | 权威 RPO=0、RTO≤1800 秒由机器状态公开；本地 PostgreSQL 跨库恢复、对象一致性和 fail-closed 逻辑通过 | 四 profile 故障注入、计时 RTO、加密密钥恢复和跨版本现场演练待目标环境执行 |
| W8-E Observability/SLO/Alert | `CLOSED_PASS_LOCAL_TARGET_PENDING` | 结构化 operational status、Prometheus exporter 与 promtool 解析通过；性能阈值从同一 M5 Authority 投影 | 目标采集端、告警路由、值班确认及持续负载 SLO 待验收 |
| W8-F 包、SBOM、升级/回滚 | `CLOSED_PASS_LOCAL_TARGET_PENDING` | 离线 deterministic bundle、包清单、CycloneDX SBOM、依赖/许可证清单和 SHA-256 完整性门禁保留；正式签名要求仍为 false 且不得伪造 | 四目标安装/卸载、升级/回滚和同候选签名属于目标环境/W9 门禁 |

## 3. 新增运行时硬门禁

- `W8OperationsStatus` 只接受固定的四 profile 和固定的六类证据；顺序或集合漂移直接失败。
- `ACCEPTED` 必须同时具有非空环境端点、64 位小写证据 SHA-256，且六类证据全部为 `PASS`。
- 未接受状态禁止携带 endpoint/evidence，避免把未验收环境显示成可用目标。
- 只有四 profile 全部 `ACCEPTED` 时 `production_activation_allowed=true`；本地生产组合使用 `local_closed()`，因此该值为 false。
- Service 恢复控制面验证每一步 stage/state 和同一 snapshot hash；激活后健康检查失败必须先成功回滚，否则不得报告完成。
- `formal_release_claimed` 固定为 false；W8 不替代 W9 同一候选综合资格。

## 4. 主要代码与测试证据

- `src/tpaa_runtime/w8_operations.py`
- `src/tpaa_runtime/recovery.py`
- `src/tpaa_runtime/service_drain.py`
- `src/tpaa_runtime/service_activation.py`
- `src/tpaa_runtime/operational_metrics.py`
- `src/tpaa_runtime/prometheus_metrics.py`
- `src/tpaa_storage/s3_object_store.py`
- `src/tpaa_api/runtime.py`
- `tests/unit/runtime/test_w8_operations_productization.py`
- `tests/integration/test_service_recovery_postgres.py`
- `tests/integration/test_s3_object_store_http.py`
- `tests/integration/test_prometheus_exposition.py`
- `docs/compliance/W8_COMPLIANCE_MATRIX.json`
- `docs/operator/W8_OPERATIONS_RUNBOOK.md`

## 5. 本地基础设施证据边界

当前主机已执行 PostgreSQL 16 真实连接下的 managed write-drain、受控 `pg_dump`、干净 staging `pg_restore` 及对象交叉验证。Prometheus 3.7.3 镜像中的 `promtool` 已接受 exporter 文本。S3 适配器在隔离的本地 Moto 5.2.4 HTTP 服务上完成 bucket、stage、seal、verify、read 和 inventory 往返；该测试验证协议适配器，不等于 MinIO 或目标 S3 产品的安全/生命周期验收。

最终全量测试、静态门禁、候选提交和 clean-worktree 打包结果记录在工作空间总整改方案的 W8 关闭章节。

## 6. 未解除的发布门禁

W8 本地关闭不解除：四 profile 目标硬件容量测试、目标 PostgreSQL/S3 安全配置、TLS/KMS/保留策略、真实 MinIO/S3 生命周期、持续负载 SLO/告警、现场故障注入与计时 RTO、跨版本升级/回滚、四 profile 安装/卸载、组织签名、protected-main 合入、Hosted CI、W9 同候选资格及生产部署。
