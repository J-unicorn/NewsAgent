import time
import json
import pandas as pd
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

class SamsungCrawler:
    def __init__(self):
        self.base_url = "https://news.samsung.com/kr/latest"
        self.driver = None

    def _format_datetime(self, date_str):
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        clean_str = date_str.replace('/', '-')
        
        try:
            if 'T' in clean_str:
                dt = datetime.fromisoformat(clean_str)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            
            if len(clean_str) <= 10:
                return f"{clean_str} 00:00:00"
            
            return datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
        except:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def get_detail_data(self, url):
        self.driver.get(url)
        time.sleep(1.5)
        
        # Simulate human scrolling
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(0.5)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
        
        raw_date = None

        try:
            json_ld_tags = self.driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
            for tag in json_ld_tags:
                data = json.loads(tag.get_attribute("innerHTML"))
                item = data[0] if isinstance(data, list) else data
                if 'datePublished' in item:
                    raw_date = item['datePublished']
                    break
        except: pass

        if not raw_date:
            try:
                date_tag = self.driver.find_element(By.CSS_SELECTOR, 'p.single-date')
                raw_date = date_tag.text.strip()
            except: pass

        formatted_date = self._format_datetime(raw_date)

        content = ""
        try:
            content_div = self.driver.find_element(By.CSS_SELECTOR, 'div.single_contents')
            tags = content_div.find_elements(By.CSS_SELECTOR, 'p, h4')
            for tag in tags:
                content += tag.text.strip() + "\n"
        except: pass
        
        content_summary = ""
        try:
            ai_summary_tag = self.driver.find_element(By.CSS_SELECTOR, '#ai-summary')
            content_summary = ai_summary_tag.get_attribute('data-summary') or ""
        except: pass
        
        categories = []
        try:
            cat_items = self.driver.find_elements(By.CSS_SELECTOR, '.footer_category_box .category')
            for item in cat_items:
                p = item.find_element(By.CSS_SELECTOR, '.parent_category_name').text.strip()
                n = item.find_element(By.CSS_SELECTOR, '.now').text.strip()
                if p and n: categories.append(f"{p}>{n}")
        except: pass
        
        return {
            "date": formatted_date,
            "content": content.strip(),
            "content_summary": content_summary,
            "category1": categories[0] if len(categories) > 0 else "",
            "category2": categories[1] if len(categories) > 1 else ""
        }

    def run(self, driver, days_to_scrape=1, max_items=None, global_seen_links=None):
        if max_items is not None and max_items <= 0:
            max_items = None
            
        self.driver = driver
        cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
        results = []
        seen_links = set(global_seen_links) if global_seen_links else set()
        page = 1
        keep_going = True

        while keep_going:
            if max_items is not None and len(results) >= max_items:
                break
                
            self.driver.get(f"{self.base_url}/page/{page}")
            time.sleep(2)
            
            # Simulate human reading list
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            items = self.driver.find_elements(By.CSS_SELECTOR, 'ul.category_box > li')
            if not items: break

            page_items = []
            for item in items:
                try:
                    list_date_str = item.find_element(By.CSS_SELECTOR, '.category_data').text.strip()
                    list_date_obj = datetime.strptime(list_date_str, '%Y/%m/%d').date()
                    
                    title = item.find_element(By.CSS_SELECTOR, '.category_title').text.strip()
                    link = item.find_element(By.CSS_SELECTOR, 'a.category_item').get_attribute('href')
                    
                    page_items.append({
                        "date_obj": list_date_obj,
                        "title": title,
                        "link": link
                    })
                except Exception as e:
                    print(f"  [Samsung] List Parsing Error: {e}")

            for p_item in page_items:
                if max_items is not None and len(results) >= max_items:
                    keep_going = False
                    break
                    
                if p_item["date_obj"] < cutoff_date:
                    keep_going = False
                    break

                if p_item["link"] in seen_links: continue
                seen_links.add(p_item["link"])

                try:
                    detail = self.get_detail_data(p_item["link"])
                    
                    dt_obj = datetime.strptime(detail['date'], '%Y-%m-%d %H:%M:%S')
                    cat_main = detail['category1'].split('>')[0] if '>' in detail['category1'] else detail['category1']
                    cat_sub = detail['category1'].split('>')[1] if '>' in detail['category1'] else ''
                    
                    results.append({
                        "title": p_item["title"],
                        "content": detail['content'],
                        "enveloped_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "date": str(detail['date']),
                        "provider": "Samsung Newsroom",
                        "category_main": cat_main.strip(),
                        "category_sub": cat_sub.strip(),
                        "reporter": "",
                        "provider_link_page": p_item["link"],
                        "useful": 1, "strategy_agenda": 1,
                        "content_summary": detail['content_summary'],
                        "category1": "Samsung Newsroom",
                        "category2": detail['category1'],
                        "YEAR": dt_obj.year, "MONTH": dt_obj.month, "WEEK": dt_obj.isocalendar()[1]
                    })
                except Exception as ex:
                    print(f"  [Samsung] Detail Parsing Error: {ex}")
                finally:
                    time.sleep(1)
                    
            page += 1
            
        return results

if __name__ == "__main__":
    import argparse
    import csv
    import os
    parser = argparse.ArgumentParser(description="Run Samsung Newsroom crawler independently.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to scrape (DATE_THRESHOLD)")
    args = parser.parse_args()
    
    print(f"삼성뉴스룸 크롤링을 시작합니다. (과거 {args.days}일)")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        crawler = SamsungCrawler()
        data = crawler.run(driver, days_to_scrape=args.days)
        
        if data:
            os.makedirs("output", exist_ok=True)
            today_str = datetime.now().strftime('%Y%m%d')
            filename = f"output/{today_str}_samsung.csv"
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