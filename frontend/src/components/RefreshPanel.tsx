/**
 * 刷新面板：手动触发一次"发现新梗 + 刷新老梗 + 重算"，并如实说清上次刷新的结果。
 *
 * 放在梗管理页：这是运维动作，不该出现在读者看的首页/详情页。
 * 刷新是慢操作（几十个梗逐个查 B 站，几分钟起步），所以后端立刻返回 202，
 * 这里每 5 秒轮一次状态；跑完顺手让列表刷新，否则用户看到的还是旧数。
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/api/client";
import type { RefreshStatus } from "@/types/api";

function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  const text = iso.replace("T", " ").slice(5, 16);
  return text || iso;
}

export function RefreshPanel({ onDone }: { onDone?: () => void }) {
  const [status, setStatus] = useState<RefreshStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const wasRunning = useRef(false);

  const poll = useCallback(async () => {
    try {
      const next = await api.refreshStatus();
      setStatus(next);
      if (wasRunning.current && !next.running) onDone?.();
      wasRunning.current = next.running;
      return next;
    } catch {
      return null;
    }
  }, [onDone]);

  useEffect(() => {
    poll();
  }, [poll]);

  // 只在跑着的时候轮询，空闲时不养后台请求
  useEffect(() => {
    if (!status?.running) return undefined;
    const timer = setInterval(() => {
      poll();
    }, 5000);
    return () => clearInterval(timer);
  }, [status?.running, poll]);

  const trigger = async (full: boolean) => {
    setBusy(true);
    setNote("");
    try {
      const result = await api.refreshNow(full);
      wasRunning.current = true;
      setNote(result.ok ? "已开始，稍后自动更新状态" : result.reason || "没触发起来");
      if (result.ok) await poll();
    } catch (error) {
      setNote((error as Error).message || "触发失败");
      await poll();
    } finally {
      setBusy(false);
    }
  };

  const running = Boolean(status?.running);
  const last = status?.last;
  const real = status?.data_source === "bilibili";
  const schedule = status?.schedule;

  return (
    <section className="card mb-6 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-[17px] font-bold">数据刷新</h2>
        <span className={`chip px-2.5 py-1 text-[11px] ${running ? "bg-brand-soft text-brand" : "bg-rail text-ink-mute"}`}>
          {running ? "正在刷新…" : "空闲"}
        </span>
        <span className={`chip px-2.5 py-1 text-[11px] ${schedule?.enabled ? "bg-go/10 text-go" : "bg-rail text-ink-mute"}`}>
          {schedule?.enabled ? `自动：每天 ${schedule.at}` : "自动刷新未启用"}
        </span>
        <span className="ml-auto flex gap-2">
          <button
            type="button"
            className="rounded-full bg-brand px-4 py-1.5 text-[13px] font-bold text-white disabled:opacity-50"
            disabled={busy || running || !real}
            onClick={() => trigger(false)}
          >
            立即刷新（补昨天）
          </button>
          <button
            type="button"
            className="rounded-full bg-rail px-4 py-1.5 text-[13px] font-bold text-ink-soft disabled:opacity-50"
            disabled={busy || running || !real}
            title="重看整个 30 天窗口：老日子的头部播放量会随时间涨，每周做一次校准"
            onClick={() => trigger(true)}
          >
            全窗口重采
          </button>
        </span>
      </div>

      {/* 说明性文字全部收进折叠区：这一屏的主角是状态和按钮，不是三段口径解释 */}
      <details className="mt-3 rounded-tile border border-line bg-rail px-3.5 py-2.5">
        <summary className="cursor-pointer list-none text-[13px] font-semibold text-ink-soft">
          刷新做什么 · 退出码含义 · 定时任务
        </summary>
        <div className="mt-2 space-y-2 text-[12px] leading-relaxed text-ink-mute">
          <p>
            刷新做三件事：翻两位 UP 主的近期投稿发现新梗（并集入池）→ 采集数据 → 重算热度、
            生命周期与赶梗判断。默认只补"昨天"那一天（每个梗一次请求），全窗口重采会把 30 天
            逐个日期重看一遍，请求量约 30 倍，建议一周一次。同一天只保留更好的一次观测，
            所以重复刷新不会把数据越刷越薄。
          </p>
          {last?.exit_code ? (
            <p>
              上次退出码 {last.exit_code}：1 = 有梗被拒或一个没采到，2 = 数据源不可用，
              4 = 连续被 B 站硬风控拦下、采集中途中止（换小号 Cookie 或把
              COLLECT_REQUEST_GAP 调大再跑）。3 = 当时已有刷新在跑，只打在终端、不写进报告。
              详情见 docs/data/refresh-report.md
            </p>
          ) : null}
          {schedule?.enabled ? (
            <p>
              定时任务：每天 {schedule.at} 自动增量
              {schedule.full_weekday >= 0
                ? `，${schedule.weekday_names?.[schedule.full_weekday] ?? "周一"}做全窗口校准`
                : "（未设周校准）"}
              {schedule.discovery ? "，含发现新梗" : "，不跑发现层"}。
              进程不常驻的话请改用系统计划任务：
              <code>python -m app.scripts.daily_refresh --trigger 定时</code>
            </p>
          ) : null}
        </div>
      </details>

      {last ? (
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[13px] sm:grid-cols-4">
          <div>
            <div className="text-ink-faint">上次刷新</div>
            <div className="font-semibold">
              {when(last.at)} · {last.trigger}
              {last.mode === "full" ? " · 全窗口" : " · 增量"}
            </div>
          </div>
          <div>
            <div className="text-ink-faint">采集结果</div>
            <div className="font-semibold">
              {last.collected ?? "—"} / {last.targets ?? "—"} 个梗成功
            </div>
          </div>
          <div>
            <div className="text-ink-faint">被拒 / 跳过演示</div>
            <div className="font-semibold">
              {last.failed ?? 0} 个 / {last.skipped_demo ?? 0} 个
            </div>
          </div>
          <div>
            <div className="text-ink-faint">统计截至</div>
            <div className="font-semibold">{when(last.data_through)}</div>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-[13px] text-ink-faint">
          还没有刷新记录。跑过一次后这里会显示时间、触发方式与结果。
        </p>
      )}

      {!real ? (
        <p className="mt-2 text-[13px] text-brand">
          当前数据源不是真实 B 站数据，刷新按钮不可用；演示模式请用 seed_data 重新生成。
        </p>
      ) : null}
      {note ? <p className="mt-2 text-[13px] text-flare">{note}</p> : null}
    </section>
  );
}
