"""
AITIMES Scrapling 크롤러 (Scrapling 0.4.7 정확한 API)

API 변경 (0.4+):
- css_first 제거됨
- 대신: css(...).first 또는 css(...)[0]
- 헬퍼: first_element(parent, selector)
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
from crawler_common import (
    first_element, get_text, get_attr, clean_text,
    normalize_url, parallel_fetch_details
)


BASE_URL = 'https://www.aitimes.com'


def fetch_aitimes_detail(article_url):
    """단일 기사 본문"""
    try:
        page = Fetcher.get(article_url, stealthy_headers=True, timeout=10)
        
        # 0.4+: first_element 헬퍼 사용 (안전)
        content_elem = first_element(page, '#article-view-content-div')
        content = clean_text(get_text(content_elem))
        
        category_elem = (
            first_element(page, '.article-head-category') or
            first_element(page, '.breadcrumb a')
        )
        category = get_text(category_elem)
        
        reporter_elem = (
            first_element(page, '.byline em.name') or
            first_element(page, '.user-info .name')
        )
        reporter = get_text(reporter_elem)
        
        return {
            'content': content,
            'category_main': category,
            'category_sub': '',
            'reporter': reporter,
        }
    except Exception as e:
        print(f"  ❌ AITIMES 본문 실패 ({article_url[:60]}): {e}")
        return {'content': '', 'category_main': '', 'category_sub': '', 'reporter': ''}


def get_aitimes_data(driver=None, days=1, max_items=100, seen_links=None):
    """AITIMES 크롤러 (Scrapling 0.4+)"""
    seen_links = seen_links or set()
    threshold_date = datetime.now() - timedelta(days=days)
    
    print("[AITIMES] 기사 목록 수집 중...")
    
    list_url = f'{BASE_URL}/news/articleList.html'
    
    try:
        page = Fetcher.get(list_url, stealthy_headers=True, timeout=10)
    except Exception as e:
        print(f"[AITIMES] 목록 페이지 실패: {e}")
        return []
    
    # page.css() → Selectors (List)
    items = page.css('li.altlist-text-item')
    print(f"[AITIMES] {len(items)}개 항목 발견")
    
    articles_to_fetch = []
    
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        # ✅ 0.4+: first_element 헬퍼로 안전하게
        a_tag = first_element(item, 'a')
        if not a_tag:
            continue
        
        title = get_text(a_tag)
        raw_link = get_attr(a_tag, 'href')
        
        if not title or not raw_link:
            continue
        
        url = normalize_url(raw_link, BASE_URL)
        
        if url in seen_links:
            continue
        
        articles_to_fetch.append({
            'title': title,
            'url': url,
            'provider': 'AI타임스',
            'provider_link_page': url,
            'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': '',
        })
    
    print(f"[AITIMES] 본문 수집 대상: {len(articles_to_fetch)}개")
    
    if not articles_to_fetch:
        return []
    
    results = parallel_fetch_details(
        articles_to_fetch,
        fetch_aitimes_detail,
        max_workers=10,
        site_name='AITIMES'
    )
    
    print(f"[AITIMES] 완료: {len(results)}개 수집")
    return results


if __name__ == '__main__':
    import time
    start = time.time()
    data = get_aitimes_data(days=1, max_items=20)
    elapsed = time.time() - start
    print(f"\n✅ {len(data)}개 기사, {elapsed:.1f}초")
    if data:
        print(f"\n샘플:")
        print(f"  제목: {data[0]['title']}")
        print(f"  본문 길이: {len(data[0]['content'])}")
