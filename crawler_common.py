"""
공통 크롤러 헬퍼 - Scrapling 0.4.x 호환

주요 변경:
- css_first → css(selector)[0] 또는 first() 헬퍼 함수
- StealthyFetcher 지원 추가
"""

from scrapling.fetchers import Fetcher, StealthyFetcher
from datetime import datetime, timedelta
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


def css_first(element, selector):
    """
    CSS 셀렉터로 첫 번째 요소 가져오기 (안전)
    Selector 또는 Selectors 객체 모두 지원
    """
    try:
        results = element.css(selector)
        if results and len(results) > 0:
            return results[0]
        return None
    except Exception:
        return None


def get_text(element, default=''):
    """요소에서 텍스트 추출 (안전)"""
    if element is None:
        return default
    try:
        if hasattr(element, 'text'):
            text = element.text
            if hasattr(text, 'strip'):
                return text.strip()
            return str(text).strip() if text else default
        return default
    except Exception:
        return default


def get_attr(element, attr_name, default=''):
    """요소에서 속성값 추출 (안전)"""
    if element is None:
        return default
    try:
        if hasattr(element, 'attrib'):
            return element.attrib.get(attr_name, default)
        return default
    except Exception:
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


def safe_fetch(url, timeout=10, max_retries=2, use_stealth=False):
    """
    재시도 로직이 있는 안전한 fetch
    use_stealth=True면 StealthyFetcher (느림, Cloudflare 우회)
    """
    last_error = None
    fetcher = StealthyFetcher if use_stealth else Fetcher
    
    for attempt in range(max_retries):
        try:
            if use_stealth:
                # StealthyFetcher는 다른 옵션
                return fetcher.fetch(url, headless=True, network_idle=True)
            else:
                return fetcher.get(url, stealthy_headers=True, timeout=timeout)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                continue
    raise last_error


def parallel_fetch_details(article_list, detail_parser, max_workers=10, site_name=''):
    """기사 본문 병렬 수집"""
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


def clean_text(text, max_length=2000):
    """텍스트 정리"""
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', str(text)).strip()
    if len(text) > max_length:
        text = text[:max_length] + '...'
    return text


def normalize_url(raw_link, base_url):
    """상대 URL을 절대 URL로"""
    if not raw_link:
        return ''
    raw_link = str(raw_link)
    if raw_link.startswith('http'):
        return raw_link
    return base_url.rstrip('/') + '/' + raw_link.lstrip('/')
