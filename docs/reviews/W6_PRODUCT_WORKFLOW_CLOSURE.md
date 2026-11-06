# W6 P04–P10 Product Workflow 本地关闭记录

## 结论

W6 在本地开发边界内关闭，状态为 `CLOSED_LOCAL / PASS / NOT_PUSHED / NOT_DEPLOYED`。P04–P10 已从错位的 M3/M4/M6/M7/M8/M9 研发工作台复用改为七个独立产品页面，页面编号、角色任务、exact identity 和语义边界与 R3.3 GUI 设计分册一致。

本结论不表示生产数据、组织审批或生产部署已获准。P07 所需的服务端型号 cohort 产品当前未发布；该页通过的是明确 `UNAVAILABLE`、禁止前端临时聚合的 fail-closed 门禁，不代表已有型号总体能力结论。

## 交付范围

| 页面 | 本地关闭证据 |
|---|---|
| P04 Individual | 精确 P4 revision、个体身份/有效性/claim/evidence、不可变 reviewer transition；禁止 team-to-individual |
| P05 Team/Package/Mission | 精确 P5 revision、composition/member/objective/world evidence、不可变 reviewer transition；成员不是个人评分 |
| P06 Aircraft Twin | 精确 Twin + Estimate；P1 Observed、P2 Adjusted、P3 Reference Estimate 分层；同 Episode truth 回流警示 |
| P07 Model Profile | 只接受服务端发布且含 aircraft/episode count 的 profile；无权威 API 时明确不可用；禁止 GUI cohort 聚合 |
| P08 Context Adjustment | comparison 与 diagnostics 同时读取；association-only；NOT_IDENTIFIABLE 不显示确定贡献；保留原尺度 |
| P09 Observed Trend | canonical 页面名；AIRCRAFT 与 MISSION_SYSTEM_INSTANCE lane 隔离；configuration/software break 显式 |
| P10 Human/Team Longitudinal | HUMAN 与 TEAM 不可变 revision history 分 lane；不在 GUI 计算 score trend 或团队到个人分摊 |

## 语义误读门禁

自动契约覆盖以下专家审查问题：

1. `latest/current` 不得作为 exact identity；
2. P2 effect 只能作为模型条件下的关联解释，不能自动解释为因果或百分比；
3. `NOT_IDENTIFIABLE` 不能出现确定贡献值；
4. P1/P2/P3 分别表示 observed、adjusted、reference-condition estimate；
5. Twin 不得回写为同一 Episode 的观察事实；
6. TEAM revision 和 participant reference 不得呈现为 HUMAN/Individual score；
7. Aircraft 与 Mission-System trend 不得混线；
8. configuration break 不得被连续同质趋势遮蔽；
9. P07 不得由 GUI 汇总单机 Twin 冒充型号 cohort；
10. OUTLIER 只表示 review，不自动判为 fault。

## 验证记录

- `pytest tests/unit -q`：763 passed；
- `pytest tests/contract -q`：817 passed，唯一失败为开发打包器按既有合同拒绝未提交工作树；业务与安全契约无失败；
- W4/W5/W6 GUI 定向回归：12 passed；
- Ruff：`src` 与 W6 测试通过；
- mypy：298 个 source files 通过；
- JSON 契约解析：通过；
- compileall：W6 与 shell 变更通过。

正式候选提交后须在干净 tracked worktree 上再次执行 contract 与 Windows Desktop package；打包器门禁不得放宽。

## 保留门禁

- 禁止 push；
- 禁止生产部署；
- 生产签名、保护分支合入、真实组织角色审批和生产数据资格仍未开启；
- P07 型号 cohort 的服务端发布能力仍是后续后端产品化事项；在其发布前 GUI 必须保持 fail closed；
- 非 Assessment 产品的 publication/withdraw/supersede 继续由 P13 Governance 承担，W6 页面只读取精确状态与历史来源。
