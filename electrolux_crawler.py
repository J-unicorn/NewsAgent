"""Electrolux Newsroom crawler: RSS-first with selector fallback."""

from crawler_common import (
    DetailConfig,
    RssConfig,
    SelectorConfig,
    apply_record_defaults,
    collect_site_articles,
)


BASE_URL = "https://www.electroluxgroup.com"

CATEGORIES = [
    {
        "name": "Press Releases",
        "url": f"{BASE_URL}/en/category/newsroom/press-releases/",
        "rss": f"{BASE_URL}/en/category/newsroom/press-releases/feed/",
    },
    {
        "name": "News",
        "url": f"{BASE_URL}/en/category/newsroom/news/",
        "rss": f"{BASE_URL}/en/category/newsroom/news/feed/",
    },
    {
        "name": "Local Newsrooms",
        "url": f"{BASE_URL}/en/category/newsroom/local-newsrooms/",
        "rss": f"{BASE_URL}/en/category/newsroom/local-newsrooms/feed/",
    },
]

DETAIL_CONFIG = DetailConfig(
    content_selectors=[".entry-content", "article"],
    date_selectors=[("time.published", "datetime"), ("time.entry-date", "datetime")],
)


def _category_configs(category):
    rss_config = RssConfig(
        url=category["rss"],
        provider="Electrolux Newsroom",
        category_main_default=category["name"],
        content_path="content:encoded",
    )
    selector_config = SelectorConfig(
        list_url=category["url"],
        provider="Electrolux Newsroom",
        item_selector="article",
        link_selector="h2.entry-title a",
        title_selector="h2.entry-title a",
        date_selector=("time.published", "datetime"),
        base_url=BASE_URL,
        max_pages=3,
        list_url_builder=lambda page, base=category["url"]: base if page == 1 else f"{base}page/{page}/",
        category_main_default=category["name"],
    )
    return rss_config, selector_config


def get_electrolux_data(driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
    results = []
    seen_links = set(global_seen_links or set())

    for category in CATEGORIES:
        if max_items is not None and len(results) >= max_items:
            break

        remaining = max_items - len(results) if max_items is not None else None
        rss_config, selector_config = _category_configs(category)
        records = collect_site_articles(
            f"ELECTROLUX/{category['name']}",
            rss_config=rss_config,
            selector_config=selector_config,
            detail_config=DETAIL_CONFIG,
            days=days_to_scrape,
            max_items=remaining,
            seen_links=seen_links,
            detail_workers=10,
        )
        apply_record_defaults(
            records,
            useful=1,
            strategy_agenda=1,
            category_main=category["name"],
            category1="Electrolux Newsroom",
            category2=category["name"],
        )
        results.extend(records)
        seen_links.update(record.get("provider_link_page") for record in records if record.get("provider_link_page"))

    return results


class ElectroluxCrawler:
    def run(self, driver=None, days_to_scrape=1, max_items=None, global_seen_links=None):
        return get_electrolux_data(driver, days_to_scrape, max_items, global_seen_links)


if __name__ == "__main__":
    data = get_electrolux_data(days_to_scrape=1, max_items=20)
    print(f"\n수집: {len(data)}건")
