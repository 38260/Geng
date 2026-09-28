import { Input, Text, View } from "@tarojs/components";
import Taro, { usePullDownRefresh, useReachBottom } from "@tarojs/taro";
import { useRef, useState } from "react";

import { listMemes } from "@/api/client";
import { MemeRow } from "@/components/MemeCardView";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/States";
import { usePaged } from "@/hooks/usePaged";

import "./index.scss";

const SORTS = [
  { key: "hotness", label: "按热度" },
  { key: "growth", label: "按增长" },
  { key: "discussion", label: "按讨论" },
  { key: "name", label: "按名称" },
];

export default function Library() {
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("hotness");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 输入停顿 400ms 才发请求：小程序里每敲一个字就打一次接口会被限流
  const onInput = (value: string) => {
    setInput(value);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setSearch(value.trim()), 400);
  };

  const board = usePaged(
    (offset, limit) => listMemes({ scope: "all", search, sort, limit, offset }),
    [search, sort],
  );

  usePullDownRefresh(async () => {
    await board.refresh();
    Taro.stopPullDownRefresh();
  });
  useReachBottom(() => {
    board.loadMore();
  });

  return (
    <View className="shell">
      <View className="card search-card">
        <Input
          className="search-input"
          value={input}
          type="text"
          confirmType="search"
          placeholder="搜梗名、别名或关键词"
          onInput={(event) => onInput(event.detail.value)}
        />
        {input ? (
          <Text className="search-clear" onClick={() => onInput("")}>
            清空
          </Text>
        ) : null}
      </View>

      <View className="pills">
        {SORTS.map((item) => (
          <Text
            key={item.key}
            className={`pill${sort === item.key ? " pill-on" : ""}`}
            onClick={() => setSort(item.key)}
          >
            {item.label}
          </Text>
        ))}
      </View>

      <Text className="lib-note">
        梗库是完整口径：包含没上热榜的过气梗与只剩残值的梗，共 {board.total || "—"} 条。
        热榜只留还在被做的，所以这里比首页多。
      </Text>

      {board.loading ? <LoadingBlock count={4} /> : null}
      {!board.loading && board.error ? <ErrorBlock message={board.error} onRetry={board.refresh} /> : null}
      {!board.loading && !board.error && !board.items.length ? (
        <EmptyBlock
          title={search ? `没搜到「${search}」` : "梗库是空的"}
          body={search ? "试试别名或关键词，比如「黄豆」「宗主」。" : "后端还没有可分析的梗，先在后台跑一轮采集。"}
        />
      ) : null}

      {board.items.length ? (
        <View className="lib-list">
          {board.items.map((meme) => (
            <MemeRow
              key={meme.id}
              meme={meme}
              onOpen={(id) => Taro.navigateTo({ url: `/pages/detail/index?id=${id}` })}
            />
          ))}
          {board.loadingMore ? <View className="more-tip">加载中…</View> : null}
          {!board.loadingMore && board.items.length >= board.total ? (
            <View className="more-tip">已经到底了</View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
