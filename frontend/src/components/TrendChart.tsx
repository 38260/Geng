import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

import { useMeta } from "@/hooks/useAppData";
import type { TrendPoint } from "@/types/api";
import { BAR_EMPTY, BAR_UNOBSERVED, STAGE_HEX, shortDate } from "@/utils/format";

echarts.use([BarChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer]);

/**
 * 热度趋势柱状图 —— 与梗史馆的逐日轨迹共用同一套视觉语言。
 *
 * 每根柱子是一天，颜色是**那天所处的生命周期阶段**。阶段由后端按管线口径逐日复算
 * （`app/services/meme/history.py::stage_path_for_rows`），与梗史馆、与右上角徽章同源，
 * 所以不会出现"同一个阶段在这一页和那一页颜色不一样"。
 *
 * 两种"没东西"的日子画成浅色短柱，**绝不当成"当天热度 0"读**：
 * 更浅的一档 = 观测到了但当天没有相关内容，最浅的一档 = 这天接口没给数据（未观测）。
 */
export function TrendChart({ points, height = 230 }: { points: TrendPoint[]; height?: number }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const { meta } = useMeta();

  // 阶段 key → 中文名。后端 meta 里就带着这份对照表，别在前端再抄一份中文
  // （抄了就会和「上升期 / 平稳期」这些说法漂移）。
  const stageLabel = useMemo(() => {
    const rows = meta?.lifecycle_stages ?? [];
    return new Map(rows.map((row) => [row.key as string, row.label]));
  }, [meta]);

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
    // 柱子高度：未观测 / 零活动都给 0，靠 barMinHeight 画出那根 3px 短柱，
    // 再用颜色区分"没观测"与"观测到但没内容"。
    const data = points.map((point) => {
      if (point.observed === false) {
        return { value: 0, itemStyle: { color: BAR_UNOBSERVED } };
      }
      if (point.hotness <= 0) {
        return { value: 0, itemStyle: { color: BAR_EMPTY } };
      }
      // stage 可能为空（老数据 / 后端没复算出来）——退回"数据不足"那档灰，
      // 不要瞎猜一个阶段色：颜色本身就是结论，猜错比留灰更糟。
      const stage = point.stage || "insufficient";
      return { value: point.hotness, itemStyle: { color: STAGE_HEX[stage] } };
    });
    const peakIndex = points.reduce(
      (best, point, index) => (point.hotness > (points[best]?.hotness ?? -1) ? index : best),
      -1,
    );
    const hasPeak = peakIndex >= 0 && points[peakIndex].hotness > 0;

    chart.setOption(
      {
        animationDuration: 420,
        grid: { left: 34, right: 16, top: 18, bottom: 26 },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow", shadowStyle: { color: "rgba(13,138,254,0.06)" } },
          backgroundColor: "#FFFFFF",
          borderColor: "#ECF0F6",
          borderWidth: 1,
          textStyle: { color: "#181818", fontSize: 12 },
          formatter: (params: unknown) => {
            const list = params as { dataIndex: number }[];
            const index = list[0]?.dataIndex ?? 0;
            const point = points[index];
            if (!point) return "";
            const head = `<b>${point.date.slice(5)}</b>`;
            if (point.observed === false) {
              return [head, "这天接口没返回结果（不是当天没人做这个梗）"].join("<br/>");
            }
            const stage = point.stage ? stageLabel.get(point.stage) ?? point.stage : "";
            return [
              head,
              `热度 ${point.hotness.toFixed(1)}${stage ? ` · ${stage}` : ""}`,
              `视频 ${point.video_count} · UP主 ${point.creator_count}`,
              `讨论量 ${point.discussion.toLocaleString("en-US")}`,
            ].join("<br/>");
          },
        },
        xAxis: {
          type: "category",
          data: dates,
          axisLine: { lineStyle: { color: "#ECF0F6" } },
          axisTick: { show: false },
          axisLabel: {
            color: "#B4BCCB",
            fontSize: 11,
            interval: Math.max(0, Math.floor(dates.length / 7) - 1),
          },
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
            type: "bar",
            data,
            barMaxWidth: 28,
            // 0 值的柱子也要看得见：梗史馆里就是一根 3px 的短柱，不是"什么都没有"
            barMinHeight: 3,
            itemStyle: { borderRadius: [2, 2, 0, 0] },
            // 峰值那一天立一根竖线，和梗史馆的标记对齐
            markLine: hasPeak
              ? {
                  silent: true,
                  symbol: "none",
                  label: { show: false },
                  lineStyle: { color: "rgba(0,2,20,0.22)", width: 2, type: "solid" },
                  data: [{ xAxis: dates[peakIndex] }],
                }
              : undefined,
          },
        ],
      },
      { notMerge: true },
    );
  }, [points, stageLabel]);

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
