import { Link } from "react-router-dom";

import { ArrowRightIcon } from "@/components/icons";
import { StickerThumb } from "@/components/StickerThumb";
import type { MemeCard as Card } from "@/types/api";
import { CATCH_STYLE, STAGE_STYLE, growthClass, percent, stageChipClass } from "@/utils/format";

/** 名次徽章：参考图里它就贴在封面插图的左上角内侧，第一名是金色圆牌。 */
function RankBadge({ rank }: { rank: number }) {
  const top = rank === 1;
  return (
    <span
      className={[
        "tabular absolute left-1 top-1 z-10 grid h-[40px] w-[40px] place-items-center rounded-full",
        "text-[18px] font-black ring-[3px] ring-surface",
        top ? "bg-gold text-[#3A2408]" : "bg-surface text-ink",
      ].join(" ")}
    >
      {rank}
      {!top ? <span className="absolute inset-0 rounded-full border border-line" /> : null}
    </span>
  );
}

/** 今日热榜卡片：只回答"现在该不该赶"，不堆指标。 */
export function MemeCard({ item, rank }: { item: Card; rank: number }) {
  return (
    <article className="card animate-rise flex min-w-0 flex-col rounded-2xl border-line p-3 shadow-none">
      <div className="relative">
        <RankBadge rank={rank} />
        <StickerThumb thumbnail={item.thumbnail} ratio="6/5" emojiSize={48} rounded="rounded-xl" />
      </div>

      <h3 className="mt-5 truncate text-[19px] font-bold leading-none" title={item.description}>
        {item.name}
      </h3>

      <div className="mt-4 flex items-center gap-2">
        <span className="flex items-center gap-1 text-brand">
          <span className="text-[20px] leading-none">🔥</span>
          <span className="tabular text-[26px] font-black leading-none">{Math.round(item.hotness)}</span>
        </span>
        <span className={`chip ${stageChipClass(item.stage, item.nickname)}`}>{item.nickname}</span>
      </div>

      <div className="mt-4 flex items-center justify-between text-[13px]">
        <span className="font-semibold text-ink-mute">最近7天讨论量</span>
        <span className={`tabular text-[15px] font-black ${growthClass(item.discussion_growth, item.stage)}`}>
          {percent(item.discussion_growth)}
        </span>
      </div>

      <Link
        to={`/meme/${item.id}`}
        className="mt-5 flex items-center justify-center gap-1.5 rounded-full bg-brand-soft py-3 text-[15px] font-bold text-brand transition hover:bg-brand hover:text-white"
      >
        查看详情
        <ArrowRightIcon size={17} />
      </Link>
    </article>
  );
}

/**
 * 精选推荐卡片：竖版封面在左，右侧名称 / 热度 / 阶段，
 * 底部一整行才是"一句状态 + 圆形箭头"，与参考图同构。
 */
export function RecommendationCard({ item }: { item: Card }) {
  const stage = STAGE_STYLE[item.stage];
  const catchStyle = CATCH_STYLE[item.catch_status];

  return (
    <Link to={`/meme/${item.id}`} className="card animate-rise flex flex-col rounded-2xl border-line p-3 shadow-none">
      <div className="flex items-start gap-3.5">
        <StickerThumb
          thumbnail={item.thumbnail}
          ratio="5/7"
          emojiSize={30}
          rounded="rounded-xl"
          className="w-[104px] shrink-0"
        />
        <div className="min-w-0 flex-1 pt-0.5">
          <h3 className="truncate text-[18px] font-bold leading-none">{item.name}</h3>
          <div className="mt-4 flex items-center gap-1 text-brand">
            <span className="text-[18px] leading-none">🔥</span>
            <span className="tabular text-[24px] font-black leading-none">{Math.round(item.hotness)}</span>
          </div>
          <div className="mt-3.5">
            <span className={`chip ${stage.chip}`}>{item.stage_label}</span>
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5">
          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${catchStyle.dot}`} />
          <span className="truncate text-[14px] text-ink-mute">
            {item.catch_reason.slice(0, 12) || item.catch_label}
          </span>
        </span>
        <span className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-full bg-nav-soft text-nav">
          <ArrowRightIcon size={15} />
        </span>
      </div>
    </Link>
  );
}
