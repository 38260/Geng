import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { MetricCard, VideoCard } from "@/components/Cards";
import { CatchUpCards } from "@/components/CatchUpStatus";
import { ArrowRightIcon, LinkIcon, PlayIcon } from "@/components/icons";
import { LifecycleTrack } from "@/components/Lifecycle";
import { StickerThumb } from "@/components/StickerThumb";
import { TrendChart } from "@/components/TrendChart";
import { ErrorState, LoadingCards } from "@/components/States";
import { TransparencyFooter } from "@/components/Sections";
import { DetailTopBar } from "@/components/Header";
import { useAsync } from "@/hooks/useAsync";
import { useFavorites, useMeta } from "@/hooks/useAppData";
import type { Certification, InsightBundle, MemeCard, Trend as TrendData, VideoItem } from "@/types/api";
import { CATCH_STYLE, STAGE_STYLE } from "@/utils/format";

const SECTIONS = [
  { id: "overview", label: "概览", emoji: "🏠" },
  { id: "trend", label: "趋势图", emoji: "📊" },
  { id: "videos", label: "相关视频", emoji: "▶" },
  { id: "creators", label: "参与UP主", emoji: "👥" },
];

const EMPTY_BUNDLE: InsightBundle = {
  trend_explanation: null,
  catch_up_advice: null,
  algorithm_reason: "",
  catch_up: { status: "caution", label: "慎赶", confidence: 0, decided_by: "algorithm" },
};

function HeadCard({
  meme,
  bundle,
  explanation,
}: {
  meme: MemeCard;
  bundle: InsightBundle;
  explanation: string | null;
}) {
  const { ids, toggle } = useFavorites();
  const stage = STAGE_STYLE[meme.stage];
  const catchStyle = CATCH_STYLE[bundle.catch_up.status];

  return (
    <section id="overview" className="card flex flex-col gap-5 p-5 sm:flex-row">
      <StickerThumb
        thumbnail={meme.thumbnail}
        ratio="1/1"
        emojiSize={62}
        className="w-[128px] shrink-0 sm:w-[146px]"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-[26px] font-black leading-tight">{meme.name}</h1>
          <button
            type="button"
            onClick={() => toggle(meme.id, meme.name)}
            className="btn-ghost rounded-full px-3 py-1 text-[12px]"
          >
            {ids.has(meme.id) ? "已收藏 ⭐" : "收藏这个梗"}
          </button>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-2.5">
          <span className="flex items-center gap-1 text-brand">
            <span className="text-[19px] leading-none">🔥</span>
            <span className="tabular text-[30px] font-black leading-none">{Math.round(meme.hotness)}</span>
          </span>
          <span className={`chip ${stage.chip} px-3 py-1.5 text-[13px]`}>{meme.nickname}</span>
          <span className={`chip ${catchStyle.chip} px-3 py-1.5 text-[13px]`}>
            <span className={`h-1.5 w-1.5 rounded-full ${catchStyle.dot}`} />
            {bundle.catch_up.label}
          </span>
          <span
            className={`chip px-2.5 py-1 text-[11px] ${
              meme.meme_data_source === "bilibili" ? "bg-flare/10 text-flare" : "bg-gold/20 text-[#B2750A]"
            }`}
            title={
              meme.meme_data_source === "bilibili"
                ? "这个梗的数据来自 B 站真实采集"
                : "这个梗的数据是演示数据，不是真实抓取结果"
            }
          >
            {meme.meme_data_source === "bilibili" ? "B站真实数据" : "演示数据"}
          </span>
        </div>

        <p className="mt-3 text-[13px] leading-relaxed text-ink-mute">
          <span className="mr-1">👋</span>
          {explanation || meme.catch_reason || "最近这个梗的数据还在积累中。"}
        </p>
        <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed text-ink-faint">{meme.description}</p>
      </div>
    </section>
  );
}

function CertificationStrip({ certification }: { certification: Certification }) {
  const sides = [
    { key: "encyclopedia", label: "梗百科", side: certification.encyclopedia },
    { key: "guide", label: "梗指南", side: certification.guide },
  ];
  return (
    <section className="card p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-[16px]">✅</span>
        <h3 className="text-[15px] font-bold">双 UP 梗认证</h3>
        <span className="chip ml-auto bg-go/10 text-go">
          {certification.certified ? "已进入正式梗库" : "候选，未进入分析"}
        </span>
      </div>
      <p className="mb-3 text-[12px] leading-relaxed text-ink-mute">
        只有 梗百科 与 梗指南 都独立发视频介绍过的梗，才会进入正式梗库参与热度与生命周期分析。
      </p>
      <ul className="space-y-2">
        {sides.map(({ key, label, side }) => (
          <li key={key} className="flex items-start gap-2.5 rounded-xl bg-rail px-3 py-2.5">
            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${side.confirmed ? "bg-go" : "bg-ink-faint"}`} />
            <div className="min-w-0">
              <div className="text-[13px] font-semibold">
                {label}
                <span className="ml-1.5 text-[11px] font-normal text-ink-faint">@{side.up_name}</span>
              </div>
              <div className="truncate text-[12px] text-ink-mute">{side.video_title || "尚未发布介绍视频"}</div>
              {side.video_url ? (
                <a
                  href={side.video_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-flare hover:underline"
                >
                  <LinkIcon size={12} />
                  {side.bvid}
                </a>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CreatorsStrip({
  creators,
  windowDays,
  note,
  tone,
}: {
  creators: { value: number; growth: number | null };
  windowDays: number;
  note: string;
  tone: string;
}) {
  return (
    <section id="creators" className="card p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-[16px]">👥</span>
        <h3 className="text-[15px] font-bold">参与 UP 主</h3>
      </div>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="tabular text-[26px] font-black">{creators.value.toLocaleString("en-US")}</span>
        <span className={`tabular text-[13px] font-bold ${tone}`}>
          {creators.growth === null
            ? "样本不足"
            : `${creators.growth > 0 ? "+" : ""}${creators.growth.toFixed(0)}%`}
        </span>
        <span className="text-[12px] text-ink-faint">近 {windowDays} 天</span>
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-ink-mute">{note}。</p>
      <Link to="/trends" className="link-quiet mt-3">
        看它在所有梗里的位置
        <ArrowRightIcon size={14} />
      </Link>
    </section>
  );
}

export default function MemeDetail() {
  const { id } = useParams();
  const memeId = Number(id);
  const { meta } = useMeta();
  const valid = Number.isFinite(memeId) && memeId > 0;

  const detail = useAsync(() => api.memeDetail(memeId), [memeId]);
  const [trendWindow, setTrendWindow] = useState<7 | 30>(7);
  const [trend30, setTrend30] = useState<TrendData | null>(null);
  const [videos, setVideos] = useState<VideoItem[] | null>(null);

  useEffect(() => {
    if (!valid) return;
    let alive = true;
    Promise.all([api.memeTrend(memeId, 30), api.memeVideos(memeId, 3)])
      .then(([trend, videoList]) => {
        if (!alive) return;
        setTrend30(trend);
        setVideos(videoList.items);
      })
      .catch(() => {
        if (!alive) return;
        setTrend30(null);
        setVideos(null);
      });
    return () => {
      alive = false;
    };
  }, [memeId, valid]);

  const bundle = detail.data?.insight ?? EMPTY_BUNDLE;

  const regenerate = useCallback(async () => {
    const next = await api.regenerateInsight(memeId, true);
    if (detail.data) {
      detail.setData({ ...detail.data, insight: { ...detail.data.insight, ...next } });
    }
  }, [memeId, detail]);

  // AI 文案不在详情接口里生成（会拖慢首屏），进页面后单独补一次
  const [generating, setGenerating] = useState(false);
  useEffect(() => {
    const insight = detail.data?.insight;
    if (!insight) return;
    if (insight.trend_explanation && insight.catch_up_advice) return;
    let alive = true;
    setGenerating(true);
    api
      .regenerateInsight(memeId, false)
      .then((next) => {
        if (!alive || !detail.data) return;
        detail.setData({ ...detail.data, insight: { ...detail.data.insight, ...next } });
      })
      .catch(() => {
        /* AI 生成失败不影响页面，卡片自己会显示降级说明 */
      })
      .finally(() => alive && setGenerating(false));
    return () => {
      alive = false;
    };
  }, [detail.data, memeId]);

  const points = useMemo(() => {
    const source = trend30?.points?.length ? trend30.points : (detail.data?.trend.points ?? []);
    return trendWindow === 7 ? source.slice(-7) : source;
  }, [trend30, detail.data, trendWindow]);

  const shownVideos = videos ?? detail.data?.videos ?? [];
  const memeThumbnail = detail.data?.meme.thumbnail ?? { emoji: "🎬", color: "#FFE9E4" };

  const explanationText =
    bundle.trend_explanation?.available && bundle.trend_explanation.result?.text
      ? bundle.trend_explanation.result.text
      : (detail.data?.meme.catch_reason ?? null);

  if (!valid) {
    return (
      <>
        <DetailTopBar />
        <div className="mx-auto w-full max-w-[1180px] px-4 py-8">
          <ErrorState message="这个梗的地址不太对" />
        </div>
      </>
    );
  }

  return (
    <>
      <DetailTopBar updatedAt={detail.data?.meme.data_updated_at ?? meta?.data_updated_at} />

      <div className="mx-auto flex w-full max-w-[1180px] gap-6 px-4 pb-10 pt-5 lg:px-7">
        <nav className="sticky top-[86px] hidden h-fit w-[124px] shrink-0 flex-col gap-1 xl:flex">
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className="flex items-center gap-2 rounded-xl px-3 py-2 text-[13px] font-medium text-ink-soft transition hover:bg-white hover:text-flare"
            >
              <span>{section.emoji}</span>
              {section.label}
            </a>
          ))}
        </nav>

        <div className="min-w-0 flex-1 space-y-5">
          {detail.loading ? <LoadingCards count={3} /> : null}

          {detail.error ? <ErrorState message={detail.error} onRetry={detail.reload} /> : null}

          {detail.data ? (
            <>
              <HeadCard meme={detail.data.meme} bundle={bundle} explanation={explanationText} />

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard kind="videos" label="视频数" metric={detail.data.metrics.videos} />
                <MetricCard kind="creators" label="参与UP主" metric={detail.data.metrics.creators} />
                <MetricCard kind="comments" label="评论" metric={detail.data.metrics.comments} />
                <MetricCard kind="danmaku" label="弹幕" metric={detail.data.metrics.danmaku} />
              </div>

              <div className="grid gap-5 xl:grid-cols-[1.55fr_1fr]">
                <section id="trend" className="card p-5">
                  <div className="mb-3 flex items-center gap-3">
                    <span className="text-[17px]">🔥</span>
                    <h3 className="text-[15px] font-bold">热度趋势</h3>
                    <div className="ml-auto flex rounded-full bg-rail p-1">
                      {([7, 30] as const).map((size) => (
                        <button
                          key={size}
                          type="button"
                          onClick={() => setTrendWindow(size)}
                          className={[
                            "rounded-full px-3.5 py-1 text-[12px] font-semibold transition",
                            trendWindow === size ? "bg-flare text-white shadow-sm" : "text-ink-mute hover:text-ink",
                          ].join(" ")}
                        >
                          {size}天
                        </button>
                      ))}
                    </div>
                  </div>
                  <TrendChart points={points} />
                  <p className="mt-2 text-[11px] text-ink-faint">
                    热度为 0-100 自定义指数（滚动 7 天窗口），不是 B 站官方指数。
                  </p>
                </section>

                <LifecycleTrack lifecycle={detail.data.lifecycle} />
              </div>

              <CatchUpCards bundle={bundle} onRetry={regenerate} generating={generating} />

              <section id="videos">
                <div className="mb-4 flex items-end justify-between">
                  <h2 className="section-title">
                    <span className="grid h-[22px] w-[22px] place-items-center rounded-full bg-flare text-[10px] text-white">
                      <PlayIcon size={13} />
                    </span>
                    相关视频
                  </h2>
                  <Link to="/library" className="link-quiet">
                    查看梗库
                    <ArrowRightIcon size={15} />
                  </Link>
                </div>
                {shownVideos.length ? (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {shownVideos.map((video) => (
                      <VideoCard key={video.bvid} video={video} thumbnail={memeThumbnail} />
                    ))}
                  </div>
                ) : (
                  <p className="rounded-card border border-dashed border-line p-6 text-[13px] text-ink-mute">
                    这个梗还没有通过相关性过滤的视频样本。
                  </p>
                )}
              </section>

              <div className="grid gap-5 xl:grid-cols-2">
                <CertificationStrip certification={detail.data.certification} />
                <CreatorsStrip
                  creators={detail.data.metrics.creators}
                  windowDays={detail.data.metrics.window_days}
                  note={detail.data.metrics.note}
                  tone={CATCH_STYLE[bundle.catch_up.status].text}
                />
              </div>
            </>
          ) : null}

          <TransparencyFooter meta={meta} />
        </div>
      </div>
    </>
  );
}
