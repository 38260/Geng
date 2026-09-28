import { Text, View } from "@tarojs/components";

import type { TrendPoint } from "@/types/api";
import { compact, dayShort, normalizeSeries } from "@/utils/format";

export type TrendMetric = "hotness" | "view" | "discussion";

const METRIC_LABEL: Record<TrendMetric, string> = {
  hotness: "热度（0-100 自定义指数）",
  view: "头部内容播放量",
  discussion: "讨论量（评论 + 弹幕）",
};

/**
 * 趋势图用 CSS 柱子画，不引 ECharts/canvas：
 * canvas 在 weapp 与 h5 两套实现差异大，柱子两边渲染一致，
 * 才能拿 H5 截图当 weapp 的视觉证据。
 */
export function TrendBars({
  points,
  metric = "hotness",
  color = "#FB3A5E",
}: {
  points: TrendPoint[];
  metric?: TrendMetric;
  color?: string;
}) {
  if (!points.length) {
    return <View className="trend-empty">还没有足够的每日数据画曲线</View>;
  }
  const heights = normalizeSeries(points.map((point) => Number(point[metric] || 0)));
  const last = points[points.length - 1];
  const first = points[0];
  const peak = Math.max(...points.map((point) => Number(point[metric] || 0)));

  return (
    <View>
      <View className="trend-bars">
        {points.map((point, index) => (
          <View className="trend-col" key={point.date}>
            <View
              className="trend-bar"
              style={{
                height: `${Math.round(heights[index] * 100)}%`,
                background: index === points.length - 1 ? color : `${color}55`,
              }}
            />
          </View>
        ))}
      </View>
      <View className="row-between trend-axis">
        <Text>{dayShort(first.date)}</Text>
        <Text>峰值 {metric === "hotness" ? Math.round(peak) : compact(peak)}</Text>
        <Text>{dayShort(last.date)}</Text>
      </View>
      <Text className="faint trend-caption">
        {METRIC_LABEL[metric]} · 共 {points.length} 天
      </Text>
    </View>
  );
}
