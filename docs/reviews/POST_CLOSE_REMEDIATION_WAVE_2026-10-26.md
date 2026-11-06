# W0～W9 关闭后短周期整改波次记录

日期：2026-10-26

分支：`local-r8-review`

起始提交：`b113a172004c9698924fd53c14723f93670eee8a`

边界：仅本地修改与验证；未推送、未签署生产发布、未执行生产部署。

## 1. 关闭结论

本波次按“W9 严格发布判定 → migration/mypy 零失败 → P13 门禁呈现与正式证据加载器 → GUI 完整功能和真实视觉/角色任务验收”的顺序完成。工程状态关闭为：

`CLOSED_LOCAL / PASS / W9_NO_GO / NOT_PUSHED / NOT_DEPLOYED / HUMAN_SIGNOFF_PENDING`

`PASS` 表示本波次代码、静态门禁、自动化回归、真实本地 Desktop 工作流和可重复证据均通过；它不改变 W9 正式发布决定。当前主工作树含本波次未提交修改，运行时未配置独立发布机构签署的正式证据，因此 P13 和 `/runtime/final-qualification` 必须继续显示 `NO_GO`。

## 2. W9 严格发布判定

- 删除发布判定中的字符串/整数宽松转换；`"false"` 不再可作为真值，布尔值不再可冒充 finding count，候选记录字段不再经 `str()` 隐式归一化。
- W7、W8 入口同步收紧文本、布尔、计数和 SHA-256 类型检查，错误类型在状态构造前失败关闭。
- 新增真值字符串、布尔计数、记录字段类型和候选漂移负面测试。
- clean-worktree 门禁未放宽：当前工作树直接打包仍按设计拒绝；同一文件集合在隔离临时 Git 副本形成仅供验证的本地提交后，开发打包合同通过。主仓库未产生新提交。

## 3. migration 与 mypy 零失败

- 两个迁移测试的历史期望已与当前批准基线 `CB-1.5.0` 对齐，SQLite/PostgreSQL 迁移合同 27 项通过。
- 修正 replay visualization 测试端口的方法签名，使关键字 `body` 与协议一致。
- Ruff 全仓通过；mypy 对 538 个 `src/tools` 源文件零问题。
- generated-source、架构依赖、确定性代码生成和 `uv lock --check --offline` 均通过；uv 缓存定向到本地 `build/uv-cache`，没有修改依赖权威。

## 4. 正式 W7/W8/W9 证据加载器与 P13

新增 `TPAA_FORMAL_RUNTIME_EVIDENCE_ENVELOPE_V1`：

- 只接受精确字段、Ed25519 签名、配置中的固定 `key_id` 和 PEM trust root；
- payload 必须同时绑定 `candidate_identity_sha256` 和 40 位 `source_revision`；
- 签名前使用排序键、紧凑分隔符、ASCII、禁止 NaN 的 canonical JSON；
- 签名、候选、source revision、字段、类型或哈希任一异常均阻止生产运行时组合启动；
- 只有验签完成后才构造 W7 external capability、W8 operations 和 W9 final qualification 状态；
- 未配置正式证据时仍使用既有 `local_closed()` 状态，不能从本地测试结果自动升级为正式资格。

P13 现在直接加载并分区显示：Final Release Gate、External Capabilities、Operations Acceptance、Release/Publication/Provenance、Catalog/Profile、Model/Twin、Permission/Audit、Runtime。页面只有在 `decision == "GO"` 且 `formal_release_allowed is true` 时显示 GO；端点不可用、字段异常或本地关闭状态一律显示红色 `NO_GO`。

操作约束见 `docs/operator/POST_CLOSE_FORMAL_EVIDENCE_AND_GUI_ACCEPTANCE.md`。

## 5. GUI 功能、视觉与角色任务

- 产品壳新增已认证角色视图；角色来自 `/security/session`，页面默认值不替代后端授权。
- P03 增加 exact 3D 轨迹、Linked Flight Plot 和 Media/Transcript 页签。无 geodetic 数据时显示 `GEODETIC_SERIES_NOT_PRESENT`，禁止使用 current/latest 或推断轨迹填充。
- 应用启动时从系统实际字体库选择 Segoe UI/Arial/DejaVu Sans，解决离屏截图方块字；没有可读字体时失败关闭。
- 当前代码对 P01～P13 在 1440×900、96 DPI 下逐页真实渲染：13/13 页面可见、scroll viewport 可见、0 横向溢出、0 裁剪控件。
- 真实 Desktop 后端角色任务 5/5 通过：TRAINEE→P02、INSTRUCTOR→P03、EVALUATOR→P13、TRAINING_MANAGER→P11、DATA_ENGINEER→P12；SOURCE_IMPORT 对 Instructor/Data Engineer 返回 201，对其余三角色返回 403。
- 真实文件工作流完成 6 类 Source → P1 Job `SUCCEEDED` → Release `PUBLISHED` → P02 exact overview → P03 exact replay → P13 W7/W8/W9 gate。主要 GUI 交互 4 项，P13 结果为预期的 `NO_GO`。

## 6. 验证矩阵

| 门禁 | 结果 |
|---|---|
| 本波次定向测试 | `88 passed` |
| 全量 unit（分片，避免 Windows 命令时限） | `796 passed` |
| contract | 818 项均完成判定：全量运行 `816 passed / 2 failed`；随后 codegen clone 忽略 Git 已忽略的 `build/` 后专项 `7 passed`，clean-worktree 打包在隔离干净副本专项 `1 passed` |
| migration | `27 passed`，包含于定向回归 |
| golden + replay + e2e + platform | `21 passed` |
| integration | `2 passed / 3 skipped`；跳过项仍为未配置的 PostgreSQL、S3、Prometheus 外部环境 |
| Ruff | 全仓通过 |
| mypy | `538 source files`，零问题 |
| generated / architecture / codegen / lock | 全部通过 |
| 当前代码视觉渲染 | `13/13 passed`，0 overflow，0 clipped controls |
| 角色任务 | `5/5 passed` |
| 真实 GUI 工作流 | `PASS`，4 项主要交互，P13=`NO_GO` |

Windows 深目录中的 recovery/object-store 用例第一次因 `MAX_PATH` 失败；把 pytest basetemp 移到系统短临时目录后，同一 runtime 分片 `136 passed`。这不是业务断言豁免。

## 7. 本地证据

| 证据 | SHA-256 |
|---|---|
| `evidence/postclose-gui-workflow-acceptance-20261026.json` | `5e7b48d848213f5a5d18ee2466bfbf3cc5bfe6095bd43a7a1410bc0f9e0a46dd` |
| `evidence/postclose-role-task-acceptance-20261026.json` | `e287b62fcf5a820a6f3ee934c05a567d71184e47fbd51723fd7d7ff18f59117a` |
| `build/postclose-visual-20261026/w4_visual_96dpi.json` | `8eac752eb3bfb476827add2d34099512779892f0558a865e9941d807bc56a44b` |

本波次机器汇总记录为 `evidence/postclose-remediation-wave-20261026.json`。

`build/` 下保存本次离屏 PNG 和本地运行数据，受 Git 忽略，不是正式发布记录。两份 `evidence/postclose-*.json` 是本地验收清单，均明确 `pushed=false`、`production_deployed=false`。

## 8. 保留门禁与人工节点

以下事项不在本波次中伪关闭：

1. P07 Model Profile 需要服务端正式发布的多机、固定型号/Block/构型 cohort 产品，并报告 aircraft count、独立 Episode/evidence count、mean/median、dispersion、P10/P90、趋势、构型差异和异常率。当前后端只有单机 Twin/Estimate，GUI 保持 `UNAVAILABLE` 且禁止前端临时聚合。
2. 本次 3D 组件已实现，但所用 P1 验收 fixture 不包含 geodetic series，因此真实工作流按设计显示不可用；不得把示意轨迹冒充真实航迹。
3. 离屏 Qt 自动化、截图检查和角色权限任务不能替代批准显示器上的人工可读性、键盘可达性和业务角色签字。
4. 正式证据必须由独立发布机构对同一不可变候选签署；不得使用测试私钥、临时副本提交或本地截图签发生产 GO。
5. protected-main exact SHA、Hosted CI、四目标 profile installed E2E/性能/DR/升级回滚、独立安全裁决、组织签名和生产部署仍未完成。

因此，本波次可以正式关闭本地整改，但 W9 正式发布状态继续为 `NO_GO`。
