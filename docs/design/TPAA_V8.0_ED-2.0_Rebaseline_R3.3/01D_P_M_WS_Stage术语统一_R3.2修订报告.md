# R3.2 P / M / WS / Stage 术语统一修订报告

**基线：** TPAA V8.0 / ED-2.0 / CB-1.3.0  
**目的：** 消除“Phase/阶段”在能力成熟度、项目进度、工程组织和训练过程之间的歧义。

## 1. 最终受控语言

| Namespace | 唯一含义 | Codes / Authority |
|---|---|---|
| P | Capability Phase / 能力成熟度 | P1～P6 / `CAPABILITY_PHASE_REGISTRY.json` |
| M | Development Milestone / 项目里程碑 | M0～M9 / `DEVELOPMENT_MILESTONE_REGISTRY.json` |
| WS | Engineering Workstream / 工程工作流 | WS-* / `ENGINEERING_WORKSTREAM_REGISTRY.json` |
| Stage | Training Episode 内部 Stage | `STAGE_REGISTRY.json` |

`TERMINOLOGY_REGISTRY.json` 冻结四个 namespace 的互斥含义；CR-029/CR-030 把该规则提升为 Core invariant。

## 2. 主要迁移

- 原 P1～P6 能力路线保留，但统一写作 P1～P6，不再使用 `Phase 1` 等易混文本。
- 原 1A～1G 开发子阶段退出 current language。
- 旧 1C 32 项 → M2 / `P1_FOUNDATION_32` / WS-METRIC。
- 旧 1D 84 项 → M3 / `P1_REMAINDER_84` / WS-METRIC。
- 旧 1E longitudinal → M4 / WS-LONGITUDINAL。
- 旧 1F/1G → M5 的 performance/product qualification 与 release。
- 训练文档中原 `Phase/阶段` 统一改为 Stage。

## 3. M0～M9

M0 工程启动基线；M1 P1最小闭环；M2 P1 Basic；M3 P1四类训练+116指标；M4 P1长期趋势/复盘；M5 P1产品资格；M6 P2；M7 P3；M8 P4/P5；M9 P6。

**重要：M3 不等于 P3。** M 是项目进度，P 是产品能力语义。

## 4. 机器权威变化

新增 `TERMINOLOGY_REGISTRY.json`、`DEVELOPMENT_MILESTONE_REGISTRY.json`、`ENGINEERING_WORKSTREAM_REGISTRY.json`；`PHASE_LIFECYCLE.json` 被 `CAPABILITY_PHASE_REGISTRY.json` 替代；`PHASE1_METRIC_CATALOG.json` 更名/迁移为 `P1_METRIC_CATALOG.json`。

P1 Catalog 的术语迁移不改变 116 项指标公式、semantic identity、algorithm identity、input fields 或 output contract；Input Authority 的 661 binding tuples 不改变。

## 5. 文档变化

03/03A/04/05A～05J 已按语义逐项修订；05C 从 current P1 Catalog 重新生成；05G 的训练 `Phase` 全部统一为 Stage；05H 使用 P feature gate + M/WS 运维证据。历史知识报告保留旧术语时必须显式标记 legacy/historical。

## 6. 验证策略

新增术语 Gate 检查：四 namespace 完整、M0～M9 唯一、WS 引用闭合、Stage 不被用作项目进度、controlled docs 不出现旧开发 Phase/1A～1G current 用法、Catalog/DTO 使用 M 字段、legacy mapping 只能存在于受控迁移区域。
