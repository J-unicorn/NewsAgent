"""ZDWang crawler: Scrapling fetch + GBK-safe parsing + parallel translation."""

import re
from datetime import datetime

from crawler_common import (
    apply_record_defaults,
    fetch_page,
    finalize_article,
    is_recent,
    normalize_url,
    parse_date_any,
    response_text,
    strip_html_text,
    translate_records,
)


CATEGORIES = [
    {"url": "http://news.zdwang.com/web/", "main": "뉴스센터", "sub": "과기쾌보"},
    {"url": "http://news.zdwang.com/hea/", "main": "뉴스센터", "sub": "지혜가전"},
]


def _fetch_html(url):
    return response_text(fetch_page(url, timeout=15, site_name="ZDWANG"))


def _parse_list_items(html, base_url):
    items = []
    for block in re.findall(r"(?is)<li>(.*?)</li>", html):
        link_match = re.search(r'(?is)<h3[^>]*class=["\']title["\'][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block)
        if not link_match:
            continue
        raw_link, title_html = link_match.groups()
        title_attr = re.search(r'(?is)title=["\']([^"\']+)["\']', link_match.group(0))
        title = title_attr.group(1) if title_attr else strip_html_text(title_html, max_length=0)
        date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", block)
        date_text = "-".join(part.zfill(2) for part in date_match.groups()) if date_match else ""
        article_date = parse_date_any(date_text)
        items.append(
            {
                "title": title,
                "url": normalize_url(raw_link, base_url),
                "date": article_date,
            }
        )
    return items


def _fetch_detail(url):
    html = _fetch_html(url)
    date_text = ""
    date_match = re.search(r"发布时间：\s*(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)", html)
    if date_match:
        date_text = date_match.group(1)

    content = ""
    content_match = re.search(r'(?is)<div\s+class=["\']content["\'][^>]*>(.*?)</div>\s*</div>', html)
    if not content_match:
        content_match = re.search(r'(?is)<div\s+class=["\']content["\'][^>]*>(.*?)</div>', html)
    if content_match:
        content = strip_html_text(content_match.group(1))

    return content, parse_date_any(date_text)


def get_zdwang_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    results = []
    seen_links = set(global_seen_links or set())

    for category in CATEGORIES:
        page = 1
        keep_going = True
        while keep_going:
            if max_items is not None and len(results) >= max_items:
                break

            list_url = f"{category['url']}index.html" if page == 1 else f"{category['url']}{page}.html"
            html = _fetch_html(list_url)
            list_items = _parse_list_items(html, category["url"])
            if not list_items or page > 5:
                break

            page_recent_count = 0
            for item in list_items:
                if max_items is not None and len(results) >= max_items:
                    keep_going = False
                    break
                if item["url"] in seen_links:
                    continue
                if item["date"] and not is_recent(item["date"], days_to_scrape):
                    continue

                content, detail_date = _fetch_detail(item["url"])
                article_date = detail_date or item["date"] or datetime.now()
                if not is_recent(article_date, days_to_scrape):
                    continue

                page_recent_count += 1
                seen_links.add(item["url"])
                results.append(
                    finalize_article(
                        {
                            "title": item["title"],
                            "content": content,
                            "provider": "zdwang",
                            "category_main": category["main"],
                            "category_sub": category["sub"],
                            "provider_link_page": item["url"],
                            "url": item["url"],
                            "date": article_date.strftime("%Y-%m-%d %H:%M:%S"),
                            "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "_article_date": article_date,
                        }
                    )
                )

            if page_recent_count == 0:
                keep_going = False
            page += 1

    apply_record_defaults(
        results,
        useful=1,
        strategy_agenda=0,
        category1="zdwang",
    )
    return translate_records(results, ["title", "content", "content_summary"], max_workers=4)


if __name__ == "__main__":
    data = get_zdwang_data(days_to_scrape=1, max_items=10)
    print(f"\n수집: {len(data)}건")
