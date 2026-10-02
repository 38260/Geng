"""给库里所有入池梗生成「这个梗是什么」的 AI 摘要（写进 ``ai_insights`` 缓存）。

详情接口只读缓存，所以要先把缓存填上——这个脚本就是干这个的。

    python -m app.scripts.generate_intros                 # 只补还没有的（幂等）
    python -m app.scripts.generate_intros --force         # 全部重算（改了提示词才用）
    python -m app.scripts.generate_intros --limit 5       # 先拿 5 个试水
    python -m app.scripts.generate_intros --name 冰冰冰

每个梗一次模型调用，所以默认串行 + 间隔 ``--gap`` 秒，不打爆上游。
结束时报四档结果：生成成功 / 模型自认材料不足 / 调用失败 / 未配置 Key。

被拦下的那些**不会写进正文**：``check_grounded`` 一旦发现材料里找不到的事实锚点，
整段作废并记成 ``status=error``，页面继续显示原文摘录——宁可信息少，也不编。
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import select

from app.config import get_logger
from app.models import Meme, MemeStatus, SessionLocal
from app.services.llm.config import load_config
from app.services.meme.certification import admitted
from app.services.meme.query import generate_intro

log = get_logger("generate-intros")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 批量生成 AI 梗介绍")
    parser.add_argument("--limit", type=int, default=0, help="最多处理几个（0 = 全部）")
    parser.add_argument("--name", default="", help="只处理名字里含这个词的梗")
    parser.add_argument("--force", action="store_true", help="忽略缓存，全部重算")
    parser.add_argument(
        "--only-failed",
        action="store_true",
        help="只重试还没有可用摘要的（缺缓存或上一次被拦下）——失败居多时用它省时间",
    )
    parser.add_argument("--gap", type=float, default=0.8, help="两次调用之间的间隔秒数")
    args = parser.parse_args(argv)

    config = load_config()
    if not config.is_configured:
        print("没配 LLM_API_KEY，无法生成。请在 backend/.env 里填 LLM_API_KEY 后重试。")
        return 2

    session = SessionLocal()
    ok = insufficient = failed = 0
    try:
        memes = [
            meme
            for meme in session.scalars(
                select(Meme).where(Meme.status == MemeStatus.CERTIFIED).order_by(Meme.id)
            )
            if admitted(meme)
        ]
        if args.name:
            memes = [meme for meme in memes if args.name in meme.name]
        if args.only_failed:
            from app.models import AIInsight, InsightStatus
            from app.services.meme.ai_intro import INTRO_AI_KIND

            done = {
                row[0]
                for row in session.execute(
                    select(AIInsight.meme_id).where(
                        AIInsight.kind == INTRO_AI_KIND,
                        AIInsight.status == InsightStatus.OK,
                    )
                )
            }
            memes = [meme for meme in memes if meme.id not in done]
        if args.limit:
            memes = memes[: args.limit]
        if not memes:
            print("没有可处理的梗。")
            return 0

        print(f"共 {len(memes)} 个梗，模型 {config.model}，开始生成…\n")
        for index, meme in enumerate(memes, start=1):
            result = generate_intro(session, meme, refresh=args.force)
            if result and result.get("text"):
                ok += 1
                text = result["text"]
                print(f"  [{index}/{len(memes)}] ✓ {meme.name}（{len(text)} 字）{text[:60]}…")
            else:
                # 两种"没结果"要分开报：材料不足是正常结果，被拦下/调用失败是故障。
                # 必须按 kind 过滤——同一个梗可能还留着趋势解释那边的 error 行，
                # 不过滤就会把别人的失败原因安到介绍头上（实测踩过）。
                from app.models import AIInsight, InsightStatus
                from app.services.meme.ai_intro import INTRO_AI_KIND

                error = session.scalar(
                    select(AIInsight).where(
                        AIInsight.meme_id == meme.id,
                        AIInsight.kind == INTRO_AI_KIND,
                        AIInsight.status == InsightStatus.ERROR,
                    )
                )
                if error is not None:
                    failed += 1
                    print(f"  [{index}/{len(memes)}] ✗ {meme.name}：未通过核对 → "
                          f"{(error.result or {}).get('reason', '')[:80]}")
                else:
                    insufficient += 1
                    print(f"  [{index}/{len(memes)}] – {meme.name}：材料撑不起来，界面退回原文摘录")
            if args.gap:
                time.sleep(args.gap)
    finally:
        session.close()

    print(
        f"\n完成：生成 {ok} / 材料不足 {insufficient} / 被拦下 {failed}；"
        f"共 {ok + insufficient + failed} 个。"
    )
    if failed:
        print("被拦下的那些在详情页会继续显示证据原文，不会露出编造内容。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
