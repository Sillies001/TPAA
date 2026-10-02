# TPAA 产品集成与最终资格化实施基线 PIQB-1.0

**Product Integration & Qualification Baseline — PIQB-1.0**  
**上位系统基线：** TPAA V8.0  
**工程设计基线：** ED-2.0  
**Core Baseline：** CB-1.4.0  
**数据库目标：** schema 1.6.0  
**输入实现状态：** M0～M9 / P1～P6 qualification complete  
**起始 protected-main SHA：** `06945127c86069918ffdfd415201d321d53aae4d`  
**治理 Umbrella：** #206  
**B0 Issue：** #207  
**发布日期：** 2026-10-02

## 1. 基线定位

PIQB-1.0 不定义新的 P 能力，也不创建 M10/P7。它只负责把已经通过治理 Gate 的 M0～M9 / P1～P6 组件收敛为一个真正可安装、可启动、可导入数据、可计算、可持久化、可历史重放、可通过 Desktop/API 使用，并能在 Windows/Linux 上正式资格化的 TPAA 软件产品。

本基线服从 TPAA V8.0、ED-2.0、CB-1.4.0、DB schema 1.6.0 以及所有已冻结 Canonical authority。若产品集成发现 schema 1.6.0 无法合法承载必须持久化的对象，必须 fail closed 并提出独立 Authority Change Proposal；PIQB 不得私建 shadow schema。

## 2. 不可变约束

1. 不修改 116 项 P1 Metric 冻结语义。
2. 不重定义 P1～P6 maturity/claim boundary。
3. 不把 Forecast/Counterfactual 当历史事实。
4. 不把 P6 training advisory 升级为战术/武器/指挥优化。
5. 历史读取禁止 current/latest/default fallback。
6. GUI 不直接写 DB，不重新计算业务产品。
7. API 不绕过 Application Service。
8. Worker 不持有 live Qt/DB connection；Desktop authoritative SQLite write 由 backend 协调。
9. Windows/Linux 共享同一 Domain/Application business core。
10. exact-head Hosted CI remains the merge authority；不得弱化 Ruff/mypy/Golden/Replay/security/fail-closed。

## 3. 最终产品形态

### 3.1 Desktop

```text
PySide6 Desktop
    │
    ▼
Loopback FastAPI Backend
    ├── Application Service
    ├── Job Manager
    ├── Repository / Audit / Admission
    ├── Worker Process Pool
    ├── SQLite WAL
    ├── Local Parquet
    └── Object / Evidence Store
```

### 3.2 Service

```text
Client
  │
FastAPI Service
  ├── Application Service
  ├── Identity / RBAC / Audit
  ├── Job Manager / Worker Pool
  ├── PostgreSQL
  └── Parquet / Object Store
```

Desktop 与 Service 共享 Domain/Application contracts，不按 OS 或部署形态分叉业务语义。

## 4. B0 冻结成果

B0 只冻结产品化目标，不修改 Runtime。机器成果：

- `PRODUCT_COMPONENT_INVENTORY.json` — PIQB-B0-001
- `PRODUCT_RUNTIME_TOPOLOGY.json` — PIQB-B0-002
- `PRODUCT_REPOSITORY_MAPPING.json` — PIQB-B0-003
- `PRODUCT_ADMISSION_MAPPING.json` — PIQB-B0-004
- `PIQB_PRODUCT_GAP_BASELINE.json` — PIQB-B0-005

B0 的任何代码修改只能用于 baseline validation / contract / CI evidence，不能开始 composition、repository 或 runtime wiring。

## 5. Batch 路线

| Batch | Issue | 目标 | Entry |
|---|---:|---|---|
| B0 | #207 | Product topology baseline | M9/P6 final qualification |
| B1 | #208 | Runtime composition closure | B0 protected-main GO |
| B2 | #209 | Persistent repositories and recovery | B1 protected-main GO |
| B3 | #210 | Production data and compute plane | B2 protected-main GO |
| B4 | #211 | Unified API/security/observability | B3 protected-main GO |
| B5 | #212 | Desktop/replay/visualization | B4 protected-main GO |
| B6 | #213 | Final product qualification/release | B5 protected-main GO |

唯一允许的施工顺序：**B0 → B1 → B2 → B3 → B4 → B5 → B6 → PIQB Exit**。

## 6. Batch 0 — Product Topology Baseline

### PIQB-B0-001 Product Component Inventory

冻结当前组件是否存在、是否为 Runtime required、是否要求 persistence、当前是否只是 qualified component，以及目标生产 adapter。不得把“有模块/有 contract test”等价成“已生产装配”。

### PIQB-B0-002 Runtime Topology Authority

冻结当前实际 Desktop M1-only composition 与目标 Desktop/Service process ownership。明确 GUI、Backend、Worker、DB、Parquet/Object、security、shutdown/recovery 边界。

### PIQB-B0-003 Production Repository Mapping

逐产品族冻结 logical object → engine-neutral repository port → SQLite/PostgreSQL adapter → object/Parquet payload 的目标映射。任何无法在 schema 1.6.0 合法实现的对象必须 fail closed。

### PIQB-B0-004 Runtime Admission Mapping

统一 P1～P6 runtime availability 必须来自 exact protected-main qualification evidence。P6 已有 `P6AdmissionEvidence`，所以正式 Runtime 禁止继续以 naked `p6_admitted=True` 作为 trust root。

### PIQB-B0-005 Product Gap Baseline

冻结阻止“组件资格化实现”成为“最终产品”的当前缺口，并把每个缺口绑定到 B1～B6 的唯一施工位置。

## 7. Batch 1 — Runtime Composition Closure

只在 B0 protected-main GO 后启动。

任务范围：
- production Composition Root；
- full Desktop backend；
- unified Desktop transport；
- ProductAdmissionResolver；
- feature availability；
- composition contract tests。

B1 Exit：同一个产品 Runtime 可以解析所有 admitted P1～P6 Application service，且 inactive/unavailable capability 明确 fail closed。

## 8. Batch 2 — Persistent Repository & Recovery

任务范围：
- P2～P6 engine-neutral repository ports；
- SQLite Desktop adapters；
- PostgreSQL Service adapters；
- object/Parquet product store；
- publication transaction/CAS；
- restart durability；
- crash/orphan recovery；
- SQLite/PostgreSQL logical parity。

B2 Exit：正式产品路径不再以 InMemory repository 作为 product authority。

## 9. Batch 3 — Production Data & Compute Plane

任务范围：
- Source Adapter Registry：FLIGHT / MISSION_AVIONICS / TDL / RANGE_ACMI / SCENARIO / AUDIO_VIDEO；
- production import boundary；
- source provenance；
- governed Polars runtime；
- Parquet plane；
- real Job lifecycle；
- real Worker commands；
- resource safety / backpressure / orphan cleanup。

B3 Exit：production import → Worker → Canonical → World → Metric → Release → persistent storage 首次完整闭环。

专有 `.phy` decoder 仅作为 Source Adapter，可独立开发，不得成为 TPAA Core 的隐式依赖。

## 10. Batch 4 — Unified API / Security / Observability

任务范围：
- `create_full_desktop_app()` / `create_full_service_app()`；
- exact-ID product API；
- DTO/OpenAPI/client contract；
- pluggable Identity/Principal Resolver；
- RBAC / separation of duties；
- persistent audit；
- structured logs/readiness/version/worker/storage/product qualification state。

B4 Exit：一个正式 Service process 提供全部 admitted P1～P6 Application API。

## 11. Batch 5 — Desktop / Replay / Visualization

必须把 ED-2.0 的 P01～P13 产品工作流装入真实 Desktop，包括 Session、Evidence/Replay、P4/P5、P2/P3、P6、Data Quality、Governance、Timeline/trajectory、Media/Bookmark/Debrief 和 C/W/P/A/J/M/Assessment/P2-P3/P6 semantic separation。

B5 Exit：用户无需调用 Python 模块即可从 Desktop 完成 P1～P6 浏览、证据下钻、Replay 与 Debrief。

## 12. Batch 6 — Product Qualification & Release

必须新增真正的 Integration/E2E/Recovery/Performance/Packaging product gates，并对以下 profile 正式资格化：

- WINDOWS_DESKTOP_X64
- LINUX_DESKTOP_X64
- WINDOWS_SERVICE_X64
- LINUX_SERVICE_X64

最终必须覆盖 clean install → start → production-format import → compute → publish → P1～P6 read → GUI/replay → shutdown → restart → exact historical replay → export auth → backup/restore。

PIQB Exit review schema：`TPAA_PIQB_EXIT_REVIEW_V1`。

## 13. 测试阶梯

```text
Unit
↓
Contract
↓
Golden
↓
Replay
↓
Integration
↓
E2E
↓
Recovery
↓
Performance
↓
Packaging
↓
Product Qualification
```

14 个 required Hosted CI jobs 的拓扑保持不变；新增 Gate 优先作为现有 job 中的 step/test group。

## 14. Git / PR / Gate discipline

- 一个 coherent sub-batch 完成后再 Run，避免高频 Run。
- candidate exact head 必须 14/14 SUCCESS。
- Ready 前重新核验 head/base/mergeable/behind。
- merge 使用 `expected_head_sha`。
- merge 后验证 actual merge parents。
- protected-main exact push 必须再次 14/14 SUCCESS。
- Batch 只有在 protected-main qualification 后才 COMPLETE。

## 15. B0 Gate

B0 candidate 可以：
- `status=PASS`
- `decision=PENDING_PROTECTED_MAIN`

但不能宣称 B0 complete。

只有：
- event=`push`
- ref=`refs/heads/main`
- exact checked-out revision
- exactly 14/14 SUCCESS
- five B0 artifacts exact-valid
- no Runtime implementation in B0

才允许：
- `decision=GO`
- `product_topology_frozen=true`
- `PIQB_B0_QUALIFIED`

B0 GO 前，#208 B1 不得开始 Runtime 修改。

## 16. PIQB Exit 的最终表述

PIQB Exit GO 前：

> M0～M9 / P1～P6 能力实现与治理资格已经完成，最终产品集成与生产资格化正在进行。

PIQB Exit GO 后才允许：

> TPAA M0～M9 / P1～P6 功能能力已经完成，并已集成为一个通过正式产品资格化的 TPAA 软件产品。
