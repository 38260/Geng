import { useMemo, useState } from "react";

import { api } from "@/api/client";
import { FilterPills } from "@/components/FilterPills";
import { MemeCard, RecommendationCard } from "@/components/MemeCard";
import { Hero, SectionHeader, TransparencyFooter } from "@/components/Sections";
import { EmptyState, ErrorState, LoadingCards } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import { useMeta } from "@/hooks/useAppData";
import type { HomeFilter, LifecycleStage, MemeCard as Card } from "@/types/api";

const HOT_LIST_SIZE = 5;
const FEATURED_STAGES: LifecycleStage[] = ["explosive", "rising", "plateau", "sprouting"];

const FALLBACK_FILTERS = [
  { key: "all" as HomeFilter, label: "全部" },
  { key: "hot" as HomeFilter, label: "正在爆" },
  { key: "taking_off" as HomeFilter, label: "快起飞" },
  { key: "receding" as HomeFilter, label: "退潮中" },
];

/** 精选推荐：每个阶段挑一个最能打的，保证首页能看到不同状态而不是五个一模一样的。 */
function pickFeatured(all: Card[]): Card[] {
  const picked: Card[] = [];
  for (const stage of FEATURED_STAGES) {
    const best = all.filter((item) => item.stage === stage).sort((a, b) => b.hotness - a.hotness)[0];
    if (best && !picked.some((item) => item.id === best.id)) picked.push(best);
  }
  for (const item of all) {
    if (picked.length >= 4) break;
    if (!picked.some((existing) => existing.id === item.id)) picked.push(item);
  }
  return picked.slice(0, 4);
}

export default function Home() {
  const [filter, setFilter] = useState<HomeFilter>("all");
  const { meta } = useMeta();

  // 一次请求拿到全量榜单，前端只做切片，避免首页打几十个接口
  const { data, loading, error, reload } = useAsync(() => api.memes({ filter, limit: 100 }), [filter]);

  const items = data?.items ?? [];
  const hotList = useMemo(() => items.slice(0, HOT_LIST_SIZE), [items]);
  const featured = useMemo(() => pickFeatured(items), [items]);

  return (
    <div className="pb-12">
      <Hero subtitle="B站网络梗热度与生命周期分析平台" />

      <div className="px-5 pt-8 lg:px-[33px]">
        <FilterPills filters={meta?.filters ?? FALLBACK_FILTERS} value={filter} onChange={setFilter} />

        <section className="mt-10">
          <SectionHeader emoji="🔥" title="今日热榜" actionLabel="查看全部" actionTo="/library" />
          {loading ? (
            <LoadingCards count={HOT_LIST_SIZE} />
          ) : error ? (
            <ErrorState message={error} onRetry={reload} />
          ) : hotList.length === 0 ? (
            <EmptyState
              title="这个筛选下暂时没有梗"
              description="换一个筛选看看，或者等下一次数据采集。"
            />
          ) : (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
              {hotList.map((item, index) => (
                <MemeCard key={item.id} item={item} rank={index + 1} />
              ))}
            </div>
          )}
        </section>

        <section className="mt-12">
          <SectionHeader emoji="⭐" title="精选推荐" actionLabel="查看更多" actionTo="/trends" />
          {loading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="skeleton h-[150px]" />
              ))}
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={reload} />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {featured.map((item) => (
                <RecommendationCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </section>

        <TransparencyFooter meta={meta} />
      </div>
    </div>
  );
}
