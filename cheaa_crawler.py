"""CHEAA crawler: selector-equivalent parser with parallel translation."""

import json
import re
from datetime import datetime

from crawler_common import (
    DetailConfig,
    apply_record_defaults,
    clean_text,
    enrich_articles,
    fetch_page,
    is_recent,
    normalize_url,
    parse_date_any,
    response_text,
    strip_html_text,
    translate_records,
)


LIST_BASE_URL = "https://m.cheaa.com"
ARTICLE_BASE_URL = "https://news.cheaa.com"

DETAIL_CONFIG = DetailConfig(
    content_selectors=["div#ctrlfscont", "div.article", ".article", "article"],
    category_selectors=["div.position a:last-child", ".crumb a:last-child"],
    date_selectors=["div.info", ".info"],
)


def _list_url(page):
    if page == 1:
        return f"{LIST_BASE_URL}/"
    offset = (page - 1) * 20
    return f"{LIST_BASE_URL}/ajax_list_more.php?action=more_index&id=&num={offset}"


def _list_html(page):
    raw = response_text(fetch_page(_list_url(page), timeout=15, site_name="CHEAA"))
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, str):
            raw = decoded
    except Exception:
        pass
    return raw.replace("\\/", "/")


def _parse_list_items(html):
    items = []
    for block in re.findall(r'(?is)<div\s+class=["\']newsBox["\'][^>]*>(.*?)</div>', html):
        links = re.findall(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block)
        text_links = [(href, strip_html_text(text, max_length=0)) for href, text in links if strip_html_text(text, max_length=0)]
        if not text_links:
            continue
        raw_link, title = text_links[-1]
        date_match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", block)
        article_date = parse_date_any(date_match.group(1)) if date_match else None
        items.append(
            {
                "title": clean_text(title, max_length=0),
                "url": normalize_url(raw_link, ARTICLE_BASE_URL),
                "date": article_date,
            }
        )
    return items


def get_cheaa_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    articles = []
    seen_links = set(global_seen_links or set())

    for page in range(1, 6):
        if max_items is not None and len(articles) >= max_items:
            break

        items = _parse_list_items(_list_html(page))
        if not items:
            break

        dated_count = 0
        old_count = 0
        for item in items:
            if max_items is not None and len(articles) >= max_items:
                break
            if item["date"]:
                dated_count += 1
                if not is_recent(item["date"], days_to_scrape):
                    old_count += 1
                    continue
            if not item["title"] or not item["url"] or item["url"] in seen_links:
                continue

            seen_links.add(item["url"])
            articles.append(
                {
                    "title": item["title"],
                    "url": item["url"],
                    "provider": "cheaa",
                    "provider_link_page": item["url"],
                    "date": item["date"].strftime("%Y-%m-%d %H:%M:%S") if item["date"] else "",
                    "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "_article_date": item["date"],
                }
            )

        if dated_count and old_count == dated_count:
            break

    print(f"[CHEAA] 본문 수집 대상: {len(articles)}개")
    records = enrich_articles(articles, detail_config=DETAIL_CONFIG, max_workers=10, site_name="CHEAA")
    apply_record_defaults(
        records,
        useful=1,
        strategy_agenda=0,
        category1="cheaa",
        category2="",
    )
    return translate_records(records, ["title", "content", "content_summary", "category_main"], max_workers=4)


if __name__ == "__main__":
    data = get_cheaa_data(days_to_scrape=1, max_items=10)
    print(f"\n수집: {len(data)}건")
