import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

def get_oceanpress_data(days_to_scrape=1, max_items=None, seen_links=None):
    if seen_links is None:
        seen_links = set()
    cutoff_date = (datetime.now() - timedelta(days=days_to_scrape)).date()
    results = []
    base_url = "https://oceanpress.co.kr"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    page = 1
    found_in_range_section = True
    
    while found_in_range_section:
        list_url = f"{base_url}/news/section_list_all.html?sec_no=40&page={page}"
        try:
            resp = requests.get(list_url, headers=headers, timeout=15)
            resp.encoding = resp.apparent_encoding
            
            if resp.status_code != 200:
                break
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select("li > a[href*='/news/article.html?no=']")
            
            if not items:
                break
                
            found_in_range = False
            
            for item in items:
                try:
                    title_elem = item.select_one("h2")
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    if not title:
                        continue
                        
                    raw_link = item['href']
                    link = raw_link if raw_link.startswith('http') else base_url + raw_link
                    
                    if link in seen_links:
                        continue
                        
                    # Date parsing (Format: YYYY-MM-DD HH:MM)
                    date_elem = item.select_one(".date")
                    full_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    date_obj = datetime.now()
                    
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        match = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', date_text)
                        if match:
                            y, m, d, h, mn = match.groups()
                            full_date_time = f"{y}-{m}-{d} {h}:{mn}:00"
                            try:
                                date_obj = datetime.strptime(full_date_time, '%Y-%m-%d %H:%M:%S')
                            except:
                                pass
                    
                    if date_obj.date() < cutoff_date:
                        continue
                        
                    found_in_range = True
                    
                    # Detail page
                    content = ""
                    try:
                        det_resp = requests.get(link, headers=headers, timeout=15)
                        det_resp.encoding = det_resp.apparent_encoding
                        det_soup = BeautifulSoup(det_resp.text, 'html.parser')
                        
                        body = det_soup.select_one("#article-view-content-div")
                        if not body:
                            body = det_soup.select_one(".article-body")
                        if not body:
                            body = det_soup.select_one("#news_body_area")
                        if not body:
                            body = det_soup.select_one(".content")
                            
                        if body:
                            for tag in body.select('script, style, figure, .ad'):
                                tag.decompose()
                            content = body.get_text('\n', strip=True)
                    except Exception as det_e:
                        print(f"  ❌ 상세 본문 오류 ({link}): {det_e}")
                        
                    print(f"  [해양통신] 수집: {full_date_time} | {title[:20]}...")
                    
                    results.append({
                        'title': title,
                        'content': content,
                        'content_summary': content[:200].replace('\n', ' '),
                        'enveloped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'date': str(full_date_time),
                        'provider': '해양통신',
                        'category_main': '뉴스',
                        'category_sub': '해운/항만/물류',
                        'provider_link_page': link,
                        'useful': 1,
                        'strategy_agenda': 3,
                        'category1': '해양통신',
                        'YEAR': date_obj.year,
                        'MONTH': date_obj.month,
                        'WEEK': date_obj.isocalendar()[1]
                    })
                    seen_links.add(link)
                    time.sleep(1)
                    
                    if max_items and len(results) >= max_items:
                        return results
                        
                except Exception as item_e:
                    print(f"  ❌ 항목 오류: {item_e}")
                    continue
                    
            if not found_in_range:
                found_in_range_section = False
            page += 1
            
        except Exception as list_e:
            print(f"❌ 페이지 목록 오류: {list_e}")
            break
            
    return results

if __name__ == "__main__":
    print("해양통신 테스트 실행 중...")
    data = get_oceanpress_data(days_to_scrape=10, max_items=2) # Using larger date range to ensure we find items during test
    if data:
        print(f"✅ {len(data)}건 수집 성공!")
        print(f"제목 미리보기: {data[0]['title']}")
        print(f"날짜 미리보기: {data[0]['date']}")
        print(f"본문 미리보기: {data[0]['content_summary'][:50]}")
    else:
        print("❌ 수집 실패.")
