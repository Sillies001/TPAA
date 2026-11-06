# W9 同一候选综合资格本地关闭记录

日期：2026-10-25

候选分支：`local-r8-review`

边界：本地整改；禁止推送；禁止生产部署

## 1. 关闭结论

W9 当前授权边界内的工程阶段状态正式关闭为：

`CLOSED_LOCAL_WITH_RELEASE_GATES / PASS / NO_GO / NOT_PUSHED / NOT_DEPLOYED / NOT_PRODUCTION_READY`

这里的 `PASS` 只表示 W9 的本地代码、候选聚合器、机器判定模型、运行时投影和本机可执行验证完成；最终发布决定是明确的 `NO_GO`。本地关闭不等于产品正式综合资格通过，更不构成生产发布批准。

## 2. 已实现的硬门禁

- 新增 `W9FinalQualificationStatus`，固定十类最终证据及其顺序，类别缺失、重复或漂移均失败关闭。
- `ACCEPTED` 证据必须同时携带候选身份 SHA-256 和证据 SHA-256；未接受状态禁止伪携带正式绑定。
- 只有十类证据全部 `ACCEPTED` 且绑定同一候选，同时满足零个未豁免 BLOCKER/HIGH、protected-main exact SHA、Hosted CI 成功、独立批准和批准签名时，`formal_release_allowed` 才能为 true。
- 本地组合固定装配 `local_closed()`，通过 `GET /runtime/final-qualification` 输出 `NO_GO`。全量问题尚未完成独立裁决，因此本地状态的 BLOCKER/HIGH 数量为 `null`，不伪称为零。
- 新增 `w9_local_candidate.py`：验证四个开发包 summary、实际包字节数与 SHA-256、统一 source revision、基线锁和依赖锁，生成一个不可变聚合候选身份，并把本地证据逐类绑定到该身份。
- 聚合器仅接受干净 tracked worktree 和当前 HEAD；四包仍明确为 `DEVELOPMENT_NOT_M5_QUALIFIED`，聚合清单固定为 `LOCAL_CANDIDATE_NOT_FORMALLY_QUALIFIED / NO_GO`。
- 锁文件级 `pip-audit` 首轮发现 `certifi 2026.7.22` 与 `cryptography 49.0.0` 的已知漏洞；已分别升级到 `certifi 2026.10.23`、`cryptography 50.0.0`，重新同步并复测后审计结果为 `No known vulnerabilities found`。这只代表审计数据库在本次执行时对锁定生产依赖的结果，不替代源码、配置或独立渗透审查。

## 3. 十类证据的当前状态

| 类别 | 本地结论 | 正式门禁 |
|---|---|---|
| 四 profile 包与 installed runtime | 四个开发包可从同一干净提交构建并聚合 | 四个批准目标环境的安装、启动、停止、卸载和黑盒 E2E 未验收 |
| Authority/Architecture/DTO/OpenAPI/Migration/Replay | 本地契约链完整通过 | 正式资格仍需绑定最终候选和独立批准 |
| Unit/Golden/Integration/Installed E2E | 本地自动化测试通过 | 批准目标环境 installed E2E 未完成 |
| 真实数据与外部系统 | W2/W7 的适配器与 fail-closed 边界保留 | 批准真实数据、生产身份、真实 endpoint 未验收 |
| 安全、角色、隐私、插件 | W3/W7 本地代码与契约通过 | 生产 trust root、组织角色、隐私审批和独立安全裁决未完成 |
| 负载、性能、资源 | W8 authority-bound workload 和阈值已冻结 | 四目标 profile 的持续负载与资源验收未完成 |
| 备份、恢复、DR、升级、回滚 | 本地 PostgreSQL/S3/recovery 路径已验证 | 四目标 profile 现场故障注入、计时 RTO、跨版本升级/回滚未完成 |
| GUI 视觉与人工角色任务 | 自动视觉基线、页面工作流及关闭行为已验证 | 批准显示环境和真实角色人工任务签字未完成 |
| SBOM、来源、签名 | 开发包含 manifest/SBOM/license evidence | 正式 provenance、组织签名和签名验证未完成 |
| protected-main 与 Hosted CI | 历史 PRCB 证据保留且不可冒用 | 当前 W0～W9 候选未推送、未合入 protected main、Hosted CI 未运行 |

## 4. 历史 PRCB 证据边界

仓库中的 PRCB 1.0.1 受保护主线资格证据继续有效地描述其历史候选，但其 source revision 与当前 W0～W9 本地候选不同。W9 聚合器禁止把历史 PRCB 的 14/14 Hosted CI 或签名结论移植到当前候选；当前候选必须形成自己的 exact SHA、目标证据、签名、独立审批和 Hosted CI 闭环。

## 5. 验证与证据位置

- 机器状态：`src/tpaa_qualification/w9_final.py`
- 候选聚合：`tools/qualification/w9_local_candidate.py`
- 运行时端点：`src/tpaa_api/runtime.py`
- 单元测试：`tests/unit/runtime/test_w9_final_qualification.py`
- 聚合器测试：`tests/unit/testing/test_w9_local_candidate.py`
- 符合性矩阵：`docs/compliance/W9_COMPLIANCE_MATRIX.json`
- 操作手册：`docs/operator/W9_RELEASE_GATE_RUNBOOK.md`

本轮最终测试数量、提交 SHA、四包 SHA-256 和本地候选身份 SHA-256 记录在工作空间总整改方案的 W9 正式关闭章节。由本地证据生成的清单位于忽略目录 `evidence/local/w9/`，不作为受控发布记录。

## 6. 正式 GO 的后续条件

正式 `GO` 必须在同一不可变候选上重新完成全部十类证据，独立裁决全部 BLOCKER/HIGH，获得三方或受控流程规定的独立批准，生成并验证组织签名，把 exact SHA 合入 protected main，并由 Hosted CI 对同一 SHA 全部通过。任何一个条件缺失、证据候选不一致或证据哈希异常，决定必须保持 `NO_GO`。
