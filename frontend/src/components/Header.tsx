import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { DemoBadge } from "@/components/States";
import { CalendarIcon, SearchIcon } from "@/components/icons";
import { useMeta } from "@/hooks/useAppData";
import { formatDateTime } from "@/utils/format";

/** 参考图顶部通栏：日历图标 + 日期 + 「今日更新」两行。 */
function DateChip({ updatedAt }: { updatedAt?: string | null }) {
  const date = updatedAt ? new Date(updatedAt) : new Date();
  const valid = !Number.isNaN(date.getTime());
  const iso = valid ? formatDateTime(updatedAt ?? new Date().toISOString()).slice(0, 10) : "—";
  return (
    <div className="hidden items-center gap-2 sm:flex">
      <CalendarIcon size={20} className="text-nav" />
      <div className="leading-tight">
        <div className="tabular text-[15px] font-bold text-ink">{iso}</div>
        <div className="text-[11px] text-ink-mute">今日更新</div>
      </div>
    </div>
  );
}

/** V1 不做登录，头像只是占位；素材直接从参考图裁出。 */
function Avatar() {
  return (
    <img
      src="/thumbs/avatar.png"
      width={36}
      height={36}
      alt=""
      title="V1 不做登录体系"
      className="h-9 w-9 shrink-0 rounded-full object-cover ring-1 ring-line"
    />
  );
}

function SearchBox() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  return (
    <div className="relative w-full max-w-[480px]">
      <SearchIcon size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-mute" />
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && value.trim()) navigate(`/library?q=${encodeURIComponent(value.trim())}`);
        }}
        placeholder="搜索梗名、别名、关键词…"
        className="h-11 w-full rounded-full border border-line bg-surface pl-11 pr-4 text-[15px] outline-none transition placeholder:text-ink-faint focus:border-nav/40 focus:ring-2 focus:ring-nav/12"
      />
    </div>
  );
}

/**
 * 全站顶部通栏（参考图里它横跨侧栏与内容区，所以放在 AppLayout 而不是各页面）。
 * variant="back" 用于梗详情页：左侧换成返回，搜索框不出现。
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
            <div className="hidden flex-1 justify-center px-4 lg:flex">
              <SearchBox />
            </div>
          </>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-3 lg:gap-4">
          {meta ? <DemoBadge isDemo={meta.is_demo} source={meta.data_source} /> : null}
          <DateChip updatedAt={updatedAt ?? meta?.data_updated_at} />
          <div className="hidden h-7 w-px bg-line sm:block" />
          <Avatar />
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
