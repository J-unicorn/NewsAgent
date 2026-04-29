import time
import re
from datetime import datetime, timedelta
import sys
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

def get_businesspost_data(driver, days_to_scrape=1, max_items=None, global_seen_links=None):
    if max_items is not None and max_items <= 0:
        max_items = None
        
    cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
    results = []
    seen_links = set(global_seen_links) if global_seen_links else set()
    base_url = "https://www.businesspost.co.kr"
    
    page = 1
    keep_going_section = True
    
    while keep_going_section:
        list_url = f"https://www.businesspost.co.kr/BP?command=sub&sub=8&page={page}"
        try:
            driver.get(list_url)
            time.sleep(2)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            items = driver.find_elements(By.CSS_SELECTOR, "div.left_post")
            if not items:
                break
                
            links_to_fetch = []
            
            for item in items:
                try:
                    a_tag = item.find_element(By.CSS_SELECTOR, "a")
                    raw_link = a_tag.get_attribute("href")
                    if not raw_link: continue
                    link = raw_link if raw_link.startswith('http') else base_url.rstrip('/') + '/' + raw_link.lstrip('/')
                    
                    title_tag = item.find_element(By.CSS_SELECTOR, "h3")
                    title = title_tag.text.strip()
                    if not title: continue
                    
                    links_to_fetch.append({
                        "title": title,
                        "link": link
                    })
                except Exception as e:
                    pass
            
            found_in_range = False
            
            for item in links_to_fetch:
                if max_items is not None and len(results) >= max_items:
                    keep_going_section = False
                    break
                
                if item["link"] in seen_links: continue
                seen_links.add(item["link"])
                
                content = ""
                cat_main, cat_sub = "분류", "뉴스"
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
                        category_span = driver.find_element(By.CSS_SELECTOR, "span.category")
                        cat_parts = category_span.text.strip().split()
                        if len(cat_parts) >= 1: cat_main = cat_parts[0]
                        if len(cat_parts) >= 2: cat_sub = cat_parts[1]
                    except: pass
                    
                    try:
                        author_info = driver.find_element(By.CSS_SELECTOR, "div.author_info")
                        date_text = author_info.text.strip()
                        date_match = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)', date_text)
                        if date_match:
                            ext_date = date_match.group(1).replace('.', '-').replace('/', '-')
                            ext_time = date_match.group(2)
                            if len(ext_time) == 5: ext_time += ":00"
                            full_date_time = f"{ext_date} {ext_time}"
                            try:
                                date_obj = datetime.strptime(full_date_time, '%Y-%m-%d %H:%M:%S')
                            except: pass
                    except: pass
                    
                    if not date_obj:
                        continue
                        
                    if date_obj.date() < cutoff_date:
                        continue
                        
                    found_in_range = True
                    
                    try:
                        content_area = driver.find_element(By.CSS_SELECTOR, "div.detail_editor")
                        content = content_area.text.strip()
                    except: pass
                except Exception as det_e:
                    print(f"  ❌ 상세 본문 오류 ({item['link']}): {det_e}")
                    
                if not date_obj or date_obj.date() < cutoff_date:
                    continue
                    
                print(f"  [BUSINESSPOST] 수집: {full_date_time} | {item['title'][:20]}...")
                
                results.append({
                    'title': item['title'],
                    'content': content,
                    'content_summary': content[:200].replace('\n', ' ') if content else "",
                    'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'date': str(full_date_time),
                    'provider': 'businesspost',
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
            
        except Exception as list_e:
            print(f"❌ 페이지 목록 오류: {list_e}")
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
    
    parser = argparse.ArgumentParser(description="Run BusinessPost crawler independently.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to scrape (DATE_THRESHOLD)")
    args = parser.parse_args()

    print(f"비즈니스포스트 크롤링을 시작합니다. (과거 {args.days}일)")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        data = get_businesspost_data(driver, days_to_scrape=args.days)
        if data:
            os.makedirs("output", exist_ok=True)
            today_str = datetime.now().strftime('%Y%m%d')
            filename = f"output/{today_str}_businesspost.csv"
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
