# TPAA 生产运行闭环整改基线 PRCB-1.0

## 1. 权威与目的

PRCB-1.0 从 PIQB-1.0 正式资格化的 protected-main `0ed48a85944699e0bbac1fe76b84c88a319121c1` 启动。PIQB-1.0 / TPAA 1.0.0 的历史资格结论保持不可变；本基线不新增 M10/P7，而是把已经实现并分别资格化的组件真正装配为生产运行链，目标版本为 TPAA 1.0.1。

## 2. 核心问题

当前主要缺口不是 Domain/Canonical/DTO/DB schema 缺失，而是 production composition 尚未把 durable repositories、production ingest、DurableJobControl、Spawn Worker、persistent audit、dependency readiness、backup/recovery 和 Desktop discovery 贯通。PRCB 明确规定：组件级 PASS 的 evidence aggregation 不能替代 installed-package end-to-end production-chain proof。

## 3. 施工批次

- **C0**：治理冻结与 acceptance contract。
- **C1**：Production composition + durable repository wiring。
- **C2**：Production ingest + durable jobs + governed worker domain execution。
- **C3**：Identity / readiness / persistent audit / backup & recovery。
- **C4**：Desktop immutable discovery + release-bound visualization。
- **C5**：四 profile installed-package E2E、跨平台逻辑等价、detached qualification attestation、TPAA 1.0.1 final qualification。

每个批次只在 coherent batch 完成后触发 Hosted CI，避免琐碎高频 Run。

## 4. 强制不变量

1. Remote GitHub 是唯一事实源；merge 前必须重新读取 exact head。
2. Hosted CI exact-head PASS 是唯一 merge authority。
3. 保持现有 14 required jobs，不增加第 15 个 required job。
4. 不弱化 Ruff、mypy、unit、contract、integration/E2E、architecture、recovery、security gate。
5. 不 force push。
6. 不用 InMemory repository 作为正式产品 authority。
7. 正式安装包不得依赖 `tests/fixtures`。
8. 禁止 mutable-latest fallback；Desktop discovery 最终仍绑定 exact immutable IDs。
9. DB authority 维持 1.9.0；如确需变更，必须单独 Authority Change Proposal。
10. TPAA 1.0.1 final qualification 必须由 immutable package hashes + detached protected-main attestation 共同形成。

## 5. 最终判据

仅当安装后的 Windows/Linux Desktop/Service 均能完成 production-format import → durable job → governed worker → Canonical → World → Metric → P1-P6 → durable DB/object persistence → API/Desktop exact reads → restart/historical replay → backup/restore → persistent audit，并且 exact-head protected-main 14/14 PASS，才能宣告 PRCB-1.0 COMPLETE / TPAA 1.0.1 QUALIFIED。
