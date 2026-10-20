# W2 真实 Flight 数据导入与回放操作说明

状态：`CLOSED_LOCAL / PASS / NOT_PUSHED / NOT_DEPLOYED`（2026-10-20）。本文只描述本地 W2 资格范围，不代表整套产品已达到生产部署条件。

## 1. 受支持入口

生产组合公开以下受管入口：

- `GET /api/v1/sources/adapters`：列出适配器、版本、Source family、媒体类型及是否需要外部解码器；
- `POST /api/v1/sources/flight-csv/inspect`：只检查受管 Flight CSV，不写入对象存储；
- `POST /api/v1/sources/flight-csv/stage`：验证后分别不可变保存原始 CSV 与规范化 JSON，并返回可直接交给 P1 发布请求的 `source_document`；
- `GET /m1/releases/{release_id}/topology`：读取 Session、Episode 与 Stage；
- `GET /m1/releases/{release_id}/world-graph`：读取 World manifest、relation 和 TPAA-M chain；
- `POST /m1/releases/{release_id}/replay`：对已发布逻辑成员执行 exact replay；
- `GET /m1/releases/{release_id}/series`：按 Session 时间范围读取已封存序列，单次最多 5000 行；
- `POST /m1/episodes/{episode_id}/revisions`：创建不可变人工修订，不原位覆盖旧 Episode。

## 2. Flight CSV 契约

文件必须为 UTF-8，表头必须严格等于：

```text
source_time_us,session_time_us,p_deg_s,nz_g,heading_deg_true,tas_kt,mach,quality_mask
```

导入时必须显式提供规范 UUID 形式的 `session_id` 和 `aircraft_id`。系统按物理行顺序处理，先识别源时钟回跳并生成 `source_clock_segment`，再以严格递增的 `session_time_us` 建立 Session 时间；不得用排序掩盖回跳。单位转换为：`p_deg_s → rad/s`、`heading_deg_true → rad`、`tas_kt → m/s`，并为每行保留 `source_row_ordinal`。

固定 profile 为：

- Time：`EXPLICIT_SESSION_TIME_V1`；
- Reference frame：`BODY_NED_TRUE_V1`；
- Unit：`DEG_KNOT_SI_NORMALIZATION_V1`；
- Association：`EXPLICIT_AIRCRAFT_UUID_V1`。

## 3. 大文件和取消语义

HTTP 接收循环把传入片段切分为最多 1 MiB 的块，并在每块进入累计缓冲时检查 64 MiB 上限；超限返回 `413` 和 `SOURCE_ARTIFACT_SIZE_INVALID`，不会静默截断。客户端断开映射为 `W2_SOURCE_IMPORT_CANCELLED`。当前 64 MiB 是 W2 受控 profile 上限，不是 W8 性能容量结论。

## 4. NASA DASHlink 本地黄金样本

`nasa-dashlink-mat-v5` 只负责 MATLAB v5 头、媒体类型、大小和 SHA-256 的字节级检查；SciPy 解码被隔离在 `tools/data/convert_nasa_dashlink_mat.py`，不进入 TPAA 生产运行依赖。转换器严格检查 `ROLL`、`VRTG`、`TH`、`TAS` 和 `MACH` 的采样率、单位和描述，再生成上述受管 CSV。资格来源为 NASA DASHlink [Sample Flight Data](https://c3.ndc.nasa.gov/dashlink/projects/85/) 项目及其 [Tail 687 资源页](https://c3.ndc.nasa.gov/dashlink/resources/664/)。

本地资格命令：

```powershell
uv run --with scipy==1.16.3 python tools/data/convert_nasa_dashlink_mat.py SOURCE_MAT TARGET_CSV
```

真实数据及派生 CSV 必须置于 `evidence/local/w2/`；该目录已被 Git 忽略。不得把下载样本、派生明文或可识别信息提交到仓库，只记录来源描述、参数映射和散列。原始对象与规范化对象使用不同 artifact ID，任何同 URI 异内容写入都会失败关闭。

## 5. 操作顺序

1. 调用适配器清单，确认 `tpaa-flight-recorder-csv` 版本；
2. 调用 inspect，审阅行数、时间区间、时钟分段、缺失计数与 mapping manifest 散列；
3. 为 raw、canonical、Source、stream 分配互不相同的规范 UUID；
4. 调用 stage，保存返回的 `source_document`；
5. 将该 `source_document` 放入既有 P1 发布请求的 `source_documents`；
6. 等待 job 成功并读取 topology、world graph 和 series；
7. 重启本地运行时后按相同 `release_id` 调用 replay，比较 `manifest_hash` 与 `logical_membership_sha256`；
8. 如需更正 Episode 边界，创建 revision；旧 Release 的 replay 必须保持不变。

任何未知表头、非有限数值、非递增 Session 时间、非法 UUID、时间越界、对象散列冲突、缺失 Release 或损坏 Parquet 均必须失败关闭，不得自动猜测或覆盖历史数据。
