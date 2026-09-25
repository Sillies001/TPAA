# 飞机机载数据评估系统软件开发实施基线 SDIB-1.1

**Software Development Implementation Baseline — SDIB-1.1**  
**上位系统基线：** TPAA V8.0  
**工程设计基线：** ED-2.0  
**Core Baseline：** CB-1.4.0  
**输入设计包：** TPAA V8.0 / ED-2.0 Rebaseline R3.3  
**输入设计包 SHA-256：** `8030b988a8740fb9fc9003866b449618abc9b7048c77930b6cc22cb85fe926b9`  
**输入 Baseline Lock SHA-256：** `9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa`  
**适用开发范围：** M0/M1 为已完成的实施级历史基线；M2 P1 Basic Flight Complete 为本版新增任务级详细基线；M3～M9 保持后续 Epic/Entry-Gate 级路线基线。  
**发布日期：** 2026-09-25
**修订性质：** M1 Exit 后的 M2 任务级实施细化；不改变 R3.3 / CB-1.4.0 / Canonical 业务权威，不改变 116 项指标、661 输入绑定、Stage 或 DB schema 1.6.0。

### 0.0.1 本次修订摘要

SDIB-1.1 在保留 M0/M1 已验证实施合同的同时，执行 §24 明确要求的 post-M1 backlog refinement，把 M2 从 Epic 级冻结为可直接建立粗粒度执行批次的任务级实施基线：

1. 记录 M1 protected-main Exit GO 作为 M2 细化的进入前提，不把 M1 GO 误写成 M2 已完成；
2. 把 M2 `P1 Basic Flight Complete` 冻结为 27 个实施 Task，并给出 Primary WS、依赖、最低验收与证据要求；
3. 把 frozen Catalog 中 `delivery_milestone=M2` 且 `delivery_batch=P1_FOUNDATION_32` 的 32 项指标完整映射到 M2 Task，不更改 Metric/Stage/DTO/Core schema 业务权威；
4. 固定 SNS family 的 `RADAR` applicability 边界，禁止因 M2 扩量把 SNS 指标误用于 IRST/EO；
5. 将 27 个 Task 规划为最多四个粗粒度执行批次，并把 exact-head Hosted CI、protected-main、Windows/Linux、SQLite/PostgreSQL、Golden/replay/cold-start 设为 M2 Exit 必备证据；
6. M3～M9 仍保持路线/Entry-Gate 级，不因 M2 任务细化而提前准入。

> **文档权威边界**：SDIB-1.1 是“如何把已冻结设计实现成软件”的实施权威，不是新的业务 schema、DTO、Metric、Stage 或 P 能力定义权威。凡字段、枚举、nullability、Metric 公式、Stage code、P/M/WS 含义与本文件描述发生冲突时，必须以 CB-1.4.0 指向的 machine-readable Canonical authority 为准，并通过受控变更修订 SDIB，而不是在代码中静默偏离。

## 0. 执行摘要

R3.3 已经完成“设计体系可实施化”所需的核心前提：P/M/WS/Stage 语言统一、116 项 P1 指标与 661 个输入绑定冻结、R39 方法和可视化知识保真、Windows/Linux 跨平台合同冻结、Metric family applicability 明确。项目下一步不再以继续扩写设计文档为主，而应进入 **M0 软件工程启动 → M1 最小端到端闭环**。

SDIB-1.1 采用四条实施主线：

1. **Machine Authority First**：软件直接消费/生成自 Canonical artifacts，禁止程序员从 Markdown 重新手抄一套 schema、DTO、Metric 或 Stage。
2. **Vertical Slice Before Breadth**：先证明一条完整 Source→Release→GUI 链路，再扩大到 116 指标和四类训练。
3. **Golden Before Scale**：每个算法/状态机/Release 能力都必须有可复算的 fixture 与预期结果，再进入批量实现。
4. **Windows/Linux From First Commit**：跨平台不是 M5 才开始“移植”；M0 起即进入 PR Gate，M5 才完成正式资格化。

本文件把 M0/M1 写到可直接拆解 Issue/PR/测试证据的粒度。M2～M9 只冻结目标、依赖和进入条件，避免在没有真实代码反馈前做过度详细的远期任务计划。

## 1. 目的、适用范围与非目标

### 1.1 目的

SDIB-1.1 回答 ED-2.0 之后开发团队必须立即面对的问题：代码仓怎么建、模块如何依赖、Canonical 如何进入代码、数据库如何 bootstrap、Release/Replay 如何先于大规模指标实现、Windows/Linux CI 怎么从第一天运行、M0/M1 做到什么程度才算完成，以及 M2～M9 在什么条件下才允许进入。

### 1.2 当前详细实施范围

- **M0**：建立可构建、可测试、可启动、可追溯、可跨平台运行的软件工程底座；M0 本身不准入任何新的 P 能力声明。
- **M1**：建立一个 Basic Flight synthetic P1 最小垂直切片，完整穿过 Data、World、Metric、Observation、Release、API、GUI 与跨平台验证。

### 1.3 明确非目标

SDIB-1.1 不在 M0/M1 中完成以下事项：

- 不宣称 116 项指标全部实现；
- 不在 M1 激活 WVR/BVR/Strike 的完整产品能力；
- 不激活 P2～P6；
- 不实现真实武器性能、战术优化或现实作战建议；
- 不使用未经批准的 operational/sensitive 数据作为开发前提；
- 不把 M0/M1 的开发包冒充 M5 正式资格发布包；
- 不因实现方便改变 CB-1.4.0 的 schema/DTO/Metric/Stage 权威。

## 2. 规范性词语与权威层级

### 2.1 规范性词语

- **必须 / SHALL / MUST**：实现、合并或里程碑通过所必需；不满足即 Gate Fail。
- **应 / SHOULD**：默认实施选择；若偏离必须有 ADR 和验证证据。
- **可以 / MAY**：允许的实现自由度，不改变业务语义。

### 2.2 权威层级

实施时按以下优先级解释冲突：

1. `BASELINE_LOCK.json` 与 CB-1.4.0 Core Rules；
2. Canonical machine-readable authority（Core Logical Model、DTO、Metric Catalog、Stage、P/M/WS、Platform 等）；
3. ED-2.0 及 05A～05J/05C1 的工程与方法说明；
4. 本 SDIB-1.1 的实施组织、代码结构、Gate 与任务基线；
5. 代码内部注释、Wiki、Issue 描述。

任何下级材料都不得覆盖上级权威。若实施发现上级设计不可实现，必须发起 **Baseline Change Request**，不得在代码中“临时修正语义”。

## 3. P / M / WS / Stage 在实施中的唯一用法

| 符号 | 英文 | 中文 | 只回答的问题 | 机器权威 |
| --- | --- | --- | --- | --- |
| P | Capability Phase | 能力成熟度/能力层 | Evaluation/intelligence capability claim depth. Stable product semantics, not project progress. | CAPABILITY_PHASE_REGISTRY.json |
| M | Development Milestone | 项目里程碑 | Project delivery/acceptance checkpoints. A milestone may advance one or more P capabilities but never renames them. | DEVELOPMENT_MILESTONE_REGISTRY.json |
| WS | Engineering Workstream | 工程工作流 | Cross-cutting engineering work organization that spans milestones and capability phases. | ENGINEERING_WORKSTREAM_REGISTRY.json |
| Stage | Episode Stage | 训练过程 Stage | Versioned sub-interval/state inside a Training Episode. Stage is never a project milestone or capability maturity label. | STAGE_REGISTRY.json |

实施 Issue/PR 必须至少标识 `M + WS + Feature`，涉及训练过程时再附 Stage；涉及产品能力时附 P。例如：

- `M1 / WS-WORLD / P1 / BASIC_FLIGHT / EXECUTION / StageProjector`
- `M3 / WS-METRIC / P1 / BVR / TrackContinuity`
- `M7 / WS-CAPABILITY / P3 / TwinRevisionPublish`

**禁止**使用“开发 Phase 2”“第三阶段实现”“Stage 5 开发”等第五套进度语言。`M3 ≠ P3`，Stage 永远不表示项目进度。

## 4. M0～M9 总体开发路线

| M | 里程碑 | 目标 | P影响 | 主要WS |
| --- | --- | --- | --- | --- |
| M0 | 工程启动基线 | Create a buildable/testable Windows+Linux software substrate; no capability Phase is admitted by M0 alone. | 无 | WS-CORE, WS-STORAGE, WS-API, WS-GUI, WS-TEST, WS-PLATFORM, WS-SECURITY, WS-DEVOPS, WS-GOVERNANCE |
| M1 | P1最小端到端闭环 | Run one Basic Flight synthetic vertical slice Source→Canonical→Context→Episode/Stage→World→representative metrics→Observation→Release→API→GUI on Windows and Linux. | P1 | WS-DATA, WS-WORLD, WS-METRIC, WS-OBSERVATION, WS-STORAGE, WS-API, WS-GUI, WS-TEST, WS-PLATFORM |
| M2 | P1基本飞行完整能力 | Complete Basic Flight P1 capability plus the 32-item P1 foundation metric delivery batch and representative Golden evidence. | P1 | WS-DATA, WS-WORLD, WS-METRIC, WS-OBSERVATION, WS-GUI, WS-TEST |
| M3 | P1四类训练观测能力完整 | Complete P1 Basic/WVR/BVR/Strike observed-performance capability and all 116 executable P1 metrics; P1 formulas/semantics are production candidates. | P1 | WS-WORLD, WS-METRIC, WS-OBSERVATION, WS-API, WS-GUI, WS-TEST |
| M4 | P1长期趋势与复盘闭环 | Close P1 aircraft/mission-system longitudinal trends, evidence-first debrief/analytics and historical replay without activating P4 human assessment. | P1 | WS-LONGITUDINAL, WS-OBSERVATION, WS-GUI, WS-API, WS-TEST, WS-GOVERNANCE |
| M5 | P1产品资格与正式发布 | Qualify P1 on mandatory Windows/Linux profiles, target workload, security/governance, packaging, upgrade/rollback and release acceptance. | P1 | WS-PLATFORM, WS-PERFORMANCE, WS-SECURITY, WS-DEVOPS, WS-TEST, WS-GOVERNANCE |
| M6 | P2归因/条件调整启用 | Admit P2 Context Attribution & Normalization after identifiability, leakage, uncertainty and evidence gates are validated. | P2 | WS-CAPABILITY, WS-DATA, WS-TEST, WS-GUI, WS-GOVERNANCE |
| M7 | P3能力模型/数字孪生启用 | Admit P3 capability models, aircraft twin revisions and model profiles with applicability/knowledge-time/model validation gates. | P3 | WS-CAPABILITY, WS-LONGITUDINAL, WS-TEST, WS-GUI, WS-GOVERNANCE |
| M8 | P4/P5训练评价启用 | Admit P4 individual/human-machine and P5 team/package/mission assessment with instructor, privacy, scope separation and longitudinal evidence gates. | P4/P5 | WS-ASSESS, WS-WORLD, WS-LONGITUDINAL, WS-GUI, WS-SECURITY, WS-TEST, WS-GOVERNANCE |
| M9 | P6联合/LVC与预测闭环启用 | Admit P6 Joint/LVC and forecast/counterfactual/recommendation products with fact/projection separation, external interoperability and approval gates. | P6 | WS-INTEROP, WS-CAPABILITY, WS-ASSESS, WS-GUI, WS-SECURITY, WS-TEST, WS-GOVERNANCE |

### 4.1 规划粒度规则

- **M0/M1**：任务级、接口级、测试级详细规划；允许直接生成 Issue/PR。
- **M2**：本 SDIB-1.1 已在 M1 Exit GO 后按真实运行反馈细化为任务级 backlog；**M3～M5** 仍保持 Epic/能力包级规划，必须等待前序 Gate 后再细化。
- **M6～M9**：准入边界与验证条件级规划；在前一 P 能力未形成可靠输入前不展开完整实现 backlog。

### 4.2 Milestone 不替代 Capability Phase

M0～M5 主要是在把 P1 从工程骨架逐步形成可正式发布的软件产品；因此 M3 仍然主要实现 P1，而不是“进入 P3”。只有 M6/M7/M8/M9 才分别执行 P2/P3/P4-P5/P6 的受控准入。

## 5. 18 个 Engineering Workstream 的实施责任

| WS | 名称 | 实施责任边界 |
| --- | --- | --- |
| WS-CORE | Core Contracts & Code Generation | Core artifacts, generated types/enums, contract loading and semantic governance. |
| WS-DATA | Data / Registry / Canonical | Source registry, ingest, provenance, time, entity, canonical facts and context. |
| WS-WORLD | Episode / Stage / World / Event | Episode detection, Stage projection, C/W/P/A/J/M reconstruction, events and relations. |
| WS-METRIC | Metric Engine | P1 metric operators, 116 metrics, input authority, evidence and metric publication. |
| WS-OBSERVATION | Observation / Release / Replay | Published observations, immutable release, historical replay and provenance. |
| WS-LONGITUDINAL | Longitudinal Analytics | P1 observed trend and later capability/person/team longitudinal products. |
| WS-ASSESS | Training Assessment | P4/P5 qualification, competency, evidence, instructor review and team/mission assessment. |
| WS-CAPABILITY | Attribution / Capability Intelligence | P2 attribution/normalization and P3 capability/twin/model profile. |
| WS-STORAGE | Persistence & Migration | DB schema, migrations, repositories, object/Parquet storage and recovery. |
| WS-API | Application / API / DTO | Use cases, REST, DTOs, idempotency and service integration. |
| WS-GUI | GUI / Visualization / Debrief | PySide6, timeline, replay, evidence, assessment and analytics UI. |
| WS-TEST | Verification / Golden / Replay | Unit, contract, Golden, replay, migration, E2E and acceptance evidence. |
| WS-PLATFORM | Cross-Platform Runtime | Windows/Linux adapters, packaging, logical equivalence and runtime certification. |
| WS-SECURITY | Security & Data Governance | Identity, RBAC, audit, privacy, data handling and export governance. |
| WS-PERFORMANCE | Performance & Scalability | Workload envelope, profiling, concurrency, resource safety and qualification. |
| WS-DEVOPS | CI/CD / Build / Release | Dependency lock, SBOM, package manifest, release, upgrade/rollback and cold-start. |
| WS-INTEROP | External / LVC Interoperability | External gateways, protocol adapters, time/frame conversion and LVC integration. |
| WS-GOVERNANCE | Architecture / Change Governance | Baseline lock, traceability, plugin/model/profile publication and change closure. |

### 5.1 责任原则

每个 Feature 必须只有一个 **Primary WS**，可以有多个 Supporting WS。Primary WS 对该 Feature 的接口、测试证据和 DoD 完整性负责；Supporting WS 不通过复制逻辑来“帮忙”。例如 Metric 的 Event 输入缺失时，应由 WS-WORLD 提供权威 Event，而不是 WS-METRIC 自己再推导一次。

## 6. 软件实现总原则

### 6.1 单一事实源进入代码

Canonical artifacts 必须作为受控输入进入软件仓库；运行时和 CI 都校验 Core Baseline、artifact version/hash 与代码生成清单。Markdown 中出现的字段名只用于解释，不作为生成源。

### 6.2 业务核心 OS-neutral

Domain、Context、World、Stage/Event、Metric、Observation、Release、Longitudinal、Assessment、Capability 与 Application Service 不允许根据 OS 改变业务行为。平台差异只能进入 Platform Adapter。

### 6.3 计算与发布分离

所有计算先进入 job-scoped staging；只有通过 schema/hash/ref/quality 校验的结果才能由 Release Service 原子/事务性发布。Worker 不直接发布 current product。

### 6.4 历史解释优先于“最新值便利”

历史 Release 只按自己的 Context/Catalog/Profile/Definition/World/Evidence refs 解释。任何缺失均 fail-closed；不允许 fallback 到 current/latest。

### 6.5 缺失不是零，失败不是业务不足

N_A、INSUFFICIENT_DATA、INVALID、REVIEW_REQUIRED 与系统异常必须分离。API/GUI 不把业务不足伪装成 0，也不把正常的 insufficient 误报为 5xx。

### 6.6 P2～P6 默认 dormant

允许预留接口/namespace/feature gate，但未通过对应 M6～M9 Admission Gate 的功能不得在 UI/API 中冒充“已可用”。

## 7. 软件仓库与模块结构基线

SDIB-1.1 采用**单一主仓（monorepo）+ 清晰包边界**作为 M0 默认实现。原因是当前 Core/DTO/Metric/Stage/GUI/Windows-Linux 合同耦合较强，早期拆成多仓会增加版本同步与 contract drift 风险。未来如需拆仓，必须通过 ADR 与 contract package/versioning 证明不会破坏原子基线。

建议目录：

```text
tpaa/
├─ pyproject.toml
├─ dependency.lock                  # 具体工具由 M0 ADR 冻结
├─ README.md
├─ baseline/
│  └─ CB-1.4.0/
│     ├─ BASELINE_LOCK.json
│     └─ canonical/*.json           # 经批准的只读快照
├─ src/
│  ├─ tpaa_generated/               # 机器生成；不得手改
│  ├─ tpaa_registry/
│  ├─ tpaa_ingest/
│  ├─ tpaa_canonical/
│  ├─ tpaa_context/
│  ├─ tpaa_episode/
│  ├─ tpaa_world/
│  ├─ tpaa_metric/
│  ├─ tpaa_observation/
│  ├─ tpaa_longitudinal/
│  ├─ tpaa_assessment/
│  ├─ tpaa_storage/
│  ├─ tpaa_application/
│  ├─ tpaa_api/
│  ├─ tpaa_gui/
│  ├─ tpaa_audit/
│  └─ tpaa_platform/                # OS adapter only
├─ migrations/
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ golden/
│  ├─ replay/
│  ├─ migration/
│  ├─ e2e/
│  ├─ platform/
│  └─ performance/
├─ fixtures/
│  ├─ synthetic/
│  └─ golden/
├─ tools/
│  ├─ baseline/
│  ├─ codegen/
│  ├─ manifest/
│  └─ dev/
├─ packaging/
│  ├─ windows/
│  └─ linux/
└─ docs/
   ├─ adr/
   ├─ generated/
   └─ developer/
```

### 7.1 模块依赖方向

```text
GUI / REST Transport
        ↓
Application Service
        ↓
Assessment / Longitudinal / Observation
        ↓
Metric
        ↓
World / Event / Stage
        ↓
Context / Canonical / Time / Entity
        ↓
Registry / Repository / Source
```

Repository 实现可被上层通过 Port 使用，但数据库方言、路径、线程/进程等物理细节不得渗入 Domain。任何反向依赖都必须由 architecture test 拦截。

## 8. Baseline Snapshot 与 Code Generation

### 8.1 Baseline Snapshot

软件仓库必须携带经批准的 Canonical 快照和 `BASELINE_LOCK.json`。M0 建立 `baseline verify` 命令：启动、测试、打包均先验证 hash；发现字节漂移即失败。

### 8.2 生成输入

至少消费：

- `CORE_LOGICAL_MODEL.json`
- `CROSS_LAYER_DTO_CONTRACTS.json`
- `P1_METRIC_CATALOG.json`
- `METRIC_INPUT_AUTHORITY_MATRIX.json`
- `STAGE_REGISTRY.json`
- `CAPABILITY_PHASE_REGISTRY.json`
- `DEVELOPMENT_MILESTONE_REGISTRY.json`
- `ENGINEERING_WORKSTREAM_REGISTRY.json`
- `PLATFORM_COMPATIBILITY_REGISTRY.json`
- `TRAINING_EVALUATION_TAXONOMY.json`

### 8.3 生成输出

M0 至少生成/校验：

- Pydantic DTO/types 与 required/nullability/transport 类型；
- 受控 enum/code constants；
- Stage profile 元数据；
- P1 Metric registry metadata 与 value-kind/schema binding；
- P/M/WS 常量与合法性校验；
- OpenAPI 可复用 schema fragment；
- Baseline metadata/build manifest input。

### 8.4 生成规则

生成文件必须带 source artifact/version/hash 与 generator version header；禁止人工编辑。CI 运行“重新生成→git diff 必须为空”。如生成结果变化，PR 必须同时包含其 Canonical 源变更和 Baseline Change evidence。

## 9. Toolchain 与 M0 ADR 决策清单

设计基线没有必要把所有工程工具品牌写死。SDIB 要求 M0 用 ADR 冻结以下选择，并在 Windows/Linux 使用同一逻辑工具链：

| ADR | 主题 | 必须冻结的结论 |
| --- | --- | --- |
| ADR-M0-001 | Python runtime baseline | 冻结一个明确的 Python minor version、支持期与 Windows/Linux 构建矩阵；不得两端使用不同 minor 作为常态。 |
| ADR-M0-002 | Dependency resolver/lock | 选择唯一依赖解析与 lock 方式；lock 是发布输入，不能只依赖“latest”。 |
| ADR-M0-003 | Static quality tools | 冻结 formatter/linter/type-checker/test runner；CI 与本地命令一致。 |
| ADR-M0-004 | Repository DB access implementation | 冻结 SQLite/PostgreSQL repository 技术实现；Domain contract 不得依赖具体驱动。 |
| ADR-M0-005 | Desktop backend lifecycle/IPC | 冻结 PySide6 与 local FastAPI backend 的启动、handshake、shutdown、token 与端口策略。 |
| ADR-M0-006 | Packaging | 冻结 Windows Desktop/Service 与 Linux Desktop/Service 的开发包格式；M5 再完成正式资格。 |
| ADR-M0-007 | Generated-source policy | 默认提交生成产物并由 CI regenerate-diff；若选择 build-only 生成必须证明离线重现和审查性。 |
| ADR-M0-008 | Logging/telemetry library | 冻结 structured logging/metrics 接口；业务时间和日志时间严格分离。 |
| ADR-M0-009 | Local object/Parquet layout | 冻结开发环境 object/Parquet 根目录和 logical URI mapping，绝对路径不进入 logical hash。 |
| ADR-M0-010 | SBOM/license tooling | 冻结生成 SBOM、第三方依赖清单和许可证清单的工具与输出格式。 |

## 10. Persistence、Migration 与 Repository 实施基线

### 10.1 Schema target

当前 DB schema target 继续是 **1.6.0**。R3.3 文档升级本身不构成新的 DB migration 理由；M0 应实现对当前 schema 的 clean bootstrap 与验证，而不是伪造“1.6.0→新版本”的迁移。

### 10.2 Desktop 与 Service

- Desktop：SQLite WAL + local Parquet/object files；权威 DB 由 local backend 单写。
- Service：PostgreSQL + Parquet/object storage；可并发 Worker，但 Release publish 仍经 Release Service/CAS。
- 两者共享 Repository contract；不得在 Domain 中出现“if sqlite / if postgres”业务分支。

### 10.3 Migration harness

M0 必须建立 migration harness，即使当前只需要 bootstrap 1.6.0：

1. clean bootstrap；
2. schema version/readiness check；
3. seed/hash parity；
4. typed value round-trip；
5. rollback/forward-recovery harness；
6. historical fixture hook；
7. SQLite/PostgreSQL repository conformance test。

真正发生 Core Logical Model 字段变化时，才新增 schema version 和 migration rehearsal。

## 11. Job、Staging、Release 与 Replay

### 11.1 Job 语义

Import、Canonicalize、WorldBuild、MetricCompute、Publish、Replay 等计算命令都必须形成 canonical request hash，并支持 Idempotency-Key。相同 key+相同请求复用同一逻辑工作；同 key+不同请求冲突。

### 11.2 Staging

Worker 只写 job-scoped staging。staging 不是正式产品，不被 GUI/current pointer 当作权威结果展示。Cancel/crash 后可以清理 staging，但不能影响已发布 Release。

### 11.3 Publish

Publish 顺序必须为：

```text
compute staging
→ validate schema / refs / logical hash
→ seal payload
→ DB transaction register product + Release
→ CAS current pointer
```

### 11.4 Replay

Replay 必须显式绑定原 Release 的 Context、Catalog/Metric Definition、World/Stage、artifact refs 和 input hashes。缺失历史依赖时返回明确 fail-closed 状态，不允许用 current 配置补齐。

## 12. Application/API 实施基线

Application Service 是 GUI/REST 的唯一业务入口；GUI 不直接查 DB，Controller 不重新实现 Domain 规则。

### M0 API/Use-case 最小集合

- runtime/baseline readiness 与 version handshake；
- health/diagnostic；
- baseline/canonical validation；
- DB readiness/bootstrap status；
- job submission/query/cancel skeleton；
- audit/log diagnostic export skeleton。

### M1 API/Use-case 最小集合

- synthetic source import；
- Session / Context / Episode / Stage query；
- World build status；
- Metric compute；
- Observation/Release publish/read；
- Metric list/detail/evidence query；
- historical Release read/replay；
- series/timeline range query。

具体 HTTP path 和 DTO 字段不在本文件另立第二权威；M0/M1 通过 `CROSS_LAYER_DTO_CONTRACTS.json` 生成/冻结 OpenAPI snapshot，并对 required/nullability、decimal-string Session Time、structured result object 做 exact contract test。

## 13. Desktop GUI 实施基线

### 13.1 M0 GUI

M0 只建立可测试壳层：

- Application shell；
- local backend handshake；
- Core/DB readiness 状态；
- version mismatch fail-closed；
- Diagnostics/About（显示 Core/Catalog/schema/build）；
- 可自动化启动/退出 smoke。

### 13.2 M1 GUI

M1 必须真正消费 Application DTO，并至少提供：

1. Session Browser；
2. Mission/Context Header；
3. Master Timeline；
4. Basic Flight Episode + Stage lane；
5. Metric List；
6. Metric Detail；
7. Evidence/Data Quality panel；
8. Release/Replay identity display。

M1 不要求实现 05G 的全部 P01～P13 页面，但所有 M1 控件必须沿用 05G 的“Evidence-first、Timeline 主控制器、N/A/Unknown/Failure 分离”原则。

## 14. Verification 体系：先有可证明的正确性，再有规模

### 14.1 测试金字塔

- **Unit**：operator、resolver、mapper、hash、small state machine；
- **Contract**：Canonical/DTO/Registry/Metric/Stage exact parity；
- **Golden**：手算/合成 Episode、Stage、Metric、Release 预期值；
- **Replay**：已发布 Release 按 frozen provenance 重放；
- **Migration**：bootstrap、hop、rollback/forward recovery；
- **E2E**：Source→Release→GUI drill-down；
- **Platform**：Windows/Linux logical equivalence；
- **Performance**：先测量、后优化；M5 才做正式资格。

### 14.2 Fixture 原则

每个 fixture 都必须有：fixture_id/version、输入 hash、Context/Stage/Profile refs、expected logical products、numeric tolerance、known invalid/insufficient cases。Golden expected 结果不得由被测实现自身生成后直接“批准”。

### 14.3 数值一致性

离散 identity、Stage/Event、status/reason code、Release membership 要 exact parity；数值使用 Metric/operator 自己的 Golden tolerance。不得为 Windows 和 Linux 设置不同阈值。

## 15. Windows/Linux CI/CD 基线

### 15.1 每个 PR 的最低流水线

```text
baseline verify
→ generated-code diff check
→ lint/type/static architecture checks
→ unit
→ contract
→ Windows Golden subset
→ Linux Golden subset
→ cross-platform logical-equivalence diff
→ migration/bootstrap smoke
→ API/GUI smoke（达到相应 M 后启用）
```

### 15.2 M0 之后的开发制品

M0～M4 可以形成 development/pre-release artifacts，用于团队验证，但必须显式标记非 M5 正式资格包。每个平台制品都记录 build version、Core/Catalog/schema、dependency lock、native dependency manifest、SBOM 与 package hash。

### 15.3 Release Fail-Closed

任一 mandatory certification profile 的受控 Gate 失败即阻止对应 Release。不得以“先发 Linux，Windows 后补”或反向方式绕过已声明的跨平台产品基线。

# Part II — M0 Engineering Bootstrap 实施规格

## 16. M0 目标、入口与退出定义

### 16.1 M0 单一目标

建立一个**真正可持续开发的软件工程底座**：同一源码在 Windows/Linux 可 clean checkout、验证 baseline、安装依赖、bootstrap DB、运行单元/合同测试、启动 API 和 Desktop shell，并生成可追溯 build artifact。

### 16.2 M0 Entry Gate

- R3.3 设计包完整可用；
- CB-1.4.0 与 Baseline Lock 可验证；
- 65/65 Core Validator 与 24/24 Independent Audit 为当前设计输入证据；
- 开发环境只使用 synthetic/public development data，除非另有批准的数据策略。

### 16.3 M0 Exit 不是 P1 能力验收

M0 结束时软件可以“构建、启动、校验、存储、排队、审计”，但仍可能没有真正的训练评价结果。M0 不得被表述为“P1 已完成”。

## 17. M0 工作包 Backlog

以下任务 ID 是 SDIB-1.1 的初始实施 backlog，共 **48 个 M0 工作包**。可以在项目管理工具中拆成更小 Task，但不得改变其验收语义；拆分项仍必须回指原 ID。

Task ID 表示“必须交付什么”，不表示唯一串行施工顺序。实际启动顺序见 §17.1；ADR ID 管理技术决策，Milestone Gate 管理 M0→M1 转换，三类编号不得混用。

| Task ID | WS | 交付物 | 最低验收 |
| --- | --- | --- | --- |
| M0-CORE-001 | WS-CORE | 导入并锁定 CB-1.4.0 baseline snapshot | baseline verify 对所有 controlled artifacts hash exact PASS |
| M0-CORE-002 | WS-CORE | 实现 Canonical artifact loader | 版本、schema、hash 错误全部 fail-closed；错误含 artifact id/version |
| M0-CORE-003 | WS-CORE | 建立 code generator framework | DTO/enum/Stage/P-M-WS/Metric registry 可重复生成 |
| M0-CORE-004 | WS-CORE | 生成代码只读治理 | 生成文件带 source hash；人工修改由 CI regenerate-diff 拦截 |
| M0-CORE-005 | WS-CORE | architecture dependency test | 禁止下层依赖 GUI/API；禁止业务核心直接依赖 tpaa_platform implementation |
| M0-CORE-006 | WS-CORE | 实现 runtime baseline handshake model | Core/Catalog/schema/build mismatch 不进入 READY |
| M0-STO-001 | WS-STORAGE | 建立 1.6.0 clean bootstrap | 空 DB 可初始化并通过 schema/hash 校验 |
| M0-STO-002 | WS-STORAGE | SQLite Desktop repository skeleton | WAL、单写者、事务 smoke PASS |
| M0-STO-003 | WS-STORAGE | PostgreSQL Service repository skeleton | 同一 repository contract conformance PASS |
| M0-STO-004 | WS-STORAGE | Parquet/object abstraction skeleton | logical URI 与绝对路径分离 |
| M0-STO-005 | WS-STORAGE | migration harness | bootstrap/rollback/forward-recovery 测试入口存在 |
| M0-STO-006 | WS-STORAGE | hash primitives | request/logical/artifact byte hash 分离并有 unit tests |
| M0-STO-007 | WS-STORAGE | backup/restore smoke skeleton | 开发 fixture 可备份恢复并校验 refs/hash |
| M0-API-001 | WS-API | Application Service skeleton | GUI/REST 均只能通过 Application use case |
| M0-API-002 | WS-API | FastAPI local/service skeleton | health/readiness/version endpoints smoke PASS |
| M0-API-003 | WS-API | DTO generation/OpenAPI snapshot | Critical DTO exact parity contract PASS |
| M0-API-004 | WS-API | Idempotency middleware/service skeleton | same key/same request 与 conflict 行为测试 |
| M0-API-005 | WS-API | 统一 error/business-status mapping | N_A/INSUFFICIENT 与系统异常分离 |
| M0-GUI-001 | WS-GUI | PySide6 application shell | Windows/Linux 启动退出 smoke PASS |
| M0-GUI-002 | WS-GUI | Local backend lifecycle handshake | backend crash/mismatch 不进入 READY；退出清理完成 |
| M0-GUI-003 | WS-GUI | Baseline/Diagnostics view | 可显示 Core/Catalog/schema/build 与 readiness |
| M0-GUI-004 | WS-GUI | UI automation smoke harness | 至少启动、ready、close 可自动验证 |
| M0-TST-001 | WS-TEST | 建立 unit/contract/golden/replay/migration/e2e 目录和 runner | 本地/CI 命令一致 |
| M0-TST-002 | WS-TEST | Canonical contract tests | Core/DTO/Metric/Stage/P-M-WS registries 可验证 |
| M0-TST-003 | WS-TEST | typed value round-trip tests | NUMERIC/TEXT/BOOLEAN/STRUCTURED transport skeleton PASS |
| M0-TST-004 | WS-TEST | Session Time decimal-string contract | JS-visible time 不经过 float |
| M0-TST-005 | WS-TEST | failure fixture harness | missing/corrupt/version mismatch 能得到确定错误 |
| M0-TST-006 | WS-TEST | test evidence output | CI 产出机器可归档的结果摘要和环境信息 |
| M0-PLAT-001 | WS-PLATFORM | path/filesystem adapter | 无硬编码 separator/drive/tmp；Unicode/case tests PASS |
| M0-PLAT-002 | WS-PLATFORM | spawn-compatible worker skeleton | job payload 可序列化；无 fork-only state |
| M0-PLAT-003 | WS-PLATFORM | temp/lock/atomic replace adapter | Windows/Linux contract tests PASS |
| M0-PLAT-004 | WS-PLATFORM | Windows CI runner | unit/contract/bootstrap/API/GUI smoke |
| M0-PLAT-005 | WS-PLATFORM | Linux CI runner | 与 Windows 同一逻辑测试集 |
| M0-SEC-001 | WS-SECURITY | Desktop loopback/token/CORS/path allowlist skeleton | 缺安全配置 fail-closed |
| M0-SEC-002 | WS-SECURITY | audit event framework | 关键命令至少记录 actor/request/reason/version/hash 框架 |
| M0-SEC-003 | WS-SECURITY | development data guard | 未批准 operational/sensitive 数据有明确阻断/警告策略 |
| M0-SEC-004 | WS-SECURITY | secret/config separation | 密钥不进入 repo/log/build manifest |
| M0-DEV-000 | WS-DEVOPS | Formal Repository Bootstrap | 正式 Git 仓建立；受保护 `main`；基础目录/README/.gitignore/.gitattributes/.editorconfig/CI placeholder 存在；首个仓库 bootstrap MR 在 Windows/Linux 最小检查 PASS |
| M0-DEV-001 | WS-DEVOPS | 统一 developer commands | bootstrap/generate/test/run/package 命令可发现 |
| M0-DEV-002 | WS-DEVOPS | dependency lock | Windows/Linux 使用同一逻辑 lock |
| M0-DEV-003 | WS-DEVOPS | build manifest | 记录 source revision、baseline hashes、dependency lock、platform profile |
| M0-DEV-004 | WS-DEVOPS | SBOM/license report skeleton | 每个平台开发包可生成 |
| M0-DEV-005 | WS-DEVOPS | development package skeleton | Windows/Linux 可 clean install/start/stop |
| M0-DEV-006 | WS-DEVOPS | cold-start job | 从 clean workspace 重建并运行 M0 gates |
| M0-GOV-001 | WS-GOVERNANCE | ADR repository | ADR-M0-001～010 有状态、owner role、decision/evidence |
| M0-GOV-002 | WS-GOVERNANCE | Issue/PR templates | 强制 M/WS/P/Stage(如适用)、authority、tests、change class |
| M0-GOV-003 | WS-GOVERNANCE | Baseline Change workflow | Canonical change 与代码 change 分离并可追踪 |
| M0-GOV-004 | WS-GOVERNANCE | Definition of Done policy | PR/Feature/Milestone DoD 进入仓库治理文档 |

### 17.1 M0 启动顺序与 Task ID 映射

M0 的启动顺序是**依赖顺序**，不是 48 个 Task 的线性编号顺序。一个启动步骤通常拉起多个 Task，同一 Task 也可能跨多个施工波次持续收敛。

| 启动顺序 | 实际动作 | 主 Task ID | 同步/后续 Task | 完成标志 |
| --- | --- | --- | --- | --- |
| 1 | 建立正式软件仓库与受控 `main` | `M0-DEV-000` | `M0-GOV-002`, `M0-GOV-004`, `M0-DEV-001` | clone/branch/MR/CI 最小闭环可用 |
| 2 | 导入 R3.3/CB-1.4.0 baseline snapshot 并验证 hash | `M0-CORE-001` | `M0-TST-002` | baseline verify exact PASS |
| 3 | 建立 `pyproject + dependency lock + developer command` 骨架 | `M0-DEV-001`, `M0-DEV-002` | `M0-GOV-001` | Windows/Linux 可执行同一高层开发命令 |
| 4 | 关闭 ADR-M0-001～003，冻结 runtime/dependency/static toolchain | `M0-GOV-001` | `M0-DEV-001`, `M0-DEV-002` | 三项 ADR 均 CLOSED，CI 使用已冻结工具链 |
| 5 | 实现 Canonical loader + codegen | `M0-CORE-002`, `003`, `004` | `M0-TST-002`, `M0-CORE-005` | regenerate-diff=0，contract tests PASS |
| 6 | 建 1.6.0 DB bootstrap + Repository skeleton | `M0-STO-001`～`005` | `M0-STO-006`, `007` | SQLite/PostgreSQL bootstrap/conformance 基础 PASS |
| 7 | 建 Application/FastAPI/PySide6 shell + version handshake | `M0-API-001`～`003`, `M0-GUI-001`～`003`, `M0-CORE-006` | `M0-API-004/005`, `M0-GUI-004` | READY/NOT_READY、启动、握手、退出可自动验证 |
| 8 | 接通 Windows/Linux CI | `M0-PLAT-004`, `005` | `M0-TST-006`, `M0-DEV-003` | 两平台执行同一逻辑 Gate 集 |
| 9 | 建完整 test/fixture harness | `M0-TST-001`～`005` | `M0-PLAT-001`～`003`, `M0-SEC-001`～`004` | unit/contract/golden/replay/migration/e2e 入口可执行 |
| 10 | 完成其余 M0 backlog、package/SBOM/cold-start | 剩余全部 M0 Task | `M0-DEV-003`～`006`, `M0-GOV-003/004` | 48/48 工作包达到各自最低验收 |
| 11 | M0 Exit Review | Milestone Gate（不是普通 Task） | §18 + 附录 K 证据包 | 14项 M0 Exit 条件全部 PASS |
| 12 | 冻结 `M0_IMPLEMENTATION_BASELINE` 并允许 M1 | Milestone Transition Gate | build manifest/tag/evidence | M1 Entry Gate 才可开启 |

### 17.2 M0 六个施工波次

为便于 GitLab/Gitea 看板管理，48 个工作包建议组织为六个施工波次。波次是项目管理视图，不是新的 M/WS/P/Stage 编号体系。

| 波次 | 目的 | 典型 Task | 允许并行的边界 |
| --- | --- | --- | --- |
| M0-A 仓库与治理 | 让团队能安全协作 | `M0-DEV-000`, `DEV-001/002`, `GOV-001`～`004` | 仓库建成后即可与 Baseline 导入并行 |
| M0-B Baseline/Codegen | 让代码直接消费机器权威 | `CORE-001`～`005`, `TST-002` | Loader 稳定后可并行 DTO/enum/registry 生成 |
| M0-C Persistence | 建存储、迁移、hash 地基 | `STO-001`～`007` | SQLite/PostgreSQL skeleton 可并行，但共享 Repository contract |
| M0-D Runtime Shell | 建 Application/API/Desktop/Worker/Platform/Security 壳 | `CORE-006`, `API-*`, `GUI-*`, `PLAT-001`～`003`, `SEC-*` | API/GUI 可并行，但必须共享 handshake/readiness |
| M0-E Automated Verification | 建双平台自动质检 | `TST-*`, `PLAT-004/005`, `DEV-003`～`005` | Windows/Linux 并行执行同一逻辑测试集 |
| M0-F Closure | Cold-start 与 Exit | `DEV-006` + 剩余未闭合项 | 不得以“后续补证据”跨过 Exit Gate |

依赖不能倒置：例如 codegen 不能在 Baseline 未锁定时把 Markdown 当输入；GUI READY 不能在 handshake 未定义时自行猜版本；CI 不得等 M0 最后才接入。

## 18. M0 Exit Gate

M0 只有在以下条件**全部**满足时才通过：

1. Baseline snapshot/hash 验证自动化；
2. Canonical code generation 可重复，regenerate diff=0；
3. 1.6.0 clean DB bootstrap 在 SQLite/PostgreSQL 均通过；
4. Application/API shell 可启动，Core/schema mismatch fail-closed；
5. PySide6 Desktop 在 Windows/Linux 可启动、握手、退出；
6. Worker 使用 spawn-compatible serialization；
7. Windows/Linux unit+contract 同时通过；
8. path/case/Unicode/temp/lock/atomic-replace 基础测试通过；
9. request/logical/artifact hash primitives 有测试；
10. audit/logging/security minimum controls 已存在；
11. dependency lock/build manifest/SBOM skeleton 可生成；
12. development package 可 clean install/start/stop；
13. 10 项 M0 ADR 全部 CLOSED 或有明确阻断理由，未决阻断项不得带入 M1；
14. cold-start 从空工作区重现所有上述结果。

M0 通过后发布 `M0_IMPLEMENTATION_BASELINE` 标签/manifest；该标签是工程基线证据，不是 P1 capability release。

# Part III — M1 P1 Minimum Vertical Slice 实施规格

## 19. M1 目标与切片边界

M1 只做一件事：证明 **Basic Flight 的一条 P1 链路是真实端到端闭合的**。

```text
Synthetic Source Bundle
→ Source Registry / Ingest
→ Canonical Facts
→ Time / Entity / Evaluation Context
→ Basic Flight Episode
→ BASIC_FLIGHT_V1 Stage
→ World product
→ 5 representative P1 AIR metrics
→ Observation
→ Immutable SESSION Release
→ Application/API
→ Timeline / Metric Detail / Evidence GUI
→ Historical read / Replay
```

为了降低第一条闭环的变量数量，M1 **不引入 RADAR/IRST/ESM/DL/FUS**。传感器系统和对应 family 在后续 M2/M3 展开。M1 的目的不是展示业务覆盖广度，而是证明架构、版本、证据与发布链路正确。

### 19.1 M1 Entry Gate

M1 不是在“代码仓能启动”后自动开始。以下条件必须全部满足并形成可追溯证据：

1. §18 M0 Exit Gate 全部 PASS；
2. 已发布并可校验 `M0_IMPLEMENTATION_BASELINE` tag/manifest；
3. M0 的 48 个工作包均 CLOSED，或经 M0 Review 明确批准为不阻断且不影响 M1 的例外；
4. ADR-M0-001～010 全部 CLOSED；
5. Windows/Linux CI 均为 GREEN，baseline verify、codegen diff、DB bootstrap、API/Desktop smoke 可重复；
6. 当前 M1 使用的 source revision、CB-1.4.0、Baseline Lock、DB schema 1.6.0、P1 Metric Catalog、Stage/DTO authority 与 dependency lock 已冻结到 M1 build manifest；
7. Synthetic/Golden 开发数据策略有效，不依赖未经批准的 operational/sensitive 数据；
8. M1 的 Primary WS owner、Golden 独立审查者、M1 Exit reviewer 已指派；
9. 无已知 architecture-level blocker 会迫使 M1 绕过 Context/Stage/World/Release/API/GUI 任一层；
10. M1 Backlog 已导入项目管理系统，并保留本节 Task ID 作为父级追踪锚点。

任一条件失败时，状态为 `M1_NOT_ADMITTED`；不得通过在 Feature Branch 中“先做一点 M1”来绕过 Milestone Transition Gate。

### 19.2 M1 启动清单（从 M0 PASS 后的实际顺序）

1. 确认 `M0_IMPLEMENTATION_BASELINE` 与 M1 Entry Gate 全部 PASS；
2. 冻结 M1 source revision / Core / Catalog / schema / dependency lock / platform profiles；
3. 创建 M1 Milestone、WS owner、56 个父级 Backlog Issue 与 Exit Review checklist；
4. 建立 8 类 Fixture 的 manifest/version/expected/tolerance 生命周期规则；
5. 先完成 `BF_M1_NOMINAL_V1` 的最小可用输入和人工可复算 expected skeleton；
6. 打通 Synthetic Source Adapter → Source Registry；
7. 打通 Session Time → Aircraft Entity → Canonical channels → Evaluation Context → lineage/quality；
8. 实现 Basic Flight Episode；
9. 实现 `BASIC_FLIGHT_V1` 四个 Stage，并先冻结 Stage Golden；
10. 构建最小 P1 World product、logical hash 与 Evidence refs；
11. 建立 MetricContext builder 和 Metric compute staging；
12. **只先实现 `P1-AIR-001`**，形成第一项 Metric unit + Golden；
13. 接 P1 Aircraft Observation → SESSION Release → publish CAS/idempotency；
14. 接最小 API：Session/Context/Episode/Stage/Metric/Release 查询；
15. 接最小 GUI：Session Browser → Header → Timeline/Stage → Metric List/Detail/Evidence；
16. 至此形成第一条最窄 E2E：`BF_M1_NOMINAL_V1 → AIR-001 → Release → GUI`；
17. 再实现 AIR-002 / AIR-003 / AIR-004 / AIR-007，并完成相应 unit + Golden；
18. 完成 GAP / ANGLE_WRAP / STRUCTURED_PARTIAL / STAGE_BOUNDARY 等剩余功能性 Fixture；
19. 完成 Release immutability / idempotency race / historical read / replay / failure 闭合；
20. 完成 SQLite/PostgreSQL parity、Windows/Linux Desktop E2E 与 Service smoke；
21. 生成 cross-platform logical-equivalence report；
22. 从 clean workspace 执行 M1 cold-start；
23. 执行 §24 M1 Exit Review；只有 GO 后才允许进入 M2 backlog 细化。

这 23 步定义 M1 的主施工依赖，不意味着每一步只能单线程执行；支持 WS 可以并行，但不得跳过上游权威产品。例如 Metric 不得在 Stage Golden 未稳定前自行重建 Stage，GUI 不得在 API/DTO 未闭合前直连 DB。

### 19.3 M1 启动顺序与 Task ID 映射

| 施工波次 | 目标 | 主要 Task ID | 必须先得到的产品/证据 | 波次完成标志 |
| --- | --- | --- | --- | --- |
| M1-A Transition & Fixture Contract | 把 M0 工程底座冻结成 M1 可执行起点 | `M1-TST-001`（先建规则/manifest），项目管理中的 M1 Gate checklist | `M0_IMPLEMENTATION_BASELINE` | M1 Entry PASS；fixture schema/lifecycle 可用 |
| M1-B Data Spine | 从 Synthetic Source 得到可追溯 Canonical/Context | `M1-DATA-001`～`007` | baseline/codegen/repository READY | Source→Canonical→Context exact trace 可验证 |
| M1-C Episode / Stage / World | 产生稳定的训练窗口和最小 World | `M1-WORLD-001`～`007`, `M1-TST-003` | Canonical/Context | 四 Stage Golden PASS；World hash/evidence 稳定 |
| M1-D First Metric | 先证明一项 Metric 能消费正式上游产品 | `M1-MET-001`, `002`, `007`, `008`, `M1-TST-002` 的 AIR-001 子集 | Stage/World Golden | AIR-001 unit+Golden PASS，结果只在 staging |
| M1-E First Published E2E | 把 AIR-001 从 staging 送到 Release/API/GUI | `M1-OBS-001`～`003`, `M1-STO-001/002`, `M1-API-001`～`003`, `M1-GUI-001`～`006` | AIR-001 valid staging | `BF_M1_NOMINAL_V1 → AIR-001 → Release → GUI/Evidence` 闭合 |
| M1-F Representative Metric Breadth | 扩到五个代表 Metric 和主要边界 Fixture | `M1-MET-003`～`006`, `M1-GUI-007`, `M1-TST-001/002` | 第一条 E2E 稳定 | 5项 Metric + 主要边界 Golden PASS |
| M1-G Replay / Failure / Platform | 证明发布不可变、历史可重放、双平台等价 | `M1-OBS-004/005`, `M1-STO-003`, `M1-API-004/005`, `M1-TST-004`～`009`, `M1-PLAT-001`～`004` | 5项 Metric/Release | Replay/failure/parity/cross-platform 全 PASS |
| M1-H Cold-start & Exit | 从空环境重建全部 M1 证据 | `M1-TST-010` + 所有未闭合 M1 Task | 前七个波次 | §24 全部 Exit Gate PASS |

### 19.4 M1 第一条最窄 E2E Critical Path

为了防止团队一开始把 56 个 Task 平铺并行，M1 必须优先闭合以下关键路径：

```text
M1-TST-001 (BF_M1_NOMINAL_V1 contract)
→ M1-DATA-001 → M1-DATA-002 → M1-DATA-003 → M1-DATA-004 → M1-DATA-005 → M1-DATA-006 → M1-DATA-007
→ M1-WORLD-001 → M1-WORLD-002 → M1-WORLD-003 → M1-WORLD-004 → M1-WORLD-006 → M1-WORLD-007
→ M1-TST-003 (Stage Golden)
→ M1-MET-001
→ M1-MET-002 (AIR-001)
→ M1-MET-008
→ M1-OBS-001 → M1-OBS-002 → M1-OBS-003
→ M1-STO-001 → M1-STO-002
→ M1-API-001 → M1-API-002 → M1-API-003
→ M1-GUI-001 → M1-GUI-002 → M1-GUI-003 → M1-GUI-004 → M1-GUI-005 → M1-GUI-006
→ M1-TST-008 (first GUI E2E subset)
```

这条 Critical Path 闭合以前，AIR-002/003/004/007 可以做局部 unit/reference 准备，但不得把“已写出算法文件”计作 M1 垂直切片进度。

## 20. M1 代表指标选择

| Metric | 名称 | Value Kind | 选择原因 | 里程碑说明 |
| --- | --- | --- | --- | --- |
| P1-AIR-001 | MAX_ABS_BODY_ROLL_RATE_OBSERVED | NUMERIC | 验证 validity-piece、coverage/max-gap 与简单 extremum 数值路径。 | 正式交付=M2 |
| P1-AIR-002 | MAX_NZ_OBSERVED | NUMERIC | 验证无 profile parameter 的普通数值 Metric 与 diagnostic evidence 分离。 | 正式交付=M2 |
| P1-AIR-003 | TRUE_HEADING_RATE_OBSERVED | NUMERIC | 验证角度 unwrap + DERIVATIVE_LLS_V1 + 参数化窗口。 | 正式交付=M2 |
| P1-AIR-004 | SUSTAINED_TRUE_HEADING_RATE_OBSERVED | NUMERIC | 验证 upstream series、ROLLING_MEDIAN、持续窗口、coverage 与 supporting dwell Evidence。 | 正式交付=M3；M1仅早期集成，不计作M3完成 |
| P1-AIR-007 | TAS_MACH_ENVELOPE_OBSERVED | STRUCTURED | 验证 STRUCTURED value、固定 output schema、分通道 insufficient 与 quantile operator。 | 正式交付=M3；M1仅早期集成，不计作M3完成 |

M1 选用 AIR family 是为了在不引入目标参考真值、传感器 applicability 和多源关联的情况下，把 Metric Engine 的五种关键路径提前跑通。AIR-004/AIR-007 的正式 Catalog delivery milestone 仍是 M3；M1 实现只用于架构集成和 Golden 提前验证，不能更改 `P1_METRIC_CATALOG.json` 的 M3 归属。

## 21. M1 Basic Flight Episode / Stage

M1 使用机器权威 `BASIC_FLIGHT_V1`，不创建新的测试专用 Stage code：

| 顺序 | Stage | 语义 |
| --- | --- | --- |
| 1 | SETUP_ENTRY | Subject/configuration/reference readiness and entry-condition interval. |
| 2 | EXECUTION | Primary maneuver/task execution interval. |
| 3 | STABILIZATION_RECOVERY | Post-execution stabilization or recovery interval. |
| 4 | COMPLETION | Completion-rule and terminal-state interval. |

Synthetic fixture 必须提供可独立审阅的 Stage boundary 依据。M1 允许使用明确的 Context official marker 构造确定性 Golden Stage，但 Stage Projector 仍必须遵守现行 precedence/revision/boundary/quality contract。

## 22. M1 Synthetic / Golden Fixture 设计

M1 至少建立以下 fixture bundle：

| Fixture | 目的 | 必须覆盖 |
| --- | --- | --- |
| BF_M1_NOMINAL_V1 | 主 Golden | 四个 Basic Stage；连续有效数据；5项代表Metric；完整Release/API/GUI |
| BF_M1_GAP_V1 | 缺口/coverage | 内部 gap、min_coverage、max_gap；AIR-001/004 eligibility 与 Evidence |
| BF_M1_ANGLE_WRAP_V1 | 角度/导数 | heading 跨 ±π；验证 unwrap + DERIVATIVE_LLS_V1 不产生假峰值 |
| BF_M1_STRUCTURED_PARTIAL_V1 | 结构化部分缺失 | tas 有数据而 mach 缺失，反向再一例；验证 AIR-007 subrecord status |
| BF_M1_STAGE_BOUNDARY_V1 | Stage 边界 | Metric window 不跨 Episode/Stage/validity boundary 产生错误结果 |
| BF_M1_REPLAY_V1 | 历史重放 | 发布后改变 current profile/fixture registry，旧 Release 仍按 frozen refs 重放 |
| BF_M1_CROSS_PLATFORM_V1 | 双平台 | 同一冻结 bundle 在 Windows/Linux 做 logical-equivalence diff |
| BF_M1_FAILURE_V1 | 失败闭合 | corrupt manifest/version mismatch/missing artifact/DB write denial 等 fail-closed |

每个 bundle 建议采用 `manifest + source payload + context artifacts + expected/` 结构。`expected` 必须由人工可复算逻辑、参考脚本或独立实现生成并经审查批准，不能把被测程序第一次输出直接作为 Golden。

## 23. M1 工作包 Backlog

| Task ID | WS | 交付物 | 最低验收 |
| --- | --- | --- | --- |
| M1-DATA-001 | WS-DATA | Synthetic Source Adapter | 只接收受控 fixture bundle；source identity/hash 可追踪 |
| M1-DATA-002 | WS-DATA | Source Registry/Artifact registration | 原始 bundle 与 Context artifact 均有 immutable ref/hash |
| M1-DATA-003 | WS-DATA | Session Time ingest path | 源时间→Session Time 显式；不依赖 OS timezone/locale |
| M1-DATA-004 | WS-DATA | Aircraft entity resolution | 单架 aircraft stable identity 可重放 |
| M1-DATA-005 | WS-DATA | Canonical flight channels | body_p_rad_s/nz_g/heading_true_rad/tas_mps/mach/session_time/quality 进入 Canonical |
| M1-DATA-006 | WS-DATA | Evaluation Context resolver | 绑定 Basic profile、Stage profile、metric profile/artifact refs |
| M1-DATA-007 | WS-DATA | Lineage/quality propagation | Canonical 字段可追溯 source；missing/invalid 不变成0 |
| M1-WORLD-001 | WS-WORLD | Basic Episode detector | 生成可重放 Episode identity/revision |
| M1-WORLD-002 | WS-WORLD | BASIC_FLIGHT_V1 Stage projector | 四 Stage 顺序、[start,end)、precedence/boundary contract |
| M1-WORLD-003 | WS-WORLD | Stage quality/status | coverage/confidence/detector_version 进入产品 |
| M1-WORLD-004 | WS-WORLD | Minimal P1 World product | 只构造代表Metric所需 aircraft observed world；无伪造 P/A/J |
| M1-WORLD-005 | WS-WORLD | Revision/supersede smoke | Stage 修订新建 revision，不改历史 published Stage |
| M1-WORLD-006 | WS-WORLD | World logical hash | 同输入跨平台逻辑 hash 稳定 |
| M1-WORLD-007 | WS-WORLD | World evidence refs | Metric 可引用确定的 World/Stage/Canonical refs |
| M1-MET-001 | WS-METRIC | MetricContext builder | exact catalog/profile/input authority；不从 UI/DB 猜字段 |
| M1-MET-002 | WS-METRIC | P1-AIR-001 | 公式/validity/coverage/Evidence/Golden exact |
| M1-MET-003 | WS-METRIC | P1-AIR-002 | 主值与 diagnostic min evidence 分离 |
| M1-MET-004 | WS-METRIC | P1-AIR-003 | unwrap + DERIVATIVE_LLS_V1 + gap |
| M1-MET-005 | WS-METRIC | P1-AIR-004 | ROLLING_MEDIAN + sustained dwell evidence |
| M1-MET-006 | WS-METRIC | P1-AIR-007 | STRUCT_P1_AIR_007_V1 typed structured output |
| M1-MET-007 | WS-METRIC | Metric applicability/value-kind gate | AIR subject=Aircraft；typed result slot exact |
| M1-MET-008 | WS-METRIC | Metric compute staging | compute 不直接发布；失败不污染 current |
| M1-OBS-001 | WS-OBSERVATION | P1 Aircraft Observation builder | Metric publication_route→CAPABILITY_OBSERVATION |
| M1-OBS-002 | WS-OBSERVATION | SESSION Release builder | 绑定 Session/Context/Catalog/Definition/World/Evidence |
| M1-OBS-003 | WS-OBSERVATION | Publish CAS/idempotency | 重复提交不产生重复 current Release |
| M1-OBS-004 | WS-OBSERVATION | Historical read | 按 release-bound refs 读取，禁止 latest fallback |
| M1-OBS-005 | WS-OBSERVATION | Replay command | 同 provenance 复算并比较 logical products |
| M1-STO-001 | WS-STORAGE | M1 persistence mappings | 只按 Core model/Repository mapping 实现，不新增隐性表语义 |
| M1-STO-002 | WS-STORAGE | staging→sealed object flow | crash/cancel/orphan cleanup smoke |
| M1-STO-003 | WS-STORAGE | SQLite/PostgreSQL parity | 相同 fixture 发布相同 logical Release membership |
| M1-API-001 | WS-API | Import/compute/publish commands | 均支持 Idempotency-Key/request hash |
| M1-API-002 | WS-API | Session/Context/Episode/Stage queries | 只返回 generated DTO/projection |
| M1-API-003 | WS-API | Metric list/detail/evidence query | 使用 immutable Definition/Release，不读取 current formula |
| M1-API-004 | WS-API | Release/historical read/replay query | 明确 release identity/provenance/status |
| M1-API-005 | WS-API | series/timeline range query | 不把高频序列塞入单个大 JSON |
| M1-GUI-001 | WS-GUI | Session Browser | 选择 synthetic Session/Release |
| M1-GUI-002 | WS-GUI | Context/Mission Header | 显示 baseline/context/release identity 和 readiness |
| M1-GUI-003 | WS-GUI | Master Timeline | 统一控制 Stage/metric/evidence 游标 |
| M1-GUI-004 | WS-GUI | Basic Stage lane | 四 Stage 可见且与时间轴对齐 |
| M1-GUI-005 | WS-GUI | Metric List | 显示5项代表Metric状态/value kind/quality |
| M1-GUI-006 | WS-GUI | Metric Detail + Evidence | 公式不由UI定义；可下钻 input/world/stage/evidence refs |
| M1-GUI-007 | WS-GUI | Data Quality/Failure states | N_A/INSUFFICIENT/INVALID/系统错误视觉分离 |
| M1-TST-001 | WS-TEST | 8个 M1 fixture bundles | fixture manifest/hash/expected/tolerance 完整 |
| M1-TST-002 | WS-TEST | 5项 Metric unit+Golden | 每项 nominal+edge+failure |
| M1-TST-003 | WS-TEST | Stage Golden | 四 Stage boundary exact |
| M1-TST-004 | WS-TEST | Release immutability test | published payload/definition/context 不可原地修改 |
| M1-TST-005 | WS-TEST | Idempotency race test | 并发同请求只有一个逻辑发布 |
| M1-TST-006 | WS-TEST | Historical replay test | current 改变不影响旧 Release 解释 |
| M1-TST-007 | WS-TEST | API contract snapshot | DTO/time/structured result exact |
| M1-TST-008 | WS-TEST | GUI E2E | import→compute→publish→timeline→metric detail→replay |
| M1-TST-009 | WS-TEST | cross-platform logical equivalence | Windows/Linux exact/tolerance diff report |
| M1-TST-010 | WS-TEST | cold-start M1 | 空 workspace + frozen bundle 重现 M1 |
| M1-PLAT-001 | WS-PLATFORM | Windows Desktop M1 E2E | 完整 vertical slice |
| M1-PLAT-002 | WS-PLATFORM | Linux Desktop M1 E2E | 与 Windows 同一 fixture |
| M1-PLAT-003 | WS-PLATFORM | Windows/Linux Service smoke | 同一 Application/Repository contract |
| M1-PLAT-004 | WS-PLATFORM | logical-equivalence report | 排除 path/PID/native bytes，业务结果可比较 |

## 24. M1 Definition of Done / Exit Gate

M1 通过必须同时满足：

1. `BF_M1_NOMINAL_V1` 能从 source bundle 一键跑到 published SESSION Release；
2. Basic Flight Episode 与四个 Stage exact Golden PASS；
3. 5项代表指标全部通过 unit + Golden；
4. AIR-007 STRUCTURED object 通过 schema/hash/transport contract；
5. N_A/INSUFFICIENT/INVALID 与系统错误路径均有 fixture；
6. Observation 与 SESSION Release 保存完整 frozen provenance；
7. 重复 compute/publish 具备 idempotency，current pointer 不产生重复逻辑 Release；
8. 修改 current Context/Profile 后，旧 Release historical read 不改变；
9. Replay 使用旧 provenance 能产生相同 logical product；
10. GUI 可完成 Session→Timeline→Stage→Metric→Evidence 下钻；
11. GUI 不直连 DB，不在 ViewModel 中重新计算业务 Metric；
12. Windows Desktop 与 Linux Desktop 完整 E2E PASS；
13. Windows/Linux exact fields 相同，numeric fields 满足同一 Golden tolerance；
14. SQLite/PostgreSQL repository conformance 至少对 M1 product 集 PASS；
15. build manifest/SBOM/baseline hashes 随 M1 artifact 归档；
16. cold-start 从冻结 source+baseline bundle 完整重现。

M1 Exit 后才允许把 M2 的 backlog 从 Epic 级细化到任务级，并以 M1 暴露的真实架构问题修订 SDIB-1.1。

# Part IV — M2～M9 后续路线与进入条件

## 25. M2 — P1 Basic Flight Complete

### 25.1 Entry Gate

M2 只有在以下条件同时成立时才进入 `M2_ADMITTED`：

1. §24 M1 Exit 全部 PASS，且 Exit Review 在 protected `main` 的 exact merged SHA 上给出 `GO`；
2. M1 暴露的 MetricContext、Release、API、GUI 不存在未关闭的架构级 blocker；
3. `CB-1.4.0`、DB schema `1.6.0`、`P1_METRIC_CATALOG.json` 与相关 Canonical machine authority 仍是当前冻结输入；
4. Catalog 对 M2 的交付集合必须保持 exact：`delivery_milestone=M2`、`delivery_batch=P1_FOUNDATION_32` 共 32 项；
5. 不存在要求实现者猜测 Metric/Stage/DTO/Core schema 语义的未决 authority gap；若发现，必须 fail closed 并进入治理变更，而不是在 runtime/adapter 中补常量。

M1 Exit GO 只允许进入 M2，不表示任何 M2 Task 已完成。

### 25.2 冻结目标与 Catalog 交付边界

完成 Basic Flight 的完整 P1 数据/Stage/World/Metric/Observation/GUI 闭环，并完成 Catalog 定义的 `P1_FOUNDATION_32`（32项）正式交付批次及其 Golden 证据。

规划边界：

- 把 M1 的代表 Metric pipeline 扩成同一套、Catalog 驱动的通用 Metric Engine；禁止复制第二套 Metric Engine；
- 32 项 foundation batch 必须按 Catalog exact delivery metadata、semantic identity/version、operator/constant/upstream/state-machine bindings、publication route、observation lane、value kind 与 structured schema 实现；
- SNS family 必须执行 frozen `RADAR` applicability；不得把 SNS 指标误用于 IRST/EO；
- M1 已实现的 `P1-AIR-001/002/003` 只能作为已存在实现复用，M2 仍必须按正式 delivery milestone 重新满足 M2 Golden/Release/GUI/跨平台验收；
- QA 的 evidence-only/system-performance route 与 AIR capability-observation route 必须保持产品语义隔离；
- Basic Flight 训练工作流与 Sensor foundation batch 可以并行施工，但必须在同一个 M2 Exit Gate 汇合。

Catalog exact 32 项：

| Family | Metric codes | Count |
|---|---|---:|
| REFERENCE_TRUTH | `P1-QA-001`, `P1-QA-002`, `P1-QA-006` | 3 |
| TIME_ALIGNMENT | `P1-QA-003`, `P1-QA-004`, `P1-QA-005`, `P1-QA-007`, `P1-QA-008` | 5 |
| AIRCRAFT_FLIGHT | `P1-AIR-001`, `P1-AIR-002`, `P1-AIR-003` | 3 |
| SENSOR_DETECTION | `P1-SNS-001` … `P1-SNS-004` | 4 |
| SENSOR_ACCURACY | `P1-SNS-005` … `P1-SNS-021` | 17 |
| **Total** | `P1_FOUNDATION_32` | **32** |

### 25.3 M2 Task Backlog

Task ID 管理可验证交付物；Canonical/Metric/Stage/DTO/schema 语义仍由 CB-1.4.0 machine authority 管理。下表中的最低验收不得通过缩小 frozen Catalog 语义来满足。

| Task ID | Primary WS | 交付物 | 主要依赖 | 最低验收 |
|---|---|---|---|---|
| M2-DATA-001 | WS-DATA | Reference-relative truth 输入闭环 | M1 data/context + frozen input authority | `P1-QA-001/002` 所需 pairwise truth/time/frame 输入可重放，identity/time/frame provenance 完整 |
| M2-DATA-002 | WS-DATA | Sensor/INS time-alignment 输入闭环 | M1 Session Time + frozen input authority | `P1-QA-003/004/005/007/008` 的时间、latency、interpolation-age/uncertainty 输入具备 exact lineage 与 negative fixture |
| M2-DATA-003 | WS-DATA | RADAR mission-system instance ingest/identity | source registry + entity resolution | SNS 输入绑定到明确 `MISSION_SYSTEM_INSTANCE`，RADAR identity/applicability 可执行，非 RADAR 路径 fail closed |
| M2-DATA-004 | WS-DATA | Reference ↔ measurement alignment/quality | DATA-001..003 | `P1-QA-006` 与 SNS accuracy 所需 measurement/reference pairing、quality、coverage/max-gap/uncertainty provenance 可审计 |
| M2-DATA-005 | WS-DATA | M2 frozen fixture family | DATA-001..004 | nominal、wrap/boundary、gap、insufficient、invalid、wrong-sensor applicability fixtures 均有 manifest/hash 与 Windows/Linux 同源约束 |
| M2-WORLD-001 | WS-WORLD | M2 reference/time World inputs | DATA-001/002/005 | 按 frozen input authority 产出 QA 所需 World 产品；logical hash/replay stable；不新增 shadow schema |
| M2-WORLD-002 | WS-WORLD | M2 RADAR sensor World inputs | DATA-003/004/005 | 按 frozen input authority 产出 SNS 所需 World 产品；RADAR applicability 与 subject identity 保真 |
| M2-WORLD-003 | WS-WORLD | M2 Basic Flight Stage/World lineage & status | WORLD-001/002 + M1 Stage | Stage/World validity、coverage、confidence、lineage 对新增 M2 产品可重放，existing Stage authority 不被改写 |
| M2-MET-001 | WS-METRIC | Catalog-driven general Metric Engine | M1 Metric engine + WORLD-001..003 | 通过 registry/operator/plugin 机制执行 M2 Catalog；无 per-family 第二引擎；deterministic ordering/hash |
| M2-MET-002 | WS-METRIC | QA foundation 8 metrics | MET-001 + DATA/WORLD QA inputs | `P1-QA-001..008` exact Catalog semantics、value kind、structured schema、Golden/negative cases PASS |
| M2-MET-003 | WS-METRIC | AIR M2 formal delivery | MET-001 + M1 AIR implementation | `P1-AIR-001/002/003` 按 M2 formal delivery 重新通过 Catalog/Golden/Evidence/Release 验收，不以 M1 提前实现替代 |
| M2-MET-004 | WS-METRIC | SNS detection 4 metrics | MET-001 + WORLD-002/003 | `P1-SNS-001..004` exact Catalog semantics 与 RADAR applicability PASS；非适用系统不产生伪观测 |
| M2-MET-005 | WS-METRIC | SNS accuracy 17 metrics | MET-001 + DATA-004 + WORLD-002/003 | `P1-SNS-005..021` exact Catalog semantics/units/operators/Golden PASS |
| M2-MET-006 | WS-METRIC | Runtime applicability/value-kind/schema gates | MET-002..005 | subject/family applicability、NUMERIC/STRUCTURED slots、structured schema 与 N_A/INSUFFICIENT/INVALID 分支 exact |
| M2-MET-007 | WS-METRIC | 32-metric deterministic batch/replay contract | MET-002..006 | exact 32-code membership、dependency ordering、batch hash、per-metric definition/evidence hash 可重复且跨平台一致 |
| M2-OBS-001 | WS-OBSERVATION | Exact publication lane/route for 32 | MET-007 | 每项 Metric 按 frozen `publication_route` / `observation_lane` 进入 capability/system-performance/evidence-only 产品；无 route 漂移 |
| M2-OBS-002 | WS-OBSERVATION | Immutable M2 Release snapshots | OBS-001 | Definition/Evidence/Context/World/identity/provenance 全部 release-bound；historical read 不读取 latest Catalog/Profile |
| M2-OBS-003 | WS-OBSERVATION | Idempotent publication + replay for foundation batch | OBS-002 | concurrent/retry 只有一个 logical publication；replay 使用 release provenance，禁止 silent latest fallback |
| M2-GUI-001 | WS-GUI | Basic Flight foundation navigation | OBS-001..003 | Session→Timeline/Stage→family/Metric→Evidence 可覆盖 32 foundation Metrics；GUI 不直连 DB |
| M2-GUI-002 | WS-GUI | Observation-lane aware presentation | GUI-001 | capability、system-performance、quality-evidence-only 语义清晰分离；route/status/provenance 可见且不在 ViewModel 重算 Metric |
| M2-GUI-003 | WS-GUI | Applicability/quality/error-state UX | GUI-001/002 + MET-006 | N_A/INSUFFICIENT/INVALID/system-error/wrong-sensor applicability 不混淆，Evidence drill-down 可追溯 |
| M2-TST-001 | WS-TEST | Exact M2 Catalog coverage contract | frozen Catalog | 32/32 codes exact；milestone/batch exact；无 M3 remainder 被计入；RADAR applicability contract 有静态/运行时断言 |
| M2-TST-002 | WS-TEST | QA/AIR Golden + negative suite | DATA/WORLD + MET-002/003 | Windows/Linux 同 fixture；QA 8 + AIR 3 的 numeric/structured/invalid/insufficient Golden PASS |
| M2-TST-003 | WS-TEST | SNS Golden + applicability suite | DATA/WORLD + MET-004/005/006 | SNS 21 项 Golden PASS；RADAR positive + IRST/EO negative applicability PASS |
| M2-TST-004 | WS-TEST | Release/history/replay/idempotency suite | OBS-001..003 | 32-metric immutable Release、historical stability、replay exact/tolerance、concurrent idempotency PASS |
| M2-TST-005 | WS-TEST | Cross-platform/storage qualification | TST-001..004 | Windows/Linux logical-equivalence + SQLite/PostgreSQL logical Release membership parity PASS on exact candidate SHA |
| M2-TST-006 | WS-TEST | Cold-start + M2 Exit review | all M2 Tasks | clean source+baseline bundle 重建；27/27 Task evidence exact；`failed_acceptance=[]`；protected-main M2 Exit GO |

### 25.4 粗粒度执行批次

在 #85 coarse-grained policy 下，M2 最多建立四个执行批次；本节冻结推荐边界与顺序，Batch Issue 必须复制完整 Task ID 与最低验收，不得重新定义语义。

1. **M2 Batch 1 — Data + World foundations**：`M2-DATA-001..005`, `M2-WORLD-001..003`
2. **M2 Batch 2 — General Metric Engine + P1_FOUNDATION_32**：`M2-MET-001..007`
3. **M2 Batch 3 — Publication + GUI product closure**：`M2-OBS-001..003`, `M2-GUI-001..003`
4. **M2 Batch 4 — Golden / parity / cold-start / Exit**：`M2-TST-001..006`

默认执行顺序为 `Batch 1 → Batch 2 → Batch 3 → Batch 4`。只有前一 Batch 的 exact candidate Hosted CI 与 post-merge protected-main evidence PASS 后，下一 Batch 才可计为 active；允许在同一 Batch 内按显式依赖并行。

### 25.5 M2 Exit Gate

M2 GO 必须同时满足：

1. 27 个 M2 Task 全部具备 exact merged-commit 与 protected-main evidence；
2. `P1_FOUNDATION_32` 32/32 exact membership PASS，且没有把 `P1_REMAINDER_84` / M3 指标计入 M2 完成度；
3. QA 8、AIR 3、SNS 21 的 Catalog semantics、Golden、Evidence 与 publication route 全部 PASS；
4. SNS `RADAR` applicability 的 positive/negative runtime gate PASS；
5. 32-metric Release immutable、historical read、replay、idempotency PASS；
6. Basic Flight GUI 对 32 foundation Metrics 的导航、状态与 Evidence drill-down PASS，GUI 不直连 DB/不重算业务 Metric；
7. Windows/Linux logical-equivalence 与 SQLite/PostgreSQL logical Release membership parity 在 exact candidate/merged SHA 上 PASS；
8. build manifest/SBOM/baseline hashes 与 M2 artifacts 归档；
9. clean workspace + frozen source/baseline bundle 可重建 M2；
10. M2 Exit Review `failed_acceptance=[]`、无未处置 authority/security/blocker risk，并在 protected `main` exact SHA 上给出 GO。

只有 M2 Exit GO 后，才允许细化并进入 M3 实施 backlog。
## 26. M3 — P1 Four-Training-Type Complete

完成 Basic/WVR/BVR/Strike 四类训练的 P1 observed-performance，以及剩余 `P1_REMAINDER_84`，使 116 项 executable P1 Metric 都拥有生产候选实现、Golden、Evidence、API/GUI 投影和跨平台验证。

重点包括：

- WVR/BVR/Strike Stage/World/Event；
- TRK/ID/PSV/ESM/DL/FUS 等产品层分离；
- 05C1 的 family applicability 全部进入 runtime gate；
- Structured schemas 全部可执行；
- 四训练类型的 GUI specialized workspace 开始形成。

## 27. M4 — P1 Longitudinal & Debrief Closure

M4 只完成 P1 Aircraft/Mission-System observed trend、historical replay、Evidence-first Debrief 与 analytics，不提前激活 P4 人员训练评价。

104 个 `p1_longitudinal_trend_eligibility=true` 的 NUMERIC Metric 才能进入当前 P1 longitudinal_sample。STRUCTURED、quality-only、TARGET_PAIR lane 仍按现有合同排除。

## 28. M5 — P1 Product Qualification & Release

M5 把“工程可运行”升级为“可正式交付”：四个 mandatory Windows/Linux certification profile、目标硬件 workload、性能、资源安全、安装/升级/回滚、安全治理、备份恢复、SBOM/Manifest、cold-start 和正式 Release evidence 全闭合。

M5 之前的开发包不得冒充该资格结果。

## 29. M6～M9 — Future P Admission

| M | 准入P | 进入前必须证明 |
| --- | --- | --- |
| M6 | P2 | P1 稳定；Factor/Reference/Cohort 数据闭合；NOT_IDENTIFIABLE、uncertainty、knowledge-time/leakage Gate 可执行 |
| M7 | P3 | P2 归因/调整经过验证；Model Registry、applicability/OOD、独立验证、Twin revision/release 已治理 |
| M8 | P4/P5 | C/W/P/A/J/M 证据边界稳定；Instructor revision、privacy、scope separation、team composition 与 assessment profile Gate 闭合 |
| M9 | P6 | 事实与 projection 物理隔离；External/LVC gateway、forecast/counterfactual assumptions/model/approval、闭环建议安全治理闭合 |

远期实施细节必须在对应前置 M 的真实运行数据和验证证据基础上重新细化，不允许 SDIB-1.1 预先替未来模型/算法做未经验证的实现承诺。

# Part V — 开发治理、变更与质量规则

## 30. Issue / Branch / PR 规则

### 30.1 Issue 标识

标题建议：`[M1][WS-METRIC][P1-AIR-003] Implement TRUE_HEADING_RATE_OBSERVED`。

Issue 必填：M、Primary WS、相关 P、Stage（如适用）、authority refs、输入/输出、acceptance tests、Golden fixture、security/data impact、cross-platform impact。

### 30.2 PR 最小内容

每个业务 PR 必须说明：

- 修改的是 machine authority、generated projection、implementation 还是 test fixture；
- 是否改变 semantic identity/comparability；
- 哪些 tests 新增/改变；
- Windows/Linux 结果；
- 是否影响 replay/migration/Release；
- 是否需要 Baseline Change Request/ADR。

禁止把“代码能跑”作为唯一合并依据。

## 31. Change Classification

| Change Class | 示例 | 处理 |
| --- | --- | --- |
| C0 Implementation-only | 性能优化、内部重构且 logical product 不变 | 普通 PR + regression + cross-platform |
| C1 SDIB implementation contract | repo结构、CI、packaging、M0/M1 task/Gate | 更新 SDIB/ADR；不改 Core |
| C2 Canonical non-semantic metadata | 描述/追踪但不改业务行为 | authority PR + Baseline Lock + validator |
| C3 Semantic contract | Metric formula/Stage/DTO/schema/nullability/authority | 必须先改 Canonical/version，再生成代码；Golden/replay/migration closure |
| C4 P capability admission | 启用 P2～P6 或扩大 intended-use | 对应 M6～M9 admission + validation/governance evidence |

## 32. Definition of Ready / Definition of Done

### Feature DoR

- 有明确 M/WS/P/Stage 分类；
- authority 已存在或变更请求已批准；
- 输入/输出、N/A/failure 边界明确；
- Golden/contract 测试方法可定义；
- 数据权限/安全/跨平台影响已识别。

### Feature DoD

- 代码+测试+文档/生成投影一致；
- 无未声明 Canonical/DTO/Metric/Stage 分叉；
- unit/contract/Golden（适用时）通过；
- Windows/Linux Gate 通过；
- audit/observability 足以定位失败；
- replay/migration/security 影响已验证；
- PR evidence 可追溯到 Issue/authority。

## 33. Security 与 Data Governance 在 M0/M1 的最低实现

M0/M1 虽然使用 synthetic data，也必须先建立正式安全骨架：

- Desktop backend 仅 loopback；随机 bearer token；受控 origin/path allowlist；
- Service profile 预留 encrypted transport、identity/RBAC port；
- audit 对 import、publish、withdraw/cancel、config/profile/baseline change 等关键动作可记录；
- raw/derived export 有统一 audit hook；
- 未批准 operational/sensitive 数据时禁止通过“临时测试路径”绕过治理；
- 诊断包默认不携带原始敏感训练数据；
- secret、token、credential 不进入日志、fixture、build manifest 或 Golden。

## 34. Observability

从 M0 起统一结构化日志字段：request/job/session/release/component/version/reason code；业务时间与系统日志时间分离。关键计算保存 build/job manifest。监控必须区分业务不足与系统故障。

M1 E2E 出错时，应能够从 UI/API 的 correlation identity 追到 Job→Staging→World/Metric→Release/Audit，而不是依赖人工翻多份日志猜测。

## 35. Performance 实施策略

M0 的 WS-PERFORMANCE 只冻结 **design workload envelope 与测量框架**，不做最终优化承诺。先保证 Correctness、Determinism、Replayability、Cross-platform parity，再优化。

M0/M1 至少记录：输入规模、rows/bytes、Session 时长、Worker数、RSS/CPU、主要 step elapsed、object/DB I/O。M5 才在批准的 target hardware/workload profile 上冻结 P50/P95、throughput、resource baseline 并做正式资格。

## 36. 主要实施风险与控制

| 风险 | 描述 | 级别 | 控制 |
| --- | --- | --- | --- |
| R-01 | Canonical 与手写代码漂移 | 高 | generated-only contract + regenerate-diff + Baseline Lock |
| R-02 | 先批量写116指标导致后期集成失败 | 高 | M1 vertical slice + Golden first；M2/M3 才扩量 |
| R-03 | SQLite/PostgreSQL 行为分叉 | 高 | Repository conformance + same logical fixtures |
| R-04 | Windows/Linux 末期移植 | 高 | M0 双平台 CI；同 fixture logical-equivalence |
| R-05 | GUI 反向定义业务逻辑 | 高 | Application-only ingress；ViewModel mapper；architecture tests |
| R-06 | Replay 依赖 latest 配置 | 高 | Release-bound refs；missing fail-closed fixture |
| R-07 | 指标族适用对象误用 | 中高 | family applicability runtime gate；SNS=RADAR 等 contract tests |
| R-08 | Golden 被被测实现自我批准 | 高 | expected 独立生成/审查；fixture hash/version |
| R-09 | 过早性能优化破坏确定性 | 中 | correctness gates before performance changes；C0 regression |
| R-10 | P2-P6 UI 暗示已实现 | 中高 | feature gate dormant；API namespace/status contract |
| R-11 | 文档持续扩写但代码迟迟不开工 | 中 | SDIB 冻结后以 M0 code evidence 为主循环 |
| R-12 | 工具/版本选择长期悬而未决 | 中 | ADR-M0-001～010 是 M0 Exit blocker |

## 37. 开发角色与审查职责（不绑定具体编制人数）

- **Architecture/Core**：Core/Canonical、依赖方向、ADR、Baseline Change；
- **Data/World**：Source/Canonical/Context/Episode/Stage/World；
- **Metric/Algorithm**：operator、Metric、Golden 数学正确性；
- **Storage/Backend**：Repository、Job、Release/Replay、API；
- **GUI/Visualization**：PySide6、Timeline、Evidence、05G 工作流；
- **V&V/Test**：独立 Golden、contract、replay、cross-platform diff；
- **Platform/DevOps**：Windows/Linux、CI、package、SBOM、cold-start；
- **Security/Governance**：identity/audit/data policy/change governance。

同一人员可以兼任多个角色，但 **Metric 实现者不应独自批准自己的 Golden expected**；Baseline authority change 也应至少有独立审查。

# Part VI — 追踪、验收与启动清单

## 38. SDIB 与当前设计基线追踪

| SDIB主题 | 上位权威/设计 |
| --- | --- |
| P/M/WS/Stage | TERMINOLOGY_REGISTRY / CAPABILITY_PHASE_REGISTRY / DEVELOPMENT_MILESTONE_REGISTRY / ENGINEERING_WORKSTREAM_REGISTRY / STAGE_REGISTRY |
| 数据/Context/Episode | CORE_LOGICAL_MODEL + 05A |
| World/Stage/Event | STAGE_REGISTRY + WORLD_CAPABILITY_REGISTRY + 05B |
| 116 Metric | P1_METRIC_CATALOG + METRIC_INPUT_AUTHORITY_MATRIX + 05C/05C1 |
| Observation/Longitudinal | CORE_LOGICAL_MODEL + 05D |
| Release/Replay/Migration | CORE_LOGICAL_MODEL + 05E |
| Application/API/DTO | CROSS_LAYER_DTO_CONTRACTS + 05F |
| GUI | 05G |
| Platform/Security/CI | PLATFORM_COMPATIBILITY_REGISTRY + 05H |
| P4/P5 | TRAINING_EVALUATION_TAXONOMY + 05I |
| P2/P3/P6 | EXTENSION_CONTRACT_REGISTRY + 05J |
| 验证 | REVIEW_GATES + 06/07 |

## 39. M0/M1 启动与施工快速索引

本节不再维护第二份规范性启动顺序，避免与 Part II/III 发生 drift。实际执行必须回到：

- **M0 Entry**：§16.2；
- **M0 Backlog**：§17；
- **M0 启动顺序 ↔ Task 映射**：§17.1；
- **M0 六个施工波次**：§17.2；
- **M0 Exit**：§18；
- **M1 Entry Gate**：§19.1；
- **M1 启动清单**：§19.2；
- **M1 启动顺序 ↔ Task 映射**：§19.3；
- **M1 第一条最窄 E2E Critical Path**：§19.4；
- **M1 Backlog**：§23；
- **M1 Exit**：§24。

执行时应遵守以下关系：

```text
Entry Gate
   ↓
Startup / Construction Sequence
   ↓
Task Backlog（多 Task 可并行）
   ↓
Integration / Evidence
   ↓
Exit Gate
```

`Task ID` 不是施工步骤编号；`ADR ID` 不是开发 Task；`Milestone Transition Gate` 不是普通 Issue。项目管理系统可以把一个 Task ID 拆为多个子 Issue，但所有子项必须回指 SDIB Task，并且只有父 Task 的最低验收闭合后才可标记父 Task DONE。

## 40. SDIB-1.1 自身变更规则

- M0/M1 实施发现问题但不影响业务 Canonical：升级 SDIB patch/minor 并记录 ADR/Change Log；
- 若需要改变 Core/DTO/Metric/Stage/P/M/WS/Platform machine authority：先走对应 Baseline Change，更新 CB/Canonical/Lock/Validator，再更新 SDIB；
- **SDIB-1.1** 已在 M1 Exit GO 后把 M2 从 Epic 级细化为任务级，并吸收 M1 的真实代码、Golden、Release/replay 与跨平台反馈；M3 仍保持 Gate 后再细化；
- 不允许在 Issue/Wiki 中形成长期存在、却未回写 SDIB/Canonical 的“事实标准”。

# 附录 A — M0/M1 Gate 证据包目录建议

```text
evidence/
├─ baseline/
│  ├─ baseline-lock-check.txt
│  └─ generated-diff.txt
├─ ci/
│  ├─ windows/
│  └─ linux/
├─ tests/
│  ├─ unit.xml
│  ├─ contract.xml
│  ├─ golden.json
│  ├─ replay.json
│  └─ migration.json
├─ cross-platform/
│  └─ logical-equivalence.json
├─ build/
│  ├─ build-manifest.json
│  ├─ sbom.*
│  └─ native-dependencies.*
├─ gui-api/
│  ├─ openapi-snapshot.json
│  └─ smoke-results.json
├─ m0/
│  └─ exit-gate.json
└─ m1/
   └─ exit-gate.json
```

证据目录结构本身不是业务 authority，但 Release/Milestone Review 必须能够以自动化方式定位这些证据。

# 附录 B — M1 五项代表指标的实现提醒

### P1-AIR-001 — MAX_ABS_BODY_ROLL_RATE_OBSERVED

- **Subject**：`AIRCRAFT`
- **Value Kind**：`NUMERIC`
- **Catalog delivery milestone**：`M2` / `P1_FOUNDATION_32`
- **Inputs**：`body_p_rad_s, session_time_us, quality_mask, profile.min_coverage, profile.max_gap_us`
- **Algorithm**：`alg.tpaa.p1.air.max_abs_body_roll_rate@1.0.1`
- **Formula authority mirror**：max(abs(body_p_rad_s)) over validity-piece samples in the eligible window. The window is eligible only when valid covered duration/window duration >= min_coverage and no internal gap exceeds max_gap_us.
- **M1 要求**：实现必须从 Catalog/registry 获取输入、profile/operator/schema binding；本附录只是实施提醒，公式权威仍是 `P1_METRIC_CATALOG.json`。

### P1-AIR-002 — MAX_NZ_OBSERVED

- **Subject**：`AIRCRAFT`
- **Value Kind**：`NUMERIC`
- **Catalog delivery milestone**：`M2` / `P1_FOUNDATION_32`
- **Inputs**：`nz_g, session_time_us, quality_mask`
- **Algorithm**：`alg.tpaa.p1.air.max_nz@1.0.1`
- **Formula authority mirror**：Primary Metric value = max(valid nz_g) over the eligible window. Diagnostic Evidence records min(valid nz_g); that diagnostic value is not part of the Metric value/output schema.
- **M1 要求**：实现必须从 Catalog/registry 获取输入、profile/operator/schema binding；本附录只是实施提醒，公式权威仍是 `P1_METRIC_CATALOG.json`。

### P1-AIR-003 — TRUE_HEADING_RATE_OBSERVED

- **Subject**：`AIRCRAFT`
- **Value Kind**：`NUMERIC`
- **Catalog delivery milestone**：`M2` / `P1_FOUNDATION_32`
- **Inputs**：`heading_true_rad, session_time_us, profile.derivative_window_s, profile.max_gap_us`
- **Algorithm**：`alg.tpaa.p1.air.true_heading_rate@1.0.0`
- **Formula authority mirror**：Unwrap heading_true_rad, then compute angular rate with DERIVATIVE_LLS_V1: local first-order least-squares slope over the declared derivative_window_s using only same-validity-piece samples and never bridging max_gap_us. Metric value is abs(rate).
- **M1 要求**：实现必须从 Catalog/registry 获取输入、profile/operator/schema binding；本附录只是实施提醒，公式权威仍是 `P1_METRIC_CATALOG.json`。

### P1-AIR-004 — SUSTAINED_TRUE_HEADING_RATE_OBSERVED

- **Subject**：`AIRCRAFT`
- **Value Kind**：`NUMERIC`
- **Catalog delivery milestone**：`M3` / `P1_REMAINDER_84`
- **Inputs**：`heading_true_rad, session_time_us, profile.sustain_duration_s, profile.min_coverage, profile.max_gap_us`
- **Algorithm**：`alg.tpaa.p1.air.sustained_true_heading_rate@1.0.2`
- **Formula authority mirror**：Use the P1-AIR-003 instantaneous absolute heading-rate series. Inside SM_VALIDITY_PIECE_V1 compute ROLLING_MEDIAN_V1 over sustain_duration_s; a window is eligible only when min_coverage is met and no internal gap exceeds max_gap_us. Primary Metric value=maximum eligible rolling-median heading rate; the exact supporting dwell interval is mandatory Evidence, not an additional result value.
- **M1 要求**：实现必须从 Catalog/registry 获取输入、profile/operator/schema binding；本附录只是实施提醒，公式权威仍是 `P1_METRIC_CATALOG.json`。

### P1-AIR-007 — TAS_MACH_ENVELOPE_OBSERVED

- **Subject**：`AIRCRAFT`
- **Value Kind**：`STRUCTURED`
- **Catalog delivery milestone**：`M3` / `P1_REMAINDER_84`
- **Inputs**：`tas_mps, mach, session_time_us`
- **Algorithm**：`alg.tpaa.p1.air.tas_mach_envelope@1.0.2`
- **Formula authority mirror**：Publish exactly STRUCT_P1_AIR_007_V1 with fixed tas and mach subrecords. For each channel independently after validity filtering: N>=1 publishes status=VALID, n=N, min/max and QUANTILE_HF7_V1 P05/P50/P95; N=0 publishes status=INSUFFICIENT_DATA, n=0 and all numeric fields null. The Metric is N_A only when both subrecords are INSUFFICIENT_DATA. Altitude/context tags remain Observation/Evidence context and are not additional result fields.
- **M1 要求**：实现必须从 Catalog/registry 获取输入、profile/operator/schema binding；本附录只是实施提醒，公式权威仍是 `P1_METRIC_CATALOG.json`。

# 附录 C — 116 指标族在开发路线中的位置

| Family | 数量 | 实施解释 |
| --- | --- | --- |
| QA | 8 | 参考/时间/数据质量证据；foundation batch，不能被当成能力值 |
| AIR | 39 | Aircraft observed flight/energy/control/handling/persistence；M1先做5项代表 |
| SNS | 21 | RADAR detection/measurement；严格 RADAR applicability |
| TRK | 7 | 本机 Track product performance；不同于原始 sensor measurement |
| ID | 12 | association/identification product performance |
| PSV | 7 | IRST/EO passive sensor family |
| ESM | 6 | RWR/ESM family |
| DL | 8 | Datalink family |
| FUS | 8 | Fusion product family |

M1 只验证 AIR family 的通用执行链。M2/M3 扩展其他 family 时，不允许复制一套新的 Metric Engine；只能新增受 Catalog 驱动的 operator/plugin/adapter 实现。

# 附录 D — SDIB-1.1 交付判定

本文件交付只证明：R3.3 已被转换成一套可执行的软件开发实施基线。它**不证明** M0/M1 已经编码完成，也不证明 Windows/Linux 真实安装包、116指标实现、真实数据适用性或 P2～P6 已验证。

正式软件进度必须以后续仓库中的代码、CI、Golden、Release/Replay 与 Milestone Exit evidence 为准。

# 附录 E — 包依赖与禁止依赖合同

软件包边界不仅靠目录约定，还必须有 architecture test。M0 起必须执行以下依赖规则：

| 包/层 | 允许依赖 | 禁止依赖 |
| --- | --- | --- |
| `tpaa_generated` | Python stdlib / generation runtime only | GUI、DB driver、业务 service |
| `tpaa_registry / tpaa_canonical / tpaa_context` | generated、core utility ports | GUI、FastAPI、Qt、具体 DB 方言、OS-specific adapter |
| `tpaa_episode / tpaa_world` | canonical/context、generated | Metric result、Assessment、GUI |
| `tpaa_metric` | World/Stage/Event refs、Metric Catalog/operator registry | GUI、Repository ORM entity、current/latest shortcut |
| `tpaa_observation` | Metric published staging、Release ports | 重新计算 Metric/World、GUI |
| `tpaa_longitudinal` | Published Observation/Release refs | raw source、GUI、P4/P5 assessment shortcut |
| `tpaa_assessment` | Published evidence/metric/world refs | 重写上游 fact/metric |
| `tpaa_storage` | generated persistence mapping、storage ports | 业务推理、训练评价规则 |
| `tpaa_application` | Domain services + repository ports | GUI toolkit、数据库方言细节 |
| `tpaa_api` | Application + generated DTO | 直接 Repository/ORM、Metric operator |
| `tpaa_gui` | Application client/DTO/ViewModel mapper | SQLite/PostgreSQL、Metric engine internals |
| `tpaa_platform` | OS/native integrations | 业务规则、Metric formula、Stage semantics |

如果跨层需要共享能力，优先定义窄 Port/Protocol，而不是让上层 import 下层具体实现，或让下层反向 import 上层。Architecture test 必须能在 CI 中自动发现违反依赖方向的 import。

# 附录 F — M0/M1 CI Gate 矩阵

| Gate | M0 PR | M0 Exit | M1 PR | M1 Exit | Windows | Linux |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline Lock/hash | 必须 | 必须 | 必须 | 必须 | ✓ | ✓ |
| Generated-code diff | 必须 | 必须 | 必须 | 必须 | ✓ | ✓ |
| Static architecture dependency | 必须 | 必须 | 必须 | 必须 | ✓ | ✓ |
| Unit tests | 必须 | 必须 | 必须 | 必须 | ✓ | ✓ |
| Canonical/DTO/Registry contract | 必须 | 必须 | 必须 | 必须 | ✓ | ✓ |
| DB bootstrap/repository conformance | 子集 | 全量 M0 | 必须 | 全量 M1 | ✓ | ✓ |
| Golden metric | 框架 smoke | 框架 smoke | 受影响 fixture | 5项+8 bundle | ✓ | ✓ |
| Stage Golden | — | — | 受影响 fixture | Basic 4 Stage | ✓ | ✓ |
| Replay | 框架 smoke | 框架 smoke | 受影响 fixture | M1 完整 | ✓ | ✓ |
| API contract/OpenAPI snapshot | 基础 | 基础 | 必须 | 完整 M1 | ✓ | ✓ |
| Desktop GUI smoke | 启动退出 | 完整 M0 | 受影响路径 | 完整 M1 E2E | ✓ | ✓ |
| Service/API smoke | 启动 | 完整 M0 | 受影响路径 | 完整 M1 | ✓ | ✓ |
| Cross-platform logical diff | 基础对象 | 基础对象 | 受影响 fixture | `BF_M1_CROSS_PLATFORM_V1` | 比较端 | 比较端 |
| Package/SBOM/manifest | 开发 smoke | 必须 | 开发 smoke | 必须 | ✓ | ✓ |
| Cold-start | — | 必须 | — | 必须 | ✓ | ✓ |

PR Gate 应保持“快速但有意义”；Milestone Exit 使用完整证据集。不得通过永久关闭测试来缩短流水线。暂时隔离 flaky test 必须建立缺陷，并标记其是否阻断当前 M。

# 附录 G — 统一失败、业务不足与可恢复错误语义

实现中最容易出现的错误之一，是把所有异常都变成 exception/500，或反过来吞掉系统故障并输出 N_A。M0/M1 应统一三层语义：

1. **Business Product Status**：N_A、INSUFFICIENT_DATA、INVALID、REVIEW_REQUIRED 等，属于可发布/可解释的业务状态；
2. **Command/Job Failure**：输入包损坏、baseline mismatch、DB 不可写、artifact 缺失等导致本次命令无法完成；
3. **Infrastructure Incident**：进程崩溃、磁盘满、权限/网络/数据库不可用等，需要运维处置。

| 场景 | 分类 | 期望行为 |
| --- | --- | --- |
| Metric 前置数据不足 | Business Product Status | 形成 INSUFFICIENT_DATA/reason/evidence；不是0，不是500 |
| Metric 对该 subject 不适用 | Business Product Status | N_A + applicability reason |
| Metric 输入违反 Catalog contract | Job Failure | fail-closed；不得“尽量算” |
| Core/Catalog/DTO version mismatch | Readiness Failure | 不进入 READY，不执行业务计算 |
| 历史 Release 缺 frozen artifact | Historical Read Failure | 明确不可解释；禁止 latest fallback |
| SQLite/PostgreSQL 写入失败 | Infrastructure/Job Failure | 事务回滚；不产生半发布 Release |
| GUI backend 断开 | Infrastructure Incident | GUI 显示不可用并允许诊断/重连；不伪造结果 |
| Worker cancel | Controlled Job Termination | staging 可清理；已发布 Release 不变 |
| 磁盘满/对象无法 seal | Publish Failure | Publish 不提交；current pointer 不变 |

# 附录 H — 版本、构建和制品命名

为避免“软件版本=Core版本=Catalog版本”的混淆，实施必须保持多维版本：

- **Product build version**：软件代码/发布版本；
- **Core Baseline**：CB-1.4.0 等；
- **DB schema version**：当前 target 1.6.0；
- **Metric Catalog version**：当前 P1 Catalog 自身版本；
- **Stage/DTO/Registry versions**：各自独立；
- **SDIB version**：实施计划/开发基线版本；
- **Fixture version**：Golden bundle 自己的版本。

建议开发制品命名包含 product build + platform profile；业务产品 identity 不包含本地文件路径。例如：

```text
tpaa-<product_build>-WINDOWS_DESKTOP_X64
  build-manifest.json
  baseline-lock.json
  sbom.*
  native-dependencies.*
```

任何 UI “About/Diagnostics” 页面都应同时显示 product build、Core、schema、Catalog、platform profile，而不是只显示一个模糊“版本号”。

# 附录 I — 开发者本地命令合同

具体脚本工具可由 ADR 冻结，但开发者必须拥有跨平台等价的高层命令语义：

```text
bootstrap        安装/校验工具链与依赖锁
generate         从 Canonical 生成代码/Schema/OpenAPI projection
verify-baseline  校验 Baseline Lock 与 authority hashes
test-unit        单元测试
test-contract    Canonical/DTO/Registry/architecture contract
test-golden      Golden fixture
test-replay      Historical replay
test-migration   DB bootstrap/migration harness
test-e2e         API/GUI 端到端
run-api          启动 local/service API profile
run-gui          启动 Desktop profile
package          生成当前 platform development artifact
manifest         生成 build/package manifest 与 SBOM
cold-start       从 clean state 执行当前 M 的完整验收
```

这些是“命令语义”，不要求 Windows 与 Linux 使用相同 shell；Platform/DevOps 可以提供不同 launcher，但最终执行步骤和证据必须等价。

# 附录 J — Code Review 检查表

- [ ] Issue 的 M/WS/P/Stage 分类正确；
- [ ] 没有把 human Markdown 当 schema/Metric authority；
- [ ] 没有新增未经 Canonical 声明的字段/enum/reason code；
- [ ] 没有在 Metric 中重建已有 Event/Stage；
- [ ] 没有在 GUI/Controller 中实现业务推理；
- [ ] 没有使用 current/latest 解释历史 Release；
- [ ] 没有把 missing/insufficient 变成0；
- [ ] 没有 OS-specific 业务分支；
- [ ] 没有把绝对路径/PID/native bytes 纳入 logical hash；
- [ ] 有 unit/contract/Golden/replay 中适当组合的测试；
- [ ] Windows/Linux 必要 Gate 均通过；
- [ ] comparability/semantic identity 改变时已升级 authority；
- [ ] 数据访问/导出/审计边界变化已审查；
- [ ] build/traceability evidence 已更新。

Metric PR 必须至少有独立 Golden/数学审查者，不能由实现者单独批准 expected result。

# 附录 K — M0/M1 Milestone Review 模板

每次 M Exit Review 不以演示截图代替证据，应形成以下审查包：

1. **Scope**：本 M 的 registry objective 与已完成 backlog；
2. **Baseline**：source revision、Core/Catalog/schema/SDIB、Baseline Lock；
3. **Gate Results**：CI、contract、Golden、replay、platform、security；
4. **Open Defects**：按阻断/非阻断分类；
5. **Deviations/ADRs**：所有偏离默认方案的批准依据；
6. **Cross-platform**：Windows/Linux profile 证据与 logical diff；
7. **Reproducibility**：clean environment cold-start；
8. **Data Governance**：所用 fixture/source 分类与访问记录；
9. **Known Limitations**：明确哪些能力尚未实现，特别是未激活 P；
10. **Decision**：GO / CONDITIONAL GO / NO-GO，且只针对当前 M，不扩大为未来 P 能力结论。

**M0 GO** 只表示工程底座可以进入 M1；**M1 GO** 只表示 P1 最小切片成立，不表示 M2/M3/M5 已通过。

# 附录 L — M1 E2E 验收故事

**Story 1 — Nominal**：启动 Desktop → baseline READY → 导入 `BF_M1_NOMINAL_V1` → 看到 Session/Context → 计算 → Stage lane 出现四个 Stage → 5项 Metric 出现 → 发布 Release → Metric Detail 可下钻 Evidence → 关闭并重启 → 按 Release identity 读到相同结果。

**Story 2 — Insufficient**：导入 gap/partial fixture → 相关 Metric 显示 INSUFFICIENT_DATA 或按 Catalog eligibility 不产生 VALID value → UI 展示 reason/evidence，不显示0分或系统错误。

**Story 3 — Replay**：先发布 Release A → 修改 current profile/软件运行配置（不修改历史 artifact）→ 对 A 执行 historical read/replay → 仍绑定 A 的 frozen refs，不使用 current/latest。

**Story 4 — Cross-platform**：同一 frozen fixture/baseline/build logic 分别在 Windows/Linux 执行 → stable identity/Stage/status/Release membership exact；数值在同一 tolerance 内；差异报告只包含允许的物理差异。

**Story 5 — Failure**：人为制造 baseline mismatch、corrupt artifact、DB write denial 或 backend crash → 系统 fail-closed、保留诊断信息、无半发布 Release、current pointer 不被破坏。

# 附录 M — M0/M1 开发评审中的“禁止提前优化”清单

为了避免工程团队在最小闭环尚未成立前陷入局部最优，M0/M1 默认禁止以下行为，除非有明确缺陷或 ADR 证明其必要性：

- 为性能原因绕过 immutable Release/staging；
- 为减少查询次数让 GUI 直接访问 SQLite；
- 为“方便”在 Controller 中重新计算 Metric；
- 为跨平台性能差异写两套业务算法；
- 为快速出结果跳过 Context/Stage/World，直接从 raw source 算最终指标；
- 把多项 Metric 合并成一个私有批处理函数而失去独立 identity/version/evidence；
- 在 Golden 不稳定前引入复杂缓存、分布式调度或 GPU 路径；
- 在 M1 过早实现 P2～P6 页面；
- 在没有 workload envelope 和 profiling 证据时进行不可逆数据降采样；
- 为测试方便使用 latest/current 替代 frozen artifact。

M0/M1 的最优目标不是“最快”，而是**最可证明、最可重放、最不易返工**。

# 附录 N — WS × M 责任矩阵

下表不是新的 Milestone authority，而是把 `DEVELOPMENT_MILESTONE_REGISTRY.json` 转换为实施视图。`P` 表示 Primary/主责，`S` 表示 Supporting/支撑，`—` 表示该 M 默认不应主动扩展该 WS 的业务范围。

| WS | M0 | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WS-CORE | P | S | S | S | S | S | S | S | S | S |
| WS-DATA | S | P | P | S | S | S | P | S | S | S |
| WS-WORLD | — | P | P | P | S | S | S | S | P | S |
| WS-METRIC | — | P | P | P | S | S | S | S | S | S |
| WS-OBSERVATION | — | P | P | P | P | S | S | S | S | S |
| WS-LONGITUDINAL | — | — | S | S | P | S | S | P | P | S |
| WS-ASSESS | — | — | — | — | — | S | — | — | P | P |
| WS-CAPABILITY | — | — | — | — | — | S | P | P | S | P |
| WS-STORAGE | P | P | S | S | S | S | S | S | S | S |
| WS-API | P | P | S | P | P | S | S | S | S | S |
| WS-GUI | P | P | P | P | P | S | P | P | P | P |
| WS-TEST | P | P | P | P | P | P | P | P | P | P |
| WS-PLATFORM | P | P | S | S | S | P | S | S | S | S |
| WS-SECURITY | P | S | S | S | S | P | S | S | P | P |
| WS-PERFORMANCE | S | S | S | S | S | P | S | S | S | S |
| WS-DEVOPS | P | S | S | S | S | P | S | S | S | S |
| WS-INTEROP | — | — | — | S | S | S | — | — | S | P |
| WS-GOVERNANCE | P | S | S | S | P | P | P | P | P | P |

矩阵的用途是防止两种常见偏差：第一，某 WS 因“当前不是主责”而完全不维护其跨 M 合同；第二，某 WS 在尚未进入相应 M 时自行扩展未来 P 能力。所有主责仍以 Milestone registry 和 Issue 的 Primary WS 为准。

# 附录 O — Test Fixture / Golden 数据生命周期

Golden 数据是软件资格证据的一部分，不应被当作普通测试文件随意覆盖。建议建立如下生命周期：

```text
DRAFT
  ↓ 独立审查输入/expected逻辑
REVIEWED
  ↓ hash/version冻结
APPROVED_GOLDEN
  ↓ 被 CI/Milestone Gate 引用
RETIRED ──仍可用于历史回归/Replay
```

## O.1 Fixture 变更规则

- 修改输入数据字节：必须升级 fixture version/hash；
- 修改 expected result：必须说明是修复 Golden 错误还是上游 semantic change；
- Metric formula/Stage semantic change 导致 expected 改变：不得只更新 expected 文件，必须回指 Canonical version change；
- 仅修复测试 harness：不得无解释地重新批准所有 expected；
- Golden retired 后仍保留历史 build/release 对它的引用；
- 测试 fixture 不得包含真实敏感 operational data，除非进入受控数据环境并有相应批准策略。

## O.2 Expected result 的独立性

M1 的简单 Metric 应尽量采用人工可算/独立 reference script 双重核对。进入复杂 Event/Track/Fusion 后，可以使用独立 reference implementation，但其代码库/算法路径不得与被测实现完全共用同一函数，否则不能证明独立正确性。

# 附录 P — Dependency Upgrade 与第三方库治理

TPAA 的可重放性不仅依赖自身版本，也依赖数值库、Qt、数据库驱动等第三方依赖。依赖升级必须作为受控工程变更：

1. 依赖 PR 必须列出 old/new version 和变更原因；
2. 重新生成 dependency lock、SBOM、native dependency manifest；
3. 至少运行 unit/contract + 代表 Golden + cross-platform diff；
4. 涉及数值栈、Parquet、数据库、Qt、serialization 的升级应扩大到 Replay/E2E；
5. 如果 logical product 发生超出既有 tolerance 的变化，不能简单扩大 tolerance 掩盖；必须判断是 bug fix、数值实现差异还是 semantic change；
6. Windows/Linux 不得长期使用不同逻辑版本的核心数值依赖；平台 native build 可以不同，但版本/功能基线需可追踪；
7. Critical security update 可以走加速流程，但仍不能跳过最小 Golden/Replay 和 Release provenance。

依赖升级的目标不是“永远不升级”，而是确保升级后的历史结果差异可解释、可审计。

# 附录 Q — Runtime Readiness / READY 判定

软件“进程启动成功”不等于系统可执行业务。M0 起建立明确 readiness 判定，至少逐项检查：

| Check | READY 所需条件 | 失败行为 |
| --- | --- | --- |
| Core baseline | CB/version/hash 与 build manifest 一致 | NOT_READY，禁止业务命令 |
| Canonical authorities | 必需 artifact 可解析且 schema/version 支持 | NOT_READY |
| Generated contract | 生成代码 source hash 与 baseline 一致 | NOT_READY |
| DB schema | schema target/compatibility 正确 | NOT_READY，只允许诊断/迁移 |
| Repository | 必要 read/write transaction smoke 正常 | NOT_READY |
| Object/Parquet store | 根目录/权限/空间/URI mapping 可用 | 根据 profile 决定 NOT_READY/DEGRADED |
| Platform adapter | 当前 certification profile 已识别 | NOT_READY 或明确 UNSUPPORTED_PROFILE |
| Security minimum | token/identity/config 满足 profile | fail-closed |
| Worker | spawn/queue/heartbeat 基本可用 | 计算命令禁用 |
| GUI-backend handshake | Core/schema/API compatibility 一致 | GUI 不进入业务 READY |

允许存在 `DEGRADED`，但必须是受控能力降级，例如可浏览已发布历史 Release、但因 Worker 不可用不能发起新计算。`DEGRADED` 不能静默改变 Metric/Assessment 语义。

# 附录 R — Workload Envelope 模板

M0 需要冻结“如何描述工作负载”，M5 才冻结正式目标性能数值。每个性能 fixture 至少记录：

| 维度 | 描述要求 |
| --- | --- |
| aircraft_count | 单/多机数量与 active interval |
| mission_system_count | 每机系统实例数及 system_type |
| source_count | source artifact/stream 数量 |
| channel_count | Canonical/高频通道规模 |
| sample_rate | 各通道 nominal/peak rate |
| session_duration | 训练时长 |
| input_rows / bytes | 原始与 Canonical 数据量 |
| stage/event density | Episode/Stage/Event 数量与密度 |
| metric_count | 本次计算 Metric 数 |
| concurrent_jobs | 并发 import/world/metric/replay job |
| replay_clients | 并发查询/GUI 客户端 |
| memory budget | 进程/总 RSS 预算 |
| storage budget | DB/Parquet/object 临时和长期空间 |
| partition/chunk policy | 分片策略及边界 |
| platform profile | Windows/Linux Desktop/Service |
| build/baseline | Product/Core/Catalog/schema/dependency lock |

性能报告必须同时给出 workload hash/profile；不允许只写“处理一架次用了 X 秒”而没有输入规模和版本上下文。

# 附录 S — SDIB 到第一批正式开发 Issue 的转换示例

SDIB 冻结后，项目管理系统中的第一批 Issue 不需要重新发明计划，可直接由 M0 backlog 转换。例如：

```text
[M0][WS-DEVOPS] Formal Repository Bootstrap
  Task: M0-DEV-000
  Authority: SDIB §7 / §17 / §17.1
  Acceptance: protected main + repository skeleton + first bootstrap MR + Windows/Linux minimum CI pass

[M0][WS-CORE] Import and verify CB-1.4.0 baseline snapshot
  Authority: BASELINE_LOCK.json / SCHEMA_AUTHORITY_REGISTRY
  Acceptance: verify-baseline exact pass on Windows/Linux

[M0][WS-STORAGE] Bootstrap DB schema 1.6.0
  Authority: CORE_LOGICAL_MODEL.json / 05E
  Acceptance: clean SQLite + PostgreSQL bootstrap and repository conformance

[M0][WS-API] Generate critical DTO and OpenAPI snapshot
  Authority: CROSS_LAYER_DTO_CONTRACTS.json
  Acceptance: exact required/nullability/transport type diff=0

[M0][WS-GUI] Desktop shell + baseline handshake
  Authority: 05F/05H/PLATFORM_COMPATIBILITY_REGISTRY
  Acceptance: Windows/Linux startup, mismatch fail-closed, clean shutdown
```

进入 M1 后同样直接从 `M1-DATA-* / M1-WORLD-* / M1-MET-* ...` 转换。这样项目计划的“事实源”仍是 SDIB/Canonical，而不是散落在项目管理工具中的临时口头版本。

# 附录 T — 实施证据的最小可追溯元数据

为了使每次 M Review 的证据可长期复查，CI/Golden/Replay/Package 结果至少携带以下元数据：

- `product_build_version` 与 source revision；
- `core_baseline` 与 `BASELINE_LOCK` hash；
- DB schema version；
- P1 Metric Catalog version/hash（适用时）；
- Stage/DTO authority version/hash（适用时）；
- dependency lock hash；
- platform certification profile；
- fixture id/version/input hash；
- command/request hash 与 job identity；
- test/gate id、开始/结束时间和最终状态；
- numeric tolerance/profile hash（适用时）；
- Release identity / replay source Release（适用时）；
- 失败时的受控 reason/error classification。

证据文件本身可以采用 CI 系统或团队批准的格式，但这些关键字段不能只存在于某个人的终端输出或截图中。Milestone 审查应能够从一个 build manifest 追到相应的测试结果、fixture、baseline、package 和 Release provenance。

SDIB-1.1 的最终实施哲学可以概括为：**先把“正确、可追溯、可重放、跨平台一致”做成工程事实，再扩大功能覆盖；先证明一条真实闭环，再批量扩展指标和训练类型。**
