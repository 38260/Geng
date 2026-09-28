"""跑一次真实采集（默认仍然只跑演示数据）。

    python -m app.scripts.collect_data --source bilibili --limit 3
    python -m app.scripts.collect_data --source bilibili --meme-id 1

B 站的搜索接口对匿名请求带风控，遇到 -352/412 时脚本会直接说明
"需要在 backend/.env 填 BILI_COOKIE"，不会伪造数据。
"""

from __future__ import annotations

import argparse
import sys

from app.config import get_logger, settings
from app.services.pipeline import collect_all

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 数据采集")
    parser.add_argument("--source", choices=["mock", "bilibili"], default=settings.data_source)
    parser.add_argument("--days", type=int, default=settings.analysis_window_days)
    parser.add_argument("--limit", type=int, default=None, help="只采前 N 个梗，避免一次打太多请求")
    parser.add_argument("--meme-id", type=int, action="append", help="只采指定梗，可重复")
    parser.add_argument(
        "--scope", choices=["real", "all", "library", "board"], default="real",
        help="real=跳过纯演示梗（默认）| all=全部 | library=已有指标快照 | board=还在热榜上的",
    )
    args = parser.parse_args(argv)

    result = collect_all(
        args.source,
        meme_ids=args.meme_id,
        limit=args.limit,
        window_days=args.days,
        scope=args.scope,
    )

    print(f"数据源：{result['source']}  可用：{'是' if result['ok'] else '否'}")
    print(f"探测结果：{result['reason']}")
    if not result["ok"]:
        print("已保留原有数据，未做任何修改。")
        return 2

    print(f"采集范围：{result.get('targets', '?')} 个梗（{result.get('scope')}）— {result.get('scope_note', '')}")
    print(
        f"采集完成：成功 {result['collected']} 个梗 / 窗口内无结果 {result['empty']} 个 / "
        f"被拒 {result['failed']} 个，共写入视频 {result['videos']} 条"
    )
    if result["collected"] == 0:
        print("一个都没采到，通常是风控或 Cookie 问题；页面会继续使用现有数据。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
