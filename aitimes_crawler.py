"""
AITIMES Scrapling 크롤러 (수정 v2)

주요 수정:
- css_first → css_first 헬퍼 함수로 통일
- 자식 요소 선택 시 css(selector)[0] 패턴 사용
- 안전한 텍스트/속성 추출
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
from crawler_common import (
    safe_fetch, parallel_fetch_details, clean_text, normalize_url,
    css_first, get_text, get_attr
)


BASE_URL = 'https://www.aitimes.com'


def fetch_aitimes_detail(article_url):
    """단일 기사 본문"""
    try:
        page = safe_fetch(article_url, timeout=10)
        
        # 본문
        content_elem = css_first(page, '#article-view-content-div')
        content = clean_text(get_text(content_elem))
        
        # 카테고리
        category_elem = css_first(page, '.article-head-category') or css_first(page, '.breadcrumb a')
        category = get_text(category_elem)
        
        # 기자
        reporter_elem = css_first(page, '.byline em.name') or css_first(page, '.user-info .name')
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
    """AITIMES 크롤러 (Scrapling)"""
    seen_links = seen_links or set()
    threshold_date = datetime.now() - timedelta(days=days)
    
    print("[AITIMES] 기사 목록 수집 중...")
    
    list_url = f'{BASE_URL}/news/articleList.html'
    
    try:
        page = safe_fetch(list_url, timeout=10)
    except Exception as e:
        print(f"[AITIMES] 목록 페이지 실패: {e}")
        return []
    
    # 메인 페이지 객체 → page.css() 가능
    items = page.css('li.altlist-text-item')
    print(f"[AITIMES] {len(items)}개 항목 발견")
    
    articles_to_fetch = []
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        # 자식 요소 선택 시 css_first 헬퍼 사용
        a_tag = css_first(item, 'a')
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
        print(f"평균: {elapsed/len(data):.2f}초/기사")
        # 샘플 출력
        print(f"\n샘플 (첫 번째 기사):")
        print(f"제목: {data[0]['title']}")
        print(f"URL: {data[0]['url']}")
        print(f"본문 길이: {len(data[0]['content'])}")
