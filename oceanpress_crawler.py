"""Oceanpress crawler: selector-only fallback path.

GitHub-hosted runners intermittently time out on oceanpress.co.kr. The RSS URL
also returns HTML, not RSS XML, so skip RSS and fail fast on connection blocks.
"""

from crawler_common import (
    DetailConfig,
    SelectorConfig,
    apply_record_defaults,
    collect_site_articles,
)


BASE_URL = "https://oceanpress.co.kr"

SELECTOR_CONFIG = SelectorConfig(
    list_url=f"{BASE_URL}/news/section_list_all.html?sec_no=40&page=1",
    provider="해양통신",
    item_selector='li > a[href*="/news/article.html?no="]',
    title_selector="h2",
    date_selector=".date",
    base_url=BASE_URL,
    max_pages=5,
    list_url_builder=lambda page: f"{BASE_URL}/news/section_list_all.html?sec_no=40&page={page}",
    category_main_default="뉴스",
    category_sub_default="해운/항만/물류",
    timeout=5,
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=[
        "#article-view-content-div",
        ".article-body",
        "#news_body_area",
        ".content",
        "article",
    ],
    date_selectors=[('meta[property="article:published_time"]', "content")],
    timeout=5,
)


def get_oceanpress_data(driver=None, days_to_scrape=1, max_items=None, seen_links=None):
    records = collect_site_articles(
        "OCEANPRESS",
        rss_config=None,
        selector_config=SELECTOR_CONFIG,
        detail_config=DETAIL_CONFIG,
        days=days_to_scrape,
        max_items=max_items,
        seen_links=seen_links,
        detail_workers=10,
    )
    return apply_record_defaults(
        records,
        useful=1,
        strategy_agenda=3,
        category_main="뉴스",
        category_sub="해운/항만/물류",
        category1="해양통신",
        category2="해운/항만/물류",
    )


if __name__ == "__main__":
    data = get_oceanpress_data(days_to_scrape=1, max_items=20)
    print(f"\n수집: {len(data)}건")
