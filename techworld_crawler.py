import time
import re
from datetime import datetime, timedelta
import sys
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

def scrape_techworld_news(driver, days_to_scrape=1, max_items=None, global_seen_links=None):
    if max_items is not None and max_items <= 0:
        max_items = None
        
    cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
    results = []
    seen_links = set(global_seen_links) if global_seen_links else set()
    base_url = "https://www.epnc.co.kr"
    
    page = 1
    keep_going_section = True
    
    while keep_going_section:
        if max_items is not None and len(results) >= max_items:
            break
            
        list_url = f"{base_url}/news/articleList.html?page={page}"
        try:
            driver.get(list_url)
            time.sleep(2)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            items = driver.find_elements(By.CSS_SELECTOR, "li")
            links_to_fetch = []
            
            for item in items:
                try:
                    item_id = item.get_attribute("id")
                    item_class = item.get_attribute("class") or ""
                    if item_id == 'sample' or 'blind' in item_class:
                        continue
                        
                    a_tags = item.find_elements(By.CSS_SELECTOR, "h2.titles a")
                    if not a_tags: continue
                    a_tag = a_tags[0]
                    
                    try:
                        date_elem = item.find_element(By.CSS_SELECTOR, "em.info.dated")
                        date_text = date_elem.text.strip()
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)', date_text)
                        
                        if date_match:
                            ext_date = date_match.group(1)
                            ext_time = date_match.group(2)
                            if len(ext_time) == 5:
                                ext_time += ":00"
                            full_date_time = f"{ext_date} {ext_time}"
                        else:
                            continue
                            
                        date_obj = datetime.strptime(full_date_time, '%Y-%m-%d %H:%M:%S')
                    except: continue
                    
                    title = a_tag.text.strip()
                    raw_link = a_tag.get_attribute("href")
                    if not raw_link: continue
                    link = raw_link if raw_link.startswith('http') else base_url + raw_link
                    
                    links_to_fetch.append({
                        "title": title,
                        "link": link,
                        "full_date_time": full_date_time,
                        "date_obj": date_obj
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
                    
                if item["date_obj"].date() < cutoff_date:
                    continue
                    
                found_in_range = True
                
                if item["link"] in seen_links: continue
                seen_links.add(item["link"])
                
                content = ""
                cat_main, cat_sub = "홈", "최신뉴스"
                
                try:
                    driver.get(item["link"])
                    time.sleep(1.5)
                    
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(0.5)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    
                    try:
                        title_text = driver.title
                        parts = [p.strip() for p in title_text.split('<')]
                        if len(parts) >= 3:
                            cat_sub = parts[1]
                            cat_main = parts[2]
                    except: pass
                    
                    try:
                        content_area = driver.find_element(By.CSS_SELECTOR, "#article-view-content-div")
                        content = content_area.text.strip()
                    except: pass
                except Exception as det_e:
                    print(f"  ❌ 상세페이지 오류 ({item['link']}): {det_e}")
                    
                print(f"  [테크월드뉴스] 수집: {item['full_date_time']} | {item['title'][:20]}...")
                
                results.append({
                    'title': item['title'],
                    'content': content,
                    'content_summary': content[:200].replace('\n', ' ') if content else "",
                    'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'date': str(item['full_date_time']),
                    'provider': '테크월드',
                    'category_main': cat_main,
                    'category_sub': cat_sub,
                    'provider_link_page': item['link'],
                    'useful': 1,
                    'strategy_agenda': 1,
                    'YEAR': item['date_obj'].year,
                    'MONTH': item['date_obj'].month,
                    'WEEK': item['date_obj'].isocalendar()[1]
                })
                time.sleep(1)
                
            if not found_in_range:
                keep_going_section = False
                
            page += 1
            
        except Exception as e:
            print(f"❌ 목록 페이지 로드 오류: {e}")
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
    
    parser = argparse.ArgumentParser(description="Run Techworld crawler independently.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to scrape (DATE_THRESHOLD)")
    args = parser.parse_args()

    print(f"테크월드뉴스 크롤링을 시작합니다. (과거 {args.days}일)")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Ignore certificate errors in Chrome
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--allow-insecure-localhost')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        crawled_data = scrape_techworld_news(driver, days_to_scrape=args.days)
        if crawled_data:
            os.makedirs("output", exist_ok=True)
            today_str = datetime.now().strftime('%Y%m%d')
            filename = f"output/{today_str}_techworld.csv"
            
            keys = crawled_data[0].keys()
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(crawled_data)
            
            print(f"✅ 수집 완료: 총 {len(crawled_data)}건의 기사가 '{filename}'에 성공적으로 저장되었습니다.")
        else:
            print("수집된 기사가 없습니다.")
    finally:
        driver.quit()