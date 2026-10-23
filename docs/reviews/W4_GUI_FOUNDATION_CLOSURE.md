# W4 GUI 产品壳与设计系统关闭评审

日期：2026-10-23
结论：`CLOSED_LOCAL / PASS / NOT_PUSHED / NOT_DEPLOYED / NOT_PRODUCTION_READY`

## 1. 关闭范围

W4 按 05G R3.3 设计权威完成 GUI 基础层整改：

- 建立独立的 P01～P13 后继页面合同，纠正早期 PIQB B5 页面编号和语义漂移，同时保留历史冻结基线不被改写；
- 建立全局 `ApplicationShellState`，以 Session、Episode、Stage、Context、时间范围、对象和 Release 精确身份驱动共享选择；
- 正式产品壳改为 Mission Header、主导航、可滚动工作区、Detail & Evidence Drawer、状态栏的五区结构；
- 提供 Light、Dark、High Contrast 主题，DPI token、通用表格/表单/Empty/Error/Loading 组件、平台原生图标和 accessibility 名称；
- 正式产品组合不再实例化 synthetic fixture 控件；资格化直达入口仍保留夹具能力；
- 修复 M1 Session Browser 行距/行高和 P08（原界面 P06）Association contribution 默认列宽。

## 2. 用户已报告缺陷

| 缺陷 | 整改 | 关闭证据 |
|---|---|---|
| M1 Session Browser 行间距过小、控件显示不全 | Grid margin/spacing、32 px 最小行高、30 px 输入高度；页面外层统一可滚动 | `test_m1_qualification_form_rows_have_readable_spacing` |
| Association contribution 默认列宽过小 | 第二列默认 240 px、最小 section 120 px、末列 stretch、32 px 行高 | P08 视觉基线及对象断言 |
| 正式 GUI 是工程诊断壳且页面语义错误 | 正式 Desktop 入口切换为 05G P01～P13 五区产品壳 | UI automation 与页面合同测试 |

## 3. 跨平台和 DPI 证据

- Windows/Python 3.13.5/PySide6 6.11.2：真实后端 + 离屏 Desktop 自动化通过；100%、125%、150%、200% DPI 生成 P01/P08/P12 三种 viewport 证据；
- Linux/Python 3.13.5/PySide6 Essentials 6.11.2：Docker 只读挂载仓库，W4 专项 `6 PASS`，200% DPI 的 1024×720、1440×900、1920×1080 三种 viewport 均成功捕获；
- Windows 96 DPI 基线 PNG 及 SHA-256 manifest 纳入版本控制；Linux/Windows CI 增加同一对象与视觉证据步骤。

## 4. 回归门禁

正式关闭要求以下门禁全部为零失败：

- W4 GUI 专项与页面合同；
- 真实 Desktop UI automation；
- 全量 Ruff、mypy 和 `compileall`；
- 全量 unit、contract 与适量 integration/E2E；
- 干净工作树开发打包，且 clean-tree 门禁不得放宽。

最终命令结果和候选包散列在本地关闭提交后的复验记录中确认；机器可读符合性见 `docs/compliance/W4_COMPLIANCE_MATRIX.json`。

## 5. 明确未关闭事项

W4 的“正式关闭”只表示 GUI 基础层退出门通过，不表示整个应用生产可用：

- W5 仍需完成 P01～P03、P12、P13 真实用户闭环；
- W6 仍需完成 P04～P10 Assessment/Capability/Longitudinal 工作流；
- W7 仍需完成 P11 计划与插件运行时；
- 生产身份设施、真实业务数据验收、保护分支 CI、签名发布和生产部署均未执行。

因此不得将本结论解释为生产投用批准。
