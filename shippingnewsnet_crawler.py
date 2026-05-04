"""ShippingNewsNet crawler: RSS-first with selector fallback."""

from crawler_common import (
    DetailConfig,
    RssConfig,
    SelectorConfig,
    apply_record_defaults,
    collect_site_articles,
)


BASE_URL = "https://www.shippingnewsnet.com"

RSS_CONFIG = RssConfig(
    url=f"{BASE_URL}/rss/allArticle.xml",
    provider="쉬핑뉴스넷",
    category_main_default="뉴스",
    category_sub_default="해운/물류",
    reporter_path="dc:creator",
    category_path="category",
    content_path="content:encoded",
)

DETAIL_CONFIG = DetailConfig(
    content_selectors=["#article-view-content-div", ".article-body", "article"],
    category_selectors=[
        ('meta[property="article:section"]', "content"),
        ".article-head-category",
    ],
    reporter_selectors=[('meta[name="author"]', "content"), ".byline em.name"],
    date_selectors=[('meta[property="article:published_time"]', "content")],
)

SECTIONS = [
    {"code": "S2N1", "name": "해운"},
    {"code": "S2N5", "name": "물류"},
]


def _section_selector(section):
    return SelectorConfig(
        list_url=f"{BASE_URL}/news/articleList.html?sc_sub_section_code={section['code']}&view_type=sm&page=1",
        provider="쉬핑뉴스넷",
        item_selector="li",
        link_selector=".titles a",
        title_selector=".titles a",
        date_selector=".info.dated",
        category_selector=".info.category",
        base_url=BASE_URL,
        max_pages=3,
        list_url_builder=lambda page, code=section["code"]: (
            f"{BASE_URL}/news/articleList.html?sc_sub_section_code={code}&view_type=sm&page={page}"
        ),
        category_main_default="뉴스",
        category_sub_default=section["name"],
    )


def get_shippingnewsnet_data(driver=None, days_to_scrape=1, max_items=None, seen_links=None):
    records = collect_site_articles(
        "SHIPPINGNEWSNET",
        rss_config=RSS_CONFIG,
        selector_config=None,
        detail_config=DETAIL_CONFIG,
        days=days_to_scrape,
        max_items=max_items,
        seen_links=seen_links,
        detail_workers=10,
    )

    if not records:
        records = []
        local_seen = set(seen_links or set())
        for section in SECTIONS:
            if max_items is not None and len(records) >= max_items:
                break
            remaining = max_items - len(records) if max_items is not None else None
            section_records = collect_site_articles(
                f"SHIPPINGNEWSNET/{section['name']}",
                selector_config=_section_selector(section),
                detail_config=DETAIL_CONFIG,
                days=days_to_scrape,
                max_items=remaining,
                seen_links=local_seen,
                detail_workers=10,
            )
            records.extend(section_records)
            local_seen.update(
                record.get("provider_link_page") for record in section_records if record.get("provider_link_page")
            )

    return apply_record_defaults(
        records,
        useful=1,
        strategy_agenda=3,
        category_main="뉴스",
        category_sub="해운/물류",
        category1="쉬핑뉴스넷",
        category2="해운/물류",
    )


if __name__ == "__main__":
    data = get_shippingnewsnet_data(days_to_scrape=1, max_items=20)
    print(f"\n수집: {len(data)}건")
