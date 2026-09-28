import { Image, Text, View } from "@tarojs/components";
import { useState } from "react";

import type { MemeCard } from "@/types/api";
import {
  catchTone,
  certTone,
  growthText,
  isRealMeme,
  stageTone,
} from "@/utils/format";

/** 缩略图：贴纸打底 + 真实封面盖在上面。封面挂了（403/无网）也还剩表情，不会是个白框。 */
function Thumb({ meme }: { meme: MemeCard }) {
  const [failed, setFailed] = useState(false);
  return (
    <View className="thumb-sticker" style={{ background: meme.thumbnail?.color || "#FFE9E4" }}>
      <Text>{meme.thumbnail?.emoji || "🎬"}</Text>
      {meme.thumbnail?.image && !failed ? (
        <Image
          className="thumb-img"
          src={meme.thumbnail.image}
          mode="aspectFill"
          lazyLoad
          onError={() => setFailed(true)}
        />
      ) : null}
    </View>
  );
}

export function MemeCardView({
  meme,
  rank,
  onOpen,
}: {
  meme: MemeCard;
  rank?: number;
  onOpen: (id: number) => void;
}) {
  const stage = stageTone(meme.stage);
  const catchT = catchTone(meme.catch_status);
  const real = isRealMeme(meme.meme_data_source, meme.verification_state);

  return (
    <View className="card meme-card" onClick={() => onOpen(meme.id)}>
      <View className="meme-head">
        {rank !== undefined ? (
          <Text className={`rank${rank < 3 ? " rank-top" : ""}`}>{rank + 1}</Text>
        ) : null}
        <Thumb meme={meme} />
        <View className="meme-main">
          <View className="row">
            <Text className="meme-name">{meme.name}</Text>
            <Text className="meme-score tabular" style={{ color: stage.color }}>
              {Math.round(meme.hotness)}
            </Text>
          </View>
          <View className="row meme-chips">
            <Text className={`chip ${stage.chip}`}>{meme.nickname}</Text>
            <Text className={`chip ${catchT.chip}`}>{meme.catch_label}</Text>
          </View>
          {meme.description || meme.catch_reason ? (
            <Text className="meme-desc">{meme.description || meme.catch_reason}</Text>
          ) : null}
        </View>
      </View>

      <View className="meme-foot">
        <Text className={`chip ${certTone(meme.cert_label)}`}>{meme.cert_label}</Text>
        {real ? null : <Text className="chip chip-gold">演示数据</Text>}
        <Text className="meme-growth tabular">
          讨论 {growthText(meme.discussion_growth)} · 视频 {growthText(meme.video_growth)}
        </Text>
      </View>
    </View>
  );
}

/**
 * 紧凑行：梗库与收藏列表用。
 * 信息对齐 Web 的「热度趋势」表：热度条 + 阶段 + 7 天增幅 + 赶梗结论，
 * 一屏能扫完相对位置，又不至于像表格那样在手机上看不下。
 */
export function MemeRow({
  meme,
  max = 100,
  favoriteAt,
  onOpen,
}: {
  meme: MemeCard;
  max?: number;
  favoriteAt?: string;
  onOpen: (id: number) => void;
}) {
  const stage = stageTone(meme.stage);
  const catchStyle = catchTone(meme.catch_status);
  const width = Math.max(4, Math.min(100, Math.round((meme.hotness / (max || 100)) * 100)));
  const [coverFailed, setCoverFailed] = useState(false);
  return (
    <View className="meme-row" onClick={() => onOpen(meme.id)}>
      <View className="row-emoji" style={{ background: meme.thumbnail?.color || "#FFE9E4" }}>
        <Text>{meme.emoji || "🎬"}</Text>
        {meme.thumbnail?.image && !coverFailed ? (
          <Image
            className="row-img"
            src={meme.thumbnail.image}
            mode="aspectFill"
            lazyLoad
            onError={() => setCoverFailed(true)}
          />
        ) : null}
      </View>
      <View className="row-main">
        <View className="row-line">
          <Text className="row-name">{meme.name}</Text>
          <Text className="row-score tabular" style={{ color: stage.color }}>
            {Math.round(meme.hotness)}
          </Text>
        </View>
        <View className="row-bar">
          <View className="row-bar-fill" style={{ width: `${width}%`, background: stage.color }} />
        </View>
        <View className="row-line row-meta">
          <Text className="row-sub">
            {meme.stage_label} · {meme.cert_label}
            {favoriteAt ? ` · 收藏于 ${favoriteAt}` : ""}
          </Text>
          <Text className="row-growth tabular">
            讨论 {growthText(meme.discussion_growth)}
            <Text className={` chip ${catchStyle.chip} row-catch`}>{meme.catch_label}</Text>
          </Text>
        </View>
      </View>
    </View>
  );
}
