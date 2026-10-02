import { Link, NavLink, useNavigate } from "react-router-dom";

import { DemoBadge } from "@/components/States";
import { CalendarIcon, HomeIcon } from "@/components/icons";
import { useMeta } from "@/hooks/useAppData";
import { formatDateTime } from "@/utils/format";

/**
 * 参考图顶部通栏：日历图标 + 日期 + 两行小字。
 * 日期给的是"统计截至哪天"，不是"今天"；第二行必须把**两个时间点**都写明白——
 * 这一天覆盖到什么时候、这批数是几点采回来的，否则"数据截至"四个字没有意义。
 */
function DateChip({ through, updatedAt }: { through?: string | null; updatedAt?: string | null }) {
  const iso = through?.slice(0, 10) || (updatedAt ? formatDateTime(updatedAt).slice(0, 10) : "—");
  const stamp = updatedAt && updatedAt !== "—" ? formatDateTime(updatedAt).slice(5) : "";
  const tip = through
    ? `统计窗口不含今天（今天没过完，头部样本会偏低、增幅会假跌）\n`
      + `「${iso}」= 这一天 00:00–24:00 的数据，采集/重算完成于 ${formatDateTime(updatedAt)}`
    : "还没有采集到统计数据";
  return (
    <div className="hidden items-center gap-2 sm:flex" title={tip}>
      <CalendarIcon size={20} className="text-nav" />
      <div className="leading-tight">
        <div className="tabular text-[15px] font-bold text-ink">{iso}</div>
        <div className="tabular text-[11px] text-ink-mute">
          {through ? `数据截至当日 24:00${stamp ? ` · 采集于 ${stamp}` : ""}` : "今日更新"}
        </div>
      </div>
    </div>
  );
}

/**
 * 全站顶部通栏（参考图里它横跨侧栏与内容区，所以放在 AppLayout 而不是各页面）。
 * variant="back" 用于梗详情页：左侧换成「返回 + 首页」。
 *
 * 这里**不再挂全站搜索框**：梗库自己有搜索框（还认 `?q=`），
 * 顶栏那个只是个重复入口，删掉后头部只剩品牌与数据时间戳，清净很多。
 */
export function TopBar({
  variant = "search",
  updatedAt,
}: {
  variant?: "search" | "back";
  updatedAt?: string | null;
}) {
  const { meta } = useMeta();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-30 bg-canvas/92 backdrop-blur-sm">
      <div className="mx-auto flex h-16 w-full max-w-[1440px] items-center gap-4 px-5 lg:px-6">
        {variant === "back" ? (
          <>
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="flex shrink-0 items-center gap-2 text-[15px] font-semibold text-ink-soft transition hover:text-nav"
            >
              <span aria-hidden className="text-[17px] leading-none">
                ←
              </span>
              返回
            </button>
            <span aria-hidden className="h-5 w-px shrink-0 bg-line" />
            {/* 返回只退一步；从分享链接落进详情页时根本没有"上一步"，所以首页入口必须一直在 */}
            <Link
              to="/"
              className="flex shrink-0 items-center gap-1.5 text-[15px] font-medium text-ink-mute transition hover:text-nav"
              title="直接回热榜首页，不走浏览器历史"
            >
              <HomeIcon size={16} />
              首页
            </Link>
          </>
        ) : (
          <>
            <Link to="/" className="flex shrink-0 items-center gap-2">
              <img
                src="/thumbs/logo-ghost.png"
                width={46}
                height={46}
                alt="赶梗潮"
                className="-ml-1 h-[46px] w-[46px] select-none object-contain"
              />
              <span
                className="brush-title text-[33px] font-black leading-none tracking-tight text-ink"
                style={{ WebkitTextStroke: "1.8px currentColor" }}
              >
                赶梗潮
              </span>
            </Link>
            <span className="hidden shrink-0 text-[15px] font-medium text-ink-mute lg:block">
              B站网络梗热度与生命周期分析平台
            </span>
          </>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-3 lg:gap-4">
          {meta ? <DemoBadge isDemo={meta.is_demo} source={meta.data_source} /> : null}
          <DateChip through={meta?.data_through} updatedAt={updatedAt ?? meta?.data_updated_at} />
          {/* V1 不做登录，右上角原来挂的是参考图里裁出来的占位头像，已删 */}
        </div>
      </div>
    </header>
  );
}

/** 移动端顶部导航（Desktop 优先，这里只保证基本可用）。 */
export function MobileNav() {
  const items = [
    { to: "/", label: "首页" },
    { to: "/library", label: "梗库" },
    { to: "/trends", label: "热度趋势" },
    { to: "/favorites", label: "我的收藏" },
    { to: "/pipeline", label: "数据管线" },
    { to: "/manage", label: "梗管理" },
    { to: "/settings", label: "系统设置" },
  ];
  return (
    <nav className="flex items-center gap-1 overflow-x-auto border-b border-line bg-rail px-3 py-2 lg:hidden">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) =>
            [
              "whitespace-nowrap rounded-lg px-2.5 py-1 text-[13px] font-medium",
              isActive ? "bg-nav-soft text-nav" : "text-ink-mute",
            ].join(" ")
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
