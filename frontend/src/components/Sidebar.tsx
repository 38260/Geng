import { NavLink } from "react-router-dom";

import { LogoMark } from "@/components/LogoMark";
import { BookmarkIcon, GearIcon, HomeIcon, LibraryIcon, TrendIcon } from "@/components/icons";

const NAV = [
  { to: "/", label: "首页", icon: HomeIcon, end: true },
  { to: "/library", label: "梗库", icon: LibraryIcon, end: false },
  { to: "/trends", label: "热度趋势", icon: TrendIcon, end: false },
  { to: "/favorites", label: "我的收藏", icon: BookmarkIcon, end: false },
  { to: "/settings", label: "系统设置", icon: GearIcon, end: false },
];

export function Sidebar() {
  return (
    <aside className="hidden w-[212px] shrink-0 flex-col border-r border-line bg-rail px-4 pb-5 pt-5 lg:flex">
      <NavLink to="/" className="mb-7 flex items-center gap-2">
        <LogoMark size={34} />
        <span className="text-[21px] font-black tracking-tight">赶梗潮</span>
      </NavLink>

      <nav className="flex flex-col gap-1.5">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              [
                "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[14px] font-semibold transition",
                isActive
                  ? "bg-flare/10 text-flare shadow-[inset_0_0_0_1px_rgba(76,126,237,0.12)]"
                  : "text-ink-soft hover:bg-white hover:text-ink",
              ].join(" ")
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto hidden pt-8 lg:block">
        {/* 素材本身就举着"今天赶什么梗？"的牌子，不再叠加文字 */}
        <img
          src="/brand/mascot-sign.png"
          width={120}
          alt="今天，赶什么梗？"
          className="mx-auto w-[122px] -rotate-2 select-none"
        />
      </div>
    </aside>
  );
}

/** 移动端顶部导航（Desktop 优先，这里只保证基本可用） */
export function MobileNav() {
  return (
    <nav className="flex items-center gap-1 overflow-x-auto border-b border-line bg-rail px-3 py-2 lg:hidden">
      <NavLink to="/" end className="flex items-center gap-1.5 px-2 py-1 text-[13px] font-bold">
        <LogoMark size={20} />
        赶梗潮
      </NavLink>
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            [
              "whitespace-nowrap rounded-lg px-2.5 py-1 text-[13px] font-medium",
              isActive ? "bg-flare/10 text-flare" : "text-ink-mute",
            ].join(" ")
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
