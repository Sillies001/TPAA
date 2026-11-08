# TPAA G6～G12 关闭后整改波次 1 复验报告

> 日期：2026-11-08
>
> 判定：`WAVE_1_IMPLEMENTED / G6～G12 NOT RECLOSED`
>
> 边界：本地修改；未提交、未推送、未部署、未发布。

## 1. 本波次结果

本波次纠正了状态真值和证据工具，并完成以下源代码整改：

1. W9 改为 `NO_GO / product_complete=false / release_ready=false`；
2. G6～G11 回退 `IN_PROGRESS_REMEDIATION`，G12 保持外部门开放；
3. 阶段能力由受信任 lock 内连续 approval 链解析，移除逐级基线白名单；
4. 旧关闭器在整改状态下失败关闭，并要求真实命令退出码证据；
5. 损坏 WE properties 不再静默转换为空对象；
6. V26 筛选栏恢复正常文档流；
7. V03 回放使用 Release/Context/WE/Perspective 四元组并拒绝缺失/不匹配；
8. GUI Gateway provenance 使用实际受信任运行时基线；
9. G9 manifest 目录由错误的 CB-1.13.0 修正为 CB-1.14.0；
10. V24 使用稳定数据属性与 V08 受控入口，自动矩阵不再依赖中文文本；
11. 视觉工具从最终 registry 读取 26 视图，断言真实视图/标题并阻止跨视图重复截图；
12. G11 关闭器要求九项正式工程门全部提供机器证据。

## 2. 复验结果

- Ruff：PASS；
- Mypy：PASS，644 个源文件；
- Python：542 passed（短临时路径；长仓库路径会触发 Windows 路径长度限制）；
- 定向新增回归：30 passed；
- G4～G12 successor `--check`：全部 PASS；
- G4～G9 codegen `--check`：全部 PASS；
- 前端 TypeScript：PASS；
- Gateway：7 passed；
- Vite production build 与桌面资源一致性：PASS；
- G8 V08→V24 WebEngine：12 captures PASS；
- G9 精确回放 WebEngine：12 captures PASS；
- G12 自动结构矩阵：156 captures、26 views、156 unique SHA，`AUTOMATED_STRUCTURAL_PASS`。

## 3. 证据范围限制

自动结构矩阵只证明视图身份、标题、主题、Ribbon、顶层面板重叠、交互控件裁切、viewport 溢出和截图唯一性。它不证明：

- 页面与 Demo v33 的区域/像素忠实度；
- 尚未准入的业务读模型已经完成；
- 真实角色任务链人工验收通过；
- 安装包、跨平台、SBOM、漏洞和性能门完成；
- 产品完成或发布就绪。

## 4. 当前裁决

- G0R～G5：`CLOSED_LOCAL_WITH_GATES`
- G6～G11：`IN_PROGRESS_REMEDIATION`
- G12：`IN_PROGRESS_EXTERNAL_DOORS_OPEN`
- W9：`NO_GO`
- `PRODUCT_COMPLETE=false`
- `RELEASE_READY=false`

下一波必须继续执行方案 R2～R8 的开放功能和正式门，不能运行旧关闭器强行改变状态。
