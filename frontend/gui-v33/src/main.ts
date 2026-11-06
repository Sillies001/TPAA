import "./style.css";
import registryJson from "../../../docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json";
import contractJson from "../../../baseline/CB-1.6.0/canonical/GUI_VIEW_CONTRACT.json";
import permissionJson from "../../../baseline/CB-1.6.0/canonical/GUI_PERMISSION_AUDIT_AUTHORITY.json";

type Theme = "tactical" | "graphite" | "light";
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

const registry = registryJson as unknown as Registry;
const contracts = contractJson as unknown as ContractDocument;
const permissions = permissionJson as unknown as PermissionDocument;
const modules = new Map(registry.modules.map((item) => [item.id, item]));
const views = new Map(registry.views.map((item) => [item.id, item]));
const viewContracts = new Map(contracts.views.map((item) => [item.view_id, item]));
const permissionPolicies = new Map(permissions.permissions.map((item) => [item.permission_id, item]));
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
    hasText(grant.releaseId) && hasText(grant.contextId) && hasText(grant.weaponEventId) &&
    hasText(grant.attackClusterId) && hasText(grant.formationId);
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
  document.documentElement.dataset.tpaaTheme = theme;
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
  const contract = viewContracts.get(view.id);
  if (!contract) return "ERROR";
  if (contract.required_context.some((field) => !hasText(contextValue(field)))) return "N_A";
  return "N_A";
}
function statusText(status: UiState): { label: string; title: string; message: string; code: string } {
  const copy: Record<UiState, { label: string; title: string; message: string; code: string }> = {
    LOADING: { label: "正在加载", title: "正在核验本地会话权限", message: "正在读取当前会话的角色与权限；核验完成前不开放业务视图。", code: "AUTHORIZATION_LOADING" },
    EMPTY: { label: "暂无数据", title: "当前精确查询范围没有可展示记录", message: "不会使用其他批次、默认样本或演示数据填充空结果。", code: "EXACT_QUERY_EMPTY" },
    READY: { label: "已就绪", title: "当前会话呈现设置可用", message: "主题只作用于当前桌面会话，不写入业务上下文或浏览器持久存储。", code: "PRESENTATION_ONLY_SESSION_STATE" },
    DEGRADED: { label: "服务降级", title: "权限服务暂不可用", message: "页面保持关闭；请检查本地后端状态后重试。", code: "AUTHORIZATION_DEGRADED" },
    ERROR: { label: "系统错误", title: "权限响应不符合合同", message: "系统无法确认当前会话权限，因此拒绝加载业务视图。", code: "AUTHORIZATION_RESPONSE_INVALID" },
    FORBIDDEN: { label: "无权访问", title: "当前会话无权访问此视图", message: "权限缺失、权限未知或受控入口上下文不完整时，系统按默认拒绝处理。", code: "FORBIDDEN" },
    N_A: { label: "尚未接入", title: "当前视图尚未接入真实业务读模型", message: "G2 只建立产品 Shell、导航、共享状态和主题。真实批次、指标、事件与回放数据将在后续阶段通过 Application/API 合同接入。", code: "G2_SHELL_ONLY_NO_BUSINESS_DATA" },
  };
  return copy[status];
}
function renderThemes(): string {
  const items: Array<{ id: Theme; title: string; description: string }> = [
    { id: "tactical", title: "暗色战术", description: "高对比战术显示，适合暗环境复盘" },
    { id: "graphite", title: "石墨深色", description: "中性深色工作台，默认主题" },
    { id: "light", title: "浅色", description: "明亮环境下的清晰阅读主题" },
  ];
  return '<section class="theme-manager"><div class="section-heading"><div><p class="eyebrow">PRESENTATION STATE</p><h3>主题管理</h3></div><span class="state-pill state-ready">会话级设置</span></div>' +
    '<p class="muted">主题只改变当前窗口的呈现方式。关闭桌面会话后恢复默认 Graphite，不使用浏览器持久存储或业务数据库保存主题。</p><div class="theme-grid">' +
    items.map((item) => '<button type="button" class="theme-option' + (state.presentation.theme === item.id ? " is-selected" : "") +
      '" data-theme="' + item.id + '" aria-pressed="' + String(state.presentation.theme === item.id) + '">' +
      '<span class="theme-swatch theme-swatch-' + item.id + '" aria-hidden="true"></span><span class="theme-option-copy"><strong>' +
      esc(item.title) + '</strong><small>' + esc(item.description) + '</small></span><span class="theme-check" aria-hidden="true">' +
      (state.presentation.theme === item.id ? "✓" : "") + "</span></button>").join("") + "</div></section>";
}
function renderV08Entry(): string {
  return '<section class="controlled-entry"><div class="section-heading"><div><p class="eyebrow">CONDITIONAL ENTRY</p><h3>协同攻击分析入口</h3></div><span class="state-pill state-na">等待真实事件授权</span></div>' +
    '<p class="muted">V24 不是独立菜单项。只有当前 V08 中存在经后端识别的 BVR 同目标协同攻击事件，并绑定精确 Release、Context、Weapon Event、Attack Cluster 与编队信息后，才允许进入。</p>' +
    '<button type="button" class="primary-button" data-action="enter-v24" disabled aria-disabled="true">进入 V24 协同攻击分析</button>' +
    '<p class="hint">G2 尚未接入真实 Weapon Event 查询，因此此入口保持禁用；不会创建演示事件或伪造授权。</p></section>';
}
function renderContextBar(): string {
  const items: Array<[string, string]> = [
    ["批次", state.domainSelection.batchId ?? "未选择"],
    ["架次", state.domainSelection.sortieId ?? state.domainSelection.sessionId ?? "未选择"],
    ["Release", state.domainSelection.releaseId ?? "未选择"], ["Context", state.domainSelection.contextId ?? "未选择"],
    ["Weapon Event", state.domainSelection.weaponEventId ?? "未选择"],
    ["编队", state.domainSelection.formationId ?? "未选择"], ["成员", state.domainSelection.memberId ?? "未选择"],
    ["视角", state.domainSelection.perspective], ["评估方", state.domainSelection.evaluatedSide ?? "未选择"],
  ];
  return '<section class="context-bar" aria-label="共享业务上下文">' + items.map(([label, value]) =>
    '<div class="context-item"><span>' + esc(label) + '</span><strong title="' + esc(value) + '">' + esc(value) + "</strong></div>",
  ).join("") + "</section>";
}
function renderSubnav(): string {
  const list = registry.views.filter((view) => view.module === state.navigation.activeModuleId && view.id !== "V24");
  return '<nav class="subnav' + (state.presentation.ribbonCollapsed ? " is-hidden" : "") + '" aria-label="当前模块视图">' +
    '<div class="subnav-heading"><span>视图导航</span><small>' + list.length + " 个入口</small></div><div class=\"subnav-items\">" +
    list.map((view) => {
      const active = view.id === state.navigation.currentViewId;
      const enabled = canNavigate(view.id);
      return '<button type="button" class="subnav-item' + (active ? " is-active" : "") + '" data-view="' + esc(view.id) +
        '" aria-current="' + (active ? "page" : "false") + '"' + (enabled ? "" : " disabled") +
        ' title="' + esc(enabled ? view.title : "权限尚未确认或缺少必需权限") + '"><span class="view-id">' +
        esc(view.id) + "</span><span>" + esc(view.title) + "</span></button>";
    }).join("") + "</div></nav>";
}
function renderModuleTabs(): string {
  return registry.modules.map((module, index) => {
    const active = module.id === state.navigation.activeModuleId;
    const enabled = canNavigate(module.landing);
    return '<button type="button" class="module-tab' + (active ? " is-active" : "") + '" data-module="' + esc(module.id) +
      '" aria-current="' + (active ? "page" : "false") + '"' + (enabled ? "" : " disabled") +
      ' title="' + esc(enabled ? module.label : "模块入口需要有效会话权限") + '"><span class="module-tab-index">' +
      String(index + 1).padStart(2, "0") + "</span><span>" + esc(module.label) + "</span></button>";
  }).join("");
}
function renderPageBody(view: View, status: UiState): string {
  if (view.id === "V25") return renderThemes();
  const content = statusText(status);
  const contract = viewContracts.get(view.id);
  const capabilities = contract?.p_capabilities.length ? contract.p_capabilities.join(" · ") : "尚未配置";
  const missing = contract?.required_context.filter((field) => !hasText(contextValue(field))) ?? [];
  const contextMessage = missing.length ? "缺少精确上下文：" + missing.join("、") : "当前阶段尚未接入业务读模型。";
  return '<section class="state-panel state-' + status.toLowerCase() + '" role="status" aria-live="polite">' +
    '<div class="state-symbol" aria-hidden="true">' + (status === "FORBIDDEN" ? "×" : status === "LOADING" ? "…" : status === "READY" ? "✓" : "—") + "</div>" +
    '<div class="state-copy"><div class="state-meta"><span class="state-pill state-' + status.toLowerCase() + '">' + content.label +
    '</span><span class="state-code">' + content.code + "</span></div><h3>" +
    esc(state.notice?.viewId === view.id ? state.notice.title : content.title) + "</h3><p>" +
    esc(state.notice?.viewId === view.id ? state.notice.message : content.message) + '</p><p class="state-context">' +
    esc(contextMessage) + "</p></div></section>" +
    '<section class="view-contract-card"><div><span class="eyebrow">VIEW CONTRACT</span><strong>' + esc(view.id + " · " + view.title) +
    '</strong></div><div><span class="eyebrow">P CAPABILITIES</span><strong>' + esc(capabilities) +
    '</strong></div><div><span class="eyebrow">数据真实性</span><strong>仅接受 Application 授权投影</strong></div></section>' +
    (view.id === "V08" ? renderV08Entry() : "");
}
function render(): void {
  let focusTarget: { key: "action" | "view" | "module" | "theme" | "main" | "skip"; value: string } | null = null;
  const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  if (active && root.contains(active)) {
    if (active.id === "main-content") {
      focusTarget = { key: "main", value: "" };
    } else if (active.classList.contains("skip-link")) {
      focusTarget = { key: "skip", value: "" };
    } else {
      for (const key of ["action", "view", "module", "theme"] as const) {
        const value = active.dataset[key];
        if (value) {
          focusTarget = { key, value };
          break;
        }
      }
    }
  }
  const view = currentView();
  const module = modules.get(view.module);
  if (!module) throw new Error("TPAA_VIEW_MODULE_MISSING");
  const status = viewState(view);
  document.documentElement.dataset.tpaaTheme = state.presentation.theme;
  root!.innerHTML = [
    '<a class="skip-link" href="#main-content">跳转到主要内容</a><div class="shell">',
    '<header class="titlebar"><div class="titlebar-brand"><span class="brand-mark">TP</span><span>TPAA</span></div>',
    '<h1>空中作战训练辅助评估系统</h1><div class="titlebar-actions"><span class="session-indicator"><i aria-hidden="true"></i>' +
      (state.authorization.status === "READY" ? "会话已核验" : "会话未核验") + '</span><button type="button" class="theme-shortcut" data-view="V25" aria-label="打开主题管理">主题</button></div></header>',
    '<section class="ribbon' + (state.presentation.ribbonCollapsed ? " is-collapsed" : "") + '" aria-label="产品模块导航">',
    '<nav class="module-tabs" aria-label="五大功能模块">' + renderModuleTabs() + '</nav><div class="ribbon-subrow"><div class="ribbon-caption"><span>TPAA WORKSPACE</span><span>V33 · ' +
      esc(module.label) + '</span></div><button type="button" class="ribbon-toggle" data-action="toggle-ribbon" aria-expanded="' +
      String(!state.presentation.ribbonCollapsed) + '">' + (state.presentation.ribbonCollapsed ? "展开视图导航" : "收起视图导航") + "</button></div></section>",
    renderContextBar(), '<div class="workspace' + (state.presentation.ribbonCollapsed ? " is-expanded" : "") + '">',
    renderSubnav(), '<main id="main-content" class="main-content" tabindex="-1"><div class="page-heading"><div><p class="eyebrow">' +
      esc(module.label + " / " + view.id) + "</p><h2>" + esc(view.title) +
      '</h2><p class="page-description">产品视图由 v33 视图注册表驱动；业务语义、权限与数据真实性以机器权威和后端合同为准。</p></div>',
    '<div class="page-actions"><button type="button" class="secondary-button" data-action="back"' +
      (state.navigation.returnStack.length ? "" : " disabled") + '>返回</button><button type="button" class="secondary-button" data-action="home">总览</button></div></div>',
    renderPageBody(view, status), '</main></div><footer class="statusbar"><span>GUI-DEMO-V33-2026-11-05 · CB-1.6.0 候选</span>',
    '<span>权限：' + esc(state.authorization.status) + " · 业务数据：未接入（G3 起）</span><span>主题：" +
      esc(state.presentation.theme) + "</span></footer></div>",
  ].join("");
  const target = focusTarget;
  if (target?.key === "main") {
    root.querySelector<HTMLElement>("#main-content")?.focus();
  } else if (target?.key === "skip") {
    root.querySelector<HTMLAnchorElement>(".skip-link")?.focus();
  } else if (target) {
    const restored = Array.from(root.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.dataset[target.key] === target.value,
    );
    if (restored && !restored.disabled) restored.focus();
    else root.querySelector<HTMLElement>("#main-content")?.focus();
  }
  root.querySelectorAll<HTMLButtonElement>("[data-module]").forEach((button) =>
    button.addEventListener("click", () => navigateToModule(button.dataset.module as ModuleId)),
  );
  root.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) =>
    button.addEventListener("click", () => navigateToView(button.dataset.view ?? "")),
  );
  root.querySelectorAll<HTMLButtonElement>("[data-theme]").forEach((button) =>
    button.addEventListener("click", () => {
      const value = button.dataset.theme;
      if (value === "tactical" || value === "graphite" || value === "light") setTheme(value);
    }),
  );
  root.querySelector<HTMLButtonElement>('[data-action="toggle-ribbon"]')?.addEventListener("click", toggleRibbon);
  root.querySelector<HTMLButtonElement>('[data-action="back"]')?.addEventListener("click", goBack);
  root.querySelector<HTMLButtonElement>('[data-action="home"]')?.addEventListener("click", () => navigateToView("V01"));
  root.querySelector<HTMLButtonElement>('[data-action="enter-v24"]')?.addEventListener("click", () => enterV24FromV08(null));
}
async function loadAuthorization(): Promise<void> {
  try {
    const response = await fetch("/security/session", {
      method: "GET", credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" },
    });
    if (response.status === 401 || response.status === 403) {
      state.authorization.status = "FORBIDDEN";
      state.authorization.permissions.clear();
      state.authorization.roles = [];
      render();
      return;
    }
    if (!response.ok) {
      state.authorization.status = "DEGRADED";
      render();
      return;
    }
    const payload: unknown = await response.json();
    if (typeof payload !== "object" || payload === null || !("schema" in payload) ||
      payload.schema !== "TPAA_SECURITY_SESSION_CONTEXT_V1" || !("permissions" in payload) ||
      !Array.isArray(payload.permissions) || !("roles" in payload) || !Array.isArray(payload.roles)) {
      state.authorization.status = "ERROR";
      render();
      return;
    }
    state.authorization.permissions = new Set(payload.permissions.filter((item): item is string => typeof item === "string"));
    state.authorization.roles = payload.roles.filter((item): item is string => typeof item === "string");
    state.authorization.status = "READY";
  } catch {
    state.authorization.status = "DEGRADED";
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
render();
void loadAuthorization();
