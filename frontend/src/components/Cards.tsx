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

const TONES: Record<keyof typeof ICONS, string> = {
  videos: "bg-flare/10 text-flare",
  creators: "bg-flare/10 text-flare",
  comments: "bg-go/10 text-go",
  danmaku: "bg-flare/10 text-flare",
};

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
    <div className="card flex items-center gap-3 px-4 py-3.5">
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${TONES[kind]}`}>
        <Icon size={18} />
      </span>
      <div className="min-w-0">
        <div className="text-[12px] text-ink-mute">{label}</div>
        <div className="flex items-baseline gap-1.5">
          <span className="tabular text-[19px] font-black leading-tight">{compact(metric.value)}</span>
          <span className={`tabular text-[12px] font-bold ${growthClass(metric.growth)}`}>
            {percent(metric.growth)}
          </span>
        </div>
      </div>
    </div>
  );
}

/** B 站视频卡：缩略图 + 标题 + UP主 + 播放/弹幕，文字保持很少。 */
export function VideoCard({ video, thumbnail }: { video: VideoItem; thumbnail: Thumbnail }) {
  return (
    <a
      href={video.url}
      target="_blank"
      rel="noreferrer noopener"
      className="card card-hover flex flex-col overflow-hidden p-0"
    >
      <div className="relative p-2.5 pb-0">
        <StickerThumb thumbnail={thumbnail} ratio="16/9" emojiSize={34} />
        <span className="absolute left-1/2 top-1/2 grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white/80 text-[13px] shadow-sm">
          ▶
        </span>
        <span className="tabular absolute bottom-4 right-4 rounded-md bg-black/65 px-1.5 py-0.5 text-[11px] font-medium text-white">
          {video.duration_text}
        </span>
      </div>
      <div className="flex flex-1 flex-col px-3 pb-3 pt-2">
        <h4 className="line-clamp-2 text-[13px] font-semibold leading-snug">{video.title}</h4>
        <div className="mt-1 truncate text-[11px] text-ink-faint">@{video.author}</div>
        <div className="mt-auto flex items-center gap-3 pt-2 text-[11px] text-ink-mute">
          <span className="flex items-center gap-1">
            <PlayIcon size={13} className="text-ink-faint" />
            {video.view_text}
          </span>
          <span className="flex items-center gap-1">
            <DanmakuIcon size={13} className="text-ink-faint" />
            {video.danmaku_text}
          </span>
        </div>
      </div>
    </a>
  );
}
