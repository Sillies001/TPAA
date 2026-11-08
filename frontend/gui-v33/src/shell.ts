// TPAA v33 GUI — 共享 Shell：五模块 Ribbon 分组、1600×900 画布缩放、面板版式。
// 视觉目标对齐 v33 Demo（apphead/mainmenu/submenu/subcard/subbtn、fit()、P 面板）。
import { ribbonIcon, ribbonSpecFor } from "./icons.ts";
import type { Theme } from "./themes.ts";

export const CANVAS_W = 1600;
export const CANVAS_H = 900;
export const RIBBON_DELTA = 88;

/** 五模块 → 分组 → 视图（最终生效 v33 结构，V24 为条件下钻不入 Ribbon）。 */
export interface RibbonGroup { readonly id: string; readonly label: string; readonly items: readonly string[] }
export interface RibbonModule { readonly id: string; readonly label: string; readonly landing: string; readonly groups: readonly RibbonGroup[] }

export const RIBBON_MODULES: readonly RibbonModule[] = [
  { id: "overview", label: "总览", landing: "V01", groups: [
    { id: "overview_main", label: "总览入口", items: ["V01"] },
  ] },
  { id: "training", label: "训练评估", landing: "V26", groups: [
    { id: "batch_entry", label: "批次入口", items: ["V26"] },
    { id: "wvr_review", label: "视距内行为", items: ["V05", "V20"] },
    { id: "bvr_review", label: "超视距行为", items: ["V04", "V08"] },
    { id: "strike_review", label: "对地攻击", items: ["V06", "V21"] },
    { id: "basic_review", label: "基本飞行（独立）", items: ["V07", "V19"] },
    { id: "multi_review", label: "长期成长与综合复盘", items: ["V09", "V02"] },
  ] },
  { id: "replay", label: "回放", landing: "V03", groups: [
    { id: "replay_main", label: "战术回放工作台", items: ["V03"] },
  ] },
  { id: "equipment", label: "装备性能", landing: "V10", groups: [
    { id: "equip_overview", label: "装备总体", items: ["V10"] },
    { id: "equip_metric", label: "分项性能", items: ["V11", "V12", "V13", "V14"] },
    { id: "equip_analysis", label: "综合分析", items: ["V15", "V16"] },
  ] },
  { id: "support", label: "数据与系统", landing: "V23", groups: [
    { id: "support_data", label: "数据管理与可信度", items: ["V23", "V17"] },
    { id: "support_output", label: "输出与系统", items: ["V18", "V22"] },
    { id: "support_preferences", label: "界面设置", items: ["V25"] },
  ] },
];

export const VIEW_TO_MODULE: Readonly<Record<string, string>> = (() => {
  const map: Record<string, string> = {};
  for (const module of RIBBON_MODULES) {
    for (const group of module.groups) for (const view of group.items) map[view] = module.id;
  }
  map["V24"] = "training";
  return map;
})();

export function ribbonModuleFor(viewId: string): RibbonModule {
  const id = VIEW_TO_MODULE[viewId] ?? "overview";
  return RIBBON_MODULES.find((m) => m.id === id) ?? RIBBON_MODULES[0];
}

export function renderMainMenu(activeModuleId: string): string {
  return RIBBON_MODULES.map((module) =>
    `<button type="button" class="mtab${module.id === activeModuleId ? " on" : ""}" data-module="${module.id}">${module.label}</button>`,
  ).join("");
}

export function renderSubmenu(activeModuleId: string, currentViewId: string, canNavigate: (id: string) => boolean): string {
  const module = RIBBON_MODULES.find((m) => m.id === activeModuleId) ?? RIBBON_MODULES[0];
  return module.groups.map((group) => {
    const buttons = group.items.map((viewId) => {
      const [kind, color] = ribbonSpecFor(viewId);
      const on = viewId === currentViewId;
      const enabled = canNavigate(viewId);
      return `<button type="button" class="subbtn${on ? " on" : ""}" data-view="${viewId}"${enabled ? "" : " disabled"} title="${viewId}">` +
        `<span class="rbicon">${ribbonIcon(kind, color)}</span><span class="rblabel">${viewId}</span></button>`;
    }).join("");
    return `<div class="subcard"><div class="subbody">${buttons}</div><div class="subhead"><span>${group.label}</span></div></div>`;
  }).join("");
}

/** 画布等比缩放适配窗口（对齐 Demo fit()）。 */
export function fitCanvas(root: HTMLElement): void {
  const k = Math.min(window.innerWidth / CANVAS_W, window.innerHeight / CANVAS_H);
  root.style.transform =
    `translate(${(window.innerWidth - CANVAS_W * k) / 2}px,${(window.innerHeight - CANVAS_H * k) / 2}px) scale(${k})`;
}

/** 面板矩形（单位：10px），对齐 Demo LY；未定义视图回退到通用三行网格。 */
const FALLBACK_LAYOUT: readonly (readonly [number, number, number, number])[] = [
  [3, 19.5, 100, 30], [105, 19.5, 52, 30], [3, 51, 75, 35], [80, 51, 77, 35],
];

const VIEW_LAYOUT: Readonly<Record<string, readonly (readonly [number, number, number, number])[]>> = {
  V23: [[3, 19.5, 154, 10], [3, 30.5, 70, 28], [75, 30.5, 82, 28], [3, 60, 55, 26], [60, 60, 48, 26], [110, 60, 47, 26]],
  V25: [[3, 20.6, 154, 10], [3, 32, 49, 44], [54, 32, 49, 44], [105, 32, 52, 44], [3, 77.5, 154, 8.5]],
  V26: [[3, 19.5, 154, 9], [3, 29.5, 154, 17.5], [3, 48, 154, 15.5], [3, 64.5, 154, 21.5]],
  V01: [[3, 19.5, 154, 12], [3, 33, 75, 30], [80, 33, 77, 30], [3, 65, 100, 21], [105, 65, 52, 21]],
};

export interface PanelRect { readonly left: number; readonly top: number; readonly width: number; readonly height: number }

export function layoutFor(viewId: string): readonly (readonly [number, number, number, number])[] {
  return VIEW_LAYOUT[viewId] ?? FALLBACK_LAYOUT;
}

let panelIndex = 0;
let currentLayout: readonly (readonly [number, number, number, number])[] = FALLBACK_LAYOUT;

export function beginLayout(viewId: string): void {
  panelIndex = 0;
  currentLayout = layoutFor(viewId);
}

// CSP（style-src 'self'）禁止内联 style 属性：面板几何以 data-geo 传递，
// 由 main.ts 在 innerHTML 之后用 CSSOM（element.style）统一应用（安全门不放宽）。
export function panel(title: string, subtitle: string, body: string): string {
  const rect = currentLayout[panelIndex];
  panelIndex += 1;
  if (!rect) return "";
  const [l, t, w, h] = rect;
  return `<div class="p" data-geo="${l * 10},${t * 10},${w * 10},${h * 10}">` +
    `<h3>${title}</h3><small>${subtitle}</small><div class="pb">${body}</div></div>`;
}

/** 渲染后将 data-geo 应用到 .p 面板（绕开内联 style 属性 CSP 限制）。 */
export function applyPanelGeometry(scope: ParentNode): void {
  scope.querySelectorAll<HTMLElement>(".p[data-geo]").forEach((element) => {
    const geo = (element.dataset.geo ?? "").split(",").map(Number);
    if (geo.length !== 4 || geo.some((value) => !Number.isFinite(value))) return;
    const [left, top, width, height] = geo;
    element.style.position = "absolute";
    element.style.left = `${left}px`;
    element.style.top = `${top}px`;
    element.style.width = `${width}px`;
    element.style.height = `${height}px`;
  });
}

/** 受控状态面板（LOADING/EMPTY/DEGRADED/ERROR/FORBIDDEN/N_A）。 */
export function statePanel(
  status: "LOADING" | "EMPTY" | "DEGRADED" | "ERROR" | "FORBIDDEN" | "N_A" | "READY",
  title: string, message: string, code: string,
): string {
  const symbol = status === "FORBIDDEN" || status === "ERROR" ? "×" : status === "LOADING" ? "…" : status === "READY" ? "✓" : "—";
  return `<div class="state-panel state-${status.toLowerCase()}" role="status">` +
    `<div class="state-symbol" aria-hidden="true">${symbol}</div><div class="state-copy">` +
    `<div class="state-meta"><span class="state-pill state-${status.toLowerCase()}">${status}</span>` +
    `<span class="state-code">${code}</span></div><h3>${title}</h3><p>${message}</p></div></div>`;
}
