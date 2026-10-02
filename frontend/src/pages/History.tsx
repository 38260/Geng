import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { ArrowRightIcon } from "@/components/icons";
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
  // 悬停高亮：原生 title 要停一两秒才弹、也没法高亮，柱子又挨得这么密，
  // 弹出来也对不上是哪天。自己做一个即时浮层，并把其余柱子压暗。
  const [hover, setHover] = useState<number | null>(null);
  const { meta } = useMeta();
  const stageText = useMemo(() => {
    const rows = meta?.lifecycle_stages ?? [];
    return new Map(rows.map((row) => [row.key as string, row.label]));
  }, [meta]);
  const active = hover === null ? null : points[hover] ?? null;
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
        {points.map((point, index) => {
          // 鼠标扫过时只留被指的那根满色，其余压暗——不压暗就分不清指到了哪天
          const dim = hover !== null && hover !== index ? "opacity-40 " : "";
          const probe = {
            onMouseEnter: () => setHover(index),
            onMouseLeave: () => setHover(null),
          };
          if (!point.observed) {
            return (
              <div
                key={point.date}
                {...probe}
                aria-label={`${point.date} 这天接口没给数据`}
                className={`h-[3px] flex-1 rounded-[2px] bg-line ${dim}`}
              />
            );
          }
          const height = point.hotness > 0 ? Math.max(6, (point.hotness / max) * 100) : 0;
          if (height === 0) {
            return (
              <div
                key={point.date}
                {...probe}
                aria-label={`${point.date} 观测到了，但当天没有相关内容`}
                className={`h-[3px] flex-1 rounded-[2px] bg-ink-faint/40 ${dim}`}
              />
            );
          }
          return (
            <div
              key={point.date}
              {...probe}
              aria-label={`${point.date} 热度 ${point.hotness}`}
              className={`flex-1 rounded-[2px] ${STAGE_STYLE[point.stage].dot} ${dim}`}
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
      {active ? (
        <>
          {/* 悬停那天的竖线：柱高只能比大小，"是哪一天"得靠它对位 */}
          <span
            aria-hidden
            className="pointer-events-none absolute -top-1.5 bottom-0 w-[2px] rounded-full bg-ink/40"
            style={{ left: `calc(${(((hover ?? 0) + 0.5) / points.length) * 100}% - 1px)` }}
          />
          <div
            role="tooltip"
            className="pointer-events-none absolute top-[-6px] z-20 w-max max-w-[220px] rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[12px] leading-snug shadow-md"
            style={{
              // 贴边的日期把浮层往里收，免得被卡片裁掉
              left: `${Math.min(Math.max((((hover ?? 0) + 0.5) / points.length) * 100, 13), 87)}%`,
              transform: "translate(-50%, -100%)",
            }}
          >
            <span className="tabular font-bold text-ink">{active.date.slice(5)}</span>
            {active.observed === false ? (
              <div className="text-ink-faint">这天接口没给数据（未观测，不当零活动）</div>
            ) : active.hotness <= 0 ? (
              <div className="text-ink-faint">观测到了，但当天没有相关内容</div>
            ) : (
              <div className="text-ink-mute">
                热度 <span className="tabular font-bold text-ink">{active.hotness.toFixed(1)}</span>
                {active.stage ? ` · ${stageText.get(active.stage) ?? active.stage}` : ""}
              </div>
            )}
          </div>
        </>
      ) : null}
      <div className="mt-1.5 flex justify-between text-[12px] text-ink-faint">
        <span>{points[0].date.slice(5)}</span>
        {item.peak_date ? <span className="text-ink-mute">峰 {item.peak_date.slice(5)}</span> : null}
        <span>{points[points.length - 1].date.slice(5)}</span>
      </div>
    </div>
  );
}

/**
 * 极简弹窗：遮罩点击 / Esc / 右上角按钮都能关；打开时锁住背景滚动，并把焦点收进来。
 *
 * 没做完整的焦点环（Tab 仍可能跑到背景里去）——这个页面是内部分析用的，
 * `aria-modal` + Esc + 显眼关闭按钮够用；以后要做通用弹窗再补焦点陷阱。
 */
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const boxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    // 锁背景滚动：不锁的话滚轮会带着底下的网格一起动，很晕
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    boxRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-ink/45 px-4 py-8 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-[980px] outline-none"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭"
          className="mb-2 ml-auto flex h-9 w-9 items-center justify-center rounded-full bg-surface text-[15px] text-ink-mute shadow-md transition hover:text-ink"
        >
          ✕
        </button>
        {children}
      </div>
    </div>
  );
}

/**
 * 格子卡：信息密度对齐梗库（封面 / 名称 / 热度 / 阶段）。
 *
 * **整张卡片可点**——点开是弹窗看轨迹，看完在弹窗里点「查看详情」才进详情页。
 * 底部那行只是视觉提示，不再是按钮（卡片本身就是入口，嵌套 button 反而别扭）。
 */
function HistoryCard({ item, onOpen }: { item: HistoryItem; onOpen: () => void }) {
  const tone = CYCLE_TONE[item.cycle];
  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
      aria-label={`${item.name}：看热度轨迹与周期`}
      className="card animate-rise group flex min-w-0 cursor-pointer flex-col rounded-2xl border-line p-3 text-left shadow-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-nav"
    >
      <StickerThumb thumbnail={item.thumbnail} ratio="6/5" emojiSize={44} rounded="rounded-xl" />

      <h3 className="mt-4 truncate text-[18px] font-bold leading-none" title={item.name}>
        {item.name}
      </h3>

      <div className="mt-3.5 flex items-center gap-2">
        <span className="flex items-center gap-1 text-brand">
          <span className="text-[18px] leading-none">🔥</span>
          <span className="tabular text-[24px] font-black leading-none">{item.current_hotness}</span>
        </span>
        <span className={`chip ${STAGE_STYLE[item.stage].chip}`}>{item.stage_label}</span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <span className={`chip ${tone.chip}`}>
          {item.cycle_emoji} {item.cycle_label}
        </span>
        {item.truncated ? (
          <span className="chip bg-rail px-2 py-0.5 text-ink-faint" title="入池日早于观测窗起点，周期左端被截断">
            左端截断
          </span>
        ) : null}
      </div>

      <div className="mt-3.5 flex items-center justify-between text-[13px]">
        <span className="font-semibold text-ink-mute">峰值</span>
        <span className="tabular font-black text-ink">
          {item.peak_hotness || "—"}
          {item.peak_date ? (
            <span className="ml-1 text-[12px] font-normal text-ink-faint">{item.peak_date.slice(5)}</span>
          ) : null}
        </span>
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[13px]">
        <span className="font-semibold text-ink-mute">半衰期</span>
        <span className="tabular font-black text-ink">
          {item.half_life_days === null
            ? item.cycle === "no_data"
              ? "—"
              : "未腰斩"
            : `${item.half_life_days}天`}
        </span>
      </div>

      <span className="mt-4 flex items-center justify-center gap-1.5 rounded-full bg-nav-soft py-2.5 text-[14px] font-bold text-nav transition group-hover:bg-nav group-hover:text-white">
        看热度轨迹
        <ArrowRightIcon size={15} />
      </span>
    </article>
  );
}

/** 展开面板：把「现在的展示」原样摊在格子里（占满一整行）。 */
function CyclePanel({ item }: { item: HistoryItem }) {
  const tone = CYCLE_TONE[item.cycle];
  return (
    <article className="card p-4 lg:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* 左：是谁 */}
        <div className="flex min-w-0 items-center gap-3 lg:w-[232px] lg:shrink-0">
          <StickerThumb thumbnail={item.thumbnail} ratio="1/1" emojiSize={20} className="w-[46px] shrink-0" rounded="rounded-tile" />
          <div className="min-w-0">
            {/* 名称不再直接跳详情页：先在这儿看轨迹，再决定要不要往下钻 */}
            <div className="truncate text-[17px] font-bold text-ink">{item.name}</div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-ink-mute">
              <span className="chip bg-rail px-2 py-[3px] text-[12px]">{item.cert_label}</span>
              <span>入池 {(item.admitted_at ?? "—").slice(0, 10)}</span>
            </div>
            <div className="mt-1 text-[12px] text-ink-faint">
              观测 {item.observed_days}/{item.window_days} 天
              {item.truncated ? " · 周期左端被截断" : ""}
            </div>
            <Link
              to={`/meme/${item.id}`}
              className="mt-2.5 inline-flex items-center gap-1 rounded-full bg-brand-soft px-3 py-1.5 text-[13px] font-bold text-brand transition hover:bg-brand hover:text-white"
            >
              查看详情
              <ArrowRightIcon size={14} />
            </Link>
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
  // 弹窗里是哪一只。筛选一变、它可能就不在列表里了，所以下面按 items 现查一次，
  // 不为这个加 effect（派生值比副作用稳）
  const [openId, setOpenId] = useState<number | null>(null);
  const { meta } = useMeta();
  const { data, loading, error, reload } = useAsync<HistoryView>(
    () => api.history({ days: 90, cycle, cert, sort }),
    [cycle, cert, sort],
  );

  const items = useMemo(() => data?.items ?? [], [data]);
  const summary = data?.summary;
  const active = openId === null ? null : items.find((item) => item.id === openId) ?? null;

  return (
    <div className="px-5 pb-12 pt-8 lg:px-[33px]">
      {/* 标题下面不再挂导语：口径该说的地方（观测窗、截断、空档）页面里都就地写明了 */}
      <SectionHeader emoji="📼" title="梗史馆" />

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

          {/* 格子布局对齐梗库；点整张卡片弹窗看轨迹，弹窗里再点「查看详情」才进详情页 */}
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            {items.length === 0 ? (
              <div className="col-span-full">
                <EmptyState
                  title="这个筛选下没有梗"
                  description="换一个周期类型，或者把认证筛选放宽到「不限认证」。"
                />
              </div>
            ) : (
              items.map((item) => (
                <HistoryCard key={item.id} item={item} onOpen={() => setOpenId(item.id)} />
              ))
            )}
          </div>

          {active ? (
            <Modal title={`${active.name}｜热度轨迹与周期`} onClose={() => setOpenId(null)}>
              <CyclePanel item={active} />
            </Modal>
          ) : null}

          <p className="mt-6 max-w-[880px] text-[13px] leading-relaxed text-ink-faint">
            {data?.rule}
          </p>
        </>
      )}

      <TransparencyFooter meta={meta} />
    </div>
  );
}
