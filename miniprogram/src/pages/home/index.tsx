import { ScrollView, Text, View } from "@tarojs/components";
import Taro, { usePullDownRefresh, useReachBottom, useShareAppMessage } from "@tarojs/taro";
import { useEffect, useMemo, useRef, useState } from "react";

import { getMeta, listMemes } from "@/api/client";
import { MemeCardView } from "@/components/MemeCardView";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/States";
import { useLoad } from "@/hooks/useLoad";
import { catchTone, freshnessText, isStale, stageTone } from "@/utils/format";
import { pickFeatured } from "@/utils/featured";

import "./index.scss";

const FALLBACK_FILTERS = [{ key: "all", label: "全部" }];
/** 一次把热榜拿全（热榜只有几十个），前端切片：精选推荐和榜单用的是同一份数 */
const FETCH_SIZE = 100;
const PAGE_SIZE = 20;

const open = (id: number) => Taro.navigateTo({ url: `/pages/detail/index?id=${id}` });

/** 精选推荐：每个阶段挑一个最能打的，避免首屏五个都是"正在爆"。 */
function Featured({ items }: { items: ReturnType<typeof pickFeatured> }) {
  const picked = useMemo(() => pickFeatured(items), [items]);
  if (picked.length < 2) return null;
  return (
    <View className="featured">
      <Text className="featured-title">精选推荐 · 不同阶段各挑一个最能打的</Text>
      <ScrollView scrollX className="featured-scroll" enhanced showScrollbar={false}>
        <View className="featured-row">
          {picked.map((item) => {
            const stage = stageTone(item.stage);
            const catchStyle = catchTone(item.catch_status);
            return (
              <View className="featured-card" key={item.id} onClick={() => open(item.id)}>
                <View className="featured-head">
                  <Text className="featured-emoji" style={{ background: item.thumbnail?.color || "#FFE9E4" }}>
                    {item.emoji || "🎬"}
                  </Text>
                  <Text className="featured-score tabular" style={{ color: stage.color }}>
                    {Math.round(item.hotness)}
                  </Text>
                </View>
                <Text className="featured-name">{item.name}</Text>
                <View className="featured-chips">
                  <Text className={`chip ${stage.chip}`}>{item.nickname}</Text>
                  <Text className={`chip ${catchStyle.chip}`}>{item.catch_label}</Text>
                </View>
              </View>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

export default function Home() {
  const [filter, setFilter] = useState<string>("all");
  const [shown, setShown] = useState(PAGE_SIZE);
  const meta = useLoad(() => getMeta(), []);
  const board = useLoad(() => listMemes({ scope: "board", filter, limit: FETCH_SIZE }), [filter]);

  const items = board.data?.items ?? [];

  // 分享文案在点"转发"那一刻才取，所以用 ref 读最新值，不重新注册回调
  const shareTitle = useRef("今天赶什么梗？B 站梗热度与生命周期");
  if (meta.data) {
    shareTitle.current = `今天赶什么梗？B 站热榜 ${meta.data.certified_count} 个活梗`;
  }
  useShareAppMessage(() => ({ title: shareTitle.current, path: "/pages/home/index" }));

  useEffect(() => {
    setShown(PAGE_SIZE);
  }, [filter, board.data]);

  usePullDownRefresh(async () => {
    await Promise.all([meta.reload(), board.reload()]);
    Taro.stopPullDownRefresh();
  });
  useReachBottom(() => {
    setShown((prev) => Math.min(prev + PAGE_SIZE, items.length));
  });

  const filters = meta.data?.filters?.length ? meta.data.filters : FALLBACK_FILTERS;
  const stale = isStale(meta.data?.data_lag_days ?? null);
  const visible = items.slice(0, shown);

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
      {!board.loading && board.error ? <ErrorBlock message={board.error} onRetry={board.reload} /> : null}
      {!board.loading && !board.error && !items.length ? (
        <EmptyBlock title="这个筛选下暂时没有梗" body="换个筛选，或去梗库看完整列表。" />
      ) : null}

      {!board.loading && items.length ? (
        <View>
          {filter === "all" ? <Featured items={items} /> : null}
          <Text className="list-title">今日热榜</Text>
          {visible.map((item, index) => (
            <MemeCardView key={item.id} meme={item} rank={index} onOpen={open} />
          ))}
          {shown < items.length ? (
            <View className="more-tip">还有 {items.length - shown} 个，继续下滑加载</View>
          ) : (
            <View className="more-tip">
              已经到底了 · 另有 {board.data?.gated_out ?? 0} 个过气或只剩残值的梗没上热榜，可在梗库查看
            </View>
          )}
        </View>
      ) : null}
    </View>
  );
}
