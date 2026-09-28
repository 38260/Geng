import { Input, Text, View } from "@tarojs/components";
import Taro, { usePullDownRefresh, useShareAppMessage } from "@tarojs/taro";
import { useState } from "react";

import { apiBase, getMeta, setApiBase, DEFAULT_API_BASE } from "@/api/client";
import { ErrorBlock, LoadingBlock } from "@/components/States";
import { useFavorites } from "@/hooks/useFavorites";
import { useLoad } from "@/hooks/useLoad";
import { freshnessText, isStale } from "@/utils/format";

import "./index.scss";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View className="kv">
      <Text className="kv-label">{label}</Text>
      <Text className="kv-value">{value}</Text>
    </View>
  );
}

export default function About() {
  const meta = useLoad(() => getMeta(), []);
  const favorites = useFavorites();
  const [base, setBase] = useState(apiBase());

  useShareAppMessage(() => ({ title: "赶梗潮：这些数字是怎么算出来的", path: "/pages/about/index" }));

  usePullDownRefresh(async () => {
    await meta.reload();
    Taro.stopPullDownRefresh();
  });

  const apply = () => {
    setApiBase(base);
    Taro.showToast({ title: "已保存，正在重新加载", icon: "none" });
    meta.reload();
  };

  const t = meta.data?.transparency;
  const last = meta.data?.refresh?.last;
  const schedule = meta.data?.refresh?.schedule;
  const refreshLine = last
    ? `${(last.at || '').replace("T", " ").slice(5, 16)} · ${last.trigger}${
        last.mode === "full" ? "（全窗口）" : "（增量）"
      } · ${last.collected ?? "—"}/${last.targets ?? "—"} 个梗`
    : "还没有刷新记录";
  const autoLine = schedule?.enabled
    ? `每天 ${schedule.at} 自动跑${
        schedule.full_weekday >= 0 ? `，${schedule.weekday_names?.[schedule.full_weekday] ?? "周一"}做全窗口校准` : ""
      }`
    : "未启用（只在后台手动触发）";
  const stale = isStale(meta.data?.data_lag_days ?? null);

  return (
    <View className="shell">
      <View className="card">
        <Text className="about-title">{meta.data?.app_name || "赶梗潮"}</Text>
        <Text className="about-sub">
          只看 B 站 · 数据源 {meta.data?.data_source === "bilibili" ? "真实采集" : "演示数据"} · 版本{" "}
          {meta.data?.version || "—"}
        </Text>
        <Text className={`about-fresh${stale ? " about-fresh-stale" : ""}`}>
          {freshnessText(meta.data?.data_through ?? null, meta.data?.data_lag_days ?? null)}
        </Text>
      </View>

      {meta.loading ? <LoadingBlock count={2} /> : null}
      {meta.error ? <ErrorBlock message={meta.error} onRetry={meta.reload} /> : null}

      {meta.data ? (
        <View className="card">
          <Text className="sec">现在有多少</Text>
          <Row label="热榜（还在被做的）" value={`${meta.data.certified_count} 个`} />
          <Row label="梗库（可分析的总数）" value={`${meta.data.library_count ?? 0} 个`} />
          <Row label="被上榜门槛挡掉" value={`${meta.data.gated_out ?? 0} 个`} />
          <Row label="候选池（两位 UP 都没做过）" value={`${meta.data.candidate_count} 个`} />
          <Row label="统计窗口" value={`${meta.data.window_days} 天`} />
        </View>
      ) : null}

      <View className="card">
        <Text className="sec">数据什么时候更新</Text>
        <Row
          label="统计截至"
          value={meta.data ? `${meta.data.data_through ?? '未知'}（滞后 ${meta.data.data_lag_days ?? '—'} 天）` : "—"}
        />
        <Row label="上次刷新" value={refreshLine} />
        <Row label="自动刷新" value={autoLine} />
        <Text className="para faint">
          刷新会翻两位 UP 主的近期投稿发现新梗、补采数据、重算热度与赶梗判断。
          默认只补"昨天"那一天，每周做一次 30 天全窗口校准；同一天只保留更好的一次观测，
          所以重复刷新不会把数据越刷越薄。小程序这一端是只读的，
          手动刷新在后台的梗管理页触发。
        </Text>
      </View>

      {t ? (
        <View className="card">
          <Text className="sec">口径怎么定的</Text>
          <Text className="para">{t.certification_rule || "准入：任一 UP 主介绍过即入池。"}</Text>
          <Text className="para">{t.board_gate || "热榜只收还在被做的梗。"}</Text>
          <Text className="para">{t.hotness_algorithm}</Text>
          <Text className="para">{t.lifecycle_algorithm}</Text>
          <Text className="para">{t.sampling || "抽样口径见后台说明。"}</Text>
          {t.coverage_rule ? <Text className="para">{t.coverage_rule}</Text> : null}
          <Text className="para">{t.llm_role}</Text>
        </View>
      ) : null}

      <View className="card">
        <Text className="sec">我的收藏（{favorites.count} 个）</Text>
        <Text className="para faint">
          V1 不做账号体系，收藏只写在这台设备的本地存储里：不上传、不跨端同步，
          换手机或清缓存就没了。梗库页顶部可以只看收藏，热度数字仍是实时算的。
        </Text>
        {favorites.items.length ? (
          <View>
            {favorites.items.map((row) => (
              <View className="fav-row" key={row.id}>
                <Text className="fav-name">{row.name}</Text>
                <Text className="faint">{row.at}</Text>
              </View>
            ))}
            <Text className="fav-clear" onClick={favorites.clear}>
              清空本机收藏
            </Text>
          </View>
        ) : (
          <Text className="para">还没有收藏。进任意一个梗的详情页点「收藏」即可。</Text>
        )}
      </View>

      <View className="card">
        <Text className="sec">后端地址（调试用）</Text>
        <Text className="para faint">
          默认 {DEFAULT_API_BASE}。真机调试要填电脑局域网 IP；正式上线必须是 https 且在小程序后台配合法域名。
        </Text>
        <View className="base-row">
          <Input className="base-input" value={base} type="text" onInput={(e) => setBase(e.detail.value)} />
          <Text className="base-btn" onClick={apply}>
            保存
          </Text>
        </View>
      </View>

      <View className="card">
        <Text className="sec">这个产品不做什么</Text>
        <Text className="para">
          V1 只做 B 站一个平台，不做多平台聚合；没有账号、登录、收藏同步；不做未来预测——
          热度、生命周期、赶梗结论全部由算法从已发生的数据里算出来，AI 只负责把结论说成人话，
          不能改任何一个数字。演示数据一律标「演示数据」，不冒充真实抓取结果。
        </Text>
      </View>
    </View>
  );
}
