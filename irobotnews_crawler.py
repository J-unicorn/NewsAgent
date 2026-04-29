import time
import re
from datetime import datetime, timedelta
import sys
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

def get_irobotnews_data(driver, days_to_scrape=1, max_items=None, global_seen_links=None):
    if max_items is not None and max_items <= 0:
        max_items = None
        
    cutoff_date = datetime.now() - timedelta(days=days_to_scrape)
    results = []
    seen_links = set(global_seen_links) if global_seen_links else set()
    base_url = "https://www.irobotnews.com"
    
    page = 1
    keep_going_section = True
    
    while keep_going_section:
        if max_items is not None and len(results) >= max_items:
            break
            
        list_url = f"{base_url}/news/articleList.html?page={page}&view_type=sm"
        
        try:
            driver.get(list_url)
            time.sleep(2)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            items = driver.find_elements(By.CSS_SELECTOR, "ul.altlist-webzine > li.altlist-webzine-item")
            links_to_fetch = []
            
            for item in items:
                try:
                    if item.get_attribute("id") == "sample":
                        continue
                        
                    a_tag = item.find_element(By.CSS_SELECTOR, "h2.altlist-subject a")
                    title = a_tag.text.strip()
                    raw_link = a_tag.get_attribute("href")
                    if not raw_link: continue
                    link = raw_link if raw_link.startswith('http') else f"{base_url}{raw_link if raw_link.startswith('/') else '/' + raw_link}"
                    
                    links_to_fetch.append({
                        "title": title,
                        "link": link
                    })
                except Exception as e:
                    pass
                    
            if not links_to_fetch:
                break
                
            found_in_range = False
            
            for item in links_to_fetch:
                if max_items is not None and len(results) >= max_items:
                    keep_going_section = False
                    break
                    
                if item["link"] in seen_links: continue
                seen_links.add(item["link"])
                
                content = ""
                cat_main, cat_sub = "홈", "최신뉴스"
                full_date_time = ""
                date_obj = None
                
                try:
                    driver.get(item["link"])
                    time.sleep(1.5)
                    
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(0.5)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    
                    try:
                        info_area = driver.find_element(By.CSS_SELECTOR, "ul.infomation")
                        info_text = info_area.text.strip()
                        date_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)', info_text)
                        
                        if date_match:
                            y, m, d, hm = date_match.groups()
                            if len(hm) == 5: hm += ":00"
                            full_date_time = f"{y}-{m}-{d} {hm}"
                            date_obj = datetime.strptime(full_date_time, '%Y-%m-%d %H:%M:%S')
                    except: pass
                    
                    if not date_obj:
                        continue
                        
                    if date_obj.date() < cutoff_date.date():
                        continue
                        
                    found_in_range = True
                    
                    try:
                        title_text = driver.title
                        parts = [p.strip() for p in title_text.split('<')]
                        if len(parts) >= 3:
                            cat_sub = parts[1]
                            cat_main = parts[2]
                    except: pass
                    
                    try:
                        content_area = driver.find_element(By.CSS_SELECTOR, "article#article-view-content-div")
                        content = content_area.text.strip()
                    except: pass
                except Exception as det_e:
                    print(f"상세 페이지 오류 ({item['link']}): {det_e}")
                    
                if not date_obj or date_obj.date() < cutoff_date.date():
                    continue
                    
                content_summary = content[:200].replace('\n', ' ') if content else ""
                print(f"수집 완료: {full_date_time} | {item['title'][:30]}...")
                
                results.append({
                    'title': item['title'],
                    'content': content,
                    'content_summary': content_summary,
                    'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'date': str(full_date_time),
                    'provider': '로봇신문',
                    'category_main': cat_main,
                    'category_sub': cat_sub,
                    'provider_link_page': item['link'],
                    'useful': 1,
                    'strategy_agenda': 1,
                    'YEAR': date_obj.year,
                    'MONTH': date_obj.month,
                    'WEEK': date_obj.isocalendar()[1]
                })
                time.sleep(1)
                
            if not found_in_range:
                keep_going_section = False
            page += 1
            
        except Exception as e:
            print(f"목록 페이지 통신 오류: {e}")
            break
            
    return results

if __name__ == "__main__":
    import argparse
    import csv
    import os
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    
    parser = argparse.ArgumentParser(description="Run iRobotNews crawler independently.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to scrape (DATE_THRESHOLD)")
    args = parser.parse_args()

    print(f"로봇신문 크롤링을 시작합니다. (과거 {args.days}일)")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        scraped_data = get_irobotnews_data(driver, days_to_scrape=args.days)
        if scraped_data:
            os.makedirs("output", exist_ok=True)
            today_str = datetime.now().strftime('%Y%m%d')
            file_name = f"output/{today_str}_irobotnews.csv"
            keys = scraped_data[0].keys()
            
            with open(file_name, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(scraped_data)
                
            print(f"\n✅ 수집 완료: 총 {len(scraped_data)}건의 기사가 '{file_name}'로 저장되었습니다.")
        else:
            print("\n[안내] 수집된 데이터가 없습니다.")
    finally:
        driver.quit()