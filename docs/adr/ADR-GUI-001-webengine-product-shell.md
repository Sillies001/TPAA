# ADR-GUI-001：GUI 产品壳采用 Qt WebEngine，本地 QML 保留为降级路线

- 状态：`APPROVED_LOCAL`
- 日期：2026-11-06（v33 修订）
- 决策范围：G0R～G12 GUI 产品化波次
- 依据：`GUI-DEMO-V33-2026-11-05`、V01/V04/V08/V26 双路线技术样板

## 背景

目标界面源自高密度 HTML/CSS/SVG Demo。现有 QWidget 页面无法在布局、Ribbon、主题、图表和交互上达到目标。PySide6 6.11.2 同时具备 Qt WebEngine 与 Qt Quick/QML 能力，因此必须在大规模页面开发前决定呈现运行时，同时保持 Application、API、DTO、状态与权限边界不依赖具体 UI 技术。

## 决策

生产候选首选“PySide6 宿主 + `QWebEngineView` + 同进程受控本地 HTTP 后端 + 模块化静态前端”。QML 样板保留为当 WebEngine 在目标环境的安全、离线、性能或打包门失败时的替代呈现层，不保留两套业务实现。

首选路线必须同时满足：

1. 只允许 `http://127.0.0.1:<owned-random-port>` 精确 origin；禁止通配 host、端口和 scheme。
2. 使用 off-the-record `QWebEngineProfile`；禁止持久 Cookie、磁盘缓存、密码库、Service Worker、任意下载和远程调试。
3. `QWebEngineUrlRequestInterceptor` 只对精确 origin 注入短期 Bearer 与 Desktop nonce；JavaScript 不得读取 token 或 nonce。
4. 顶层导航和静态资源也必须通过 Desktop 身份门；unsafe method 还需精确 Origin、自定义头和 Desktop nonce。
5. 前端构建只允许本地、带 hash 的生产 `dist`；生产包禁止 Vite dev server、CDN 和远程字体/脚本。
6. CSP 至少限制 `default-src 'self'`，并对 script/style/img/font/connect/frame/object/base-uri/form-action 分项收紧；例外必须有独立安全审批。
7. 文件访问使用不透明、短期、单次、受权限约束的 ticket；不向前端暴露任意本地路径。
8. renderer 崩溃、后端退出、窗口关闭和宿主重启必须可恢复且不遗留孤儿进程。

## 双路线样板结论

WebEngine 直接执行冻结 Demo，能保持布局、三主题、SVG 和原交互；QML 样板可以承载相同合同数据，但 V01/V04/V08/V26 的高密度图表、双视角与动态布局需要逐项重写，视觉偏差和重复实现成本显著更高。因此在安全和打包门尚未发现阻断项的前提下选择 WebEngine。G0R 已生成 26×3 WebEngine 参考截图和 4×3 QML 合同样板，并在 1600×900、1280×720 对 V01 子元素盒模型执行零重叠/零越界门禁。

该结论不是生产发布批准。本机采集时 Chromium 无法建立 GLES3 共享上下文并回退软件渲染，因此目标 Windows/Linux 四 profile 的安装包、离线资源、SBOM、许可证、GPU/软件渲染、renderer 恢复与独立安全验收仍是 G11/G12 外部门禁；任一关键门失败时按本 ADR 切换 QML，并复用相同 API/DTO/状态合同。

## 后果

- G1 先建立 WebEngine 安全宿主、静态资源门和 feature flag，再开发页面。
- 前端不持有业务真值，不计算资格、评分、权限或发布结论。
- 旧 P 壳保留为开发诊断回退，是否从生产包移除由 G10 决定。
- 所有页面都必须支持后端不可用、无权限、空数据和系统错误状态。

## 不可接受的实现

- `file://` 直接加载生产静态页；
- 关闭 Web 安全、允许任意 Origin 或把 token 写入 JavaScript/localStorage；
- 生产包访问 CDN、安装时下载前端依赖；
- 用 WebChannel 暴露任意 Python 对象或文件系统；
- 为追求像素一致而绕过 RBAC、审计、CSP 或 API authority。
