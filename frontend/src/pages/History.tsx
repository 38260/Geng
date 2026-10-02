import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { SectionHeader, TransparencyFooter } from "@/components/Sections";
import { StickerThumb } from "@/components/StickerThumb";
import { EmptyState, ErrorState, LoadingCards } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import { useMeta } from "@/hooks/useAppData";
import type { CycleType, HistoryItem, HistoryView, LifecycleStage } from "@/types/api";
import { STAGE_STYLE, compact, percent } from "@/utils/format";

const CYCLE_TONE: Record<CycleType, { chip: string; text: string }> = {
  rising: { chip: "bg-flare-soft text-flare", text: "text-flare" },
  pulse: { chip: "bg-brand-soft text-brand", text: "text-brand" },
  long_tail: { chip: "bg-dusk-soft text-dusk", text: "text-dusk" },
  no_data: { chip: "bg-ink-faint/15 text-ink-mute", text: "text-ink-mute" },
};

const SORTS = [
  { key: "recent", label: "最近入池" },
  { key: "peak", label: "峰值热度" },
  { key: "hotness", label: "当前热度" },
  { key: "off_peak", label: "距峰最远" },
];

/** 阶段 → 颜色图例（轨迹条按**当天**的阶段着色，不是按当前阶段）。 */
const LEGEND: { stage: LifecycleStage; label: string }[] = [
  { stage: "sprouting", label: "萌芽" },
  { stage: "rising", label: "上升" },
  { stage: "explosive", label: "爆发" },
  { stage: "plateau", label: "平稳" },
  { stage: "receding", label: "退潮" },
  { stage: "obsolete", label: "过气" },
];

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card px-4 py-3.5">
      <div className="text-[13px] font-medium text-ink-mute">{label}</div>
      <div className="tabular mt-1 text-[26px] font-black leading-none text-ink">{value}</div>
      {hint ? <div className="mt-1.5 text-[12px] leading-snug text-ink-faint">{hint}</div> : null}
    </div>
  );
}

/**
 * 逐日轨迹：一格一天，高度=当天热度，颜色=当天阶段。
 *
 * 没观测到的那天画成一条浅色空档——它表示"接口那天没给我们数据"，
 * 跟"那天真的没人做这个梗"不是一回事，所以绝不许画成热度 0 的柱子。
 */
function Spark({ item }: { item: HistoryItem }) {
  const points = item.spark;
  const max = Math.max(1, ...points.map((point) => point.hotness));
  const peakIndex = points.findIndex((point) => point.date === item.peak_date);
  if (!points.length) {
    return <div className="grid h-[58px] place-items-center rounded-tile bg-rail text-[13px] text-ink-faint">库里还没有这个梗的逐日序列</div>;
  }
  if (points.length < 3) {
    return (
      <div className="grid h-[58px] place-items-center rounded-tile bg-rail text-[13px] text-ink-faint">
        才入池 {points.length} 天，还画不出轨迹
      </div>
    );
  }
  return (
    <div className="relative">
      <div className="flex h-[58px] items-end gap-[2px]">
        {points.map((point) => {
          if (!point.observed) {
            return (
              <div
                key={point.date}
                title={`${point.date}｜这天接口没给数据（未观测，不当零活动）`}
                className="h-[3px] flex-1 rounded-[2px] bg-line"
              />
            );
          }
          const height = point.hotness > 0 ? Math.max(6, (point.hotness / max) * 100) : 0;
          if (height === 0) {
            return (
              <div
                key={point.date}
                title={`${point.date}｜观测到了，但当天没有相关内容`}
                className="h-[3px] flex-1 rounded-[2px] bg-ink-faint/40"
              />
            );
          }
          return (
            <div
              key={point.date}
              title={`${point.date}｜热度 ${point.hotness}（${point.stage}）`}
              className={`flex-1 rounded-[2px] ${STAGE_STYLE[point.stage].dot}`}
              style={{ height: `${height}%` }}
            />
          );
        })}
      </div>
      {peakIndex >= 0 ? (
        <span
          aria-hidden
          className="pointer-events-none absolute -top-1.5 bottom-0 w-[2px] rounded-full bg-ink/25"
          style={{ left: `calc(${((peakIndex + 0.5) / points.length) * 100}% - 1px)` }}
        />
      ) : null}
      <div className="mt-1.5 flex justify-between text-[12px] text-ink-faint">
        <span>{points[0].date.slice(5)}</span>
        {item.peak_date ? <span className="text-ink-mute">峰 {item.peak_date.slice(5)}</span> : null}
        <span>{points[points.length - 1].date.slice(5)}</span>
      </div>
    </div>
  );
}

function CycleRow({ item }: { item: HistoryItem }) {
  const tone = CYCLE_TONE[item.cycle];
  return (
    <article className="card card-hover p-4 lg:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* 左：是谁 */}
        <div className="flex min-w-0 items-center gap-3 lg:w-[232px] lg:shrink-0">
          <StickerThumb thumbnail={item.thumbnail} ratio="1/1" emojiSize={20} className="w-[46px] shrink-0" rounded="rounded-tile" />
          <div className="min-w-0">
            <Link to={`/meme/${item.id}`} className="block truncate text-[17px] font-bold text-ink hover:text-flare">
              {item.name}
            </Link>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-ink-mute">
              <span className="chip bg-rail px-2 py-[3px] text-[12px]">{item.cert_label}</span>
              <span>入池 {(item.admitted_at ?? "—").slice(0, 10)}</span>
            </div>
            <div className="mt-1 text-[12px] text-ink-faint">
              观测 {item.observed_days}/{item.window_days} 天
              {item.truncated ? " · 周期左端被截断" : ""}
            </div>
          </div>
        </div>

        {/* 中：轨迹 */}
        <div className="min-w-0 flex-1">
          <Spark item={item} />
        </div>

        {/* 右：周期画像 */}
        <div className="lg:w-[300px] lg:shrink-0">
          <div className="flex items-center gap-2">
            <span className={`chip ${tone.chip}`}>
              {item.cycle_emoji} {item.cycle_label}
            </span>
            <span className={`chip ${STAGE_STYLE[item.stage].chip}`}>{item.stage_label}</span>
          </div>
          <dl className="mt-2.5 grid grid-cols-3 gap-x-3 gap-y-1.5 text-[13px] lg:grid-cols-3">
            <div>
              <dt className="text-ink-faint">峰值</dt>
              <dd className="tabular font-bold text-ink">
                {item.peak_hotness || "—"}
                <span className="ml-1 text-[12px] font-normal text-ink-faint">
                  {item.peak_date ? item.peak_date.slice(5) : ""}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-ink-faint">当前</dt>
              <dd className="tabular font-bold text-ink">{item.current_hotness}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">距峰</dt>
              <dd className="tabular font-bold text-ink">
                {item.days_since_peak === null ? "—" : `${item.days_since_peak}天`}
              </dd>
            </div>
            <div>
              <dt className="text-ink-faint">半衰期</dt>
              <dd className="tabular font-bold text-ink">
                {item.half_life_days === null ? (item.cycle === "no_data" ? "—" : "未腰斩") : `${item.half_life_days}天`}
              </dd>
            </div>
            <div>
              <dt className="text-ink-faint">爬升</dt>
              <dd className="tabular font-bold text-ink">
                {item.rise_days === null ? "—" : `${item.rise_days}天`}
              </dd>
            </div>
            <div>
              <dt className="text-ink-faint">离开峰值</dt>
              <dd className="tabular font-bold text-ink">{percent(item.off_peak * 100)}</dd>
            </div>
          </dl>
          <div className="mt-2 text-[12px] text-ink-faint">
            窗口内头部播放 {compact(item.window_view)} · 讨论 {compact(item.window_discussion)}
          </div>
        </div>
      </div>
    </article>
  );
}

/** 梗史馆：不复述"今天玩什么"，只回答"这些梗后来怎么了"。 */
export default function History() {
  const [cycle, setCycle] = useState<"" | CycleType>("");
  const [cert, setCert] = useState<"" | "double" | "single">("");
  const [sort, setSort] = useState("recent");
  const { meta } = useMeta();
  const { data, loading, error, reload } = useAsync<HistoryView>(
    () => api.history({ days: 90, cycle, cert, sort }),
    [cycle, cert, sort],
  );

  const items = useMemo(() => data?.items ?? [], [data]);
  const summary = data?.summary;

  return (
    <div className="px-5 pb-12 pt-8 lg:px-[33px]">
      <SectionHeader emoji="📼" title="梗史馆" />
      <p className="-mt-2 mb-6 max-w-[880px] text-[15px] leading-relaxed text-ink-mute">
        把最近 90 天里被梗百科 / 梗指南介绍过的梗搬进来，摊开它们的热度轨迹与周期：
        谁还在爬、谁已经过峰、谁是一闪而过的脉冲。这里不做预测，只做复盘——
        所有数字都由算法从逐日序列算出，模型不参与。
      </p>

      {loading ? (
        <LoadingCards count={5} />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !summary ? null : (
        <>
          {/* 概览 */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            <Stat
              label="近 90 天入池"
              value={`${summary.pool}`}
              hint={`本页列出 ${summary.returned} 只 · 排序：${data?.sort_label ?? ""}`}
            />
            <Stat
              label="峰值最高"
              value={summary.peak_leader ? `${summary.peak_leader.peak_hotness}` : "—"}
              hint={summary.peak_leader ? `${summary.peak_leader.name}（${summary.peak_leader.peak_date?.slice(5)}）` : "还没有可比的峰值"}
            />
            <Stat
              label="距峰天数（中位）"
              value={summary.median_days_since_peak === null ? "—" : `${summary.median_days_since_peak}天`}
              hint="越大说明越多梗已经离开自己的高点"
            />
            <Stat
              label="平均爬升"
              value={summary.avg_rise_days === null ? "—" : `${summary.avg_rise_days}天`}
              hint="从开始有内容到冲上峰值用掉的天数"
            />
            <Stat
              label="平均半衰期"
              value={summary.avg_half_life_days === null ? "—" : `${summary.avg_half_life_days}天`}
              hint="见峰后跌到一半所需天数，只统计已腰斩的"
            />
          </div>

          {/* 口径自解释：观测窗有多长、多少梗的左端被截断，都必须写在页面上 */}
          <div className="mt-3 rounded-tile border border-line bg-rail px-4 py-3 text-[13px] leading-relaxed text-ink-mute">
            <span className="font-bold text-ink-soft">观测窗 {summary.obs_from} ~ {summary.obs_to}</span>
            （{summary.window_days} 天）
            {summary.truncated_count > 0 ? (
              <>
                ，其中 <span className="font-bold text-ink-soft">{summary.truncated_count}</span> 只入池日早于观测窗起点，
                它们的周期左端被截断——爬升天数与半衰期可能被低估。轨迹条里的
                <span className="mx-1 inline-block h-[3px] w-4 translate-y-[-2px] rounded-[2px] bg-line align-middle" />
                是接口当天没给数据的空档，不当作"当天没人做"。
              </>
            ) : null}
            {summary.obs_to && meta?.data_through ? `　统计截至 ${meta.data_through.slice(0, 10)}。` : null}
          </div>

          {/* 周期分布 = 筛选入口：计数与点进去的条数取自同一个集合 */}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setCycle("")}
              className={`chip transition ${cycle === "" ? "bg-nav text-white" : "bg-rail text-ink hover:bg-nav-soft"}`}
            >
              全部 {summary.returned}
            </button>
            {summary.by_cycle.map((option) => (
              <button
                key={option.key}
                type="button"
                title={option.hint}
                onClick={() => setCycle(option.key)}
                disabled={option.count === 0}
                className={`chip transition ${cycle === option.key ? "bg-nav text-white" : "bg-rail text-ink hover:bg-nav-soft"} ${option.count === 0 ? "cursor-not-allowed opacity-45" : ""}`}
              >
                {option.emoji} {option.label} {option.count}
              </button>
            ))}
            <span className="mx-1 h-5 w-px bg-line" />
            {([
              { key: "", label: "不限认证" },
              { key: "double", label: "双 UP 认证" },
              { key: "single", label: "单 UP" },
            ] as const).map((option) => (
              <button
                key={option.key || "any"}
                type="button"
                onClick={() => setCert(option.key)}
                className={`chip transition ${cert === option.key ? "bg-flare text-white" : "bg-rail text-ink hover:bg-nav-soft"}`}
              >
                {option.label}
              </button>
            ))}
            <span className="ml-auto flex items-center gap-1 text-[13px] text-ink-mute">
              排序
              {SORTS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setSort(option.key)}
                  className={`rounded-full px-2.5 py-1.5 font-semibold transition ${sort === option.key ? "bg-nav-soft text-nav" : "text-ink-mute hover:bg-rail"}`}
                >
                  {option.label}
                </button>
              ))}
            </span>
          </div>

          {/* 阶段色图例 */}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-ink-faint">
            <span>轨迹条按当天的阶段着色：</span>
            {LEGEND.map((entry) => (
              <span key={entry.stage} className="flex items-center gap-1.5">
                <span className={`inline-block h-2.5 w-2.5 rounded-[3px] ${STAGE_STYLE[entry.stage].dot}`} />
                {entry.label}
              </span>
            ))}
          </div>

          <div className="mt-4 flex flex-col gap-3">
            {items.length === 0 ? (
              <EmptyState
                title="这个筛选下没有梗"
                description="换一个周期类型，或者把认证筛选放宽到「不限认证」。"
              />
            ) : (
              items.map((item) => <CycleRow key={item.id} item={item} />)
            )}
          </div>

          <p className="mt-6 max-w-[880px] text-[13px] leading-relaxed text-ink-faint">
            {data?.rule}
          </p>
        </>
      )}

      <TransparencyFooter meta={meta} />
    </div>
  );
}
