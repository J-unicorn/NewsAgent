"""
공통 크롤러 헬퍼 - Scrapling 기반
모든 사이트 크롤러가 공유하는 함수들
"""

from scrapling.fetchers import Fetcher
from datetime import datetime, timedelta
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


def parse_date_flexible(date_str, current_year=None):
    """다양한 날짜 형식 파싱"""
    if not date_str:
        return None
    
    if current_year is None:
        current_year = datetime.now().year
    
    date_str = date_str.strip()
    
    patterns = [
        # 2026-05-04 12:30:45
        (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))),
        # 2026-05-04 12:30
        (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]))),
        # 2026.05.04
        (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]))),
        # 05.04 12:30 (연도 생략)
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


def safe_fetch(url, timeout=10, max_retries=2):
    """재시도 로직이 있는 안전한 fetch"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return Fetcher.get(url, stealthy_headers=True, timeout=timeout)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                continue
    raise last_error


def parallel_fetch_details(article_list, detail_parser, max_workers=10, site_name=''):
    """
    기사 본문을 병렬로 가져오기
    
    Args:
        article_list: [{'url': ..., 'title': ..., ...}, ...]
        detail_parser: URL을 받아 dict 반환하는 함수
        max_workers: 동시 실행 수
        site_name: 로그용
    
    Returns:
        병합된 결과 리스트
    """
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
                # 기본 정보 + 상세 정보 병합 (detail이 우선)
                merged = {**art, **detail}
                results.append(merged)
                
                if i % 25 == 0 and site_name:
                    print(f"[{site_name}] 진행: {i}/{len(article_list)}")
            except Exception as e:
                print(f"[{site_name}] {art.get('url', '')[:60]} 실패: {e}")
                # 실패해도 기본 정보는 보존
                results.append({**art, 'content': ''})
    
    return results


def clean_text(text, max_length=2000):
    """텍스트 정리: 공백 정규화, 길이 제한"""
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_length:
        text = text[:max_length] + '...'
    return text


def normalize_url(raw_link, base_url):
    """상대 URL을 절대 URL로 변환"""
    if not raw_link:
        return ''
    if raw_link.startswith('http'):
        return raw_link
    return base_url.rstrip('/') + '/' + raw_link.lstrip('/')
