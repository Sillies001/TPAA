# TPAA G7（V26 单批次发射事件工作台）关闭报告

> **已被复核撤销（2026-11-08）：** 本报告不再构成 G7 当前关闭依据；见 `G6_G12_POST_CLOSURE_REVIEW_SUPERSESSION_2026-11-08.md`。

> 日期：2026-11-07（本地）· 分支 `codex/v33-g1-handoff-20261106` · HEAD `e0a9677…`
> 判定：**G7 = CLOSED_LOCAL_WITH_GATES**（101 安全路由；V26 视觉证据 12 张；盒模型无重叠）
> 边界：未 push/未部署/未 release claim；W9 `NO_GO`；CB-1.11.0 及此前基线字节不变。
> 证据：`evidence/gui-g7-v33-closure.json`、`evidence/gui-g7-v33-webengine.json` + `evidence/gui-g7-v33-webengine/*.png`。

## 交付

1. **CB-1.12.0 不可变后继**（`tools/baseline/adopt_g7_successor.py`，`--check` PASS）：激活 `gui.batch.events`=`api.route.101` GET `/api/v1/gui/batches/{batch_id}/weapon-events`（`DERIVED_DATA_READ`+`weapon_event.read`，ALWAYS 审计）；`gui.replay` 保持 `RESERVED_G7_NOT_EXPOSED`；DTO 契约 additive 扩展 `WeaponEventListItemDTO`（+batch_id/t1/射手/目标/episode/三维状态/分类例外）并新增 `BatchEventWorkbenchDTO`；`GUI_BATCH_EVENTS_AUTHORITY` + G7 approval；DB 1.10.0 无迁移；55 受控工件。
2. **后端全链路**：`tpaa_application/batch_events.py`（唯一 owner：精确批次 workset、类别/裁决/Cluster 筛选、按 t1 排序、opaque checksum 游标分页、未知批次 404、非法筛选 422、越界/篡改游标 400）；`batch_events_application.py`（四态）；`tpaa_runtime/durable_batch_events.py`（WEAPON_EVENT/ATTACK_CLUSTER 关系读取，jsonb TEXT 解析）；`tpaa_api/gui_batch_events.py`（has_batch_events 守卫）；`ApplicationService.batch_events()`；`g7_activation`；`production.py` g7_active 接线；`gui_capabilities` +G7；g5/g6 激活门 lineage 扩至 CB-1.12.0；bootstrap/loader 信任锚（lock `387fe31e…`，55 工件，lineage 含 CB-1.11.0）。
3. **前端 V26**：批次选择 + 类别/裁决筛选 + Context 管理入口（V23）；概况统计（随筛选变化）；发射时间线（按 t1 定位、齐射独立、Cluster 徽标）；事件清单（分页"加载更多"、复盘 deep-link 入口至 V04/V05/V06）；未发射行为诚实 N_A（G10 来源矩阵准入）；CSP 合规。
4. **视觉证据**：`tools/gui/g7_webengine_acceptance.py`（CB-1.12.0 激活 + 6 WE 含齐射 Cluster 种子）；12 张截图（1600×900/1280×720 × 三主题 × Ribbon 两态）盒模型无重叠；主题经 V25 应用内通路。
5. **codegen**：`tools/codegen/g7_batch_events_generate.py`（authority/gateway/TS/manifest 4 产物，`--check` 零漂移）；security/gateway 翻转至 `generated_g7_*`；前端 bootstrap `CB-1.12.0:1.0.0`（G2 令牌同步）。

## 门禁实测

g5/g6/g7 关闭器复验 PASS（99/100/101 路由）；四代 successor + 四代 codegen `--check` 全 PASS；ruff PASS；mypy 608 文件 PASS；pytest gui_v33 契约 46 passed、application 169 passed（含 7 项 G7 领域退出门）、unit/api+runtime 199 passed（唯一失败为已记录缺口的 C5 installed-desktop e2e，HEAD 纯净副本同样失败，与 G7 无关）；前端 typecheck/build PASS。

## 声明与复验

未提交、未 push、未部署；`stash@{0}` 未触碰。复验命令：`python tools/gui/g7_v33_close.py` + 关闭报告 G6 同款全套（见 `docs/reviews/G6_V33_HISTORICAL_OVERVIEW_CLOSURE_2026-11-07.md` §3，外加 `adopt_g7_successor.py --check` 与 `g7_batch_events_generate.py --check`）。已知缺口：C5 e2e 环境问题（见 handoff）。G8 起步：专项页双视角/V24/独立窗口（复用 G5 window/perspective owner）。
