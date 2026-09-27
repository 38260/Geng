import { Link } from "react-router-dom";

import { ArrowRightIcon } from "@/components/icons";
import { StickerThumb } from "@/components/StickerThumb";
import type { MemeCard as Card } from "@/types/api";
import { CATCH_STYLE, STAGE_STYLE, percent, growthClass } from "@/utils/format";

function RankBadge({ rank }: { rank: number }) {
  const top = rank === 1;
  return (
    <span
      className={[
        "tabular absolute -left-1 -top-2 z-10 grid h-7 w-7 place-items-center rounded-full text-[13px] font-black ring-2 ring-white",
        top ? "bg-gold text-white shadow-[0_4px_10px_-4px_rgba(245,166,35,0.9)]" : "bg-white text-ink-soft",
      ].join(" ")}
    >
      {rank}
    </span>
  );
}

/** 今日热榜卡片：只回答"现在该不该赶"，不堆指标。 */
export function MemeCard({ item, rank }: { item: Card; rank: number }) {
  const stage = STAGE_STYLE[item.stage];

  return (
    <article className="card card-hover animate-rise flex flex-col p-3">
      <div className="relative">
        <RankBadge rank={rank} />
        <StickerThumb thumbnail={item.thumbnail} ratio="4/3" emojiSize={40} />
      </div>

      <h3 className="mt-3 truncate text-[15px] font-bold" title={item.description}>
        {item.name}
      </h3>

      <div className="mt-1.5 flex items-center gap-2">
        <span className="flex items-center gap-0.5 text-brand">
          <span className="text-[15px] leading-none">🔥</span>
          <span className="tabular text-[20px] font-black leading-none">{Math.round(item.hotness)}</span>
        </span>
        <span className={`chip ${stage.chip}`}>{item.nickname}</span>
      </div>

      <div className="mt-2.5 flex items-center justify-between text-[12px]">
        <span className="text-ink-mute">最近7天讨论量</span>
        <span className={`tabular font-bold ${growthClass(item.discussion_growth)}`}>
          {percent(item.discussion_growth)}
        </span>
      </div>

      <Link
        to={`/meme/${item.id}`}
        className="mt-3 flex items-center justify-center gap-1.5 rounded-full bg-brand-soft py-2 text-[13px] font-semibold text-brand transition hover:bg-brand hover:text-white"
      >
        查看详情
        <ArrowRightIcon size={15} />
      </Link>
    </article>
  );
}

/** 精选推荐卡片：横向小卡，一句状态描述 + 箭头。 */
export function RecommendationCard({ item }: { item: Card }) {
  const stage = STAGE_STYLE[item.stage];
  const catchStyle = CATCH_STYLE[item.catch_status];

  return (
    <Link to={`/meme/${item.id}`} className="card card-hover animate-rise flex items-center gap-3 p-3">
      <StickerThumb thumbnail={item.thumbnail} ratio="1/1" emojiSize={30} className="w-[68px] shrink-0" />
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-[14px] font-bold">{item.name}</h3>
        <div className="mt-1 flex items-center gap-1.5">
          <span className="flex items-center gap-0.5 text-brand">
            <span className="text-[12px] leading-none">🔥</span>
            <span className="tabular text-[16px] font-black leading-none">{Math.round(item.hotness)}</span>
          </span>
          <span className={`chip ${stage.chip}`}>{item.stage_label}</span>
        </div>
        <div className="mt-1.5 flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${catchStyle.dot}`} />
          <span className="truncate text-[12px] text-ink-mute">{item.catch_reason.slice(0, 18) || item.catch_label}</span>
        </div>
      </div>
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-flare/10 text-flare">
        <ArrowRightIcon size={15} />
      </span>
    </Link>
  );
}
