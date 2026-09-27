import { Link } from "react-router-dom";

import { ArrowRightIcon } from "@/components/icons";
import type { Meta } from "@/types/api";
import { formatDateTime } from "@/utils/format";

/** 首页 Hero：毛笔标题 + 吉祥物，刻意不做"巨型渐变 AI Hero"。 */
export function Hero({ subtitle }: { subtitle: string }) {
  return (
    <section
      className="relative overflow-hidden rounded-card border border-line"
      style={{
        background:
          "linear-gradient(100deg, #FFF7F0 0%, #FEF1F2 40%, #FDEDEE 62%, #FEF8EE 88%, #FEF8EE 100%)",
      }}
    >
      <div className="relative z-10 px-6 pb-7 pt-8 sm:px-9">
        <h1 className="brush-title text-[38px] font-black leading-tight text-ink sm:text-[46px]">
          今天，赶什么梗？
        </h1>
        <div className="hero-swoosh mt-1 h-[5px] w-[168px] rounded-full opacity-90" />
        <p className="mt-4 text-[14px] font-medium text-[#5A6B8C]">{subtitle}</p>
      </div>

      <div className="pointer-events-none absolute right-0 top-0 hidden h-full w-[340px] md:block lg:w-[420px]">
        <span className="brush-title absolute left-4 top-4 z-20 -rotate-[9deg] text-[16px] font-bold leading-snug text-ink lg:text-[18px]">
          现在不赶
          <br />
          就晚了！
        </span>
        <img
          src="/brand/hero-mascot.png"
          alt=""
          className="blend-mascot h-full w-full select-none object-contain object-bottom"
        />
      </div>

      <span aria-hidden className="pointer-events-none absolute -bottom-10 right-1/3 h-32 w-64 rounded-full bg-brand/10 blur-2xl" />
    </section>
  );
}

export function SectionHeader({
  emoji,
  title,
  actionLabel,
  actionTo,
}: {
  emoji: string;
  title: string;
  actionLabel?: string;
  actionTo?: string;
}) {
  return (
    <div className="mb-4 flex items-end justify-between">
      <h2 className="section-title">
        <span className="text-[20px] leading-none">{emoji}</span>
        {title}
      </h2>
      {actionLabel && actionTo ? (
        <Link to={actionTo} className="link-quiet">
          {actionLabel}
          <ArrowRightIcon size={15} />
        </Link>
      ) : null}
    </div>
  );
}

/** 数据透明度：数据来源 / 认证方式 / 算法口径 / 更新时间。 */
export function TransparencyFooter({ meta }: { meta: Meta | null }) {
  return (
    <footer className="mt-8 flex flex-col gap-2 border-t border-line pt-4 text-[12px] text-ink-mute sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 whitespace-nowrap">
        <span>数据更新于：{formatDateTime(meta?.data_updated_at)}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-ink-soft">Bilibili</span>
        <span className="text-ink-faint">|</span>
        <span>梗百科</span>
        <span className="text-ink-faint">|</span>
        <span>梗指南</span>
        <span className="text-ink-faint">|</span>
        <span className="font-medium text-brand">赶梗潮自定义热度指数</span>
      </div>
      <details className="sm:w-full">
        <summary className="cursor-pointer select-none text-[12px] text-ink-faint hover:text-ink-mute">
          数据与算法说明
        </summary>
        <dl className="mt-2 grid gap-1 text-[12px] text-ink-mute sm:grid-cols-2">
          <div>数据来源：{meta?.transparency.data_platform ?? "Bilibili"}</div>
          <div>梗认证：{(meta?.transparency.certification ?? []).join(" + ")}</div>
          <div>热度算法：{meta?.transparency.hotness_algorithm ?? "—"}</div>
          <div>生命周期：{meta?.transparency.lifecycle_algorithm ?? "—"}</div>
          <div className="sm:col-span-2">AI 角色：{meta?.transparency.llm_role ?? "—"}</div>
          {meta?.transparency.sampling ? (
            <div className="sm:col-span-2">{meta.transparency.sampling}</div>
          ) : null}
          <div className="sm:col-span-2">
            正式梗库 {meta?.certified_count ?? 0} 个 · 候选（未通过双 UP 认证）{meta?.candidate_count ?? 0} 个 · 统计窗口 {meta?.window_days ?? 0} 天
          </div>
        </dl>
      </details>
    </footer>
  );
}
