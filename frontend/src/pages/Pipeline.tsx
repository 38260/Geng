import { api } from "@/api/client";
import { SectionHeader, TransparencyFooter } from "@/components/Sections";
import { ErrorState, LoadingCards } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import { useMeta } from "@/hooks/useAppData";
import type { PipelineFact, PipelineStep, PipelineView } from "@/types/api";
import { compact, formatDateTime, withThousands } from "@/utils/format";

/**
 * 数据管线：把「这套数是怎么来的」整条链路摊开。
 *
 * 与「系统设置」页的分工：设置页管**怎么跑**（改配置），这一页只**陈述事实**。
 * 与「口径」页的分工：口径页讲业务规则（什么样的梗能上榜），
 * 这一页讲数据科学流程（数据怎么采、怎么洗、怎么算、质量如何）。
 *
 * 页面上的数字全部来自后端 GET /api/pipeline 现算，没有一处是写死的——
 * 所以库变了它就跟着变，不会出现「页面说一套、库里是另一套」。
 */

const n = (value: number | null | undefined) => (value == null ? "—" : withThousands(value));
const big = (value: number | null | undefined) => (value == null ? "—" : compact(value));
const pct = (value: number | null | undefined, digits = 1) =>
  value == null ? "—" : `${(value * 100).toFixed(digits)}%`;

/** 一个关键数字块 */
function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-tile border border-line bg-surface px-4 py-3">
      <div className="text-[12px] font-medium text-ink-mute">{label}</div>
      <div className="tabular mt-1 text-[21px] font-black leading-none text-ink">{value}</div>
      {hint ? <div className="mt-1.5 text-[11px] leading-snug text-ink-faint">{hint}</div> : null}
    </div>
  );
}

/** 一行「标签 / 值 / 说明」 */
function FactRow({ item }: { item: PipelineFact }) {
  return (
    <div className="rounded-tile border border-line bg-surface px-3.5 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[13px] font-medium text-ink-soft">{item.label}</span>
        <span className="tabular text-[14px] font-bold text-ink">{item.value}</span>
      </div>
      <div className="mt-1 text-[11px] leading-snug text-ink-faint">{item.hint}</div>
    </div>
  );
}

/** 流程步骤列表 */
function Steps({ items }: { items: PipelineStep[] }) {
  return (
    <ol className="flex flex-col gap-3">
      {items.map((step, index) => (
        <li key={step.key} className="flex gap-3">
          <span className="tabular mt-[3px] flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full bg-nav-soft text-[11px] font-black text-nav">
            {index + 1}
          </span>
          <div className="min-w-0">
            <div className="text-[13.5px] font-bold text-ink">{step.title}</div>
            <div className="mt-0.5 text-[12.5px] leading-relaxed text-ink-mute">{step.detail}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

/** 五段里的一段 */
function Block({
  index,
  title,
  summary,
  children,
}: {
  index: string;
  title: string;
  summary?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card mb-5 p-5 lg:p-6">
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-flare text-[13px] font-black text-white">
          {index}
        </span>
        <h3 className="text-[18px] font-black tracking-tight text-ink">{title}</h3>
        {summary ? <span className="ml-auto text-[12px] text-ink-mute">{summary}</span> : null}
      </div>
      {children}
    </section>
  );
}

const CHECK_STYLE: Record<string, string> = {
  ok: "text-nav",
  warn: "text-brand",
  demo: "text-brand",
};

function Content({ data }: { data: PipelineView }) {
  const { acquisition: acq, processing: proc, modeling, quality, ai } = data;

  return (
    <>
      {/* ------------------------------ 概览 ------------------------------ */}
      <div className="card mb-5 p-5 lg:p-6">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="text-[18px] font-black tracking-tight text-ink">一眼看全</h3>
          <span className="text-[12px] text-ink-mute">
            来自 {data.source.platform}
            {data.source.is_demo ? "（演示数据）" : "（真实采集）"} · 生成于 {formatDateTime(data.generated_at)}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Stat label="认证梗" value={n(data.counts.certified)} hint="通过双 UP 认证" />
          <Stat label="视频样本" value={big(acq.video_total)} hint={`真实 ${big(acq.video_real)}`} />
          <Stat label="参与 UP 主" value={big(acq.creator_total)} hint="去重后的作者数" />
          <Stat
            label="日观测点"
            value={big(proc.observation_points)}
            hint={`已观测 ${big(proc.observed_points)}`}
          />
          <Stat label="统计窗口" value={`${modeling.window_days} 天`} hint="滚动窗口" />
          <Stat
            label="观测覆盖率"
            value={pct(quality.observed_ratio)}
            hint={`缺失 ${pct(quality.missing_ratio)}`}
          />
        </div>
      </div>

      {/* ---------------------------- ① 数据获取 ---------------------------- */}
      <Block
        index="1"
        title="数据获取"
        summary={`约 ${big(acq.est_requests_total)} 次接口请求 / 全量一轮`}
      >
        <Steps items={acq.steps} />
        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {acq.params.map((item) => (
            <FactRow key={item.label} item={item} />
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="视频样本"
            value={n(acq.video_total)}
            hint={`真实 ${n(acq.video_real)} / 演示 ${n(acq.video_demo)}`}
          />
          <Stat
            label="发布时间跨度"
            value={acq.publish_from ? `${acq.publish_from} 起` : "—"}
            hint={acq.publish_to ? `至 ${acq.publish_to}` : "尚无样本"}
          />
          <Stat label="逐日检索请求" value={big(acq.est_requests_daily)} hint="梗 × 天 × 翻页" />
          <Stat label="详情补齐请求" value={big(acq.est_requests_enrich)} hint="头部视频逐条补齐" />
        </div>
        {acq.crawl_to ? (
          <p className="mt-3 text-[11.5px] text-ink-faint">
            最近一次抓取：{formatDateTime(acq.crawl_to)}
            {acq.crawl_from ? ` · 最早 ${formatDateTime(acq.crawl_from)}` : ""}
          </p>
        ) : null}
      </Block>

      {/* ---------------------------- ② 数据处理 ---------------------------- */}
      <Block index="2" title="数据处理" summary={`${big(proc.meme_with_series)} 个梗有时间序列`}>
        <Steps items={proc.steps} />
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="观测点总数" value={n(proc.observation_points)} hint="梗 × 天的序列格" />
          <Stat label="已观测" value={n(proc.observed_points)} hint="接口确实给了内容" />
          <Stat
            label="未观测"
            value={n(proc.unobserved_points)}
            hint={`占 ${pct(proc.unobserved_ratio)}，不当零活动用`}
          />
          <Stat
            label="播放量合计"
            value={big(proc.view_total)}
            hint="仅统计已观测的日子"
          />
        </div>
        {proc.stat_from ? (
          <p className="mt-3 text-[11.5px] text-ink-faint">
            序列覆盖 {proc.stat_from} 至 {proc.stat_to}
            {proc.derived.map((item) => (
              <span key={item.label}>
                {" · "}
                {item.label} {big(item.value)}（{item.hint}）
              </span>
            ))}
          </p>
        ) : null}
      </Block>

      {/* ---------------------------- ③ 分析建模 ---------------------------- */}
      <Block index="3" title="分析建模" summary={`热度指数同时在 ${modeling.hotness_windows.join("/")} 天窗口上看`}>
        <div className="flex flex-col gap-3">
          {modeling.items.map((item) => (
            <div key={item.title} className="rounded-tile border border-line bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13.5px] font-bold text-ink">{item.title}</span>
                <span className="chip bg-nav-soft !py-[4px] !text-[11px] text-nav">{item.tag}</span>
              </div>
              {item.detail ? (
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-mute">{item.detail}</p>
              ) : null}
            </div>
          ))}
        </div>
        {modeling.stages.length ? (
          <div className="mt-4">
            <div className="mb-2 text-[12px] font-medium text-ink-mute">生命周期阶段</div>
            <div className="flex flex-wrap gap-2">
              {modeling.stages.map((stage) => (
                <span key={stage.key} className="chip bg-canvas !py-[5px] !text-[12px] text-ink-soft">
                  {stage.label}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">{modeling.note}</p>
      </Block>

      {/* ---------------------------- ④ 数据质量 ---------------------------- */}
      <Block index="4" title="数据质量" summary={quality.is_demo ? "当前为演示数据" : "当前为真实采集"}>
        <div className="flex flex-col gap-2">
          {quality.checks.map((check) => (
            <div
              key={check.label}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-tile border border-line bg-surface px-3.5 py-2.5"
            >
              <span className="text-[13px] font-medium text-ink-soft">{check.label}</span>
              <span className={`tabular text-[14px] font-bold ${CHECK_STYLE[check.status] ?? "text-ink"}`}>
                {check.value}
              </span>
              <span className="w-full text-[11px] leading-snug text-ink-faint sm:w-auto sm:flex-1">
                {check.hint}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="统计截至" value={quality.data_through ?? "—"} hint="采集窗口不含今天" />
          <Stat
            label="数据滞后"
            value={quality.data_lag_days == null ? "—" : `${quality.data_lag_days} 天`}
            hint="越小越新鲜"
          />
          <Stat label="演示数据占比" value={pct(quality.demo_ratio)} hint="演示数据一律显式标注" />
          <Stat label="数据更新于" value={formatDateTime(quality.data_updated_at)} hint="指标重算时间" />
        </div>
      </Block>

      {/* ---------------------------- ⑤ AI 应用 ---------------------------- */}
      <Block
        index="5"
        title="AI 应用"
        summary={ai.configured ? `${ai.provider} · ${ai.model}` : "未配置（走算法兜底文案）"}
      >
        <div className="rounded-tile border border-line bg-surface px-4 py-3">
          <p className="text-[13px] leading-relaxed text-ink">{ai.role}</p>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="AI 文案条数" value={n(ai.insight_total)} hint="含缓存与兜底" />
          <Stat
            label="真实调用"
            value={n(ai.by_source.llm ?? 0)}
            hint={`兜底 ${n(ai.by_source.rule ?? 0)}`}
          />
          <Stat label="缓存命中" value={pct(ai.cache_hit_ratio)} hint="命中即不重复烧额度" />
          <Stat
            label="平均耗时"
            value={ai.avg_latency_ms == null ? "—" : `${withThousands(Math.round(ai.avg_latency_ms))} ms`}
            hint="单次生成"
          />
        </div>
        <ul className="mt-4 flex flex-col gap-2">
          {ai.boundaries.map((line) => (
            <li key={line} className="flex gap-2 text-[12.5px] leading-relaxed text-ink-mute">
              <span className="mt-[7px] h-[5px] w-[5px] shrink-0 rounded-full bg-flare" />
              {line}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[11.5px] text-ink-faint">
          兜底开关：{ai.fallback.rule_based ? "开启" : "关闭"} · 缓存有效间隔{" "}
          {ai.fallback.cache_gap_hours} 小时 · 版本 {data.version} · 环境 {data.environment}
        </p>
      </Block>
    </>
  );
}

export default function Pipeline() {
  const { meta } = useMeta();
  const { data, loading, error, reload } = useAsync(() => api.pipeline(), []);

  return (
    <>
      <div className="px-5 pb-12 pt-8 lg:px-[33px]">
        <SectionHeader emoji="🧪" title="数据管线" />
        <p className="-mt-3 mb-6 text-[13px] leading-relaxed text-ink-mute">
          这套数据从哪来、怎么清洗、怎么建模、质量如何、AI 用在哪——
          下面每个数字都由后端现算，不是写死的说明文案。
        </p>

        {loading ? (
          <LoadingCards count={4} />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data ? (
          <Content data={data} />
        ) : null}

        <TransparencyFooter meta={meta} />
      </div>
    </>
  );
}
