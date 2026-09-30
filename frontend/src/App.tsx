import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { LoadingCards } from "@/components/States";
import Favorites from "@/pages/Favorites";
import Home from "@/pages/Home";
import MemeLibrary from "@/pages/MemeLibrary";
import Pipeline from "@/pages/Pipeline";
import Settings from "@/pages/Settings";
import Trends from "@/pages/Trends";

// 详情页才用 ECharts、梗管理是运营入口，都不该进首页首屏包，按需拆出去。
const MemeDetail = lazy(() => import("@/pages/MemeDetail"));
const Manage = lazy(() => import("@/pages/Manage"));

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/library" element={<MemeLibrary />} />
        <Route path="/trends" element={<Trends />} />
        <Route path="/favorites" element={<Favorites />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route
          path="/manage"
          element={
            <Suspense fallback={<div className="p-8"><LoadingCards count={3} /></div>}>
              <Manage />
            </Suspense>
          }
        />
        <Route path="/settings" element={<Settings />} />
        <Route
          path="/meme/:id"
          element={
            <Suspense fallback={<div className="p-8"><LoadingCards count={3} /></div>}>
              <MemeDetail />
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
