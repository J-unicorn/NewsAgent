import time
import re
from datetime import datetime, timedelta
import sys
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

def get_oceanpress_data(driver, days_to_scrape=1, max_items=None, seen_links=None):
    if seen_links is None:
        seen_links = set()
    cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
    results = []
    base_url = "https://oceanpress.co.kr"

    page = 1
    found_in_range_section = True
    
    while found_in_range_section:
        if max_items is not None and len(results) >= max_items:
            break
            
        list_url = f"{base_url}/news/section_list_all.html?sec_no=40&page={page}"
        try:
            driver.get(list_url)
            time.sleep(2)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            items = driver.find_elements(By.CSS_SELECTOR, "li > a[href*='/news/article.html?no=']")
            links_to_fetch = []
            
            for item in items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, "h2")
                    title = title_elem.text.strip()
                    if not title: continue
                    
                    raw_link = item.get_attribute("href")
                    if not raw_link: continue
                    link = raw_link if raw_link.startswith('http') else base_url + raw_link
                    
                    full_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    date_obj = datetime.now()
                    
                    try:
                        date_elem = item.find_element(By.CSS_SELECTOR, ".date")
                        date_text = date_elem.text.strip()
                        match = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', date_text)
                        if match:
                            y, m, d, h, mn = match.groups()
                            full_date_time = f"{y}-{m}-{d} {h}:{mn}:00"
                            try:
                                date_obj = datetime.strptime(full_date_time, '%Y-%m-%d %H:%M:%S')
                            except: pass
                    except: pass
                    
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
                    found_in_range_section = False
                    break
                    
                if item["date_obj"].date() < cutoff_date:
                    continue
                    
                found_in_range = True
                
                if item["link"] in seen_links: continue
                seen_links.add(item["link"])
                
                content = ""
                try:
                    driver.get(item["link"])
                    time.sleep(1.5)
                    
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(0.5)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    
                    try:
                        body = None
                        try: body = driver.find_element(By.CSS_SELECTOR, "#article-view-content-div")
                        except:
                            try: body = driver.find_element(By.CSS_SELECTOR, ".article-body")
                            except:
                                try: body = driver.find_element(By.CSS_SELECTOR, "#news_body_area")
                                except:
                                    try: body = driver.find_element(By.CSS_SELECTOR, ".content")
                                    except: pass
                        if body:
                            content = body.text.strip()
                    except: pass
                except Exception as det_e:
                    print(f"  ❌ 상세 본문 오류 ({item['link']}): {det_e}")
                    
                print(f"  [해양통신] 수집: {item['full_date_time']} | {item['title'][:20]}...")
                
                results.append({
                    'title': item['title'],
                    'content': content,
                    'content_summary': content[:200].replace('\n', ' ') if content else "",
                    'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'date': str(item['full_date_time']),
                    'provider': '해양통신',
                    'category_main': '뉴스',
                    'category_sub': '해운/항만/물류',
                    'provider_link_page': item['link'],
                    'useful': 1,
                    'strategy_agenda': 3,
                    'category1': '해양통신',
                    'YEAR': item['date_obj'].year,
                    'MONTH': item['date_obj'].month,
                    'WEEK': item['date_obj'].isocalendar()[1]
                })
                time.sleep(1)
                
            if not found_in_range:
                found_in_range_section = False
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
    
    print("해양통신 테스트 실행 중...")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        data = get_oceanpress_data(driver, days_to_scrape=10, max_items=2)
        if data:
            print(f"✅ {len(data)}건 수집 성공!")
            print(f"제목 미리보기: {data[0]['title']}")
            print(f"날짜 미리보기: {data[0]['date']}")
            print(f"본문 미리보기: {data[0]['content_summary'][:50]}")
        else:
            print("❌ 수집 실패.")
    finally:
        driver.quit()
