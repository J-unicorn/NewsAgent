"""
BUSINESSPOST Scrapling 크롤러 (정확한 공식 API)

StealthyFetcher를 정확하게 사용:
- StealthyFetcher.adaptive = True (글로벌 설정)
- StealthyFetcher.fetch(url, headless=True, network_idle=True)
- 봇 차단(403) 우회 가능
"""

from scrapling.fetchers import StealthyFetcher
from datetime import datetime, timedelta
from crawler_common import (
    safe_text, safe_attr, clean_text, normalize_url,
    parallel_fetch_details
)


BASE_URL = 'https://www.businesspost.co.kr'


def fetch_businesspost_page(url):
    """StealthyFetcher로 페이지 가져오기 (Cloudflare/봇 차단 우회)"""
    try:
        # 공식 권장 방식
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            # solve_cloudflare=True,  # Cloudflare Turnstile 자동 해결
        )
        return page
    except Exception as e:
        print(f"  ❌ BUSINESSPOST fetch 실패 ({url[:60]}): {e}")
        return None


def fetch_businesspost_detail(article_url):
    """단일 기사 본문"""
    try:
        page = fetch_businesspost_page(article_url)
        if not page:
            return {'content': '', 'category_main': '', 'category_sub': '', 'reporter': ''}
        
        content_elem = page.css_first('div.detail_editor')
        content = clean_text(safe_text(content_elem))
        
        category_elem = page.css_first('span.category')
        category = safe_text(category_elem)
        
        author_elem = page.css_first('div.author_info')
        reporter = ''
        if author_elem:
            author_text = safe_text(author_elem)
            reporter = author_text.split()[0] if author_text else ''
        
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
    
    print("[BUSINESSPOST] 기사 목록 수집 중 (StealthyFetcher 사용)...")
    
    list_url = f'{BASE_URL}/'
    
    page = fetch_businesspost_page(list_url)
    if not page:
        print("[BUSINESSPOST] 목록 실패")
        return []
    
    items = page.css('div.left_post')
    print(f"[BUSINESSPOST] {len(items)}개 항목 발견")
    
    articles_to_fetch = []
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        # 자식: Selector에서 css_first 사용
        a_tag = item.css_first('a')
        if not a_tag:
            continue
        
        title_elem = item.css_first('h3')
        title = safe_text(title_elem)
        
        raw_link = safe_attr(a_tag, 'href')
        if not title or not raw_link:
            continue
        
        url = normalize_url(raw_link, BASE_URL)
        
        if url in seen_links:
            continue
        
        articles_to_fetch.append({
            'title': title,
            'url': url,
            'provider': '비즈니스포스트',
            'provider_link_page': url,
            'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': '',
        })
    
    print(f"[BUSINESSPOST] 본문 수집 대상: {len(articles_to_fetch)}개")
    
    if not articles_to_fetch:
        return []
    
    # StealthyFetcher는 무거우므로 동시성 5
    results = parallel_fetch_details(
        articles_to_fetch,
        fetch_businesspost_detail,
        max_workers=5,
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
    if data:
        print(f"\n샘플: {data[0]['title']}")
