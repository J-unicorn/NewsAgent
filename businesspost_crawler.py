"""
BUSINESSPOST Scrapling 크롤러
정적 HTML → Fetcher만 사용

기존 셀렉터:
- 목록: div.left_post
- 제목: h3 (with a tag)
- 카테고리: span.category
- 작성자: div.author_info
- 본문: div.detail_editor
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
from crawler_common import parse_date_flexible, safe_fetch, parallel_fetch_details, clean_text, normalize_url


BASE_URL = 'https://www.businesspost.co.kr'


def fetch_businesspost_detail(article_url):
    """단일 기사 본문"""
    try:
        page = safe_fetch(article_url, timeout=10)
        
        # 본문
        content_elem = page.css_first('div.detail_editor')
        content = clean_text(content_elem.text) if content_elem else ''
        
        # 카테고리
        category_elem = page.css_first('span.category')
        category = category_elem.text.strip() if category_elem else ''
        
        # 작성자
        author_elem = page.css_first('div.author_info')
        reporter = ''
        if author_elem:
            author_text = author_elem.text.strip()
            # 보통 "기자명 reporter@email.com" 형식
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
    
    print("[BUSINESSPOST] 기사 목록 수집 중...")
    
    # 비즈니스포스트 메인 또는 뉴스 목록
    list_url = f'{BASE_URL}/'
    
    try:
        page = safe_fetch(list_url, timeout=10)
    except Exception as e:
        print(f"[BUSINESSPOST] 목록 실패: {e}")
        return []
    
    # 기사 목록 (셀렉터: div.left_post)
    items = page.css('div.left_post')
    print(f"[BUSINESSPOST] {len(items)}개 항목 발견")
    
    articles_to_fetch = []
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        a_tag = item.css_first('a')
        if not a_tag:
            continue
        
        # 제목 (h3)
        title_elem = item.css_first('h3')
        title = title_elem.text.strip() if title_elem else ''
        
        raw_link = a_tag.attrib.get('href', '')
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
    data = get_businesspost_data(days=1, max_items=20)
    elapsed = time.time() - start
    print(f"\n✅ {len(data)}개 기사, {elapsed:.1f}초")
