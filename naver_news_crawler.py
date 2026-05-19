"""Naver News search crawler for Korean missing-source coverage.

This crawler intentionally keeps Naver article URLs as provider_link_page so
dashboard actual-curation uploads using n.news.naver.com can match exactly.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import unescape
import json
import os
import re
from threading import Lock
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

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
from news_keyword_sets import (
    GOOGLE_NEWS_QUERY_TARGETS,
    NAVER_NEWS_GOOGLE_TARGET_ALIASES,
    NAVER_NEWS_HS_REPRO_QUERIES,
    NAVER_NEWS_HS_SUPPLEMENTAL_QUERIES_2026_05_12,
    unique_keywords,
)


BASE_URL = "https://search.naver.com"
OPENAPI_URL = "https://openapi.naver.com/v1/search/news.json"
PROVIDER_DEFAULT = "Naver News"
REQUEST_DELAY_SECONDS = 1.5
MAX_RESULTS_PER_QUERY = 24
MAX_RESULTS_PER_SORT = 4
OPENAPI_WORKERS = 6
NAVER_TRANSIENT_QUERY_PARAMS = {"sid"}
KST = timezone(timedelta(hours=9))

REPRO_QUERIES = unique_keywords(
    GOOGLE_NEWS_QUERY_TARGETS,
    NAVER_NEWS_GOOGLE_TARGET_ALIASES,
    NAVER_NEWS_HS_REPRO_QUERIES,
    NAVER_NEWS_HS_SUPPLEMENTAL_QUERIES_2026_05_12,
)

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


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _search_url(query, sort="1", start=None):
    encoded = quote(query)
    url = f"{BASE_URL}/search.naver?where=news&sm=tab_jum&sort={sort}&query={encoded}"
    if start:
        url = f"{url}&start={start}"
    return url


def _normalize_naver_article_url(url):
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return re.sub(r"#.*$", "", url).rstrip("/")
    if "news.naver.com" not in parsed.netloc.lower():
        return url

    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in NAVER_TRANSIENT_QUERY_PARAMS
    ]
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            re.sub(r"/+$", "", parsed.path or "/") or "/",
            urlencode(sorted(query_items), doseq=True),
            "",
        )
    )


def _strip_html(value):
    return clean_text(re.sub(r"<[^>]+>", " ", unescape(value or "")), max_length=0)


def _date_window():
    start = os.getenv("NAVER_NEWS_DATE_START", "").strip()
    end = os.getenv("NAVER_NEWS_DATE_END", "").strip()
    if start and end:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            return None
        start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=KST)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=KST)
        return start_dt, end_dt

    days_ago_from = os.getenv("NAVER_NEWS_DAYS_AGO_FROM", "").strip()
    days_ago_to = os.getenv("NAVER_NEWS_DAYS_AGO_TO", "").strip()
    if not days_ago_from or not days_ago_to:
        return None
    try:
        older = max(int(days_ago_from), int(days_ago_to))
        newer = min(int(days_ago_from), int(days_ago_to))
    except ValueError:
        return None
    today = datetime.now(KST).date()
    start_date = today - timedelta(days=older)
    end_date = today - timedelta(days=newer)
    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=KST)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=KST)
    return start_dt, end_dt


def _article_in_scope(article_date, days):
    if not article_date:
        return True
    window = _date_window()
    if not window:
        return is_recent(article_date, days)

    start_dt, end_dt = window
    if getattr(article_date, "tzinfo", None):
        comparable = article_date.astimezone(KST)
    else:
        comparable = article_date.replace(tzinfo=KST)
    return start_dt <= comparable <= end_dt


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
            url = _normalize_naver_article_url(normalize_url(get_attr(naver_link, "href"), "https://news.naver.com"))
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
        url = _normalize_naver_article_url(raw_url.replace("&amp;", "&"))
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

    if not _article_in_scope(article_date, days):
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


def _openapi_credentials():
    client_id = os.getenv("NAVER_OPENAPI_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_OPENAPI_CLIENT_SECRET", "").strip()
    return client_id, client_secret


def _openapi_enabled():
    disabled = os.getenv("NAVER_NEWS_OPENAPI_ENABLED", "1").strip().lower()
    client_id, client_secret = _openapi_credentials()
    return disabled not in {"0", "false", "no"} and bool(client_id and client_secret)


def _openapi_sorts():
    configured = os.getenv("NAVER_NEWS_API_SORTS", "").strip()
    if configured:
        sorts = [sort.strip() for sort in re.split(r"[,|]", configured) if sort.strip()]
        return sorts or ["date"]

    mapped = []
    for sort in _search_sorts():
        if sort == "1":
            mapped.append("date")
        elif sort == "0":
            mapped.append("sim")
        elif sort in {"date", "sim"}:
            mapped.append(sort)
    return mapped or ["date"]


def _openapi_url(query, sort, display, start=1):
    params = urlencode(
        {
            "query": query,
            "display": display,
            "start": start,
            "sort": sort,
        }
    )
    return f"{OPENAPI_URL}?{params}"


def _openapi_provider(item):
    origin = item.get("originallink") or item.get("link") or ""
    try:
        host = urlsplit(origin).netloc.lower()
    except ValueError:
        host = ""
    return host.replace("www.", "") or PROVIDER_DEFAULT


def _openapi_record(query, item):
    link = item.get("link") or ""
    original_link = item.get("originallink") or ""
    preferred_link = link if "news.naver.com" in link else original_link or link
    preferred_link = _normalize_naver_article_url(preferred_link)
    article_date = parse_date_any(item.get("pubDate", ""))
    title = _strip_html(item.get("title", ""))
    summary = _strip_html(item.get("description", ""))

    return finalize_article(
        {
            "title": title or query,
            "content": summary or title,
            "content_summary": summary[:200] if summary else title[:200],
            "provider": _openapi_provider(item),
            "category_main": "Naver News",
            "category_sub": query,
            "reporter": "",
            "provider_link_page": preferred_link,
            "url": preferred_link,
            "useful": -1,
            "strategy_agenda": -1,
            "category1": query,
            "category2": "NAVER_NEWS",
            "date": article_date.strftime("%Y-%m-%d %H:%M:%S") if article_date else "",
            "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "_article_date": article_date,
            "_query": query,
        }
    )


def _fetch_openapi_items(query, sort, display, client_id, client_secret):
    url = _openapi_url(query, sort=sort, display=display)
    request = Request(
        url,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "User-Agent": "NewsAgent/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        print(f"[NAVER_NEWS_API/{query}/{sort}] HTTP {e.code}: {e.reason}")
        return None
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"[NAVER_NEWS_API/{query}/{sort}] 실패: {e}")
        return None

    return payload.get("items", [])


def _parse_openapi_query(query, days, seen_links, seen_titles, seen_lock, display, sorts, client_id, client_secret):
    records = []
    ok = True
    for sort in sorts:
        items = _fetch_openapi_items(query, sort, display, client_id, client_secret)
        if items is None:
            ok = False
            continue

        for item in items:
            record = _openapi_record(query, item)
            url = _normalize_naver_article_url(record.get("provider_link_page") or record.get("url"))
            if not url:
                continue
            article_date = record.get("_article_date")
            if not _article_in_scope(article_date, days):
                continue

            title_key = _compact(record.get("title"))
            with seen_lock:
                if url in seen_links or (title_key and title_key in seen_titles):
                    continue
                seen_links.add(url)
                if title_key:
                    seen_titles.add(title_key)

            records.append(record)

    print(f"[NAVER_NEWS_API/{query}] 검색 결과: {len(records)}개")
    return ok, records


def _get_naver_news_data_openapi(days_to_scrape, max_items, global_seen_links):
    client_id, client_secret = _openapi_credentials()
    display = _bounded_int(
        os.getenv("NAVER_NEWS_API_DISPLAY", os.getenv("NAVER_NEWS_MAX_RESULTS_PER_QUERY", str(MAX_RESULTS_PER_QUERY))),
        MAX_RESULTS_PER_QUERY,
        1,
        100,
    )
    workers = _bounded_int(os.getenv("NAVER_NEWS_WORKERS"), OPENAPI_WORKERS, 1, 12)
    sorts = _openapi_sorts()
    seen_links = {
        _normalize_naver_article_url(link)
        for link in (global_seen_links or set())
        if link
    }
    seen_titles = set()
    seen_lock = Lock()
    records = []
    failed_queries = 0

    window = _date_window()
    window_text = f", window={window[0].date()}~{window[1].date()}" if window else ""
    print(f"[NAVER_NEWS_API] 공식 API 병렬 수집 시작: queries={len(_queries())}, workers={workers}, display={display}, sorts={sorts}{window_text}")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _parse_openapi_query,
                query,
                days_to_scrape,
                seen_links,
                seen_titles,
                seen_lock,
                display,
                sorts,
                client_id,
                client_secret,
            ): query
            for query in _queries()
        }

        for future in as_completed(futures):
            query = futures[future]
            try:
                ok, query_records = future.result()
            except Exception as e:
                print(f"[NAVER_NEWS_API/{query}] 예외: {e}")
                failed_queries += 1
                continue
            if not ok:
                failed_queries += 1
            records.extend(query_records)
            if max_items is not None and len(records) >= max_items:
                records = records[:max_items]
                break

    print(f"[NAVER_NEWS_API] 완료: {len(records)}개 수집, 실패 쿼리={failed_queries}")
    return records, failed_queries


def _queries():
    configured = os.getenv("NAVER_NEWS_QUERIES", "").strip()
    if configured:
        return [query.strip() for query in configured.split("|") if query.strip()]
    return list(REPRO_QUERIES)


def _search_sorts():
    configured = os.getenv("NAVER_NEWS_SEARCH_SORTS", "1,0").strip()
    sorts = [sort.strip() for sort in re.split(r"[,|]", configured) if sort.strip()]
    return sorts or ["1"]


def _search_starts():
    configured = os.getenv("NAVER_NEWS_SEARCH_STARTS", "1,11,21").strip()
    starts = []
    for start in re.split(r"[,|]", configured):
        try:
            value = int(start.strip())
        except ValueError:
            continue
        if value > 0:
            starts.append(value)
    return starts or [1]


def get_naver_news_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    if _openapi_enabled():
        records, failed_queries = _get_naver_news_data_openapi(days_to_scrape, max_items, global_seen_links)
        if records or failed_queries == 0:
            return records[:max_items] if max_items is not None else records
        print("[NAVER_NEWS_API] 결과가 없고 실패가 있어 HTML 검색 fallback 실행")
    else:
        print("[NAVER_NEWS_API] credentials 없음 또는 비활성화: HTML 검색 fallback 실행")

    seen_links = {
        _normalize_naver_article_url(link)
        for link in (global_seen_links or set())
        if link
    }
    seen_titles = set()
    records = []
    delay = _env_float("NAVER_NEWS_REQUEST_DELAY", REQUEST_DELAY_SECONDS)
    per_query = _env_int("NAVER_NEWS_MAX_RESULTS_PER_QUERY", MAX_RESULTS_PER_QUERY)
    per_sort = _env_int("NAVER_NEWS_MAX_RESULTS_PER_SORT", MAX_RESULTS_PER_SORT)
    search_sorts = _search_sorts()
    search_starts = _search_starts()

    for query in _queries():
        if max_items is not None and len(records) >= max_items:
            break

        candidates = []
        seen_candidate_urls = set()
        for start in search_starts:
            for sort in search_sorts:
                page = fetch_page(
                    _search_url(query, sort=sort, start=start),
                    timeout=15,
                    site_name=f"NAVER_NEWS/{query}/sort={sort}/start={start}",
                    max_retries=2,
                )
                if not page:
                    time.sleep(delay)
                    continue
                for candidate in _extract_search_records(page, query)[:per_sort]:
                    url = _normalize_naver_article_url(candidate.get("provider_link_page") or candidate.get("url"))
                    if not url or url in seen_candidate_urls:
                        continue
                    seen_candidate_urls.add(url)
                    candidates.append(candidate)
                    if len(candidates) >= per_query:
                        break
                time.sleep(delay)
                if len(candidates) >= per_query:
                    break
            if len(candidates) >= per_query:
                break

        print(f"[NAVER_NEWS/{query}] 검색 후보: {len(candidates)}개")
        for candidate in candidates:
            if max_items is not None and len(records) >= max_items:
                break
            url = _normalize_naver_article_url(candidate.get("provider_link_page") or candidate.get("url"))
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
