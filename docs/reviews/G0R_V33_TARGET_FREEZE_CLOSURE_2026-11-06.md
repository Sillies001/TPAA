# G0R v33 目标重开、资产冻结与架构复验关闭报告

- 状态：`CLOSED_LOCAL`
- 日期：2026-11-06
- 当前目标：`GUI-DEMO-V33-2026-11-05`
- 适用方案：`TPAA_HTML_Demo_v33驱动_GUI产品化重构与后端设计同步整改方案_2026-11-06.md`
- 发布结论：`NO_RELEASE_CLAIM`
- 禁止事项：未推送、未生产部署、未修改冻结前序基线

## 1. 关闭结论

G0R 的本地退出门全部通过，允许进入 G1 Machine Authority First。v33 HTML 和三份 v1.3 设计输入已经按字节哈希冻结；V01～V26 最终页面注册、P→V 符合性矩阵、v19 失效说明、版本兼容决策、WebEngine/QML 双路线样板、三主题参考截图和 V01 元素级几何证据均已落盘并由独立校验器 fail-closed 验证。

该关闭只证明“目标、语义、路线和本地证据可用于后续实现”，不等于生产资格通过。Windows/Linux 目标 profile 的 GPU/软件渲染、安装包、离线资源、SBOM、许可证、renderer 恢复、安全验收和独立发布审批仍属于 G11/G12。

## 2. 冻结输入

| 输入 | SHA-256 | 结果 |
|---|---|---|
| v33 HTML | `7aa5ff433fcaa49c3a54ac592acb43c42ee98fd944d4fb66de6e75bac2401a9a` | PASS |
| 总体设计 Patch v1.3 | `abc6b000b846dbe2e367cb5af67efe7f152ebef1a26ab0fc104918a7b37de3bb` | PASS |
| 工程设计 Patch v1.3 | `26be99db27d726bd25830281da0023202bcb7b048be1d02ac81278265666890f` | PASS |
| 差距清单 v1.3 | `402c3941c9be625b488c8e3425ed8fee7d0c3ba78f4084471e17688f231a6896` | PASS |
| R3.3 `PACKAGE_MANIFEST.sha256` | `1b70d8149975da0635b79adb1eb72e2f37743739def2ead7ade27bfb3b6db421` | PASS，清单逐文件校验 |
| CB-1.4.0 `BASELINE_LOCK` | `06fb823c8db79a19a45bb5f1da2c201644945c3967de94a312acd8f93d0ab437` | PASS |
| CB-1.5.0 `BASELINE_LOCK` | `ecdb68d0aa17ad49b2b0b3bdbad0e82559cd455725a0eb2a2a4855feba99edab` | PASS |
| CB-1.5.0 `SOURCE_PROVENANCE` | `9f771642b32a2da3d4b5f3b88ba22302fbe05f49e5284d6d85308a6485967ce8` | PASS |

v19 及其 G0 证据保留为历史参考，状态为 `SUPERSEDED_REFERENCE_ONLY`，不参与 v33 当前关闭判定。

## 3. 最终语义裁决

1. 产品视图严格为 V01～V26；HTML 标题中的 V30 是陈旧展示文字，不是版本权威。
2. V25 虽未列入 `TPAA_V33.preservedPages`，但最终路由和页面均存在，因此纳入正式注册。
3. V27 是内部补丁标签，不是产品页面。
4. 训练评估模块 landing 是 V26；V01 只允许按 exact Batch 下钻 V26。
5. V24 只允许从 V08 的合格 BVR 同目标协同攻击事件进入。
6. V04/V05/V08/V20 支持 shooter/target 双视角；V06/V21 仅 shooter；V07/V19 不引入目标视角。
7. Demo 中的合成数字、几何和曲线仅是布局样例，生产值必须来自机器权威和受控 API。
8. Demo 中 `localStorage` 业务事实方案不被采纳；G1 以后使用带版本、有效时间、权限和审计的 Context。

## 4. 双路线与视觉证据

| 门禁 | 数量/范围 | 结果 |
|---|---:|---|
| WebEngine 三主题全页面 | 26×3 = 78 | PASS |
| WebEngine V01 1280×720 | 1×3 = 3 | PASS |
| QML 合同样板 | V01/V04/V08/V26 × 3 = 12 | PASS |
| V01 元素几何 | 1600×900、1280×720；KPI 6、首排面板 2、次排 3、底排 2 | 零缺失、零重叠、零越界 |
| WebEngine profile | off-the-record | PASS |
| Demo 加载 | 单文件、本地受控合成 base URL | PASS |

本机 Windows 采集期间 Chromium 无法创建 GLES3 共享上下文并自动使用软件渲染，截图和几何门禁仍通过。该信息作为 G11 目标机 GPU/软件渲染矩阵的明确输入，不作为当前失败，也不作为硬件加速通过证据。

## 5. 架构与版本决策

- 产品壳首选 PySide6 宿主 + Qt WebEngine + 受控本地 HTTP origin；QML 是共享 API/DTO/状态合同的降级呈现层，不建立第二套业务实现。
- P01～P13 保持能力和数据语义权威；V01～V26 是产品任务视图合同。
- Overall 保持 TPAA V8.0；工程设计进入 ED-2.1；后继设计基线为 R3.4；核心候选为 CB-1.6.0。
- DB 默认保持 1.9.0；只有 G1 批准持久化 Batch/WE/Cluster/Window/Context 后才进入 1.10.0 migration/backfill/rollback。
- API v1 只允许兼容性增量；现有 route 不得重定义。
- 旧 P 壳保留为 feature-flag 诊断回退，是否移除由 G11 决定。

## 6. 自动验证结果

```text
ruff: PASS
pytest tests/contract/gui_v33 -q: 6 passed
tools/gui/g0r_v33_verify.py: PASS
tpaa_dev.py verify-baseline: PASS, 37/37
tpaa_dev.py verify-w0-successor: PASS
```

Pytest 仅出现工作区 `.pytest_cache` 无写权限警告，不影响测试结果，也没有改变门禁判定。

## 7. 关闭资产

- `docs/gui/demo-v33/DEMO_TARGET_BASELINE.json`
- `docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json`
- `docs/gui/demo-v33/G0R_VERSION_AND_COMPATIBILITY_DECISION.json`
- `docs/gui/demo-v33/WORKTREE_BASELINE_2026-11-06.json`
- `docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json`
- `docs/gui/demo-v19/SUPERSEDED.md`
- `docs/adr/ADR-GUI-001-webengine-product-shell.md`
- `docs/adr/ADR-GUI-002-p-v-view-contract.md`
- `docs/adr/ADR-GUI-003-theme-session-semantics.md`
- `evidence/gui-g0-v33/g0-runtime-spike.json`
- `evidence/gui-g0-v33/v01-1280x720/g0-runtime-spike.json`
- `evidence/gui-g0-v33/g0r-v33-closure.json`
- `tools/gui/g0_runtime_spike.py`
- `tools/gui/g0r_v33_verify.py`
- `tests/contract/gui_v33/`

## 8. G1 准入边界

G1 必须先完成 authority diff，再修改 Application/API/GUI。优先裁决 BatchWorkset/BatchMetadata、WE、Cluster、Window、Perspective、Force/Formation Context 是否属于持久对象；更新 Core Logical Model、DTO、route/permission/audit/state/reason authority；需要持久化时再批准 schema 1.10.0。任何前端页面不得先于机器权威自行定义这些业务对象。
