"""
News Collector - Scrapling 기반
RSS-first + selector fallback 크롤러

병렬 처리 지원:
- SITE 환경변수로 단일 사이트만 실행 가능
- 예: SITE=AITIMES python news_collector.py

Selenium 의존성 제거, GitHub Actions matrix 병렬 실행 지원
"""

import pandas as pd
import os
import sys
from datetime import datetime

# utf-8
sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# Scrapling 마이그레이션된 크롤러
# ============================================================
import aitimes_crawler
import techworld_crawler
import businesspost_crawler
import samsung_crawler
import electrolux_crawler
import cheaa_crawler
import zdwang_crawler
import irobotnews_crawler
import oceanpress_crawler
import shippingnewsnet_crawler
import google_news_crawler
import impacton_crawler
import greenpost_crawler
import prnewswire_crawler
import naver_news_crawler

# ============================================================
# 설정
# ============================================================
DATE_THRESHOLD = int(os.getenv('DATE_THRESHOLD', '1'))
MAX_ITEMS_PER_CRAWLER = int(os.getenv('MAX_ITEMS_PER_CRAWLER', '100'))

COLUMNS = [
    'title', 'content', 'enveloped_at', 'date', 'provider',
    'category_main', 'category_sub', 'reporter', 'provider_link_page',
    'useful', 'strategy_agenda', 'content_summary', 'category1', 'category2',
    'YEAR', 'MONTH', 'WEEK'
]

# ============================================================
# 병렬 처리: SITE 환경변수
# ============================================================
TARGET_SITE = os.getenv('SITE', '').upper().strip()

print(f"\n🚀 Scrapling 기반 뉴스 수집 시작 (최근 {DATE_THRESHOLD}일치)")
print(f"📦 RSS-first + selector fallback 전체 크롤러")

if TARGET_SITE:
    print(f"🎯 단일 사이트 모드: {TARGET_SITE}")
else:
    print(f"📋 전체 사이트 모드")

# ============================================================
# 출력 디렉토리
# ============================================================
try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    base_dir = os.getcwd()

db_dir = os.path.join(base_dir, 'output')
os.makedirs(db_dir, exist_ok=True)

history_file = os.path.join(db_dir, '.crawled_history.txt')
global_seen_links = set()
if os.path.exists(history_file):
    with open(history_file, 'r', encoding='utf-8') as f:
        for line in f:
            link = line.strip()
            if link:
                global_seen_links.add(link)

print(f"📖 수집 기록: {len(global_seen_links)}개 기사 건너뛰기")

# ============================================================
# 크롤러 등록
# ============================================================
ALL_CRAWLER_TASKS = [
    {"name": "AITIMES", "func": aitimes_crawler.get_aitimes_data},
    {"name": "TECHWORLD", "func": techworld_crawler.get_techworld_data},
    {"name": "BUSINESSPOST", "func": businesspost_crawler.get_businesspost_data},
    {"name": "SAMSUNG", "func": samsung_crawler.get_samsung_data},
    {"name": "ELECTROLUX", "func": electrolux_crawler.get_electrolux_data},
    {"name": "CHEAA", "func": cheaa_crawler.get_cheaa_data},
    {"name": "ZDWANG", "func": zdwang_crawler.get_zdwang_data},
    {"name": "IROBOTNEWS", "func": irobotnews_crawler.get_irobotnews_data},
    {"name": "OCEANPRESS", "func": oceanpress_crawler.get_oceanpress_data},
    {"name": "SHIPPINGNEWSNET", "func": shippingnewsnet_crawler.get_shippingnewsnet_data},
    {"name": "IMPACTON", "func": impacton_crawler.get_impacton_data},
    {"name": "GREENPOST", "func": greenpost_crawler.get_greenpost_data},
    {"name": "PRNEWSWIRE", "func": prnewswire_crawler.get_prnewswire_data},
    {"name": "NAVER_NEWS", "func": naver_news_crawler.get_naver_news_data},
    {"name": "GOOGLE_NEWS", "func": google_news_crawler.get_google_news_data},
]

# 단일 사이트 모드 처리
if TARGET_SITE:
    crawler_tasks = [t for t in ALL_CRAWLER_TASKS if t['name'] == TARGET_SITE]
    if not crawler_tasks:
        print(f"❌ 등록되지 않은 사이트: {TARGET_SITE}")
        print(f"   사용 가능: {[t['name'] for t in ALL_CRAWLER_TASKS]}")
        sys.exit(1)
else:
    crawler_tasks = ALL_CRAWLER_TASKS


# ============================================================
# 크롤러 실행
# ============================================================
def execute_crawler(task):
    try:
        limit_str = f" (최대 {MAX_ITEMS_PER_CRAWLER}개)" if MAX_ITEMS_PER_CRAWLER else ""
        print(f"\n--- {task['name']} 수집 중{limit_str} ---")
        start_time = datetime.now()
        
        # Scrapling은 driver 불필요 → None 전달
        data = task['func'](None, DATE_THRESHOLD, MAX_ITEMS_PER_CRAWLER, global_seen_links)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if data:
            print(f"✅ {task['name']}: {len(data)}건 수집 완료 ({elapsed:.1f}초)")
            return data
        else:
            print(f"⚠️ {task['name']}: 수집된 데이터 없음 ({elapsed:.1f}초)")
            return []
    except Exception as e:
        print(f"❌ {task['name']} 수집 실패: {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================================
# 실행
# ============================================================
all_data = []
total_start = datetime.now()

for task in crawler_tasks:
    try:
        result_data = execute_crawler(task)
        all_data.extend(result_data)
    except Exception as e:
        print(f"⚠️ {task['name']} 예외: {e}")

total_elapsed = (datetime.now() - total_start).total_seconds()
print(f"\n⏱️ 전체 수집 시간: {total_elapsed:.1f}초")

# ============================================================
# 빈 결과 처리
# ============================================================
if not all_data:
    print("최종 수집된 데이터가 없습니다.")
    if TARGET_SITE:
        empty_df = pd.DataFrame(columns=COLUMNS)
        today_str = datetime.now().strftime('%y%m%d_%H%M%S')
        save_path = os.path.join(db_dir, f"{today_str}_{TARGET_SITE}_empty.csv")
        empty_df.to_csv(save_path, encoding='utf-8-sig', index=False)
        print(f"📁 빈 결과 파일 생성: {save_path}")
    sys.exit(0)

# ============================================================
# 데이터프레임 후처리
# ============================================================
df_result = pd.DataFrame(all_data)

# 누락 컬럼 채우기
for col in COLUMNS:
    if col not in df_result.columns:
        df_result[col] = ""

df_result = df_result[COLUMNS]

# 중복 제거
if not df_result.empty:
    import re
    def normalize_title(text):
        if pd.isna(text): return ""
        return re.sub(r'\s+', '', str(text)).lower()
    
    df_result['norm_title'] = df_result['title'].apply(normalize_title)
    initial_len = len(df_result)
    df_result = df_result.drop_duplicates(subset=['norm_title'], keep='first')
    df_result = df_result.drop(columns=['norm_title'])
    removed_count = initial_len - len(df_result)
    if removed_count > 0:
        print(f"🧹 중복 기사 {removed_count}건 제거")

# 정렬
df_result = df_result.sort_values(by=['date', 'enveloped_at'], ascending=False).reset_index(drop=True)

# ============================================================
# 저장
# ============================================================
today_str = datetime.now().strftime('%y%m%d_%H%M%S')

if TARGET_SITE:
    save_path = os.path.join(db_dir, f"{today_str}_{TARGET_SITE}.csv")
else:
    save_path = os.path.join(db_dir, f"{today_str}_competitor.csv")

df_result.to_csv(save_path, encoding='utf-8-sig', index=False)
print(f"📁 결과 저장: {save_path}")

# 히스토리 업데이트
if not df_result.empty:
    with open(history_file, 'a', encoding='utf-8') as f:
        for link in df_result['provider_link_page'].unique():
            if link and link not in global_seen_links:
                f.write(f"{link}\n")

print(f"\n✨ 작업 완료: 총 {len(df_result)}건")
