"""Naver News search crawler for Korean missing-source coverage.

This crawler intentionally keeps Naver article URLs as provider_link_page so
dashboard actual-curation uploads using n.news.naver.com can match exactly.
"""

from __future__ import annotations

from datetime import datetime
import os
import re
import time
from urllib.parse import quote

from crawler_common import (
    DetailConfig,
    clean_text,
    date_to_output,
    extract_by_specs,
    fetch_page,
    finalize_article,
    first_element,
    get_all_text,
    get_attr,
    is_recent,
    normalize_url,
    parse_date_any,
    response_text,
)


BASE_URL = "https://search.naver.com"
PROVIDER_DEFAULT = "Naver News"
REQUEST_DELAY_SECONDS = 1.5
MAX_RESULTS_PER_QUERY = 5

REPRO_QUERIES = [
    "풀뎁스 로봇 물고기",
    "중국 로봇 청년 취업",
    "코웨이 말레이시아 신규상품 매출",
    "보람그룹 삼성 가전 할인",
    "삼성 LG 전장사업",
    "쿠팡 녹색제품 기획전",
    "한국개발연구원 유가 물가",
    "고용보험 가입자 27만",
    "해상 초크포인트 대응",
    "브렌트유 아시아 증시",
    "환율 상승 물가압력",
    "파월 긴축 구제",
    "트럼프미디어 1분기 손실",
    "LG전자 중국 생태계 활용",
    "LG전자 냉난방공조 2030 매출 20조",
    "국내 로봇 해외산",
    "군용 로봇 시장 성장",
    "현대차 비전투 로봇",
    "스마트테크 코리아 로봇",
    "소방청 AI 로봇 위원회",
    "미국 이란 종전협상",
    "이란 해상봉쇄 원유",
    "네타냐후 이란 우라늄",
    "모디 기름 소비 절감",
    "삼성전자 노사 성과급 사후조정",
]

DETAIL_CONFIG = DetailConfig(
    content_selectors=[
        "#dic_area",
        "article#dic_area",
        ".newsct_article",
        "#articeBody",
        "article",
    ],
    category_selectors=[
        ".media_end_categorize_item",
        ('meta[property="article:section"]', "content"),
    ],
    reporter_selectors=[
        ".media_end_head_journalist_name",
        ".byline_s",
        ('meta[name="author"]', "content"),
    ],
    date_selectors=[
        ("span.media_end_head_info_datestamp_time", "data-date-time"),
        ".media_end_head_info_datestamp_time",
        ('meta[property="article:published_time"]', "content"),
    ],
    summary_selectors=[
        ('meta[property="og:description"]', "content"),
    ],
    max_content_length=2500,
    timeout=15,
)

TITLE_SELECTORS = [
    "#title_area span",
    "h2#title_area",
    ".media_end_head_headline",
    ('meta[property="og:title"]', "content"),
]

PROVIDER_SELECTORS = [
    ('.media_end_head_top_logo img', "alt"),
    ".media_end_head_top_logo_text",
    ".media_end_linked_more_point",
    ('meta[property="og:article:author"]', "content"),
]

SEARCH_ITEM_SELECTORS = [
    "div.news_area",
    "div.news_wrap",
    "li.bx",
    "div.total_wrap",
]


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _search_url(query):
    encoded = quote(query)
    return f"{BASE_URL}/search.naver?where=news&sm=tab_jum&sort=1&query={encoded}"


def _compact(value):
    return re.sub(r"\s+", "", (value or "").lower())


def _search_title(item):
    for selector in ('a.news_tit', 'a[href*="n.news.naver.com"]', "a"):
        elem = first_element(item, selector)
        if not elem:
            continue
        title = clean_text(get_attr(elem, "title"), max_length=0) or get_all_text(elem, max_length=0)
        title = re.sub(r"\s*-\s*NAVER\s*News\s*$", "", title, flags=re.I)
        if title:
            return title
    return ""


def _search_provider(item):
    for selector in (".info_group .press", ".news_info .press", ".press"):
        elem = first_element(item, selector)
        provider = get_all_text(elem, max_length=100)
        if provider:
            return provider
    return PROVIDER_DEFAULT


def _extract_search_records(page, query):
    records = []
    seen_urls = set()

    for selector in SEARCH_ITEM_SELECTORS:
        try:
            items = page.css(selector)
        except Exception:
            items = []
        for item in items or []:
            naver_link = first_element(item, 'a[href*="n.news.naver.com"]')
            if not naver_link:
                naver_link = first_element(item, 'a[href*="news.naver.com/main/read.naver"]')
            url = normalize_url(get_attr(naver_link, "href"), "https://news.naver.com")
            if not url or "news.naver.com" not in url or url in seen_urls:
                continue
            seen_urls.add(url)
            records.append(
                {
                    "title": _search_title(item),
                    "url": url,
                    "provider_link_page": url,
                    "provider": _search_provider(item),
                    "category_main": "Naver News",
                    "category_sub": query,
                    "category1": query,
                    "category2": "NAVER_NEWS",
                    "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "_query": query,
                }
            )

    if records:
        return records

    html = response_text(page)
    url_matches = re.findall(r'https?://n\.news\.naver\.com/[^"\'<>\s]+', html)
    for raw_url in url_matches:
        url = raw_url.replace("&amp;", "&")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        records.append(
            {
                "title": "",
                "url": url,
                "provider_link_page": url,
                "provider": PROVIDER_DEFAULT,
                "category_main": "Naver News",
                "category_sub": query,
                "category1": query,
                "category2": "NAVER_NEWS",
                "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "_query": query,
            }
        )
    return records


def _fetch_detail(record, days):
    page = fetch_page(record["url"], timeout=DETAIL_CONFIG.timeout, site_name="NAVER_NEWS", max_retries=2)
    if not page:
        return finalize_article(
            {
                **record,
                "content": record.get("title", ""),
                "content_summary": record.get("title", ""),
                "useful": -1,
                "strategy_agenda": -1,
            }
        )

    title = extract_by_specs(page, TITLE_SELECTORS, max_length=500)
    content = extract_by_specs(page, DETAIL_CONFIG.content_selectors, max_length=DETAIL_CONFIG.max_content_length)
    provider = extract_by_specs(page, PROVIDER_SELECTORS, max_length=100)
    reporter = extract_by_specs(page, DETAIL_CONFIG.reporter_selectors, max_length=100)
    category = extract_by_specs(page, DETAIL_CONFIG.category_selectors, max_length=100)
    date_text = extract_by_specs(page, DETAIL_CONFIG.date_selectors, max_length=100)
    summary = extract_by_specs(page, DETAIL_CONFIG.summary_selectors, max_length=300)
    article_date = parse_date_any(date_text)

    if article_date and not is_recent(article_date, days):
        return None

    merged = {
        **record,
        "title": title or record.get("title") or record.get("_query", ""),
        "content": content or summary or record.get("title") or "",
        "content_summary": summary or clean_text((content or "")[:200]),
        "provider": provider or record.get("provider") or PROVIDER_DEFAULT,
        "reporter": reporter,
        "category_main": category or record.get("category_main") or "Naver News",
        "date": date_to_output(article_date),
        "_article_date": article_date,
        "useful": -1,
        "strategy_agenda": -1,
    }
    return finalize_article(merged)


def _queries():
    configured = os.getenv("NAVER_NEWS_QUERIES", "").strip()
    if configured:
        return [query.strip() for query in configured.split("|") if query.strip()]
    return list(REPRO_QUERIES)


def get_naver_news_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    seen_links = set(global_seen_links or set())
    seen_titles = set()
    records = []
    delay = _env_float("NAVER_NEWS_REQUEST_DELAY", REQUEST_DELAY_SECONDS)
    per_query = _env_int("NAVER_NEWS_MAX_RESULTS_PER_QUERY", MAX_RESULTS_PER_QUERY)

    for query in _queries():
        if max_items is not None and len(records) >= max_items:
            break
        page = fetch_page(_search_url(query), timeout=15, site_name=f"NAVER_NEWS/{query}", max_retries=2)
        if not page:
            time.sleep(delay)
            continue

        candidates = _extract_search_records(page, query)[:per_query]
        print(f"[NAVER_NEWS/{query}] 검색 후보: {len(candidates)}개")
        for candidate in candidates:
            if max_items is not None and len(records) >= max_items:
                break
            url = candidate.get("provider_link_page") or candidate.get("url")
            if not url or url in seen_links:
                continue

            article = _fetch_detail(candidate, days_to_scrape)
            time.sleep(delay)
            if not article:
                continue

            title_key = _compact(article.get("title"))
            if title_key and title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            seen_links.add(url)
            records.append(article)

        time.sleep(delay)

    print(f"[NAVER_NEWS] 완료: {len(records)}개 수집")
    return records[:max_items] if max_items is not None else records


if __name__ == "__main__":
    data = get_naver_news_data(days_to_scrape=1, max_items=10)
    print(f"\n수집: {len(data)}건")
