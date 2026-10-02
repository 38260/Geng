"""梗史馆报告：近 N 天入池的梗，逐个摊开热度轨迹与周期画像。

    python -m app.scripts.history_report                    # 默认 90 天，按峰值热度排
    python -m app.scripts.history_report --days 90 --sort peak
    python -m app.scripts.history_report --cycle pulse      # 只看脉冲型的

输出：终端表格 + ``docs/data/meme-history.md``。

这份报告与页面（``/history``）读的是同一个服务
:func:`app.services.meme.history.history_payload`，所以不会出现
"报告里 12 个脉冲型、页面上 9 个"这种对不上的情况。

所有数字都由算法从逐日序列算出；LLM 不参与，本脚本也不做任何推断。
"""

from __future__ import annotations

import argparse
import sys

from app.config import PROJECT_DIR, get_logger
from app.models import SessionLocal
from app.services.meme.history import CYCLE_LABELS, SORTS, history_payload

log = get_logger("history-report")

# 文本热度条：8 档，够看出形状又不至于在 Markdown 里糊成一片
_BLOCKS = "▁▂▃▄▅▆▇█"


def _bar(values: list[float]) -> str:
    """把逐日热度画成一行文本条；没观测到的日子用空格留缺口。"""
    if not values:
        return ""
    top = max(values) or 1.0
    out: list[str] = []
    for value in values:
        if value <= 0:
            out.append("·")
            continue
        index = min(len(_BLOCKS) - 1, int(value / top * (len(_BLOCKS) - 1)))
        out.append(_BLOCKS[index])
    return "".join(out)


def build_markdown(report: dict) -> str:
    summary = report["summary"]
    items = report["items"]
    lines = [
        f"# 梗史馆 · 最近 {report['days']} 天入池的梗",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 入池规则：{report['rule']}",
        f"- 命中 {summary['pool']} 只，本页列出 {summary['returned']} 只"
        f"（排序：{report['sort_label']}）",
        f"- 观测窗：{summary['obs_from']} ~ {summary['obs_to']}"
        f"（{summary['window_days']} 天）"
        + (f"，其中 {summary['truncated_count']} 只入池早于观测窗起点，周期左端被截断"
           if summary["truncated_count"] else ""),
        "",
        "## 周期分布",
        "",
        "| 周期类型 | 数量 | 判定口径 |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {item['emoji']} {item['label']} | {item['count']} | {item['hint']} |"
        for item in summary["by_cycle"]
    ]
    lines += ["", "## 参考值", ""]
    lines += [
        f"- 距峰天数（中位数 / 均值）：{summary['median_days_since_peak']} / "
        f"{summary['avg_days_since_peak']}",
        f"- 爬升天数（均值）：{summary['avg_rise_days']}",
        f"- 半衰期（均值，仅统计已腰斩的）：{summary['avg_half_life_days']}",
        f"- 峰值最高：{summary['peak_leader']['name']} "
        f"{summary['peak_leader']['peak_hotness']}（{summary['peak_leader']['peak_date']}）"
        if summary["peak_leader"] else "- 峰值最高：无",
        "",
        "## 逐梗明细",
        "",
        "| 梗 | 入池日 | 认证 | 周期 | 峰值 | 峰值日 | 当前 | 距峰 | 半衰期 | 观测 | 热度轨迹 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        hotness = [point["hotness"] for point in item["spark"]]
        lines.append(
            "| {name} | {admitted} | {cert} | {cycle} | {peak} | {peak_date} | {current} | "
            "{since} | {half} | {obs}/{span} | `{bar}` |".format(
                name=item["name"],
                admitted=(item["admitted_at"] or "—")[:10],
                cert=item["cert_label"],
                cycle=f"{item['cycle_emoji']} {item['cycle_label']}",
                peak=item["peak_hotness"],
                peak_date=(item["peak_date"] or "—")[5:],
                current=item["current_hotness"],
                since="—" if item["days_since_peak"] is None else f"{item['days_since_peak']}天",
                half="未腰斩" if item["half_life_days"] is None else f"{item['half_life_days']}天",
                obs=item["observed_days"],
                span=item["window_days"],
                bar=_bar(hotness),
            )
        )
    lines += [
        "",
        "> 口径：热度为赶梗潮自定义指数（0-100）。轨迹条一格一天，"
        "`·` 表示那天接口给了空壳（未观测），**不当作零活动**。",
        "> 半衰期 = 从峰值日起热度首次跌到峰位一半所用的天数；"
        "「未腰斩」表示到观测窗末尾仍在一半以上，不是缺数据。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 梗史馆报告")
    parser.add_argument("--days", type=int, default=90, help="入池窗口（默认 90 天）")
    parser.add_argument("--window", type=int, default=0, help="观测窗天数，0 = 用满库里序列")
    parser.add_argument("--cycle", default="", help=f"周期类型：{' | '.join(CYCLE_LABELS)}")
    parser.add_argument("--cert", default="", choices=["", "double", "single"])
    parser.add_argument("--sort", default="peak", choices=sorted(SORTS))
    parser.add_argument("--out", default="docs/data/meme-history.md")
    args = parser.parse_args(argv)

    session = SessionLocal()
    try:
        report = history_payload(
            session,
            days=args.days,
            window_days=args.window or None,
            cycle=args.cycle,
            cert=args.cert,
            sort=args.sort,
        )
    finally:
        session.close()

    summary = report["summary"]
    print(
        f"入池 {summary['pool']} 只 / 列出 {summary['returned']} 只；"
        f"观测窗 {summary['obs_from']} ~ {summary['obs_to']}（{summary['window_days']} 天）"
    )
    for item in summary["by_cycle"]:
        print(f"  {item['emoji']} {item['label']}：{item['count']}")
    if summary["peak_leader"]:
        leader = summary["peak_leader"]
        print(f"  峰值最高：{leader['name']} {leader['peak_hotness']}（{leader['peak_date']}）")

    out_path = PROJECT_DIR / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 重复运行要能覆盖：Windows 上被占用时 open('w') 会直接抛错，这里先删掉再写。
    # newline='\\n' 是刻意的：仓库 .gitattributes 是 eol=lf，默认的文本模式会在
    # Windows 上把每行都翻成 CRLF，生成物跟仓库里其它 md 不一致。
    if out_path.exists():
        out_path.unlink()
    out_path.write_text(build_markdown(report), encoding="utf-8", newline="\n")
    print(f"已写出：{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
