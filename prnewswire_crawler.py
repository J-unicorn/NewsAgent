"""PRNewswire crawler with RSS filtering for HS-relevant releases."""

from __future__ import annotations

from datetime import datetime
import re

from crawler_common import (
    DetailConfig,
    RssConfig,
    SelectorConfig,
    clean_text,
    enrich_articles,
    finalize_article,
    is_recent,
    parse_rss_articles,
    parse_selector_articles,
    translate_records,
)


BASE_URL = "https://www.prnewswire.com"
PROVIDER = "PRNewswire"

KEYWORDS = [
    "ESG",
    "sustainability",
    "sustainable",
    "climate",
    "carbon",
    "emissions",
    "governance",
    "supply chain",
    "energy transition",
    "battery",
    "AI",
    "appliance",
    "electronics",
    "manufacturing",
    "Husqvarna",
    "YOFC",
    "APsystems",
]

RSS_CONFIG = RssConfig(
    url=f"{BASE_URL}/rss/news-releases-list.rss",
    provider=PROVIDER,
    category_path="category",
    content_path="description",
)

SELECTOR_CONFIG = SelectorConfig(
    list_url=f"{BASE_URL}/news-releases/news-releases-list/?page=1&pagesize=25",
    provider=PROVIDER,
    item_selector='a[href*="/news-releases/"]',
    base_url=BASE_URL,
    category_main_default="Press Release",
    category_sub_default="PRNewswire",
    max_pages=1,
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=[
        ".release-body",
        ".news-release-content",
        ".col-sm-10",
        "article",
    ],
    date_selectors=[
        ('meta[property="article:published_time"]', "content"),
        ".mb-no",
        ".release-date",
    ],
    summary_selectors=[
        ('meta[property="og:description"]', "content"),
    ],
    max_content_length=2500,
)


def _compact(value):
    return re.sub(r"\s+", "", (value or "").lower())


def _keyword_match(article):
    haystack = " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("content") or ""),
            str(article.get("content_summary") or ""),
            str(article.get("_rss_content") or ""),
        ]
    ).lower()
    return any(keyword.lower() in haystack for keyword in KEYWORDS)


def _filter_records(records, days, max_items):
    filtered = []
    seen_titles = set()
    seen_urls = set()
    for article in records:
        url = article.get("provider_link_page") or article.get("url")
        title_key = _compact(article.get("title"))
        article_date = article.get("_article_date")
        if url in seen_urls or (title_key and title_key in seen_titles):
            continue
        if article_date and not is_recent(article_date, days):
            continue
        if not _keyword_match(article):
            continue
        seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        filtered.append(article)
        if max_items and len(filtered) >= max_items:
            break
    return filtered


def _apply_defaults(records):
    for article in records:
        article["provider"] = PROVIDER
        article["category_main"] = article.get("category_main") or "Press Release"
        article["category_sub"] = article.get("category_sub") or "PRNewswire"
        article["category1"] = article.get("category1") or "PRNewswire"
        article["category2"] = article.get("category2") or "Press Release"
        article["useful"] = article.get("useful", -1)
        article["strategy_agenda"] = article.get("strategy_agenda", -1)
        article["enveloped_at"] = article.get("enveloped_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return records


def get_prnewswire_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    seen_links = set(global_seen_links or set())
    print("[PRNEWSWIRE] RSS 목록 수집 중...")
    records = parse_rss_articles(
        RSS_CONFIG,
        days=days_to_scrape,
        max_items=max(max_items or 100, 100),
        seen_links=seen_links,
        site_name="PRNEWSWIRE",
    )
    records = _filter_records(records, days_to_scrape, max_items)

    if not records:
        print("[PRNEWSWIRE] selector fallback 실행")
        records = parse_selector_articles(
            SELECTOR_CONFIG,
            days=days_to_scrape,
            max_items=max_items or 100,
            seen_links=seen_links,
            site_name="PRNEWSWIRE",
        )
        records = _filter_records(records, days_to_scrape, max_items)

    print(f"[PRNEWSWIRE] 본문 수집 대상: {len(records)}개")
    enriched = enrich_articles(
        records,
        detail_config=DETAIL_CONFIG,
        max_workers=2,
        site_name="PRNEWSWIRE",
        request_delay=1.0,
    )
    enriched = _apply_defaults([finalize_article(article) for article in enriched])
    print(f"[PRNEWSWIRE] 번역 대상: {len(enriched)}개")
    return translate_records(enriched, ["title", "content", "content_summary"], max_workers=2)


if __name__ == "__main__":
    data = get_prnewswire_data(days_to_scrape=1, max_items=20)
    print(f"\n수집: {len(data)}건")
