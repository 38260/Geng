"""梗元数据的人工维护：封面、介绍、别名、关键词。

边界很硬：这里只改"怎么展示、怎么被搜到"，绝不碰热度、生命周期、赶梗结论——
那些是算法从数据里算出来的，人工改一次就等于造假一次。所以本模块不 import
任何 analytics 计算函数，写完也不会触发重算。
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HotnessSnapshot, LifecycleSnapshot, Meme, Video

from .query import _https, card_payload, cover_for_meme, manual_cover_for, thumbnail_for

MAX_TERMS = 12
MAX_TERM_LEN = 20
MAX_DESC = 600
EDITABLE = {"cover_url", "description", "aliases", "keywords"}


def _clean_image(raw: str | None) -> str:
    """封面只收 http(s) 外链或站内路径，挡掉 data:/javascript: 这类能直接执行的地址。"""
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith(("javascript:", "data:", "file:", "vbscript:")):
        raise HTTPException(status_code=400, detail="封面地址只支持 http(s) 图片或站内路径")
    if not value.startswith(("http://", "https://", "//", "/")):
        raise HTTPException(status_code=400, detail="封面地址必须以 http(s):// 或 / 开头")
    return value


def _clean_terms(raw: Any, label: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail=f"{label}必须是字符串数组")
    out: list[str] = []
    for item in raw:
        term = str(item or "").strip()
        if not term:
            continue
        if len(term) > MAX_TERM_LEN:
            raise HTTPException(status_code=400, detail=f"{label}「{term[:MAX_TERM_LEN]}…」超过 {MAX_TERM_LEN} 字")
        if term not in out:
            out.append(term)
    if len(out) > MAX_TERMS:
        raise HTTPException(status_code=400, detail=f"{label}最多 {MAX_TERMS} 个")
    return out


def cover_options(session: Session, meme: Meme, limit: int = 12) -> list[dict[str, Any]]:
    """可以挑来当封面的真实视频封面：按播放量从高到低、按地址去重。"""
    rows = session.scalars(
        select(Video).where(Video.meme_id == meme.id).order_by(Video.view.desc())
    )
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for video in rows:
        link = _https(video.cover or "")
        if not link or link in seen:
            continue
        seen.add(link)
        out.append(
            {
                "cover": link,
                "bvid": video.bvid,
                "title": (video.title or "")[:60],
                "view": video.view,
                "data_source": video.data_source,
            }
        )
        if len(out) >= limit:
            break
    return out


def sample_videos(session: Session, meme: Meme, limit: int = 8) -> dict[str, Any]:
    """这个梗到底采信了哪些视频——数据像不对，先来这里抽查。

    表里存的就是过了相关性阈值的样本（过滤发生在写入前），所以这里
    列出来的每一条都真的进了热度计算。
    """
    rows = list(
        session.scalars(
            select(Video).where(Video.meme_id == meme.id).order_by(Video.view.desc())
        )
    )
    return {
        "accepted": len(rows),
        "views": sum(row.view for row in rows),
        "items": [
            {
                "bvid": row.bvid,
                "title": row.title,
                "view": row.view,
                "author": row.author,
                "url": row.url,
                "relevance_score": round(row.relevance_score or 0.0, 2),
                "matched_terms": list(row.matched_terms or []),
                "data_source": row.data_source,
            }
            for row in rows[:limit]
        ],
    }


def meme_view(session: Session, meme: Meme) -> dict[str, Any]:
    """管理表单要的一次性读：当前值 + 自动封面 + 可挑的真实封面。"""
    hotness = session.get(HotnessSnapshot, meme.id)
    lifecycle = session.get(LifecycleSnapshot, meme.id)
    auto_cover = cover_for_meme(session, meme.id)
    return {
        "id": meme.id,
        "name": meme.name,
        "slug": meme.slug,
        "description": meme.description or "",
        "aliases": list(meme.aliases or []),
        "keywords": list(meme.keywords or []),
        "cover_url": manual_cover_for(meme),
        "auto_cover": auto_cover,
        "effective_cover": thumbnail_for(meme, auto_cover)["image"],
        "cover_options": cover_options(session, meme),
        "sample_videos": sample_videos(session, meme),
        "data_source": meme.data_source or "mock",
        "status": meme.status,
        "certified": bool(meme.certified),
        "verification_state": meme.verification_state or "unverified",
        "card": card_payload(meme, hotness, lifecycle, real_cover=auto_cover)
        if hotness and lifecycle
        else None,
        "note": "别名与关键词只影响搜索命中和后续采集的相关性过滤，不会改动已算好的热度与生命周期",
    }


def update_meta(session: Session, meme: Meme, payload: dict[str, Any]) -> dict[str, Any]:
    """写回人工维护的元数据。只认白名单字段，返回改完后的完整视图。"""
    fields = set(payload)
    if not fields:
        raise HTTPException(status_code=400, detail="没有任何要改的字段")
    unknown = fields - EDITABLE
    if unknown:
        raise HTTPException(status_code=400, detail=f"不支持修改的字段：{', '.join(sorted(unknown))}")

    changed: list[str] = []
    if "cover_url" in fields:
        meme.cover_url = _clean_image(payload["cover_url"])
        changed.append("cover_url")
    if "description" in fields:
        text = str(payload["description"] or "").strip()
        if len(text) > MAX_DESC:
            raise HTTPException(status_code=400, detail=f"介绍最长 {MAX_DESC} 字")
        meme.description = text
        changed.append("description")
    if "aliases" in fields:
        meme.aliases = _clean_terms(payload["aliases"], "别名")
        changed.append("aliases")
    if "keywords" in fields:
        meme.keywords = _clean_terms(payload["keywords"], "关键词")
        changed.append("keywords")

    session.commit()
    return {"changed": changed, "meme": meme_view(session, meme)}
