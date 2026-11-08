# TPAA G6（V01 历史聚合）关闭报告：GUI 产品化重构与后端/设计同步整改

> **已被复核撤销（2026-11-08）：** 本报告不再构成 G6 当前关闭依据；见 `G6_G12_POST_CLOSURE_REVIEW_SUPERSESSION_2026-11-08.md`。

> 日期：2026-11-07（本地）
> 分支：`codex/v33-g1-handoff-20261106` · HEAD：`e0a9677090ea6249c4883e6d503035aea9cd801a`（未提交工作树为事实来源）
> 判定：**G6 = CLOSED_LOCAL_WITH_GATES**（100 安全路由；WebEngine 视觉证据 12 张全过；盒模型无重叠）
> 边界：未 push、未生产部署、未 release claim；W9 保持 `NO_GO`；CB-1.10.0 及此前基线字节不变（`adopt_g4/g5_successor --check` PASS）。
> 证据：`evidence/gui-g6-v33-closure.json`（本关闭器生成）、`evidence/gui-g6-v33-webengine.json` + `evidence/gui-g6-v33-webengine/*.png`（12 张）。

---

## 1. 本阶段完成内容（G6 剩余三项，严格按序）

### 1.1 CB-1.11.0 运行时激活（Machine Authority First 的直接后继链）

| 工件 | 说明 |
|---|---|
| `tools/codegen/g6_historical_generate.py` | 新增 G6 生成器；`--check` 零漂移。产物 4 件：`src/tpaa_security/generated_g6_authority.py`（**100 路由**，CB-1.11.0）、`src/tpaa_application/generated_g6_gateway.py`（catalog_version `CB-1.11.0:1.0.0`）、`frontend/gui-v33/src/generated/g6-historical.ts`（4 个 G6 DTO + `G6_HISTORICAL_ROUTES` + authority）、`generated/g6-cb-1.11.0/manifest.json` |
| 翻转 | `tpaa_security/api.py`、`tpaa_security/gui_authority.py` → `generated_g6_authority`；`tpaa_application/gui_gateway.py` → `generated_g6_gateway`；`tpaa_api/gui_gateway.py`、`gui_weapon_event.py` 错误 provenance → CB-1.11.0（与 `gui_historical.py` 一致） |
| 存储信任锚 | `tpaa_storage/bootstrap.py`：`_TRUSTED_BASELINE_PINS[CB-1.11.0]`（lock `7b8783bd…59150515`，53 受控工件，DB 1.10.0）；`_COMPATIBLE_SCHEMA_LOCKS[CB-1.11.0]=(G6 lock, G5 lock)`，CB-1.10.0 纳入 lineage，数据根无迁移复用 |
| 加载器 | `tpaa_canonical/loader.py` + `__init__.py`：`G6_LOCAL_*` 针（lock sha + 工件数）进 `trusted_loader_for_baseline` |
| authority_root | 运行时激活经 `TPAA_AUTHORITY_ROOT` 指向 `baseline/CB-1.11.0/canonical`（与 G5 激活 CB-1.10.0 同模式；默认产品入口 CB-1.5.0 不变，`test_production_entry_config.py` 不受影响）。G6 WebEngine 验收工具显式设置并断言 bootstrap provenance `core_baseline=CB-1.11.0` |
| 激活门修正 | `g5_activation.validate_g5_activation` 接受 CB-1.11.0 后继 lineage（G5 设计原则"叠加层非替换"：`CB-1.11.0` 保留全部 G5 路由不变）；新增后继 lineage 单测 |
| 前端 bootstrap | `main.ts` 契约/权限 JSON 指向 CB-1.11.0；校验 `provenance.core_baseline=="CB-1.11.0"`、`catalog_version=="CB-1.11.0:1.0.0"`；G2 契约令牌同步（`test_g2_v33_shell_contract.py`） |

### 1.2 前端 V01 页（v29 markup 复刻 v33 Demo overviewMarkup）

- 完整结构：`v29Header`（训练总览 + 副题 + 起始/结束日期 + 机型 + 训练类型筛选 + V09/V16 入口 + 日期无效警告）、`v29Kpis` 六卡、`v29RowFirst`（任务级指标趋势 + 历史训练活动趋势）、`v29RowSecond`（训练结果与裁决状态趋势 + 训练行为类别构成 + 装备性能历史趋势）、`v29RowBottom`（历史训练批次列表 + 选中批次摘要）、`v29Footer`。
- 数据经生成式 `g6-historical.ts` client（`gateway.ts` 新增 `historicalOverview()`）消费真实 `gui.overview`（`api.route.100`）。
- 诚实口径：任务指标标"演示口径 · 未准入"（Metric Authority 未准入，后端诚实返回空）；装备指标未准入 → EMPTY；行为类别只给跨批次合计（细分属 V26）；无数据诚实 EMPTY，不合成。
- CSP 合规：图例色点/条形宽度经 `data-*` + 渲染后 CSSOM 应用，无内联 style。
- 修复既有缺陷：`durable_historical_overview._properties` 现按 G5 适配器同款方式解析 SQLite jsonb TEXT（此前真实库 WE 计数恒为 0），新增回归测试 `tests/unit/runtime/test_g6_durable_historical_overview.py`。

### 1.3 视觉证据（V01 Demo 对照截图矩阵）

- `tools/gui/g6_webengine_acceptance.py`：真实 Windows WebEngine + 本地后端（CB-1.11.0 激活、3 个 QUALIFIED 批次、5 条 WEAPON_EVENT 关系种子）。
- 矩阵：1600×900、1280×720 × graphite/tactical/light × Ribbon 展开/收起 = **12 张**（`evidence/gui-g6-v33-webengine/`）。
- 每帧盒模型检查（`.v29Kpi`/`.v29Panel` 两两不相交、无画布溢出）+ 内容断言（6 KPI、3 批次行、2 条活动折线、2 条裁决条、标题"训练总览"）全 PASS。
- 主题切换经应用自身 V25 通路（状态一致，页脚标签同步）。

---

## 2. 阶段状态总览

| 阶段 | 状态 | 关闭证据 |
|---|---|---|
| G0R–G4 | CLOSED_LOCAL_WITH_GATES | `docs/reviews/G4_*`、`evidence/gui-g4-v33-closure.json` |
| G5 | CLOSED_LOCAL_WITH_GATES（本次复验无回归：99 路由 PASS） | `docs/reviews/G5_V33_WEAPON_EVENT_WINDOW_PERSPECTIVE_CLOSURE_2026-11-07.md`、`evidence/gui-g5-v33-closure.json` |
| **G6** | **CLOSED_LOCAL_WITH_GATES** | **本报告、`evidence/gui-g6-v33-closure.json`、`evidence/gui-g6-v33-webengine*.json/png`** |
| G7–G12 | NOT_STARTED | gui.batch.events（G7）、gui.replay（G9）保持 `RESERVED_G6_NOT_EXPOSED` |

## 3. 全量门禁结果（本机关闭时实测）

```bash
export POLARS_SKIP_CPU_CHECK=1; export UV_CACHE_DIR="$PWD/.tmp/uv-cache"
python tools/gui/g5_v33_close.py                      # PASS CLOSED_LOCAL_WITH_GATES routes=99（无回归）
python tools/gui/g6_v33_close.py                      # PASS CLOSED_LOCAL_WITH_GATES routes=100 captures=12
python tools/baseline/adopt_g4_successor.py --check   # PASS
python tools/baseline/adopt_g5_successor.py --check   # PASS digest=e20b1356…
python tools/baseline/adopt_g6_successor.py --check   # PASS digest=c05620cf…
python tools/codegen/g4_batch_generate.py --check     # PASS routes=7 security_routes=96（零漂移）
python tools/codegen/g5_weapon_event_generate.py --check  # PASS routes=3 security_routes=99（零漂移）
python tools/codegen/g6_historical_generate.py --check    # PASS routes=1 security_routes=100 files=3（零漂移）
python -m ruff check src tests tools migrations       # PASS
python tools/dev/tpaa_dev.py typecheck                # PASS 599 source files
python -m pytest tests/contract/gui_v33/ tests/unit/application/ -q --basetemp .tmp/pytest   # 162 passed
python -m pytest tests/unit/api/ tests/unit/runtime/ -q --basetemp .tmp/pytest              # 195 passed, 1 failed（见 §5）
cd frontend/gui-v33 && npm run typecheck && npm run build                                   # PASS（web_dist 已同步）
python tools/gui/g6_webengine_acceptance.py           # PASS captures=12 box_model_no_overlap=True
```

## 4. 新增/修改清单（本阶段）

- 新增：`tools/codegen/g6_historical_generate.py`、`tools/gui/g6_webengine_acceptance.py`、`tools/gui/g6_v33_close.py`、`src/tpaa_security/generated_g6_authority.py`、`src/tpaa_application/generated_g6_gateway.py`、`frontend/gui-v33/src/generated/g6-historical.ts`、`generated/g6-cb-1.11.0/manifest.json`、`tests/unit/api/test_g6_gui_historical_api.py`（4 项，含 403 负测/反向日期/422）、`tests/unit/runtime/test_g6_durable_historical_overview.py`。
- 修改：`src/tpaa_security/api.py`、`gui_authority.py`、`src/tpaa_application/gui_gateway.py`、`src/tpaa_api/gui_gateway.py`、`gui_weapon_event.py`、`src/tpaa_storage/bootstrap.py`、`src/tpaa_canonical/loader.py`、`__init__.py`、`src/tpaa_runtime/g5_activation.py`、`durable_historical_overview.py`、`frontend/gui-v33/src/main.ts`、`services/gateway.ts`、`style.css`、G2/G3/G5 既有测试令牌与断言（受控后继更新）。
- 基线字节不变：CB-1.5.0～CB-1.10.0 未触碰；CB-1.11.0 为 adopt 工具产物，`--check` 稳定。

## 5. 未过门禁与说明

1. `tests/unit/runtime/test_prcb_c5_installed_desktop_e2e.py`（installed-desktop P1–P6 e2e）在本机失败：`PRCB_C5_API_EXACT_READ_FAILED:P3_TWIN:422 object missing: tpaa-object://p3-capability/models/454a0bf9…json`。**已用 `git archive HEAD` 纯净副本复现同样失败**，判定为与 G6 无关的本机环境既有问题（G6 全部改动对 CB-1.5.0 默认组成是惰性的）。不在本阶段修复，留待独立排查。
2. W9 最终资格：保持 `NO_GO`（`restrictions.release_claim=false`，各 approval restrictions 未变）。
3. PRODUCT_COMPLETE ≠ RELEASE_READY：本次为本地关闭，不构成发布声明。

## 6. 声明

- 工作树**未提交**（保持接手时状态事实来源）；**未 push、未 pull/merge、未生产部署**；`stash@{0}=pre-g2-sync-local-web-dist-2026-11-06` 未触碰；远端 ahead 5 保持原状。
- 全程未执行任何 git 写操作。

## 7. 复验命令（供逐阶段审计）

按 §3 顺序执行即可完整复验；另可参考 `docs/handoff/TPAA_G6续接记录_2026-11-07.md` 的续接与 G7 起步清单。
