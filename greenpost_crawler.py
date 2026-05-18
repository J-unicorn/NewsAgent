"""GreenPost Korea crawler: RSS-first with selector fallback."""

from crawler_common import DetailConfig, RssConfig, SelectorConfig, collect_site_articles


BASE_URL = "https://www.greenpostkorea.co.kr"
PROVIDER = "그린포스트코리아"

RSS_CONFIG = RssConfig(
    url=f"{BASE_URL}/rss/allArticle.xml",
    provider=PROVIDER,
    reporter_path="dc:creator",
    category_path="category",
    content_path="description",
)

SELECTOR_CONFIG = SelectorConfig(
    list_url=f"{BASE_URL}/news/articleList.html",
    provider=PROVIDER,
    item_selector='a[href*="articleView.html"]',
    base_url=BASE_URL,
    category_main_default="ESG",
    category_sub_default="GreenPost",
    max_pages=1,
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=["#article-view-content-div", ".article-body", "article"],
    category_selectors=[
        ('meta[property="article:section"]', "content"),
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
        ".info-text",
    ],
    max_content_length=2500,
)


def get_greenpost_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    return collect_site_articles(
        "GREENPOST",
        rss_config=RSS_CONFIG,
        selector_config=SELECTOR_CONFIG,
        detail_config=DETAIL_CONFIG,
        days=days_to_scrape,
        max_items=max_items,
        seen_links=global_seen_links,
        detail_workers=2,
        detail_request_delay=1.0,
    )


if __name__ == "__main__":
    data = get_greenpost_data(days_to_scrape=1, max_items=20)
    print(f"\n수집: {len(data)}건")
