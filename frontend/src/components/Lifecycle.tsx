import type { Lifecycle, LifecycleStage } from "@/types/api";
import { STAGE_STYLE } from "@/utils/format";

const EMOJI: Record<LifecycleStage, string> = {
  sprouting: "🌱",
  rising: "📈",
  explosive: "🔥",
  plateau: "🌊",
  receding: "📉",
  obsolete: "🪦",
  // 「数据不足」是闸门不是阶段，画在时间轴上会让人以为存在这么一站
  insufficient: "",
};

/**
 * 生命周期可视化：🌱 ─ 📈 ─ 🔥 ─ 🌊 ─ 📉 ─ ，当前阶段带"现在"标记。
 * 阶段由后端算法给出，这里只负责画出来。
 */
export function LifecycleTrack({ lifecycle }: { lifecycle: Lifecycle }) {
  // 时间轴上只画六个真阶段；"数据不足"是闸门，画成一站等于编造一个阶段
  const stages = lifecycle.stages.filter((stage) => stage.key !== "insufficient");
  const starved = lifecycle.stage === "insufficient";

  return (
    <div className="card p-5">
      <div className="mb-5 flex items-center gap-2.5">
        <span className="text-[19px]">⭐</span>
        <h3 className="text-[18px] font-bold">生命周期</h3>
        <span className={`chip ml-auto ${STAGE_STYLE[lifecycle.stage].chip}`}>
          {lifecycle.emoji} {lifecycle.stage_label}
        </span>
      </div>

      {/* 观测天数不够时宁可不画这条路径，也不把接口抖动画成"正在退潮" */}
      {starved ? (
        <div className="rounded-lg bg-ink-faint/10 px-4 py-3 text-[13px] leading-relaxed text-ink-mute">
          {lifecycle.reasons[0] || "最近观测到的天数不够，暂时给不出阶段结论。"}
          <span className="mt-1 block text-[12px] text-ink-faint">
            热度分数照旧（那是存量水平，跨梗同一把尺子），只是"在涨还是在退"这个判断
            要先等采集把洞补上才敢说。
          </span>
        </div>
      ) : (
      <div className="relative">
        {/* 连接线 */}
        <span aria-hidden className="absolute left-[9%] right-[9%] top-[21px] h-[2px] rounded bg-line" />
        <div className="relative flex items-start justify-between">
          {stages.map((stage) => {
            const active = stage.active;
            return (
              <div key={stage.key} className="flex w-[15%] flex-col items-center gap-2">
                <span
                  className={[
                    "grid h-[42px] w-[42px] place-items-center rounded-full text-[19px] transition",
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
                    "text-[13px] leading-none",
                    active ? "font-bold text-go" : "text-ink-faint",
                  ].join(" ")}
                >
                  {stage.label}
                </span>
                {active ? (
                  <span className="mt-1 flex flex-col items-center">
                    <span className="h-[2px] w-6 rounded bg-go" />
                    <span className="mt-1 text-[11px] font-semibold text-go">当前阶段</span>
                  </span>
                ) : (
                  <span className="mt-1 h-[2px] w-6" />
                )}
              </div>
            );
          })}
        </div>
      </div>
      )}

      {lifecycle.reasons.length ? (
        <ul className="mt-5 space-y-1.5 border-t border-line pt-4 text-[13px] leading-relaxed text-ink-mute">
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
