// TPAA v33 GUI — 三主题定义与图表色板（视觉目标对齐 v33 Demo）。
// 每次打开默认 graphite；主题仅会话级生效，不写入业务状态或浏览器持久存储。
export type Theme = "tactical" | "graphite" | "light";

export const THEME_IDS: readonly Theme[] = ["tactical", "graphite", "light"];

export interface ChartPalette {
  readonly me: string; // 本机/主系列
  readonly op: string; // 对手/对比系列
  readonly al: string; // 通过/达标
  readonly wn: string; // 警告
  readonly hi: string; // 高亮
  readonly rd: string; // 危险/红线
  readonly mu: string; // 次要文字
  readonly pu: string; // 补充系列
  readonly tx: string; // 主文字
}

export const THEME_CL: Readonly<Record<Theme, ChartPalette>> = {
  tactical: {
    me: "#3a9ad9", op: "#e0701a", al: "#1fbf94", wn: "#e69f00",
    hi: "#56b4e9", rd: "#e0314b", mu: "#8da2b8", pu: "#cc79a7", tx: "#e8eef5",
  },
  graphite: {
    me: "#6c9ad4", op: "#d89460", al: "#56b89b", wn: "#d5ab5b",
    hi: "#8ab6e5", rd: "#de6977", mu: "#a2adba", pu: "#b19bde", tx: "#e8edf3",
  },
  light: {
    me: "#2567a8", op: "#c26b32", al: "#187b63", wn: "#a57323",
    hi: "#2468a7", rd: "#bd4050", mu: "#65788d", pu: "#7b5bb0", tx: "#213246",
  },
};

export interface ThemeDef {
  readonly label: string;
  readonly short: string;
  readonly desc: string;
  readonly base: string;
  readonly panel: string;
  readonly panel2: string;
  readonly border: string;
  readonly accent: string;
  readonly text: string;
  readonly muted: string;
  readonly green: string;
  readonly orange: string;
}

export const THEME_DEF: Readonly<Record<Theme, ThemeDef>> = {
  tactical: {
    label: "暗色战术主题", short: "Tactical Dark", base: "#0e1722", panel: "#152233",
    panel2: "#102337", border: "#314c62", accent: "#56b4e9", text: "#e8eef5",
    muted: "#91adc3", green: "#1fbf94", orange: "#e69f00",
    desc: "蓝黑底色 · 青蓝高亮 · 训练态势辨识",
  },
  graphite: {
    label: "深色主题", short: "Graphite / AIP-inspired", base: "#1b1e24", panel: "#292e36",
    panel2: "#22262e", border: "#414a56", accent: "#8ab6e5", text: "#eef1f6",
    muted: "#a3aebb", green: "#56b89b", orange: "#d5ab5b",
    desc: "石墨色底 · 中性分层 · 企业数据分析",
  },
  light: {
    label: "浅色主题", short: "Arctic / Modern Light", base: "#f2f5f9", panel: "#ffffff",
    panel2: "#e8eef6", border: "#cbd6e3", accent: "#2568a7", text: "#213246",
    muted: "#63768b", green: "#178368", orange: "#bd8730",
    desc: "冰川灰白 · 现代信息密度 · 清晰易读",
  },
};

export function isTheme(value: string): value is Theme {
  return (THEME_IDS as readonly string[]).includes(value);
}

export function assignTheme(root: HTMLElement, theme: Theme): void {
  root.setAttribute("data-tpaa-theme", theme);
}
