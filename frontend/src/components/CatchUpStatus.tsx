import { useState } from "react";

import { CheckIcon, RefreshIcon, StarIcon } from "@/components/icons";
import type { CatchUpStatus as Status, InsightBundle } from "@/types/api";

const CHIP: Record<Status, string> = {
  can_catch: "bg-go text-white",
  caution: "bg-gold text-white",
  too_late: "bg-brand text-white",
};

/**
 * 「现在赶这个梗？」+「趋势解释」。
 *
 * AI 只是文案层：状态与置信度来自后端算法；LLM 不可用时卡片照常显示，
 * 只在文案位置给出降级说明与"重新判断"。
 */
export function CatchUpCards({
  bundle,
  onRetry,
  generating = false,
}: {
  bundle: InsightBundle;
  onRetry: () => Promise<void>;
  generating?: boolean;
}) {
  const [retrying, setRetrying] = useState(false);
  const [failed, setFailed] = useState(false);

  const advice = bundle.catch_up_advice;
  const explanation = bundle.trend_explanation;

  const adviceOk = advice?.available && advice.result?.reason;
  const explanationOk = explanation?.available && explanation.result?.text;
  const reason = adviceOk ? advice!.result.reason! : bundle.algorithm_reason;

  const retry = async () => {
    setRetrying(true);
    setFailed(false);
    try {
      await onRetry();
    } catch {
      setFailed(true);
    } finally {
      setRetrying(false);
    }
  };

  const aiDown = !adviceOk || !explanationOk;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-card border border-go/20 bg-go/5 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-white text-[16px] shadow-sm">🐧</span>
          <h3 className="text-[15px] font-bold">现在赶这个梗？</h3>
          <span className={`chip ${CHIP[bundle.catch_up.status]}`}>
            <CheckIcon size={13} />
            {bundle.catch_up.label}
          </span>
          <span className="ml-auto text-[11px] text-ink-faint">
            判断置信度 {Math.round((bundle.catch_up.confidence || 0) * 100)}%
          </span>
        </div>

        <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{reason}</p>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-ink-faint">
          {adviceOk ? (
            <span>
              文案来源：{advice!.source === "rule" ? "算法兜底" : advice!.model || "LongCat"} · 状态由算法判定
            </span>
          ) : generating ? (
            <span>AI 文案生成中…</span>
          ) : (
            <span>暂时无法生成赶梗建议，上面是算法自己的判断</span>
          )}
          <button
            type="button"
            onClick={retry}
            disabled={retrying}
            className="ml-auto inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2 py-1 font-medium text-ink-soft transition hover:border-flare/40 hover:text-flare disabled:opacity-60"
          >
            <RefreshIcon size={13} className={retrying ? "animate-spin" : ""} />
            {retrying ? "重新判断中…" : "重新判断"}
          </button>
        </div>
        {failed ? <p className="mt-2 text-[11px] text-brand">重试还是没成功，核心数据不受影响，可以稍后再试。</p> : null}
      </section>

      <section className="rounded-card border border-flare/20 bg-flare/5 p-5">
        <div className="flex items-center gap-2">
          <StarIcon size={17} className="text-flare" />
          <h3 className="text-[15px] font-bold">趋势解释</h3>
          {explanation?.source === "cache" ? (
            <span className="chip bg-dusk/10 text-ink-mute">缓存</span>
          ) : null}
        </div>
        <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
          {explanationOk ? explanation!.result.text : bundle.algorithm_reason}
        </p>
        {!explanationOk ? (
          <p className="mt-2 text-[11px] text-ink-faint">
            {generating
              ? "AI 文案生成中，先给你看算法自己的判断。"
              : explanation?.error
                ? `AI 暂不可用：${explanation.error}`
                : "AI 文案还没生成，上面是算法自己的判断。"}
          </p>
        ) : null}
        {aiDown ? (
          <p className="mt-2 text-[11px] text-ink-faint">热度、生命周期、图表与 B 站数据都不依赖 AI，照常显示。</p>
        ) : null}
      </section>
    </div>
  );
}
