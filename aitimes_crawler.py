"""
AITIMES Scrapling 크롤러
정적 HTML → Fetcher만 사용

기존 셀렉터:
- 목록: li.altlist-text-item
- 링크: a (각 li 내부)
- 본문: #article-view-content-div
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
from crawler_common import parse_date_flexible, safe_fetch, parallel_fetch_details, clean_text, normalize_url


BASE_URL = 'https://www.aitimes.com'


def fetch_aitimes_detail(article_url):
    """단일 기사 본문 가져오기"""
    try:
        page = safe_fetch(article_url, timeout=10)
        
        # 본문 (셀렉터: #article-view-content-div)
        content_elem = page.css_first('#article-view-content-div')
        content = clean_text(content_elem.text) if content_elem else ''
        
        # 카테고리
        category_elem = page.css_first('.article-head-category') or page.css_first('.breadcrumb a')
        category = category_elem.text.strip() if category_elem else ''
        
        # 기자
        reporter_elem = page.css_first('.byline em.name') or page.css_first('.user-info .name')
        reporter = reporter_elem.text.strip() if reporter_elem else ''
        
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
    """
    AITIMES 크롤러 (Scrapling)
    driver 파라미터는 인터페이스 호환용 (사용 안 함)
    """
    seen_links = seen_links or set()
    threshold_date = datetime.now() - timedelta(days=days)
    
    print("[AITIMES] 기사 목록 수집 중...")
    
    list_url = f'{BASE_URL}/news/articleList.html'
    
    try:
        page = safe_fetch(list_url, timeout=10)
    except Exception as e:
        print(f"[AITIMES] 목록 페이지 실패: {e}")
        return []
    
    # 기사 목록 (셀렉터: li.altlist-text-item)
    items = page.css('li.altlist-text-item')
    print(f"[AITIMES] {len(items)}개 항목 발견")
    
    articles_to_fetch = []
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        # 링크
        a_tag = item.css_first('a')
        if not a_tag:
            continue
        
        title = a_tag.text.strip() if a_tag.text else ''
        raw_link = a_tag.attrib.get('href', '')
        if not title or not raw_link:
            continue
        
        url = normalize_url(raw_link, BASE_URL)
        
        # 중복 체크
        if url in seen_links:
            continue
        
        articles_to_fetch.append({
            'title': title,
            'url': url,
            'provider': 'AI타임스',
            'provider_link_page': url,
            'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': '',  # 본문에서 추출 가능하면 보충
        })
    
    print(f"[AITIMES] 본문 수집 대상: {len(articles_to_fetch)}개")
    
    if not articles_to_fetch:
        return []
    
    # 본문 병렬 수집 (10개 동시)
    results = parallel_fetch_details(
        articles_to_fetch,
        fetch_aitimes_detail,
        max_workers=10,
        site_name='AITIMES'
    )
    
    print(f"[AITIMES] 완료: {len(results)}개 수집")
    return results


# 단독 실행 시 테스트용
if __name__ == '__main__':
    import time
    start = time.time()
    data = get_aitimes_data(days=1, max_items=20)
    elapsed = time.time() - start
    print(f"\n✅ {len(data)}개 기사, {elapsed:.1f}초")
    if data:
        print(f"평균: {elapsed/len(data):.2f}초/기사")
