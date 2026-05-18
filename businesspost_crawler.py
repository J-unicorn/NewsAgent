"""BUSINESSPOST crawler: RSS first, browser fallback for blocked runners."""

from __future__ import annotations

from datetime import datetime, timedelta
import os
import re
import shutil
from xml.etree import ElementTree as ET

from crawler_common import (
    DetailConfig,
    RssConfig,
    clean_text,
    date_to_output,
    enrich_articles,
    fetch_page,
    finalize_article,
    first_element,
    get_all_text,
    get_attr,
    normalize_url,
    parse_date_any,
    response_text,
    strip_html_text,
    xml_find_text,
)


BASE_URL = "https://www.businesspost.co.kr"
PROVIDER = "비즈니스포스트"
BROWSER_MAX_PAGES = 5

RSS_CONFIG = RssConfig(
    url=f"{BASE_URL}/rss/Article.xml",
    provider=PROVIDER,
    reporter_path="author",
    category_path="category",
    content_path="description",
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=["div.detail_editor", "#article-view-content-div", "article"],
    category_selectors=[
        "span.category",
        ('meta[property="article:section"]', "content"),
        ('meta[property="og:category"]', "content"),
    ],
    reporter_selectors=[
        "div.author_info",
        ('meta[property="article:author"]', "content"),
        ('meta[name="author"]', "content"),
    ],
    date_selectors=[
        "div.author_info",
        ('meta[property="article:published_time"]', "content"),
    ],
)


def _article_base(title, url, date_obj=None, category_main="", category_sub="", reporter="", rss_content=""):
    return {
        "title": clean_text(title),
        "url": url,
        "provider": PROVIDER,
        "provider_link_page": url,
        "category_main": clean_text(category_main),
        "category_sub": clean_text(category_sub),
        "reporter": clean_text(reporter),
        "date": date_to_output(date_obj),
        "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_article_date": date_obj,
        "_rss_content": rss_content,
        "useful": 1,
        "strategy_agenda": 1,
    }


def _is_recent_businesspost(article_date, days):
    if not article_date:
        return True
    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    return article_date.date() >= cutoff_date


def _browser_kwargs():
    chrome_path = os.getenv("BUSINESSPOST_CHROME_PATH") or ""
    if not chrome_path:
        chrome_path = (
            shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")
            or shutil.which("chromium")
            or shutil.which("chromium-browser")
            or ""
        )

    kwargs = {
        "real_chrome": True,
        "headless": True,
        "timeout": 45_000,
        "wait": 500,
        "locale": "ko-KR",
        "timezone_id": "Asia/Seoul",
        "extra_flags": ["--no-sandbox", "--disable-dev-shm-usage"],
        "extra_headers": {"Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"},
    }
    if chrome_path:
        kwargs["executable_path"] = chrome_path
    return kwargs


def _dynamic_classes():
    try:
        from scrapling.fetchers import DynamicFetcher, DynamicSession

        return DynamicFetcher, DynamicSession
    except Exception as exc:
        print(f"[BUSINESSPOST] DynamicFetcher 사용 불가: {exc}")
        return None, None


def _parse_rss_text(xml_text, days=1, max_items=100, seen_links=None, site_name="BUSINESSPOST"):
    seen_links = seen_links or set()
    try:
        root = ET.fromstring(xml_text.strip())
    except Exception as exc:
        print(f"[{site_name}] Dynamic RSS 파싱 실패: {exc}")
        return []

    articles = []
    for item in root.findall("./channel/item"):
        title = xml_find_text(item, RSS_CONFIG.title_path, RSS_CONFIG.namespaces)
        url = normalize_url(xml_find_text(item, RSS_CONFIG.link_path, RSS_CONFIG.namespaces), RSS_CONFIG.url)
        date_text = xml_find_text(item, RSS_CONFIG.date_path, RSS_CONFIG.namespaces)
        reporter = xml_find_text(item, RSS_CONFIG.reporter_path, RSS_CONFIG.namespaces)
        category = xml_find_text(item, RSS_CONFIG.category_path, RSS_CONFIG.namespaces)
        rss_content = strip_html_text(xml_find_text(item, RSS_CONFIG.content_path, RSS_CONFIG.namespaces))
        article_date = parse_date_any(date_text)

        if not title or not url or url in seen_links or not _is_recent_businesspost(article_date, days):
            continue

        articles.append(
            _article_base(
                title=title,
                url=url,
                date_obj=article_date,
                category_main=category,
                reporter=reporter,
                rss_content=rss_content,
            )
        )
        if max_items and len(articles) >= max_items:
            break
    return articles


def _split_category(category_text):
    parts = clean_text(category_text, max_length=200).split()
    category_main = parts[0] if parts else "분류"
    category_sub = parts[1] if len(parts) > 1 else "뉴스"
    return category_main, category_sub


def _reporter_from_author_info(author_info):
    author_info = clean_text(author_info, max_length=300)
    if not author_info:
        return ""
    return re.sub(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?.*$", "", author_info).strip()


def _browser_detail(session, url):
    try:
        page = session.fetch(url, wait_selector="div.detail_editor", wait=500, timeout=45_000)
    except Exception as exc:
        print(f"[BUSINESSPOST] 상세 브라우저 수집 실패 ({url[:80]}): {exc}")
        return {}

    content = get_all_text(first_element(page, "div.detail_editor"), max_length=2_000)
    category_text = get_all_text(first_element(page, "span.category"), max_length=200)
    author_info = get_all_text(first_element(page, "div.author_info"), max_length=300)
    article_date = parse_date_any(author_info)
    category_main, category_sub = _split_category(category_text)

    result = {
        "category_main": category_main,
        "category_sub": category_sub,
    }
    if content:
        result["content"] = content
    if author_info:
        result["reporter"] = _reporter_from_author_info(author_info)
    if article_date:
        result["date"] = date_to_output(article_date)
        result["_article_date"] = article_date
    return result


def _browser_enrich_articles(articles, max_items=None):
    if not articles:
        return []

    _, DynamicSession = _dynamic_classes()
    if not DynamicSession:
        return [finalize_article(article) for article in articles]

    results = []
    with DynamicSession(**_browser_kwargs()) as session:
        for index, article in enumerate(articles, 1):
            detail = _browser_detail(session, article["provider_link_page"])
            merged = dict(article)
            for key, value in detail.items():
                if value:
                    merged[key] = value
            results.append(finalize_article(merged))
            if index % 25 == 0:
                print(f"[BUSINESSPOST] 브라우저 상세 진행: {index}/{len(articles)}")
            if max_items and len(results) >= max_items:
                break
    return results


def _collect_dynamic_rss_articles(days=1, max_items=100, seen_links=None):
    DynamicFetcher, _ = _dynamic_classes()
    if not DynamicFetcher:
        return []

    try:
        page = DynamicFetcher.fetch(RSS_CONFIG.url, **_browser_kwargs())
    except Exception as exc:
        print(f"[BUSINESSPOST] Dynamic RSS 수집 실패: {exc}")
        return []

    status = getattr(page, "status", None) or getattr(page, "status_code", None)
    print(f"[BUSINESSPOST] Dynamic RSS 응답: {status}")
    articles = _parse_rss_text(response_text(page), days=days, max_items=max_items, seen_links=seen_links)
    print(f"[BUSINESSPOST] Dynamic RSS 최근 {days}일 대상: {len(articles)}개")
    return articles


def _collect_http_rss_articles(days=1, max_items=100, seen_links=None):
    page = fetch_page(RSS_CONFIG.url, timeout=RSS_CONFIG.timeout, site_name="BUSINESSPOST")
    if not page:
        return []
    articles = _parse_rss_text(response_text(page), days=days, max_items=max_items, seen_links=seen_links)
    print(f"[BUSINESSPOST] RSS 최근 {days}일 대상: {len(articles)}개")
    return articles


def _collect_browser_list_articles(days=1, max_items=100, seen_links=None):
    _, DynamicSession = _dynamic_classes()
    if not DynamicSession:
        return []

    seen_links = set(seen_links or set())
    collected = []
    visited_urls = set()

    with DynamicSession(**_browser_kwargs()) as session:
        for page_no in range(1, BROWSER_MAX_PAGES + 1):
            list_url = f"{BASE_URL}/BP?command=sub&sub=8&page={page_no}"
            try:
                page = session.fetch(list_url, wait_selector="div.left_post", wait=500, timeout=45_000)
            except Exception as exc:
                print(f"[BUSINESSPOST] 목록 브라우저 수집 실패 ({list_url}): {exc}")
                break

            items = page.css("div.left_post")
            print(f"[BUSINESSPOST] 브라우저 목록 page={page_no}: {len(items)}개")
            if not items:
                break

            page_new_urls = 0
            page_dated = 0
            page_old = 0
            for item in items:
                link_elem = first_element(item, "a")
                title_elem = first_element(item, "h3")
                raw_url = get_attr(link_elem, "href")
                url = normalize_url(raw_url, BASE_URL)
                title = get_all_text(title_elem, max_length=0) or get_all_text(link_elem, max_length=0)

                if not title or not url or url in seen_links or url in visited_urls:
                    continue

                visited_urls.add(url)
                page_new_urls += 1
                base_article = _article_base(title=title, url=url)
                detail = _browser_detail(session, url)
                article_date = detail.get("_article_date")
                if not article_date:
                    continue

                page_dated += 1
                if not _is_recent_businesspost(article_date, days):
                    page_old += 1
                    continue

                merged = {**base_article, **detail}
                collected.append(finalize_article(merged))
                if max_items and len(collected) >= max_items:
                    return collected

            if page_new_urls == 0:
                break
            if page_dated > 0 and page_old == page_dated:
                break

    return collected


def get_businesspost_data(driver=None, days=1, max_items=100, seen_links=None):
    if max_items is not None and max_items <= 0:
        max_items = None
    seen_links = set(seen_links or set())

    print("[BUSINESSPOST] RSS 목록 수집 중...")
    rss_articles = _collect_http_rss_articles(days=days, max_items=max_items, seen_links=seen_links)

    if rss_articles:
        print(f"[BUSINESSPOST] HTTP RSS 성공: {len(rss_articles)}개")
        results = enrich_articles(rss_articles, detail_config=DETAIL_CONFIG, max_workers=5, site_name="BUSINESSPOST")
        print(f"[BUSINESSPOST] 완료: {len(results)}개 수집")
        return results

    print("[BUSINESSPOST] RSS 실패/0건: DynamicFetcher fallback 실행")
    dynamic_rss_articles = _collect_dynamic_rss_articles(days=days, max_items=max_items, seen_links=seen_links)
    if dynamic_rss_articles:
        results = _browser_enrich_articles(dynamic_rss_articles, max_items=max_items)
        print(f"[BUSINESSPOST] 완료: {len(results)}개 수집")
        return results

    print("[BUSINESSPOST] Dynamic RSS 실패/0건: 브라우저 목록 fallback 실행")
    results = _collect_browser_list_articles(days=days, max_items=max_items, seen_links=seen_links)
    print(f"[BUSINESSPOST] 완료: {len(results)}개 수집")
    return results


if __name__ == "__main__":
    data = get_businesspost_data(days=1, max_items=20)
    print(f"\n수집: {len(data)}건")
