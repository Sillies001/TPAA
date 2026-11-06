# TPAA V8.0 / ED-2.0 Rebaseline R3.3 — 116-Metric Design Intent & Applicability

本包建立在 R3.1 Knowledge-Fidelity + Cross-Platform Contract 上，新增项目级进度/层级语言治理。评价方法、116 项 P1 Metric 的公式/语义、661 个 Input Authority 绑定以及 Windows/Linux 合同不因本轮改变。

## 推荐阅读顺序

`01 → 01A → 01B → 01C → 01D → 01E → 02 → 03 → 03A → 04 → 05A → 05B → 05C → 05C1 → 05D~05J → 06 → 07 → 08`。

连续审阅可阅读 `09_ED-2.0_合订本_只读审阅版.md`；该文件只是投影，不拥有定义权。

## 关键版本

- Overall: TPAA V8.0
- Methodology: TPAA V8.0 Overall Training Effectiveness Evaluation
- Engineering: ED-2.0
- Core Baseline: **CB-1.4.0**
- Rebaseline: **R3.3_METRIC_DESIGN_GUIDE**
- DB schema target: 1.6.0
- P1 executable metrics: **116**
- Metric input bindings: **661**
- Professional volumes: **05A～05J 共 10 个**；另有 05C1 指标设计解释配套说明（非字段/算法第二权威）

## 唯一允许的进度/层级语言

- **P — Capability Phase / 能力成熟度**：P1～P6。
- **M — Development Milestone / 项目里程碑**：M0～M9。
- **WS — Engineering Workstream / 工程工作流**：`WS-*`。
- **Stage — Episode Stage / 训练过程 Stage**：只用于 Training Episode 内部。

机器权威分别为：

- `canonical/TERMINOLOGY_REGISTRY.json`
- `canonical/CAPABILITY_PHASE_REGISTRY.json`
- `canonical/DEVELOPMENT_MILESTONE_REGISTRY.json`
- `canonical/ENGINEERING_WORKSTREAM_REGISTRY.json`
- `canonical/STAGE_REGISTRY.json`

旧 1A～1G、1C/1D/1E 只保留为迁移追踪标签，不再用于当前计划、Issue、代码状态、文档章节或验收。

## 定义权原则

字段、DTO、Stage、P 能力、M 里程碑、WS 工作流、Metric、训练评价扩展与平台兼容均从 `canonical/SCHEMA_AUTHORITY_REGISTRY.json` 定位唯一 machine authority。Human documents 负责解释方法、边界、工作流和工程决策，不创建第二套 current schema。

## R3.1 跨平台权威继续有效

- `canonical/PLATFORM_COMPATIBILITY_REGISTRY.json`
- `CORE_RULES` CR-027 Platform-Neutral Business Core
- `CORE_RULES` CR-028 Cross-Platform Logical Equivalence

Windows 与 Linux 仍为 mandatory OS family；OS-specific 差异只能存在于 Platform Adapter，不允许业务算法/评价语义分叉。

## R3.2 新增术语权威

- `CORE_RULES` CR-029 Controlled Progress/Layer Vocabulary
- `CORE_RULES` CR-030 P/M/WS/Stage Orthogonality
- `canonical/TERMINOLOGY_REGISTRY.json`
- `canonical/DEVELOPMENT_MILESTONE_REGISTRY.json`
- `canonical/ENGINEERING_WORKSTREAM_REGISTRY.json`
- `canonical/CAPABILITY_PHASE_REGISTRY.json`


## R3.3 116指标设计解释与适用性

- `05C1_116指标设计意图_适用边界_区别联系与计算方法说明.md`：逐项解释 116 指标的设计原因、适用对象、计算合同镜像、区别联系、解释边界和 Golden 意图。
- `P1-SNS-*` 正式解释并机器约束为 **RADAR sensor detection/measurement**，不再作为泛化 all-sensor family。
- `P1_METRIC_CATALOG.json` v1.14.0 新增 family applicability contracts；116 metric code、semantic/algorithm identity、formula、input_fields 与 661 binding tuple 均不改变。
- `CORE_RULES` 新增 CR-031 Metric Family Applicability and Product-Layer Separation。

## 验证

```bash
python tools/validate_rebaseline.py
python tools/independent_audit.py
sha256sum -c PACKAGE_MANIFEST.sha256
```

封版还必须从最终 ZIP 解压到空目录后重复以上检查。

## 变更报告

R3 知识保真见 `01B_R39知识保真与可视化保真_R3修复报告.md`；R3.1 跨平台增强见 `01C_跨平台兼容性与逻辑一致性_R3.1增强报告.md`；R3.2 术语治理见 `01D_P_M_WS_Stage术语统一_R3.2修订报告.md`；R3.3 指标设计说明增强见 `01E_116指标设计说明_R3.3增强报告.md`。
