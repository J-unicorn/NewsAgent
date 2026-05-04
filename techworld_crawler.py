"""
TECHWORLD Scrapling 크롤러
정적 HTML → Fetcher만 사용

기존 셀렉터:
- 목록: li
- 제목 링크: h2.titles a
- 날짜: em.info.dated
- 본문: #article-view-content-div
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
from crawler_common import parse_date_flexible, safe_fetch, parallel_fetch_details, clean_text, normalize_url


BASE_URL = 'https://www.epnc.co.kr'


def fetch_techworld_detail(article_url):
    """단일 기사 본문 가져오기"""
    try:
        page = safe_fetch(article_url, timeout=10)
        
        # 본문
        content_elem = page.css_first('#article-view-content-div')
        content = clean_text(content_elem.text) if content_elem else ''
        
        # 카테고리 (제목의 < > 기호로 추출 가능하지만 일단 빈 값)
        return {
            'content': content,
            'category_main': '',
            'category_sub': '',
            'reporter': '',
        }
    except Exception as e:
        print(f"  ❌ TECHWORLD 본문 실패: {e}")
        return {'content': '', 'category_main': '', 'category_sub': '', 'reporter': ''}


def extract_category_from_title(title):
    """제목에서 [카테고리] 또는 <카테고리> 추출"""
    import re
    # [카테고리] 패턴
    match = re.match(r'\[([^\]]+)\](.*)', title)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    # <카테고리> 패턴
    match = re.match(r'<([^>]+)>(.*)', title)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return '', title


def get_techworld_data(driver=None, days=1, max_items=100, seen_links=None):
    """TECHWORLD 크롤러 (Scrapling)"""
    seen_links = seen_links or set()
    threshold_date = datetime.now() - timedelta(days=days)
    
    print("[TECHWORLD] 기사 목록 수집 중...")
    
    list_url = f'{BASE_URL}/news/articleList.html'
    
    try:
        page = safe_fetch(list_url, timeout=10)
    except Exception as e:
        print(f"[TECHWORLD] 목록 실패: {e}")
        return []
    
    # 기사 목록
    items = page.css('li')
    print(f"[TECHWORLD] {len(items)}개 li 발견 (필터링 필요)")
    
    articles_to_fetch = []
    for item in items:
        if len(articles_to_fetch) >= max_items:
            break
        
        # 제목 링크 (셀렉터: h2.titles a)
        a_tag = item.css_first('h2.titles a')
        if not a_tag:
            continue
        
        title_text = a_tag.text.strip() if a_tag.text else ''
        raw_link = a_tag.attrib.get('href', '')
        if not title_text or not raw_link:
            continue
        
        url = normalize_url(raw_link, BASE_URL)
        
        if url in seen_links:
            continue
        
        # 카테고리 추출
        category, title = extract_category_from_title(title_text)
        
        # 날짜
        date_elem = item.css_first('em.info.dated')
        date_str = date_elem.text.strip() if date_elem else ''
        article_date = parse_date_flexible(date_str)
        
        if article_date and article_date < threshold_date:
            continue
        
        articles_to_fetch.append({
            'title': title or title_text,
            'url': url,
            'provider': '테크월드뉴스',
            'provider_link_page': url,
            'category_main': category,
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


# 단독 실행 테스트
if __name__ == '__main__':
    import time
    start = time.time()
    data = get_techworld_data(days=1, max_items=20)
    elapsed = time.time() - start
    print(f"\n✅ {len(data)}개 기사, {elapsed:.1f}초")
