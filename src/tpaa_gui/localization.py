"""Simplified-Chinese presentation localization for the Desktop adapter.

The service and storage contracts intentionally keep their stable English codes.
This module translates only text owned by Qt widgets, so localization cannot
change API payloads, persisted evidence, hashes, or release-gate decisions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

EXACT_TRANSLATIONS: Mapping[str, str] = {
    "Application shell initialized": "应用程序界面已初始化",
    "Runtime diagnostics": "运行时诊断",
    "Analysis workspace": "分析工作区",
    "Primary page navigation": "主页面导航",
    "R3.3 governed P01 through P13 page catalogue": "R3.3 受控 P01 至 P13 页面目录",
    "Training Session List": "训练会话列表",
    "Session / Episode & Platform Performance": "会话／架次与平台性能",
    "Interactive Evidence / Episode Debrief": "交互式证据／架次复盘",
    "Individual Training Assessment": "个人训练评估",
    "Team / Package / Mission Assessment": "团队／编队／任务评估",
    "Aircraft Capability Digital Twin": "飞机能力数字孪生",
    "Aircraft Model Capability Profile": "机型能力画像",
    "Context Adjustment / Capability Separation": "情境校正／能力分离",
    "Aircraft / Mission-System Observed Trend / Capability Evolution": "飞机／任务系统观测趋势与能力演化",
    "Longitudinal Human / Team": "人员／团队纵向分析",
    "Course / Unit / Joint-LVC & Planning": "课程／单位／联合 LVC 与规划",
    "Data Quality & Observation Eligibility": "数据质量与观测资格",
    "Profile / Version / Publication / Model Governance": "画像／版本／发布／模型治理",
    "Training Sessions": "训练会话",
    "Episode Review": "架次复盘",
    "Human Capability": "人员能力",
    "Team Capability": "团队能力",
    "Aircraft Capability": "飞机能力",
    "Course & Unit": "课程与单位",
    "Data Quality": "数据质量",
    "Governance": "治理",
    "No governed content": "无受控内容",
    "No Session selected": "未选择会话",
    "Context: exact selection required": "上下文：必须精确选择",
    "Episode —  |  Stage —  |  Release —": "架次 —  |  阶段 —  |  发布 —",
    "Data confidence: unavailable": "数据置信度：不可用",
    "Detail & Evidence": "详情与证据",
    "Runtime": "运行时",
    "Selection: P01": "当前选择：P01",
    "Keyboard: Tab / Shift+Tab  •  resizable panels": "键盘：Tab／Shift+Tab  •  面板可调整大小",
    "M1 Session Browser": "M1 会话浏览器",
    "Synthetic fixture": "合成测试数据",
    "Explicit upstream/test binding required": "必须显式绑定上游或测试数据",
    "Import → Compute → Publish": "导入 → 计算 → 发布",
    "Release": "发布",
    "Context / Mission Header": "上下文／任务标题",
    "Master Timeline / Stage lane": "主时间轴／阶段泳道",
    "Metrics / Detail / Evidence": "指标／详情／证据",
    "Quality / Failure states": "质量／故障状态",
    "Replay selected Release": "重放所选发布",
    "Session / Release": "会话／发布",
    "Data Quality / Metric Evidence": "数据质量／指标证据",
    "Master timeline": "主时间轴",
    "Media / transcript": "媒体／文字记录",
    "Bookmarks": "书签",
    "Playlists": "播放列表",
    "Final Release Gate": "最终发布门禁",
    "External Capabilities": "外部能力",
    "Operations Acceptance": "运行验收",
    "Unavailable": "不可用",
    "Refresh": "刷新",
    "Load": "加载",
    "Open": "打开",
    "Close": "关闭",
    "Cancel": "取消",
    "Apply": "应用",
    "Approve": "批准",
    "Reject": "拒绝",
    "Export": "导出",
    "Import": "导入",
    "Search": "搜索",
    "Filter": "筛选",
    "Overview": "概览",
    "Evidence": "证据",
    "Diagnostics": "诊断",
    "Timeline": "时间轴",
    "Summary": "摘要",
    "Details": "详情",
    "Status": "状态",
    "Reason": "原因",
    "Actions": "操作",
    "Metric": "指标",
    "Value": "值",
    "Count": "数量",
    "Name": "名称",
    "Description": "说明",
    "ALL TYPES": "所有类型",
    "ALL DATA STATUS": "所有数据状态",
    "Select a governed object to inspect exact identity.": "选择受控对象以查看精确标识。",
    "Exact governed snapshot not loaded": "尚未加载精确受控快照",
    "Observation Eligibility": "观测资格",
    "Refresh exact Releases": "刷新精确发布列表",
    "Evidence remains bound to immutable observations.": "证据始终绑定到不可变观测。",
    "Provenance and chain identity are not reconstructed.": "不在界面中重建溯源信息和链路标识。",
    "Evidence path: Twin → Estimate → Attribution → Observation → Episode/Stage → Evidence": "证据路径：数字孪生 → 估计 → 归因 → 观测 → 架次／阶段 → 证据",
    "P11 · Course / Unit / Joint-LVC & Planning · exact immutable revisions only": "P11 · 课程／单位／联合 LVC 与规划 · 仅允许精确不可变修订",
    "Select a governed TPAA P1 request manifest. Inline source JSON is staged as immutable managed artifacts before BUILD_P1_RELEASE is submitted.": "选择受控的 TPAA P1 请求清单。提交 BUILD_P1_RELEASE 前，内联数据源 JSON 将暂存为不可变受管制品。",
    "N/A": "不适用",
    "session_id / episode_id / stage_id / scope / subject / session_time / release_id": "会话 ID／架次 ID／阶段 ID／范围／主体／会话时间／发布 ID",
}


# Long phrases are replaced before individual terms.  Entries are presentation
# language only; stable identifiers such as release_id do not match because an
# underscore is a word character.
PHRASE_TRANSLATIONS: tuple[tuple[str, str], ...] = (
    ("Session / Episode & Platform Performance", "会话／架次与平台性能"),
    ("Interactive Evidence / Episode Debrief", "交互式证据／架次复盘"),
    ("Individual Training Assessment", "个人训练评估"),
    ("Team / Package / Mission Assessment", "团队／编队／任务评估"),
    ("Aircraft Capability Digital Twin", "飞机能力数字孪生"),
    ("Aircraft Model Capability Profile", "机型能力画像"),
    ("Context Adjustment / Capability Separation", "情境校正／能力分离"),
    (
        "Aircraft / Mission-System Observed Trend / Capability Evolution",
        "飞机／任务系统观测趋势与能力演化",
    ),
    ("Longitudinal Human / Team", "人员／团队纵向分析"),
    ("Course / Unit / Joint-LVC & Planning", "课程／单位／联合 LVC 与规划"),
    ("Data Quality & Observation Eligibility", "数据质量与观测资格"),
    ("Profile / Version / Publication / Model Governance", "画像／版本／发布／模型治理"),
    ("Training Session List", "训练会话列表"),
    ("Metric instance", "指标实例"),
    ("no current/latest fallback", "不回退到当前／最新版本"),
    ("no current/latest alias", "无当前／最新别名"),
    ("exact selection required", "必须精确选择"),
    ("fail-closed default retained", "保留故障关闭默认值"),
    ("failed closed", "已按故障关闭处理"),
    ("Discovery failed closed", "发现过程失败，已关闭"),
    ("discovery failed closed", "发现过程失败，已关闭"),
    ("exact governed workspace", "精确受控工作区"),
    ("exact assessment history", "精确评估历史"),
    ("exact assessment", "精确评估"),
    ("exact observed trend", "精确观测趋势"),
    ("exact model evidence", "精确模型证据"),
    ("exact review", "精确审查"),
    ("exact Release", "精确发布"),
    ("immutable approval revision", "不可变批准修订"),
    ("immutable revision", "不可变修订"),
    ("immutable snapshots", "不可变快照"),
    ("immutable history", "不可变历史"),
    ("immutable model history", "不可变模型历史"),
    ("immutable longitudinal releases", "不可变纵向发布"),
    ("immutable Releases", "个不可变发布"),
    ("governed reviewer transition", "受控审查人流转"),
    ("Recommendation approval transition", "建议批准流转"),
    ("independent review reason", "独立审查原因"),
    ("review/approval/rejection reason", "审查／批准／驳回原因"),
    ("runtime gates", "运行时门禁"),
    ("model registry", "模型注册表"),
    ("recommendation history", "建议历史"),
    ("media history", "媒体历史"),
    ("assessment history", "评估历史"),
    ("Release history", "发布历史"),
    ("Session Browser", "会话浏览器"),
    ("Mission Header", "任务标题"),
    ("Master Timeline", "主时间轴"),
    ("Stage lane", "阶段泳道"),
    ("Detail / Evidence", "详情／证据"),
    ("Quality / Failure states", "质量／故障状态"),
    ("Role view", "角色视图"),
    ("Training workspace", "训练工作区"),
    ("Historical replay", "历史重放"),
    ("Historical Release ID", "历史发布 ID"),
    ("Load historical Release", "加载历史发布"),
    ("Open Evidence", "打开证据"),
    ("Foundation metrics", "基础指标"),
    ("Metric family", "指标族"),
    ("Observation lane", "观测泳道"),
    ("Association contribution", "关联贡献"),
    ("model profiles", "模型画像"),
    ("Course / Unit", "课程／单位"),
    ("Joint-LVC contract", "联合 LVC 契约"),
    ("Media / transcript", "媒体／文字记录"),
    ("Data confidence", "数据置信度"),
    ("Capability dimension", "能力维度"),
    ("Capability type", "能力类型"),
    ("Aircraft model id", "飞机型号 ID"),
    ("Aircraft instance id", "飞机实例 ID"),
    ("Subject entity id", "主体实体 ID"),
)


TERM_TRANSLATIONS: Mapping[str, str] = {
    "Application": "应用程序",
    "shell": "界面",
    "initialized": "已初始化",
    "Runtime": "运行时",
    "runtime": "运行时",
    "diagnostics": "诊断",
    "Diagnostics": "诊断",
    "Readiness": "就绪状态",
    "Backend": "后端",
    "Lifecycle": "生命周期",
    "Mismatches": "不匹配项",
    "Build": "构建",
    "expected": "预期",
    "observed": "实测",
    "Observed": "实测值",
    "Adjusted": "校正值",
    "Residual": "残差",
    "Uncertainty": "不确定性",
    "Baseline": "基线",
    "schema": "模式",
    "Product": "产品",
    "spine": "主链",
    "Semantic": "语义",
    "layers": "层级",
    "Session": "会话",
    "Sessions": "会话",
    "Episode": "架次",
    "Stage": "阶段",
    "Release": "发布",
    "Releases": "发布",
    "Context": "上下文",
    "Workflow": "工作流",
    "Cursor": "游标",
    "Metric": "指标",
    "Metrics": "指标",
    "Evidence": "证据",
    "Replay": "重放",
    "Navigation": "导航",
    "Selection": "当前选择",
    "State": "状态",
    "Reasons": "原因",
    "Reason": "原因",
    "Training": "训练",
    "Provenance": "溯源信息",
    "Historical": "历史",
    "Status": "状态",
    "Discovery": "发现",
    "Refresh": "刷新",
    "Load": "加载",
    "Open": "打开",
    "Create": "创建",
    "Published": "已发布",
    "published": "已发布",
    "required": "必填",
    "Required": "必须",
    "available": "可用",
    "unavailable": "不可用",
    "invalid": "无效",
    "empty": "为空",
    "selected": "已选择",
    "history": "历史",
    "revision": "修订",
    "revisions": "修订",
    "snapshot": "快照",
    "snapshots": "快照",
    "model": "模型",
    "Model": "模型",
    "profile": "画像",
    "profiles": "画像",
    "assessment": "评估",
    "Assessment": "评估",
    "recommendation": "建议",
    "Recommendation": "建议",
    "approval": "批准",
    "review": "审查",
    "reviewer": "审查人",
    "transition": "流转",
    "source": "数据源",
    "Source": "数据源",
    "quality": "质量",
    "Quality": "质量",
    "failure": "故障",
    "Failure": "故障",
    "timeline": "时间轴",
    "Timeline": "时间轴",
    "media": "媒体",
    "Media": "媒体",
    "transcript": "文字记录",
    "bookmark": "书签",
    "bookmarks": "书签",
    "playlist": "播放列表",
    "playlists": "播放列表",
    "fact": "事实",
    "forecast": "预测",
    "counterfactual": "反事实",
    "advisory": "建议",
    "governance": "治理",
    "Governance": "治理",
    "publication": "发布",
    "version": "版本",
    "permission": "权限",
    "permissions": "权限",
    "audit": "审计",
    "operations": "运行",
    "Operations": "运行",
    "acceptance": "验收",
    "Acceptance": "验收",
    "external": "外部",
    "External": "外部",
    "capabilities": "能力",
    "Capabilities": "能力",
    "gate": "门禁",
    "Gate": "门禁",
    "decision": "判定",
    "Decision": "判定",
    "summary": "摘要",
    "Summary": "摘要",
    "detail": "详情",
    "Detail": "详情",
    "value": "值",
    "Value": "值",
    "count": "数量",
    "Count": "数量",
    "name": "名称",
    "Name": "名称",
    "description": "说明",
    "Description": "说明",
    "action": "操作",
    "Actions": "操作",
    "course": "课程",
    "Course": "课程",
    "unit": "单位",
    "Unit": "单位",
    "planning": "规划",
    "Planning": "规划",
    "aircraft": "飞机",
    "Aircraft": "飞机",
    "mission": "任务",
    "Mission": "任务",
    "system": "系统",
    "System": "系统",
    "team": "团队",
    "Team": "团队",
    "individual": "个人",
    "Individual": "个人",
    "capability": "能力",
    "Capability": "能力",
    "trend": "趋势",
    "Trend": "趋势",
    "evolution": "演化",
    "Evolution": "演化",
    "comparison": "对比",
    "Comparison": "对比",
    "configuration": "配置",
    "Configuration": "配置",
    "identity": "标识",
    "Identity": "标识",
    "role": "角色",
    "Role": "角色",
    "user": "用户",
    "User": "用户",
    "records": "记录",
    "record": "记录",
    "items": "项",
    "item": "项",
    "results": "结果",
    "result": "结果",
    "none": "无",
    "None": "无",
    "error": "错误",
    "Error": "错误",
    "Page": "页面",
    "Select": "选择",
    "Metric instance": "指标实例",
    "Observation": "观测",
    "Audit": "审计",
}


STATE_TRANSLATIONS: Mapping[str, str] = {
    "NOT_READY": "未就绪",
    "SYSTEM_ERROR": "系统错误",
    "INSUFFICIENT": "证据不足",
    "UNAVAILABLE": "不可用",
    "AVAILABLE": "可用",
    "PUBLISHED": "已发布",
    "RUNNING": "运行中",
    "SUCCEEDED": "成功",
    "FAILED": "失败",
    "INVALID": "无效",
    "SELECTED": "已选择",
    "READY": "就绪",
    "EMPTY": "为空",
    "IDLE": "空闲",
    "NONE": "无",
    "N_A": "不适用",
    "STOPPED": "已停止",
    "UNKNOWN": "未知",
    "ACTIVE": "有效",
    "INACTIVE": "未启用",
    "APPROVED": "已批准",
    "REJECTED": "已驳回",
    "PENDING": "待处理",
    "SUBMITTED": "已提交",
    "ACCEPTED": "已接受",
    "DISABLED": "已禁用",
    "ENABLED": "已启用",
    "NOT_CONFIGURED": "未配置",
    "PASS": "通过",
    "FAIL": "失败",
    "HUMAN": "个人",
    "TEAM": "团队",
    "AIRCRAFT": "飞机",
    "MISSION_SYSTEM_INSTANCE": "任务系统实例",
    "ABSOLUTE_SESSION_TIME": "绝对会话时间",
    "STAGE_ALIGNED": "阶段对齐",
    "IN_REVIEW": "审查中",
    "RELEASED": "已发布",
    "LIVE": "实装",
    "SIM": "仿真",
    "PARTIAL": "部分",
}


# Exact results after the generic terminology pass.  Keeping these separate
# makes the glossary reusable for dynamic text while allowing polished Chinese
# for the design-owned explanatory sentences.
SECOND_PASS_TRANSLATIONS: Mapping[str, str] = {
    "角色视图: not loaded · server authorization remains authoritative": "角色视图：未加载；服务器授权始终具有最终效力",
    "Apply authenticated 角色 view": "应用已认证角色视图",
    "P13  Profile / Version / Publication / 模型 治理": "P13  画像／版本／发布／模型治理",
    "Profiles, contexts, releases, models, 权限, 审计, and 运行时": "画像、上下文、发布、模型、权限、审计与运行时治理",
    "加载 exact 治理 快照": "加载精确治理快照",
    "发布 / Publication / 溯源信息": "发布／发布记录／溯源信息",
    "Catalog / Profiles / 上下文": "目录／画像／上下文",
    "Models / Twins": "模型／数字孪生",
    "Permissions / Approvals": "权限／批准",
    "Audit / 运行时": "审计／运行时",
    "Formal release: NOT LOADED (fail-closed)": "正式发布：未加载（故障关闭）",
    "治理: 精确发布 not loaded": "治理：未加载精确发布",
    "P12  Data 质量 & Observation Eligibility": "P12  数据质量与观测资格",
    "数据源, World, time, association, and observation eligibility evidence": "数据源、世界模型、时间、关联及观测资格证据",
    "加载 Data 质量": "加载数据质量",
    "Overall Data 质量": "总体数据质量",
    "World 能力": "世界模型能力",
    "M Coverage": "M 层覆盖率",
    "Observation Eligibility": "观测资格",
    "Time / Reference / Association 质量": "时间／参考／关联质量",
    "数据源 / World Coverage": "数据源／世界模型覆盖率",
    "质量: 精确发布 not loaded": "质量：未加载精确发布",
    "P11  课程／单位 / Joint-LVC & 规划": "P11  课程／单位／联合 LVC 与规划",
    "课程, 单位, Joint-LVC, 预测, and what-if 规划": "课程、单位、联合 LVC、预测与假设规划",
    "P11 · 课程／单位 / Joint-LVC & 规划 · exact 不可变修订s only": "P11 · 课程／单位／联合 LVC 与规划 · 仅允许精确不可变修订",
    "课程／单位 & Joint-LVC": "课程／单位与联合 LVC",
    "P6 规划 & Approval": "P6 规划与批准",
    "媒体 / Transcript / Compare": "媒体／文字记录／对比",
    "模型 Registry & Gates": "模型注册表与门禁",
    "模型 registry and 外部 能力 activation gates": "模型注册表与外部能力激活门禁",
    "No exact 模型 已选择": "未选择精确模型",
    "门禁 state": "门禁状态",
    "Action enabled": "操作已启用",
    "必须 evidence": "必需证据",
    "验收 SHA-256": "验收证据 SHA-256",
    "模型 rollback disabled — monitoring endpoint and independent 批准 必填": "模型回滚已禁用——必须具备监控端点和独立批准",
    "外部 plugin install disabled — trust root and sandbox not configured": "外部插件安装已禁用——尚未配置信任根和沙箱",
    "媒体／文字记录 / master-time 审查 and exact compare": "媒体／文字记录、主时间审查与精确对比",
    "No exact 媒体 快照 已选择": "未选择精确媒体快照",
    "Export disabled — accepted object-store/redaction 门禁 必填": "导出已禁用——必须通过对象存储与脱敏门禁验收",
    "P6 Forecast / Counterfactual / 建议 规划": "P6 预测／反事实／建议规划",
    "The four lanes have permanent visual semantics. Forecast and 反事实 outputs are projections and can never be upgraded to factual 历史 by this GUI.": "四条泳道具有固定视觉语义。预测和反事实输出属于推演结果，本 GUI 绝不会将其提升为事实历史。",
    "ACTUAL · immutable factual 历史": "实际 · 不可变事实历史",
    "FORECAST · predictive projection": "预测 · 预测性推演",
    "COUNTERFACTUAL · scenario projection": "反事实 · 情景推演",
    "RECOMMENDATION · governed 建议": "建议 · 受控建议",
    "No 批准 操作 submitted": "尚未提交批准操作",
    "课程／单位 analytics and 联合 LVC 契约 快照": "课程／单位分析与联合 LVC 契约快照",
    "Aggregates obey cohort suppression. A gateway 快照 proves mapping lineage only; it never claims a live 外部 connection.": "汇总结果遵守群组抑制规则。网关快照仅证明映射溯源，不代表存在实时外部连接。",
    "加载 联合 LVC 契约": "加载联合 LVC 契约",
    "No exact 快照 已选择": "未选择精确快照",
    "P10  Longitudinal Human / 团队": "P10  人员／团队纵向分析",
    "Comparable 个人 and 团队 longitudinal views": "可比的个人与团队纵向视图",
    "Longitudinal: select HUMAN or TEAM; the two lanes are never aggregated.": "纵向分析：请选择个人或团队；两条泳道绝不混合汇总。",
    "Exact 不可变修订s only. Comparable scenarios/configurations must be 已发布 by the server; no GUI score 趋势 or 团队-to-个人 allocation is calculated.": "仅允许精确不可变修订。可比情景与配置必须由服务器发布；GUI 不计算得分趋势，也不进行团队到个人的分摊。",
    "飞机 and 任务-系统 实测 trends and 能力 演化": "飞机与任务系统观测趋势及能力演化",
    "P08  上下文 Adjustment / 能力 Separation": "P08  情境校正／能力分离",
    "Association-only attribution, normalization, and CAP-L2 separation": "仅关联归因、归一化及 CAP-L2 分离",
    "加载 对比 + 诊断 + evidence bindings": "加载对比、诊断与证据绑定",
    "MODEL-CONDITIONED ASSOCIATION ONLY · not causal attribution · not percentage unless the 已发布 scale explicitly says so.": "仅限模型条件关联；不代表因果归因；除非发布的量表明确说明，否则不表示百分比。",
    "Factor": "因素",
    "原因 / identifiability": "原因／可辨识性",
    "P07  飞机 模型 能力 Profile": "P07  机型能力画像",
    "模型, block, and 配置 能力 画像": "型号、批次与配置能力画像",
    "Only a server-已发布 模型/block/配置 cohort is admissible. The GUI will not aggregate 飞机 Twins. OUTLIER means 审查, never automatic fault.": "仅允许服务器发布的型号／批次／配置群组。GUI 不汇总单机数字孪生；异常点仅表示需要审查，绝不自动判定故障。",
    "P06  飞机 能力 Digital Twin": "P06  飞机能力数字孪生",
    "飞机 CAP-L3 and immutable digital-twin estimates": "飞机 CAP-L3 与不可变数字孪生估计",
    "加载 exact Twin 修订 and estimate": "加载精确数字孪生修订与估计",
    "Twin: 不可用": "数字孪生：不可用",
    "证据 path: Twin → Estimate → Attribution → Observation → 架次/阶段 → 证据": "证据路径：数字孪生 → 估计 → 归因 → 观测 → 架次／阶段 → 证据",
    "Reference-condition estimate only; never fed back as same-架次 实测 truth.": "仅表示参考条件估计；绝不回写为同一架次的观测事实。",
    "P05  团队 / Package / 任务 评估": "P05  团队／编队／任务评估",
    "WVR, BVR, Strike, 团队, package, and 任务 评估": "WVR、BVR、突击、团队、编队与任务评估",
    "TEAM / PACKAGE / MISSION only · composition is immutable. 个人 members remain evidence references, never derived personal scores.": "仅限团队／编队／任务；组成关系不可变。个人成员仅作为证据引用，绝不派生个人得分。",
    "评估: no exact 修订 已选择": "评估：未选择精确修订",
    "Governed 审查人 流转": "受控审查人流转",
    "个人 Basic and human-machine 评估": "个人基础能力与人机协同评估",
    "INDIVIDUAL only · automatic 评估, instructor annotation, and final 批准 remain separate products. 团队 结果 are never copied here.": "仅限个人；自动评估、教员批注与最终批准始终是独立产品。团队结果绝不复制到此处。",
    "P03  Interactive 证据 / 架次 Debrief": "P03  交互式证据／架次复盘",
    "发布-bound replay, master 时间轴, evidence, and debrief": "发布绑定重放、主时间轴、证据与复盘",
    "加载 exact replay": "加载精确重放",
    "< Previous 阶段": "< 上一阶段",
    "Next 阶段 >": "下一阶段 >",
    "指标 / Observation": "指标／观测",
    "Linked Flight Plot": "联动飞行图",
    "媒体 / Transcript": "媒体／文字记录",
    "主时间轴 · 阶段 / W / P / A / J / M / Observation": "主时间轴 · 阶段／W／P／A／J／M／观测",
    "重放: 精确发布 not loaded": "重放：未加载精确发布",
    "P02  会话 / 架次 & Platform Performance": "P02  会话／架次与平台性能",
    "会话 and 架次 overview with 飞机 and 任务-系统 observations": "包含飞机与任务系统观测的会话和架次概览",
    "加载 会话 / 架次 overview": "加载会话／架次概览",
    "上下文/Profile": "上下文／画像",
    "Data Confidence": "数据置信度",
    "飞机 Performance": "飞机性能",
    "任务-系统 Performance": "任务系统性能",
    "Reference Truth 质量": "参考真值质量",
    "Exact 发布 not loaded": "未加载精确发布",
    "P01  训练 会话 List": "P01  训练会话列表",
    "会话 import, immutable release status, and filtering": "会话导入、不可变发布状态与筛选",
    "会话 search & filters": "会话搜索与筛选",
    "会话 code / immutable 会话 ID": "会话代码／不可变会话 ID",
    "Governed real-file import → P1 发布": "受控真实文件导入 → P1 发布",
    "Select a governed TPAA P1 request manifest. Inline 数据源 JSON is staged as immutable managed artifacts before BUILD_P1_RELEASE is submitted.": "选择受控的 TPAA P1 请求清单。提交 BUILD_P1_RELEASE 前，内联数据源 JSON 将暂存为不可变受管制品。",
    "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1 JSON file": "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1 JSON 文件",
    "Browse…": "浏览…",
    "1  Validate & stage sources": "1  校验并暂存数据源",
    "2  构建 & publish P1 发布": "2  构建并发布 P1",
    "Formal compute job ID": "正式计算作业 ID",
    "刷新 job status": "刷新作业状态",
    "Import: waiting for a real governed file": "导入：等待选择真实受控文件",
    "Latest 已发布 state": "最新发布状态",
    "Immutable 会话 ID": "不可变会话 ID",
    "Exact 发布 selection 必填": "必须选择精确发布",
    "重放: 精确发布 selection 必填": "重放：必须选择精确发布",
    "为空 · no 评估 修订 is 已发布 for this 角色": "为空 · 此角色没有已发布的评估修订",
    "为空 · no 已发布 exact Twin/Estimate pair": "为空 · 没有已发布的精确数字孪生／估计组合",
    "Block / 配置": "批次／配置",
    "Independent episodes": "独立架次",
    "Profile 版本": "画像版本",
    "As-of": "截至时间",
    "为空 · no P2 estimate 已发布": "为空 · 尚未发布 P2 估计",
    "为空 · no 实测 趋势 release": "为空 · 尚无观测趋势发布",
    "Lane": "泳道",
    "Subject": "主体",
    "Exact 修订": "精确修订",
    "Knowledge/publish time": "知识时间／发布时间",
    "会话 scope": "会话范围",
    "为空 · no 模型 修订 is visible for this 角色": "为空 · 此角色无可见模型修订",
    "为空 · no 媒体 debrief 快照 is 可用": "为空 · 没有可用的媒体复盘快照",
    "为空 · exact linked P6 修订 are 必填": "为空 · 必须提供精确关联的 P6 修订",
    "为空 · no JOINT_LVC_GATEWAY 快照 is 可用": "为空 · 没有可用的 JOINT_LVC_GATEWAY 快照",
    "质量: 精确发布 selection 必填": "质量：必须选择精确发布",
    "治理: 精确发布 selection 必填": "治理：必须选择精确发布",
}


DYNAMIC_TRANSLATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^会话: (\d+) governed 记录$"), r"会话：\1 条受控记录"),
    (re.compile(r"^已发布 immutable 模型画像: (\d+)$"), r"已发布不可变模型画像：\1"),
    (
        re.compile(
            r"^HUMAN exact 历史: (\d+) 修订\(s\) · TEAM 结果 are never presented as HUMAN scores$"
        ),
        r"个人精确历史：\1 个修订 · 团队结果绝不作为个人得分呈现",
    ),
    (re.compile(r"^(\d+) revision\(s\)$"), r"\1 个修订"),
)


FINAL_TERM_TRANSLATIONS: Mapping[str, str] = {
    "Type": "类型",
    "Data": "数据",
    "Latest": "最新",
    "Immutable": "不可变",
    "immutable": "不可变",
    "governed": "受控",
    "Governed": "受控",
    "exact": "精确",
    "Exact": "精确",
    "selection": "选择",
    "Block": "批次",
    "Independent": "独立",
    "episodes": "架次",
    "Profile": "画像",
    "As-of": "截至时间",
    "Lane": "泳道",
    "Subject": "主体",
    "Knowledge": "知识",
    "publish": "发布",
    "scope": "范围",
    "linked": "关联",
    "visible": "可见",
    "debrief": "复盘",
}


def translate_visible_text(text: str) -> str:
    """Translate user-facing Qt text while preserving technical identifiers."""

    if not text:
        return text
    normalized = text.replace("鈫?", "→").replace("路", "·")
    exact = EXACT_TRANSLATIONS.get(normalized)
    if exact is not None:
        return exact
    translated = normalized
    for source, target in PHRASE_TRANSLATIONS:
        translated = translated.replace(source, target)
    for source, target in STATE_TRANSLATIONS.items():
        translated = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(source)}(?![A-Za-z0-9_])", target, translated
        )
    for source, target in TERM_TRANSLATIONS.items():
        translated = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(source)}(?![A-Za-z0-9_])", target, translated
        )
    polished = SECOND_PASS_TRANSLATIONS.get(translated, translated)
    if polished != translated:
        return polished
    for pattern, replacement in DYNAMIC_TRANSLATIONS:
        polished = pattern.sub(replacement, polished)
    for source, target in FINAL_TERM_TRANSLATIONS.items():
        polished = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(source)}(?![A-Za-z0-9_])",
            target,
            polished,
        )
    return polished


def _translate_item(item: Any) -> None:
    if item is None or not hasattr(item, "text") or not hasattr(item, "setText"):
        return
    try:
        text = item.text()
    except TypeError:
        return
    if isinstance(text, str):
        translated = translate_visible_text(text)
        if translated != text:
            item.setText(translated)


def localize_widget(widget: Any, qt_widgets: Any) -> None:
    """Localize one Qt widget without touching its domain payload data."""

    text_types = tuple(
        cls
        for cls in (
            getattr(qt_widgets, "QLabel", None),
            getattr(qt_widgets, "QPushButton", None),
            getattr(qt_widgets, "QCheckBox", None),
            getattr(qt_widgets, "QRadioButton", None),
        )
        if cls is not None
    )
    if text_types and isinstance(widget, text_types):
        text = widget.text()
        translated = translate_visible_text(text)
        if translated != text:
            widget.setText(translated)

    group_box = getattr(qt_widgets, "QGroupBox", None)
    if group_box is not None and isinstance(widget, group_box):
        title = widget.title()
        translated = translate_visible_text(title)
        if translated != title:
            widget.setTitle(translated)

    line_edit = getattr(qt_widgets, "QLineEdit", None)
    if line_edit is not None and isinstance(widget, line_edit):
        placeholder = widget.placeholderText()
        translated = translate_visible_text(placeholder)
        if translated != placeholder:
            widget.setPlaceholderText(translated)

    text_edits = tuple(
        cls
        for cls in (
            getattr(qt_widgets, "QPlainTextEdit", None),
            getattr(qt_widgets, "QTextEdit", None),
        )
        if cls is not None
    )
    if text_edits and isinstance(widget, text_edits):
        text = widget.toPlainText()
        translated = translate_visible_text(text)
        if translated != text:
            widget.setPlainText(translated)

    tabs = getattr(qt_widgets, "QTabWidget", None)
    if tabs is not None and isinstance(widget, tabs):
        for index in range(widget.count()):
            text = widget.tabText(index)
            translated = translate_visible_text(text)
            if translated != text:
                widget.setTabText(index, translated)

    combo = getattr(qt_widgets, "QComboBox", None)
    if combo is not None and isinstance(widget, combo):
        label_mode = getattr(combo, "LabelDrawingMode", None)
        if label_mode is not None and hasattr(widget, "setLabelDrawingMode"):
            widget.setLabelDrawingMode(label_mode.UseDelegate)

    table = getattr(qt_widgets, "QTableWidget", None)
    if table is not None and isinstance(widget, table):
        for column in range(widget.columnCount()):
            _translate_item(widget.horizontalHeaderItem(column))
        for row in range(widget.rowCount()):
            _translate_item(widget.verticalHeaderItem(row))

    tree = getattr(qt_widgets, "QTreeWidget", None)
    if tree is not None and isinstance(widget, tree):
        header = widget.headerItem()
        if header is not None:
            for column in range(widget.columnCount()):
                text = header.text(column)
                translated = translate_visible_text(text)
                if translated != text:
                    header.setText(column, translated)

    dock = getattr(qt_widgets, "QDockWidget", None)
    if dock is not None and isinstance(widget, dock):
        title = widget.windowTitle()
        translated = translate_visible_text(title)
        if translated != title:
            widget.setWindowTitle(translated)

    if hasattr(widget, "toolTip") and hasattr(widget, "setToolTip"):
        tooltip = widget.toolTip()
        translated = translate_visible_text(tooltip)
        if translated != tooltip:
            widget.setToolTip(translated)
    if hasattr(widget, "accessibleName") and hasattr(widget, "setAccessibleName"):
        name = widget.accessibleName()
        translated = translate_visible_text(name)
        if translated != name:
            widget.setAccessibleName(translated)
    if hasattr(widget, "accessibleDescription") and hasattr(widget, "setAccessibleDescription"):
        description = widget.accessibleDescription()
        translated = translate_visible_text(description)
        if translated != description:
            widget.setAccessibleDescription(translated)


def localize_widget_tree(root: Any, qt_widgets: Any) -> None:
    """Localize a widget and all QWidget descendants."""

    localize_widget(root, qt_widgets)
    widget_type = getattr(qt_widgets, "QWidget", None)
    if widget_type is None or not hasattr(root, "findChildren"):
        return
    for widget in root.findChildren(widget_type):
        localize_widget(widget, qt_widgets)


def install_chinese_localization(
    qt_core: Any,
    qt_widgets: Any,
    app: Any,
    window: Any,
) -> Any:
    """Install dynamic localization for text changed after user actions."""

    localize_widget_tree(window, qt_widgets)
    if not all(
        (
            hasattr(qt_core, "QObject"),
            hasattr(qt_core, "QEvent"),
            hasattr(app, "installEventFilter"),
        )
    ):
        return None

    class _ChineseDisplayDelegate(qt_widgets.QStyledItemDelegate):  # type: ignore[misc]
        def displayText(self, value: Any, locale: Any) -> str:  # noqa: N802
            del locale
            return translate_visible_text(str(value))

    delegates: list[Any] = []
    abstract_view = getattr(qt_widgets, "QAbstractItemView", None)
    if abstract_view is not None and hasattr(window, "findChildren"):
        for view in window.findChildren(abstract_view):
            delegate = _ChineseDisplayDelegate(view)
            view.setItemDelegate(delegate)
            delegates.append(delegate)
    window._tpaa_chinese_display_delegates = delegates

    class _ChineseUiEventFilter(qt_core.QObject):  # type: ignore[misc]
        def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802
            event_type = event.type()
            watched_type = getattr(qt_widgets, "QWidget", None)
            if watched_type is not None and isinstance(watched, watched_type):
                if event_type in {
                    qt_core.QEvent.Type.Show,
                    qt_core.QEvent.Type.Paint,
                    qt_core.QEvent.Type.LayoutRequest,
                    qt_core.QEvent.Type.ToolTipChange,
                }:
                    localize_widget(watched, qt_widgets)
            return False

    event_filter = _ChineseUiEventFilter(app)
    app.installEventFilter(event_filter)
    window._tpaa_chinese_ui_event_filter = event_filter
    return event_filter


__all__ = [
    "EXACT_TRANSLATIONS",
    "install_chinese_localization",
    "localize_widget",
    "localize_widget_tree",
    "translate_visible_text",
]
