"""TECHWORLD crawler: RSS-first with selector fallback."""

from crawler_common import DetailConfig, RssConfig, SelectorConfig, collect_site_articles


BASE_URL = "https://www.epnc.co.kr"

RSS_CONFIG = RssConfig(
    url="https://cdn.epnc.co.kr/rss/gn_rss_allArticle.xml",
    provider="테크월드뉴스",
    reporter_path="dc:creator",
    category_path="category",
    content_path="content:encoded",
)

SELECTOR_CONFIG = SelectorConfig(
    list_url=f"{BASE_URL}/news/articleList.html",
    provider="테크월드뉴스",
    item_selector="li.altlist-text-item",
    link_selector='a[href*="articleView"]',
    date_selector=".altlist-info-item:nth-child(3)",
    category_selector=".altlist-info-item:nth-child(1)",
    reporter_selector=".altlist-info-item:nth-child(2)",
    base_url=BASE_URL,
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=["#article-view-content-div", "article"],
    category_selectors=[
        ('meta[property="article:section"]', "content"),
        ('meta[property="article:section1"]', "content"),
        ".article-head-category",
        ".breadcrumb a",
    ],
    reporter_selectors=[
        ('meta[name="author"]', "content"),
        ".byline em.name",
        ".user-info .name",
    ],
    date_selectors=[
        ('meta[property="article:published_time"]', "content"),
        ".updated",
        ".byline",
    ],
)


def get_techworld_data(driver=None, days=1, max_items=100, seen_links=None):
    return collect_site_articles(
        "TECHWORLD",
        rss_config=RSS_CONFIG,
        selector_config=SELECTOR_CONFIG,
        detail_config=DETAIL_CONFIG,
        days=days,
        max_items=max_items,
        seen_links=seen_links,
        detail_workers=10,
    )


if __name__ == "__main__":
    data = get_techworld_data(days=1, max_items=20)
    print(f"\n수집: {len(data)}건")
