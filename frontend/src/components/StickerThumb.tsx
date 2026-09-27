import { useState, type CSSProperties } from "react";

import type { Thumbnail } from "@/types/api";

/**
 * 梗缩略图。
 *
 * 参考图里已有的封面直接从 `public/thumbs/`（由 scripts/extract_ref_assets.py
 * 裁出）取用；参考图里没有的梗退回"主题色 + 表情"贴纸块，
 * 比例、圆角、裁剪方式保持一致，不会出现两种画风。
 */
export function StickerThumb({
  thumbnail,
  ratio = "6/5",
  emojiSize = 44,
  className = "",
  rounded = "rounded-tile",
  children,
}: {
  thumbnail: Thumbnail;
  ratio?: string;
  emojiSize?: number;
  className?: string;
  rounded?: string;
  children?: React.ReactNode;
}) {
  const style: CSSProperties = { aspectRatio: ratio };
  // B站封面是外链，挂了也要退回贴纸而不是裂图
  const [broken, setBroken] = useState(false);
  const image = thumbnail.image && !broken ? thumbnail.image : "";

  if (image) {
    return (
      <div className={`relative overflow-hidden ${rounded} ${className}`} style={style}>
        <img
          src={image}
          alt=""
          loading="lazy"
          // B站图床会因 Referer 直接 403，外链封面必须不带来源请求
          referrerPolicy="no-referrer"
          onError={() => setBroken(true)}
          className="absolute inset-0 h-full w-full object-cover"
        />
        {children}
      </div>
    );
  }

  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden ${rounded} ${className}`}
      style={{
        ...style,
        background: `radial-gradient(120% 120% at 22% 12%, #ffffff 0%, ${thumbnail.color} 46%, ${thumbnail.color} 100%)`,
      }}
    >
      <span aria-hidden className="pointer-events-none absolute -right-4 -top-5 h-14 w-14 rounded-full bg-white/45" />
      <span aria-hidden className="pointer-events-none absolute -bottom-6 -left-3 h-16 w-16 rounded-full bg-white/30" />
      <span
        className="relative select-none leading-none drop-shadow-[0_2px_6px_rgba(0,0,0,0.10)]"
        style={{ fontSize: emojiSize }}
      >
        {thumbnail.emoji}
      </span>
      {children}
    </div>
  );
}
