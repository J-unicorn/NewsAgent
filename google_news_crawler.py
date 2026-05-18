"""Google News RSS crawler with parallel fetch and translation."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from urllib.parse import quote
from xml.etree import ElementTree as ET

from crawler_common import (
    clean_text,
    fetch_page,
    finalize_article,
    is_recent,
    parse_date_any,
    response_text,
    strip_html_text,
    translate_records,
)
from news_keyword_sets import GOOGLE_NEWS_TARGET_GROUPS


TARGET_GROUPS = GOOGLE_NEWS_TARGET_GROUPS


def _rss_url(target, days, locale, extra_query=""):
    q = f'"{target}" when:{days}d'
    if extra_query:
        q = f"{q} {extra_query}"
    return f"https://news.google.com/rss/search?q={quote(q)}&{locale}"


def _text(item, tag):
    return clean_text(item.findtext(tag), max_length=0)


def _parse_target(group_name, target, rss_url, days, seen_links, seen_lock):
    page = fetch_page(rss_url, timeout=15, site_name=f"GOOGLE_NEWS/{target}")
    if not page:
        return []
    try:
        root = ET.fromstring(response_text(page).strip())
    except Exception as e:
        print(f"[GOOGLE_NEWS/{target}] RSS 파싱 실패: {e}")
        return []

    records = []
    for item in root.findall("./channel/item"):
        title = _text(item, "title")
        link = _text(item, "link").replace("/rss/", "/")
        pub_date = _text(item, "pubDate")
        source = item.find("source")
        provider = clean_text(source.text if source is not None else "", max_length=0) or "Google News"
        description = strip_html_text(_text(item, "description"))
        article_date = parse_date_any(pub_date)

        if not title or not link or not is_recent(article_date, days):
            continue

        with seen_lock:
            if link in seen_links:
                continue
            seen_links.add(link)

        records.append(
            finalize_article(
                {
                    "title": title,
                    "content": description or title,
                    "content_summary": description[:200] if description else title[:200],
                    "provider": provider,
                    "category_main": "",
                    "category_sub": "",
                    "reporter": "",
                    "provider_link_page": link,
                    "url": link,
                    "useful": -1,
                    "strategy_agenda": -1,
                    "category1": target,
                    "category2": group_name,
                    "date": article_date.strftime("%Y-%m-%d %H:%M:%S") if article_date else "",
                    "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "_article_date": article_date,
                }
            )
        )
    print(f"[GOOGLE_NEWS/{target}] RSS 최근 {days}일 대상: {len(records)}개")
    return records


def get_google_news_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    search_jobs = []
    seen_links = set(global_seen_links or set())

    for group in TARGET_GROUPS:
        for target in group["targets"]:
            search_jobs.append(
                (
                    group["name"],
                    target,
                    _rss_url(target, days_to_scrape, group["locale"], group.get("extra_query", "")),
                )
            )

    records = []
    seen_lock = Lock()
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_parse_target, group_name, target, url, days_to_scrape, seen_links, seen_lock): target
            for group_name, target, url in search_jobs
        }
        for future in as_completed(futures):
            try:
                records.extend(future.result())
            except Exception as e:
                print(f"[GOOGLE_NEWS/{futures[future]}] 실패: {e}")
            if max_items is not None and len(records) >= max_items:
                records = records[:max_items]
                break

    records = records[:max_items] if max_items is not None else records
    print(f"[GOOGLE_NEWS] 번역 대상: {len(records)}개")
    return translate_records(records, ["title", "content", "content_summary"], max_workers=4)


if __name__ == "__main__":
    data = get_google_news_data(days_to_scrape=1, max_items=10)
    print(f"\n수집: {len(data)}건")
