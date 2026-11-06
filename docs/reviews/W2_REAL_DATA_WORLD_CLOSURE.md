# W2 真实数据入口与时间/World 闭环关闭评审

评审日期：2026-10-20
结论：`CLOSED_LOCAL / PASS / NOT_PUSHED / NOT_DEPLOYED / NOT_PRODUCTION_READY`

## 1. 关闭范围

本轮关闭了 W2 的六项工作和阶段退出门：受版本治理的 Source registry/inspect/stage/canonicalize API；真实 Flight 数据适配；显式时间、坐标、单位和实体关联 profile；Episode 自动建立与不可变修订；World manifest/relation/TPAA-M chain 查询；有界输入、取消、真实样本和隐私处理。W3～W9、干净候选打包、签名发布、现场性能和生产部署仍保持阻断。

## 2. 实现证据

| 子项 | 实现 | 关闭判定 |
|---|---|---|
| Source 入口 | `source_workflow.py`、`source_v1.py`；原始 CSV 与规范化 JSON 双对象不可变暂存 | `PASS` |
| 真实适配器 | NASA MATLAB v5 字节门、隔离 SciPy 转换器、受管 Flight CSV 适配器 | `PASS` |
| 语义 profile | 显式 Session 时间、BODY/NED/TRUE、度/节到 SI、显式 aircraft UUID | `PASS` |
| Episode/World | P1 自动 Episode/Stage、`supersedes_episode_id` 修订、World graph、显式部分 TPAA-M chain | `PASS` |
| 大文件控制 | 1 MiB 分块、接收过程 64 MiB 上限、断连/协作取消、series 5000 行界限 | `PASS_FOR_W2_PROFILE` |
| 黄金集/隐私 | NASA 公开去标识化样本仅留本地；Git 只保存元数据和散列 | `PASS` |

应用分层门禁曾在回归中发现 `tpaa_api → tpaa_ingest` 的直接依赖；profile 构造随后被收回 `tpaa_application`，架构契约已重新通过。这一问题未被豁免。

## 3. 真实样本证据

使用 NASA DASHlink [Sample Flight Data](https://c3.ndc.nasa.gov/dashlink/projects/85/) 项目 [Tail 687 资源](https://c3.ndc.nasa.gov/dashlink/resources/664/) 压缩包中的 `687200404160841.mat` 作本地资格样本。NASA 页面将该集合描述为机载记录的区域喷气机运行数据，并说明数据已去标识化。由于资源页未给出可供仓库再分发的明确许可，本地原始文件、派生 CSV 和转换 manifest 均置于被 Git 忽略的 `evidence/local/w2/`；仓库只记录以下不可逆证据：

- MATLAB 文件：34,648 bytes，SHA-256 `317500a39ab3f38a3d48fa20a1f6f2ea31c31aefb8057cac87b6e4005bf85fc2`；
- 转换后 CSV：2,292 bytes，48 行、4 Hz，SHA-256 `c3a9268b02077ae2e6dad7e2d8da918b939ecb1029859ba84afecf17ea0fb3ed`；
- 隔离环境重复转换得到相同 CSV SHA-256；
- TPAA 实际规范化结果：48 行、1 个源时钟段、Session 时间 `[0, 11750000]` 微秒；
- mapping manifest SHA-256：`5d2bd59441a6f12e56ea801f5d818f64e83a2a1dff2104782f33f1f60379831f`。

转换映射为：8 Hz `ROLL` 相邻样本推导 `p_deg_s`，8 Hz `VRTG` 两点平均到 4 Hz `nz_g`，4 Hz `TH/TAS/MACH` 分别映射为真航向、真空速和马赫数。转换器对采样率、单位、描述及长度偏移全部失败关闭。

## 4. 全链与历史一致性

生产 P1 聚焦测试从受管 CSV 入口开始，经 raw/canonical 双暂存进入既有六 Source family 请求，发布 116 项 P1 catalog 和 4 个 World product。除常规固定测试外，本地资格运行还把上述真实 NASA 派生 CSV 直接替换为 FLIGHT Source，并把显式 SCENARIO Stage markers 绑定到真实区间 `[0,11750001)`；首次使用不匹配的旧 marker 区间时系统按预期以 `ED2_STAGE_MARKER_INTERVAL_INVALID` 失败关闭，修正上下文后全链发布和重启 exact replay 通过。其余五类 Source 为资格 companion，不把它们误述为真实机载数据。发布后验证：

- Session/Episode/Stage topology 可由正式 repository 查询；
- TPAA-M chain 显式绑定 C/W/A/M，P/J 为空并给出 `P_AND_J_UNAVAILABLE`，不得伪造完整链；
- sealed Parquet 可按 Session 时间范围重建并验证 artifact SHA-256；
- 重启运行时后同一 Release 返回一致的 `manifest_hash`、成员集合和 `logical_membership_sha256`；
- 创建 Episode revision 只新增带 `supersedes_episode_id` 的 `REVIEW_REQUIRED` 记录，旧 Release exact replay 不变。

## 5. 验证结果

- W2/架构聚焦：`18 PASS`；
- 全量单元：`737 PASS`；
- 全量契约：干净本地候选提交 `8401751` 上 `815 PASS / 0 FAIL`；
- 打包门禁：`WINDOWS_DESKTOP_X64` 开发包、build manifest、package manifest 和 SBOM 均通过；本地包 SHA-256 为 `7adcb81e1e35b3ae991e2664340d6f27782d7742319f1c5d485f601573538d8a`；
- 集成：`2 PASS / 3 SKIP`；跳过项要求外部 Prometheus、S3 和 PostgreSQL 环境变量，与 W2 Desktop 本地退出门无冲突；W1 已独立证明 PostgreSQL 16 基础、迁移、恢复和 registry/release 双引擎能力；
- 定向 Ruff 与 mypy：通过；
- 真实样本转换、重复散列和 TPAA 规范化：通过。
- 真实 NASA FLIGHT + 五类资格 companion 的正式 P1 全链、重启 exact replay：通过。

上游 FastAPI/Starlette 仍报告两条弃用警告；不影响 W2 业务断言，但应在后续依赖治理中清理。

## 6. 残余边界

本地关闭不等于整套产品生产可用：GUI 导入工作台属于 W4/W5；身份、授权、导出与保留策略属于 W3；硬件容量、持续负载和超大文件性能属于 W8；M5 正式资格、候选签名和上线仍属于后续发布门禁。当前生成物明确标记为 `DEVELOPMENT_NOT_M5_QUALIFIED`。W2 的 64 MiB 上限是安全边界，不是最终容量承诺。当前禁止推送和生产部署的约束继续有效。
