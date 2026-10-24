# W6 P04–P10 Desktop 操作说明

W6 页面只读取或修订精确、不可变的产品版本。`current`、`latest` 等可变别名不构成历史回放依据，GUI 也不重算 Assessment、Attribution、Twin、型号 cohort 或趋势统计。

## 页面职责

- P04：选择精确 P4 个体评估，查看 subject、Episode、有效性、claim、证据与审批链；团队结果不会映射为个人分数。
- P05：选择精确 P5 团队/任务评估，查看 composition、成员引用、objective/world evidence 与审批链；成员引用不是个人评分。
- P06：选择精确 Twin revision 与 Estimate，核对 P1 Observed、P2 Adjusted、P3 Reference Estimate 三层及证据路径。
- P07：仅接受服务端发布的型号/Block/构型 cohort。若该聚合产品未发布，页面显示 `UNAVAILABLE`，禁止从单机 Twin 在前端临时聚合。
- P08：选择精确 P2 Estimate，同时读取 comparison 与 diagnostics。贡献统一标为模型条件下的 association；`NOT_IDENTIFIABLE` 只显示原因，不显示确定数值。
- P09：先选择 `AIRCRAFT` 或 `MISSION_SYSTEM_INSTANCE` lane，再读取精确 longitudinal release。lane 不匹配时为空，不混线；configuration/software break 独立显示。
- P10：选择 `HUMAN` 或 `TEAM` lane，查看不可变 P4/P5 历史。页面不计算新的 score trend，也不执行 team-to-individual 分摊。

## 生命周期与权限

P04/P05 的 reviewer transition 会创建新的不可变 revision；理由为必填。后端角色、scope 和状态机仍是最终授权源，拒绝结果按失败状态呈现。非 Assessment 产品的发布、撤回和 supersede 由 P13 治理工作流负责，P06–P10 只显示其精确状态和历史来源。

## 失败语义

无数据显示 `EMPTY`；权威聚合或 reader 未发布显示 `UNAVAILABLE`；HTTP、身份、hash、schema 或 exact binding 不一致时 fail closed。任何失败都不得回退到当前 Catalog、Context、Model 或最新 Release。
