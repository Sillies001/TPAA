# W4 GUI 基础运行与复验

## 范围

本说明只覆盖 W4 产品壳、设计系统、页面对象合同和布局复验。它不表示 P01～P13 的全部业务工作流已经达到生产可用；页面工作流分别由 W5～W7 继续完成。

## Windows 本地复验

在仓库根目录进入冻结的 Python 3.13.5 环境后运行：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -p no:cacheprovider tests/unit/gui/test_w4_gui_foundation.py -q
python tools/gui/automation_smoke.py --timeout 30
python tools/gui/w4_visual_regression.py --output-dir build/w4-visual/windows --dpi 192
```

人工窗口复验使用：

```powershell
python -m tpaa_desktop
```

检查 P01～P13 导航、Mission Header、三栏分隔器、详情/证据抽屉、底部状态栏；重点检查 P08 表格列标题和最小窗口滚动行为。

## Linux 隔离复验

```powershell
docker build --file tools/gui/Dockerfile.w4-linux --tag tpaa-w4-linux:py313 .
$repo=(Get-Location).Path
docker run --rm --mount "type=bind,source=$repo,target=/workspace,readonly" --env PYTHONPATH=/workspace/src:/workspace tpaa-w4-linux:py313 sh -lc "python -m pytest -p no:cacheprovider tests/unit/gui/test_w4_gui_foundation.py -q && python tools/gui/w4_visual_regression.py --output-dir /tmp/w4-linux --dpi 192"
```

仓库以只读方式挂载；截图只写入一次性容器 `/tmp`。本地镜像不是部署镜像，不得推送到镜像仓库或用于生产运行。

## 失败关闭

- P01～P13 编号、标题或语义漂移：`W4_PAGE_*`；
- Episode 没有 Session、Stage 没有 Episode、Context 版本没有精确 ID：`W4_*_REQUIRES_*`；
- 时间范围不完整或非法：`W4_TIME_RANGE_*`；
- 正式产品树出现 `tpaaM1FixtureSelector`：对象测试失败；
- 视觉基线 PNG 与 manifest SHA-256 不一致：视觉基线测试失败。

## 生产边界

W4 只在本地关闭。禁止推送、生产部署、发布签名或把开发截图当作业务验收证据。真实业务数据导入、页面端到端流程、角色化交互和生产部署仍受后续阶段门禁约束。
