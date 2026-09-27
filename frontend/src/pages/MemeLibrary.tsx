import { useState } from "react";

import { api } from "@/api/client";
import { Header } from "@/components/Header";
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
  const [filter, setFilter] = useState<HomeFilter>("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("hotness");
  const { meta } = useMeta();

  const { data, loading, error, reload } = useAsync(
    () => api.memes({ filter, search, sort, limit: 100 }),
    [filter, search, sort],
  );

  return (
    <>
      <Header search={search} onSearch={setSearch} />
      <div className="mx-auto w-full max-w-[1180px] px-4 pb-10 pt-5 lg:px-7">
        <SectionHeader emoji="📚" title="梗库" />
        <p className="-mt-2 mb-5 text-[13px] text-ink-mute">
          只收录通过 梗百科 + 梗指南 双 UP 认证的梗，共 {data?.total ?? 0} 个。
        </p>

        <div className="mb-6 flex flex-wrap items-center gap-3">
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
          <div className="ml-auto flex rounded-full bg-rail p-1">
            {SORTS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setSort(option.key)}
                className={[
                  "rounded-full px-3 py-1.5 text-[12px] font-semibold transition",
                  sort === option.key ? "bg-flare text-white" : "text-ink-mute hover:text-ink",
                ].join(" ")}
              >
                {option.label}
              </button>
            ))}
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
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
            {data!.items.map((item, index) => (
              <MemeCard key={item.id} item={item} rank={index + 1} />
            ))}
          </div>
        )}

        <TransparencyFooter meta={meta} />
      </div>
    </>
  );
}
