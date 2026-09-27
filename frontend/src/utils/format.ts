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

/** 状态色：涨=绿，跌=珊瑚红，持平=蓝灰（参考图口径） */
export function growthClass(value: number | null | undefined): string {
  const tone = growthTone(value);
  if (tone === "up") return "text-go";
  if (tone === "down") return "text-brand";
  return "text-flare";
}

export const STAGE_STYLE: Record<LifecycleStage, { chip: string; dot: string; text: string }> = {
  explosive: { chip: "bg-brand text-white", dot: "bg-brand", text: "text-brand" },
  rising: { chip: "bg-go/10 text-go", dot: "bg-go", text: "text-go" },
  sprouting: { chip: "bg-gold/20 text-[#B2750A]", dot: "bg-gold", text: "text-gold" },
  plateau: { chip: "bg-flare/10 text-flare", dot: "bg-flare", text: "text-flare" },
  receding: { chip: "bg-dusk/20 text-dusk", dot: "bg-dusk", text: "text-dusk" },
  obsolete: { chip: "bg-ink-faint/25 text-ink-mute", dot: "bg-ink-faint", text: "text-ink-mute" },
};

export const CATCH_STYLE: Record<CatchUpStatus, { chip: string; text: string; dot: string }> = {
  can_catch: { chip: "bg-go/10 text-go", text: "text-go", dot: "bg-go" },
  caution: { chip: "bg-gold/20 text-[#B2750A]", text: "text-[#B2750A]", dot: "bg-gold" },
  too_late: { chip: "bg-brand/10 text-brand", text: "text-brand", dot: "bg-brand" },
};

export const STAGE_ORDER: LifecycleStage[] = [
  "sprouting",
  "rising",
  "explosive",
  "plateau",
  "receding",
  "obsolete",
];

export function safeNumber(value: number | null | undefined, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
