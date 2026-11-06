# ED-2.0 分册 F：Application Service、REST API 与 DTO

**定义权声明：** DTO 字段契约只由 `canonical/CROSS_LAYER_DTO_CONTRACTS.json` 定义；本分册定义服务/API 行为，不允许 Controller/UI 反向创造 DTO schema。

## 1. 边界

Application Service 是 GUI/REST 唯一业务入口。GUI 不直接查询 DB；REST controller 不重新实现 Domain rules；DTO 不从 UI view model 反向定义。

## 2. Query / Command

Query：Session/Episode/Stage/Context/MetricDetail/Observation/Trend/World/Chain/Evidence。Command：Import/Recompute/Publish/Context correction/Annotation/Mission-System lifecycle 等。写操作必须支持 Idempotency-Key 或等价 canonical request hash。

## 3. Critical DTO

字段级权威见 `canonical/CROSS_LAYER_DTO_CONTRACTS.json`。至少包括 EvaluationContextDTO、ContextArtifactRefDTO、EvaluationContextBundleDTO、CapabilityObservationDTO、MissionSystemObservationDTO、MetricCatalogEntryDTO、TPAAChainDTO；MetricDetail 等复杂 projection 必须同样从 immutable Definition/Release 构建，而非 current Catalog。

## 4. Context API

必须支持 exact context-id read、Session contexts list、Release-bound context list/bundle。历史 Release 使用 frozen context_id；禁止 latest/max-revision fallback。

## 5. Metric Detail

返回 immutable Metric Definition identity、release/catalog provenance、stable subject、typed value、Context refs、episode/stage、required worlds、world versions、chain/evidence、versions。Structured value 按 object 传输。

## 6. Trend API

路由明确 subject type；as-of 使用明确命名参数（session order/calendar/release），互斥条件 422；数据不足是 HTTP 200 + business status，而不是在 200/422 间漂移。

## 7. Time transport

所有 JS-visible `*_session_time_us` 使用 decimal-string。API 内不使用浮点表示 Session microseconds。

## 8. Error model

输入/前置非法→4xx；合法请求但数据不足→200 + N_A/INSUFFICIENT_DATA/REVIEW_REQUIRED；系统错误→5xx + 受控日志。

## 9. Version handshake

API v1、DB schema、Core Baseline、Catalog/Metric/World versions 分离。Runtime handshake 必须阻止前后端 schema/core contract mismatch 进入 READY。

## 10. Application Service 用例分组

- Registry/Master：Session、Aircraft、Mission-System、Context artifact；
- Context：Resolve/Get/List/Bundle/Release Context；
- Episode：Detect/Validate/Get/List/Stage/Window；
- World：Build/Get Manifest/Get Relation/Get Chain；
- Metric：Compute/Get Detail/Get Catalog；
- Observation：Aircraft/System list/detail；
- Longitudinal：Build sample/trend、Get trend/history；
- Release：Publish/Get/List/Withdraw/Supersede；
- Annotation/Governance：revision、audit、export。

Application Service 返回 Domain/Application result，再由 transport mapper 生成 DTO。Service 不返回 ORM entity 给 GUI。

## 11. REST 资源设计原则

资源 URL 使用 stable ID；历史请求显式携带 release/context/as-of 语义；列表接口统一分页、排序和 filter schema。禁止 `GET /latest` 成为历史业务逻辑依赖；“current”只用于用户导航，响应必须回传解析后的 exact release/context IDs。

## 12. Context Read Surface

至少包括按 context_id 读取、按 Session 列出 Context revisions、按 Release 获取实际 bindings、获取 deterministic Bundle。Bundle 数组稳定排序；artifact missing/schema unsupported 使用明确错误码。UI 选中的 `context_id` 是历史主键，revision_no 不用于推导“最新”。

## 13. MetricDetail Projection

MetricDetail 从 metric_instance + immutable metric_definition/semantic + release + context bindings + world/chain/evidence 组成。value 根据 value_kind 映射；required worlds、lane、route、subject 等解释元数据从历史 Definition 读取。任何 current Catalog lookup 只能用于展示“当前是否还有同 code”，不能覆盖历史字段。

## 14. Observation API

Aircraft 与 Mission-System Observation 使用不同资源或明确 subject_type，不能返回一个字段含义随 subject 改变的模糊对象。响应必须含 observed metric/evidence anchor，支持 P02/P03 drill-down。

## 15. Longitudinal API

请求必须明确 subject_type+subject_id、metric semantic/definition、configuration key/comparison filters 和 as-of 语义。`as_of_session_order`、`as_of_occurred_at_utc`、`as_of_longitudinal_release_id` 互斥。历史响应必须回传 longitudinal release/scope 与每个 point 的 input Session Release。

## 16. DTO 代码生成与校验

Critical DTO 应从 `CROSS_LAYER_DTO_CONTRACTS.json` 生成/校验 Pydantic/OpenAPI/TypeScript(or equivalent) 类型。CI 对 required/nullability/transport type 做 exact diff。UI ViewModel 可以增加显示字段，但必须通过明确 mapper 且不得反向成为 API authority。

## 17. Idempotent Command

Import/WorldBuild/MetricCompute/TrendBuild/Publish 等 command 接受 Idempotency-Key。服务构造 canonical request hash；并发同请求合并或返回已有 job；同 key 不同请求返回 conflict。Crash recovery 不能产生两个 current Release。

## 18. Pagination / Streaming

高频 series/trajectory 不直接塞入普通 JSON 大列表。使用范围查询、LOD/downsample/Arrow/streaming 或专门 series endpoint。列表 DTO 保持轻量，detail/evidence 分资源加载。

## 19. Security Boundary

Desktop token、Service identity/RBAC、CORS、path allowlist、export permission 在 transport/application 边界执行；Domain 仍验证 resource ownership/session/release consistency，避免只依赖 UI 隐藏按钮。

## 20. API Contract Tests

Golden OpenAPI snapshot、DTO field parity、decimal-string time、structured object、historical Definition replay、Context artifact fail-closed、idempotency race、data-insufficient=200 business status、current pointer lock 等必须自动化。

## 21. P4/P5 Training Assessment API Surface

进入 P4/P5 实现时，Application 层至少提供以下概念级资源/用例，字段在实现前由 DTO machine authority 正式冻结：

- Actor / Human-Machine Assessment；
- Competency Observation / Qualification；
- Team / Mission / Package Assessment；
- Objective Result；
- Instructor Annotation / Review / Override Revision；
- Root-cause Candidate / Evidence Graph；
- Human/Team longitudinal / cohort analytics；
- Course/Unit aggregate analytics。

每个历史 Assessment response 必须携带 exact Release/Profile/Context/Metric/World evidence refs。current Profile 只能用于比较/导航，不能重解释历史结果。

## 22. P2/P3 Capability Intelligence API Surface

至少预留：

- Observation Eligibility；
- Factor Feature / Attribution Run/Result；
- Context-adjusted Estimate；
- Capability Model / Surface metadata；
- Aircraft Twin Revision；
- Reference-condition Estimate history；
- Aircraft Model Capability Profile；
- Lifecycle/Change-point evidence；
- Model validation/release metadata。

API 必须完整表达 NOT_IDENTIFIABLE、OOD、INSUFFICIENT_DATA 等状态；不得把无结果转换成 `0` 或空对象假装成功。

## 23. P6 Intelligence API Separation

Forecast、Counterfactual、Recommendation 使用与 fact/replay 不同的 resource namespace/product type，响应必须带 assumptions/model/spec/validation/approval。禁止在 Session historical endpoint 中把 forecast field 混入事实 DTO。

## 24. Debrief / Media / Bookmark API

Debrief 使用 Timeline/Trajectory/Event/Metric/Assessment/Evidence/Media 等统一服务。Media query 需要 Session Time mapping；Bookmark/Debrief Point 保存 stable refs + view state；Playlist 保存排序依据和 event/evidence refs，不复制底层时序数据。

## 25. Scope / Participant Query

P4/P5 查询必须显式传递/返回 scope（Individual/Team/Package/Joint-LVC）和 participant/observer/actor subject identity。禁止一个 generic `subject_id` 在不同 endpoint 随上下文改变含义而无 subject_type/scope。

## 26. Analytics / Cohort API

长期/课程/单位分析请求必须显式指定 cohort/comparison version/as-of semantics。响应同时返回样本数、独立 subject 数、World Capability/Profile/Metric/Attribution versions 与 excluded reason summary，避免前端只拿一条 aggregate 曲线失去可比性解释。

## 27. External Interoperability Boundary

TENA/HLA/DIS 等协议不直接暴露为 Domain DTO。Gateway/Adapter 先转换为 Registry/Canonical/World identity，再由标准 Application API 对外提供。这样协议版本变化不会扩散到 Metric/Assessment API。

## 28. DTO Future-freeze Rule

R2 只冻结 P2～P6 的**语义资源合同**，不凭空发明尚未进入实现的字段。某 P capability admission 前必须：

1. 把需要的 DTO 加入 `CROSS_LAYER_DTO_CONTRACTS.json`；
2. 对应 Core Logical Model/migration；
3. 生成 OpenAPI/客户端类型；
4. 加 exact parity/history fixtures；
5. 通过 review gate 后才能对 UI 开放。
