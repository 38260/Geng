"""演示数据采集器。

实现 :class:`app.collectors.base.Collector` 契约，输出与真实采集器完全同构的数据，
区别只在于 ``data_source='mock'``——这个字段会一路带到前端，页面上显示「演示数据」。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from app.config import get_logger
from app.models import CertRole, Meme
from app.mock.catalogue import spec_for
from app.mock.curves import build_daily_points, build_sample_videos, stats_from_points

from .base import CollectedBundle, CertificationEvidence

log = get_logger(__name__)

SOURCE = "mock"

_CERT_TITLES = {
    CertRole.ENCYCLOPEDIA: "「{name}」是什么梗？｜梗百科",
    CertRole.GUIDE: "{name}：出处、用法与含义｜梗指南",
}


def stable_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


class MockCollector:
    """按梗的生命周期原型生成 30 天时间序列 + 相关视频样本。"""

    source = SOURCE

    def is_available(self) -> tuple[bool, str]:
        return True, "演示数据始终可用"

    def collect(self, meme: Meme, *, window_days: int = 30) -> CollectedBundle:
        spec = spec_for(meme.name)
        if spec is None:
            log.warning("mock collector: %s 不在演示梗库中，跳过", meme.name)
            return CollectedBundle()

        seed = stable_seed(meme.name)
        points = build_daily_points(
            archetype=spec.archetype, scale=spec.scale, seed=seed, days=window_days
        )
        videos = build_sample_videos(
            meme_name=meme.name,
            aliases=spec.aliases,
            keywords=spec.keywords,
            points=points,
            scale=spec.scale,
            seed=seed,
            count=12 if spec.certification == "both" else 6,
        )
        return CollectedBundle(
            daily_stats=stats_from_points(meme.id, points),
            videos=videos,
            certifications=self._certifications(meme, spec, seed),
        )

    @staticmethod
    def _certifications(meme: Meme, spec, seed: int) -> list[CertificationEvidence]:
        wanted: list[str] = []
        if spec.certification in {"both", "enc"}:
            wanted.append(CertRole.ENCYCLOPEDIA)
        if spec.certification in {"both", "guide"}:
            wanted.append(CertRole.GUIDE)

        out: list[CertificationEvidence] = []
        for offset, role in enumerate(wanted):
            published = datetime.now() - timedelta(days=40 + (seed % 120) + offset * 7)
            out.append(
                CertificationEvidence(
                    role=role,
                    bvid=f"BV1cert{seed % 10000:04d}{offset}",
                    video_title=_CERT_TITLES[role].format(name=meme.name),
                    published_at=published,
                    confirmed=True,
                    data_source=SOURCE,
                )
            )
        return out
