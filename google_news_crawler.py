import requests
import feedparser
import time
import datetime
import sys
from deep_translator import GoogleTranslator
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

def translate_text(text, max_retries=3):
    if not text: return ""
    text_to_translate = text[:4500]
    chunk_size = 1500
    chunks = [text_to_translate[i:i+chunk_size] for i in range(0, len(text_to_translate), chunk_size)]
    
    translated_chunks = []
    for chunk in chunks:
        chunk_translated = chunk
        for attempt in range(max_retries):
            try:
                res = GoogleTranslator(source='auto', target='ko').translate(chunk)
                if res:
                    chunk_translated = res
                    break
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"  [번역 실패] {e}")
                time.sleep(1.5 * (attempt + 1))
        translated_chunks.append(chunk_translated)
        time.sleep(0.5)
        
    return " ".join(translated_chunks)

def get_article_content(driver, url):
    """
    Selenium을 사용하여 구글 뉴스 리다이렉트를 처리하고 본문을 추출합니다.
    """
    try:
        try:
            driver.get(url)
        except TimeoutException:
            pass # 페이지 로드가 지연되더라도 이미 렌더링된 본문 텍스트는 추출 시도
            
        time.sleep(3) # 리다이렉트 대기
        
        content = driver.execute_script("return document.body ? document.body.innerText : '';")
        if content:
            content = " ".join(content.split())
            content_summary = content[:200]
            return content, content_summary
        return "", ""
    except Exception as e:
        print(f"  [GoogleNews] Detail Parsing Error: {e}")
        return "", ""

def get_google_news_data(driver, days_to_scrape=1, max_items=None, global_seen_links=None):
    if max_items is not None and max_items <= 0:
        max_items = None
        
    TARGET_GROUPS = [
        {
            "name": "China Competitors",
            "targets": ["海尔", "美的", "海信集團"],
            "url_template": 'https://news.google.com/rss/search?q="{query}"%20when%3A{period}-ETF%2C%20-专利&hl=zh-CN&gl=CN&ceid=CN%3Azh-Hans'
        },
        {
            "name": "Global Competitors",
            "targets": ["Electrolux", "GE Appliance", "Whirlpool", "Bosch Appliance"],
            "url_template": 'https://news.google.com/rss/search?q="{query}"%20when%3A{period}&hl=en-US&gl=US&ceid=US%3Aen'
        },
        {
            "name": "Logistics Keywords",
            "targets": ["수에즈 운하", "파나마 운하", "홍해", "SCFI"],
            "url_template": 'https://news.google.com/rss/search?q="{query}"%20when%3A{period}&hl=ko&gl=KR&ceid=KR%3Ako'
        }
    ]

    search_period = f"{days_to_scrape}d"
    results = []
    seen_links = set(global_seen_links) if global_seen_links else set()

    print(">>> 구글 뉴스 크롤링 시작")
    print(f"※ 최근 {search_period} 뉴스를 검색합니다.")

    try:
        for group in TARGET_GROUPS:
            if max_items is not None and len(results) >= max_items:
                break
                
            print(f"\n--- Group: {group['name']} ---")
            for target in group['targets']:
                if max_items is not None and len(results) >= max_items:
                    break
                    
                target_url = group['url_template'].format(query=target, period=search_period)
                print(f"Searching: {target}")
                
                remaining = None
                if max_items is not None:
                    remaining = max_items - len(results)
                group_results = crawl_google_rss_url(driver, target_url, target, max_retries=3, seen_links=seen_links, max_items=remaining)
                results.extend(group_results)
                
                if group_results:
                    print(f"  -> {len(group_results)}건 수집 완료")
                else:
                    print("  -> 수집된 뉴스 없음")
    finally:
        pass

    print("\n>>> 모든 구글 뉴스 크롤링 완료")
    return results

def crawl_google_rss_url(driver, news_url, competitor, max_retries=3, seen_links=None, max_items=None):
    if seen_links is None: seen_links = set()
    retries = 0
    while retries < max_retries:
        try:
            res = requests.get(news_url, timeout=(5, 10))
            if res.status_code == 200:
                print(f"  [GoogleNews] RSS XML fetching successful. Parsing...")
                datas = feedparser.parse(res.text).entries
                print(f"  [GoogleNews] {len(datas)} entries found in RSS.")
                # max_items 제한 고려 (남은 개수만큼만)
                remaining = None
                if 'max_items' in globals() or 'max_items' in locals(): # 이 시점에서는 전달받은 max_items 사용
                    pass # 루프 내에서 처리됨
                
                print(f"  [GoogleNews] Starting to parse {len(datas)} items...")
                parsed_data = parse_rss_entries(driver, competitor, datas, seen_links, max_items)
                
                # 수집 직후 필터링은 parse_rss_entries 내부 혹은 이후 수행 가능하나 
                # 여기서는 전체를 받은 후 반환 시점의 개수를 상위 루프가 제어함
                time.sleep(abs(np.random.randn() * 2)) 
                return parsed_data
            else:
                print(f"  [Error] Status Code: {res.status_code}")
                if 400 <= res.status_code < 500:
                    break
        except requests.exceptions.Timeout:
            print(f"  [Timeout] 요청 시간 초과 (시도 {retries+1}/{max_retries})")
        except requests.exceptions.RequestException as err:
            print(f"  [Connection Error] {err} (시도 {retries+1}/{max_retries})")
        except Exception as e:
            print(f"  [Unknown Error] {e}")

        retries += 1
        wait_time = 2 ** retries
        time.sleep(wait_time)
        print(f"  Retrying in {wait_time} seconds...")

    print(f"  [Fail] '{competitor}' 크롤링 최종 실패")
    return []

def parse_rss_entries(driver, competitor, datas, seen_links, max_items=None):
    enveloped_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    parsed_results = []

    for data in datas:
        if max_items is not None and len(parsed_results) >= max_items:
            break
            
        try:
            # RSS 항목 파싱
            title = translate_text(data.title)
            provider = data.source.title if hasattr(data, 'source') and hasattr(data.source, 'title') else "Google News"
            
            provider_link_page = data.link
            provider_link_page = provider_link_page.replace("/rss/", "/")
            
            if provider_link_page in seen_links: continue
            seen_links.add(provider_link_page)
            
            try:
                datetime_object = datetime.datetime.strptime(data.published, "%a, %d %b %Y %H:%M:%S %Z")
            except:
                datetime_object = datetime.datetime.now()
            
            year = str(datetime_object.year)
            month = str(datetime_object.month)
            week = str(datetime_object.isocalendar()[1])
            date_str = datetime_object.strftime('%Y-%m-%d %H:%M:%S')

            # 본문 추출
            content, content_summary = get_article_content(driver, provider_link_page)
            if not content:
                content = data.title # 본문이 없으면 제목으로 대체
            
            # 번역 수행
            translated_content = translate_text(content)
            translated_summary = translate_text(content_summary)
                
            print(f"  [GoogleNews] 수집: {date_str} | {title[:30]}...")
            print(f"  --> 요약: {translated_summary[:50]}")

            # 결과 리스트에 딕셔너리 추가 (기존 프로젝트 포맷 맞춤)
            parsed_results.append({
                'title': title,
                'content': translated_content,
                'enveloped_at': enveloped_at,
                'date': date_str,
                'provider': provider,
                'category_main': '',
                'category_sub': '',
                'reporter': '',
                'provider_link_page': provider_link_page,
                'useful': -1,
                'strategy_agenda': -1,
                'content_summary': translated_summary,
                'category1': competitor,
                'category2': '',
                'YEAR': year,
                'MONTH': month,
                'WEEK': week
            })
        except Exception as e:
            print(f"  [RSS Parse Error] {e}")
            
    return parsed_results

if __name__ == "__main__":
    import argparse
    import csv
    import os
    parser = argparse.ArgumentParser(description="Run Google News crawler independently.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to scrape (DATE_THRESHOLD)")
    args = parser.parse_args()
    
    print(f"구글 뉴스 크롤링을 시작합니다. (과거 {args.days}일)")
    
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    
    try:
        data = get_google_news_data(driver, days_to_scrape=args.days, max_items=5)
        
        if data:
            os.makedirs("output", exist_ok=True)
            today_str = datetime.now().strftime('%Y%m%d')
            filename = f"output/{today_str}_googlenews.csv"
            keys = data[0].keys()
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(data)
            print(f"✅ 수집 완료: 총 {len(data)}건 -> {filename}")
        else:
            print("수집된 기사가 없습니다.")
    finally:
        driver.quit()
