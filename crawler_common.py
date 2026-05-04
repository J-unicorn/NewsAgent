"""
Scrapling 0.4+ 정확한 API 사용

공식 문서 기반:
- Selector.css() / .css_first() / .xpath() / .xpath_first()
- Selectors (List) 는 .css() 만 가능 (css_first 없음)
- adaptive=True로 자동 적응
- StealthyFetcher.adaptive = True 설정 가능
"""

from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher
from datetime import datetime, timedelta
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# StealthyFetcher 글로벌 설정 (공식 권장)
# adaptive=True: 사이트 구조 변경에 자동 적응
# ============================================================
StealthyFetcher.adaptive = True


def safe_text(element, default=''):
    """Selector에서 텍스트 추출 (안전)"""
    if element is None:
        return default
    try:
        # Scrapling의 Selector는 .text 속성 (TextHandler 반환)
        text = element.text
        return str(text).strip() if text else default
    except (AttributeError, TypeError):
        return default


def safe_attr(element, attr_name, default=''):
    """Selector에서 속성값 추출 (안전)"""
    if element is None:
        return default
    try:
        # Scrapling의 attrib은 AttributesHandler (dict-like)
        if hasattr(element, 'attrib'):
            return str(element.attrib.get(attr_name, default))
        return default
    except (AttributeError, TypeError):
        return default


def parse_date_flexible(date_str, current_year=None):
    """다양한 날짜 형식 파싱"""
    if not date_str:
        return None
    
    if current_year is None:
        current_year = datetime.now().year
    
    date_str = str(date_str).strip()
    
    patterns = [
        (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))),
        (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]))),
        (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]))),
        (r'(\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})',
         lambda m: datetime(current_year, int(m[0]), int(m[1]), int(m[2]), int(m[3]))),
    ]
    
    for pattern, parser in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                return parser(match.groups())
            except:
                continue
    return None


def clean_text(text, max_length=2000):
    """텍스트 정리"""
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', str(text)).strip()
    if len(text) > max_length:
        text = text[:max_length] + '...'
    return text


def normalize_url(raw_link, base_url):
    """상대 URL → 절대 URL"""
    if not raw_link:
        return ''
    raw_link = str(raw_link)
    if raw_link.startswith('http'):
        return raw_link
    return base_url.rstrip('/') + '/' + raw_link.lstrip('/')


def parallel_fetch_details(article_list, detail_parser, max_workers=10, site_name=''):
    """병렬 본문 수집"""
    if not article_list:
        return []
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_article = {
            executor.submit(detail_parser, art['url']): art
            for art in article_list
        }
        
        for i, future in enumerate(as_completed(future_to_article), 1):
            art = future_to_article[future]
            try:
                detail = future.result()
                merged = {**art, **detail}
                results.append(merged)
                
                if i % 25 == 0 and site_name:
                    print(f"[{site_name}] 진행: {i}/{len(article_list)}")
            except Exception as e:
                print(f"[{site_name}] {art.get('url', '')[:60]} 실패: {e}")
                results.append({**art, 'content': ''})
    
    return results
