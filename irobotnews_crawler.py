"""iRobotNews crawler: RSS-first with selector fallback."""

from crawler_common import (
    DetailConfig,
    RssConfig,
    SelectorConfig,
    apply_record_defaults,
    collect_site_articles,
)


BASE_URL = "https://www.irobotnews.com"

RSS_CONFIG = RssConfig(
    url=f"{BASE_URL}/rss/allArticle.xml",
    provider="로봇신문",
    category_main_default="홈",
    category_sub_default="최신뉴스",
    reporter_path="dc:creator",
    category_path="category",
    content_path="content:encoded",
)

SELECTOR_CONFIG = SelectorConfig(
    list_url=f"{BASE_URL}/news/articleList.html?page=1&view_type=sm",
    provider="로봇신문",
    item_selector="ul.altlist-webzine > li.altlist-webzine-item:not(#sample)",
    link_selector="h2.altlist-subject a",
    title_selector="h2.altlist-subject a",
    base_url=BASE_URL,
    max_pages=3,
    list_url_builder=lambda page: f"{BASE_URL}/news/articleList.html?page={page}&view_type=sm",
    category_main_default="홈",
    category_sub_default="최신뉴스",
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=["article#article-view-content-div", "#article-view-content-div", "article"],
    category_selectors=[
        ('meta[property="article:section"]', "content"),
        ".article-head-category",
    ],
    reporter_selectors=[
        ('meta[name="author"]', "content"),
        ".byline em.name",
    ],
    date_selectors=[
        ('meta[property="article:published_time"]', "content"),
        "ul.infomation",
    ],
)


def get_irobotnews_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    records = collect_site_articles(
        "IROBOTNEWS",
        rss_config=RSS_CONFIG,
        selector_config=SELECTOR_CONFIG,
        detail_config=DETAIL_CONFIG,
        days=days_to_scrape,
        max_items=max_items,
        seen_links=global_seen_links,
        detail_workers=10,
    )
    return apply_record_defaults(
        records,
        useful=1,
        strategy_agenda=1,
        category_main="홈",
        category_sub="최신뉴스",
        category1="로봇신문",
        category2="최신뉴스",
    )


if __name__ == "__main__":
    data = get_irobotnews_data(days_to_scrape=1, max_items=20)
    print(f"\n수집: {len(data)}건")
