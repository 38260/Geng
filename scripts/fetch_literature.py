"""核验开题相关文献的元数据（Crossref 权威记录：DOI / 作者 / 年份 / 刊名 / 卷期页）。

    python scripts/fetch_literature.py > docs/research/literature-raw.txt

两条路：
1. 已知 DOI 直接解析（最可靠，拿到就是出版商登记的信息）；
2. 只有标题线索的，用 query.title 精搜 + query.author 收窄，取匹配度最高的第一条，
   并把前两条都打出来方便人工核对是否同名不同篇。
匹配不上的一律标 NO_MATCH，不猜、不编。
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "gengchao-lit-check/1.0 (https://github.com/gengchao; mailto:zyb@example.com)"}
SELECT = "DOI,title,author,container-title,volume,issue,page,published,published-print,type"

# 已经拿到 DOI（来自出版商页面 / 检索结果链接），直接解析核对
BY_DOI = [
    "10.1177/1461444811412160",      # Shifman, An anatomy of a YouTube meme
    "10.1609/icwsm.v5i1.14097",      # Bauckhage, Insights into Internet Memes
    "10.1145/1787234.1787254",       # Szabo & Huberman, Predicting the popularity of online content
    "10.1073/pnas.0803685105",       # Crane & Sornette, response function of a social system
    "10.1038/s41467-019-09311-w",    # Lorenz-Spreen et al., Accelerating dynamics of collective attention
    "10.1145/775047.775061",         # Kleinberg, Bursty and hierarchical structure in streams
    "10.1177/10949968251320612",     # Ward, Internet Meme Marketing over the Fad Cycle
    "10.17645/mac.v10i2.4996",       # Wang, Community-Building on Bilibili
    "10.1177/1461445620940051",      # Zhang & Cassany, Making sense of danmu
    "10.1145/3578840.3598356",       # 猜测：某篇 meme 相关（核对不上就丢）
]

# 只有标题线索的，精搜
BY_TITLE = [
    ("Memetracker", ""),
    ("Meme diffusion on the internet", "Zeng"),
    ("Modeling the evolution of internet topics", "Adar"),
    ("Patterns of topic impact in online news media", "Yang"),
    ("Modeling the popularity of buzz events", ""),
    ("Life cycle prediction of viral tweets", ""),
    ("You call this a meme? A taxonomy of internet memes", ""),
    ("The Meme Machine: A Review of Online Meme Studies", "Arif"),
    ("Distributed creativity and internet memes", ""),
    ("Topic detection and tracking in social streams", "Mathioudakis"),
    ("Predicting the popularity of short videos", ""),
    ("模因视角下网络流行语的传播与反思", ""),
    ("基于百度指数的突发事件网络舆情预测分析", ""),
    ("网络舆情预警研究综述", ""),
    ("微博舆情传播周期中不同传播者的主题挖掘与观点识别", ""),
    ("突发事件舆情观点识别与分析研究评述", ""),
    ("网络流行语的生命周期", ""),
    ("B站 弹幕 网络梗 研究", ""),
]


def get(url: str, timeout: float = 25.0, tries: int = 4) -> bytes:
    last = None
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - 429 要退避重试
            last = exc
            time.sleep(2.0 + 3.0 * attempt)
    raise last  # type: ignore[misc]


def fmt(item: dict) -> dict:
    authors = [f"{a.get('family', a.get('name', ''))} {a.get('given', '')}".strip()
               for a in (item.get("author") or [])][:8]
    print_year = ((item.get("published-print") or {}).get("date-parts") or [[None]])[0][0]
    online_year = ((item.get("published") or {}).get("date-parts") or [[None]])[0][0]
    return {
        "title": (item.get("title") or [""])[0].replace("\n", " ").strip(),
        "authors": authors,
        "venue": (item.get("container-title") or [""])[0],
        "year_print": print_year,
        "year_online": online_year,
        "volume": item.get("volume"),
        "issue": item.get("issue"),
        "page": item.get("page"),
        "doi": item.get("DOI"),
        "type": item.get("type"),
    }


def by_doi(doi: str) -> dict:
    try:
        data = json.loads(get(f"https://api.crossref.org/works/{doi}").decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"doi": doi, "error": str(exc)[:100]}
    return {"doi": doi, **fmt(data.get("message") or {})}


def by_title(title: str, author: str) -> dict:
    params = {"query.title": title, "rows": 2, "select": SELECT}
    if author:
        params["query.author"] = author
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(get(url).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"query": title, "error": str(exc)[:100]}
    items = (data.get("message") or {}).get("items") or []
    if not items:
        return {"query": title, "error": "NO_MATCH"}
    return {"query": title, "query_author": author, "best": fmt(items[0]),
            "second": fmt(items[1]) if len(items) > 1 else None}


def main() -> int:
    print("### 按 DOI 解析")
    for doi in BY_DOI:
        print(json.dumps(by_doi(doi), ensure_ascii=False))
        time.sleep(1.0)
    print()
    print("### 按标题精搜")
    for title, author in BY_TITLE:
        print(json.dumps(by_title(title, author), ensure_ascii=False))
        time.sleep(1.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
