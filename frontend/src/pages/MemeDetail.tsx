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
import { useAsync } from "@/hooks/useAsync";
import { useFavorites, useMeta } from "@/hooks/useAppData";
import type { Certification, InsightBundle, IntroSource, MemeCard, MemeIntro, Trend as TrendData, VideoItem } from "@/types/api";
import { CATCH_STYLE, STAGE_STYLE } from "@/utils/format";

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
          <h1 className="text-[30px] font-black leading-tight">{meme.name}</h1>
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
            <span className="text-[24px] leading-none">🔥</span>
            <span className="tabular text-[34px] font-black leading-none">{Math.round(meme.hotness)}</span>
          </span>
          <span className={`chip ${stage.chip} px-3 py-1.5 text-[13px]`}>{meme.nickname}</span>
          <span className={`chip ${catchStyle.chip} px-3 py-1.5 text-[13px]`}>
            <span className={`h-1.5 w-1.5 rounded-full ${catchStyle.dot}`} />
            {bundle.catch_up.label}
          </span>
          {meme.meme_data_source === "bilibili" ? null : (
            <span
              className="chip bg-gold/20 px-2.5 py-1 text-[11px] text-[#B2750A]"
              title="这个梗的数据是演示数据，不是真实抓取结果"
            >
              演示数据
            </span>
          )}
          {meme.thumbnail.manual ? (
            <span className="chip bg-brand-soft px-2.5 py-1 text-[11px] text-brand" title="封面由人工在梗管理里指定，不是某条视频自带封面">
              人工封面
            </span>
          ) : null}
        </div>

        <p className="mt-4 text-[15px] leading-relaxed text-ink-mute">
          <span className="mr-1">🌟</span>
          {explanation || meme.catch_reason || "最近这个梗的数据还在积累中。"}
        </p>
      </div>
    </section>
  );
}

/** 介绍来源决定这句话说得多硬：人工写的可以直接信，证据拼出的只是原文摘录，没内容就明说。 */
const INTRO_STYLE: Record<IntroSource, { chip: string; hint: string }> = {
  manual: { chip: "bg-go/10 text-go", hint: "这条介绍是人工在梗管理里维护的" },
  transcript: {
    chip: "bg-flare/10 text-flare",
    hint: "还没有人工介绍，这段直接摘自解说视频的字幕原文，系统只挑句子、不写句子",
  },
  evidence: {
    chip: "bg-flare/10 text-flare",
    hint: "还没有人工介绍，这段由抓取到的解说视频标题与简介原文拼出，系统没有改写",
  },
  none: { chip: "bg-gold/20 text-[#B2750A]", hint: "既没有人工介绍，也没有可用的原文证据" },
};

/**
 * 字幕原文块：正文那几句从哪来的，得能当场核对。
 * source=transcript 时正文已经是这段摘录，所以只补出处与折叠原文；
 * 有人工介绍时它作为「对照」出现，让人看得见人工稿写的是不是视频里说过的话。
 */
function TranscriptBlock({ intro }: { intro: MemeIntro }) {
  const item = intro.transcript;
  if (!item) return null;
  const isSource = intro.source === "transcript";
  const who = [item.up_label, item.certified ? "" : "非认证视频"].filter(Boolean).join(" · ");
  return (
    <div className="mt-3 rounded-xl border border-dashed border-line bg-canvas px-4 py-3">
      <div className="text-[12px] font-bold text-ink-faint">
        {isSource ? "字幕原文" : "字幕原文对照"} · 来自《{item.video_title || item.bvid}》
        {who ? `（${who}）` : ""}
        <span title={item.kind_hint}> · {item.kind_label}</span>
      </div>

      {isSource ? null : (
        <p className="mt-1 text-[13px] leading-relaxed text-ink-mute">{item.excerpt}</p>
      )}

      {isSource && item.summary ? (
        <p
          className="mt-1 text-[12px] leading-relaxed text-ink-faint"
          title={`模型想加但原文没有的句子：${item.summary.invented.length} 条，已全部丢弃`}
        >
          AI 只做了挑选：从 {item.matched_sentences} 句相关原句里留了 {item.summary.sentences.length} 句
          （{item.summary.chars} 字），整句照抄、逐字核对；未缩短的摘录是 {item.excerpt_chars} 字。
        </p>
      ) : null}

      <details className="mt-1.5">
        <summary className="cursor-pointer list-none text-[12px] text-flare hover:underline">
          {item.full_truncated
            ? `展开字幕原文（共 ${item.chars} 字，这里放前 ${item.full.length} 字）`
            : `展开字幕原文（${item.chars} 字，挑了 ${item.matched_sentences} 句进介绍）`}
        </summary>
        <p className="mt-1.5 whitespace-pre-line text-[12px] leading-relaxed text-ink-mute">
          {item.full}
        </p>
      </details>

      <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[12px] text-ink-faint">
        {item.url ? (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-flare hover:underline"
          >
            <LinkIcon className="h-3 w-3" />
            看完整视频
          </a>
        ) : null}
        {item.fetched_at ? <span>字幕抓取于 {item.fetched_at}</span> : null}
      </div>
    </div>
  );
}

function IntroCard({ intro }: { intro: MemeIntro }) {
  const style = INTRO_STYLE[intro.source];
  return (
    <section id="intro" className="card p-5">
      <div className="mb-2 flex flex-wrap items-center gap-2.5">
        <span className="text-[20px]">📖</span>
        <h3 className="text-[18px] font-bold">这个梗是什么</h3>
        <span className={`chip px-2.5 py-1 text-[11px] ${style.chip}`} title={style.hint}>
          {intro.source_label}
        </span>
        {intro.evidence.length ? (
          <span className="ml-auto text-[12px] text-ink-faint">
            {intro.evidence.length} 位 UP 主介绍过
          </span>
        ) : null}
      </div>

      {intro.text ? (
        <p className="text-[15px] leading-relaxed text-ink-mute">{intro.text}</p>
      ) : (
        <p className="rounded-xl bg-rail px-4 py-3 text-[13px] leading-relaxed text-ink-faint">
          {intro.note}
          <Link to="/manage" className="ml-1 font-bold text-brand hover:underline">
            去梗管理补一条 →
          </Link>
        </p>
      )}

      {intro.transcript ? <TranscriptBlock intro={intro} /> : null}

      {intro.excerpt ? (
        <div className="mt-3 rounded-xl border border-dashed border-line bg-canvas px-4 py-3">
          <div className="text-[12px] font-bold text-ink-faint">
            简介原文摘录 · 来自《{intro.excerpt.video_title}》（UP：{intro.excerpt.author}）
            {intro.excerpt.data_source !== "bilibili" ? "（演示数据）" : ""}
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-mute">{intro.excerpt.text}</p>
        </div>
      ) : null}

      {intro.evidence.length ? (
        <ul className="mt-3 space-y-1.5">
          {intro.evidence.map((item) => (
            <li key={`${item.role}-${item.bvid}`} className="flex items-start gap-2 text-[12px]">
              <span className="chip shrink-0 bg-rail px-2 py-0.5 text-ink-mute">{item.up_label}</span>
              <span className="min-w-0 flex-1 text-ink-mute">
                {item.published_at ? `${item.published_at} · ` : ""}
                {item.video_url ? (
                  <a
                    href={item.video_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-flare hover:underline"
                  >
                    <LinkIcon className="h-3 w-3" />
                    <span className="truncate">{item.video_title}</span>
                  </a>
                ) : (
                  // 演示/未核验的证据不给链接，点进去会是 404
                  <span className="text-ink-faint" title="这条证据不是真实抓取到的投稿，没有可点开的链接">
                    {item.video_title}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function CertificationStrip({
  certification,
  verification,
}: {
  certification: Certification;
  verification: string;
}) {
  const sides = [
    { key: "encyclopedia", label: "梗百科", side: certification.encyclopedia },
    { key: "guide", label: "梗指南", side: certification.guide },
  ];
  const stateText =
    verification === "verified_both"
      ? "已在线核验"
      : verification === "partially_verified"
        ? `${certification.certified_by[0] ?? "单 UP"}已核验`
        : "未在线核验";
  const stateTitle =
    verification === "verified_both"
      ? "已在两位 UP 主的真实投稿中命中"
      : verification === "partially_verified"
        ? `只在一位 UP 主的真实投稿中命中（另一位没做过或被风控挡住）：${certification.certified_by.join("、")}`
        : "梗库里的认证位来自人工整理；B 站投稿接口被风控时无法在线核验";
  return (
    <section className="card p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-[19px]">✅</span>
        <h3 className="text-[18px] font-bold">双 UP 梗认证</h3>
        <span
          className={`chip ml-auto ${
            verification === "verified_both"
              ? "bg-go/10 text-go"
              : verification === "partially_verified"
                ? "bg-flare/10 text-flare"
                : "bg-gold/20 text-[#B2750A]"
          }`}
          title={stateTitle}
        >
          {stateText}
        </span>
        <span
          className={`chip ${certification.certified ? "bg-go/10 text-go" : "bg-rail text-ink-mute"}`}
          title={
            certification.certified
              ? "两位 UP 主都独立介绍过"
              : `发现层按并集准入：任一 UP 主在 ${certification.cert_window_days} 天内介绍过即入池；这条只有 ${certification.certified_by.join("、") || "没有"} 的证据`
          }
        >
          {certification.cert_label}
        </span>
      </div>
      <p className="mb-3 text-[12px] leading-relaxed text-ink-mute">
        准入看并集：梗百科为主、梗指南补充，任一 UP 主在最近 {certification.cert_window_days} 天里真实介绍过就进梗库；
        两位都独立介绍过的标「双 UP 认证」，只有一位的会写明是哪一位。
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
              <div className="truncate text-[12px] text-ink-mute">{side.video_title || "没有介绍过这个梗"}</div>
              {side.linkable && side.video_url ? (
                <a
                  href={side.video_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-flare hover:underline"
                >
                  <LinkIcon size={12} />
                  {side.bvid}
                </a>
              ) : (
                <span className="text-[11px] text-ink-faint">
                  {side.video_title || (certification.admitted ? "未在该 UP 主的投稿中找到" : "未在线核验到该 UP 主的对应投稿")}
                </span>
              )}
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
        <span className="text-[19px]">👥</span>
        <h3 className="text-[18px] font-bold">参与 UP 主</h3>
      </div>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="tabular text-[30px] font-black">{creators.value.toLocaleString("en-US")}</span>
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
  // 相关视频两档排法：B 站搜这个词的默认（综合）顺序 vs 播放量
  const [videoSort, setVideoSort] = useState<"rank" | "view">("rank");
  // 后端会不会真按默认排序给：没抓到名次的梗会退回播放量，界面必须当场说，
  // 否则点「B站默认排序」列表纹丝不动，看起来就是按钮坏了
  const [videoSortState, setVideoSortState] = useState<{ applied: string; label: string; note: string }>({
    applied: "rank",
    label: "B站默认排序",
    note: "",
  });

  useEffect(() => {
    if (!valid) return;
    let alive = true;
    Promise.all([api.memeTrend(memeId, 30), api.memeVideos(memeId, 3, videoSort)])
      .then(([trend, videoList]) => {
        if (!alive) return;
        setTrend30(trend);
        setVideos(videoList.items);
        setVideoSortState({
          applied: videoList.sort_applied || videoSort,
          label: videoList.sort_label || "",
          note: videoList.note || "",
        });
      })
      .catch(() => {
        if (!alive) return;
        setTrend30(null);
        setVideos(null);
      });
    return () => {
      alive = false;
    };
  }, [memeId, valid, videoSort]);

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

  // 断口要如实说明：B站搜索会随机把有内容的日子返回成空壳，那不是"当天没人做"
  const holes = points.filter((point) => point.observed === false).length;

  const shownVideos = videos ?? detail.data?.videos ?? [];
  const memeThumbnail = detail.data?.meme.thumbnail ?? { emoji: "🎬", color: "#FFE9E4" };

  const explanationText =
    bundle.trend_explanation?.available && bundle.trend_explanation.result?.text
      ? bundle.trend_explanation.result.text
      : (detail.data?.meme.catch_reason ?? null);

  if (!valid) {
    return (
      <>
        <div className="px-5 py-8 lg:px-[33px]">
          <ErrorState message="这个梗的地址不太对" />
        </div>
      </>
    );
  }

  return (
    <div className="px-5 pb-12 pt-7 lg:px-[33px]">
      <div className="min-w-0 space-y-5">
          {detail.loading ? <LoadingCards count={3} /> : null}

          {detail.error ? <ErrorState message={detail.error} onRetry={detail.reload} /> : null}

          {detail.data ? (
            <>
              <HeadCard meme={detail.data.meme} bundle={bundle} explanation={explanationText} />

              <IntroCard intro={detail.data.intro} />

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard kind="videos" label="视频数" metric={detail.data.metrics.videos} />
                <MetricCard kind="creators" label="参与UP主" metric={detail.data.metrics.creators} />
                <MetricCard kind="comments" label="评论" metric={detail.data.metrics.comments} />
                <MetricCard kind="danmaku" label="弹幕" metric={detail.data.metrics.danmaku} />
              </div>

              <div className="grid gap-5 xl:grid-cols-[1.55fr_1fr]">
                <section id="trend" className="card p-5">
                  <div className="mb-3 flex items-center gap-3">
                    <span className="text-[20px]">🔥</span>
                    <h3 className="text-[18px] font-bold">热度趋势</h3>
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
                  {holes > 0 ? (
                    <p className="mt-1 text-[11px] leading-relaxed text-brand">
                      这 {points.length} 天里有 {holes} 天接口没返回结果（图上画成断口，不当成 0）——
                      B 站搜索对同一天会随机给空结果，观测不足时算法拒绝给"在涨还是在退"的结论。
                    </p>
                  ) : null}
                </section>

                <LifecycleTrack lifecycle={detail.data.lifecycle} />
              </div>

              <CatchUpCards bundle={bundle} onRetry={regenerate} generating={generating} />

              <section id="videos">
                <div className="mb-1 flex flex-wrap items-end justify-between gap-3">
                  <h2 className="section-title">
                    <span className="grid h-[22px] w-[22px] place-items-center rounded-full bg-flare text-[10px] text-white">
                      <PlayIcon size={13} />
                    </span>
                    相关视频
                  </h2>
                  <div className="flex items-center gap-3">
                    <div className="flex rounded-full bg-rail p-1">
                      {([
                        { key: "rank", label: "B站默认排序" },
                        { key: "view", label: "播放量" },
                      ] as const).map((item) => {
                        // 请求了默认排序却被后端退回播放量 = 这个梗一条名次都没抓到
                        // 只有"我们要了默认排序、后端却没给"才叫排不出来：
                        // 用户主动切到播放量时 applied 本来就是 view，不能反过来把默认档标成坏的
                        const starved =
                          item.key === "rank" && videoSort === "rank" && videoSortState.applied !== "rank";
                        return (
                          <button
                            key={item.key}
                            type="button"
                            onClick={() => setVideoSort(item.key)}
                            title={
                              starved
                                ? "这条梗还没抓到 B 站综合排序的名次，这一档暂时排不出来（补一名次后会生效）"
                                : item.key === "rank"
                                  ? "按你在 B 站搜这个词看到的默认（综合）顺序排"
                                  : "按播放量从高到低排"
                            }
                            className={[
                              "rounded-full px-3.5 py-1 text-[12px] font-semibold transition",
                              starved
                                ? "text-ink-faint line-through decoration-ink-faint/60"
                                : videoSort === item.key
                                  ? "bg-flare text-white shadow-sm"
                                  : "text-ink-mute hover:text-ink",
                            ].join(" ")}
                          >
                            {item.label}
                            {starved ? "（暂无名次）" : ""}
                          </button>
                        );
                      })}
                    </div>
                    <Link to="/library" className="link-quiet">
                      查看梗库
                      <ArrowRightIcon size={15} />
                    </Link>
                  </div>
                </div>
                <p className="mb-4 text-[12px] text-ink-faint">
                  当前顺序：{videoSortState.label}
                  {videoSortState.note ? ` · ${videoSortState.note}` : ""}
                </p>
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
                <CertificationStrip
                  certification={detail.data.certification}
                  verification={detail.data.meme.verification_state}
                />
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
  );
}
