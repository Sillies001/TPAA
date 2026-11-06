# ADR-GUI-002：P 语义页与 V 产品视图采用双层合同

- 状态：`APPROVED_LOCAL`
- 日期：2026-11-06（v33 修订）
- 决策范围：页面注册、路由、DTO、权限、审计与证据追溯

## 背景

现有 GUI 以 P01～P13 组织后端能力和工程语义；v33 目标 Demo 以 V01～V26 组织用户任务。直接以 V 替换 P 会丢失既有机器权威和测试资产，直接把 P 标签改成 V 又无法表达目标信息架构。

## 决策

保留 P01～P13 作为能力、数据语义与治理合同；新增 V01～V26 作为产品视图合同。V 视图只能组合已授权的 P 能力投影，不能重定义指标、资格、证据、权限或发布语义。

规范如下：

1. `GUI_VIEW_CONTRACT` 是 V 视图注册、入口、状态、P 映射、查询资源和权限引用的机器权威。
2. `API_ROUTE_AUTHORITY` 是 route id、method、path、permission、audit 的唯一权威；Desktop policy 只能引用 route id，禁止复制 route allowlist。
3. 前端类型从 DTO/schema authority 生成；禁止手写与 Python 模型平行演化的业务 DTO。
4. `V24` 不是独立 Ribbon 页面，只能由 V08 中已识别的 BVR 同目标协同攻击事件进入，返回目标固定为 V08。
5. `V26` 是训练评估模块 landing，并可由 V01 的 exact Batch 明细下钻；没有 exact Batch/Release/Context 时必须 fail-closed，禁止回退 latest/current。
6. 共享上下文至少包括 Batch、Session、Release、Context、Episode、Stage、WE、Cluster、Perspective、Scope、时间游标、选择区间与 evidence cursor；切页时按显式规则保留或清除。
7. V01、V02、V09、V15、V18 不得生成没有权威定义的综合分或因果结论。
8. 页面隐藏、禁用和菜单过滤仅改善体验，不构成服务端授权。
9. 加载、空、降级、错误、无权限、不适用与系统错误必须是合同状态，不使用空白面板代替。

## P→V 映射原则

- P01/P02/P03/P05/P12/P13 共同支撑 V01/V02/V03/V09/V18/V26 等跨域产品视图；
- P04 的训练工作区能力被 V04～V08、V19～V21、V24 组合使用；
- P06/P07 支撑 V10～V16，但只有 P3 Model Profile 准入后才能显示受控产品结果；
- P12 支撑 V17 和 V23 的质量、资格与导入预检；
- P13 支撑 V22/V25 的治理、门禁和会话界面设置。

完整逐视图合同冻结在 `docs/compliance/GUI_V33_CONFORMANCE_MATRIX.json`。G1 将把其中稳定字段提升为后继机器权威并生成前后端类型。

## 兼容与迁移

新壳由 feature flag 控制；旧 P 壳在 G11 决定前保持可启动。API v1 只做兼容性增量，不改变既有 route 语义。R3.3、CB-1.4.0 和 CB-1.5.0 字节不变；新 route、DTO 和状态只进入 CB-1.6.0 后继基线。
