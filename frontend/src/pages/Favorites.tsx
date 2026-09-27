import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { MemeCard } from "@/components/MemeCard";
import { SectionHeader, TransparencyFooter } from "@/components/Sections";
import { EmptyState, ErrorState, LoadingCards } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import { useFavorites, useMeta } from "@/hooks/useAppData";

/**
 * 我的收藏：只存在这台浏览器的 localStorage 里。
 * V1 明确不做登录 / 关注 / 社交，所以这里没有账号概念。
 */
export default function Favorites() {
  const { items, clear } = useFavorites();
  const { meta } = useMeta();
  const { data, loading, error, reload } = useAsync(() => api.memes({ limit: 100 }), []);
  const all = data?.items ?? [];
  const saved = items
    .map((favorite) => all.find((item) => item.id === favorite.id))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  return (
    <>
      <div className="px-5 pb-12 pt-8 lg:px-[33px]">
        <div className="flex items-end justify-between">
          <SectionHeader emoji="🔖" title="我的收藏" />
          {items.length ? (
            <button type="button" onClick={clear} className="link-quiet -mb-4">
              清空
            </button>
          ) : null}
        </div>
        <p className="-mt-2 mb-5 text-[13px] text-ink-mute">
          收藏只保存在本机浏览器，不需要登录（V1 不做账号体系）。
        </p>

        {loading ? (
          <LoadingCards count={3} />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : items.length === 0 ? (
          <EmptyState
            title="还没收藏任何梗"
            description="去梗详情页点「收藏这个梗」，就会出现在这里。"
          />
        ) : saved.length === 0 ? (
          <EmptyState title="收藏的梗暂时不在榜上" description="可能它还没通过双 UP 认证，或已被移出正式梗库。" />
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
            {saved.map((item, index) => (
              <MemeCard key={item.id} item={item} rank={index + 1} />
            ))}
          </div>
        )}

        {items.length > saved.length ? (
          <p className="mt-4 text-[12px] text-ink-faint">
            有 {items.length - saved.length} 个收藏项当前查不到数据。
            <Link to="/library" className="ml-1 text-flare hover:underline">
              去梗库看看
            </Link>
          </p>
        ) : null}

        <TransparencyFooter meta={meta} />
      </div>
    </>
  );
}
