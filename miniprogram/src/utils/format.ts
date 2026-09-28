/**
 * 展示层纯函数：格式化、配色映射。
 *
 * 刻意不放任何请求或状态，方便用 `node --test` 直接跑单测（tests/format.test.ts）。
 * 规则与 web 端保持一致：数字用"万/亿"，增长没有对照就显示 "—"，不拿 0 冒充"没涨"。
 */
import type { CatchUpStatus, CertLabel, IntroSource, LifecycleStage } from "@/types/api";

export function compact(value: number | null | undefined): string {
  const n = Number(value || 0);
  if (!Number.isFinite(n)) return "0";
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(n >= 1_000_000_000 ? 0 : 1)}亿`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(n >= 1_000_000 ? 0 : 1)}万`;
  return n.toLocaleString("en-US");
}

/** 增长率：后端给的是百分数（23616 表示 +23616%）；null 表示没有可比对照。 */
export function growthText(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Math.round(value).toLocaleString("en-US")}%`;
}

export function isUp(value: number | null | undefined): boolean {
  return typeof value === "number" && value > 0;
}

/** "2026-09-26" → "9 月 26 日"；空值给"未知"，不显示空白。 */
export function dateCn(value: string | null | undefined): string {
  if (!value) return "未知";
  const parts = value.slice(0, 10).split("-");
  if (parts.length < 3) return value;
  return `${Number(parts[1])} 月 ${Number(parts[2])} 日`;
}

/** MM-DD（趋势图横轴用） */
export function dayShort(value: string): string {
  return value.length >= 10 ? value.slice(5, 10) : value;
}

/**
 * 数据新鲜度那句话。
 *
 * 采集窗口不含今天，所以"统计截至昨天"是常态；滞后超过 1 天要标出来，
 * 免得用户拿三天前的数当今天的数用。
 */
export function freshnessText(through: string | null, lagDays: number | null): string {
  if (!through) return "还没有采集数据";
  const when = dateCn(through);
  if (lagDays === null) return `统计截至 ${when}`;
  if (lagDays <= 0) return `统计截至 ${when}（含今天）`;
  if (lagDays === 1) return `统计截至 ${when}（昨天）`;
  return `统计截至 ${when} · 已滞后 ${lagDays} 天`;
}

export function isStale(lagDays: number | null): boolean {
  return lagDays !== null && lagDays > 1;
}

export interface Tone {
  /** 对应的样式类名（在 app.scss / 页面 scss 里定义） */
  chip: string;
  color: string;
}

const STAGE_TONE: Record<LifecycleStage, Tone> = {
  sprouting: { chip: "chip-dusk", color: "#546F98" },
  rising: { chip: "chip-flare", color: "#0D8AFE" },
  explosive: { chip: "chip-brand", color: "#FB3A5E" },
  plateau: { chip: "chip-gold", color: "#B2750A" },
  receding: { chip: "chip-dusk", color: "#546F98" },
  obsolete: { chip: "chip-mute", color: "#B0BAD0" },
};

const CATCH_TONE: Record<CatchUpStatus, Tone> = {
  can_catch: { chip: "chip-go", color: "#019646" },
  caution: { chip: "chip-gold", color: "#B2750A" },
  too_late: { chip: "chip-mute", color: "#5E739F" },
};

const CERT_TONE: Record<CertLabel, string> = {
  "双 UP 认证": "chip-brand",
  "梗百科认证": "chip-flare",
  "梗指南认证": "chip-flare",
  未认证: "chip-mute",
};

const INTRO_TONE: Record<IntroSource, string> = {
  manual: "chip-go",
  evidence: "chip-flare",
  none: "chip-gold",
};

export function stageTone(stage: LifecycleStage): Tone {
  return STAGE_TONE[stage] || { chip: "chip", color: "#3C5989" };
}

export function catchTone(status: CatchUpStatus): Tone {
  return CATCH_TONE[status] || CATCH_TONE.caution;
}

export function certTone(label: CertLabel): string {
  return CERT_TONE[label] || "chip";
}

export function introTone(source: IntroSource): string {
  return INTRO_TONE[source] || "chip";
}

/** 演示数据必须一眼看出来，不能和真实抓取结果混在同一张榜上。 */
export function isRealMeme(memeDataSource: string, verificationState: string): boolean {
  return memeDataSource === "bilibili" && ["verified_both", "partially_verified"].includes(verificationState);
}

/** 置信度 0-1 → "判断置信度 95%"；0 表示算法没给，不显示成 0%。 */
export function confidenceText(confidence: number | null | undefined): string {
  if (!confidence) return "置信度：算法未给出";
  return `判断置信度 ${Math.round(confidence * 100)}%`;
}

/** 趋势图归一化：返回 0-1 的高度比例，全 0 时给一列等高，不出现 NaN。 */
export function normalizeSeries(values: number[]): number[] {
  const max = Math.max(...values, 0);
  if (max <= 0) return values.map(() => 0.06);
  return values.map((value) => Math.max(0.06, Math.min(1, value / max)));
}
