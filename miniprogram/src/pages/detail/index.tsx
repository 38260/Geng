import { Button, Image, Text, View } from "@tarojs/components";
import Taro, { useRouter, usePullDownRefresh, useShareAppMessage } from "@tarojs/taro";
import { useEffect, useRef, useState } from "react";

import { describeError, getDetail, getTrend, getVideos } from "@/api/client";
import { TrendBars, type TrendMetric } from "@/components/TrendBars";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/States";
import { useFavorites } from "@/hooks/useFavorites";
import { copyText, useLoad } from "@/hooks/useLoad";
import type { MemeDetail, VideoItem } from "@/types/api";
import {
  catchTone,
  compact,
  confidenceText,
  dateCn,
  freshnessText,
  growthText,
  introTone,
  isRealMeme,
  isUp,
  stageTone,
} from "@/utils/format";

import "./index.scss";

const METRICS: { key: keyof MemeDetail["metrics"]; label: string }[] = [
  { key: "videos", label: "视频数" },
  { key: "creators", label: "参与 UP" },
  { key: "comments", label: "评论" },
  { key: "danmaku", label: "弹幕" },
];

/** 介绍卡：人工撰写 / 证据原文拼出 / 暂无介绍，三种情况都要有明确说法。 */
function IntroCard({ detail }: { detail: MemeDetail }) {
  const intro = detail.intro;
  return (
    <View className="card">
      <View className="row-between">
        <Text className="sec-title">这个梗是什么</Text>
        <Text className={`chip ${introTone(intro.source)}`} onClick={() => intro.note && Taro.showToast({ title: intro.note, icon: "none" })}>
          {intro.source_label}
        </Text>
      </View>

      {intro.text ? (
        <Text className="intro-text">{intro.text}</Text>
      ) : (
        <View className="intro-empty">
          <Text>{intro.note}</Text>
          <Text className="intro-empty-link">介绍由人工在后台维护，补完刷新即可看到</Text>
        </View>
      )}

      {intro.excerpt ? (
        <View className="excerpt">
          <Text className="excerpt-head">
            简介原文摘录 · 来自《{intro.excerpt.video_title}》（UP：{intro.excerpt.author}）
            {intro.excerpt.data_source !== "bilibili" ? "（演示数据）" : ""}
          </Text>
          <Text className="excerpt-body">{intro.excerpt.text}</Text>
        </View>
      ) : null}

      {intro.evidence.length ? (
        <View className="evidence">
          {intro.evidence.map((item) => (
            <View
              className="evidence-row"
              key={`${item.role}-${item.bvid}`}
              onClick={() =>
                item.video_url
                  ? copyText(item.video_url)
                  : Taro.showToast({ title: "这条证据不是真实投稿，没有链接", icon: "none" })
              }
            >
              <Text className="chip chip-flare">{item.up_label}</Text>
              <Text className="evidence-title">{item.published_at ? `${item.published_at} · ` : ""}{item.video_title}</Text>
              <Text className="evidence-copy">{item.video_url ? "复制链接" : "无链接"}</Text>
            </View>
          ))}
          <Text className="faint evidence-tip">小程序打不开站外链接，点一条即可复制视频地址</Text>
        </View>
      ) : null}
    </View>
  );
}

function VideoRow({ video }: { video: VideoItem }) {
  return (
    <View className="video" onClick={() => copyText(video.url)}>
      <View className="video-main">
        <Text className="video-title">{video.title}</Text>
        <Text className="video-sub">
          {video.author} · {dateCn(video.publish_time)} · 相关性 {video.relevance_score.toFixed(2)}
          {video.data_source !== "bilibili" ? " · 演示数据" : ""}
        </Text>
      </View>
      <View className="video-num">
        <Text className="video-view tabular">{video.view_text}</Text>
        <Text className="faint tabular">{video.duration_text}</Text>
      </View>
    </View>
  );
}

/** 详情页先给 4 条，其余靠展开——一次拉 20 条，展开是瞬时的，不用等第二个请求。 */
const VIDEO_TEASER = 4;
const VIDEO_PAGE = 20;

function HeadCard({
  detail,
  id,
  favorited,
  onToggleFavorite,
}: {
  detail: MemeDetail;
  id: number;
  favorited: boolean;
  onToggleFavorite: () => void;
}) {
  const meme = detail.meme;
  const stage = stageTone(meme.stage);
  const catchT = catchTone(detail.lifecycle.catch_up.status);
  const real = isRealMeme(meme.meme_data_source, meme.verification_state);
  const [failed, setFailed] = useState(false);

  return (
    <View className="card head">
      <View className="head-top">
        {/* 封面盖在表情贴纸上：挂了也还剩个贴纸，不会是个白框 */}
        <View className="head-sticker" style={{ background: meme.thumbnail?.color || "#FFE9E4" }}>
          {meme.emoji || "🎬"}
          {meme.thumbnail?.image && !failed ? (
            <Image className="head-img" src={meme.thumbnail.image} mode="aspectFill" onError={() => setFailed(true)} />
          ) : null}
        </View>
        <View className="head-main">
          <Text className="head-name">{meme.name}</Text>
          <View className="row head-chips">
            <Text className={`chip ${stage.chip}`}>{meme.stage_label}</Text>
            <Text className={`chip ${catchT.chip}`}>{detail.lifecycle.catch_up.label}</Text>
            {real ? null : <Text className="chip chip-gold">演示数据</Text>}
          </View>
        </View>
        <View className="head-side">
          <Text className="head-score-num" style={{ color: stage.color }}>
            {Math.round(detail.hotness.score)}
          </Text>
          <Text className="faint">热度</Text>
          <View className="head-actions">
            {/* 收藏只写本机 storage：V1 没有账号体系，不跨端同步，界面也这么写 */}
            <Text
              className={`head-btn${favorited ? " head-btn-on" : ""}`}
              onClick={onToggleFavorite}
            >
              {favorited ? "已收藏" : "收藏"}
            </Text>
            {/* 小程序没有"复制链接"这种入口，转发才是原生分发路径 */}
            <Button className="head-btn head-btn-share" openType="share">
              分享
            </Button>
          </View>
        </View>
      </View>
      <Text className="head-note">
        热度为 0-100 自定义指数（近 {detail.hotness.window_days} 天），不是 B 站官方排名
      </Text>
    </View>
  );
}

export default function Detail() {
  const router = useRouter();
  const id = Number(router.params.id || 0);
  const favorites = useFavorites();
  const [metric, setMetric] = useState<TrendMetric>("hotness");
  const [trend30, setTrend30] = useState<MemeDetail["trend"] | null>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [videoTotal, setVideoTotal] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);

  const detail = useLoad(() => getDetail(id), [id]);
  const data = detail.data;

  // 视频列表单独拉一次：详情接口只带 4 条，而"到底有几条"只有视频接口知道
  useEffect(() => {
    if (!id) return undefined;
    let alive = true;
    setExpanded(false);
    setVideoError(null);
    getVideos(id, VIDEO_PAGE, 0)
      .then((page) => {
        if (!alive) return;
        setVideos(page.items);
        setVideoTotal(page.total);
      })
      .catch((error) => alive && setVideoError(describeError(error)));
    return () => {
      alive = false;
    };
  }, [id]);

  const loadMoreVideos = async () => {
    setLoadingMore(true);
    setVideoError(null);
    try {
      const page = await getVideos(id, VIDEO_PAGE, videos.length);
      const seen = new Set(videos.map((item) => item.bvid));
      setVideos((prev) => [...prev, ...page.items.filter((item) => !seen.has(item.bvid))]);
      setVideoTotal(page.total);
    } catch (error) {
      setVideoError(describeError(error));
    } finally {
      setLoadingMore(false);
    }
  };

  usePullDownRefresh(async () => {
    await detail.reload();
    Taro.stopPullDownRefresh();
  });

  // 分享标题走"人话问句"，不写"AI 智能分析"这类词
  const shareTitle = useRef("这个梗现在赶还来得及吗？");
  if (data?.meme) shareTitle.current = `「${data.meme.name}」现在赶还来得及吗？`;
  useShareAppMessage(() => ({ title: shareTitle.current, path: `/pages/detail/index?id=${id}` }));

  // 30 天曲线单独拉：详情接口只带 7 天，切到 30 天才补一次请求
  const switchMetric = (next: TrendMetric) => {
    setMetric(next);
    if (next !== "hotness" && !trend30 && id) {
      getTrend(id, 30).then(setTrend30, () => setTrend30(null));
    }
  };

  if (!id) {
    return (
      <View className="shell">
        <ErrorBlock message="这条梗的地址不太对，回梗库重新选一个吧。" />
      </View>
    );
  }

  const shownVideos = videos.length ? videos : (data?.videos ?? []);
  const points = metric === "hotness" ? (data?.trend.points ?? []) : (trend30?.points ?? data?.trend.points ?? []);

  return (
    <View className="shell">
      {detail.loading ? <LoadingBlock count={4} /> : null}
      {detail.error ? <ErrorBlock message={detail.error} onRetry={detail.reload} /> : null}

      {data ? (
        <View>
          <HeadCard
            detail={data}
            id={id}
            favorited={favorites.has(id)}
            onToggleFavorite={() => favorites.toggle({ id, name: data.meme.name })}
          />
          <IntroCard detail={data} />

          <View className="metrics">
            {METRICS.map((item) => {
              const block = data.metrics[item.key] as { value: number; growth: number | null };
              return (
                <View className="metric" key={item.key}>
                  <Text className="metric-label">{item.label}</Text>
                  <Text className="metric-value tabular">{compact(block.value)}</Text>
                  <Text className={`metric-growth tabular${isUp(block.growth) ? " up" : ""}`}>
                    {growthText(block.growth)}
                  </Text>
                </View>
              );
            })}
          </View>

          <View className="card">
            <View className="row-between">
              <Text className="sec-title">趋势</Text>
              <View className="seg">
                {(["hotness", "view", "discussion"] as TrendMetric[]).map((key) => (
                  <Text
                    key={key}
                    className={`seg-item${metric === key ? " seg-on" : ""}`}
                    onClick={() => switchMetric(key)}
                  >
                    {key === "hotness" ? "热度" : key === "view" ? "播放" : "讨论"}
                  </Text>
                ))}
              </View>
            </View>
            <TrendBars points={points} metric={metric} color={stageTone(data.meme.stage).color} />
          </View>

          <View className="card">
            <Text className="sec-title">生命周期</Text>
            <View className="stages">
              {data.lifecycle.stages.map((step) => (
                <View key={step.key} className={`stage${step.active ? " stage-on" : ""}`}>
                  <Text className="stage-emoji">{step.emoji}</Text>
                  <Text className="stage-label">{step.label}</Text>
                </View>
              ))}
            </View>
            {data.lifecycle.reasons.length ? (
              <View className="reasons">
                {data.lifecycle.reasons.map((reason) => (
                  <Text className="reason" key={reason}>· {reason}</Text>
                ))}
              </View>
            ) : null}
          </View>

          <View className="card">
            <View className="row-between">
              <Text className="sec-title">现在赶这个梗？</Text>
              <Text className={`chip ${catchTone(data.lifecycle.catch_up.status).chip}`}>
                {data.lifecycle.catch_up.label}
              </Text>
            </View>
            <Text className="catch-reason">
              {data.lifecycle.catch_up.reason || data.insight.algorithm_reason || "算法没有给出理由"}
            </Text>
            <Text className="faint catch-note">
              {confidenceText(data.lifecycle.catch_up.confidence)} · 状态由算法判定，AI 只复述不改判
            </Text>
          </View>

          <View className="card">
            <Text className="sec-title">相关视频（按播放量）</Text>
            {shownVideos.length ? (
              <View>
                {(expanded ? shownVideos : shownVideos.slice(0, VIDEO_TEASER)).map((video) => (
                  <VideoRow key={video.bvid} video={video} />
                ))}
                {!expanded && videoTotal > shownVideos.length ? (
                  <Text className="video-more" onClick={() => setExpanded(true)}>
                    展开全部 {videoTotal} 条（已加载 {shownVideos.length} 条）
                  </Text>
                ) : null}
                {expanded && shownVideos.length < videoTotal ? (
                  <Text className="video-more" onClick={loadMoreVideos}>
                    {loadingMore ? "加载中…" : `再加载 ${Math.min(VIDEO_PAGE, videoTotal - shownVideos.length)} 条`}
                  </Text>
                ) : null}
                {expanded && shownVideos.length >= videoTotal && videoTotal > VIDEO_TEASER ? (
                  <Text className="video-more" onClick={() => setExpanded(false)}>
                    收起
                  </Text>
                ) : null}
                <Text className="faint video-tip">点一条即可复制视频地址（小程序打不开站外链接）</Text>
              </View>
            ) : (
              <EmptyBlock
                title="还没有采信的视频"
                body={videoError || "这个梗的数据还在积累，或采集时被风控挡住了。"}
              />
            )}
          </View>

          <View className="card">
            <Text className="sec-title">这条数据怎么来的</Text>
            <Text className="cert-line">
              准入（并集）：梗百科为主、梗指南补充，任一 UP 主在最近 {data.certification.cert_window_days} 天里
              真实介绍过就进梗库；两位都介绍过的标「双 UP 认证」。
            </Text>
            <Text className="cert-line">
              这条：{data.certification.cert_label} ·{" "}
              {data.meme.verification_state === "verified_both"
                ? "已在两位 UP 主的真实投稿中命中"
                : data.meme.verification_state === "partially_verified"
                  ? `只在一位 UP 主的真实投稿中命中（${data.certification.certified_by.join("、") || "单 UP"}）`
                  : "未在线核验（B 站投稿接口被风控时无法核对）"}
            </Text>
            <Text className="faint cert-foot">
              {freshnessText(data.meme.data_updated_at?.slice(0, 10) ?? null, null)} · 口径详情见「口径」页
            </Text>
          </View>
        </View>
      ) : null}
    </View>
  );
}
