import type { CSSProperties } from "react";

import type { Thumbnail } from "@/types/api";

/**
 * 梗缩略图（演示用"贴纸"）。
 *
 * 说明：项目里没有真实梗图素材，也不允许从 B 站盗图，因此这里用
 * "主题色 + 表情符号"的贴纸块占位；比例、圆角、裁剪方式与参考图保持一致，
 * 换成真实封面时只需要把 <img> 放进来，不需要改布局。
 */
export function StickerThumb({
  thumbnail,
  label,
  ratio = "4/3",
  emojiSize = 46,
  className = "",
  children,
}: {
  thumbnail: Thumbnail;
  label?: string;
  ratio?: string;
  emojiSize?: number;
  className?: string;
  children?: React.ReactNode;
}) {
  const style: CSSProperties = {
    aspectRatio: ratio,
    background: `radial-gradient(120% 120% at 22% 12%, #ffffff 0%, ${thumbnail.color} 46%, ${thumbnail.color} 100%)`,
  };

  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden rounded-tile ${className}`}
      style={style}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute -right-4 -top-5 h-14 w-14 rounded-full bg-white/45"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -bottom-6 -left-3 h-16 w-16 rounded-full bg-white/30"
      />
      <span className="relative select-none leading-none drop-shadow-[0_2px_6px_rgba(0,0,0,0.10)]" style={{ fontSize: emojiSize }}>
        {thumbnail.emoji}
      </span>
      {label ? (
        <span className="absolute bottom-1.5 left-2 right-2 truncate text-[11px] font-medium text-ink-soft/80">
          {label}
        </span>
      ) : null}
      {children}
    </div>
  );
}
