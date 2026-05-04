"""BUSINESSPOST crawler: RSS-first with selector fallback."""

from crawler_common import DetailConfig, RssConfig, SelectorConfig, collect_site_articles


BASE_URL = "https://www.businesspost.co.kr"

RSS_CONFIG = RssConfig(
    url=f"{BASE_URL}/rss/Article.xml",
    provider="비즈니스포스트",
    reporter_path="author",
    category_path="category",
    content_path="description",
)

SELECTOR_CONFIG = SelectorConfig(
    list_url=f"{BASE_URL}/BP",
    provider="비즈니스포스트",
    item_selector='a[href*="command=article_view"]',
    base_url=BASE_URL,
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=["div.detail_editor", "#article-view-content-div", "article"],
    category_selectors=[
        ('meta[property="article:section"]', "content"),
        ('meta[property="og:category"]', "content"),
    ],
    reporter_selectors=[
        ('meta[property="article:author"]', "content"),
        ('meta[name="author"]', "content"),
    ],
    date_selectors=[('meta[property="article:published_time"]', "content")],
)


def get_businesspost_data(driver=None, days=1, max_items=100, seen_links=None):
    return collect_site_articles(
        "BUSINESSPOST",
        rss_config=RSS_CONFIG,
        selector_config=SELECTOR_CONFIG,
        detail_config=DETAIL_CONFIG,
        days=days,
        max_items=max_items,
        seen_links=seen_links,
        detail_workers=10,
    )


if __name__ == "__main__":
    data = get_businesspost_data(days=1, max_items=20)
    print(f"\n수집: {len(data)}건")
