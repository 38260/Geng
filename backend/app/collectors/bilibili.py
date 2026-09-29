"""B 站 WBI 签名与请求封装。

B 站 Web 接口现在要求 WBI 签名（w_rid + wts），并且对无 Cookie 的匿名请求
经常返回 412（风控）。这里把签名、UA、Cookie、限流都收在一处，
上层只关心"搜某个已认证的梗"。

拿不到数据时抛 :class:`BilibiliBlocked`，由调用方决定回退到演示数据，
而不是悄悄返回一份假数据。
"""

from __future__ import annotations

import hashlib
import random
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import get_logger, settings

log = get_logger(__name__)

NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
SPI_URL = "https://api.bilibili.com/x/frontend/finger/spi"
SEARCH_URL = "https://api.bilibili.com/x/web-interface/wbi/search/type"
SPACE_ARCHIVE_URL = "https://api.bilibili.com/x/space/wbi/arc/search"
VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYER_URL = "https://api.bilibili.com/x/player/wbi/v2"

# B 站搜索接口有三种"没有结果"的返回，长得完全不同，必须分清楚：
#
#   ① 有结果        : {"result": [...], "numResults": 682, "numPages": 35, ...}
#   ② 真的没内容    : {"result": [], "numResults": 0, "numPages": 0, ...}
#   ③ 被限流吞掉    : {"v_voucher": "voucher_xxxx"}          ← 没有 numResults 字段
#
# ③ 是 B 站的风控应答：HTTP 200、没有错误码，但结果被整个拿掉，
# 只回一个 v_voucher 令牌。实测搜「动画」这种绝对有内容的词也会被这样吞掉，
# 所以它**不代表"当天没有内容"**。
#
# 关键在于它会随持续请求累积：冷启动时命中率 ~98%，
# 连续打几百次后掉到 0~30%，停手静默约 5 分钟后恢复。
# 也就是"吞"是会话级的限流状态，不是你查的那一天真的没数据。
#
# 老实现把 ② 和 ③ 混成一个 rows==[]（`numResults` 缺失时 total 兜底成 0），
# 于是"被限流"在库里长得和"当天没人做这个梗"一模一样——
# 这正是历史上 1070 行 observed=0 的来源。
THROTTLE_KEY = "v_voucher"


class BilibiliThrottled(RuntimeError):
    """搜索被 B 站限流吞掉（返回体只有 v_voucher）。

    这不是错误、也不是"没有数据"，而是"这次没给我"。
    调用方应当退避后重试；连续多次出现说明已进入限流状态，
    继续打只会加深处罚，应该停下来。
    """

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]


class BilibiliBlocked(RuntimeError):
    """B 站拒绝请求（风控 / 需要 Cookie / 签名失效）。"""


def _mixin_key(original: str) -> str:
    return "".join(original[index] for index in MIXIN_KEY_ENC_TAB)[:32]


def _clean(value: str) -> str:
    for char in "!'()*":
        value = value.replace(char, "")
    return value


def sign_params(params: dict[str, str | int], img_key: str, sub_key: str) -> dict[str, str]:
    """官方 WBI 算法：md5(query + mixin_key) -> w_rid。"""
    prepared = {
        key: _clean(str(value))
        for key, value in sorted(params.items())
    }
    prepared["wts"] = str(int(time.time()))
    query = urllib.parse.urlencode(prepared)
    mixin = _mixin_key(img_key + sub_key)
    w_rid = hashlib.md5((query + mixin).encode("utf-8")).hexdigest()
    prepared["w_rid"] = w_rid
    return prepared


@dataclass
class SubtitleResult:
    """一条视频的字幕抓取结果。拿不到时 reason 说人话，不返回半截内容。"""

    bvid: str = ""
    cid: int = 0
    text: str = ""
    kind: str = ""          # cc | ai
    lang: str = ""
    title: str = ""         # view 接口下发的真实标题，脚本入库时用它
    tracks: int = 0
    logged_in: bool = False
    reason: str = ""        # no-cid / no-track-anonymous / no-track / download-failed

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())


@dataclass
class BiliClient:
    cookie: str = ""
    timeout: float = 10.0
    _img_key: str = ""
    _sub_key: str = ""
    _key_ts: float = 0.0
    _fetched_cookie: str = ""

    def headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        }
        cookie = self.cookie or self._fetched_cookie
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def bootstrap_fingerprint(self, retries: int = 3) -> bool:
        """匿名取一次设备指纹（buvid3/buvid4）。

        B 站的 space/搜索接口对完全没有 Cookie 的请求经常直接 412/-352，
        带上这个公开端点下发的指纹后大部分能放行。取不到就返回 False，
        由调用方决定是降级还是要求用户填 BILI_COOKIE。
        """
        if self.cookie or self._fetched_cookie:
            return True
        for attempt in range(retries):
            try:
                response = httpx.get(SPI_URL, headers=self.headers(), timeout=self.timeout)
                payload = response.json() if response.status_code == 200 else {}
            except Exception:  # noqa: BLE001 - 指纹取不到不算致命错误
                payload = {}
            data = payload.get("data") or {}
            if data.get("b_3"):
                self._fetched_cookie = f"buvid3={data['b_3']}; buvid4={data.get('b_4', '')}"
                log.info("已取得 B 站匿名设备指纹 buvid3=***")
                return True
            time.sleep(1.2 * (attempt + 1))
        log.warning("取不到 B 站设备指纹，部分接口可能被风控")
        return False

    def _get_payload(self, url: str, params: dict[str, str] | None = None) -> dict:
        """返回完整响应体（不预设 code==0），供 nav 这类"未登录也带数据"的接口使用。"""
        try:
            response = httpx.get(
                url, params=params, headers=self.headers(),
                timeout=self.timeout, follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise BilibiliBlocked(f"网络请求失败：{exc.__class__.__name__}") from exc

        if response.status_code in (403, 412):
            raise BilibiliBlocked(
                f"B 站风控拦截（HTTP {response.status_code}）。"
                "这一步需要在 .env 里配置 BILI_COOKIE（浏览器登录 B 站后复制）才能稳定获取。"
            )
        if response.status_code != 200:
            raise BilibiliBlocked(f"B 站返回 HTTP {response.status_code}")
        try:
            return response.json()
        except Exception as exc:  # noqa: BLE001
            raise BilibiliBlocked("B 站返回的不是 JSON，可能被重定向到验证页") from exc

    def _get(self, url: str, params: dict[str, str] | None = None) -> dict:
        try:
            response = httpx.get(url, params=params, headers=self.headers(), timeout=self.timeout, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise BilibiliBlocked(f"网络请求失败：{exc.__class__.__name__}") from exc

        if response.status_code in (412, 403):
            raise BilibiliBlocked(
                f"B 站风控拦截（HTTP {response.status_code}）。"
                "这一步需要在 .env 里配置 BILI_COOKIE（浏览器登录 B 站后复制）才能稳定获取。"
            )
        if response.status_code != 200:
            raise BilibiliBlocked(f"B 站返回 HTTP {response.status_code}")
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise BilibiliBlocked("B 站返回的不是 JSON，可能被重定向到验证页") from exc

        code = payload.get("code")
        if code not in (0, None):
            message = str(payload.get("message") or "")[:80]
            if code in (-352, -403, -412):
                raise BilibiliBlocked(f"B 站安全校验未通过（code={code} {message}），需要有效 Cookie")
            raise BilibiliBlocked(f"B 站接口报错（code={code} {message}）")
        return payload.get("data") or {}

    # ------------------------------------------------------------------ #
    def wbi_keys(self, refresh: bool = False) -> tuple[str, str]:
        """WBI 签名要用 nav 接口下发的两个 key，缓存 1 小时。"""
        if self._img_key and self._sub_key and not refresh and time.time() - self._key_ts < 3600:
            return self._img_key, self._sub_key

        # nav 对匿名请求会返回 code=-101（未登录），但 wbi_img 照样下发，
        # 签名只需要这两个 key，不需要登录态。
        payload = self._get_payload(NAV_URL)
        data = payload.get("data") or {}
        wbi = data.get("wbi_img") or {}
        img_url, sub_url = wbi.get("img_url") or "", wbi.get("sub_url") or ""
        if not img_url or not sub_url:
            raise BilibiliBlocked("拿不到 WBI 签名密钥（nav 接口未返回 wbi_img）")

        def filename(url: str) -> str:
            return url.rsplit("/", 1)[-1].split(".", 1)[0]

        self._img_key, self._sub_key = filename(img_url), filename(sub_url)
        self._key_ts = time.time()
        return self._img_key, self._sub_key

    def signed_get(self, url: str, params: dict[str, str | int]) -> dict:
        img_key, sub_key = self.wbi_keys()
        return self._get(url, sign_params({**{k: str(v) for k, v in params.items()}}, img_key, sub_key))

    # ------------------------------------------------------------------ #
    def probe(self) -> tuple[bool, str]:
        """只读探测：能不能拿到签名密钥（顺带把设备指纹准备好）。"""
        self.bootstrap_fingerprint()
        try:
            self.wbi_keys(refresh=True)
        except BilibiliBlocked as exc:
            return False, str(exc)
        return True, "WBI 签名 + 设备指纹可用"

    def search_videos(self, keyword: str, *, pages: int = 1, order: str = "pubdate") -> list[dict]:
        """B 站定向搜索（梗库驱动，不是全站下载）。"""
        results: list[dict] = []
        for page in range(1, pages + 1):
            data = self.signed_get(
                SEARCH_URL,
                {"search_type": "video", "keyword": keyword, "page": page, "order": order, "ps": 30},
            )
            rows = data.get("result") or []
            if not rows:
                break
            results.extend(rows)
            time.sleep(0.6 + random.random() * 0.5)  # 限流：别把人家接口打爆
        return results

    def search_range(
        self,
        keyword: str,
        *,
        begin: "datetime",
        end: "datetime",
        order: str = "click",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """按发布时间区间搜索，返回 (结果行, B站给出的结果总数)。

        这是拿到"逐日"序列的唯一可靠途径：不带区间时搜索结果会被最近的
        内容占满，早期日期直接看不见。

        被限流吞掉时抛 :class:`BilibiliThrottled`——**不能**返回 ([], 0)，
        那会让"被限流"和"当天真没内容"在上层看起来一模一样。
        """
        data = self.signed_get(
            SEARCH_URL,
            {
                "search_type": "video",
                "keyword": keyword,
                "page": page,
                "ps": page_size,
                "order": order,
                "pubtime_begin_s": int(begin.timestamp()),
                "pubtime_end_s": int(end.timestamp()),
            },
        )
        rows = data.get("result") or []
        if not rows and THROTTLE_KEY in data:
            raise BilibiliThrottled(
                "搜索被限流吞掉（返回体只有 %s，没有 numResults）" % THROTTLE_KEY)
        # 真空返回会带着 numResults=0，这是可信的"当天没有内容"。
        try:
            total = int(data.get("numResults") or len(rows))
        except (TypeError, ValueError):
            total = len(rows)
        return rows, total

    def subtitle_of(self, bvid: str) -> SubtitleResult:
        """抓一条视频的字幕逐字稿。

        实测口径（2026-09-29）：匿名请求 `player/wbi/v2` 会返回 code=0 但
        `subtitles` 是空数组，B 站自己的 AI 视频总结端点直接 -101 未登录 ——
        也就是**没有 BILI_COOKIE 就没有字幕**，这不是解析能绕过去的。
        所以"拿不到"要分开写清楚：没登录 / 这条视频真没字幕 / 字幕文件下载失败，
        三者对用户的解释完全不同，混成一句"失败"就等于让人瞎猜。
        """
        out = SubtitleResult(bvid=bvid, logged_in=bool(self.cookie))
        try:
            view = self._get_payload(VIEW_URL, {"bvid": bvid})
        except BilibiliBlocked as exc:
            out.reason = f"view 失败：{exc}"
            return out
        data = view.get("data") or {}
        out.cid = int(data.get("cid") or 0)
        out.title = str(data.get("title") or "")
        if not out.cid:
            out.reason = "拿不到 cid（视频可能已删除或审核中）"
            return out

        try:
            player = self.signed_get(PLAYER_URL, {"bvid": bvid, "cid": str(out.cid)})
        except BilibiliBlocked as exc:
            out.reason = f"播放器信息失败：{exc}"
            return out

        # signed_get 已经剥过一层，返回的就是 data 本身（和搜索接口同一个口径）
        tracks = ((player.get("subtitle") or {}).get("subtitles")) or []
        out.tracks = len(tracks)
        if not tracks:
            out.reason = (
                "这条视频没有字幕轨（解说区很多是把字烧在画面里的）"
                if self.cookie else "匿名请求拿不到字幕轨，需要在 .env 配 BILI_COOKIE"
            )
            return out

        # 人工字幕优先（AI 识别的错字与断句明显更多），同档里再优先中文
        def sort_key(track: dict) -> tuple[int, int]:
            ai_last = 1 if int(track.get("ai_type") or 0) else 0
            zh_first = 0 if str(track.get("lan") or "").lower().startswith("zh") else 1
            return (ai_last, zh_first)

        chosen = sorted(tracks, key=sort_key)[0]
        out.kind = "ai" if int(chosen.get("ai_type") or 0) else "cc"
        out.lang = str(chosen.get("lan") or "")
        url = str(chosen.get("subtitle_url") or "")
        if url.startswith("//"):
            url = "https:" + url
        if not url:
            out.reason = "字幕轨里没有下载地址"
            return out

        try:
            response = httpx.get(
                url, headers=self.headers(), timeout=self.timeout, follow_redirects=True
            )
            response.raise_for_status()
            body = response.json().get("body") or []
        except Exception as exc:  # noqa: BLE001 - 字幕文件是另一个域，失败原因五花八门
            out.reason = f"字幕文件下载失败：{exc.__class__.__name__}"
            return out

        lines = [str(item.get("content") or "").strip() for item in body]
        out.text = "\n".join(line for line in lines if line)
        if not out.text:
            out.reason = "字幕文件是空的"
        return out

    def space_videos(self, mid: int, *, page_size: int = 50, page: int = 1) -> list[dict]:
        """某个 UP 主的投稿列表（按发布时间倒序）。"""
        data = self.signed_get(
            SPACE_ARCHIVE_URL,
            {"mid": mid, "ps": page_size, "pn": page, "order": "pubdate", "platform": "web"},
        )
        return ((data.get("list") or {}).get("vlist")) or []

    def space_search(self, mid: int, keyword: str, *, page_size: int = 20) -> list[dict]:
        """在某个 UP 主的投稿里搜关键词——双 UP 认证就靠它。"""
        data = self.signed_get(
            SPACE_ARCHIVE_URL,
            {"mid": mid, "ps": page_size, "pn": 1, "search_keyword": keyword, "platform": "web"},
        )
        return ((data.get("list") or {}).get("vlist")) or []


def parse_search_row(row: dict) -> dict:
    """搜索结果的标题带 <em> 高亮标签，统一清洗。"""
    import re

    strip = lambda value: re.sub(r"<[^>]+>", "", str(value or "")).strip()  # noqa: E731
    pubdate = row.get("pubdate") or row.get("pub_tag") or 0
    return {
        "bvid": strip(row.get("bvid") or row.get("id")),
        "aid": row.get("aid"),
        "title": strip(row.get("title") or row.get("short_title")),
        "description": strip(row.get("description")),
        "author": strip(row.get("author")),
        "author_mid": row.get("mid"),
        "cover": strip(row.get("pic")),
        "tag": strip(row.get("tag")),
        "view": int(row.get("play") or 0),
        "danmaku": int(row.get("danmaku") or 0),
        "reply": int(row.get("review") or 0),
        "publish_time": datetime.fromtimestamp(pubdate) if pubdate else datetime.now(),
        "duration_seconds": _duration_seconds(row.get("duration")),
    }


def _duration_seconds(value) -> int:
    if isinstance(value, int):
        return value
    text = str(value or "")
    parts = text.split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return 0
    seconds = 0
    for number in numbers:
        seconds = seconds * 60 + number
    return seconds


_default_client: BiliClient | None = None


def get_client() -> BiliClient:
    global _default_client
    if _default_client is None:
        _default_client = BiliClient(cookie=settings.bili_cookie, timeout=settings.bili_timeout)
    return _default_client
