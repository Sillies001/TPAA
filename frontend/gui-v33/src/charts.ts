// TPAA v33 GUI — 图表原语（SVG，主题感知，纯数据驱动）。
// 仅渲染调用方提供的真实投影数据；缺数据由调用方以受控状态呈现，本模块不伪造曲线。
import type { ChartPalette } from "./themes.ts";

export interface Series { readonly x: readonly number[]; readonly y: readonly number[]; readonly color: string; readonly dashed?: boolean; readonly width?: number }
export interface AxisSpec { readonly x: readonly [number, number]; readonly y: readonly [number, number]; readonly xLabel?: string }

const scale = (a: number, b: number, c: number, d: number) => (v: number) => c + (v - a) / (b - a || 1) * (d - c);
const num = (v: number) => +v.toFixed(2);

export function lineChart(
  palette: ChartPalette, size: { W: number; H: number }, axis: AxisSpec, series: readonly Series[],
  options: { readonly horizontal?: readonly (readonly [number, string])[] } = {},
): string {
  const { W, H } = size;
  const m = [34, 8, 8, 24];
  const sx = scale(axis.x[0], axis.x[1], m[0], W - m[1]);
  const sy = scale(axis.y[0], axis.y[1], H - m[3], m[2]);
  let s = "";
  for (let i = 0; i <= 4; i += 1) {
    const yv = axis.y[0] + (axis.y[1] - axis.y[0]) * i / 4;
    const xv = axis.x[0] + (axis.x[1] - axis.x[0]) * i / 4;
    s += `<line x1=${m[0]} x2=${W - m[1]} y1=${sy(yv)} y2=${sy(yv)} stroke="${palette.mu}" opacity=".35"/>` +
      `<text x=${m[0] - 4} y=${sy(yv) + 3} text-anchor="end">${num(yv)}</text>` +
      `<text x=${sx(xv)} y=${H - m[3] + 12} text-anchor="middle">${num(xv)}</text>`;
  }
  for (const [yv, color] of options.horizontal ?? []) {
    s += `<line x1=${m[0]} x2=${W - m[1]} y1=${sy(yv)} y2=${sy(yv)} stroke="${color}" stroke-dasharray="4 3"/>`;
  }
  for (const q of series) {
    const pts = q.x.map((xv, i) => `${sx(xv)},${sy(q.y[i])}`).join(" ");
    s += `<polyline points="${pts}" fill="none" stroke="${q.color}" stroke-width="${q.width ?? 1.8}"${q.dashed ? ' stroke-dasharray="4 3"' : ""}/>`;
  }
  if (axis.xLabel) s += `<text x=${W / 2} y=${H - 2} text-anchor="middle">${axis.xLabel}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}">${s}</svg>`;
}

export interface BarRow { readonly label: string; readonly value: number; readonly error?: number; readonly color?: string; readonly display?: string }

export function barChart(
  palette: ChartPalette, size: { W: number; H: number }, rows: readonly BarRow[], max: number,
): string {
  const { W, H } = size;
  const rh = Math.min(34, (H - 8) / (rows.length || 1));
  const sx = scale(0, max, 104, W - 30);
  let s = "";
  rows.forEach((row, i) => {
    const y = i * rh + 4;
    s += `<text x=98 y=${y + 9} text-anchor="end" class="t">${row.label}</text>` +
      `<rect x=${sx(0)} y=${y} width=${Math.max(2, sx(row.value) - sx(0))} height=15 rx=3 fill="${row.color ?? palette.me}"/>`;
    if (row.error) s += `<line x1=${sx(row.value - row.error)} x2=${sx(row.value + row.error)} y1=${y + 7.5} y2=${y + 7.5} stroke="${palette.tx}"/>`;
    s += `<text x=${sx(row.value) + (row.error ? sx(row.error) - sx(0) : 0) + 4} y=${y + 11}>${row.display ?? String(row.value)}</text>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}">${s}</svg>`;
}

export function radarChart(
  palette: ChartPalette, size: { W: number; H: number }, labels: readonly string[],
  series: ReadonlyArray<{ readonly values: readonly number[]; readonly color: string; readonly filled: boolean; readonly dashed?: boolean }>,
): string {
  const { W, H } = size;
  const n = labels.length;
  const cx = W / 2, cy = H / 2, r = Math.min(W / 2 - 48, H / 2 - 20);
  const pt = (i: number, v: number) =>
    `${cx + r * v / 100 * Math.sin(6.2832 * i / n)},${cy - r * v / 100 * Math.cos(6.2832 * i / n)}`;
  let s = [25, 50, 75, 100].map((v) =>
    `<polygon points="${labels.map((_, i) => pt(i, v)).join(" ")}" fill="none" stroke="${palette.mu}" opacity=".4"/>`).join("");
  labels.forEach((label, i) => {
    s += `<text x=${cx + (r + 16) * Math.sin(6.2832 * i / n)} y=${cy - (r + 10) * Math.cos(6.2832 * i / n) + 3} text-anchor="middle">${label}</text>`;
  });
  for (const q of series) {
    const points = q.values.map((v, i) => pt(i, v)).join(" ");
    s += `<polygon points="${points}" fill="${q.filled ? q.color : "none"}" fill-opacity=.2 stroke="${q.color}" stroke-width=1.6${q.dashed ? ' stroke-dasharray="4 3"' : ""}/>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}">${s}</svg>`;
}

export interface HeatmapSpec {
  readonly matrix: readonly (readonly number[])[];
  readonly rowLabels: readonly string[];
  readonly colLabels: readonly string[];
  readonly lo: number; readonly hi: number;
  readonly color: (t: number) => string;
  readonly format?: (v: number) => string;
  readonly onCell?: (row: number, col: number) => string | null;
}

export function heatmap(palette: ChartPalette, size: { W: number; H: number }, spec: HeatmapSpec): string {
  const { W, H } = size;
  const k = spec.colLabels.length;
  const cw = (W - 56) / k;
  const ch = Math.min(60, (H - 18) / (spec.matrix.length || 1));
  const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
  let s = "";
  spec.matrix.forEach((row, i) => row.forEach((v, j) => {
    const x = 54 + j * cw, y = i * ch;
    const t = clamp((v - spec.lo) / (spec.hi - spec.lo), 0, 1);
    const go = spec.onCell?.(i, j);
    s += `<rect${go ? ` class="c" data-go="${go}"` : ""} x=${x} y=${y} width=${cw - 2} height=${ch - 2} rx=3 fill="${spec.color(t)}"/>` +
      `<text x=${x + cw / 2} y=${y + ch / 2 + 3} text-anchor="middle" class="t" pointer-events="none">${spec.format ? spec.format(v) : Math.round(v)}</text>`;
  }));
  spec.rowLabels.forEach((label, i) => { s += `<text x=50 y=${i * ch + ch / 2 + 3} text-anchor="end">${label}</text>`; });
  spec.colLabels.forEach((label, j) => { s += `<text x=${54 + j * cw + cw / 2} y=${spec.matrix.length * ch + 12} text-anchor="middle">${label}</text>`; });
  return `<svg viewBox="0 0 ${W} ${H}">${s}</svg>`;
}
