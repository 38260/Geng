import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import { SearchIcon } from "@/components/icons";
import { MemeCard } from "@/components/MemeCard";
import { FilterPills } from "@/components/FilterPills";
import { SectionHeader, TransparencyFooter } from "@/components/Sections";
import { EmptyState, ErrorState, LoadingCards } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import { useMeta } from "@/hooks/useAppData";
import type { HomeFilter } from "@/types/api";

const SORTS: { key: string; label: string }[] = [
  { key: "hotness", label: "按热度" },
  { key: "growth", label: "按增速" },
  { key: "discussion", label: "按讨论量" },
  { key: "name", label: "按名称" },
];

export default function MemeLibrary() {
  const [params] = useSearchParams();
  const [filter, setFilter] = useState<HomeFilter>("all");
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [sort, setSort] = useState("hotness");
  const { meta } = useMeta();

  const { data, loading, error, reload } = useAsync(
    () => api.memes({ filter, search, sort, limit: 100 }),
    [filter, search, sort],
  );

  return (
    <div className="px-5 pb-12 pt-8 lg:px-[33px]">
      <SectionHeader emoji="📚" title="梗库" />
      <p className="-mt-2 mb-6 text-[15px] text-ink-mute">
        只收录通过 梗百科 + 梗指南 双 UP 认证的梗，共 {data?.total ?? 0} 个。
      </p>

      <div className="mb-7 flex flex-wrap items-center gap-3">
        <FilterPills
          filters={meta?.filters ?? [
            { key: "all", label: "全部" },
            { key: "hot", label: "正在爆" },
            { key: "taking_off", label: "快起飞" },
            { key: "receding", label: "退潮中" },
          ]}
          value={filter}
          onChange={setFilter}
        />
        <div className="ml-auto flex items-center gap-3">
          <div className="relative w-[220px]">
            <SearchIcon size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-mute" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="在结果里搜索…"
              className="h-10 w-full rounded-full border border-line bg-surface pl-9 pr-3 text-[14px] outline-none transition placeholder:text-ink-faint focus:border-nav/40"
            />
          </div>
          <div className="flex rounded-full bg-rail p-1">
            {SORTS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setSort(option.key)}
                className={[
                  "rounded-full px-3 py-1.5 text-[13px] font-semibold transition",
                  sort === option.key ? "bg-nav text-white" : "text-ink-mute hover:text-ink",
                ].join(" ")}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingCards count={10} />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data && data.items.length === 0 ? (
        <EmptyState
          title={search ? `没搜到「${search}」` : "这个筛选下暂时没有梗"}
          description={search ? "试试别名或关键词，比如「赛博木鱼」。" : "换一个筛选看看。"}
        />
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          {data!.items.map((item, index) => (
            <MemeCard key={item.id} item={item} rank={index + 1} />
          ))}
        </div>
      )}

      <TransparencyFooter meta={meta} />
    </div>
  );
}
