# 正式资格证据装载与 GUI 人工验收操作说明

## 1. 适用边界

本文用于关闭后整改波次的后续独立发布与人工 GUI 验收。它不授权生成生产签名、推送代码、合入保护分支或部署生产环境。

## 2. 正式证据装载

运行配置可选增加以下精确对象：

```json
{
  "formal_qualification": {
    "manifest": "C:/absolute/path/formal-runtime-evidence.json",
    "trust_root": "C:/absolute/path/release-authority-ed25519-public.pem",
    "key_id": "controlled-release-authority-key-id",
    "candidate_identity_sha256": "64-lowercase-hex",
    "source_revision": "40-lowercase-git-sha"
  }
}
```

要求：

- manifest 和 trust root 必须是绝对路径且文件存在；
- trust root 必须为 Ed25519 公钥；私钥不得进入运行配置、仓库、日志或 evidence 目录；
- envelope schema 必须为 `TPAA_FORMAL_RUNTIME_EVIDENCE_ENVELOPE_V1`；payload schema 必须为 `TPAA_FORMAL_RUNTIME_EVIDENCE_V1`；
- payload 必须精确绑定配置中的 candidate SHA-256 与 source revision；
- signature 对象只允许 `algorithm=Ed25519`、精确 `key_id` 和 64-byte signature 的 Base64；
- W7/W8/W9 对象的字段、顺序、布尔和计数类型必须通过各自严格合同；字符串 `"false"`、浮点计数和候选漂移均不得接受。

验签失败、字段漂移、文件缺失或 trust root 不正确时，生产运行时应拒绝启动；不能回退为 GO。未提供该对象时，运行时使用本地关闭证据并保持 `NO_GO`。

## 3. 人工 GUI 验收节点

在批准的 Windows/Linux Desktop 显示环境中，由真实业务角色依次执行：

1. 启动批准候选，确认 Mission Header 的 build/Core/DB/role/session/release 与候选清单一致。
2. 使用 TRAINEE 登录，点击“Apply authenticated role view”，确认进入 P02；尝试 Source Import，应被拒绝且无越权副作用。
3. 使用 INSTRUCTOR 登录，确认进入 P03；选择精确 Release，依次检查 2D、3D、Linked Flight Plot、Media/Transcript、Timeline 和 Evidence。无 geodetic 数据时必须明确 unavailable。
4. 使用 EVALUATOR 登录，确认进入 P13；检查 Final Release Gate 位于首个可见页签，`NO_GO/GO` 与 `/runtime/final-qualification` 完全一致。
5. 使用 TRAINING_MANAGER 登录，确认进入 P11；使用 DATA_ENGINEER 登录，确认进入 P12；只有受权角色可执行 Source Import。
6. 在 100%、125%、150%、200% DPI 和批准的最小/标准/大屏分辨率检查文字、焦点、表格列、页签、滚动、键盘 Tab/Shift-Tab、状态颜色与高对比主题。
7. 关闭窗口，确认无错误弹窗、后台线程和本地后端进程退出。
8. 对每个角色记录候选 SHA、OS/profile、分辨率/DPI、操作者、结果、截图哈希、缺陷编号和签字时间。

若任一页面裁剪关键控制、角色越权、P13 与机器状态不一致、字体不可读、历史数据使用 current/latest 回退或缺少证据绑定，人工验收必须判定失败。

## 4. 当前本地参考证据

- `evidence/postclose-role-task-acceptance-20261026.json`
- `evidence/postclose-gui-workflow-acceptance-20261026.json`
- `build/postclose-visual-20261026/w4_visual_96dpi.json`
- `docs/reviews/POST_CLOSE_REMEDIATION_WAVE_2026-10-26.md`

这些文件只证明当前本地自动化执行，不是独立组织签字或生产发布批准。
