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

/**
 * 分类胶囊：选中实心蓝、未选中浅底。
 * 刻意比生命周期那排做得小一号——让「处于什么阶段」和「讲的是什么」
 * 在视觉上是两层不同的筛选，而不是一排混在一起。
 */
function categoryClass(active: boolean) {
  return [
    "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold transition",
    active ? "bg-nav text-white shadow-pill" : "bg-[#F6FAFE] text-ink-soft hover:bg-nav-soft",
  ].join(" ");
}

export default function MemeLibrary() {
  const [params] = useSearchParams();
  const [filter, setFilter] = useState<HomeFilter>("all");
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [sort, setSort] = useState("hotness");
  // 分类筛选：专题（算法现算）与主题标签（LLM 打标）。各自单选，可与生命周期叠加。
  const [collection, setCollection] = useState("");
  const [tag, setTag] = useState("");
  const { meta } = useMeta();

  const { data, loading, error, reload } = useAsync(
    // 梗库是完整数据库：过气与暂时没内容的梗也要能查到，只有首页热榜才收门槛
    () => api.memes({ filter, search, sort, limit: 100, scope: "all", tag, collection }),
    [filter, search, sort, tag, collection],
  );

  return (
    <div className="px-5 pb-12 pt-8 lg:px-[33px]">
      <SectionHeader emoji="📚" title="梗库" />
      {/* 原来这里写"只收录通过 梗百科 + 梗指南 双 UP 认证的梗"——那是已经废掉的交集口径，
          准入早就改成并集了，留着就是一句假话，按要求删掉。梗库分母在下方筛选行与口径页都有。 */}

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

      {/* 分类：上面那排讲「这个梗处于什么阶段」，这里讲「这个梗是讲什么的」。
          专题由规则现算（本月新梗 / 年度爆款），标签由模型按固定清单打。
          都点一下即筛、再点一下取消，与上面的筛选叠加而不是互斥。 */}
      {meta?.collections?.length || meta?.tags?.length ? (
        <div className="mb-7 flex flex-col gap-3">
          {meta?.collections?.length ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-[46px] shrink-0 text-[13px] font-bold text-ink-mute">专题</span>
              {meta.collections.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  title={item.description}
                  onClick={() => setCollection(collection === item.key ? "" : item.key)}
                  className={categoryClass(collection === item.key)}
                >
                  <span>{item.emoji}</span>
                  {item.label}
                  <span className="tabular text-[11px] opacity-70">{item.count}</span>
                </button>
              ))}
            </div>
          ) : null}
          {meta?.tags?.length ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-[46px] shrink-0 text-[13px] font-bold text-ink-mute">主题</span>
              {meta.tags.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setTag(tag === item.key ? "" : item.key)}
                  className={categoryClass(tag === item.key)}
                >
                  <span>{item.emoji}</span>
                  {item.label}
                  <span className="tabular text-[11px] opacity-70">{item.count}</span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

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
