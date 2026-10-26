#!/usr/bin/env python3
"""
Fetch international Chinese-language RSS feeds and merge into a single news.json.
Runs on GitHub Actions (overseas network) and commits the result back.
"""
import urllib.request
import xml.etree.ElementTree as ET
import json
import ssl
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# ===== Source Configuration =====
# Add / remove feeds here. Each feed belongs to one category.
# A source can appear in multiple categories via keyword filtering.

FEEDS = [
    # --- 全球新闻 ---
    {
        "category": "world",
        "source": "法国国际广播电台",
        "url": "https://www.rfi.fr/cn/rss",
    },
    {
        "category": "world",
        "source": "BBC中文",
        "url": "https://feeds.bbci.co.uk/zhongchi/simp/rss.xml",
    },
    {
        "category": "world",
        "source": "德国之声中文",
        "url": "https://rss.dw.com/atom/chi-zh",
    },
    {
        "category": "world",
        "source": "纽约时报中文",
        "url": "https://cn.nytimes.com/rss/",
    },
    # --- AI 与科技 ---
    {
        "category": "tech",
        "source": "Hacker News",
        "url": "https://hnrss.org/frontpage",
    },
    {
        "category": "tech",
        "source": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
    },
    # --- 财经市场 ---
    {
        "category": "finance",
        "source": "金融时报中文",
        "url": "https://cn.ft.com/rss",
    },
    {
        "category": "finance",
        "source": "Reuters World",
        "url": "https://feeds.reuters.com/reuters/worldNews",
    },
]

# Keyword filters: if a source has no explicit category, we bucket it by keywords.
# Not used for the explicit feeds above, but available if you add general feeds.
CATEGORY_KEYWORDS = {
    "tech": ["AI", "人工智能", "科技", "技术", "芯片", "OpenAI", "Google", "苹果", "微软", "特斯拉", "space", "科技公司", "互联网", "软件"],
    "finance": ["经济", "金融", "股市", "美元", "人民币", "央行", "通胀", "利率", "贸易", "投资", "市场", "油价"],
}

MAX_ITEMS_PER_CATEGORY = 12
TIMEOUT = 20

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsDashboard/1.0; +https://github.com/)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def strip_html(text):
    """Remove HTML tags from text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_date(date_str):
    """Parse RSS pubDate to ISO string."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.isoformat()
        except Exception:
            return None


def fetch_feed(url):
    """Fetch and return raw XML text."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        return resp.read()


def parse_items(xml_bytes):
    """Parse RSS/RDF/Atom XML and return list of dicts."""
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items

    # RSS 2.0: <item> under <channel>
    for item in root.findall(".//item"):
        title = strip_html(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        pub_date = item.findtext("pubDate") or item.findtext("date") or ""
        source = item.findtext("source") or ""
        if title and link:
            items.append({
                "title": title,
                "link": link,
                "pubDate": parse_date(pub_date),
                "source": source,
            })

    # RDF 1.0: <item> with rdf:about
    if not items:
        ns = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
              "rss": "http://purl.org/rss/1.0/"}
        for item in root.findall(".//rss:item", ns):
            title = strip_html(item.findtext("rss:title") or "")
            link = (item.findtext("rss:link") or "").strip()
            pub_date = item.findtext("dc:date") or ""
            if title and link:
                items.append({
                    "title": title,
                    "link": link,
                    "pubDate": parse_date(pub_date),
                    "source": "",
                })

    # Atom 1.0: <entry> with atom namespace
    if not items:
        ns_atom = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns_atom):
            title = strip_html(entry.findtext("atom:title", ns_atom) or "")
            # Atom link can have multiple <link> elements; pick the one with rel="alternate" or first
            link = ""
            for l in entry.findall("atom:link", ns_atom):
                if l.get("rel") == "alternate" or not l.get("rel"):
                    link = l.get("href", "")
                    break
            if not link:
                link = entry.findtext("atom:link", ns_atom) or ""
            pub_date = entry.findtext("atom:published", ns_atom) or entry.findtext("atom:updated", ns_atom) or ""
            if title and link:
                items.append({
                    "title": title,
                    "link": link.strip(),
                    "pubDate": parse_date(pub_date),
                    "source": "",
                })

    return items


def bucket_by_category(title):
    """Guess category from title keywords."""
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title.lower():
                return cat
    return None


def main():
    result = {
        "world": [],
        "tech": [],
        "finance": [],
        "trending": [],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceCount": 0,
    }

    all_items = []  # for trending aggregation

    for feed in FEEDS:
        cat = feed["category"]
        source = feed["source"]
        url = feed["url"]
        try:
            print(f"Fetching {source} ({cat})...")
            xml_bytes = fetch_feed(url)
            items = parse_items(xml_bytes)
            for item in items:
                item["source"] = source
                # If the feed didn't specify source, use our configured one
                if not item.get("source"):
                    item["source"] = source
                result[cat].append(item)
                all_items.append(item)
            print(f"  -> {len(items)} items")
            result["sourceCount"] += 1
        except Exception as e:
            print(f"  -> FAILED: {e}")

    # Deduplicate and sort each category by date (newest first)
    for cat in ["world", "tech", "finance"]:
        seen = set()
        unique = []
        for item in result[cat]:
            key = item["link"] or item["title"]
            if key not in seen:
                seen.add(key)
                unique.append(item)
        unique.sort(key=lambda x: x.get("pubDate") or "", reverse=True)
        result[cat] = unique[:MAX_ITEMS_PER_CATEGORY]

    # Trending: aggregate from all categories, take top by recency
    seen = set()
    trending = []
    for item in all_items:
        key = item["link"] or item["title"]
        if key not in seen:
            seen.add(key)
            trending.append(item)
    trending.sort(key=lambda x: x.get("pubDate") or "", reverse=True)
    result["trending"] = trending[:MAX_ITEMS_PER_CATEGORY]

    # Write output
    output_path = "data/news.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Output: {output_path}")
    print(f"  world: {len(result['world'])} items")
    print(f"  tech: {len(result['tech'])} items")
    print(f"  finance: {len(result['finance'])} items")
    print(f"  trending: {len(result['trending'])} items")
    print(f"  sources: {result['sourceCount']}")


if __name__ == "__main__":
    main()
