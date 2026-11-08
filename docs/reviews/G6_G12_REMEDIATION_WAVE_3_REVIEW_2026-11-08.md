# TPAA G6～G12 关闭后整改波次 3 复核记录

> 日期：2026-11-08
> 结论：继续整改有效，但尚不满足 G6～G12 正式再关闭条件。
> 边界：本地修改和验证；未推送、未部署、未生成发布声明。

## 1. 为什么当前不能直接关闭

### G6：任务/装备指标权威尚未准入

`baseline/CB-1.17.0/canonical/GUI_TASK_METRIC_ADMISSION_AUTHORITY.json` 仍明确为
`NOT_ADMITTED`。v33 Patch 只给出了 Demo 暂定口径，并明确声明其不是正式 P1 Metric
Definition。缺少 Scope、被评估方、去重、J 来源、零分母、任务目标清单、质量门和
比较键时，软件不得自行发明正式公式或展示权威值。

### G7～G8：业务事实来源缺失

非发射行为、感知形成、感知—攻击、攻击支援和几何事实尚无被批准的 Canonical owner
及真实样本。算法和页面可以继续完善，但不能用发射事件反推这些事实，也不能用 Demo
数据替代。

### G9：真实媒体和可读取轨迹投影尚未齐备

仓库没有真实媒体资产；现有 Durable Discovery 对精确 Release 只返回呈现绑定状态，
在 geodetic reader 未绑定时诚实返回不可用。媒体播放还必须通过短期授权票据，不能把
本机路径或对象存储 URI 直接交给浏览器。

### G10：部分正式能力仍未准入

P3 Model Profile、报告修订、治理 mutation、基本飞行和来源覆盖不能由占位页面或
`NOT_ADMITTED` 状态冒充完整功能。它们需要各自的 authority、Application owner、DTO、
权限、审计和真实数据闭环。

### G11～G12：正式环境和人工门未产生证据

安装包、Linux Desktop/Service、SBOM/许可证/漏洞、目标 workload，以及真实角色视觉
任务验收必须在相应环境真实执行。G12 又依赖 G6～G11 全部再关闭。因此当前 W9 必须
保持 `NO_GO`，`product_complete=false`，`release_ready=false`。

## 2. 本波次已经实施的代码整改

1. `ReplayContextApplicationService` 新增精确 Release 呈现源边界。
2. 强制校验呈现 schema、release_id、`SESSION_TIME`、无业务重算、无持久层旁路、无
   mutable/latest alias。
3. 轨迹只保留精确 Weapon Event 锚点窗口内的样本；乱序、跨 Release、非法坐标一律
   503 失败关闭。
4. 媒体只返回 `media_id/media_type/evidence_ref`，剥离原始 URI，并标记必须取得短期
   授权票据。
5. Production 组合复用同一个 `DurableProductDiscovery` owner，避免并行 owner 漂移。
6. V03 在有真实轨迹样本时绘制 2D 和 3D 投影视图；无数据时显示明确 EMPTY/N_A，
   不生成随机轨迹或 Demo 数值。
7. 新增窗口裁剪、媒体 URI 不泄漏、exact Release 和 no-latest 单元验证。

## 3. 本波次验证

- Ruff：PASS。
- Mypy：PASS，644 source files。
- Python contract/unit：PASS，559 tests。
- G9 codegen `--check`：PASS。
- 前端 TypeScript：PASS。
- Vite production build：PASS。

pytest 结束时出现 Windows 临时目录清理的权限警告；测试进程退出码为 0，559 项测试
均已通过。该警告不是业务门通过证据，也不影响上述测试结果。

## 4. 再关闭所需的外部输入/批准

1. 项目所有者批准三项任务指标的完整 Metric Definition，或明确永久从生产范围删除。
2. 提供并批准非发射行为、感知/几何/攻击支援的 Canonical 来源与至少一组可审计样本。
3. 提供一组可导入的真实轨迹和媒体样本，并批准媒体票据/Range 传输策略。
4. 明确 G10 五类未准入能力是“本版本必须实现”还是“从产品范围剔除”；不能保留页面
   同时以未准入状态宣称产品完成。
5. 在 Windows/Linux Desktop/Service 目标环境执行正式交付门，并由真实角色完成视觉
   任务验收。

在这些输入到位前，继续修改可以降低技术缺口，但不能诚实地把 G6～G12 写成
`CLOSED_LOCAL_WITH_GATES`。
