import time
import re
from datetime import datetime, timedelta
import sys
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

def get_shippingnewsnet_data(driver, days_to_scrape=1, max_items=None, seen_links=None):
    if seen_links is None:
        seen_links = set()
    cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
    results = []
    base_url = "https://www.shippingnewsnet.com"
    
    sections = [
        {"code": "S2N1", "name": "해운"},
        {"code": "S2N5", "name": "물류"}
    ]

    for section in sections:
        page = 1
        found_in_range_section = True
        
        while found_in_range_section:
            if max_items is not None and len(results) >= max_items:
                break
                
            list_url = f"{base_url}/news/articleList.html?sc_sub_section_code={section['code']}&view_type=sm&page={page}"
            try:
                driver.get(list_url)
                time.sleep(2)
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                
                items = driver.find_elements(By.CSS_SELECTOR, "li")
                links_to_fetch = []
                
                for item in items:
                    try:
                        a_tags = item.find_elements(By.CSS_SELECTOR, ".titles a")
                        if not a_tags: continue
                        a_tag = a_tags[0]
                        
                        raw_link = a_tag.get_attribute('href')
                        if not raw_link or 'articleView' not in raw_link: continue
                        
                        title = a_tag.text.strip()
                        link = raw_link if raw_link.startswith('http') else base_url + raw_link
                        
                        full_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        date_obj = datetime.now()
                        cat_sub = section['name']
                        
                        try:
                            cat_elem = item.find_element(By.CSS_SELECTOR, ".info.category")
                            cat_sub = cat_elem.text.strip()
                        except: pass
                        
                        try:
                            date_elem = item.find_element(By.CSS_SELECTOR, ".info.dated")
                            date_text = date_elem.text.strip()
                            curr_year = datetime.now().year
                            match = re.search(r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})', date_text)
                            if match:
                                m, d, h, mn = match.groups()
                                full_date_time = f"{curr_year}-{m}-{d} {h}:{mn}:00"
                                try:
                                    date_obj = datetime.strptime(full_date_time, '%Y-%m-%d %H:%M:%S')
                                    if date_obj > datetime.now() + timedelta(days=1):
                                        date_obj = date_obj.replace(year=curr_year - 1)
                                        full_date_time = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                                except: pass
                        except: pass
                        
                        links_to_fetch.append({
                            "title": title,
                            "link": link,
                            "full_date_time": full_date_time,
                            "date_obj": date_obj,
                            "cat_sub": cat_sub
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
                            content_area = driver.find_element(By.CSS_SELECTOR, "#article-view-content-div")
                            content = content_area.text.strip()
                        except: pass
                    except Exception as det_e:
                        print(f"  ❌ 상세 본문 오류 ({item['link']}): {det_e}")
                        
                    print(f"  [쉬핑뉴스넷 - {section['name']}] 수집: {item['full_date_time']} | {item['title'][:20]}...")
                    
                    results.append({
                        'title': item['title'],
                        'content': content,
                        'content_summary': content[:200].replace('\n', ' ') if content else "",
                        'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'date': str(item['full_date_time']),
                        'provider': '쉬핑뉴스넷',
                        'category_main': '뉴스',
                        'category_sub': item['cat_sub'],
                        'provider_link_page': item['link'],
                        'useful': 1,
                        'strategy_agenda': 3,
                        'category1': '쉬핑뉴스넷',
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
    
    print("쉬핑뉴스넷 테스트 실행 중...")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        data = get_shippingnewsnet_data(driver, days_to_scrape=1, max_items=2)
        if data:
            print(f"✅ {len(data)}건 수집 성공!")
            print(f"제목 미리보기: {data[0]['title']}")
            print(f"날짜 미리보기: {data[0]['date']}")
            print(f"본문 미리보기: {data[0]['content_summary'][:50]}")
        else:
            print("❌ 수집 실패.")
    finally:
        driver.quit()
