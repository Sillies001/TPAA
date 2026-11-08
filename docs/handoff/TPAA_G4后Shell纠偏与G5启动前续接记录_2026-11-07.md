# TPAA G4 关闭后 · 共享 Shell 纠偏增量与 G5 启动前续接记录

> 日期：2026-11-07（G4 关闭后的同日纠偏增量，非新 G 阶段）
> 分支：`codex/v33-g1-handoff-20261106` · HEAD：`e0a9677090ea6249c4883e6d503035aea9cd801a`（未提交工作树为事实来源）
> 阶段状态：`G0R～G4=CLOSED_LOCAL_WITH_GATES`（不变）；`G5～G12=NOT_STARTED`
> 边界：未推送、未生产部署、未声明发布就绪；既有 `stash@{0}: pre-g2-sync-local-web-dist-2026-11-06` 未改动。

## 本增量完成内容（G4 关闭后纠偏，G5 前置）

按 `docs/reviews/G4_POST_CLOSURE_GUI_FIDELITY_AUDIT_2026-11-07.md` 的差距清单，完成共享 Shell/Ribbon/三主题/公共组件整改：

- **关键约束**：生产 WebEngine CSP `style-src 'self'`（`src/tpaa_api/desktop.py:228`）禁止内联 `style` 属性；整改采用「`data-*` + 渲染后 CSSOM 应用」，**未放宽 CSP**。
- 前端新增/重写：`frontend/gui-v33/src/{style.css,themes.ts,icons.ts,shell.ts,charts.ts,main.ts}`。
- G4 验收 DOM 契约完整保留（`.ticket-card`/`.revision-panel`/`.state-pill`/`.state-ready` 等，已在构建产物逐项核对）。
- v33 Demo 与用户工作区镜像 SHA-256 一致（`7aa5ff43…2401a9a`），未发生需同步的受控变更。

## 验证结果（本增量）

- Ruff 通过；Mypy 573 源文件零错误。
- GUI 契约测试 29/29；网关 node 测试 7/7；GUI/API 单测 67/67。
- `vite build` 通过；`main.ts` 内联 `style="..."` 计数为 0。
- 真实 WebEngine 截图证据：`evidence/shell-fidelity/`（6 张：V01 展开/收起、V25 三主题、V26），Shell 结构/三主题/分组 Ribbon/画布缩放/fail-closed 均与 Demo 一致。

## 开放门禁 / 已知事项

- 共享 Shell 全视觉矩阵（26×3×Ribbon×分辨率）归 G12；逐页 Demo 对照随 G6～G10 同步。
- G4 WebEngine 完整验收闭环（写库路径）在本机后端子进程/SQLite 间歇不稳定（后端侧，与前端无关）；既有 `-100/-150` 证据仍有效。建议稳定环境重跑，非本增量阻塞项。

## G5 启动前复验命令

```bash
export POLARS_SKIP_CPU_CHECK=1
export UV_CACHE_DIR="$PWD/.tmp/uv-cache"
python tools/baseline/adopt_g4_successor.py --check
python tools/codegen/g4_batch_generate.py --check
python -m ruff check src tests tools migrations
python tools/dev/tpaa_dev.py typecheck
python tools/gui/g4_v33_close.py            # 预期 CLOSED_LOCAL_WITH_GATES
python -m pytest tests/contract/gui_v33/ -q  # 预期 29 passed
cd frontend/gui-v33 && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vite build --emptyOutDir
```

## G5 范围提示（严格按实施方案 §14 G5 / §9）

唯一 owner：WE detector、identity/linker、category、cluster、window resolver、perspective projection；重叠窗口；状态分离（terminal/adjudication/window 独立）；Golden fixtures；必要 migration/backfill。退出门：一发一 WE、齐射多 WE+Cluster、Episode 多/交错 WE、缺 P/A/J/T2、clock reset/gap/alignment 正负用例。建立 CB-1.10.0 后继机器权威后，才允许注册暴露 G5 路由（当前 6 条仍为 `RESERVED_G4_NOT_EXPOSED`）。
