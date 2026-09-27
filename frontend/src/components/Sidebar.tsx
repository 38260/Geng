import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import {
  BookmarkSolidIcon,
  ChartSolidIcon,
  GearSolidIcon,
  ManageSolidIcon,
  HomeSolidIcon,
  LibrarySolidIcon,
  PlaySolidIcon,
  UserSolidIcon,
} from "@/components/icons";

const NAV = [
  { to: "/", label: "首页", icon: HomeSolidIcon, end: true },
  { to: "/library", label: "梗库", icon: LibrarySolidIcon, end: false },
  { to: "/trends", label: "热度趋势", icon: ChartSolidIcon, end: false },
  { to: "/favorites", label: "我的收藏", icon: BookmarkSolidIcon, end: false },
  { to: "/manage", label: "梗管理", icon: ManageSolidIcon, end: false },
  { to: "/settings", label: "系统设置", icon: GearSolidIcon, end: false },
];

/** 参考图口径：选中态是浅蓝圆角块 + 亮蓝实心图标与文字，未选中是深板蓝。 */
function railClass(isActive: boolean) {
  return [
    "flex items-center gap-3 rounded-[15px] px-4 py-3.5 text-[18px] font-bold transition",
    isActive ? "bg-nav-soft text-nav" : "text-ink-soft hover:bg-white hover:text-ink",
  ].join(" ");
}

export function Sidebar() {
  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-64px)] w-[240px] shrink-0 flex-col border-r border-line bg-rail px-3.5 pb-5 pt-7 lg:flex">
      <nav className="flex flex-col gap-4">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => railClass(isActive)}>
            <item.icon size={22} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto hidden pt-8 lg:block">
        {/* 素材本身就举着"今天赶什么梗？"的牌子，不再叠加文字 */}
        <img
          src="/brand/mascot-sign.png"
          width={168}
          alt="今天，赶什么梗？"
          className="mx-auto w-[168px] -rotate-2 select-none"
        />
      </div>
    </aside>
  );
}

const SECTIONS = [
  { id: "overview", label: "概览", icon: HomeSolidIcon },
  { id: "trend", label: "趋势图", icon: ChartSolidIcon },
  { id: "videos", label: "相关视频", icon: PlaySolidIcon },
  { id: "creators", label: "参与UP主", icon: UserSolidIcon },
];

/**
 * 梗详情页把主导航换成章节导航（参考图第二块画板就是这么排的）。
 * 用 IntersectionObserver 跟着滚动高亮，不额外监听 scroll 事件。
 */
export function DetailRail() {
  const [active, setActive] = useState("overview");

  useEffect(() => {
    const nodes = SECTIONS.map((section) => document.getElementById(section.id)).filter(
      (node): node is HTMLElement => Boolean(node),
    );
    if (!nodes.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible?.target.id) setActive(visible.target.id);
      },
      { rootMargin: "-72px 0px -60% 0px", threshold: 0 },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-64px)] w-[240px] shrink-0 flex-col border-r border-line bg-rail px-3.5 pt-6 xl:flex">
      <nav className="flex flex-col gap-4">
        {SECTIONS.map((section) => {
          const isActive = active === section.id;
          return (
            <a
              key={section.id}
              href={`#${section.id}`}
              onClick={() => setActive(section.id)}
              className={railClass(isActive)}
            >
              <section.icon size={22} />
              {section.label}
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
