"""Common helpers for Scrapling-based crawlers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
import re
import time
from typing import Callable, Iterable
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from scrapling.fetchers import Fetcher


DEFAULT_NAMESPACES = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
}


@dataclass
class RssConfig:
    url: str
    provider: str
    category_main_default: str = ""
    category_sub_default: str = ""
    title_path: str = "title"
    link_path: str = "link"
    date_path: str = "pubDate"
    reporter_path: str = "author"
    category_path: str = "category"
    content_path: str = ""
    namespaces: dict[str, str] = field(default_factory=dict)
    timeout: int = 15


SelectorSpec = str | tuple[str, str | None]


@dataclass
class SelectorConfig:
    list_url: str
    provider: str
    item_selector: str
    link_selector: str | None = None
    title_selector: SelectorSpec | None = None
    date_selector: SelectorSpec | None = None
    category_selector: SelectorSpec | None = None
    reporter_selector: SelectorSpec | None = None
    base_url: str = ""
    max_pages: int = 1
    list_url_builder: Callable[[int], str] | None = None
    category_main_default: str = ""
    category_sub_default: str = ""
    reporter_default: str = ""
    timeout: int = 15


@dataclass
class DetailConfig:
    content_selectors: list[str] = field(default_factory=list)
    category_selectors: list[str | tuple[str, str | None]] = field(default_factory=list)
    reporter_selectors: list[str | tuple[str, str | None]] = field(default_factory=list)
    date_selectors: list[str | tuple[str, str | None]] = field(default_factory=list)
    summary_selectors: list[str | tuple[str, str | None]] = field(default_factory=list)
    max_content_length: int = 2000
    timeout: int = 15


def first_element(parent, selector):
    """Return the first element matching selector, compatible with Scrapling 0.4+."""
    if parent is None:
        return None
    try:
        results = parent.css(selector)
        if not results or len(results) == 0:
            return None
        if hasattr(results, "first"):
            return results.first
        return results[0]
    except Exception:
        return None


def clean_text(text, max_length=2000):
    """Normalize whitespace and optionally truncate."""
    if not text:
        return ""
    text = unescape(re.sub(r"\s+", " ", str(text)).strip())
    if max_length and len(text) > max_length:
        text = text[:max_length] + "..."
    return text


def get_text(element, default=""):
    """Extract direct text from a Scrapling selector."""
    if element is None:
        return default
    try:
        text = element.text
        if text is not None and str(text).strip():
            return str(text).strip()
    except (AttributeError, TypeError):
        pass
    try:
        text_handler = element.css("::text")
        result = text_handler.get() if hasattr(text_handler, "get") else None
        if result:
            return str(result).strip()
    except Exception:
        pass
    return default


def get_all_text(element, max_length=2000):
    """Extract all descendant text from a Scrapling selector."""
    if element is None:
        return ""
    try:
        text_handler = element.css("::text")
        if hasattr(text_handler, "getall"):
            return clean_text(" ".join(text_handler.getall()), max_length=max_length)
    except Exception:
        pass
    return clean_text(get_text(element), max_length=max_length)


def get_attr(element, attr_name, default=""):
    """Extract an attribute value from a Scrapling selector."""
    if element is None:
        return default
    try:
        if hasattr(element, "attrib"):
            return str(element.attrib.get(attr_name, default))
    except (AttributeError, TypeError):
        pass
    try:
        attr_handler = element.css(f"::attr({attr_name})")
        result = attr_handler.get() if hasattr(attr_handler, "get") else None
        if result:
            return str(result)
    except Exception:
        pass
    return default


def strip_html_text(html_text, max_length=2000):
    """Convert small RSS HTML fragments into text."""
    if not html_text:
        return ""
    html_text = re.sub(r"(?is)<(script|style).*?</\1>", " ", str(html_text))
    html_text = re.sub(r"(?i)<br\s*/?>", " ", html_text)
    html_text = re.sub(r"(?i)</p\s*>", " ", html_text)
    html_text = re.sub(r"<[^>]+>", " ", html_text)
    return clean_text(html_text, max_length=max_length)


def normalize_url(raw_link, base_url):
    """Resolve relative URLs."""
    if not raw_link:
        return ""
    raw_link = str(raw_link).strip().replace("\\/", "/")
    if raw_link.startswith("http"):
        return raw_link
    return urljoin(base_url.rstrip("/") + "/", raw_link)


def _response_status(page):
    status = getattr(page, "status", None) or getattr(page, "status_code", None)
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def fetch_page(url, timeout=10, site_name="", max_retries=3, backoff_seconds=2):
    prefix = f"[{site_name}] " if site_name else ""
    for attempt in range(1, max(max_retries, 1) + 1):
        try:
            page = Fetcher.get(url, stealthy_headers=True, timeout=timeout)
            status = _response_status(page)
            if status in {403, 429} and attempt < max_retries:
                wait = backoff_seconds * attempt
                print(f"{prefix}fetch {status}, {wait}s 후 재시도 ({attempt}/{max_retries}): {url[:80]}")
                time.sleep(wait)
                continue
            return page
        except Exception as e:
            if attempt < max_retries:
                wait = backoff_seconds * attempt
                print(f"{prefix}fetch 실패, {wait}s 후 재시도 ({attempt}/{max_retries}) ({url[:80]}): {e}")
                time.sleep(wait)
                continue
            print(f"{prefix}fetch 실패 ({url[:80]}): {e}")
            return None


def response_text(page):
    if page is None:
        return ""
    body = getattr(page, "body", "")
    if isinstance(body, bytes):
        for encoding in ("utf-8", "gb18030", "gbk", "euc-kr"):
            try:
                return body.decode(encoding)
            except Exception:
                continue
        return body.decode("utf-8", "ignore")
    return str(body or page)


def parse_date_any(date_str, current_year=None):
    """Parse dates commonly seen in RSS, Korean, Chinese, and news list pages."""
    if not date_str:
        return None
    current_year = current_year or datetime.now().year
    date_str = clean_text(date_str, max_length=0)

    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass

    try:
        normalized = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        pass

    patterns = [
        (
            r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})",
            lambda m: datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5])),
        ),
        (
            r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})",
            lambda m: datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4])),
        ),
        (
            r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})",
            lambda m: datetime(int(m[0]), int(m[1]), int(m[2])),
        ),
        (
            r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
            lambda m: datetime(int(m[0]), int(m[1]), int(m[2])),
        ),
        (
            r"(\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})",
            lambda m: datetime(current_year, int(m[0]), int(m[1]), int(m[2]), int(m[3])),
        ),
    ]
    for pattern, parser in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                parsed = parser(match.groups())
                if parsed.replace(tzinfo=None) > datetime.now() + timedelta(days=1):
                    parsed = parsed.replace(year=parsed.year - 1)
                return parsed
            except Exception:
                continue
    return None


def parse_date_flexible(date_str, current_year=None):
    """Backward-compatible wrapper."""
    return parse_date_any(date_str, current_year=current_year)


def date_to_output(article_date):
    if not article_date:
        return ""
    return article_date.strftime("%Y-%m-%d %H:%M:%S")


def is_recent(article_date, days):
    if not article_date:
        return True
    if getattr(article_date, "tzinfo", None):
        threshold = datetime.now(article_date.tzinfo) - timedelta(days=days)
        return article_date >= threshold
    return article_date >= datetime.now() - timedelta(days=days)


def xml_find_text(item, path, namespaces=None):
    namespaces = {**DEFAULT_NAMESPACES, **(namespaces or {})}
    if not path:
        return ""
    if ":" in path:
        prefix, local = path.split(":", 1)
        uri = namespaces.get(prefix)
        if uri:
            return item.findtext(f"{{{uri}}}{local}") or ""
    return item.findtext(path) or ""


def _base_article(title, url, provider, date_obj=None, category_main="", category_sub="", reporter="", rss_content=""):
    return {
        "title": clean_text(title),
        "url": url,
        "provider": provider,
        "provider_link_page": url,
        "category_main": clean_text(category_main),
        "category_sub": clean_text(category_sub),
        "reporter": clean_text(reporter),
        "date": date_to_output(date_obj),
        "enveloped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_article_date": date_obj,
        "_rss_content": rss_content,
    }


def parse_rss_articles(config: RssConfig, days=1, max_items=100, seen_links=None, site_name=""):
    seen_links = seen_links or set()
    page = fetch_page(config.url, timeout=config.timeout, site_name=site_name)
    if not page:
        return []
    try:
        root = ET.fromstring(response_text(page).strip())
    except Exception as e:
        print(f"[{site_name}] RSS 파싱 실패: {e}")
        return []

    articles = []
    for item in root.findall("./channel/item"):
        title = xml_find_text(item, config.title_path, config.namespaces)
        url = xml_find_text(item, config.link_path, config.namespaces)
        date_str = xml_find_text(item, config.date_path, config.namespaces)
        reporter = xml_find_text(item, config.reporter_path, config.namespaces)
        category = xml_find_text(item, config.category_path, config.namespaces)
        rss_content = strip_html_text(xml_find_text(item, config.content_path, config.namespaces)) if config.content_path else ""

        url = normalize_url(url, config.url)
        article_date = parse_date_any(date_str)
        if not title or not url or url in seen_links or not is_recent(article_date, days):
            continue

        articles.append(
            _base_article(
                title=title,
                url=url,
                provider=config.provider,
                date_obj=article_date,
                category_main=category or config.category_main_default,
                category_sub=config.category_sub_default,
                reporter=reporter,
                rss_content=rss_content,
            )
        )
        if max_items and len(articles) >= max_items:
            break
    return articles


def _selector_value(parent, spec: SelectorSpec | None):
    if not spec:
        return ""
    selector, attr = spec if isinstance(spec, tuple) else (spec, None)
    elem = first_element(parent, selector)
    if attr:
        return clean_text(get_attr(elem, attr), max_length=0)
    return get_all_text(elem, max_length=0)


def parse_selector_articles(config: SelectorConfig, days=1, max_items=100, seen_links=None, site_name=""):
    seen_links = seen_links or set()
    articles = []
    for page_no in range(1, max(config.max_pages, 1) + 1):
        list_url = config.list_url_builder(page_no) if config.list_url_builder else config.list_url
        page = fetch_page(list_url, timeout=config.timeout, site_name=site_name)
        if not page:
            break

        items = page.css(config.item_selector)
        if not items:
            break

        page_added = 0
        dated_items = 0
        old_dated_items = 0
        for item in items:
            link_elem = first_element(item, config.link_selector) if config.link_selector else item
            if not link_elem:
                continue

            raw_url = get_attr(link_elem, "href")
            url = normalize_url(raw_url, config.base_url or list_url)
            title = _selector_value(item, config.title_selector) if config.title_selector else get_all_text(link_elem, max_length=0)
            date_text = _selector_value(item, config.date_selector)
            category = _selector_value(item, config.category_selector) or config.category_main_default
            reporter = _selector_value(item, config.reporter_selector) or config.reporter_default
            article_date = parse_date_any(date_text)

            if article_date:
                dated_items += 1
                if not is_recent(article_date, days):
                    old_dated_items += 1
                    continue

            if not title or not url or url in seen_links:
                continue

            articles.append(
                _base_article(
                    title=title,
                    url=url,
                    provider=config.provider,
                    date_obj=article_date,
                    category_main=category,
                    category_sub=config.category_sub_default,
                    reporter=reporter,
                )
            )
            page_added += 1
            if max_items and len(articles) >= max_items:
                return articles

        if page_added == 0 and dated_items > 0 and old_dated_items == dated_items:
            break
        if not config.list_url_builder:
            break
    return articles


def extract_by_specs(page, specs: Iterable[SelectorSpec], max_length=2000):
    for spec in specs or []:
        selector, attr = spec if isinstance(spec, tuple) else (spec, None)
        elem = first_element(page, selector)
        if not elem:
            continue
        if attr:
            value = get_attr(elem, attr)
            if value:
                return clean_text(value, max_length=max_length)
        else:
            value = get_all_text(elem, max_length=max_length)
            if value:
                return value
    return ""


def fetch_detail(article, detail_config: DetailConfig | None, site_name=""):
    if not detail_config:
        return {}
    page = fetch_page(article["url"], timeout=detail_config.timeout, site_name=site_name)
    if not page:
        return {}

    content = extract_by_specs(page, detail_config.content_selectors, max_length=detail_config.max_content_length)
    category = extract_by_specs(page, detail_config.category_selectors, max_length=200)
    reporter = extract_by_specs(page, detail_config.reporter_selectors, max_length=200)
    date_text = extract_by_specs(page, detail_config.date_selectors, max_length=200)
    summary = extract_by_specs(page, detail_config.summary_selectors, max_length=200)
    article_date = parse_date_any(date_text)

    result = {}
    if content:
        result["content"] = content
    if category:
        result["category_main"] = category
    if reporter:
        result["reporter"] = reporter
    if article_date:
        result["date"] = date_to_output(article_date)
        result["_article_date"] = article_date
    if summary:
        result["content_summary"] = summary
    return result


def finalize_article(article):
    article = dict(article)
    content = article.get("content") or article.pop("_rss_content", "")
    article["content"] = clean_text(content)
    article["content_summary"] = article.get("content_summary") or clean_text(article["content"][:200])

    date_obj = article.pop("_article_date", None)
    if not article.get("date") and date_obj:
        article["date"] = date_to_output(date_obj)

    if date_obj:
        article["YEAR"] = date_obj.year
        article["MONTH"] = date_obj.month
        article["WEEK"] = date_obj.isocalendar()[1]
    elif article.get("date"):
        parsed = parse_date_any(article["date"])
        if parsed:
            article["YEAR"] = parsed.year
            article["MONTH"] = parsed.month
            article["WEEK"] = parsed.isocalendar()[1]
    return article


def enrich_articles(articles, detail_config=None, max_workers=10, site_name="", request_delay=0):
    if not articles:
        return []
    if not detail_config:
        return [finalize_article(article) for article in articles]

    max_workers = max(int(max_workers or 1), 1)
    request_delay = float(request_delay or 0)
    results = []

    def _merge_batch(batch):
        batch_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_article = {
                executor.submit(fetch_detail, article, detail_config, site_name): article
                for article in batch
            }
            for future in as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    detail = future.result()
                except Exception as e:
                    print(f"[{site_name}] 상세 실패 ({article.get('url', '')[:80]}): {e}")
                    detail = {}
                merged = dict(article)
                for key, value in detail.items():
                    if value:
                        merged[key] = value
                batch_results.append(finalize_article(merged))
        return batch_results

    if request_delay > 0:
        for start in range(0, len(articles), max_workers):
            results.extend(_merge_batch(articles[start : start + max_workers]))
            if site_name and len(results) % 25 == 0:
                print(f"[{site_name}] 진행: {len(results)}/{len(articles)}")
            if start + max_workers < len(articles):
                time.sleep(request_delay)
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_article = {
            executor.submit(fetch_detail, article, detail_config, site_name): article
            for article in articles
        }
        for i, future in enumerate(as_completed(future_to_article), 1):
            article = future_to_article[future]
            try:
                detail = future.result()
            except Exception as e:
                print(f"[{site_name}] 상세 실패 ({article.get('url', '')[:80]}): {e}")
                detail = {}
            merged = dict(article)
            for key, value in detail.items():
                if value:
                    merged[key] = value
            results.append(finalize_article(merged))
            if site_name and i % 25 == 0:
                print(f"[{site_name}] 진행: {i}/{len(articles)}")
    return results


def collect_site_articles(
    site_name,
    rss_config=None,
    selector_config=None,
    detail_config=None,
    days=1,
    max_items=100,
    seen_links=None,
    detail_workers=10,
    detail_request_delay=0,
):
    seen_links = seen_links or set()
    articles = []

    if rss_config:
        print(f"[{site_name}] RSS 목록 수집 중...")
        articles = parse_rss_articles(rss_config, days=days, max_items=max_items, seen_links=seen_links, site_name=site_name)
        print(f"[{site_name}] RSS 최근 {days}일 대상: {len(articles)}개")

    if not articles and selector_config:
        print(f"[{site_name}] selector fallback 실행")
        articles = parse_selector_articles(selector_config, days=days, max_items=max_items, seen_links=seen_links, site_name=site_name)
        print(f"[{site_name}] selector 대상: {len(articles)}개")

    print(f"[{site_name}] 본문 수집 대상: {len(articles)}개")
    results = enrich_articles(
        articles,
        detail_config=detail_config,
        max_workers=detail_workers,
        site_name=site_name,
        request_delay=detail_request_delay,
    )
    print(f"[{site_name}] 완료: {len(results)}개 수집")
    return results


def parallel_fetch_details(article_list, detail_parser, max_workers=10, site_name=""):
    """Backward-compatible detail fetcher."""
    if not article_list:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_article = {executor.submit(detail_parser, art["url"]): art for art in article_list}
        for i, future in enumerate(as_completed(future_to_article), 1):
            art = future_to_article[future]
            try:
                results.append({**art, **future.result()})
                if i % 25 == 0 and site_name:
                    print(f"[{site_name}] 진행: {i}/{len(article_list)}")
            except Exception as e:
                print(f"[{site_name}] {art.get('url', '')[:60]} 실패: {e}")
                results.append({**art, "content": ""})
    return results


def translate_text(text, enabled=True, max_retries=3):
    if not enabled or not text:
        return text or ""
    try:
        from deep_translator import GoogleTranslator
    except Exception:
        return text

    chunks = [str(text)[i:i + 1500] for i in range(0, min(len(str(text)), 4500), 1500)]
    translated = []
    for chunk in chunks:
        chunk_result = chunk
        for _ in range(max_retries):
            try:
                result = GoogleTranslator(source="auto", target="ko").translate(chunk)
                if result:
                    chunk_result = result
                    break
            except Exception:
                continue
        translated.append(chunk_result)
    return " ".join(translated)


def translate_records(records, fields, max_workers=4):
    tasks = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, record in enumerate(records):
            for field_name in fields:
                value = record.get(field_name, "")
                if value:
                    tasks.append((idx, field_name, executor.submit(translate_text, value, True)))
        for idx, field_name, future in tasks:
            try:
                records[idx][field_name] = future.result()
            except Exception:
                pass
    return records


def apply_record_defaults(records, **defaults):
    for record in records:
        for key, value in defaults.items():
            if key not in record or record.get(key) in ("", None):
                record[key] = value
    return records
