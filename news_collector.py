import pandas as pd
import os
import sys
import io
from datetime import datetime
import concurrent.futures

# utf-8 for console output robustness
sys.stdout.reconfigure(encoding='utf-8')

import zdwang_crawler
import cheaa_crawler
import samsung_crawler
import techworld_crawler
import irobotnews_crawler
import google_news_crawler
import aitimes_crawler

# oo일전 뉴스부터 수집
DATE_THRESHOLD = 1

# 크롤러별 최대 수집 개수 (0 또는 None 시 제한 없음)
MAX_ITEMS_PER_CRAWLER = 100

# 1. 설정값 상수화
COLUMNS = [
    'title', 'content', 'enveloped_at', 'date', 'provider',
    'category_main', 'category_sub', 'reporter', 'provider_link_page',
    'useful', 'strategy_agenda', 'content_summary', 'category1', 'category2',
    'YEAR', 'MONTH', 'WEEK'
]

print(f"\n🚀 최근 {DATE_THRESHOLD}일치 데이터 수집을 시작합니다...")


try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # __file__ 이 없는 환경 (Jupyter, IPython 등)
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
print(f"📖 수집 기록 로깅 완료: 이전에 수집된 {len(global_seen_links)}개의 기사를 건너뜁니다.")

import businesspost_crawler

# 2. 크롤러 등록 (작업 리스트화)
# 각 크롤러의 인스턴스나 실행 함수를 리스트에 담아 관리합니다.
# 만약 앞서 리팩토링한 것처럼 클래스 형태라면 인스턴스를 생성합니다.
crawler_tasks = [
    {"name": "ZDWANG", "func": zdwang_crawler.get_zdwang_data},
    {"name": "CHEAA", "func": cheaa_crawler.get_cheaa_data},
    {"name": "SAMSUNG", "func": samsung_crawler.SamsungCrawler().run},
    {"name": "TECHWORLD", "func": techworld_crawler.scrape_techworld_news},
    {"name": "IROBOTNEWS", "func": irobotnews_crawler.get_irobotnews_data},
    {"name": "BUSINESSPOST", "func": businesspost_crawler.get_businesspost_data},
    {"name": "GOOGLE_NEWS", "func": google_news_crawler.get_google_news_data},
    {"name": "AITIMES", "func": aitimes_crawler.get_aitimes_data}
]

all_data = []

# 3. 비동기/멀티스레딩을 통한 자동화 수집
def execute_crawler(task):
    try:
        limit_str = f" (최대 {MAX_ITEMS_PER_CRAWLER}개)" if MAX_ITEMS_PER_CRAWLER else " (제한 없음)"
        print(f"--- {task['name']} 수집 중{limit_str} ---")
        
        # DATE_THRESHOLD, MAX_ITEMS_PER_CRAWLER, global_seen_links 전달
        data = task['func'](DATE_THRESHOLD, MAX_ITEMS_PER_CRAWLER, global_seen_links)
        
        if data:
            print(f"✅ {task['name']}: {len(data)}건 수집 완료")
            return data
        else:
            print(f"⚠️ {task['name']}: 수집된 데이터 없음")
            return []
    except Exception as e:
        print(f"❌ {task['name']} 수집 실패: {e}")
        return []

executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(crawler_tasks))
# 각 크롤러 태스크를 비동기로 실행
futures = [executor.submit(execute_crawler, task) for task in crawler_tasks]

try:
    for future in concurrent.futures.as_completed(futures, timeout=180):
        try:
            all_data.extend(future.result())
        except Exception as e:
            print(f"⚠️ 크롤러 실행 중 스레드 예외 발생: {e}")
except concurrent.futures.TimeoutError:
    print("⚠️ 전체 수집 제한시간(3분)을 초과하여 완료되지 않은 크롤러를 강제 중단합니다.")

# 완료되지 않은 스레드가 메인 스레드를 막지 못하도록 바로 종료 옵션 설정
executor.shutdown(wait=False, cancel_futures=True)

if not all_data:
    print("최종 수집된 데이터가 없습니다.")

# 4. 데이터프레임 생성 및 통합 후처리
df_result = pd.DataFrame(all_data)

# 존재하지 않는 컬럼 빈 값으로 생성
for col in COLUMNS:
    if col not in df_result.columns:
        df_result[col] = ""

# 컬럼 순서 고정
df_result = df_result[COLUMNS]

# 4.5 통합 텍스트 기준 중복 제거 (다른 언론사에 배포된 동일 뉴스 차단)
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
        print(f"🧹 제목이 유사한 중복 기사 {removed_count}건을 제거했습니다.")

# 날짜 기준 정렬
df_result = df_result.sort_values(by=['date', 'enveloped_at'], ascending=False).reset_index(drop=True)

# 5. 절대 경로를 사용한 안전한 파일 저장
today_str = datetime.now().strftime('%y%m%d_%H%M%S')
save_path = os.path.join(db_dir, f"{today_str}_competitor.csv")
df_result.to_csv(save_path, encoding='utf-8-sig', index=False)
print(f"📁 결과 저장 완료: {save_path}")

# 수집 기록 업데이트
if not df_result.empty:
    with open(history_file, 'a', encoding='utf-8') as f:
        for link in df_result['provider_link_page'].unique():
            if link and link not in global_seen_links:
                f.write(f"{link}\n")
    print(f"📝 새로운 수집 기록이 히스토리에 업데이트되었습니다.")

# 기존 크롤링 자료와 통합 파트는 현재 db_crawling이 정의되어 있지 않으므로 주석 처리
# if not df_result.empty:
#     df_crawling = pd.concat([df_crawling, df_result], axis=0, ignore_index=True)