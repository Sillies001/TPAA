import "./style.css";
import registryJson from "../../../docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json";
import contractJson from "../../../baseline/CB-1.14.0/canonical/GUI_VIEW_CONTRACT.json";
import permissionJson from "../../../baseline/CB-1.14.0/canonical/GUI_PERMISSION_AUDIT_AUTHORITY.json";
import type {
  BatchRegistrationDTO,
  ForceFormationContextDTO,
  ImportTicketDTO,
} from "./generated/g4-batch.ts";
import { AsyncGateway, GatewayError, createGuiClient } from "./services/gateway.js";
import { selectImportSource } from "./services/nativeImport.js";
import {
  RIBBON_MODULES, applyPanelGeometry, beginLayout, fitCanvas, panel, renderMainMenu, renderSubmenu, statePanel,
} from "./shell.ts";
import { THEME_DEF, THEME_IDS, assignTheme, isTheme, type Theme } from "./themes.ts";

type UiState = "LOADING" | "EMPTY" | "READY" | "DEGRADED" | "ERROR" | "FORBIDDEN" | "N_A";
type AuthState = "LOADING" | "READY" | "DEGRADED" | "ERROR" | "FORBIDDEN";
type ModuleId = "overview" | "training" | "replay" | "equipment" | "support";
type ViewId = string;
interface View { id: ViewId; title: string; module: ModuleId; entry: string; perspectives: string[] }
interface Module { id: ModuleId; label: string; landing: ViewId }
interface Registry { view_count: number; modules: Module[]; views: View[] }
interface ViewContract {
  view_id: ViewId; module: ModuleId; entry_type: string; required_context: string[];
  allowed_predecessor: string[]; return_target: string | null; p_capabilities: string[];
  required_permissions: string[];
}
interface ContractDocument { views: ViewContract[] }
interface PermissionDocument { permissions: Array<{ permission_id: string; unknown_policy: string }> }
interface DomainSelection {
  batchId: string | null; sessionId: string | null; sortieId: string | null;
  releaseId: string | null; contextId: string | null; policyId: string | null;
  episodeId: string | null; stageId: string | null; weaponEventId: string | null;
  attackClusterId: string | null; formationId: string | null; memberId: string | null;
  perspective: string; evaluatedSide: string | null; scope: string;
}
interface ReplayState {
  masterTimeCursorUs: number | null; selectionStartUs: number | null; selectionEndUs: number | null;
  mediaId: string | null; transcriptId: string | null;
}
interface Frame { viewId: ViewId; moduleId: ModuleId; domain: DomainSelection; replay: ReplayState }
interface V24Grant {
  sourceView: "V08"; eventCategory: "BVR"; releaseId: string; contextId: string;
  weaponEventId: string; attackClusterId: string; formationId: string;
}
interface Notice { viewId: ViewId; state: UiState; title: string; message: string; code: string }

/* ===== G6 V01 历史聚合读模型（TPAA_G6_HISTORICAL_OVERVIEW_V1，真实后端） ===== */
interface OverviewKpi {
  batch_count: number; sortie_count: number; episode_count: number;
  weapon_event_count: number; adjudicated_event_count: number;
  data_qualification_summary: { qualified: number; with_event_detail: number };
}
interface OverviewFilter {
  start_date: string; end_date: string; model: string; training_type: string;
  invalid_date_range: boolean;
}
interface ActivityPoint { batch_date: string; weapon_launch: number; engagement_process: number }
interface ActivityTrend { unit: string; points: ActivityPoint[] }
interface OutcomeTrend { adjudicated: number; pending: number }
interface CategoryComposition { note: string; total_weapon_events: number }
interface TaskMetricTrend {
  metric_id: string; label: string; unit: string | null; definition_version: string | null;
  status: string; numerator: number | null; denominator: number | null;
  value: string | null; reason: string | null;
}
interface EquipmentTrend {
  metric_id: string; label: string; unit: string; comparable: boolean; eligibility: string;
  reason: string | null; points: readonly { batch_date: string; value: string }[];
}
interface OverviewBatch {
  batch_id: string; batch_date: string; batch_training_type: string;
  sortie_count: number; episode_count: number; weapon_event_count: number;
  adjudicated_event_count: number; qualification_status: string; has_event_detail: boolean;
}
interface OverviewPayload {
  schema: string; query_context_id: string; filter: OverviewFilter; kpi: OverviewKpi;
  task_metric_trends: readonly TaskMetricTrend[]; activity_trend: ActivityTrend;
  outcome_trend: OutcomeTrend; category_composition: CategoryComposition;
  equipment_trends: readonly EquipmentTrend[]; batches: readonly OverviewBatch[];
  batch_set_fingerprint: string; aggregation_cutoff: string;
}
type OverviewTransport = "LOADING" | "READY" | "DEGRADED" | "ERROR";

/* ===== G7 V26 批次发射事件工作台（TPAA_G7_BATCH_EVENT_WORKBENCH_V1，真实后端） ===== */
interface BatchEventItem {
  weapon_event_id: string; revision_no: number; batch_id: string; cluster_id: string | null;
  category: string; t1_session_time_us: string; shooter_entity_id: string;
  target_entity_id: string | null; episode_id: string | null;
  weapon_terminal_state: string; adjudication_state: string;
  observation_window_state: string; classification_exception: boolean;
}
interface BatchEventsSummary {
  weapon_event_count: number; cluster_count: number;
  category_counts: Readonly<Record<string, number>>;
  adjudication_counts: Readonly<Record<string, number>>;
  classification_exception_count: number;
}
interface BatchEventsData {
  schema: string; request_id: string; batch_id: string; query_context_id: string;
  batch_context_id?: string | null;
  filter: {
    category: string; adjudication: string; cluster_id: string | null;
    entity_id: string | null; episode_id: string | null;
    start_time_us: string | null; end_time_us: string | null;
  };
  summary: BatchEventsSummary; items: BatchEventItem[];
  next_cursor: string | null; total_count: number;
}

const registry = registryJson as unknown as Registry;
const contracts = contractJson as unknown as ContractDocument;
const permissions = permissionJson as unknown as PermissionDocument;
const modules = new Map<ModuleId, Module>(registry.modules.map((item) => [item.id, item]));
const views = new Map(registry.views.map((item) => [item.id, item]));
const viewContracts = new Map(contracts.views.map((item) => [item.view_id, item]));
const permissionPolicies = new Map(permissions.permissions.map((item) => [item.permission_id, item]));
const asyncGateway = new AsyncGateway();
const guiClient = createGuiClient(asyncGateway);
const rootElement = document.querySelector<HTMLDivElement>("#app");
if (!rootElement) throw new Error("TPAA_GUI_ROOT_MISSING");
const root: HTMLDivElement = rootElement;

function validateRegistry(): void {
  const expected = Array.from({ length: 26 }, (_, i) => "V" + String(i + 1).padStart(2, "0"));
  if (registry.view_count !== 26 || registry.views.map((v) => v.id).join("|") !== expected.join("|") ||
      contracts.views.map((v) => v.view_id).join("|") !== expected.join("|")) {
    throw new Error("TPAA_V33_VIEW_REGISTRY_DRIFT");
  }
  if (modules.get("training")?.landing !== "V26") throw new Error("TPAA_TRAINING_LANDING_NOT_V26");
  const v24 = viewContracts.get("V24");
  if (v24?.entry_type !== "CONDITIONAL_V08_ONLY" || v24.allowed_predecessor.join("|") !== "V08" || v24.return_target !== "V08") {
    throw new Error("TPAA_V24_ENTRY_CONTRACT_DRIFT");
  }
}
validateRegistry();

function directV24Request(): boolean {
  const query = new URLSearchParams(window.location.search);
  const queryMatch = ["view", "view_id", "route", "page"].some((key) =>
    query.getAll(key).some((value) => value.trim().toUpperCase() === "V24"),
  );
  return queryMatch || /(?:^|[\/#?=&])V24(?:$|[\/?&#])/i.test(window.location.hash);
}
const directV24 = directV24Request();
const state = {
  navigation: {
    currentViewId: (directV24 ? "V08" : "V01") as ViewId,
    activeModuleId: (directV24 ? "training" : "overview") as ModuleId,
    approvedPredecessor: null as ViewId | null,
    deepLink: null as string | null,
    returnStack: [] as Frame[],
  },
  domainSelection: {
    batchId: null, sessionId: null, sortieId: null, releaseId: null, contextId: null, policyId: null,
    episodeId: null, stageId: null, weaponEventId: null, attackClusterId: null,
    formationId: null, memberId: null, perspective: "overview", evaluatedSide: null, scope: "batch",
  } as DomainSelection,
  replayState: {
    masterTimeCursorUs: null, selectionStartUs: null, selectionEndUs: null, mediaId: null, transcriptId: null,
  } as ReplayState,
  authorization: { status: "LOADING" as AuthState, permissions: new Set<string>(), roles: [] as string[] },
  presentation: {
    theme: "graphite" as Theme, ribbonCollapsed: false,
    expandedPanels: new Set<string>(), reportZoom: 1, tableLayout: {} as Record<string, string>,
  },
  overview: {
    status: "LOADING" as OverviewTransport,
    data: null as OverviewPayload | null,
    errorCode: null as string | null,
    filters: { startDate: "", endDate: "", model: "ALL", trainingType: "ALL", equip: "" },
    selectedBatchId: null as string | null,
  },
  batchEvents: {
    status: "LOADING" as OverviewTransport,
    batchId: null as string | null,
    data: null as BatchEventsData | null,
    items: [] as BatchEventItem[],
    errorCode: null as string | null,
    filters: {
      category: "ALL", adjudication: "ALL", clusterId: "", entityId: "",
      episodeId: "", startTimeUs: "", endTimeUs: "",
    },
    nextCursor: null as string | null,
  },
  weaponWorkbench: {
    status: "LOADING" as OverviewTransport,
    detail: null as Readonly<Record<string, unknown>> | null,
    window: null as Readonly<Record<string, unknown>> | null,
    perspective: "shooter" as "shooter" | "target",
    errorCode: null as string | null,
    requestSerial: 0,
  },
  coAttack: {
    status: "LOADING" as OverviewTransport,
    data: null as CoAttackPayload | null,
    errorCode: null as string | null,
  },
  replay: {
    status: "LOADING" as OverviewTransport,
    data: null as Readonly<Record<string, unknown>> | null,
    errorCode: null as string | null,
  },
  batchImport: {
    ticket: null as ImportTicketDTO | null, idempotencyKey: null as string | null, working: false,
    errorCode: null as string | null, receipt: null as BatchRegistrationDTO | null,
    contextReceipt: null as ForceFormationContextDTO | null,
  },
  v24Grant: null as V24Grant | null,
  notice: directV24 ? ({
    viewId: "V08", state: "FORBIDDEN", title: "禁止直接访问协同攻击分析",
    message: "V24 只能从 V08 中已识别的 BVR 同目标协同攻击事件进入；当前请求未提供受控入口上下文。",
    code: "V24_REQUIRES_V08_CONTEXT",
  } satisfies Notice) : null as Notice | null,
};

function esc(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}
function currentView(): View {
  const view = views.get(state.navigation.currentViewId);
  if (!view) throw new Error("TPAA_CURRENT_VIEW_UNKNOWN");
  return view;
}
function hasText(value: string | null | undefined): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
function validV24Grant(grant: V24Grant | null): grant is V24Grant {
  return state.navigation.currentViewId === "V08" && grant !== null &&
    grant.sourceView === "V08" && grant.eventCategory === "BVR" &&
    hasText(grant.releaseId) && hasText(grant.contextId) &&
    hasText(grant.weaponEventId) && hasText(grant.attackClusterId);
}
function hasViewPermissions(id: ViewId): boolean {
  if (state.authorization.status !== "READY") return false;
  const contract = viewContracts.get(id);
  if (!contract || contract.required_permissions.length === 0) return false;
  return contract.required_permissions.every((permissionId) => {
    const policy = permissionPolicies.get(permissionId);
    return Boolean(policy && policy.unknown_policy === "DENY" && state.authorization.permissions.has(permissionId));
  });
}
function canNavigate(id: ViewId): boolean {
  if (id === "V24") {
    return state.navigation.currentViewId === "V24" && state.v24Grant !== null &&
      hasViewPermissions("V24") &&
      state.navigation.returnStack[state.navigation.returnStack.length - 1]?.viewId === "V08";
  }
  return hasViewPermissions(id);
}
function snapshot(): Frame {
  return { viewId: state.navigation.currentViewId, moduleId: state.navigation.activeModuleId,
    domain: { ...state.domainSelection }, replay: { ...state.replayState } };
}
function setForbidden(viewId: ViewId, title: string, message: string, code: string): void {
  state.notice = { viewId, state: "FORBIDDEN", title, message, code };
}
function navigateToView(id: ViewId): boolean {
  if (id === "V24") {
    setForbidden("V08", "禁止直接访问协同攻击分析", "V24 不是常规导航项，只能从 V08 的受控 BVR 同目标协同攻击入口进入。", "V24_REQUIRES_V08_CONTEXT");
    render();
    return false;
  }
  if (!views.has(id) || !canNavigate(id)) {
    setForbidden(state.navigation.currentViewId, "当前会话无权打开该视图", "权限缺失、权限未知或会话尚未核验时，导航按默认拒绝处理。", "GUI_VIEW_ACCESS_DENIED");
    render();
    return false;
  }
  if (id === state.navigation.currentViewId) { state.notice = null; render(); return true; }
  state.navigation.returnStack.push(snapshot());
  if (state.navigation.returnStack.length > 40) state.navigation.returnStack.shift();
  const selected = views.get(id);
  if (!selected) return false;
  state.navigation.currentViewId = id;
  state.navigation.activeModuleId = selected.module;
  state.navigation.approvedPredecessor = null;
  state.notice = null;
  state.v24Grant = null;
  render();
  if (id === "V01") void loadOverview();
  if (id === "V26") void ensureBatchEvents();
  if (id in WEAPON_VIEW_CATEGORY) void ensureWeaponPage(id);
  if (id === "V24") void loadCoAttack();
  if (id === "V03") void loadReplayContext();
  return true;
}
function navigateToModule(id: ModuleId): void {
  const module = modules.get(id);
  if (module) navigateToView(module.landing);
}
function enterV24FromV08(grant: V24Grant | null): boolean {
  if (!validV24Grant(grant) || !hasViewPermissions("V24")) {
    setForbidden("V08", "协同攻击入口尚未获准", "必须由后端提供精确的 BVR Weapon Event、Attack Cluster、Formation、Release 和 Context 授权上下文；G2 不生成演示授权。", "V24_CONTROLLED_ENTRY_NOT_AVAILABLE");
    render();
    return false;
  }
  state.navigation.returnStack.push(snapshot());
  state.v24Grant = grant;
  state.domainSelection.releaseId = grant.releaseId;
  state.domainSelection.contextId = grant.contextId;
  state.domainSelection.weaponEventId = grant.weaponEventId;
  state.domainSelection.attackClusterId = grant.attackClusterId;
  state.domainSelection.formationId = grant.formationId;
  state.navigation.currentViewId = "V24";
  state.navigation.activeModuleId = "training";
  state.navigation.approvedPredecessor = "V08";
  state.notice = null;
  render();
  void loadCoAttack();
  return true;
}
function goBack(): void {
  if (state.navigation.currentViewId === "V24") {
    const previous = state.navigation.returnStack.pop();
    state.v24Grant = null;
    state.navigation.currentViewId = "V08";
    state.navigation.activeModuleId = "training";
    state.navigation.approvedPredecessor = null;
    if (previous?.viewId === "V08") {
      state.domainSelection = { ...previous.domain };
      state.replayState = { ...previous.replay };
    }
    state.notice = null;
    render();
    return;
  }
  const previous = state.navigation.returnStack.pop();
  if (!previous) return;
  state.navigation.currentViewId = previous.viewId;
  state.navigation.activeModuleId = previous.moduleId;
  state.navigation.approvedPredecessor = null;
  state.domainSelection = { ...previous.domain };
  state.replayState = { ...previous.replay };
  state.notice = null;
  state.v24Grant = null;
  render();
}
function setTheme(theme: Theme): void {
  state.presentation.theme = theme;
  assignTheme(document.documentElement, theme);
  render();
}
function toggleRibbon(): void {
  state.presentation.ribbonCollapsed = !state.presentation.ribbonCollapsed;
  render();
}
function contextValue(field: string): string | null {
  const values: Record<string, string | null> = {
    batch_id: state.domainSelection.batchId, session_id: state.domainSelection.sessionId,
    sortie_id: state.domainSelection.sortieId, release_id: state.domainSelection.releaseId,
    context_id: state.domainSelection.contextId, policy_id: state.domainSelection.policyId,
    episode_id: state.domainSelection.episodeId, stage_id: state.domainSelection.stageId,
    weapon_event_id: state.domainSelection.weaponEventId, attack_cluster_id: state.domainSelection.attackClusterId,
    formation_id: state.domainSelection.formationId, member_id: state.domainSelection.memberId,
    evaluated_side: state.domainSelection.evaluatedSide,
  };
  return values[field] ?? null;
}
function viewState(view: View): UiState {
  if (state.notice?.viewId === view.id) return state.notice.state;
  if (view.id === "V25") return "READY";
  if (view.id === "V24" && !canNavigate("V24")) return "FORBIDDEN";
  if (state.authorization.status !== "READY") return state.authorization.status;
  if (!canNavigate(view.id)) return "FORBIDDEN";
  if (view.id === "V01") return state.overview.status === "READY" ? "READY" : state.overview.status;
  if (view.id === "V26") return state.batchEvents.status === "READY" ? "READY" : state.batchEvents.status;
  if (view.id === "V24" && canNavigate("V24")) return state.coAttack.status === "READY" ? "READY" : state.coAttack.status;
  if (view.id === "V03") return state.replay.status === "READY" ? "READY" : state.replay.status;
  if (view.id in WEAPON_VIEW_CATEGORY) return state.batchEvents.status === "READY" ? "READY" : state.batchEvents.status;
  if (view.id === "V23") return state.batchImport.working ? "LOADING" : "READY";
  const contract = viewContracts.get(view.id);
  if (!contract) return "ERROR";
  if (contract.required_context.some((field) => !hasText(contextValue(field)))) return "N_A";
  return "N_A";
}
function statusCopy(status: UiState): { label: string; title: string; message: string; code: string } {
  const copy: Record<UiState, { label: string; title: string; message: string; code: string }> = {
    LOADING: { label: "LOADING", title: "正在核验本地会话权限", message: "正在读取当前会话的角色与权限；核验完成前不开放业务视图。", code: "AUTHORIZATION_LOADING" },
    EMPTY: { label: "EMPTY", title: "当前精确查询范围没有可展示记录", message: "不会使用其他批次、默认样本或演示数据填充空结果。", code: "EXACT_QUERY_EMPTY" },
    READY: { label: "READY", title: "当前会话呈现设置可用", message: "主题只作用于当前桌面会话，不写入业务上下文或浏览器持久存储。", code: "PRESENTATION_ONLY_SESSION_STATE" },
    DEGRADED: { label: "DEGRADED", title: "权限服务暂不可用", message: "页面保持关闭；请检查本地后端状态后重试。", code: "AUTHORIZATION_DEGRADED" },
    ERROR: { label: "ERROR", title: "权限响应不符合合同", message: "系统无法确认当前会话权限，因此拒绝加载业务视图。", code: "AUTHORIZATION_RESPONSE_INVALID" },
    FORBIDDEN: { label: "FORBIDDEN", title: "当前会话无权访问此视图", message: "权限缺失、权限未知或受控入口上下文不完整时，系统按默认拒绝处理。", code: "FORBIDDEN" },
    N_A: { label: "N_A", title: "当前视图尚未接入真实业务读模型", message: "真实批次、指标、事件与回放数据将在后续阶段通过 Application/API 合同接入；不会以演示数据填充。", code: "VIEW_READ_MODEL_NOT_AVAILABLE" },
  };
  return copy[status];
}

/* ===== V25 主题管理（Demo themeChoice 版式） ===== */
function themeDashboardPreview(id: Theme): string {
  const d = THEME_DEF[id];
  const pr = [d.base, d.panel, d.panel2, d.border, d.accent, d.text, d.muted, d.green, d.orange].join("|");
  return `<div class="themeMock" data-pr="${pr}">
    <div class="themeMockMenu"><span class="mockLogo">◈</span><b>分析工作台</b><i></i><span>⋯</span></div>
    <div class="themeMockMain">
      <div class="themeMockSide"><div class="mockNavOn">▤　总体态势</div><div>▥　事件分析</div><div>◎　目标关系</div><div>≋　数据质量</div></div>
      <div class="themeMockContent">
        <div class="mockTitle"><strong>架次分析概览</strong><span>2026-10-22 · 演示</span></div>
        <div class="mockStats"><div>已关联事件<strong>08</strong><small>覆盖率 96%</small></div><div>活动目标<strong>04</strong><small>航迹同步</small></div><div>异常提示<strong>02</strong><small>待复核</small></div></div>
        <div class="mockGraph"><div class="mockGraphTitle">航迹质量趋势 <span>● 可用　● 降级</span></div></div>
      </div>
    </div>
  </div>`;
}
function themePickCard(id: Theme): string {
  const d = THEME_DEF[id];
  const active = state.presentation.theme === id;
  return `<div class="themeChoice${active ? " isChosen" : ""}">
    <div class="themeChoiceHeader"><div><strong>${d.label}</strong><span>${d.short}</span></div>
      <span class="themeStatus${active ? " selected" : ""}">${active ? "✓ 当前启用" : "可切换"}</span></div>
    ${themeDashboardPreview(id)}
    <div class="themeChoiceFooter"><div><span class="themePalette">${[d.base, d.panel, d.accent, d.green, d.orange].map((c) => `<i class="palette-swatch" data-color="${c}"></i>`).join("")}</span><span class="themeDesc">${d.desc}</span></div>
      <button type="button" data-theme="${id}" class="themeSetButton${active ? " active" : ""}"${active ? " disabled" : ""}>${active ? "正在使用" : "应用此主题"}</button></div>
  </div>`;
}
function renderThemes(): string {
  beginLayout("V25");
  return panel("界面主题", "", `<div class="themeIntroduction"><div><b>当前主题：</b><strong>${THEME_DEF[state.presentation.theme].label}</strong><span>主题仅改变界面表现，不影响批次、事件、指标和回放功能。</span></div><span class="themeVersion">每次打开默认 Graphite · 主题切换即时生效且仅会话级</span></div>`) +
    panel("暗色战术主题", "", themePickCard("tactical")) +
    panel("深色主题 · Palantir AIP 风格参考", "", themePickCard("graphite")) +
    panel("浅色主题 · 冰川灰白", "", themePickCard("light")) +
    panel("应用范围", "", `<div class="themeScope"><span>✓　所有主菜单 / Ribbon 子菜单</span><span>✓　评估、回放与数据管理面板</span><span>✓　图表背景 / 轴线 / 选择态</span><span>✓　每次打开默认深色主题</span></div>`);
}

/* ===== V01 训练总览（G6 历史聚合读模型，v29 markup 复刻自 v33 Demo） ===== */
const TRAINING_TYPE_LABELS: Record<string, string> = {
  SIMPLE_OPPOSITION: "简单对抗", MIXED_OPPOSITION: "混合对抗",
  COMPREHENSIVE_OPPOSITION: "综合对抗", UNCLASSIFIED: "暂不分类",
};
function trainingTypeLabel(value: string): string {
  return TRAINING_TYPE_LABELS[value] ?? value;
}
function typeTagClass(value: string): string {
  return value === "SIMPLE_OPPOSITION" ? "type-simple"
    : value === "MIXED_OPPOSITION" ? "type-mixed" : "type-comprehensive";
}
/** 活动趋势折线（对齐 Demo svgLine：网格 + 双序列 + 日期标签，真实批次数据）。 */
function overviewActivitySvg(points: readonly ActivityPoint[]): string {
  const W = 690, H = 108, L = 42, R = 14, T = 10, B = 24;
  const iw = W - L - R, ih = H - T - B;
  const series = [
    { name: "武器发射", color: "#55a9e5", value: (p: ActivityPoint) => p.weapon_launch },
    { name: "交战过程", color: "#d5ad55", value: (p: ActivityPoint) => p.engagement_process },
  ] as const;
  const max = Math.max(1, ...points.flatMap((p) => series.map((s) => s.value(p)))) * 1.12;
  const x = (i: number) => L + (points.length <= 1 ? 0 : i / (points.length - 1) * iw);
  const y = (v: number) => T + ih - v / max * ih;
  let grid = "";
  for (let i = 0; i <= 4; i += 1) {
    const v = max * i / 4, yy = y(v);
    grid += `<line x1="${L}" y1="${yy}" x2="${W - R}" y2="${yy}" stroke="var(--ln)" stroke-width="1"/>` +
      `<text x="${L - 7}" y="${yy + 3}" text-anchor="end" fill="var(--mu)" font-size="9">${String(Number(v.toFixed(1)))}</text>`;
  }
  const lines = series.map((s) => {
    const pts = points.map((p, i) => `${x(i)},${y(s.value(p))}`).join(" ");
    const dots = points.map((p, i) =>
      `<circle cx="${x(i)}" cy="${y(s.value(p))}" r="3" fill="${s.color}"><title>${p.batch_date} ${s.name}: ${String(s.value(p))}</title></circle>`).join("");
    return `<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>${dots}`;
  }).join("");
  const labels = points.map((p, i) =>
    `<text x="${x(i)}" y="${H - 7}" text-anchor="middle" fill="var(--mu)" font-size="8">${p.batch_date.slice(5, 10).replace("-", "/")}</text>`).join("");
  const legend = series.map((s) => `<span class="v29Legend"><i data-color="${s.color}"></i>${s.name}</span>`).join("");
  return `<div class="v29ChartLegend">${legend}</div><svg class="v29Svg" viewBox="0 0 ${W} ${H}" role="img">${grid}${lines}${labels}</svg>`;
}
/** 裁决状态双横条：只呈现后端给出的已裁决/待裁决合计，不虚构命中/规避分布。 */
function overviewOutcomeSvg(outcome: OutcomeTrend): string {
  const W = 690, H = 96, L = 64, R = 40, rowH = 30;
  const max = Math.max(1, outcome.adjudicated, outcome.pending);
  const rows = [
    { label: "已正式裁决", value: outcome.adjudicated, color: "#49a889" },
    { label: "待正式裁决", value: outcome.pending, color: "#788da6" },
  ];
  const bars = rows.map((row, i) => {
    const y = 14 + i * rowH;
    const w = Math.max(2, (W - L - R) * row.value / max);
    return `<text x="${L - 8}" y="${y + 11}" text-anchor="end" fill="var(--mu)" font-size="9">${row.label}</text>` +
      `<rect x="${L}" y="${y}" width="${w}" height="16" rx="2" fill="${row.color}"><title>${row.label}: ${String(row.value)}</title></rect>` +
      `<text x="${L + w + 6}" y="${y + 12}" fill="var(--tx)" font-size="10">${String(row.value)}</text>`;
  }).join("");
  return `<svg class="v29Svg" viewBox="0 0 ${W} ${H}" role="img">${bars}</svg>`;
}
function overviewEquipmentSvg(trend: EquipmentTrend): string {
  const points = trend.points;
  if (!points.length) return '<div class="v29Empty">该指标暂无已准入的跨批次数据点。</div>';
  const W = 690, H = 118, L = 46, R = 14, T = 10, B = 24;
  const iw = W - L - R, ih = H - T - B;
  const values = points.map((p) => Number(p.value));
  const min = Math.floor(Math.min(...values) * 0.9 * 10) / 10;
  const max = Math.ceil(Math.max(...values) * 1.1 * 10) / 10;
  const x = (i: number) => L + (points.length <= 1 ? 0 : i / (points.length - 1) * iw);
  const y = (v: number) => T + ih - (v - min) / (max - min || 1) * ih;
  let grid = "";
  for (let i = 0; i <= 4; i += 1) {
    const v = min + (max - min) * i / 4, yy = y(v);
    grid += `<line x1="${L}" y1="${yy}" x2="${W - R}" y2="${yy}" stroke="var(--ln)"/>` +
      `<text x="${L - 6}" y="${yy + 3}" text-anchor="end" fill="var(--mu)" font-size="8">${String(Number(v.toFixed(2)))}</text>`;
  }
  const pts = points.map((p, i) => `${x(i)},${y(Number(p.value))}`).join(" ");
  const dots = points.map((p, i) =>
    `<circle cx="${x(i)}" cy="${y(Number(p.value))}" r="3" fill="#55a9e5"><title>${p.batch_date}: ${p.value} ${trend.unit}</title></circle>`).join("");
  const labels = points.map((p, i) =>
    `<text x="${x(i)}" y="${H - 7}" text-anchor="middle" fill="var(--mu)" font-size="8">${p.batch_date.slice(5, 10).replace("-", "/")}</text>`).join("");
  return `<svg class="v29Svg" viewBox="0 0 ${W} ${H}" role="img">${grid}` +
    `<polyline points="${pts}" fill="none" stroke="#55a9e5" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>${dots}${labels}</svg>`;
}
function overviewTaskMetrics(trends: readonly TaskMetricTrend[]): string {
  if (!trends.length) {
    return '<div class="v29Empty">任务级指标尚未经 Metric Authority 准入；当前不展示演示曲线，正式统计以权威裁决和任务目标数据为准。</div>';
  }
  return `<div class="v29MetricRows">${trends.map((item) => {
    const demo = item.status === "DEMO_FORMULA_NOT_FORMAL";
    const badge = demo ? "演示口径 · 未准入" : (item.reason ?? "FAIL_CLOSED");
    const value = item.value !== null ? `${item.value}${item.unit ?? ""}` : "—";
    const frac = item.numerator !== null && item.denominator !== null
      ? `<small>${String(item.numerator)} / ${String(item.denominator)}（分子/分母重算，非简单平均）</small>` : "";
    return `<div class="v29MetricRow"><div><b>${esc(item.label)}</b>${frac}</div>` +
      `<strong>${esc(value)}</strong><span class="v29MetricBadge${demo ? " demo" : " closed"}">${esc(badge)}</span></div>`;
  }).join("")}</div>`;
}
function overviewSelectedBatch(batch: OverviewBatch | null): string {
  if (!batch) {
    return '<div class="v29Empty">当前筛选条件下没有选中的历史批次。</div>';
  }
  const loaded = batch.has_event_detail;
  const status = loaded ? "逐事件明细已加载" : "已登记 · 资格确认";
  const foot = loaded
    ? '<button type="button" class="v29Primary" data-v29-open-selected>进入该批次详细复盘 ›</button>'
    : "<span>该批次已通过数据资格确认，逐事件明细尚未载入；不会跳转到其他批次的事件明细。</span>";
  return `<div class="v29SelectedBatch"><div class="v29SelectedHead"><div><b>训练批次 ${esc(batch.batch_id.slice(0, 13))}</b>` +
    `<small>${esc(batch.batch_id)} · ${esc(batch.batch_date)} · ${esc(trainingTypeLabel(batch.batch_training_type))}</small></div>` +
    `<span class="${loaded ? "loaded" : "archive"}">${status}</span></div>` +
    `<div class="v29SelectedStats"><span>架次 <b>${String(batch.sortie_count)}</b></span><span>交战过程 <b>${String(batch.episode_count)}</b></span>` +
    `<span>武器发射 <b>${String(batch.weapon_event_count)}</b></span><span>已裁决 <b>${String(batch.adjudicated_event_count)}</b></span></div>` +
    `<div class="v29ImportedNote">训练行为类别细分由 V26 批次工作台所有；本摘要仅呈现 V01 精确批次集合内的真实合计。</div>` +
    `<div class="v29SelectedFoot">${foot}</div></div>`;
}
function renderOverview(): string {
  const overview = state.overview;
  const data = overview.data;
  const f = overview.filters;
  const invalidDate = f.startDate !== "" && f.endDate !== "" && f.startDate > f.endDate;
  if (overview.status === "LOADING") {
    return `<section class="v29Overview"><div class="v29Header"><div class="v29Title"><h1>训练总览</h1>` +
      `<span>历史训练综合态势 · 多批次统计与趋势分析</span></div></div>` +
      `<div class="v29Kpis">${Array.from({ length: 6 }, () => '<div class="v29Kpi"><span>载入中</span><b>…</b><small>正在读取历史聚合读模型</small></div>').join("")}</div>` +
      `<div class="v29Row v29RowFirst"><article class="v29Panel"><header><b>任务级指标趋势</b></header>` +
      statePanel("LOADING", "正在读取历史聚合读模型", "所有指标、趋势与列表均来自同一精确批次集合。", "G6_OVERVIEW_LOADING") +
      `</article><article class="v29Panel"><header><b>历史训练活动趋势</b></header></article></div></section>`;
  }
  if (overview.status === "DEGRADED" || overview.status === "ERROR" || !data) {
    const status = overview.status === "READY" ? "ERROR" : overview.status;
    return `<section class="v29Overview"><div class="v29Header"><div class="v29Title"><h1>训练总览</h1>` +
      `<span>历史训练综合态势 · 多批次统计与趋势分析</span></div></div>` +
      panel("历史训练批次", "读模型不可用", statePanel(status, "历史聚合读模型暂不可用",
        esc(overview.errorCode ?? "G6_OVERVIEW_FAILED") + "；页面保持关闭，不会以演示数据填充。", "G6_OVERVIEW_UNAVAILABLE")) +
      `</section>`;
  }
  const rows = [...data.batches].sort((a, b) => b.batch_date.localeCompare(a.batch_date));
  const kpi = data.kpi;
  const kpis = [
    ["历史训练批次", kpi.batch_count, "按日期、机型和训练类型筛选"],
    ["飞行架次", kpi.sortie_count, "跨批次累计，不按人员评分"],
    ["交战过程", kpi.episode_count, "跨批次训练过程统计"],
    ["武器发射", kpi.weapon_event_count, "按每枚武器独立统计"],
    ["已正式裁决", kpi.adjudicated_event_count, "仅统计已形成正式裁决的记录"],
    ["数据资格通过批次", kpi.data_qualification_summary.qualified, "以批次数据资格摘要为准"],
  ].map(([label, value, hint]) =>
    `<div class="v29Kpi"><span>${String(label)}</span><b>${String(value)}</b><small>${String(hint)}</small></div>`).join("");
  const header = `<div class="v29Header"><div class="v29Title"><h1>训练总览</h1><span>历史训练综合态势 · 多批次统计与趋势分析</span></div><div class="v29Filters">
      <label>起始日期<input type="date" data-v29-filter="startDate" value="${esc(f.startDate)}"></label>
      <label>结束日期<input type="date" data-v29-filter="endDate" value="${esc(f.endDate)}"></label>
      <label>机型<select data-v29-filter="model"><option value="ALL"${f.model === "ALL" ? " selected" : ""}>全部机型</option><option value="A型"${f.model === "A型" ? " selected" : ""}>A 型</option><option value="B型"${f.model === "B型" ? " selected" : ""}>B 型</option></select></label>
      <label>训练类型<select data-v29-filter="trainingType"><option value="ALL"${f.trainingType === "ALL" ? " selected" : ""}>全部类型</option><option value="SIMPLE_OPPOSITION"${f.trainingType === "SIMPLE_OPPOSITION" ? " selected" : ""}>简单对抗</option><option value="MIXED_OPPOSITION"${f.trainingType === "MIXED_OPPOSITION" ? " selected" : ""}>混合对抗</option><option value="COMPREHENSIVE_OPPOSITION"${f.trainingType === "COMPREHENSIVE_OPPOSITION" ? " selected" : ""}>综合对抗</option></select></label>
      <button type="button" data-v29-open-v09>训练成长趋势 ›</button><button type="button" data-v29-open-v16>装备性能趋势 ›</button>${invalidDate || data.filter.invalid_date_range ? '<span class="v29DateWarning">日期范围无效</span>' : ""}
    </div></div>`;
  const selected = rows.find((b) => b.batch_id === overview.selectedBatchId) ?? null;
  const equipTrends = data.equipment_trends;
  const equipSelected = equipTrends.find((t) => t.metric_id === f.equip) ?? equipTrends[0] ?? null;
  const equipBody = equipTrends.length === 0
    ? '<div class="v29Empty">装备性能指标尚未经 Metric Authority 准入；未准入指标不展示趋势，不使用演示样例填充。</div>'
    : `<div class="v29EquipMetric">${esc(equipSelected?.label ?? "")} · ${esc(equipSelected?.unit ?? "")}${equipSelected && !equipSelected.comparable ? ` · ${esc(equipSelected.reason ?? "NOT_COMPARABLE")}` : ""}</div>` +
      (equipSelected && equipSelected.comparable ? overviewEquipmentSvg(equipSelected)
        : '<div class="v29Empty">该装备指标在当前批次集合内不可比（fail-closed），不展示趋势。</div>');
  const table = rows.length ? rows.map((b) => {
    const active = b.batch_id === overview.selectedBatchId;
    return `<button type="button" class="v29BatchRow${active ? " selected" : ""}" data-v29-batch="${esc(b.batch_id)}"><span>${esc(b.batch_date)}</span><b>${esc(b.batch_id)}</b>` +
      `<span><i class="v29TypeTag ${typeTagClass(b.batch_training_type)}">${esc(trainingTypeLabel(b.batch_training_type))}</i></span>` +
      `<span>${String(b.sortie_count)}</span><strong>${String(b.weapon_event_count)}</strong>` +
      `<span class="${b.has_event_detail ? "ok" : "pending"}">${b.has_event_detail ? "逐事件明细已加载" : "资格确认"}</span></button>`;
  }).join("") : '<div class="v29Empty">当前筛选条件下没有历史批次，请调整日期范围或训练类型。</div>';
  return `<section class="v29Overview">
      ${header}
      <div class="v29Kpis">${kpis}</div>
      <div class="v29Row v29RowFirst">
        <article class="v29Panel v29TaskMetrics"><header><div><b>任务级指标趋势</b><small>跨批次比较击杀比、敌我交换比与任务达成率；演示口径，正式统计以权威裁决和任务目标数据为准。</small></div><span>${String(data.task_metric_trends.length)} 项指标</span></header>${overviewTaskMetrics(data.task_metric_trends)}</article>
        <article class="v29Panel v29Activity"><header><div><b>历史训练活动趋势</b><small>按训练批次日期汇总武器发射与交战过程数量</small></div><span>${String(data.activity_trend.points.length)} 个批次</span></header>${data.activity_trend.points.length ? overviewActivitySvg(data.activity_trend.points) : '<div class="v29Empty">当前筛选条件下暂无活动趋势数据。</div>'}</article>
      </div>
      <div class="v29Row v29RowSecond">
        <article class="v29Panel v29Outcome"><header><div><b>训练结果与裁决状态趋势</b><small>按正式裁决记录统计；待裁决单独列示，不计入已裁决结果</small></div><span>${String(data.outcome_trend.adjudicated)} 条已裁决记录</span></header>${overviewOutcomeSvg(data.outcome_trend)}</article>
        <article class="v29Panel v29Category"><header><div><b>训练行为类别构成</b><small>跨批次武器发射合计；类别细分由 V26 批次工作台所有</small></div><span>发射数量</span></header><div class="v29CategoryTotal">跨批次武器发射合计 <b>${String(data.category_composition.total_weapon_events)}</b></div><div class="v29Empty">WVR / BVR / STRIKE 逐批次分布不在 V01 推导；进入 V26 查看类别级明细。</div></article>
        <article class="v29Panel v29Equipment"><header><div><b>装备性能历史趋势</b><small>仅展示已准入装备指标；详细分析进入装备性能专项页面</small></div>${equipTrends.length ? `<label>趋势指标<select data-v29-equip>${equipTrends.map((t) => `<option value="${esc(t.metric_id)}"${equipSelected?.metric_id === t.metric_id ? " selected" : ""}>${esc(t.label)}</option>`).join("")}</select></label>` : ""}</header>${equipBody}</article>
      </div>
      <div class="v29Row v29RowBottom">
        <article class="v29Panel v29BatchList"><header><div><b>历史训练批次</b><small>按日期与训练类型筛选；选择批次查看汇总与数据准备情况</small></div><span>${String(rows.length)} 条记录</span></header><div class="v29BatchTable"><div class="v29BatchHead"><span>日期</span><span>批次编号</span><span>训练类型</span><span>架次</span><span>发射数</span><span>数据状态</span></div>${table}</div></article>
        <article class="v29Panel v29BatchDetail"><header><div><b>选中批次摘要</b><small>批次汇总与数据准备情况</small></div></header>${overviewSelectedBatch(selected)}</article>
      </div>
      <div class="v29Footer">任务级指标为演示口径、未正式准入；训练行为类别细分由 V26 批次工作台所有；页面仅呈现精确批次集合的真实统计，空结果不作填充。</div>
    </section>`;
}

/* ===== V26 批次发射事件工作台（G7，真实 gui.batch.events） ===== */
const EVENT_CATEGORY_LABELS: Record<string, string> = {
  WVR: "视距内", BVR: "超视距", STRIKE: "对地攻击", UNKNOWN: "未分类",
};
function eventCategoryLabel(value: string): string {
  return EVENT_CATEGORY_LABELS[value] ?? value;
}
function eventCategoryView(value: string): ViewId {
  return value === "WVR" ? "V05" : value === "STRIKE" ? "V06" : "V04";
}
function formatEventTimeUs(value: string): string {
  const micros = Number(value);
  if (!Number.isFinite(micros)) return value;
  const seconds = Math.floor(micros / 1_000_000);
  const remainder = String(micros % 1_000_000).padStart(6, "0");
  return `${String(seconds)}.${remainder}s`;
}
function renderBatchTimeline(items: readonly BatchEventItem[]): string {
  if (!items.length) return '<div class="v29Empty">当前筛选条件下没有发射事件。</div>';
  const times = items.map((item) => Number(item.t1_session_time_us));
  const min = Math.min(...times), max = Math.max(...times);
  const span = Math.max(1, max - min);
  const rows = items.map((item) => {
    const left = ((Number(item.t1_session_time_us) - min) / span) * 100;
    return `<div class="v26TrackRow"><span class="v26TrackTime">${formatEventTimeUs(item.t1_session_time_us)}</span>` +
      `<i class="v26TrackBar"><em data-w="${left.toFixed(2)}%"></em><b data-color="${item.category === "WVR" ? "#e58a43" : item.category === "STRIKE" ? "#b77ca8" : "#d5ad55"}"></b></i>` +
      `<span class="v26TrackCat">${eventCategoryLabel(item.category)}</span></div>`;
  }).join("");
  return `<div class="v26Timeline">${rows}</div><div class="v26TimelineNote">按武器发射时刻（session_time_us）定位；齐射各自独立显示。</div>`;
}
function renderBatchEvents(): string {
  beginLayout("V26");
  const workbench = state.batchEvents;
  if (workbench.status === "LOADING") {
    return panel("批次与筛选", "精确批次范围", statePanel("LOADING", "正在读取批次发射事件工作台", "所有统计、时间线与清单均来自同一精确批次范围。", "G7_BATCH_EVENTS_LOADING"));
  }
  if (workbench.status === "DEGRADED" || workbench.status === "ERROR" || !workbench.data) {
    return panel("批次与筛选", "读模型不可用", statePanel(
      workbench.status === "READY" ? "ERROR" : workbench.status,
      "批次发射事件工作台暂不可用",
      esc(workbench.errorCode ?? "G7_BATCH_EVENTS_FAILED") + "；页面保持关闭，不会借用其他批次数据填充。",
      "G7_BATCH_EVENTS_UNAVAILABLE"));
  }
  const data = workbench.data;
  const batches = state.overview.data?.batches ?? [];
  const selectedBatch = batches.find((item) => item.batch_id === workbench.batchId) ?? null;
  const filterPanel = `<div class="selbar v23-bar">
      <label>批次<select data-v26-batch>${batches.map((item) =>
        `<option value="${esc(item.batch_id)}"${item.batch_id === workbench.batchId ? " selected" : ""}>${esc(item.batch_date)} · ${esc(trainingTypeLabel(item.batch_training_type))}</option>`).join("")}</select></label>
      <label>行为类别<select data-v26-filter="category">${["ALL", "WVR", "BVR", "STRIKE", "UNKNOWN"].map((value) =>
        `<option value="${value}"${workbench.filters.category === value ? " selected" : ""}>${value === "ALL" ? "全部类别" : eventCategoryLabel(value)}</option>`).join("")}</select></label>
      <label>裁决状态<select data-v26-filter="adjudication">${["ALL", "ADJUDICATED", "ADJUDICATION_PENDING"].map((value) =>
        `<option value="${value}"${workbench.filters.adjudication === value ? " selected" : ""}>${value === "ALL" ? "全部状态" : value === "ADJUDICATED" ? "已正式裁决" : "待正式裁决"}</option>`).join("")}</select></label>
      <label>主体<input data-v26-filter="entityId" value="${esc(workbench.filters.entityId)}" placeholder="射手或目标 ID"></label>
      <label>架次/阶段<input data-v26-filter="episodeId" value="${esc(workbench.filters.episodeId)}" placeholder="Episode ID"></label>
      <label>起始时刻 µs<input data-v26-filter="startTimeUs" inputmode="numeric" value="${esc(workbench.filters.startTimeUs)}"></label>
      <label>结束时刻 µs<input data-v26-filter="endTimeUs" inputmode="numeric" value="${esc(workbench.filters.endTimeUs)}"></label>
      <span class="muted">query_context ${esc(data.query_context_id)}</span>
    </div>
    <div class="v26EntryRow"><button type="button" data-view="V23">Context 管理入口 ›</button>
    <span class="muted-note">未发射行为列表由 G10 来源覆盖矩阵准入后接入；当前不以演示数据填充。</span></div>`;
  const summary = data.summary;
  const summaryPanel = `<div class="v26Stats"><div><span>武器发射</span><b>${String(summary.weapon_event_count)}</b></div>` +
    `<div><span>攻击簇</span><b>${String(summary.cluster_count)}</b></div>` +
    `<div><span>分类例外</span><b>${String(summary.classification_exception_count)}</b></div></div>` +
    `<div class="v26CatChips">${Object.entries(summary.category_counts).map(([key, value]) =>
      `<span class="v26Chip">${eventCategoryLabel(key)} <b>${String(value)}</b></span>`).join("")}</div>` +
    `<div class="v26CatChips"><span class="v26Chip ok">已正式裁决 <b>${String(summary.adjudication_counts.ADJUDICATED ?? 0)}</b></span>` +
    `<span class="v26Chip pending">待正式裁决 <b>${String(summary.adjudication_counts.ADJUDICATION_PENDING ?? 0)}</b></span></div>`;
  const listRows = workbench.items.map((item) => `<tr><td>${formatEventTimeUs(item.t1_session_time_us)}</td>` +
    `<td><span class="v29TypeTag type-${item.category === "SIMPLE_OPPOSITION" ? "simple" : item.category === "MIXED_OPPOSITION" ? "mixed" : item.category === "WVR" ? "simple" : item.category === "STRIKE" ? "comprehensive" : "mixed"}">${eventCategoryLabel(item.category)}</span>` +
    `${item.classification_exception ? ' <span class="pill">分类例外</span>' : ""}${item.cluster_id ? ` <span class="pill">簇 ${esc(item.cluster_id.slice(0, 8))}</span>` : ""}</td>` +
    `<td class="mono">${esc(item.shooter_entity_id.slice(0, 8))}${item.target_entity_id ? " → " + esc(item.target_entity_id.slice(0, 8)) : ""}</td>` +
    `<td>${esc(item.weapon_terminal_state)}</td><td>${item.adjudication_state === "ADJUDICATED" ? "已裁决" : "待裁决"}</td>` +
    `<td>${esc(item.observation_window_state)}</td>` +
    `<td><button type="button" data-v26-open="${eventCategoryView(item.category)}" data-event="${esc(item.weapon_event_id)}">复盘 ›</button></td></tr>`).join("");
  const listPanel = workbench.items.length
    ? `<table class="batch-table v26Table"><thead><tr><th>发射时刻</th><th>类别</th><th>射手 → 目标</th><th>武器终止</th><th>裁决</th><th>观察窗口</th><th>操作</th></tr></thead><tbody>${listRows}</tbody></table>` +
      (workbench.nextCursor
        ? `<div class="mt10"><button type="button" data-v26-more>加载更多（已载 ${String(workbench.items.length)} / ${String(data.total_count)}）</button></div>`
        : `<div class="muted-note">已载全部 ${String(data.total_count)} 条。</div>`)
    : '<div class="v29Empty">当前筛选条件下没有发射事件，请调整类别或裁决状态。</div>';
  return panel("批次与筛选", selectedBatch ? `${esc(selectedBatch.batch_date)} · 精确批次范围` : "精确批次范围", filterPanel) +
    panel("批次发射类别与结果概况", "统计随当前筛选条件变化；命中/未命中仅引用正式裁决", summaryPanel) +
    panel("全批次发射事件时间线", "按发射时刻展示；齐射中的每一发分别显示", renderBatchTimeline(workbench.items)) +
    panel("武器发射事件清单", "每枚武器独立事件；复盘入口在 G8 接入专项页", listPanel);
}

/* ===== G8 专项页双视角（V04/V05/V06/V08/V20/V21）与 V24 协同攻击分析 ===== */
interface WeaponDetailState {
  status: OverviewTransport;
  detail: Readonly<Record<string, unknown>> | null;
  window: Readonly<Record<string, unknown>> | null;
  perspective: "shooter" | "target";
  errorCode: string | null;
}
const WEAPON_VIEW_CATEGORY: Record<string, string> = {
  V04: "BVR", V08: "BVR", V05: "WVR", V20: "WVR", V06: "STRIKE", V21: "STRIKE",
};
const WEAPON_PAGE_TITLES: Record<string, string> = {
  V04: "超视距空战 · 单机", V08: "超视距空战 · 编队", V05: "视距内空战 · 单机",
  V20: "视距内空战 · 编队", V06: "对地攻击 · 单机", V21: "对地攻击 · 编队",
};
function renderWeaponPage(view: View): string {
  beginLayout(view.id);
  const category = WEAPON_VIEW_CATEGORY[view.id] ?? "BVR";
  const items = state.batchEvents.items.filter((item) => item.category === category);
  const selected = items.find((item) => item.weapon_event_id === state.domainSelection.weaponEventId) ?? items[0] ?? null;
  const listPanel = items.length
    ? `<div class="v26Timeline">${items.map((item) =>
      `<button type="button" class="v29BatchRow${selected && item.weapon_event_id === selected.weapon_event_id ? " selected" : ""}" data-wp-event="${esc(item.weapon_event_id)}" data-cluster="${String(Boolean(item.cluster_id))}">` +
      `<span>${formatEventTimeUs(item.t1_session_time_us)}</span><b>${esc(item.weapon_event_id.slice(0, 13))}</b>` +
      `<span>${eventCategoryLabel(item.category)}</span><span>${item.adjudication_state === "ADJUDICATED" ? "已裁决" : "待裁决"}</span>` +
      `<strong>${item.cluster_id ? "簇" : "—"}</strong><span>${esc(item.observation_window_state)}</span></button>`).join("")}</div>`
    : '<div class="v29Empty">当前精确批次范围内没有该类别的发射事件。</div>';
  const weapon = state.weaponWorkbench;
  const shooterOnly = category === "STRIKE";
  const toggle = shooterOnly
    ? '<span class="muted-note">对地攻击仅射手视角；目标视角入口服务端与界面均拒绝。</span>'
    : `<div class="selbar"><label>复盘视角<select data-wp-perspective>` +
      `<option value="shooter"${weapon.perspective === "shooter" ? " selected" : ""}>射手侧</option>` +
      `<option value="target"${weapon.perspective === "target" ? " selected" : ""}>目标侧</option></select></label></div>`;
  const facts = weapon.detail
    ? `<div class="v26Stats"><div><span>武器终止</span><b>${esc(String(weapon.detail.weapon_terminal_state ?? "—"))}</b></div>` +
      `<div><span>裁决</span><b>${esc(String(weapon.detail.adjudication_state ?? "—"))}</b></div>` +
      `<div><span>修订</span><b>${String(weapon.detail.revision_no ?? 1)}</b></div></div>`
    : statePanel(weapon.status === "READY" ? "EMPTY" : weapon.status, "事件明细尚未载入", "选择事件后由 G5 读模型提供精确事实。", "G8_WEAPON_DETAIL_PENDING");
  const windowPanel = weapon.window
    ? `<div class="v26Stats"><div><span>窗口状态</span><b>${esc(String(weapon.window.window_state ?? "—"))}</b></div>` +
      `<div><span>对齐</span><b>${esc(String(weapon.window.alignment_state ?? "—"))}</b></div>` +
      `<div><span>覆盖</span><b>${esc(String(weapon.window.coverage ?? "—"))}</b></div></div>` +
      (weapon.window.reason ? `<p class="muted-note">${esc(String(weapon.window.reason))}</p>` : "")
    : statePanel(weapon.status === "READY" ? "EMPTY" : weapon.status, "观察窗口尚未解析", "窗口由 G5 Event Window owner 解析；缺几何/共享/序列时不造图。", "G8_WINDOW_PENDING");
  const coAttackEntry = (view.id === "V08" || view.id === "V20") && selected && selected.cluster_id
    ? `<div class="mt10"><button type="button" class="v29Primary" data-wp-coattack="${esc(selected.weapon_event_id)}">协同攻击分析 →</button></div>`
    : (view.id === "V08" || view.id === "V20")
      ? '<div class="mt10"><span class="muted-note">选中带攻击簇的 BVR 事件后可进入协同攻击分析。</span></div>'
      : "";
  const exactReplayReady = selected !== null &&
    String(weapon.detail?.weapon_event_id ?? "") === selected.weapon_event_id &&
    hasText(typeof weapon.detail?.release_id === "string" ? weapon.detail.release_id : null) &&
    hasText(state.batchEvents.data?.batch_context_id);
  return panel(`${WEAPON_PAGE_TITLES[view.id] ?? view.id} · 事件清单`, "精确批次范围；每枚武器独立事件", listPanel) +
    panel("事件事实", "G5 读模型精确事实", facts + toggle + coAttackEntry) +
    panel("观察窗口", "窗口甘特由 G5 owner 提供；本页不重复推导", windowPanel) +
    panel("复盘与回放", "精确回放深链", exactReplayReady && selected
      ? `<div class="mt10"><button type="button" class="v29Primary" data-wp-replay="${esc(selected.weapon_event_id)}">精确回放 ›</button></div>`
      : statePanel(selected ? "N_A" : "EMPTY", selected ? "精确回放上下文未就绪" : "尚未选择事件", selected ? "必须先加载与当前事件一致的 Release、Context 和观察窗口，禁止仅凭 WE ID 进入回放。" : "选择事件后可进入精确回放。", selected ? "G9_EXACT_CONTEXT_PENDING" : "G9_NO_EVENT"));
}
interface CoAttackPayload {
  schema: string; request_id: string; query_context_id: string; cluster_id: string;
  batch_id: string; context_id: string | null; batch_context_id?: string | null;
  weapon_events: BatchEventItem[];
  formation: { context_id: string | null; revision_no: number | null; members: readonly { aircraft_id: string; formation_id: string | null; side: string; member_role: string; independent_target: boolean }[]; reason_code?: string };
  dimensions: readonly {
    dimension_id: string; status: string; reason: string;
    facts?: Readonly<Record<string, unknown>>;
  }[];
}
function renderCoAttackDimension(item: CoAttackPayload["dimensions"][number]): string {
  const facts = item.facts;
  if (item.dimension_id === "co_target_attack_timing" && facts) {
    const gaps = Array.isArray(facts.inter_event_gap_us)
      ? facts.inter_event_gap_us.map((value) => String(value)).join(" / ")
      : "—";
    return `<div class="g8FactCard"><header><b>同目标攻击时序</b><span>${esc(item.status)}</span></header>` +
      `<div class="v26Stats"><div><span>发射事件</span><b>${String(facts.event_count ?? 0)}</b></div>` +
      `<div><span>齐射跨度 µs</span><b>${esc(String(facts.salvo_span_us ?? "—"))}</b></div>` +
      `<div><span>同一目标</span><b>${facts.same_target === true ? "是" : "否"}</b></div></div>` +
      `<p class="muted-note">相邻发射间隔 µs：${esc(gaps)}。${esc(item.reason)}</p></div>`;
  }
  if (item.dimension_id === "role_relation" && facts) {
    const roles = Array.isArray(facts.shooter_roles)
      ? facts.shooter_roles.filter((value): value is Record<string, unknown> => typeof value === "object" && value !== null)
      : [];
    const missing = Array.isArray(facts.missing_shooter_ids)
      ? facts.missing_shooter_ids.map((value) => String(value)) : [];
    return `<div class="g8FactCard"><header><b>编队角色关系</b><span>${esc(item.status)}</span></header>` +
      (roles.length
        ? `<div class="v26CatChips">${roles.map((role) => `<span class="v26Chip">${esc(String(role.aircraft_id ?? "—").slice(0, 8))} <b>${esc(String(role.member_role ?? "—"))}</b></span>`).join("")}</div>`
        : '<div class="v29Empty">当前 Context 没有覆盖 Cluster 的射手角色事实。</div>') +
      (missing.length ? `<p class="muted-note">未绑定编队角色：${esc(missing.join("、"))}</p>` : "") +
      `<p class="muted-note">${esc(item.reason)}</p></div>`;
  }
  return `<div class="v26Chip"><span>${esc(item.dimension_id)}</span> <b>${esc(item.status)}</b><small>${esc(item.reason)}</small></div>`;
}
function renderCoAttack(): string {
  beginLayout("V24");
  const data = state.coAttack.data;
  if (!data || state.coAttack.status !== "READY") {
    return panel("同目标攻击时序", "精确 Cluster 范围", statePanel(
      state.coAttack.status, "协同攻击分析尚未载入", esc(state.coAttack.errorCode ?? "G8_CO_ATTACK_PENDING"), "G8_CO_ATTACK_PENDING"));
  }
  const timing = data.weapon_events.length
    ? `<div class="v26Timeline">${data.weapon_events.map((item) =>
      `<div class="v26TrackRow"><span class="v26TrackTime">${formatEventTimeUs(item.t1_session_time_us)}</span>` +
      `<i class="v26TrackBar"><b data-color="#55a9e5"></b></i><span class="v26TrackCat">${esc(item.shooter_entity_id.slice(0, 6))} → ${esc(String(item.target_entity_id ?? "—").slice(0, 6))}</span></div>`).join("")}</div>`
    : '<div class="v29Empty">Cluster 内没有发射事件。</div>';
  const members = data.formation.members.length
    ? `<table class="batch-table"><thead><tr><th>航空器</th><th>编队</th><th>阵营</th><th>角色</th><th>独立目标</th></tr></thead><tbody>${data.formation.members.map((member) =>
      `<tr><td class="mono">${esc(member.aircraft_id.slice(0, 8))}</td><td>${esc(String(member.formation_id ?? "—"))}</td><td>${esc(member.side)}</td><td>${esc(member.member_role)}</td><td>${member.independent_target ? "是" : "否"}</td></tr>`).join("")}</tbody></table>`
    : statePanel("EMPTY", "编队上下文未绑定", esc(data.formation.reason_code ?? "FORMATION_CONTEXT_NOT_PROVIDED_OR_ABSENT") + "；不以演示数据填充。", "G8_FORMATION_EMPTY");
  const dimensions = data.dimensions.map(renderCoAttackDimension).join("");
  return panel("同目标攻击时序", `Cluster ${esc(data.cluster_id.slice(0, 8))} · query_context ${esc(data.query_context_id)}`, timing) +
    panel("编队成员（角色关系事实）", `context ${esc(String(data.context_id ?? "—"))} · 修订 ${String(data.formation.revision_no ?? "—")}`, members) +
    panel("五维协同链", "真实时序与角色事实；不形成总分，未准入维度不造图", `<div class="g8Dims">${dimensions}</div>`) +
    panel("感知—攻击关系", "缺几何/共享/序列不造图", statePanel("N_A", "关系图待证据准入", "探测/几何证据未准入前，本面板保持关闭。", "G8_GEOMETRY_NOT_ADMITTED"));
}


/* ===== G10 其余视图产品化闭合（真实 owner / 受控不可用，不合成数据） ===== */
const P3_CONTROLLED_VIEWS = new Set(["V11", "V12", "V13", "V14", "V15"]);
const CLOSURE_VIEW_TITLES: Record<string, string> = {
  V02: "架次综合复盘", V07: "基本飞行 · 单机", V09: "分类长期成长", V10: "型号与机体性能总览",
  V11: "机动包线 E-M", V12: "探测性能", V13: "告警性能", V14: "攻击系统性能", V15: "条件因子分离",
  V16: "性能趋势与告警", V17: "数据质量与资格", V18: "报告：架次复盘", V19: "基本飞行 · 编队", V22: "管理与版本治理",
};
function _notAdmittedPanel(title: string, authority: string, reason: string): string {
  return statePanel("N_A", `${title} 读模型未准入`, `${reason}（${authority} admission_status=NOT_ADMITTED）；按受控不可用呈现，不合成数据。`, "G10_NOT_ADMITTED");
}
function renderViewClosure(view: View): string {
  beginLayout(view.id);
  const id = view.id;
  const overview = state.overview.data;
  if (P3_CONTROLLED_VIEWS.has(id)) {
    const labels: Record<string, string> = {
      V11: "机动包线 E-M", V12: "探测性能", V13: "告警性能", V14: "攻击系统性能", V15: "条件因子分离",
    };
    return panel(labels[id], "P3 Model Profile", _notAdmittedPanel(labels[id], "GUI_P3_PROFILE_AUTHORITY", "P3 Model Profile  Metric Authority 未准入")) +
      panel("准入规则", "单一 owner：tpaa_application.p3_profile", statePanel("N_A", "未准入前不展示 Profile", "不合成 P3 能力剖面；准入后由 P3 读模型提供精确事实。", "G10_P3_PROFILE_NOT_ADMITTED")) +
      panel("批次范围", "精确批次集合", _kpiOverviewPanel()) +
      panel("数据资格", "以批次数据资格摘要为准", _qualificationPanel());
  }
  if (id === "V18") {
    return panel("报告：架次复盘", "不可变 revision 规则已固化", _notAdmittedPanel("报告 revision", "GUI_REPORT_REVISION_AUTHORITY", "报告 revision 服务未准入")) +
      panel("不可变规则", "revision 追加式、不可变", statePanel("N_A", "报告 revision 不可变", "每次报告生成新 revision，不覆盖历史；服务准入后启用。", "G10_REPORT_REVISION_NOT_ADMITTED")) +
      panel("批次范围", "精确批次集合", _kpiOverviewPanel()) +
      panel("数据资格", "以批次数据资格摘要为准", _qualificationPanel());
  }
  if (id === "V22") {
    return panel("管理与版本治理", "治理 mutation 权限/审计规则已固化", _notAdmittedPanel("结构化治理", "GUI_GOVERNANCE_AUTHORITY", "治理 mutation 服务未准入")) +
      panel("权限说明", "governance.audit.read", statePanel("READY", "治理审计只读说明", "治理 mutation 将全部经过权限校验与审计；当前仅呈现受控说明。", "G10_GOVERNANCE_NOT_ADMITTED")) +
      panel("批次范围", "精确批次集合", _kpiOverviewPanel()) +
      panel("数据资格", "以批次数据资格摘要为准", _qualificationPanel());
  }
  if (id === "V09") {
    const cat = overview?.category_composition;
    return panel("分类长期成长", "跨批次行为类别构成（合计口径）",
      cat ? `<div class="v26CatChips"><span class="v26Chip">跨批次武器发射合计 <b>${String(cat.total_weapon_events)}</b></span></div><div class="v29Empty">WVR/BVR/STRIKE 逐批次分布由 V26 工作台所有；本页仅呈现 V01 精确合计。</div>` : statePanel("LOADING", "正在读取历史聚合", "本页复用 V01 精确批次集合。", "G10_OVERVIEW_PENDING")) +
      panel("历史训练活动趋势", "复用 V01 活动趋势", _activityPanel()) +
      panel("训练结果与裁决状态", "复用 V01 裁决口径", _outcomePanel()) +
      panel("装备性能趋势", "未准入指标不展示", _equipmentPanel());
  }
  if (id === "V16") {
    return panel("性能趋势与告警", "装备性能历史趋势", _equipmentPanel()) +
      panel("训练结果与裁决状态", "复用 V01 裁决口径", _outcomePanel()) +
      panel("历史训练活动趋势", "复用 V01 活动趋势", _activityPanel()) +
      panel("批次范围", "精确批次集合", _kpiOverviewPanel());
  }
  if (id === "V10") {
    return panel("型号与机体性能总览", "六 KPI 与装备准入状态", _kpiOverviewPanel()) +
      panel("装备性能历史趋势", "未准入指标不展示", _equipmentPanel()) +
      panel("历史训练活动趋势", "复用 V01 活动趋势", _activityPanel()) +
      panel("数据资格", "以批次数据资格摘要为准", _qualificationPanel());
  }
  if (id === "V02") {
    return panel("架次综合复盘", "精确批次范围事件与统计", _kpiOverviewPanel()) +
      panel("批次发射事件", "复用 V26 工作台口径", _qualificationPanel()) +
      panel("训练结果与裁决状态", "复用 V01 裁决口径", _outcomePanel()) +
      panel("进入批次工作台", "V26", `<div class="mt10"><button type="button" data-view="V26">打开批次发射事件工作台 ›</button></div>`);
  }
  if (id === "V17") {
    return panel("数据质量与资格", "QUALIFIED 批次清单", _qualificationPanel(true)) +
      panel("数据资格汇总", "资格状态统计", _kpiOverviewPanel()) +
      panel("历史训练活动趋势", "复用 V01 活动趋势", _activityPanel()) +
      panel("数据管理入口", "V23", `<div class="mt10"><button type="button" data-view="V23">打开数据管理 ›</button></div>`);
  }
  if (id === "V07" || id === "V19") {
    const scope = id === "V07" ? "单机" : "编队";
    return panel(`基本飞行（${scope}）`, "独立于武器发射主线", statePanel("N_A", "基本飞行过程数据未准入", "未发射行为/基本飞行过程由 G10 来源覆盖矩阵（后续）准入；当前不以演示数据填充。", "G10_BASIC_FLIGHT_NOT_ADMITTED")) +
      panel("批次范围", "精确批次集合", _kpiOverviewPanel()) +
      panel("历史训练活动趋势", "复用 V01 活动趋势", _activityPanel()) +
      panel("数据资格", "以批次数据资格摘要为准", _qualificationPanel());
  }
  return panel(view.title, view.id, statePanel("N_A", "视图读模型未准入", "以受控不可用呈现。", "G10_VIEW_NOT_ADMITTED"));
}
function _kpiOverviewPanel(): string {
  const kpi = state.overview.data?.kpi;
  if (!kpi) return statePanel("LOADING", "正在读取历史聚合", "复用 V01 精确批次集合。", "G10_OVERVIEW_PENDING");
  return `<div class="v26Stats"><div><span>历史批次</span><b>${String(kpi.batch_count)}</b></div>` +
    `<div><span>武器发射</span><b>${String(kpi.weapon_event_count)}</b></div>` +
    `<div><span>已正式裁决</span><b>${String(kpi.adjudicated_event_count)}</b></div></div>`;
}
function _qualificationPanel(asTable = false): string {
  const batches = state.overview.data?.batches ?? [];
  if (!batches.length) return statePanel("EMPTY", "当前精确查询范围没有可展示记录", "不会使用其他批次或演示数据填充空结果。", "EXACT_QUERY_EMPTY");
  const rows = batches.map((item) => `<tr><td>${esc(item.batch_date)}</td><td class="mono">${esc(item.batch_id.slice(0, 13))}</td>` +
    `<td><span class="pill">${esc(item.qualification_status)}</span></td><td>${item.has_event_detail ? "逐事件明细已加载" : "资格确认"}</td></tr>`).join("");
  const table = `<table class="batch-table"><thead><tr><th>日期</th><th>批次</th><th>资格状态</th><th>数据状态</th></tr></thead><tbody>${rows}</tbody></table>`;
  return asTable ? table : table;
}
function _activityPanel(): string {
  const points = state.overview.data?.activity_trend.points ?? [];
  if (!points.length) return statePanel("EMPTY", "当前筛选条件下暂无活动趋势数据", "请调整 V01 筛选条件。", "G10_ACTIVITY_EMPTY");
  return overviewActivitySvg(points);
}
function _outcomePanel(): string {
  const outcome = state.overview.data?.outcome_trend;
  if (!outcome) return statePanel("LOADING", "正在读取历史聚合", "复用 V01 精确批次集合。", "G10_OVERVIEW_PENDING");
  return overviewOutcomeSvg(outcome);
}
function _equipmentPanel(): string {
  const trends = state.overview.data?.equipment_trends ?? [];
  if (!trends.length) return statePanel("EMPTY", "装备性能指标尚未经 Metric Authority 准入", "未准入指标不展示趋势，不使用演示样例填充。", "G6_EQUIPMENT_NOT_ADMITTED");
  return `<div class="v26CatChips">${trends.map((trend) => `<span class="v26Chip">${esc(trend.label)} <b>${esc(trend.comparable ? "可比对" : "NOT_COMPARABLE")}</b></span>`).join("")}</div>`;
}

/* ===== V23 批次登记与导入（真实 G4 能力） ===== */
function renderG4RevisionPanels(receipt: BatchRegistrationDTO | null): string {
  if (!receipt) return "";
  const trainingRevision = `<section class="revision-panel"><div class="rev-head"><b>训练类型修订</b> <span class="state-pill state-ready">修订号 ${String(receipt.revision_no)}</span></div>
    <form id="training-type-revision-form" class="rev-form-inline"><label class="fld">明确训练类型<select name="batch_training_type" required><option value="">请选择</option><option value="SIMPLE_OPPOSITION">简单对抗</option><option value="MIXED_OPPOSITION">混合对抗</option><option value="COMPREHENSIVE_OPPOSITION">综合对抗</option></select></label><label class="fld">修订原因<input name="reason" required autocomplete="off" maxlength="512"></label><button class="btn-submit" type="submit">提交审计修订</button></form></section>`;
  const contextId = receipt.context_id ?? state.domainSelection.contextId;
  if (!contextId) {
    return trainingRevision + '<section class="revision-panel state-na"><b>编队上下文尚未绑定</b><p class="muted-note">登记批次时填写编队上下文 ID 后，才能建立带有效时间和成员阵营的审计修订。</p></section>';
  }
  const contextReceipt = state.batchImport.contextReceipt;
  return trainingRevision + `<section class="revision-panel"><div class="rev-head"><b>兵力与编队上下文修订</b> <span class="state-pill ${contextReceipt ? "state-ready" : "state-na"}">${contextReceipt ? "已保存修订 " + String(contextReceipt.revision_no) : "等待修订"}</span></div>
    <p class="muted-note">上下文 ID：${esc(contextId)}。每次提交均追加新修订并写入审计日志，不覆盖历史。</p>
    <form id="force-formation-form" class="form-grid"><label class="fld">生效起点（微秒）<input name="valid_from_session_time_us" type="number" min="0" required value="0"></label><label class="fld">失效终点（微秒，可选）<input name="valid_to_session_time_us" type="number" min="1"></label><label class="fld">来源<input name="source" required value="MANUAL_REVIEWED"></label><label class="fld">修订原因<input name="reason" required autocomplete="off" maxlength="512"></label><label class="fld">成员航空器 ID<input name="member_aircraft_id" required autocomplete="off" placeholder="UUID"></label><label class="fld">编队 ID（可选）<input name="formation_id" autocomplete="off"></label><label class="fld">阵营<select name="side" required><option value="">请选择</option><option value="RED">红方</option><option value="BLUE">蓝方</option><option value="NEUTRAL">中立</option><option value="UNASSIGNED">未分配</option><option value="CONFLICT">冲突待裁决</option></select></label><label class="fld">成员角色<input name="member_role" required value="MEMBER"></label><label class="fld fld-wide"><input name="independent_target" type="checkbox"> 独立目标</label><button class="btn-submit" type="submit">追加上下文修订</button></form></section>`;
}
function renderBatchImport(): string {
  beginLayout("V23");
  const ticket = state.batchImport.ticket;
  const receipt = state.batchImport.receipt;
  const workbench = `<div class="selbar v23-bar">
      <button type="button" data-action="select-file"${state.batchImport.working ? " disabled" : ""}>选择 CSV 文件</button>
      <button type="button" data-action="select-directory"${state.batchImport.working ? " disabled" : ""}>选择 CSV 目录</button>
      ${ticket ? `<div class="ticket-card"><span>票据</span><strong>${esc(ticket.ticket_id)}</strong><span>${String(ticket.entry_count)} 个文件 / ${String(ticket.size_bytes)} 字节</span><span>有效期至 ${esc(ticket.expires_at)}</span></div>` : '<span class="muted">尚未选择数据 · 本机路径不向前端暴露</span>'}
    </div>
    <form id="batch-registration-form" class="form-grid top-gap">
      <label class="fld">训练架次 ID<input name="session_id" required autocomplete="off" placeholder="UUID"></label>
      <label class="fld">航空器 ID<input name="aircraft_id" required autocomplete="off" placeholder="UUID"></label>
      <label class="fld">批次日期<input name="batch_date" type="date" required></label>
      <label class="fld">训练类型<select name="batch_training_type" required><option value="">请选择，不设默认值</option><option value="SIMPLE_OPPOSITION">简单对抗</option><option value="MIXED_OPPOSITION">混合对抗</option><option value="COMPREHENSIVE_OPPOSITION">综合对抗</option><option value="UNCLASSIFIED">暂不分类（待后续明确确认）</option></select></label>
      <label class="fld">数据生产系统<input name="producer_system" required value="RECORDER_EXPORT"></label>
      <label class="fld">架次代码<input name="session_code" required autocomplete="off"></label>
      <label class="fld">架次类型<select name="session_type" required><option value="">请选择</option><option value="LIVE">实装</option><option value="SIM">模拟</option><option value="LVC">虚实结合</option></select></label>
      <label class="fld">编队上下文 ID（可选）<input name="context_id" autocomplete="off" placeholder="UUID"></label>
      <label class="fld fld-wide"><input name="training_type_confirmed" type="checkbox"> 除“暂不分类”外，我已核对并明确确认训练类型</label>
      <button type="submit" class="themeSetButton btn-submit"${!ticket || state.batchImport.working ? " disabled" : ""}>${state.batchImport.working ? "正在解析与资格校验…" : "登记、解析并进入总览"}</button>
    </form>
    ${state.batchImport.errorCode ? `<p class="err-text" role="alert">${esc(state.batchImport.errorCode)}</p>` : ""}
    ${receipt ? `<p class="ok-text">批次 ${esc(receipt.batch_id)} 已达到 ${esc(receipt.qualification_status)}。</p>` : ""}`;
  return panel("导入工作台", "选择 → 登记 → 解析 → 资格确认", workbench) +
    panel("五类核心数据", "飞行/总线/ACMI/任务场景/音视频", statePanel("N_A", "来源覆盖矩阵待 G10 接入", "来源域覆盖与架次归并矩阵由数据管理读模型提供；当前登记流程已可用。", "G10_SOURCE_MATRIX_PENDING")) +
    panel("导入与解析队列", "原始文件先登记 provenance", statePanel("N_A", "解析队列读模型待接入", "导入与解析队列由后端登记投影提供。", "G10_IMPORT_QUEUE_PENDING")) +
    panel("选中批次修订", "追加式审计修订", renderG4RevisionPanels(receipt) || statePanel("EMPTY", "尚无已登记批次", "完成一次登记后可在此提交训练类型与编队上下文修订。", "G4_NO_RECEIPT"));
}

function renderViewBody(view: View, status: UiState): string {
  if (view.id === "V25") return renderThemes();
  if (view.id === "V01" && state.authorization.status === "READY") return renderOverview();
  if (view.id === "V26" && state.authorization.status === "READY") return renderBatchEvents();
  if (view.id in WEAPON_VIEW_CATEGORY && state.authorization.status === "READY") return renderWeaponPage(view);
  if (view.id === "V24" && state.authorization.status === "READY" && canNavigate("V24")) return renderCoAttack();
  if (view.id === "V03" && state.authorization.status === "READY") return renderReplay();
  if (view.id in CLOSURE_VIEW_TITLES && state.authorization.status === "READY") return renderViewClosure(view);
  if (view.id === "V23" && state.authorization.status === "READY") return renderBatchImport();
  beginLayout(view.id);
  // V24 是条件下钻页，不作为普通 Ribbon 导航项渲染；其余常规视图进入受控状态面板。
  const isRibbon = view.id !== "V24";
  const content = statusCopy(status);
  const contract = viewContracts.get(view.id);
  const missing = contract?.required_context.filter((field) => !hasText(contextValue(field))) ?? [];
  const contextMessage = missing.length ? "缺少精确上下文：" + missing.join("、") : "当前阶段尚未接入业务读模型。";
  const notice = state.notice?.viewId === view.id ? state.notice : null;
  return panel(
    view.title,
    isRibbon ? view.id : "CONDITIONAL_DEEPLINK",
    statePanel(status, notice ? notice.title : content.title, notice ? notice.message : content.message + " " + contextMessage, notice ? notice.code : content.code),
  );
}

/** 主题预览 mock 的 CSS 自定义属性与色板颜色经 CSSOM 应用（绕开内联 style CSP）。 */
function applyDynamicPresentation(scope: ParentNode): void {
  const props = ["--pr-bg", "--pr-panel", "--pr-panel2", "--pr-border", "--pr-a", "--pr-t", "--pr-m", "--pr-g", "--pr-o"];
  scope.querySelectorAll<HTMLElement>(".themeMock[data-pr]").forEach((element) => {
    const values = (element.dataset.pr ?? "").split("|");
    props.forEach((name, index) => {
      const value = values[index];
      if (value) element.style.setProperty(name, value);
    });
  });
  scope.querySelectorAll<HTMLElement>(".palette-swatch[data-color]").forEach((element) => {
    const value = element.dataset.color;
    if (value) element.style.background = value;
  });
  // v29 图例色点与来源条宽度经 data-* 传递，渲染后由 CSSOM 应用（绕开内联 style CSP）。
  scope.querySelectorAll<HTMLElement>("[data-color]").forEach((element) => {
    const value = element.dataset.color;
    if (value && !element.classList.contains("palette-swatch")) element.style.background = value;
  });
  scope.querySelectorAll<HTMLElement>("[data-w]").forEach((element) => {
    const value = element.dataset.w;
    if (value) element.style.width = value;
  });
}

function render(): void {
  let focusTarget: { key: "action" | "view" | "module" | "theme" | "main" | "skip"; value: string } | null = null;
  const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  if (active && root.contains(active)) {
    if (active.id === "main-content") focusTarget = { key: "main", value: "" };
    else if (active.classList.contains("skip-link")) focusTarget = { key: "skip", value: "" };
    else {
      for (const key of ["action", "view", "module", "theme"] as const) {
        const value = active.dataset[key];
        if (value) { focusTarget = { key, value }; break; }
      }
    }
  }
  const view = currentView();
  const module = modules.get(view.module);
  if (!module) throw new Error("TPAA_VIEW_MODULE_MISSING");
  const status = viewState(view);
  assignTheme(document.documentElement, state.presentation.theme);
  root.dataset.currentView = view.id;
  root.dataset.currentModule = view.module;
  root.classList.toggle("ribbon-collapsed", state.presentation.ribbonCollapsed);
  root.innerHTML = [
    '<a class="skip-link" href="#main-content">跳转到主要内容</a>',
    '<div class="apphead"><div class="apptitle">空战训练评估系统</div>',
    `<div class="mainmenu">${renderMainMenu(state.navigation.activeModuleId)}</div>`,
    `<div class="submenu"><div class="subgroups">${renderSubmenu(state.navigation.activeModuleId, state.navigation.currentViewId, canNavigate)}</div></div>`,
    `<button type="button" class="ribbon-toggle" data-action="toggle-ribbon" aria-expanded="${String(!state.presentation.ribbonCollapsed)}" title="${state.presentation.ribbonCollapsed ? "展开功能区" : "收起功能区"}">${state.presentation.ribbonCollapsed ? "⌄" : "⌃"}</button></div>`,
    `<main id="main-content" tabindex="-1" aria-label="${esc(view.title)}">${renderViewBody(view, status)}</main>`,
    `<div class="ft">TPAA v33 · ${esc(module.label)} / ${esc(view.id)} · 权限 ${esc(state.authorization.status)} · 主题 ${esc(state.presentation.theme)} · GUI-DEMO-V33-2026-11-05</div>`,
  ].join("");
  fitCanvas(root);
  // CSP（style-src 'self'）禁止内联 style 属性：动态几何与主题预览变量在 innerHTML 后经由 CSSOM 应用。
  applyPanelGeometry(root);
  applyDynamicPresentation(root);

  const target = focusTarget;
  if (target?.key === "main") root.querySelector<HTMLElement>("#main-content")?.focus();
  else if (target?.key === "skip") root.querySelector<HTMLAnchorElement>(".skip-link")?.focus();
  else if (target) {
    const restored = Array.from(root.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.dataset[target.key] === target.value);
    if (restored && !restored.disabled) restored.focus();
    else root.querySelector<HTMLElement>("#main-content")?.focus();
  }
  root.querySelectorAll<HTMLButtonElement>("[data-module]").forEach((button) =>
    button.addEventListener("click", () => navigateToModule(button.dataset.module as ModuleId)));
  root.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) =>
    button.addEventListener("click", () => navigateToView(button.dataset.view ?? "")));
  root.querySelectorAll<HTMLButtonElement>("[data-theme]").forEach((button) =>
    button.addEventListener("click", () => {
      const value = button.dataset.theme;
      if (value && isTheme(value)) setTheme(value);
    }));
  root.querySelector<HTMLButtonElement>('[data-action="toggle-ribbon"]')?.addEventListener("click", toggleRibbon);
  root.querySelectorAll<HTMLButtonElement>("[data-batch-id]").forEach((button) => button.addEventListener("click", () => {
    state.domainSelection.batchId = button.dataset.batchId ?? null;
    render();
  }));
  root.querySelectorAll<HTMLElement>("[data-v29-filter]").forEach((control) =>
    control.addEventListener("change", () => {
      const key = control.dataset.v29Filter ?? "";
      if (key === "startDate" || key === "endDate" || key === "model" || key === "trainingType") {
        const input = control instanceof HTMLInputElement || control instanceof HTMLSelectElement ? control.value : "";
        state.overview.filters[key] = input;
        void loadOverview();
      }
    }));
  root.querySelectorAll<HTMLElement>("[data-v29-equip]").forEach((control) =>
    control.addEventListener("change", () => {
      if (control instanceof HTMLSelectElement) {
        state.overview.filters.equip = control.value;
        render();
      }
    }));
  root.querySelectorAll<HTMLButtonElement>("[data-v29-batch]").forEach((button) =>
    button.addEventListener("click", () => {
      state.overview.selectedBatchId = button.dataset.v29Batch ?? null;
      state.domainSelection.batchId = state.overview.selectedBatchId;
      render();
    }));
  root.querySelectorAll<HTMLButtonElement>('[data-v29-open-v09]').forEach((button) =>
    button.addEventListener("click", () => { void navigateToView("V09"); }));
  root.querySelectorAll<HTMLButtonElement>('[data-v29-open-v16]').forEach((button) =>
    button.addEventListener("click", () => { void navigateToView("V16"); }));
  root.querySelectorAll<HTMLButtonElement>('[data-v29-open-selected]').forEach((button) =>
    button.addEventListener("click", () => {
      if (state.overview.selectedBatchId) state.domainSelection.batchId = state.overview.selectedBatchId;
      void navigateToView("V26");
    }));
  root.querySelectorAll<HTMLElement>("[data-v26-filter]").forEach((control) =>
    control.addEventListener("change", () => {
      const key = control.dataset.v26Filter ?? "";
      if (control instanceof HTMLSelectElement && (key === "category" || key === "adjudication")) {
        state.batchEvents.filters[key] = control.value;
        if (state.batchEvents.batchId) void loadBatchEvents(state.batchEvents.batchId, null);
      } else if (control instanceof HTMLInputElement &&
        (key === "entityId" || key === "episodeId" || key === "startTimeUs" || key === "endTimeUs")) {
        state.batchEvents.filters[key] = control.value.trim();
        if (state.batchEvents.batchId) void loadBatchEvents(state.batchEvents.batchId, null);
      }
    }));
  root.querySelectorAll<HTMLElement>("[data-v26-batch]").forEach((control) =>
    control.addEventListener("change", () => {
      if (control instanceof HTMLSelectElement && control.value) {
        state.domainSelection.batchId = control.value;
        void loadBatchEvents(control.value, null);
      }
    }));
  root.querySelectorAll<HTMLButtonElement>("[data-v26-more]").forEach((button) =>
    button.addEventListener("click", () => {
      if (state.batchEvents.batchId && state.batchEvents.nextCursor) {
        void loadBatchEvents(state.batchEvents.batchId, state.batchEvents.nextCursor);
      }
    }));
  root.querySelectorAll<HTMLButtonElement>("[data-v26-open]").forEach((button) =>
    button.addEventListener("click", () => {
      const eventId = button.dataset.event;
      if (eventId) state.domainSelection.weaponEventId = eventId;
      void navigateToView(button.dataset.v26Open ?? "V04");
    }));
  root.querySelectorAll<HTMLButtonElement>("[data-wp-event]").forEach((button) =>
    button.addEventListener("click", () => {
      const eventId = button.dataset.wpEvent;
      if (eventId) void loadWeaponFacts(eventId);
    }));
  root.querySelectorAll<HTMLElement>("[data-wp-perspective]").forEach((control) =>
    control.addEventListener("change", () => {
      if (control instanceof HTMLSelectElement && (control.value === "shooter" || control.value === "target")) {
        state.weaponWorkbench.perspective = control.value;
        if (state.domainSelection.weaponEventId) {
          void loadWeaponFacts(state.domainSelection.weaponEventId);
        }
      }
    }));
  root.querySelectorAll<HTMLButtonElement>("[data-wp-replay]").forEach((button) =>
    button.addEventListener("click", () => {
      const eventId = button.dataset.wpReplay;
      if (eventId) state.domainSelection.weaponEventId = eventId;
      state.domainSelection.releaseId = String(state.weaponWorkbench.detail?.release_id ?? "") || null;
      state.domainSelection.contextId = state.batchEvents.data?.batch_context_id ?? null;
      void navigateToView("V03");
    }));
  root.querySelectorAll<HTMLButtonElement>("[data-wp-coattack]").forEach((button) =>
    button.addEventListener("click", () => {
      const eventId = button.dataset.wpCoattack;
      const item = state.batchEvents.items.find((entry) => entry.weapon_event_id === eventId);
      const batchContextId: string | null = state.batchEvents.data?.batch_context_id ?? null;
      if (!item || !item.cluster_id || !batchContextId) {
        setForbidden("V08", "协同攻击入口上下文不完整", "必须由后端提供精确的 BVR Attack Cluster 与编队上下文；当前事件缺少 cluster 或批次未绑定上下文。", "V24_CONTROLLED_ENTRY_NOT_AVAILABLE");
        render();
        return;
      }
      void (async () => {
        if (String(state.weaponWorkbench.detail?.weapon_event_id ?? "") !== item.weapon_event_id) {
          await loadWeaponFacts(item.weapon_event_id);
        }
        if (String(state.weaponWorkbench.detail?.weapon_event_id ?? "") !== item.weapon_event_id) {
          setForbidden("V08", "协同攻击入口事件事实未就绪", "当前事件的精确 Release/WE 事实尚未成功加载；拒绝使用其他事件的上下文。", "V24_EVENT_CONTEXT_STALE");
          render();
          return;
        }
        const releaseId = String(state.weaponWorkbench.detail?.release_id ?? "");
        let formationId = "";
        try {
          const context = await guiClient.context(batchContextId);
          formationId = context.members[0]?.formation_id ?? "";
        } catch {
          formationId = "";
        }
        enterV24FromV08({
          sourceView: "V08", eventCategory: "BVR", releaseId,
          contextId: batchContextId, weaponEventId: item.weapon_event_id,
          attackClusterId: item.cluster_id ?? "", formationId,
        });
      })();
    }));
  root.querySelector<HTMLFormElement>("#batch-registration-form")?.addEventListener("submit", (event) => void submitBatch(event));
  root.querySelector<HTMLFormElement>("#training-type-revision-form")?.addEventListener("submit", (event) => void submitTrainingTypeRevision(event));
  root.querySelector<HTMLFormElement>("#force-formation-form")?.addEventListener("submit", (event) => void submitForceFormationRevision(event));
  root.querySelectorAll<HTMLButtonElement>('[data-action="select-file"]').forEach((b) => b.addEventListener("click", () => void chooseImportSource("FILE")));
  root.querySelectorAll<HTMLButtonElement>('[data-action="select-directory"]').forEach((b) => b.addEventListener("click", () => void chooseImportSource("DIRECTORY")));
}

async function chooseImportSource(kind: "FILE" | "DIRECTORY"): Promise<void> {
  state.batchImport.errorCode = null;
  try {
    const ticket = await selectImportSource(kind);
    if (!ticket) return;
    state.batchImport.ticket = ticket;
    state.batchImport.idempotencyKey = crypto.randomUUID();
    state.batchImport.receipt = null;
    state.batchImport.contextReceipt = null;
  } catch (error) {
    state.batchImport.errorCode = error instanceof Error ? error.message : "NATIVE_IMPORT_FAILED";
  }
  render();
}
async function submitBatch(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget;
  if (!(form instanceof HTMLFormElement) || !state.batchImport.ticket || !state.batchImport.idempotencyKey) return;
  const data = new FormData(form);
  const value = (name: string): string => String(data.get(name) ?? "").trim();
  const trainingType = value("batch_training_type");
  const trainingTypeConfirmed = data.get("training_type_confirmed") === "on";
  if ((trainingType === "UNCLASSIFIED" && trainingTypeConfirmed) || (trainingType !== "UNCLASSIFIED" && !trainingTypeConfirmed)) {
    state.batchImport.errorCode = trainingType === "UNCLASSIFIED" ? "G4_UNCLASSIFIED_MUST_REMAIN_UNCONFIRMED" : "G4_TRAINING_TYPE_CONFIRMATION_REQUIRED";
    render();
    return;
  }
  state.batchImport.working = true;
  state.batchImport.errorCode = null;
  const request = {
    ticket_id: state.batchImport.ticket.ticket_id,
    session_id: value("session_id"), aircraft_id: value("aircraft_id"), batch_date: value("batch_date"),
    batch_training_type: trainingType, training_type_confirmed: trainingTypeConfirmed,
    producer_system: value("producer_system"), session_code: value("session_code"), session_type: value("session_type"),
    context_id: value("context_id") || null,
  };
  render();
  try {
    const receipt = await guiClient.registerBatch(state.batchImport.idempotencyKey, request);
    state.batchImport.receipt = receipt;
    state.domainSelection.batchId = receipt.batch_id;
    state.domainSelection.sessionId = receipt.session_id;
    state.domainSelection.contextId = receipt.context_id;
    if (receipt.qualification_status !== "QUALIFIED") {
      state.batchImport.errorCode = receipt.reason_code ?? receipt.qualification_status;
      return;
    }
    navigateToView("V01");
  } catch (error) {
    state.batchImport.errorCode = error instanceof GatewayError ? error.code : "G4_BATCH_REGISTER_FAILED";
  } finally {
    state.batchImport.working = false;
    render();
  }
}
async function submitTrainingTypeRevision(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget;
  const receipt = state.batchImport.receipt;
  if (!(form instanceof HTMLFormElement) || !receipt) return;
  const data = new FormData(form);
  state.batchImport.working = true;
  state.batchImport.errorCode = null;
  render();
  try {
    const revised = await guiClient.reviseBatchTrainingType(receipt.batch_id, {
      batch_training_type: String(data.get("batch_training_type") ?? "").trim(),
      reason: String(data.get("reason") ?? "").trim(),
    });
    state.batchImport.receipt = revised;
    state.domainSelection.batchId = revised.batch_id;
  } catch (error) {
    state.batchImport.errorCode = error instanceof GatewayError ? error.code : "G4_TRAINING_TYPE_REVISION_FAILED";
  } finally {
    state.batchImport.working = false;
    render();
  }
}
async function submitForceFormationRevision(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget;
  const contextId = state.batchImport.receipt?.context_id ?? state.domainSelection.contextId;
  if (!(form instanceof HTMLFormElement) || !contextId) return;
  const data = new FormData(form);
  const text = (name: string): string => String(data.get(name) ?? "").trim();
  const validTo = text("valid_to_session_time_us");
  state.batchImport.working = true;
  state.batchImport.errorCode = null;
  render();
  try {
    state.batchImport.contextReceipt = await guiClient.reviseContext(contextId, {
      valid_from_session_time_us: Number(text("valid_from_session_time_us")),
      valid_to_session_time_us: validTo ? Number(validTo) : null,
      source: text("source"), reason: text("reason"),
      members: [{
        aircraft_id: text("member_aircraft_id"), formation_id: text("formation_id") || null,
        side: text("side"), member_role: text("member_role"),
        independent_target: data.get("independent_target") === "on",
      }],
    });
  } catch (error) {
    state.batchImport.errorCode = error instanceof GatewayError ? error.code : "G4_FORCE_FORMATION_REVISION_FAILED";
  } finally {
    state.batchImport.working = false;
    render();
  }
}
async function loadOverview(): Promise<void> {
  if (state.authorization.status !== "READY") return;
  state.overview.status = "LOADING";
  state.overview.errorCode = null;
  render();
  try {
    const f = state.overview.filters;
    const payload = await guiClient.historicalOverview({
      startDate: f.startDate || undefined,
      endDate: f.endDate || undefined,
      model: f.model,
      trainingType: f.trainingType,
    });
    state.overview.data = payload as unknown as OverviewPayload;
    const batches = state.overview.data.batches;
    if (!batches.some((item) => item.batch_id === state.overview.selectedBatchId)) {
      state.overview.selectedBatchId = batches.length
        ? batches[batches.length - 1].batch_id
        : null;
    }
    state.overview.status = "READY";
    if (state.navigation.currentViewId === "V26") ensureBatchEvents();
  } catch (error) {
    state.overview.status = error instanceof GatewayError
      && (error.code === "TIMEOUT" || error.code === "BACKEND_UNAVAILABLE") ? "DEGRADED" : "ERROR";
    state.overview.errorCode = error instanceof GatewayError ? error.code : "G6_OVERVIEW_FAILED";
  }
  render();
}
function _defaultBatchEventsBatch(): string | null {
  const batches = state.overview.data?.batches ?? [];
  if (!batches.length) return null;
  const requested = state.domainSelection.batchId;
  if (requested && batches.some((item) => item.batch_id === requested)) return requested;
  return state.overview.selectedBatchId ?? batches[batches.length - 1].batch_id;
}
async function loadBatchEvents(batchId: string | null, cursor: string | null): Promise<void> {
  if (state.authorization.status !== "READY" || !batchId) return;
  state.batchEvents.status = "LOADING";
  state.batchEvents.errorCode = null;
  render();
  try {
    const f = state.batchEvents.filters;
    const payload = await guiClient.batchEvents(batchId, {
      category: f.category,
      adjudication: f.adjudication,
      clusterId: f.clusterId || undefined,
      entityId: f.entityId || undefined,
      episodeId: f.episodeId || undefined,
      startTimeUs: f.startTimeUs || undefined,
      endTimeUs: f.endTimeUs || undefined,
      cursor: cursor ?? undefined,
      limit: 25,
    });
    const data = payload as unknown as BatchEventsData;
    state.batchEvents.batchId = data.batch_id;
    state.batchEvents.data = data;
    state.batchEvents.items = cursor ? [...state.batchEvents.items, ...data.items] : [...data.items];
    state.batchEvents.nextCursor = data.next_cursor;
    state.domainSelection.batchId = data.batch_id;
    state.batchEvents.status = "READY";
  } catch (error) {
    state.batchEvents.status = error instanceof GatewayError
      && (error.code === "TIMEOUT" || error.code === "BACKEND_UNAVAILABLE") ? "DEGRADED" : "ERROR";
    state.batchEvents.errorCode = error instanceof GatewayError ? error.code : "G7_BATCH_EVENTS_FAILED";
  }
  render();
}
function ensureBatchEvents(): void {
  const current = state.batchEvents.batchId;
  const wanted = _defaultBatchEventsBatch();
  if (!wanted) return;
  if (current !== wanted || state.batchEvents.status !== "READY") {
    void loadBatchEvents(wanted, null);
  }
}
async function ensureWeaponPage(viewId: ViewId): Promise<void> {
  ensureBatchEvents();
  const category = WEAPON_VIEW_CATEGORY[viewId] ?? "BVR";
  const wanted = state.batchEvents.items.find((item) => item.category === category)
    ?? null;
  const selected = state.batchEvents.items.find(
    (item) => item.weapon_event_id === state.domainSelection.weaponEventId,
  ) ?? wanted;
  if (selected) await loadWeaponFacts(selected.weapon_event_id);
}
async function loadWeaponFacts(weaponEventId: string): Promise<void> {
  const requestSerial = ++state.weaponWorkbench.requestSerial;
  state.domainSelection.weaponEventId = weaponEventId;
  state.weaponWorkbench.status = "LOADING";
  state.weaponWorkbench.errorCode = null;
  render();
  try {
    const detail = await guiClient.weaponEvent(weaponEventId);
    if (requestSerial !== state.weaponWorkbench.requestSerial) return;
    state.weaponWorkbench.detail = detail as unknown as Readonly<Record<string, unknown>>;
    const window = await guiClient.weaponEventWindow(weaponEventId, state.weaponWorkbench.perspective);
    if (requestSerial !== state.weaponWorkbench.requestSerial) return;
    state.weaponWorkbench.window = window as unknown as Readonly<Record<string, unknown>>;
    state.weaponWorkbench.status = "READY";
  } catch (error) {
    if (requestSerial !== state.weaponWorkbench.requestSerial) return;
    state.weaponWorkbench.status = "ERROR";
    state.weaponWorkbench.errorCode = error instanceof GatewayError ? error.code : "G8_WEAPON_FACTS_FAILED";
  }
  render();
}
async function loadReplayContext(): Promise<void> {
  const weaponEventId = state.domainSelection.weaponEventId;
  const releaseId = state.domainSelection.releaseId;
  const contextId = state.domainSelection.contextId;
  if (!weaponEventId || !releaseId || !contextId) {
    state.replay.status = "ERROR";
    state.replay.errorCode = "REPLAY_EXACT_CONTEXT_REQUIRED";
    render();
    return;
  }
  state.replay.status = "LOADING";
  state.replay.errorCode = null;
  try {
    const payload = await guiClient.replayContext(weaponEventId, {
      releaseId,
      contextId,
      perspective: state.weaponWorkbench.perspective,
    });
    state.replay.data = payload as unknown as Readonly<Record<string, unknown>>;
    state.replay.status = "READY";
  } catch (error) {
    state.replay.status = "ERROR";
    state.replay.errorCode = error instanceof GatewayError ? error.code : "G9_REPLAY_FAILED";
  }
  render();
}
function renderReplayLegacy(): string {
  beginLayout("V03");
  const data = state.replay.data;
  if (!data || state.replay.status !== "READY") {
    return panel("精确回放上下文", "exact Weapon Event", statePanel(
      state.replay.status, "回放上下文尚未载入", esc(state.replay.errorCode ?? "G9_REPLAY_PENDING"), "G9_REPLAY_PENDING"));
  }
  const facts = `<div class="v26Stats"><div><span>Weapon Event</span><b>${esc(String(data.weapon_event_id)).slice(0, 18)}</b></div>` +
    `<div><span>批次</span><b>${esc(String(data.batch_id)).slice(0, 18)}</b></div>` +
    `<div><span>窗口状态</span><b>${esc(String(data.window_state))}</b></div></div>` +
    `<div class="v26CatChips"><span class="v26Chip">t1 <b>${esc(String(data.t1_session_time_us))}</b></span>` +
    `<span class="v26Chip">t2 <b>${esc(String(data.t2_session_time_us ?? "—"))}</b></span>` +
    `<span class="v26Chip">t3 <b>${esc(String(data.t3_session_time_us ?? "—"))}</b></span></div>`;
  const ranges = data.ranges as Readonly<Record<string, unknown>> | undefined;
  const media = ranges && Array.isArray(ranges.media_ranges) && ranges.media_ranges.length
    ? `<div class="v29Empty">媒体范围已准入。</div>`
    : statePanel("EMPTY", "媒体/曲线范围尚未准入", esc(String(ranges?.reason_code ?? "MEDIA_PIPELINE_NOT_ADMITTED")) + "；时间漂移与缺失显式暴露，不以演示数据填充。", "G9_MEDIA_EMPTY");
  return panel("回放上下文", "精确 WE；往返保持 exact 上下文（V26/专项页 ↔ V03）", facts) +
    panel("媒体与曲线范围", "媒体管道准入前诚实空集", media) +
    panel("主时间游标", "Master Cursor 联动", statePanel("N_A", "游标联动待媒体准入", "媒体范围准入后启用主时间游标与事件/曲线同步。", "G9_CURSOR_PENDING")) +
    panel("回放视图", "二维/三维回放", statePanel("N_A", "回放视图待媒体准入", "二维/三维、HUD/媒体/转写同步在媒体管道准入后接入。", "G9_VIEW_PENDING"));
}
interface ReplayTrajectorySample {
  readonly session_time_us: string;
  readonly latitude_deg: number;
  readonly longitude_deg: number;
  readonly altitude_m: number | null;
  readonly evidence_ref: string | null;
}
function replayTrajectory(ranges: Readonly<Record<string, unknown>> | undefined): string {
  const trajectory = ranges?.trajectory as Readonly<Record<string, unknown>> | undefined;
  const raw = trajectory?.samples;
  if (trajectory?.state !== "READY" || !Array.isArray(raw) || !raw.length) {
    return statePanel(
      String(trajectory?.state ?? "N_A") as UiState,
      "当前事件窗口没有可呈现轨迹",
      esc(String(trajectory?.reason_code ?? "REPLAY_TRAJECTORY_NOT_AVAILABLE")),
      "G9_TRAJECTORY_EMPTY",
    );
  }
  const samples = raw as ReplayTrajectorySample[];
  const lons = samples.map((item) => Number(item.longitude_deg));
  const lats = samples.map((item) => Number(item.latitude_deg));
  const minLon = Math.min(...lons); const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats); const maxLat = Math.max(...lats);
  const lonSpan = Math.max(maxLon - minLon, 0.000001);
  const latSpan = Math.max(maxLat - minLat, 0.000001);
  const points = samples.map((item) => {
    const x = 24 + ((item.longitude_deg - minLon) / lonSpan) * 552;
    const y = 236 - ((item.latitude_deg - minLat) / latSpan) * 204;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
  const markers = samples.map((item, index) => {
    const [x, y] = points.split(" ")[index].split(",");
    return `<circle cx="${x}" cy="${y}" r="3.5"><title>${esc(item.session_time_us)} μs</title></circle>`;
  }).join("");
  return `<div class="replayViews" data-trajectory-samples="${samples.length}">` +
    `<section><header><b>二维航迹</b><span>经纬度 / Session Time</span></header>` +
    `<svg class="replayMap" viewBox="0 0 600 260" role="img" aria-label="精确事件窗口二维航迹">` +
    `<polyline points="${points}"/>${markers}</svg></section>` +
    `<section><header><b>三维轨迹投影视图</b><span>高度来自同一 Release</span></header>` +
    `<div class="replay3d"><svg viewBox="0 0 600 260" role="img" aria-label="精确事件窗口三维轨迹投影">` +
    `<polyline points="${points}"/>${markers}</svg></div></section></div>`;
}
function renderReplay(): string {
  beginLayout("V03");
  const data = state.replay.data;
  if (!data || state.replay.status !== "READY") {
    return panel("精确回放上下文", "精确 Weapon Event", statePanel(
      state.replay.status,
      "回放上下文尚未载入",
      esc(state.replay.errorCode ?? "G9_REPLAY_PENDING"),
      "G9_REPLAY_PENDING",
    ));
  }
  const facts = `<div class="v26Stats"><div><span>Weapon Event</span><b>${esc(String(data.weapon_event_id)).slice(0, 18)}</b></div>` +
    `<div><span>批次</span><b>${esc(String(data.batch_id)).slice(0, 18)}</b></div>` +
    `<div><span>窗口状态</span><b>${esc(String(data.window_state))}</b></div></div>` +
    `<div class="v26CatChips"><span class="v26Chip">t1 <b>${esc(String(data.t1_session_time_us))}</b></span>` +
    `<span class="v26Chip">t2 <b>${esc(String(data.t2_session_time_us ?? "—"))}</b></span>` +
    `<span class="v26Chip">t3 <b>${esc(String(data.t3_session_time_us ?? "—"))}</b></span></div>`;
  const ranges = data.ranges as Readonly<Record<string, unknown>> | undefined;
  const mediaItems = Array.isArray(ranges?.media_ranges) ? ranges.media_ranges : [];
  const media = mediaItems.length
    ? `<div class="replayMediaList">${mediaItems.map((raw) => {
      const item = raw as Readonly<Record<string, unknown>>;
      return `<div><b>${esc(String(item.media_id))}</b><span>${esc(String(item.media_type))}</span>` +
        `<em>需短期授权票据</em></div>`;
    }).join("")}</div>`
    : statePanel(
      "EMPTY",
      "当前事件窗口没有可用媒体",
      `${esc(String(ranges?.reason_code ?? "MEDIA_PIPELINE_NOT_ADMITTED"))}；不以演示数据填充。`,
      "G9_MEDIA_EMPTY",
    );
  const trajectory = replayTrajectory(ranges);
  return panel("回放上下文", "Release / Context / Weapon Event / Perspective 精确绑定", facts) +
    panel("媒体清单", "只显示同一 Release 的受控媒体引用", media) +
    panel("主时间游标", "Session Time 联动", trajectory.includes("replayViews")
      ? `<div class="replayCursor"><input type="range" min="0" max="100" value="0" aria-label="主时间游标"/>` +
        `<button type="button" disabled title="媒体票据就绪后启用播放">播放</button><span>1×</span></div>`
      : statePanel("N_A", "游标等待真实轨迹", "没有可联动数据时不启用伪播放。", "G9_CURSOR_PENDING")) +
    panel("二维 / 三维回放", "仅使用后端返回的精确轨迹样本", trajectory);
}
async function loadCoAttack(): Promise<void> {
  const grant = state.v24Grant;
  if (!grant) return;
  state.coAttack.status = "LOADING";
  state.coAttack.errorCode = null;
  try {
    const payload = await guiClient.coAttackAnalysis(grant.attackClusterId, {
      contextId: grant.contextId || undefined,
    });
    state.coAttack.data = payload as unknown as CoAttackPayload;
    state.coAttack.status = "READY";
  } catch (error) {
    state.coAttack.status = "ERROR";
    state.coAttack.errorCode = error instanceof GatewayError ? error.code : "G8_CO_ATTACK_FAILED";
  }
  render();
}
async function loadAuthorization(): Promise<void> {
  try {
    const payload = await guiClient.bootstrap();
    const principal = payload.principal;
    const provenance = payload.provenance;
    const runtimeBaseline = String(provenance.core_baseline ?? "");
    if (!Array.isArray(principal.gui_permissions) || !Array.isArray(principal.roles) ||
      provenance.authority_id !== "GUI_ASYNC_GATEWAY_AUTHORITY" ||
      provenance.authority_version !== "1.0.0" ||
      !/^CB-\d+\.\d+\.\d+$/.test(runtimeBaseline) ||
      payload.catalog.schema !== "TPAA_GUI_CATALOG_V1" ||
      payload.catalog.catalog_version !== `${runtimeBaseline}:1.0.0`) {
      state.authorization.status = "ERROR";
      render();
      return;
    }
    asyncGateway.setPartition(payload.cache_partition_key, state.domainSelection.releaseId);
    state.authorization.permissions = new Set(
      principal.gui_permissions.filter((item): item is string => typeof item === "string"));
    state.authorization.roles = principal.roles.filter((item): item is string => typeof item === "string");
    state.authorization.status = "READY";
    void loadOverview();
  } catch (error) {
    if (error instanceof GatewayError && (error.status === 401 || error.status === 403 || error.code === "FORBIDDEN")) {
      state.authorization.status = "FORBIDDEN";
      state.authorization.permissions.clear();
      state.authorization.roles = [];
    } else if (error instanceof GatewayError && (error.code === "TIMEOUT" || error.code === "BACKEND_UNAVAILABLE")) {
      state.authorization.status = "DEGRADED";
    } else {
      state.authorization.status = "ERROR";
    }
  }
  render();
}
window.addEventListener("keydown", (event: KeyboardEvent) => {
  if (!event.altKey || event.ctrlKey || event.metaKey) return;
  const key = event.key.toLowerCase();
  const shortcuts: Record<string, ModuleId> = { "1": "overview", "2": "training", "3": "replay", "4": "equipment", "5": "support" };
  if (shortcuts[key]) { event.preventDefault(); navigateToModule(shortcuts[key]); }
  else if (key === "arrowleft") { event.preventDefault(); goBack(); }
  else if (key === "r") { event.preventDefault(); toggleRibbon(); }
});
window.addEventListener("resize", () => fitCanvas(root));
render();
void loadAuthorization();
