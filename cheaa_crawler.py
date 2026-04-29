import time
import re
from datetime import datetime, timedelta
import sys
from deep_translator import GoogleTranslator
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

def translate_text(text, max_retries=3):
    if not text: return ""
    text_to_translate = text[:4500]
    for attempt in range(max_retries):
        try:
            translated = GoogleTranslator(source='auto', target='ko').translate(text_to_translate)
            if translated: return translated
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  [번역 실패] {e}")
                return text_to_translate
            time.sleep(1.5 * (attempt + 1))
    return text_to_translate

def get_cheaa_data(driver, days_to_scrape=1, max_items=None, global_seen_links=None):
    if max_items is not None and max_items <= 0:
        max_items = None
        
    cutoff_date = datetime.now() - timedelta(days=days_to_scrape)
    results = []
    seen_links = set(global_seen_links) if global_seen_links else set()
    base_url = "https://m.cheaa.com/"
    
    for page in range(1, 4):
        if max_items is not None and len(results) >= max_items:
            break
            
        url = base_url if page == 1 else f"{base_url}include/ajax_more.php?type=index&page={page}"
        try:
            driver.get(url)
            time.sleep(2)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            boxes = driver.find_elements(By.CSS_SELECTOR, "div.newsBox")
            links_to_fetch = []
            
            for box in boxes:
                try:
                    p_b = box.find_element(By.CSS_SELECTOR, "p b")
                    date_text = p_b.text.strip()
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                    if not date_match: continue
                    
                    list_date_only = date_match.group(1)
                    date_obj = datetime.strptime(list_date_only, '%Y-%m-%d')
                    
                    a_tag = box.find_element(By.CSS_SELECTOR, "p a")
                    raw_link = a_tag.get_attribute('href')
                    if not raw_link: continue
                    link = raw_link if raw_link.startswith('http') else "https://news.cheaa.com" + raw_link
                    
                    title = a_tag.text.strip()
                    if not title: continue
                    
                    links_to_fetch.append({
                        "title": title,
                        "link": link,
                        "list_date_only": list_date_only,
                        "date_obj": date_obj
                    })
                except Exception as e:
                    pass
            
            for item in links_to_fetch:
                if max_items is not None and len(results) >= max_items:
                    break
                    
                if item["date_obj"].date() < cutoff_date.date():
                    continue
                    
                if item["link"] in seen_links: continue
                seen_links.add(item["link"])
                
                full_date_time = f"{item['list_date_only']} 00:00:00"
                content = ""
                cat_main = ""
                
                try:
                    driver.get(item["link"])
                    time.sleep(1.5)
                    
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(0.5)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    
                    try:
                        info_area = driver.find_element(By.CSS_SELECTOR, "div.info")
                        info_text = info_area.text.strip()
                        time_pattern = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)', info_text)
                        if time_pattern:
                            ext_date = time_pattern.group(1)
                            ext_time = time_pattern.group(2)
                            if len(ext_time) == 5: ext_time += ":00"
                            full_date_time = f"{ext_date} {ext_time}"
                    except: pass
                    
                    try:
                        cont_area = None
                        try: cont_area = driver.find_element(By.CSS_SELECTOR, "div#ctrlfscont")
                        except:
                            try: cont_area = driver.find_element(By.CSS_SELECTOR, "div.article")
                            except: pass
                            
                        if cont_area:
                            content = cont_area.text.strip()
                    except: pass
                    
                    try:
                        title_text = driver.title
                        parts = [p.strip() for p in title_text.split('-')]
                        if len(parts) >= 2:
                            cat_main = parts[1]
                    except: pass
                except Exception as ex:
                    print(f"  [CHEAA] Detail Parsing Error: {ex}")

                print(f"  [CHEAA] 매칭: {full_date_time} | {item['title'][:20]}...")

                results.append({
                    'title': translate_text(item['title']),
                    'content': translate_text(content),
                    'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'date': str(full_date_time),
                    'provider': 'cheaa',
                    'category_main': translate_text(cat_main), 
                    'category_sub': '',
                    'provider_link_page': item['link'],
                    'useful': 1, 'strategy_agenda': 0,
                    'content_summary': translate_text(content[:200]) if content else "",
                    'category1': 'cheaa', 'category2': '',
                    'YEAR': item['date_obj'].year, 'MONTH': item['date_obj'].month, 'WEEK': item['date_obj'].isocalendar()[1]
                })
                time.sleep(1.2)
                
        except Exception as e:
            print(f"  ❌ CHEAA 페이지 오류: {e}")
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
    
    parser = argparse.ArgumentParser(description="Run CHEAA crawler independently.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to scrape (DATE_THRESHOLD)")
    args = parser.parse_args()
    
    print(f"CHEAA 크롤링을 시작합니다. (과거 {args.days}일)")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        data = get_cheaa_data(driver, days_to_scrape=args.days)
        if data:
            os.makedirs("output", exist_ok=True)
            today_str = datetime.now().strftime('%Y%m%d')
            filename = f"output/{today_str}_cheaa.csv"
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