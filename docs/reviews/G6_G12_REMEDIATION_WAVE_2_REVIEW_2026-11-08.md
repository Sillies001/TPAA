# TPAA G6～G12 关闭后整改波次 2 复验报告

> 日期：2026-11-08
>
> 判定：`R3_R4_PARTIAL_PASS / G6～G12 NOT RECLOSED`
>
> 边界：本地修改；未提交、未推送、未部署、未发布。

## 1. 已完成整改

1. V26 增加精确主体、Episode、起止 Session Time 筛选；
2. 类别、裁决、Cluster、主体、Episode、时间范围共同进入游标指纹；
3. API、Application、Gateway 和页面 filter 回显保持一致；
4. 损坏 Canonical relation JSON 或畸形 WE 行显式返回 503，不再静默少计；
5. 前端筛选控件进入正式构建，并通过真实 G7 WebEngine 验收。
6. V24 要求精确 Context、完整纯 BVR Cluster 和覆盖事件时刻的 Formation revision；
7. V24 呈现真实 WE 时序/同目标与射手编队角色事实，不计算总分；
8. G8 durable relation JSON 损坏显式返回 503，并通过真实 G8 WebEngine 验收。

## 2. 复验

- Ruff：PASS；
- Mypy：PASS（644 source files）；
- Python 全回归：558 passed；
- G7 Application/API/durable 专项：18 passed；
- 前端 TypeScript/Vite build：PASS；
- G7 WebEngine：12 captures，box-model no-overlap PASS。
- G8 Application/API/durable/前端竞态契约专项：18 passed；
- G8 WebEngine：12 captures，box-model no-overlap PASS。
- G12 自动结构矩阵重采集：156 captures、26 views、156 unique SHA，PASS。

## 3. 未关闭原因

- G6：任务/装备 Metric Definition、真实目标/裁决/装备观测来源未获独立准入。Demo 文本明确这些指标仍是演示口径，禁止在缺少公式及证据时自行升级为权威指标；
- G7：非发射训练行为尚无独立权威来源和类别合同，当前只能保持明确 N_A；
- G8：感知形成、感知—攻击、攻击支援与几何/共享/序列来源仍未准入；
- G8～G12：仍按总整改方案保持开放。

当前裁决继续为 G6～G11 `IN_PROGRESS_REMEDIATION`、G12 `IN_PROGRESS_EXTERNAL_DOORS_OPEN`、W9 `NO_GO`。
