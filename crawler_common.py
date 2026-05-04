"""
공통 헬퍼 - Scrapling 0.4.7 정확한 API

핵심 변경 (0.4+ 기준):
- css_first 제거 → css(...).first 또는 css(...)[0] 사용
- 텍스트: css('::text').get() 또는 .text 속성
- 속성: css('::attr(href)').get() 또는 .attrib.get('href', '')
- Selectors.first 속성: 안전 (None 반환)
"""

from datetime import datetime, timedelta
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# Scrapling 0.4+ 호환 헬퍼 함수들
# ============================================================

def first_element(parent, selector):
    """
    부모 요소에서 셀렉터 매치 첫 번째 Selector 반환
    Scrapling 0.4+ API 사용
    """
    if parent is None:
        return None
    try:
        results = parent.css(selector)
        if not results or len(results) == 0:
            return None
        # 0.4+: Selectors.first 속성 (안전)
        if hasattr(results, 'first'):
            return results.first
        # fallback: [0] 인덱싱
        return results[0]
    except Exception:
        return None


def get_text(element, default=''):
    """
    Selector에서 텍스트 추출 (0.4+)
    
    여러 방법 시도:
    1. .text 속성
    2. css('::text').get()
    """
    if element is None:
        return default
    
    # 방법 1: .text 속성 (가장 간단)
    try:
        text = element.text
        if text is not None:
            return str(text).strip()
    except (AttributeError, TypeError):
        pass
    
    # 방법 2: css('::text').get()
    try:
        text_handler = element.css('::text')
        if text_handler:
            result = text_handler.get() if hasattr(text_handler, 'get') else None
            if result:
                return str(result).strip()
    except Exception:
        pass
    
    return default


def get_attr(element, attr_name, default=''):
    """
    Selector에서 속성값 추출 (0.4+)
    
    1. .attrib['name'] 직접 접근 (빠름)
    2. css('::attr(name)').get()
    """
    if element is None:
        return default
    
    # 방법 1: .attrib (가장 빠름)
    try:
        if hasattr(element, 'attrib'):
            return str(element.attrib.get(attr_name, default))
    except (AttributeError, TypeError):
        pass
    
    # 방법 2: css('::attr(...)').get()
    try:
        attr_handler = element.css(f'::attr({attr_name})')
        if attr_handler:
            result = attr_handler.get() if hasattr(attr_handler, 'get') else None
            if result:
                return str(result)
    except Exception:
        pass
    
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
