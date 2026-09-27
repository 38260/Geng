import { useLocation, Outlet } from "react-router-dom";

import { MobileNav } from "@/components/Header";
import { DetailRail, Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/Header";

/**
 * 全站骨架按参考图来：顶部通栏（logo + 标语 + 搜索 + 日期 + 头像）横跨整个视口，
 * 下面才是"左侧栏 + 白色内容区"。梗详情页把主导航换成章节导航。
 */
export function AppLayout() {
  const { pathname } = useLocation();
  const isDetail = /^\/meme\/\d+/.test(pathname);

  return (
    <div className="min-h-screen bg-canvas">
      <TopBar variant={isDetail ? "back" : "search"} />
      <MobileNav />
      <div className="mx-auto flex w-full max-w-[1440px] items-stretch">
        {isDetail ? <DetailRail /> : <Sidebar />}
        <main className="min-w-0 flex-1 bg-surface">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
