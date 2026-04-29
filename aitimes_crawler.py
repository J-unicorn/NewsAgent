import time
import re
from datetime import datetime, timedelta
import sys
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

def get_aitimes_data(driver, days_to_scrape=1, max_items=None, seen_links=None):
    if seen_links is None:
        seen_links = set()
    cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
    results = []
    base_url = "https://www.aitimes.com"
    
    page = 1
    keep_going_section = True
    
    while keep_going_section:
        list_url = f"https://www.aitimes.com/news/articleList.html?page={page}"
        try:
            driver.get(list_url)
            time.sleep(2)
            
            # Simulate human reading list
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            items = driver.find_elements(By.CSS_SELECTOR, "li.altlist-text-item")
            if not items:
                break
                
            links_to_fetch = []
            
            for item in items:
                try:
                    a_tag = item.find_element(By.CSS_SELECTOR, "a")
                    title = a_tag.text.strip()
                    raw_link = a_tag.get_attribute('href')
                    if not raw_link: continue
                    link = raw_link if raw_link.startswith('http') else base_url.rstrip('/') + '/' + raw_link.lstrip('/')
                    
                    item_text = item.text.replace('\n', ' ')
                    
                    # Date extraction
                    date_match = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})', item_text)
                    short_date_match = re.search(r'(?<!\d)(0[1-9]|1[0-2])[-./](0[1-9]|[12]\d|3[01])(?!\d)', item_text)
                    
                    ext_date = None
                    if date_match:
                        ext_date = date_match.group(1).replace('.', '-').replace('/', '-')
                    elif short_date_match:
                        curr_year = datetime.now().year
                        ext_date = f"{curr_year}-{short_date_match.group(1)}-{short_date_match.group(2)}"
                        
                    full_date_time = datetime.now().strftime("%Y-%m-%d 00:00:00")
                    if ext_date:
                        time_match = re.search(r'(\d{2}:\d{2}(?::\d{2})?)', item_text)
                        ext_time = time_match.group(1) if time_match else "00:00:00"
                        if len(ext_time) == 5:
                            ext_time += ":00"
                        full_date_time = f"{ext_date} {ext_time}"
                        
                    try:
                        date_obj = datetime.strptime(full_date_time, '%Y-%m-%d %H:%M:%S')
                    except:
                        date_obj = datetime.now()
                        full_date_time = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                        
                    links_to_fetch.append({
                        "title": title,
                        "link": link,
                        "date_obj": date_obj,
                        "full_date_time": full_date_time
                    })
                except Exception as e:
                    pass
            
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
                cat_sub = "뉴스"
                
                try:
                    driver.get(item["link"])
                    time.sleep(1.5)
                    
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(0.5)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    
                    try:
                        title_text = driver.title
                        parts = [p.strip() for p in re.split(r'[-|<>&]', title_text)]
                        if len(parts) >= 2:
                            cat_sub = parts[-2]
                    except: pass
                    
                    try:
                        content_area = driver.find_element(By.CSS_SELECTOR, "#article-view-content-div")
                        content = content_area.text.strip()
                    except: pass
                except Exception as det_e:
                    print(f"  ❌ 상세 본문 오류 ({item['link']}): {det_e}")
                    
                print(f"  [AI타임스] 수집: {item['full_date_time']} | {item['title'][:20]}...")
                
                results.append({
                    'title': item['title'],
                    'content': content,
                    'content_summary': content[:200].replace('\n', ' ') if content else "",
                    'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'date': str(item['full_date_time']),
                    'provider': 'AI타임스',
                    'category_main': "분류",
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
            
        except Exception as list_e:
            print(f"❌ 페이지 목록 오류: {list_e}")
            break
            
    return results

if __name__ == "__main__":
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    
    print("AI타임스 테스트 실행 중...")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        data = get_aitimes_data(driver, days_to_scrape=1, max_items=2)
        if data:
            print(f"✅ {len(data)}건 수집 성공!")
            print(f"제목 미리보기: {data[0]['title']}")
            print(f"날짜 미리보기: {data[0]['date']}")
        else:
            print("❌ 수집 실패.")
    finally:
        driver.quit()
