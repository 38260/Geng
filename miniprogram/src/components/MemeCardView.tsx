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
            <Text className={`chip ${stage.chip}`}>
              {meme.emoji} {meme.nickname}
            </Text>
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

/** 紧凑行：梗库/搜索结果用，一屏能看更多条。 */
export function MemeRow({ meme, onOpen }: { meme: MemeCard; onOpen: (id: number) => void }) {
  const stage = stageTone(meme.stage);
  return (
    <View className="meme-row" onClick={() => onOpen(meme.id)}>
      <View className="row-emoji" style={{ background: meme.thumbnail?.color || "#FFE9E4" }}>
        <Text>{meme.emoji || "🎬"}</Text>
        {meme.thumbnail?.image ? (
          <Image className="row-img" src={meme.thumbnail.image} mode="aspectFill" lazyLoad />
        ) : null}
      </View>
      <View className="row-main">
        <Text className="row-name">{meme.name}</Text>
        <Text className="row-sub">
          {meme.stage_label} · {meme.cert_label}
        </Text>
      </View>
      <Text className="row-score tabular" style={{ color: stage.color }}>
        {Math.round(meme.hotness)}
      </Text>
    </View>
  );
}
