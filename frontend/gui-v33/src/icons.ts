// TPAA v33 GUI — Ribbon 按钮图标库（视觉目标对齐 v33 Demo RB_SPEC/ribbonIcon）。
// 仅移植 SVG 视觉；图标不含业务语义。

export type RibbonIconKind =
  | "chart" | "doc" | "play" | "radar" | "target" | "strike" | "flight"
  | "formation" | "trend" | "gauge" | "curve" | "warn" | "layers" | "data"
  | "gear" | "palette";

const BASE = (color: string) =>
  `stroke="${color}" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"`;

const PATHS: Record<RibbonIconKind, string> = {
  chart: `<path d="M5 26V16h5v10M14 26V10h5v16M23 26V5h5v21"/><path d="M3 27.5h27"/>`,
  doc: `<path d="M8 4h11l6 6v18H8z"/><path d="M19 4v7h6M12 16h9M12 21h9"/>`,
  play: `<rect x="4" y="7" width="24" height="18" rx="3"/><path d="m13 11 8 5-8 5z"/>`,
  radar: `<circle cx="16" cy="18" r="3"/><path d="M8 18a8 8 0 0 1 8-8M5 18A11 11 0 0 1 16 7M16 18l8-8M16 18h11"/>`,
  target: `<circle cx="16" cy="16" r="10"/><circle cx="16" cy="16" r="4"/><path d="M16 3v5M16 24v5M3 16h5M24 16h5"/>`,
  strike: `<path d="M5 23 24 8l3 3L10 27z"/><path d="m17 14-7-3-2 2 6 4M20 18l3 7-2 2-4-6"/><circle cx="7" cy="25" r="2"/>`,
  flight: `<path d="M4 17 28 9l-9 10-2 9-3-7-10-4z"/><path d="M14 21 28 9"/>`,
  formation: `<path d="m16 5 4 6-4-2-4 2zM7 16l4 6-4-2-4 2zM25 16l4 6-4-2-4 2z"/><path d="M16 10v5M9 17l5-3M23 17l-5-3"/>`,
  trend: `<path d="M4 25h24M6 22l6-6 5 3 9-10"/><path d="M21 9h5v5"/>`,
  gauge: `<path d="M6 24a11 11 0 1 1 20 0"/><path d="M16 18l7-6"/><circle cx="16" cy="18" r="2"/>`,
  curve: `<path d="M4 26h24M6 25c4-13 7-18 12-18 5 0 6 7 8 13"/><path d="M5 9h5M22 8h5"/>`,
  warn: `<path d="M16 4 29 27H3z"/><path d="M16 11v8M16 23h.1"/>`,
  layers: `<path d="m16 5 12 6-12 6L4 11zM4 16l12 6 12-6M4 21l12 6 12-6"/>`,
  data: `<ellipse cx="16" cy="7" rx="10" ry="4"/><path d="M6 7v8c0 2 4 4 10 4s10-2 10-4V7M6 15v8c0 2 4 4 10 4s10-2 10-4v-8"/><path d="m12 22 3 3 6-6"/>`,
  gear: `<circle cx="16" cy="16" r="5"/><path d="M16 4v4M16 24v4M4 16h4M24 16h4M7.5 7.5l3 3M21.5 21.5l3 3M24.5 7.5l-3 3M10.5 21.5l-3 3"/>`,
  palette: `<path d="M16 3C8.8 3 3 8.4 3 15.2S8.8 29 16 29c2.5 0 3.3-2.6 2-4.1-1-1.2-1.1-3 1.2-3.3h3.1c4.1 0 6.7-3 6.7-7.3C29 7.9 23.3 3 16 3z"/><circle cx="9.5" cy="13" r="1.6"/><circle cx="15" cy="8.5" r="1.6"/><circle cx="22" cy="11.5" r="1.6"/><circle cx="9.7" cy="20" r="1.6"/>`,
};

export function ribbonIcon(kind: RibbonIconKind, color: string): string {
  const resolved = PATHS[kind] ?? PATHS.chart;
  return `<svg viewBox="0 0 32 32" aria-hidden="true"><g ${BASE(color)}>${resolved}</g></svg>`;
}

/** 每视图按钮图标与颜色规格（对齐 Demo RB_SPEC；V23/V25/V26 为 v33 增补）。 */
export const RIBBON_SPEC: Readonly<Record<string, readonly [RibbonIconKind, string]>> = {
  V01: ["chart", "#56b4e9"], V02: ["doc", "#7ec8f1"], V03: ["play", "#56b4e9"],
  V04: ["radar", "#f0b24a"], V05: ["target", "#e0701a"], V06: ["strike", "#e69f00"],
  V07: ["flight", "#56b4e9"], V08: ["radar", "#e6b84a"], V09: ["trend", "#1fbf94"],
  V10: ["gauge", "#56b4e9"], V11: ["curve", "#8ecae6"], V12: ["radar", "#6ec6e8"],
  V13: ["warn", "#e69f00"], V14: ["target", "#e0701a"], V15: ["layers", "#cc79a7"],
  V16: ["trend", "#1fbf94"], V17: ["data", "#6cc5a8"], V18: ["doc", "#a7c7df"],
  V19: ["flight", "#56b4e9"], V20: ["target", "#e0701a"], V21: ["strike", "#cc79a7"],
  V22: ["gear", "#9fb8cd"], V23: ["data", "#6cc5a8"], V25: ["palette", "#8aa9d7"],
  V26: ["target", "#e0701a"],
};

export function ribbonSpecFor(viewId: string): readonly [RibbonIconKind, string] {
  return RIBBON_SPEC[viewId] ?? ["chart", "#56b4e9"];
}
