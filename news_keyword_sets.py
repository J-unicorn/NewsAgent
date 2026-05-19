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
    "풀뎁스 로봇 물고기",
    "중국 로봇 청년 취업",
    "노동절 로봇 베이징",
    "코웨이 말레이시아 신규상품 매출",
    "보람그룹 삼성 가전 할인",
    "삼성 LG 전장사업",
    "쿠팡 녹색제품 기획전",
    "한국개발연구원 유가 물가",
    "KDI 고유가 길어지면 물가",
    "고용보험 가입자 27만",
    "해상 초크포인트 대응",
    "브렌트유 아시아 증시",
    "환율 상승 물가압력",
    "현대硏 환율 10% 물가",
    "파월 긴축 구제",
    "트럼프미디어 1분기 손실",
    "트루스소셜 가상화폐 적자 2배",
    "LG전자 중국 생태계 활용",
    "LG전자 냉난방공조 2030 매출 20조",
    "국내 로봇 해외산",
    "샌드위치 K-로봇 품질 가격",
    "군용 로봇 시장 성장",
    "현대차 비전투 로봇",
    "스마트테크 코리아 로봇",
    "소방청 AI 로봇 위원회",
    "미국 이란 종전협상",
    "이란 답변 수용 못해 트럼프 반응",
    "이란 해상봉쇄 원유",
    "이란 점진적 감산 봉쇄 대응",
    "네타냐후 이란 우라늄",
    "모디 기름 소비 절감",
    "모디 지하철 카풀 기름 절약",
    "삼성전자 노사 성과급 사후조정",
    "반도체 적자부서 3억 성과급",
]


NAVER_NEWS_HS_SUPPLEMENTAL_QUERIES_2026_05_12 = [
    "골드만삭스 한은 금리인상",
    "정부 내년도 확장재정",
    "삼성 갤럭시S27 중국 패널",
    "중국 관영매체 미국 전기차 진출",
    "트럼프 베이징 이란 러시아 지원 압박",
    "맥코믹 유니레버 합병 ESG",
    "알파벳 AI 투자 주가",
    "코트라 선전 배터리 수출상담회",
    "기술보호법 강화",
    "중국 조선업 수주",
    "나프타 부족 플라스틱",
    "금융 ESG 인재 채용",
    "삼성 총파업 공급망 리스크",
    "산업 ESG 협의체",
    "국민연금 ESG 공시",
    "전기차 시장 혼합 전략",
    "엑손 셰브론 CCS",
    "EU 공급망 AI 규제",
    "타타 JSW 전기차 배터리",
    "AI 반도체 슈퍼사이클",
    "현대차 할인전략 영업익",
    "Husqvarna climate targets",
    "YOFC ESG report",
    "APsystems ESG report",
    "Science Based Targets initiative",
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
