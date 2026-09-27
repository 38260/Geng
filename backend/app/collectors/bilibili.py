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
SEARCH_URL = "https://api.bilibili.com/x/web-interface/wbi/search/type"
SPACE_ARCHIVE_URL = "https://api.bilibili.com/x/space/wbi/arc/search"

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
class BiliClient:
    cookie: str = ""
    timeout: float = 10.0
    _img_key: str = ""
    _sub_key: str = ""
    _key_ts: float = 0.0

    def headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

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
        """只读探测：能不能拿到签名密钥。"""
        try:
            self.wbi_keys(refresh=True)
        except BilibiliBlocked as exc:
            return False, str(exc)
        return True, "WBI 签名可用"

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

    def space_videos(self, mid: int, *, page_size: int = 30) -> list[dict]:
        """某个 UP 主的投稿列表，用于双 UP 认证的真实证据。"""
        data = self.signed_get(
            SPACE_ARCHIVE_URL,
            {"mid": mid, "ps": page_size, "pn": 1, "order": "pubdate", "platform": "web"},
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
