# W5 核心用户工作流关闭评审

日期：2026-10-25  
结论：`CLOSED_LOCAL / PASS / NOT_PUSHED / NOT_DEPLOYED / NOT_PRODUCTION_READY`

## 关闭范围

W5 按 05G R3.3 完成 P01、P02、P03、P12、P13 核心闭环：真实文件经不可变源暂存进入受控 P1 worker 和正式 Release；Session/Episode、三类 subject lane、Master Timeline、Metric、Observation、Evidence、Data Quality 与 Governance 均由精确 Release 身份贯通。

## 硬门禁结论

- 真实 JSON 文件导入、6 类源暂存、P1 计算和 Release 发布通过。
- Observation/Assessment 到 Evidence 的验收轨迹为 3 次主要交互，满足不超过 4 次。
- 历史重放返回 `EXACT_REPLAY`，`current_latest_fallback_used=false`。
- `N/A`、Unknown/未计算、Review、Failure 使用不同语义，不互相替代。
- P03 只消费精确 geodetic presentation；输入缺少该载荷时明确 fail-closed，不绘制推断轨迹。
- P01 长任务在 GUI 后台线程执行，不冻结 Qt 主线程。

## 运行期整改

真实 Desktop 验收暴露并关闭了两项此前仅单元测试无法发现的问题：

1. Windows 子进程中的大体积 `multiprocessing` 启动负载产生管道背压。正式 worker 改为固定模块、二进制 stdio、无 shell 的一次性隔离子进程，仍保留 allowlist、身份校验、容量、取消和 120 秒超时门禁；轻量 multiprocessing spawn 资格测试继续保留。
2. `/m1/releases/{id}/replay` 曾被路径分类器误判为产品发布。现明确归类为 `COMPUTE_EXECUTE`，INSTRUCTOR 可执行精确重放，发布权限未放宽。

## 证据

- 机器可读契约：`docs/gui/W5_CORE_WORKFLOW_CONTRACT.json`
- 符合性矩阵：`docs/compliance/W5_COMPLIANCE_MATRIX.json`
- Windows 真实链路：`evidence/local/w5/windows/w5-acceptance.json`
- 自动化：`tests/unit/gui/test_w5_core_workflows.py`
- 操作说明：`docs/operator/W5_P1_DESKTOP_WORKFLOW.md`

## 边界

W5 关闭不代表整套产品可生产部署。P04～P10 属于 W6，P11 属于 W7；真实生产身份设施、生产数据验收、签名发布、保护分支 CI 和生产部署均未执行。
