# TPAA G11（性能/安全/可访问性/跨平台硬化）关闭报告

> **已被复核撤销（2026-11-08）：** 安装包、Linux/Service、SBOM/许可证/漏洞和目标 workload 门未完成，本报告不再构成 G11 当前关闭依据。见 `G6_G12_POST_CLOSURE_REVIEW_SUPERSESSION_2026-11-08.md`。

> 日期：2026-11-07（本地）· 分支 `codex/v33-g1-handoff-20261106` · HEAD `e0a9677…`
> 判定：**G11 = CLOSED_LOCAL_WITH_GATES**（安全路由稳定 103；硬化检查 23 项全过）
> 边界：未 push/未部署/未 release claim；W9 `NO_GO`；CB-1.15.0 及此前基线字节不变。
> 证据：`evidence/gui-g11-v33-closure.json`、`evidence/gui-g11-v33-hardening.json`。

## 交付
1. **CB-1.16.0 后继**（lock `69798bcf…`，65 工件，路由稳定 103）：`GUI_HARDENING_AUTHORITY`（csp_self_only/exact_origin_loopback/desktop_nonce_enforced/off_the_record/no_orphan/renderer_crash_fail_closed/wcag_keyboard_focus/chinese_copy_complete）+ `G11_HARDENING_APPROVAL`。
2. **真实硬化增量**：`/ui` 静态响应新增 `frame-ancestors 'self'` 与 `Cache-Control: private, no-store`（CSP/nosniff/referrer 既有）；g10 激活门 lineage 扩至 CB-1.16.0；bootstrap/loader 信任锚。
3. **g11_hardening_acceptance.py（23 项全过）**：CSP 头（default/script/style 'self'、frame-ancestors、nosniff、no-store）、错 token/nonce 拒绝（401/403）、html lang=zh、skip-link→#main-content、main aria-label/tabindex、可聚焦控件、Ribbon aria-expanded、中文文案、off-the-record、loopback exact origin、renderer 降级 fail-closed、后端关闭终态且无孤儿进程（GetExitCodeProcess 判定）。
4. **契约**：`test_g11_v33_hardening_contract.py`（后继/authority 规则/静态头源码断言）。

## 门禁与已知缺口
ruff PASS；mypy 638 文件 PASS；g11 successor `--check` PASS；契约+application 190 passed；前端 build PASS；`g11_v33_close.py` PASS。
- 既有缺口：C5 installed-desktop e2e（P3_TWIN 对象缺失）仍未独立排查，安装包 smoke 因此顺延（G12 前必须解决）。
- Linux profile / SBOM / 目标 workload 压测需 Linux 环境与打包流水线，本机仅完成 Windows Desktop 侧证据，记入 G12 外部门清单。

## 声明
未提交、未 push、未部署；W9 NO_GO。剩余：G12（设计封版/全量资格/切换；含 C5 缺口处理、Linux/安装包 smoke、26×3×Ribbon 两态全量视觉）。
