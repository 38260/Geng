import type { Lifecycle, LifecycleStage } from "@/types/api";
import { STAGE_STYLE } from "@/utils/format";

const EMOJI: Record<LifecycleStage, string> = {
  sprouting: "🌱",
  rising: "📈",
  explosive: "🔥",
  plateau: "🌊",
  receding: "📉",
  obsolete: "🪦",
};

/**
 * 生命周期可视化：🌱 ─ 📈 ─ 🔥 ─ 🌊 ─ 📉 ─ ，当前阶段带"现在"标记。
 * 阶段由后端算法给出，这里只负责画出来。
 */
export function LifecycleTrack({ lifecycle }: { lifecycle: Lifecycle }) {
  const stages = lifecycle.stages;

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-[17px]">⭐</span>
        <h3 className="text-[15px] font-bold">生命周期</h3>
        <span className={`chip ml-auto ${STAGE_STYLE[lifecycle.stage].chip}`}>
          {lifecycle.emoji} {lifecycle.stage_label}
        </span>
      </div>

      <div className="relative">
        {/* 连接线 */}
        <span aria-hidden className="absolute left-[9%] right-[9%] top-[17px] h-[2px] rounded bg-line" />
        <div className="relative flex items-start justify-between">
          {stages.map((stage) => {
            const active = stage.active;
            return (
              <div key={stage.key} className="flex w-[15%] flex-col items-center gap-1.5">
                <span
                  className={[
                    "grid h-[34px] w-[34px] place-items-center rounded-full text-[15px] transition",
                    active
                      ? "bg-go/15 ring-2 ring-go animate-pulse-soft"
                      : "bg-dusk/10 opacity-70",
                  ].join(" ")}
                  title={`${stage.label}${active ? "（当前阶段）" : ""}`}
                >
                  {EMOJI[stage.key]}
                </span>
                <span
                  className={[
                    "text-[11px] leading-none",
                    active ? "font-bold text-go" : "text-ink-faint",
                  ].join(" ")}
                >
                  {stage.label}
                </span>
                {active ? (
                  <span className="mt-0.5 flex flex-col items-center">
                    <span className="h-[2px] w-6 rounded bg-go" />
                    <span className="mt-1 text-[10px] font-semibold text-go">现在</span>
                  </span>
                ) : (
                  <span className="mt-0.5 h-[2px] w-6" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {lifecycle.reasons.length ? (
        <ul className="mt-4 space-y-1 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-mute">
          {lifecycle.reasons.map((reason) => (
            <li key={reason} className="flex gap-1.5">
              <span className="text-ink-faint">·</span>
              {reason}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
