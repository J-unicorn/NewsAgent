"""Shared search keyword sets for external news crawlers."""


GOOGLE_NEWS_TARGET_GROUPS = [
    {
        "name": "China Competitors",
        "targets": ["海尔", "美的", "海信集團"],
        "locale": "hl=zh-CN&gl=CN&ceid=CN%3Azh-Hans",
        "extra_query": "-ETF -专利",
    },
    {
        "name": "Global Competitors",
        "targets": ["Electrolux", "GE Appliance", "Whirlpool", "Bosch Appliance"],
        "locale": "hl=en-US&gl=US&ceid=US%3Aen",
        "extra_query": "",
    },
    {
        "name": "Logistics Keywords",
        "targets": ["수에즈 운하", "파나마 운하", "홍해", "SCFI"],
        "locale": "hl=ko&gl=KR&ceid=KR%3Ako",
        "extra_query": "",
    },
]


GOOGLE_NEWS_QUERY_TARGETS = [
    target
    for group in GOOGLE_NEWS_TARGET_GROUPS
    for target in group["targets"]
]


NAVER_NEWS_GOOGLE_TARGET_ALIASES = [
    "하이얼",
    "메이디",
    "하이센스",
    "일렉트로룩스",
    "GE 어플라이언스",
    "월풀",
    "보쉬 가전",
]


NAVER_NEWS_HS_REPRO_QUERIES = [
    "로봇 물고기",
    "중국 로봇",
    "중국 로봇 취업",
    "중국 로봇 일자리",
    "코웨이 말레이시아",
    "보람그룹 삼성",
    "삼성 LG",
    "삼성 중국",
    "LG전자 중국",
    "쿠팡 녹색제품",
    "KDI 유가 물가",
    "고용보험 가입자",
    "고용보험 27만",
    "해상 초크포인트",
    "브렌트유 증시",
    "환율 물가",
    "현대연 환율",
    "파월 긴축",
    "트럼프미디어 손실",
    "LG전자 냉난방공조",
    "국내 로봇",
    "군용 로봇",
    "현대차 로봇",
    "스마트테크 코리아",
    "소방청 AI 로봇",
    "트럼프 이란",
    "이란 종전",
    "이란 봉쇄",
    "이란 원유",
    "네타냐후 이란",
    "베이징 이란 러시아",
    "모디 기름",
    "삼성 성과급",
    "삼성 노사 성과급",
]


NAVER_NEWS_HS_SUPPLEMENTAL_QUERIES_2026_05_12 = [
    "골드만삭스 한은",
    "정부 확장재정",
    "갤럭시 중국",
    "중국 전기차",
    "트럼프 러시아 이란",
    "맥코믹 유니레버",
    "알파벳 AI",
    "코트라 선전",
    "기술보호법",
    "중국 조선업",
    "나프타 플라스틱",
    "금융 ESG",
    "삼성 총파업",
    "산업 ESG",
    "국민연금 ESG",
    "전기차 시장",
    "엑손 셰브론",
    "EU 공급망",
    "타타 JSW",
    "AI 반도체",
    "현대차 할인전략",
    "Husqvarna climate",
    "YOFC ESG",
    "APsystems ESG",
    "Science Based Targets",
]


def unique_keywords(*groups):
    keywords = []
    seen = set()
    for group in groups:
        for keyword in group:
            normalized = " ".join(str(keyword).split())
            key = normalized.casefold()
            if normalized and key not in seen:
                seen.add(key)
                keywords.append(normalized)
    return keywords
