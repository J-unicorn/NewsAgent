"""
AITIMES Scrapling 크롤러 (정확한 공식 API)

공식 API 사용 패턴:
- page.css('selector')              → Selectors (List of Selector)
- page.css_first('selector')        → 첫 번째 Selector (10% 빠름)
- selector.css('selector')          → 자식 Selectors (Selector에서 호출 시 작동!)
- selector.css_first('selector')    → 자식 첫 번째 (Selector에서 작동!)
- selector.text                     → TextHandler (str-like)
- selector.attrib['key']            → 속성값
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
from crawler_common import (
    safe_text, safe_attr, clean_text, normalize_url,
    parallel_fetch_details
)


BASE_URL = 'https://www.aitimes.com'


def fetch_aitimes_detail(article_url):
    """단일 기사 본문"""
    try:
        # adaptive=True: 사이트 변경에 자동 적응
        page = Fetcher.get(article_url, stealthy_headers=True, timeout=10)
        
        # css_first는 Selector 반환 (없으면 None 반환)
        content_elem = page.css_first('#article-view-content-div')
        content = clean_text(safe_text(content_elem))
        
        category_elem = page.css_first('.article-head-category') or page.css_first('.breadcrumb a')
        category = safe_text(category_elem)
        
        reporter_elem = page.css_first('.byline em.name') or page.css_first('.user-info .name')
        reporter = safe_text(reporter_elem)
        
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
    """AITIMES 크롤러 - 정확한 Scrapling API"""
    seen_links = seen_links or set()
    threshold_date = datetime.now() - timedelta(days=days)
    
    print("[AITIMES] 기사 목록 수집 중...")
    
    list_url = f'{BASE_URL}/news/articleList.html'
    
    try:
        page = Fetcher.get(list_url, stealthy_headers=True, timeout=10)
    except Exception as e:
        print(f"[AITIMES] 목록 페이지 실패: {e}")
        return []
    
    # ✅ page.css() → Selectors (List of Selector)
    items = page.css('li.altlist-text-item')
    print(f"[AITIMES] {len(items)}개 항목 발견")
    
    articles_to_fetch = []
    
    # ✅ items는 Selectors지만 iter하면 각 element는 Selector
    # ✅ Selector는 css_first() 사용 가능!
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        # ✅ 자식 element에서 css_first() 사용
        a_tag = item.css_first('a')
        if not a_tag:
            continue
        
        # ✅ Selector.text → TextHandler (str)
        title = safe_text(a_tag)
        
        # ✅ Selector.attrib → AttributesHandler (dict-like)
        raw_link = safe_attr(a_tag, 'href')
        
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
        print(f"  URL: {data[0]['url']}")
