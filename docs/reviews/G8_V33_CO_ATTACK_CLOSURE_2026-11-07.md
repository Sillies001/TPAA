# TPAA G8（专项页双视角、V24 与独立事件窗口）关闭报告

> **已被复核撤销（2026-11-08）：** 本报告不再构成 G8 当前关闭依据；见 `G6_G12_POST_CLOSURE_REVIEW_SUPERSESSION_2026-11-08.md`。

> 日期：2026-11-07（本地）· 分支 `codex/v33-g1-handoff-20261106` · HEAD `e0a9677…`
> 判定：**G8 = CLOSED_LOCAL_WITH_GATES**（102 安全路由；V24 视觉证据 12 张；盒模型无重叠）
> 边界：未 push/未部署/未 release claim；W9 `NO_GO`；CB-1.12.0 及此前基线字节不变。
> 证据：`evidence/gui-g8-v33-closure.json`、`evidence/gui-g8-v33-webengine.json` + `*.png`。

## 交付
1. **CB-1.13.0 后继**（lock `69ba7e44…`，57 工件）：激活 `gui.coattack`=`api.route.102`（BVR-only；Strike 簇/跨批次簇 fail-closed；缺上下文诚实空编队；不形成总分）；新增 `CoAttackAnalysisDTO`；`BatchEventWorkbenchDTO` additive +`batch_context_id`；`gui.replay` 保持 `RESERVED_G8_NOT_EXPOSED`。
2. **后端**：`co_attack.py` 唯一 owner + 应用服务 + `durable_co_attack.py` + API + `g8_activation` + production；g5/g6/g7 门 lineage 扩至 CB-1.13.0；bootstrap/loader 信任锚。
3. **前端**：V04/V05/V06/V08/V20/V21 专项页（双视角切换、STRIKE 仅射手侧、观察窗口事实、G9 回放 N_A）；V24 协同攻击分析页；V08 受控入口由真实 cluster+context+release grant 进入。
4. **缺陷修复**：SQLite busy timeout 0→30s（WAL 并发审计写误判 "database is locked"）；V24 grant releaseId 赋值顺序；`enterV24FromV08` 未触发 `loadCoAttack`；验收工具 SPA 会话重排（resize 不重置页面状态，二次分辨率直接复用会话重进入 V24）。
5. **视觉证据**：`tools/gui/g8_webengine_acceptance.py` PASS（12 captures，V08→V24 受控进入，主题经 V25 应用内通路）。

## 门禁
ruff PASS；mypy 621 文件 PASS；g8 successor/codegen `--check` PASS；契约 55 + G8 领域/API 9 全过；前端 typecheck/build PASS；全量 api/runtime/application 336 passed（唯一失败为已记录缺口的 C5 installed-desktop e2e）。复验：`python tools/gui/g8_v33_close.py`。

## 声明
未提交、未 push、未部署；W9 NO_GO。G9 起步见 handoff。
