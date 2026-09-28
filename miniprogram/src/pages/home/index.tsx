import { Text, View } from "@tarojs/components";
import Taro, { usePullDownRefresh, useReachBottom } from "@tarojs/taro";
import { useState } from "react";

import { getMeta, listMemes } from "@/api/client";
import { MemeCardView } from "@/components/MemeCardView";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/States";
import { useLoad } from "@/hooks/useLoad";
import { usePaged } from "@/hooks/usePaged";
import { freshnessText, isStale } from "@/utils/format";

import "./index.scss";

const FALLBACK_FILTERS = [{ key: "all", label: "全部" }];

export default function Home() {
  const [filter, setFilter] = useState<string>("all");
  const meta = useLoad(() => getMeta(), []);
  const board = usePaged((offset, limit) => listMemes({ scope: "board", filter, limit, offset }), [filter]);

  usePullDownRefresh(async () => {
    await Promise.all([meta.reload(), board.refresh()]);
    Taro.stopPullDownRefresh();
  });
  useReachBottom(() => {
    board.loadMore();
  });

  const filters = meta.data?.filters?.length ? meta.data.filters : FALLBACK_FILTERS;
  const stale = isStale(meta.data?.data_lag_days ?? null);

  return (
    <View className="shell">
      <View className="hero card">
        <Text className="hero-title">今天，赶什么梗？</Text>
        <Text className="hero-sub">只看 B 站 · 梗百科与梗指南介绍过的网络梗</Text>
        <View className={`hero-fresh${stale ? " hero-fresh-stale" : ""}`}>
          <Text className="hero-fresh-text">
            {freshnessText(meta.data?.data_through ?? null, meta.data?.data_lag_days ?? null)}
          </Text>
          {meta.data ? (
            <Text className="hero-count">
              热榜 {meta.data.certified_count} · 梗库 {meta.data.library_count ?? 0}
            </Text>
          ) : null}
        </View>
        {meta.data?.is_demo ? <Text className="chip chip-gold hero-demo">当前是演示数据</Text> : null}
      </View>

      <View className="pills">
        {filters.map((item) => (
          <Text
            key={item.key}
            className={`pill${filter === item.key ? " pill-on" : ""}`}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </Text>
        ))}
      </View>

      {board.loading ? <LoadingBlock count={4} /> : null}
      {!board.loading && board.error ? <ErrorBlock message={board.error} onRetry={board.refresh} /> : null}
      {!board.loading && !board.error && !board.items.length ? (
        <EmptyBlock title="这个筛选下暂时没有梗" body="换个筛选，或去梗库看完整列表。" />
      ) : null}

      {!board.loading ? (
        <View>
          {board.items.map((meme, index) => (
            <MemeCardView
              key={meme.id}
              meme={meme}
              rank={index}
              onOpen={(id) => Taro.navigateTo({ url: `/pages/detail/index?id=${id}` })}
            />
          ))}
          {board.loadingMore ? <View className="more-tip">加载中…</View> : null}
          {!board.loadingMore && board.items.length && board.items.length >= board.total ? (
            <View className="more-tip">
              已经到底了 · 另有 {board.gatedOut} 个过气或只剩残值的梗没上热榜，可在梗库查看
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
