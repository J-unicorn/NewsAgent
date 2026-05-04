"""TECHWORLD Scrapling 크롤러 (Scrapling 0.4.7 정확한 API)"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
import re
from crawler_common import (
    first_element, get_text, get_attr, clean_text,
    normalize_url, parse_date_flexible, parallel_fetch_details
)


BASE_URL = 'https://www.epnc.co.kr'


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


def extract_category_from_title(title):
    """제목에서 [카테고리] 또는 <카테고리> 추출"""
    if not title:
        return '', ''
    title = str(title)
    match = re.match(r'\[([^\]]+)\](.*)', title)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    match = re.match(r'<([^>]+)>(.*)', title)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return '', title


def fetch_techworld_detail(article_url):
    """단일 기사 본문"""
    try:
        page = Fetcher.get(article_url, stealthy_headers=True, timeout=10)
        
        content_elem = first_element(page, '#article-view-content-div')
        content = get_all_text(content_elem)
        
        return {
            'content': content,
            'category_main': '',
            'category_sub': '',
            'reporter': '',
        }
    except Exception as e:
        print(f"  ❌ TECHWORLD 본문 실패: {e}")
        return {'content': '', 'category_main': '', 'category_sub': '', 'reporter': ''}


def get_techworld_data(driver=None, days=1, max_items=100, seen_links=None):
    """TECHWORLD 크롤러"""
    seen_links = seen_links or set()
    threshold_date = datetime.now() - timedelta(days=days)
    
    print("[TECHWORLD] 기사 목록 수집 중...")
    
    list_url = f'{BASE_URL}/news/articleList.html'
    
    try:
        page = Fetcher.get(list_url, stealthy_headers=True, timeout=10)
    except Exception as e:
        print(f"[TECHWORLD] 목록 실패: {e}")
        return []
    
    items = page.css('li.altlist-text-item')
    print(f"[TECHWORLD] {len(items)}개 항목 발견")
    
    articles_to_fetch = []
    
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        a_tag = first_element(item, 'a[href*="articleView"]')
        if not a_tag:
            continue
        
        title_text = get_text(a_tag)
        raw_link = get_attr(a_tag, 'href')
        
        if not title_text or not raw_link:
            continue
        
        url = normalize_url(raw_link, BASE_URL)
        
        if url in seen_links:
            continue
        
        category, title = extract_category_from_title(title_text)
        
        info_items = [get_all_text(elem) for elem in item.css('.altlist-info-item')]
        if info_items and not category:
            category = info_items[0]
        reporter = info_items[1] if len(info_items) > 1 else ''
        date_str = info_items[2] if len(info_items) > 2 else ''
        article_date = parse_date_flexible(date_str)
        
        if article_date and article_date < threshold_date:
            continue
        
        articles_to_fetch.append({
            'title': title or title_text,
            'url': url,
            'provider': '테크월드뉴스',
            'provider_link_page': url,
            'category_main': category,
            'reporter': reporter,
            'date': article_date.strftime('%Y-%m-%d %H:%M:%S') if article_date else '',
            'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    print(f"[TECHWORLD] 본문 수집 대상: {len(articles_to_fetch)}개")
    
    if not articles_to_fetch:
        return []
    
    results = parallel_fetch_details(
        articles_to_fetch,
        fetch_techworld_detail,
        max_workers=10,
        site_name='TECHWORLD'
    )
    
    print(f"[TECHWORLD] 완료: {len(results)}개 수집")
    return results


if __name__ == '__main__':
    import time
    start = time.time()
    data = get_techworld_data(days=1, max_items=20)
    elapsed = time.time() - start
    print(f"\n✅ {len(data)}개 기사, {elapsed:.1f}초")
