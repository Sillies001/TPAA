# W5 P1 Desktop 操作流程

## 前置条件

- Desktop 运行诊断为 `READY`，且本地身份拥有 `SOURCE_IMPORT` 与 `COMPUTE_EXECUTE`。
- 输入文件是 `TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1` JSON，不接受界面推断或临时拼装的数据。
- 操作仅面向本地 Desktop 数据根；生产发布不属于本流程。

## P01 导入与发布

1. 在 P01 选择真实 P1 request manifest。
2. 执行 `Validate & stage sources`。六类内联源文件会先写入不可变 managed artifact，界面显示数量和 source family。
3. 执行 `Build & publish P1 Release`。任务在后台线程等待受控 worker，界面保持响应并明确显示 `RUNNING`、`SUCCEEDED` 或 `FAILURE`。
4. 成功后刷新 Session 列表，选择目标 Session 与精确 Release。

## P02～P03 追溯

1. P02 载入精确 Release，核对 Mission Header、Episode/Stage 以及 Aircraft、Mission-System、Reference Truth 三条 lane。
2. P03 执行 exact replay，选择 Stage 和 Metric，再打开绑定 Observation/Evidence；禁止使用 `latest`、`current` 或邻近 Release 代替。
3. Release 含精确 geodetic presentation 时绘制二维轨迹；缺少时显示明确不可用原因，不合成轨迹。

## P12～P13 治理检查

- P12 检查时间、参考、关联、world coverage 和每条 Observation Eligibility；被排除或需复核的记录不得从表中消失。
- P13 检查 Release/Provenance、Catalog/Profile、Context、Model/Twin、权限审批和运行时状态。
- `N/A`、未知/未计算、需复核和失败必须分别显示。
