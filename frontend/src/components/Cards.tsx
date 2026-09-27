import { CommentIcon, DanmakuIcon, PlayIcon, UsersIcon } from "@/components/icons";
import { StickerThumb } from "@/components/StickerThumb";
import type { MetricPair, Thumbnail, VideoItem } from "@/types/api";
import { compact, growthClass, percent } from "@/utils/format";

const ICONS = {
  videos: PlayIcon,
  creators: UsersIcon,
  comments: CommentIcon,
  danmaku: DanmakuIcon,
} as const;

export function MetricCard({
  metric,
  label,
  kind,
}: {
  metric: MetricPair;
  label: string;
  kind: keyof typeof ICONS;
}) {
  const Icon = ICONS[kind];
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl bg-dusk-soft px-4 py-3.5">
      <div className="flex items-center gap-2 text-[14px] font-semibold text-ink-soft">
        <Icon size={17} className="text-flare" />
        {label}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="tabular text-[24px] font-black leading-none">{compact(metric.value)}</span>
        <span className={`tabular text-[14px] font-bold ${growthClass(metric.growth)}`}>
          {percent(metric.growth)}
        </span>
      </div>
    </div>
  );
}

/** B 站视频卡：真实封面优先，没有才退回梗的贴纸占位。 */
export function VideoCard({ video, thumbnail }: { video: VideoItem; thumbnail: Thumbnail }) {
  // 只有真实采集的视频才有真封面；演示数据宁可标出来，也不拿梗图冒充某条视频的封面
  const realCover = video.data_source === "bilibili" && video.cover ? video.cover : "";
  return (
    <a
      href={video.url}
      target="_blank"
      rel="noreferrer noopener"
      className="card card-hover flex flex-col overflow-hidden p-0"
    >
      <div className="relative p-2.5 pb-0">
        <StickerThumb thumbnail={{ ...thumbnail, image: realCover }} ratio="16/9" emojiSize={34}>
          {!realCover ? (
            <span className="absolute right-4 top-4 rounded-md bg-ink/55 px-1.5 py-0.5 text-[10px] font-semibold text-white">
              演示封面
            </span>
          ) : null}
        </StickerThumb>
        <span className="absolute left-1/2 top-1/2 grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white/80 text-[13px] shadow-sm">
          ▶
        </span>
        <span className="tabular absolute bottom-4 right-4 rounded-md bg-black/65 px-1.5 py-0.5 text-[11px] font-medium text-white">
          {video.duration_text}
        </span>
      </div>
      <div className="flex flex-1 flex-col px-3.5 pb-3.5 pt-2.5">
        <h4 className="line-clamp-2 text-[15px] font-semibold leading-snug">{video.title}</h4>
        <div className="mt-1 truncate text-[12px] text-ink-faint">@{video.author}</div>
        <div className="mt-auto flex items-center gap-3 pt-2.5 text-[13px] text-ink-mute">
          <span className="flex items-center gap-1">
            <PlayIcon size={14} className="text-ink-faint" />
            {video.view_text}
          </span>
          <span className="flex items-center gap-1">
            <DanmakuIcon size={14} className="text-ink-faint" />
            {video.danmaku_text}
          </span>
        </div>
      </div>
    </a>
  );
}
