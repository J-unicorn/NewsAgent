"""
BUSINESSPOST Scrapling 크롤러 (Scrapling 0.4.7 정확한 API)
RSS 목록 + 상세 페이지 원문 수집
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from crawler_common import (
    first_element, get_text, clean_text, parallel_fetch_details
)


BASE_URL = 'https://www.businesspost.co.kr'
RSS_URL = f'{BASE_URL}/rss/Article.xml'


def fetch_businesspost_page(url):
    """Fetcher로 페이지 가져오기"""
    try:
        return Fetcher.get(url, stealthy_headers=True, timeout=10)
    except Exception as e:
        print(f"  ❌ BUSINESSPOST fetch 실패 ({url[:60]}): {e}")
        return None


def get_all_text(element):
    """Selector 하위의 모든 텍스트를 공백 정리해서 반환"""
    if element is None:
        return ''
    try:
        text_handler = element.css('::text')
        if hasattr(text_handler, 'getall'):
            return clean_text(' '.join(text_handler.getall()))
    except Exception:
        pass
    return clean_text(get_text(element))


def get_meta_content(page, selector):
    elem = first_element(page, selector)
    if elem and hasattr(elem, 'attrib'):
        return clean_text(elem.attrib.get('content', ''))
    return ''


def parse_rss_datetime(date_str):
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def parse_businesspost_rss(page):
    """RSS XML에서 기사 목록 추출"""
    try:
        raw = ''
        if hasattr(page, 'body'):
            body = page.body
            raw = body.decode('utf-8', 'ignore') if isinstance(body, bytes) else str(body)
        if not raw.strip().startswith('<?xml'):
            raw = str(page)

        root = ET.fromstring(raw)
    except Exception as e:
        print(f"[BUSINESSPOST] RSS 파싱 실패: {e}")
        return []

    articles = []
    for item in root.findall('./channel/item'):
        title = clean_text(item.findtext('title'))
        link = clean_text(item.findtext('link'))
        reporter = clean_text(item.findtext('author'))
        pub_date = clean_text(item.findtext('pubDate'))
        article_date = parse_rss_datetime(pub_date)

        if not title or not link:
            continue

        articles.append({
            'title': title,
            'url': link,
            'provider': '비즈니스포스트',
            'provider_link_page': link,
            'category_main': '',
            'category_sub': '',
            'reporter': reporter,
            'date': article_date.strftime('%Y-%m-%d %H:%M:%S') if article_date else '',
            'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '_article_date': article_date,
        })
    return articles


def fetch_businesspost_detail(article_url):
    """단일 기사 본문"""
    try:
        page = fetch_businesspost_page(article_url)
        if not page:
            return {'content': '', 'category_main': '', 'category_sub': '', 'reporter': ''}
        
        content_elem = first_element(page, 'div.detail_editor')
        content = get_all_text(content_elem)

        category = (
            get_meta_content(page, 'meta[property="article:section"]') or
            get_meta_content(page, 'meta[property="og:category"]')
        )

        reporter = get_meta_content(page, 'meta[property="article:author"]')
        
        return {
            'content': content,
            'category_main': category,
            'category_sub': '',
            'reporter': reporter,
        }
    except Exception as e:
        print(f"  ❌ BUSINESSPOST 본문 실패: {e}")
        return {'content': '', 'category_main': '', 'category_sub': '', 'reporter': ''}


def get_businesspost_data(driver=None, days=1, max_items=100, seen_links=None):
    """BUSINESSPOST 크롤러"""
    seen_links = seen_links or set()
    threshold_date = datetime.now() - timedelta(days=days)
    
    print("[BUSINESSPOST] RSS 기사 목록 수집 중...")
    
    page = fetch_businesspost_page(RSS_URL)
    if not page:
        print("[BUSINESSPOST] 목록 실패")
        return []
    
    rss_articles = parse_businesspost_rss(page)
    print(f"[BUSINESSPOST] RSS {len(rss_articles)}개 항목 발견")
    
    articles_to_fetch = []
    for article in rss_articles:
        if len(articles_to_fetch) >= max_items:
            break

        url = article['url']
        if url in seen_links:
            continue

        article_date = article.pop('_article_date', None)
        if article_date:
            threshold = datetime.now(article_date.tzinfo) - timedelta(days=days) if article_date.tzinfo else threshold_date
            if article_date < threshold:
                continue

        articles_to_fetch.append(article)
    
    print(f"[BUSINESSPOST] 본문 수집 대상: {len(articles_to_fetch)}개")
    
    if not articles_to_fetch:
        return []
    
    results = parallel_fetch_details(
        articles_to_fetch,
        fetch_businesspost_detail,
        max_workers=10,
        site_name='BUSINESSPOST'
    )
    
    print(f"[BUSINESSPOST] 완료: {len(results)}개 수집")
    return results


if __name__ == '__main__':
    import time
    start = time.time()
    data = get_businesspost_data(days=1, max_items=10)
    elapsed = time.time() - start
    print(f"\n✅ {len(data)}개 기사, {elapsed:.1f}초")
