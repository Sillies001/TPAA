# ED-2.0 分册 E：Storage、Release、Migration 与 Historical Replay

**定义权声明：** 本分册不另建逻辑 schema；字段级事实只由 `canonical/CORE_LOGICAL_MODEL.json` 定义，Release/Replay 服从 Core Rules。

## 1. Storage authority

逻辑字段只由 `CORE_LOGICAL_MODEL.json` 定义。schema target 继续为 1.6.0；本次文档重构不伪造 1.6.0→新版本 DDL migration。

## 2. Repository

Desktop profile：SQLite WAL + local Parquet，由 Backend Repository 单写数据库；Worker 仅写 staging。Service/CI profile：PostgreSQL + Parquet/Alembic；Domain contract 不因 dialect 分叉。

## 3. Immutable Release

SESSION / LONGITUDINAL Release 均有 release identity、compute job、catalog provenance、context binding hash、manifest hash、status 与 parent/supersession。Publish 使用 CAS/idempotency；staging 不得被 current pointer 引用。

## 4. Context artifact storage

Scenario/Profile/Rule/Reference 等历史配置必须注册 immutable artifact，绑定 sealed object reference 与 SHA-256。RETIRED 仍可历史读取；缺失或 schema unsupported 必须 fail-closed。

## 5. Historical Metric Replay

按 metric_instance_id 读取时，Metric Definition、Semantic Registry、Catalog provenance、Context refs、TPAA chain、Evidence 均来自 immutable historical rows。不得用 current Catalog 查 name/subject/lane/value kind/required worlds 来覆盖历史定义。

## 6. Hash semantics

区分 artifact byte hash、logical content hash、request hash。跨平台 scientific determinism 比较 canonical logical content/tolerance；不要求物理 Parquet byte hash 相同。

## 7. Migration

R39 支持链仍作为历史 provenance；新基线部署若继续使用 schema 1.6.0，无需因文档版本升级执行 DB migration。只有 Core Logical Model 字段变化时才产生新的 schema version + migration rehearsal。

## 8. Backup / Recovery / Orphan

Crash/cancel 不留下已发布半成品；sealed-but-unreferenced object 进入 orphan scan；restore 后必须通过 manifest/hash/release referential checks 再恢复 current pointer。

## 9. 物理存储分工

关系库保存 identity、registry、revision/supersession、release、small/medium relational facts、索引和关键契约；Parquet/object storage 保存高频 Canonical/World/series/evidence payload；二者通过 immutable object reference/hash 连接。禁止在数据库和文件系统各维护一份相互独立的“当前状态”。

## 10. 发布事务

发布流程：完成 staging → 校验 schema/hash/ref → seal payload → DB transaction 登记 Release/产品 → CAS current pointer。若 staging 与 final 不在同一文件系统，不得声称 rename 原子；object storage/NAS 使用其自身 finalize/version semantics。

## 11. Current Pointer

current_release_id 只是缓存/导航指针，不是历史解释权威。所有 historical object 都通过 release_id/definition/context/artifact IDs 精确读取。current pointer 更新失败不能破坏已发布旧 Release；并发 publish 使用 CAS/unique scope release number。

## 12. Metric Definition Persistence

Metric Definition 必须持久化足够的 immutable 解释元数据，包括 catalog provenance、semantic identity、subject/lane/route、required worlds、definition hash 与 executable/plugin version。MetricInstance 不复制所有定义字段，而通过 immutable definition ID 解释。

## 13. Context Artifact Immutability

artifact identity/content 注册后不可变；状态最多允许 ACTIVE→RETIRED，RETIRED 仍可 replay。若历史 payload reader/schema 不支持，系统返回明确错误并阻断解释，不自动 migrate 到 current schema。

## 14. Release Types

SESSION Release 绑定一个 Session 和实际 Context bindings，并承载 World/Metric/Observation products；LONGITUDINAL Release 绑定 longitudinal scope 和 input SESSION Releases。Longitudinal Release 自己的 catalog/prod contract 不能覆盖输入 Session Release 的历史 catalog provenance。

## 15. Migration Discipline

每次真实 schema 变更必须具备 clean bootstrap、当前 hop up/down、forward recovery、完整支持链、seed/hash parity、typed value round-trip 与 historical replay fixture。仅改变文档组织或 Core authority 位置不构成数据库迁移理由。

## 16. Concurrency

Desktop SQLite 由单一 Backend writer 事务化提交；Worker 不直接写权威表。Service/PostgreSQL 可并发计算，但同一 scope 发布仍必须经过 Release Service、idempotency 和 CAS。Repository contract 不允许把数据库 dialect 差异泄漏到 Domain 业务分支。

## 17. Retention / Export / Deletion

Retention 与 export 遵循批准的数据策略。删除/归档前必须检查 Release/Context/Evidence/manifest 引用；不能删掉仍被历史 Release 需要的 artifact。若政策要求物理删除，应把历史产品标记为不可再解释并保留审计，而不是偷偷回退到最新配置。

## 18. Backup / Restore 验证

Restore 后执行 schema version、manifest/hash、foreign refs、sealed objects、current pointer、Context artifacts、Catalog/Definition 与 sample/trend provenance 检查。只有通过后恢复服务写入。

## 19. P2～P6 Product Release 分类

除 P1 Session/Longitudinal Release 外，后续成熟度产品需要保持独立 release/product identity：Attribution/Adjusted Estimate、Capability Model/Surface、Aircraft Twin Revision、Actor/Competency Assessment、Mission/Objective Assessment、Forecast/Counterfactual/Recommendation。具体持久化对象由 Core Logical Model/未来 migration 控制，本分册只规定发布语义。

任何下游 Release 必须引用 immutable upstream Release/Product refs，而不是复制 current 值。Withdraw/Supersede 只改变 current selection，不删除历史 provenance。

## 20. Model / Profile / Rubric Artifact Storage

Assessment Profile、Training Standard/Rule、Attribution Spec、Capability Model artifact、Validation evidence、Instructor Rubric、Forecast/Counterfactual spec 都作为 sealed object/artifact 管理，记录 hash、schema/version、status 和 binding。

算法/模型 binary、surface dataset、uncertainty dataset 等大对象可以在 object storage，但 DB 必须保存 immutable ref/hash。仅保存版本字符串不足以重放。

## 21. Annotation / Media / Bookmark Retention

Instructor annotation/review 是 revisioned governed data；Audio/Video/Transcript 是 registered time-aligned artifact；Bookmark/Debrief Playlist 是 view/evidence reference product。三者的 retention/export 权限可以不同，但都不得通过“删除 UI 记录”破坏已发布 Assessment 的 evidence lineage。

若按 policy 删除媒体本体，历史产品应标记 media unavailable，并保留允许保留的 hash/metadata/reference status；不得从其他 current 媒体偷偷替代。

## 22. Knowledge-time Replay

Historical replay 除业务 valid time 外，还应尊重 information-available/as-of boundary。系统需要明确支持：

- ORIGINAL_AS_KNOWN：按当时可得 Context/lifecycle/adjudication/labels 重现；
- RETROSPECTIVE_REVISION：使用后来补充资料形成新 Release，并明确 revision source。

两类结果不得共用一个“current”字段悄然覆盖。

## 23. External/LVC Artifact

TENA/HLA/DIS 等 gateway 输入与仿真 scenario/model 也必须注册 source/artifact/version/hash。LVC replay 依赖的 federation/scenario configuration 进入 Release provenance；否则不能声称 deterministic replay。

## 24. E 分册扩展验收

- P2～P6 下游产品引用 upstream immutable refs；
- model/profile/rubric artifacts 有 hash/版本/validation binding；
- annotation/media/bookmark retention 不破坏 evidence lineage；
- as-known 与 retrospective revision 可分别重放；
- LVC external configuration 可追踪。
