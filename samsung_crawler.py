"""Samsung Newsroom crawler: RSS-first with selector fallback."""

from crawler_common import (
    DetailConfig,
    RssConfig,
    SelectorConfig,
    apply_record_defaults,
    collect_site_articles,
)


BASE_URL = "https://news.samsung.com"

RSS_CONFIG = RssConfig(
    url=f"{BASE_URL}/kr/feed",
    provider="Samsung Newsroom",
    category_main_default="Samsung Newsroom",
    content_path="content:encoded",
)

SELECTOR_CONFIG = SelectorConfig(
    list_url=f"{BASE_URL}/kr/latest",
    provider="Samsung Newsroom",
    item_selector="ul.category_box > li",
    link_selector="a.category_item",
    title_selector=".category_title",
    date_selector=".category_data",
    base_url=BASE_URL,
    max_pages=3,
    list_url_builder=lambda page: f"{BASE_URL}/kr/latest/page/{page}",
    category_main_default="Samsung Newsroom",
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=["div.single_contents", "article"],
    category_selectors=[".footer_category_box .category", ".category"],
    summary_selectors=[("#ai-summary", "data-summary")],
)


def get_samsung_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    records = collect_site_articles(
        "SAMSUNG",
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
        category1="Samsung Newsroom",
        category2="Samsung Newsroom",
    )


class SamsungCrawler:
    def run(self, driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
        return get_samsung_data(driver, days_to_scrape, max_items, global_seen_links)


if __name__ == "__main__":
    data = get_samsung_data(days_to_scrape=1, max_items=20)
    print(f"\n수집: {len(data)}건")
