# TPAA G2 阶段 GitHub 续接记录

- 日期：2026-11-06
- 仓库：`Sillies001/TPAA`
- 工作分支：`codex/v33-g1-handoff-20261106`
- G2 开工基线：`b92229da8dcc23f433ab7fc87f7210adbf32485e`
- G2 当前代码快照（修复 TypeScript TS18047）：`4b5e51f2abfc3aaea63c287a94d26a4b092f3155`
- 当前阶段：`G2=IN_PROGRESS`
- 前置阶段：`G0R=CLOSED_LOCAL_WITH_GATES`，`G1=CLOSED_LOCAL_WITH_GATES`
- 后续阶段：`G3～G12=NOT_STARTED`

## 本轮变更

G2 已建立 v33 产品 Shell 的源代码框架：五模块 Ribbon、25 个常规视图导航、machine-authority 驱动的 view contract / permission checks、V24 双端直接访问拒绝、三主题、共享导航/领域/回放/呈现状态、会话权限读取和无假数据状态面板。

本轮没有重建 `src/tpaa_gui/web_dist`。必须在原 Windows 工作空间使用锁定的 Node 依赖执行 Vite 构建，不能手工伪造 dist 或修改 G1 确定性构建门禁。

## 下一步必须执行

确认工作区没有其他未提交更改、且本地已快进到本记录对应提交后，在仓库根目录：

```powershell
$env:POLARS_SKIP_CPU_CHECK='1'
Push-Location frontend/gui-v33
npm ci
npm run typecheck
npm run build
Pop-Location

python tools/gui/g1_frontend_build.py
python tools/gui/g2_v33_verify.py
python -m ruff check src/tpaa_api/desktop.py tests/contract/gui_v33/test_g2_v33_shell_contract.py tests/unit/api/test_g2_v33_conditional_view_guard.py tools/gui/g2_v33_verify.py
python tools/dev/tpaa_dev.py typecheck
python -m pytest tests/contract/gui_v33/test_g2_v33_shell_contract.py tests/unit/api/test_g2_v33_conditional_view_guard.py -q

python tools/gui/g0r_v33_verify.py
python tools/baseline/adopt_g1_successor.py --check
python tools/codegen/g1_generate.py --check
python tools/gui/g1_v33_verify.py
```

随后在 Windows 本机执行 `python tools/gui/g1_webengine_smoke.py`，并对三主题、Ribbon 两态、V24 非法直达、键盘焦点和 DPI 布局进行实机检查。

## 未关闭门禁

- Vite typecheck / build / web_dist 同步；
- Python Ruff / pytest；
- G0R/G1 复验脚本本机执行；
- WebEngine 实机与视觉检查；
- 实际桌面 principal / permission matrix 评审。

在这些门禁通过前，不得将 G2 标记为 `CLOSED_LOCAL_WITH_GATES`，不得启动 G3，不得修改默认/保护分支，不得部署或发布。
