import { Outlet } from "react-router-dom";

import { MobileNav, Sidebar } from "@/components/Sidebar";

/** 全站骨架：左侧固定导航 + 右侧内容区（Desktop 优先）。 */
export function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileNav />
        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
