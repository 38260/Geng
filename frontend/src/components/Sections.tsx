import { Link } from "react-router-dom";

import { ArrowRightIcon } from "@/components/icons";
import type { Meta } from "@/types/api";
import { formatDateTime } from "@/utils/format";

/** 参考图里标题下方那道珊瑚红毛笔横扫：左头粗、右尾细，起笔处还有一个小点。 */
function BrushUnderline({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 520 26" className={className} aria-hidden fill="none">
      <defs>
        <linearGradient id="swoosh" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#FB3A5E" />
          <stop offset="55%" stopColor="#FF6A72" />
          <stop offset="100%" stopColor="#FF9A8B" />
        </linearGradient>
      </defs>
      {/* 起笔小点 + 一条由粗到细的横扫 */}
      <path d="M3 14C40 8 78 5 112 5c-30 5-66 10-100 13-9 1-14-1-12-7z" fill="#FB3A5E" opacity="0.9" />
      <path d="M132 17c104-9 250-12 384-10-122 10-268 16-380 15-5 0-6-3-4-5z" fill="url(#swoosh)" />
    </svg>
  );
}

/** 首页 Hero：满血粉色带 + 毛笔标题 + 右侧水彩吉祥物带，和参考图同一构图。 */
export function Hero({ subtitle }: { subtitle: string }) {
  return (
    <section
      className="relative isolate overflow-hidden"
      style={{
        background: "linear-gradient(103deg, #FEF0F5 0%, #FEF2F6 42%, #FEEEF3 74%, #FEEFF2 100%)",
      }}
    >
      <div className="relative z-10 max-w-[860px] px-10 pb-[64px] pt-[58px] lg:px-[70px]">
        <h1 className="brush-title brush-heavy text-[40px] leading-[1.1] text-ink sm:text-[62px] lg:text-[82px]">
          今天，赶什么梗？
        </h1>
        <BrushUnderline className="-mt-1 h-[22px] w-[430px] max-w-full" />
        <p className="mt-[26px] text-[20px] font-semibold text-[#2D4A84] lg:text-[23px]">{subtitle}</p>
      </div>

      {/* 装饰带直接从参考图裁出（含"现在不赶就晚了"与水彩），左边缘渐隐避免接缝 */}
      <img
        src="/thumbs/hero-band-right.png"
        alt="现在不赶就晚了"
        className="pointer-events-none absolute right-0 top-0 hidden h-full w-[440px] select-none object-cover object-right md:block lg:w-[470px]"
        style={{
          maskImage: "linear-gradient(to right, transparent 0, #000 14%)",
          WebkitMaskImage: "linear-gradient(to right, transparent 0, #000 14%)",
        }}
      />
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
    <div className="mb-6 flex items-end justify-between">
      <h2 className="flex items-center gap-3 text-[30px] font-black leading-none tracking-tight text-ink">
        <span className="text-[28px] leading-none">{emoji}</span>
        {title}
      </h2>
      {actionLabel && actionTo ? (
        <Link to={actionTo} className="link-quiet text-[16px]">
          {actionLabel}
          <ArrowRightIcon size={18} />
        </Link>
      ) : null}
    </div>
  );
}

/** 数据透明度：数据来源 / 认证方式 / 算法口径 / 更新时间。 */
export function TransparencyFooter({ meta }: { meta: Meta | null }) {
  return (
    <footer className="mt-10 flex flex-col gap-2 border-t border-line pt-5 text-[14px] text-ink-mute sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 whitespace-nowrap">
        <span>数据更新于：{formatDateTime(meta?.data_updated_at)}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-ink-soft">Bilibili</span>
        <span className="text-ink-faint">|</span>
        <span>梗百科</span>
        <span className="text-ink-faint">|</span>
        <span>梗指南</span>
        <span className="text-ink-faint">|</span>
        <span className="font-semibold text-brand">赶梗潮自定义热度指数</span>
      </div>
    </footer>
  );
}
