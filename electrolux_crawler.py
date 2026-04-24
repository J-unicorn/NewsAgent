import time
import sys
import pandas as pd
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# utf-8 for console output robustness
sys.stdout.reconfigure(encoding='utf-8')

class ElectroluxCrawler:
    def __init__(self):
        self.driver = None

    def _setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(30)

    def _format_datetime(self, date_str):
        try:
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def get_detail_data(self, url):
        try:
            self.driver.get(url)
            time.sleep(1.5)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            content_tag = soup.select_one('.entry-content')
            content = ""
            if content_tag:
                content = content_tag.get_text(' ', strip=True)
            return content
        except Exception as e:
            print(f"  [Electrolux] Detail Parsing Error: {e}")
            return ""

    def run(self, days_to_scrape=1, max_items=None, global_seen_links=None):
        if max_items is not None and max_items <= 0:
            max_items = None
            
        self._setup_driver()
        cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
        results = []
        seen_links = set(global_seen_links) if global_seen_links else set()
        
        categories = [
            {"url": "https://www.electroluxgroup.com/en/category/newsroom/press-releases/", "cat": "Press Releases"},
            {"url": "https://www.electroluxgroup.com/en/category/newsroom/news/", "cat": "News"},
            {"url": "https://www.electroluxgroup.com/en/category/newsroom/local-newsrooms/", "cat": "Local Newsrooms"}
        ]
        
        try:
            for cat_info in categories:
                page = 1
                keep_going = True
                
                while keep_going:
                    if max_items is not None and len(results) >= max_items:
                        break
                        
                    page_url = f"{cat_info['url']}page/{page}/" if page > 1 else cat_info['url']
                    try:
                        self.driver.get(page_url)
                        time.sleep(2)
                        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                        
                        articles = soup.select('article')
                        if not articles:
                            break
                            
                        # Links to fetch
                        links_to_fetch = []
                        
                        for article in articles:
                            if max_items is not None and len(results) + len(links_to_fetch) >= max_items:
                                keep_going = False
                                break
                            
                            time_tag = article.select_one('time.published')
                            if not time_tag or not time_tag.has_attr('datetime'):
                                continue
                                
                            raw_date = time_tag['datetime']
                            dt_obj = datetime.fromisoformat(raw_date)
                            
                            if dt_obj.date() < cutoff_date:
                                keep_going = False
                                break
                                
                            title_tag = article.select_one('h2.entry-title a')
                            if not title_tag:
                                continue
                                
                            title = title_tag.get_text(strip=True)
                            link = title_tag['href']
                            
                            if link in seen_links:
                                continue
                                
                            seen_links.add(link)
                            
                            links_to_fetch.append({
                                "title": title,
                                "link": link,
                                "date": raw_date,
                                "dt_obj": dt_obj
                            })
                            
                        # Now fetch the details
                        for item in links_to_fetch:
                            content = self.get_detail_data(item['link'])
                            formatted_date = item['dt_obj'].strftime('%Y-%m-%d %H:%M:%S')
                            
                            results.append({
                                "title": item['title'],
                                "content": content,
                                "enveloped_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "date": formatted_date,
                                "provider": "Electrolux Newsroom",
                                "category_main": cat_info['cat'],
                                "category_sub": "",
                                "reporter": "",
                                "provider_link_page": item['link'],
                                "useful": 1,
                                "strategy_agenda": 1,
                                "content_summary": "",
                                "category1": "Electrolux Newsroom",
                                "category2": cat_info['cat'],
                                "YEAR": item['dt_obj'].year,
                                "MONTH": item['dt_obj'].month,
                                "WEEK": item['dt_obj'].isocalendar()[1]
                            })
                            
                    except Exception as e:
                        print(f"  [Electrolux] Page Request Error: {e}")
                        break
                        
                    page += 1
        finally:
            if self.driver:
                self.driver.quit()
                
        return results

def get_electrolux_data(days_to_scrape=1, max_items=None, global_seen_links=None):
    crawler = ElectroluxCrawler()
    return crawler.run(days_to_scrape, max_items, global_seen_links)

if __name__ == "__main__":
    import argparse
    import csv
    import os
    parser = argparse.ArgumentParser(description="Run Electrolux Newsroom crawler independently.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to scrape (DATE_THRESHOLD)")
    args = parser.parse_args()
    
    print(f"일렉트로룩스 뉴스룸 크롤링을 시작합니다. (과거 {args.days}일)")
    data = get_electrolux_data(days_to_scrape=args.days)
    
    if data:
        os.makedirs("output", exist_ok=True)
        today_str = datetime.now().strftime('%Y%m%d')
        filename = f"output/{today_str}_electrolux.csv"
        keys = data[0].keys()
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data)
        print(f"✅ 수집 완료: 총 {len(data)}건 -> {filename}")
    else:
        print("수집된 기사가 없습니다.")
