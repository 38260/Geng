import type { CatchUpStatus, LifecycleStage } from "@/types/api";

/** 1.2万 / 18.2K / 52.7万 —— 与参考图一致的紧凑数字 */
export function compact(value: number | null | undefined): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}亿`;
  if (Math.abs(n) >= 10_000) return `${(n / 10_000).toFixed(1)}万`;
  if (Math.abs(n) >= 1_000) return `${(n / 1000).toFixed(1)}K`;
  return String(Math.round(n));
}

export function withThousands(value: number | null | undefined): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return "—";
  return Math.round(n).toLocaleString("en-US");
}

/** +68% / -37% / — （null 表示样本不足，不假装是 0%） */
export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function growthTone(value: number | null | undefined): "up" | "down" | "flat" {
  if (value === null || value === undefined || !Number.isFinite(value)) return "flat";
  if (value >= 1) return "up";
  if (value <= -1) return "down";
  return "flat";
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/**
 * 增幅文字颜色 —— 参考图口径不是"涨绿跌红"，而是**跟随所处阶段的颜色**，
 * 只有负增长才统一转红：
 *   正在爆 +142% 红 / 快起飞 +68% 绿 / 上升期 +51% 蓝 / 平稳期 +12% 灰蓝 / 退潮期 -37% 红
 */
export function growthClass(value: number | null | undefined, stage?: LifecycleStage): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "text-ink-faint";
  if (value < 0) return "text-brand";
  return stage ? STAGE_STYLE[stage].text : "text-go";
}

/** chip 底色/字色取自参考图对应徽章的采样值 */
export const STAGE_STYLE: Record<LifecycleStage, { chip: string; dot: string; text: string }> = {
  explosive: { chip: "bg-brand-soft text-brand", dot: "bg-brand", text: "text-brand" },
  rising: { chip: "bg-flare-soft text-flare", dot: "bg-flare", text: "text-flare" },
  sprouting: { chip: "bg-gold/15 text-[#B2750A]", dot: "bg-gold", text: "text-gold" },
  plateau: { chip: "bg-dusk-soft text-dusk", dot: "bg-dusk", text: "text-dusk" },
  receding: { chip: "bg-dusk-soft text-dusk", dot: "bg-dusk", text: "text-dusk" },
  obsolete: { chip: "bg-dusk-soft text-ink-mute", dot: "bg-ink-faint", text: "text-ink-mute" },
  // 数据不足是闸门态：刻意不给它任何"阶段色"，免得看起来像一个正常结论
  insufficient: { chip: "bg-ink-faint/15 text-ink-mute", dot: "bg-ink-faint", text: "text-ink-mute" },
};

/** 「快起飞」这类上升中的梗用绿色徽章，与参考图一致 */
export function stageChipClass(stage: LifecycleStage, nickname: string): string {
  if (nickname === "快起飞") return "bg-go-soft text-go";
  return STAGE_STYLE[stage].chip;
}

export const CATCH_STYLE: Record<CatchUpStatus, { chip: string; text: string; dot: string }> = {
  can_catch: { chip: "bg-go-soft text-go", text: "text-go", dot: "bg-go" },
  caution: { chip: "bg-gold/20 text-[#B2750A]", text: "text-[#B2750A]", dot: "bg-gold" },
  too_late: { chip: "bg-brand/10 text-brand", text: "text-brand", dot: "bg-brand" },
  insufficient: { chip: "bg-ink-faint/15 text-ink-mute", text: "text-ink-mute", dot: "bg-ink-faint" },
};

export const STAGE_ORDER: LifecycleStage[] = [
  "sprouting",
  "rising",
  "explosive",
  "plateau",
  "receding",
  "obsolete",
  "insufficient",
];

export function safeNumber(value: number | null | undefined, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
