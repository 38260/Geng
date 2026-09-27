import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, MarkPointComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

import type { TrendPoint } from "@/types/api";
import { shortDate } from "@/utils/format";

echarts.use([LineChart, GridComponent, TooltipComponent, MarkPointComponent, CanvasRenderer]);

/**
 * 热度趋势折线图。
 *
 * 保持参考图的克制：单条珊瑚色线 + 淡渐变面积，不做 BI 大屏那种多轴多系列。
 */
export function TrendChart({
  points,
  height = 230,
}: {
  points: TrendPoint[];
  height?: number;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = echarts.init(host);
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(host);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const dates = points.map((point) => shortDate(point.date));
    const values = points.map((point) => point.hotness);
    const peakIndex = values.length ? values.indexOf(Math.max(...values)) : -1;

    chart.setOption(
      {
        animationDuration: 420,
        grid: { left: 34, right: 16, top: 18, bottom: 26 },
        tooltip: {
          trigger: "axis",
          backgroundColor: "#FFFFFF",
          borderColor: "#ECF0F6",
          borderWidth: 1,
          textStyle: { color: "#181818", fontSize: 12 },
          formatter: (params: unknown) => {
            const list = params as { dataIndex: number; axisValue: string }[];
            const index = list[0]?.dataIndex ?? 0;
            const point = points[index];
            if (!point) return "";
            return [
              `<b>${point.date.slice(5)}</b>`,
              `热度 ${point.hotness.toFixed(1)}`,
              `视频 ${point.video_count} · UP主 ${point.creator_count}`,
              `讨论量 ${point.discussion.toLocaleString("en-US")}`,
            ].join("<br/>");
          },
        },
        xAxis: {
          type: "category",
          data: dates,
          boundaryGap: false,
          axisLine: { lineStyle: { color: "#ECF0F6" } },
          axisTick: { show: false },
          axisLabel: { color: "#B4BCCB", fontSize: 11, interval: Math.max(0, Math.floor(dates.length / 7) - 1) },
        },
        yAxis: {
          type: "value",
          min: 0,
          max: 100,
          interval: 25,
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: "#F2F5FA" } },
          axisLabel: { color: "#B4BCCB", fontSize: 11 },
        },
        series: [
          {
            type: "line",
            data: values,
            smooth: 0.35,
            symbol: "circle",
            symbolSize: 6,
            showSymbol: values.length <= 31,
            lineStyle: { width: 2.6, color: "#FF6B5F" },
            itemStyle: { color: "#FF6B5F", borderColor: "#fff", borderWidth: 1.5 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "rgba(255,107,95,0.26)" },
                { offset: 1, color: "rgba(255,107,95,0.02)" },
              ]),
            },
            markPoint:
              peakIndex >= 0 && values[peakIndex] > 0
                ? {
                    symbol: "circle",
                    symbolSize: 9,
                    itemStyle: { color: "#FF6B5F", borderColor: "#fff", borderWidth: 2 },
                    label: { show: false },
                    data: [{ name: "peak", coord: [dates[peakIndex], values[peakIndex]] }],
                  }
                : undefined,
          },
        ],
      },
      { notMerge: true },
    );
  }, [points]);

  if (!points.length) {
    return (
      <div
        className="grid place-items-center rounded-tile border border-dashed border-line text-[13px] text-ink-faint"
        style={{ height }}
      >
        暂无趋势数据
      </div>
    );
  }

  return <div ref={hostRef} style={{ height, width: "100%" }} />;
}
