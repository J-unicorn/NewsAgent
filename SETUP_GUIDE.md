# test_scrapling 브랜치 셋업 가이드

## 🎯 Phase 1: 3개 사이트만 Scrapling으로 마이그레이션

### 대상 사이트
- AITIMES
- TECHWORLD  
- BUSINESSPOST

### 나머지 8개 (Phase 2에서 처리)
- ZDWANG, CHEAA, SAMSUNG, IROBOTNEWS
- GOOGLE_NEWS, ELECTROLUX, SHIPPINGNEWSNET, OCEANPRESS

---

## 📋 셋업 순서

### Step 1: test_scrapling 브랜치 생성

```bash
cd ~/pyenv/claude/hsdata/news_collector

# 현재 브랜치 확인
git branch

# test_hs 또는 main 기준으로 새 브랜치 생성
git checkout test_hs  # 또는 main
git checkout -b test_scrapling

# 원격에 push (브랜치 생성)
git push -u origin test_scrapling
```

### Step 2: 파일 교체

다운로드한 파일들을 적절한 위치에 복사:

```bash
# 1. 공통 헬퍼 추가
cp ~/Downloads/crawler_common.py ./

# 2. 크롤러 3개 교체 (Scrapling 버전)
cp ~/Downloads/aitimes_crawler.py ./
cp ~/Downloads/techworld_crawler.py ./
cp ~/Downloads/businesspost_crawler.py ./

# 3. news_collector.py 교체
cp ~/Downloads/news_collector.py ./

# 4. requirements.txt 추가/교체
cp ~/Downloads/requirements.txt ./

# 5. workflow 추가
mkdir -p .github/workflows
# ⚠️ 기존 daily-crawler-test-hs.yml 등이 있으면 일단 둠
cp ~/Downloads/daily-crawler-scrapling.yml .github/workflows/
```

### Step 3: 변경 확인

```bash
git status

# 예상 출력:
# new file: crawler_common.py
# new file: requirements.txt
# new file: .github/workflows/daily-crawler-scrapling.yml
# modified: aitimes_crawler.py
# modified: techworld_crawler.py
# modified: businesspost_crawler.py
# modified: news_collector.py
```

### Step 4: Commit & Push

```bash
git add .
git commit -m "Phase 1: Migrate 3 sites to Scrapling (AITIMES, TECHWORLD, BUSINESSPOST)"
git push origin test_scrapling
```

### Step 5: Actions 확인

```
https://github.com/J-unicorn/NewsAgent/actions
```

`Daily News Crawler (Scrapling)` workflow가 실행됨.

---

## 🧪 로컬 테스트 (선택, 권장)

push 전에 로컬에서 먼저 테스트하면 실수를 줄일 수 있어요:

```bash
# 1. Scrapling 설치
pip install "scrapling[fetchers]"

# 2. 한 사이트만 테스트
SITE=AITIMES python news_collector.py

# 또는 단독 실행
python aitimes_crawler.py
```

**예상 출력:**
```
🚀 Scrapling 기반 뉴스 수집 시작 (최근 1일치)
📦 Phase 1: AITIMES, TECHWORLD, BUSINESSPOST (3개 사이트)
🎯 단일 사이트 모드: AITIMES
📖 수집 기록: 0개 기사 건너뛰기

--- AITIMES 수집 중 (최대 100개) ---
[AITIMES] 기사 목록 수집 중...
[AITIMES] 100개 항목 발견
[AITIMES] 본문 수집 대상: 100개
[AITIMES] 진행: 25/100
[AITIMES] 진행: 50/100
[AITIMES] 진행: 75/100
[AITIMES] 진행: 100/100
[AITIMES] 완료: 100개 수집
✅ AITIMES: 100건 수집 완료 (15.3초)
```

**핵심 확인 포인트:**
- 100개 수집에 **15-30초** 정도 걸리면 ✅ 성공
- 1분 이상 걸리면 셀렉터 문제 가능성

---

## 📊 예상 vs 실제 비교

### Selenium 버전 (이전)
```
AITIMES 100개:        ~5분
TECHWORLD 100개:      ~4분  
BUSINESSPOST 100개:   ~5분
순차 합계:           ~14분
```

### Scrapling 버전 (Phase 1)
```
AITIMES 100개:        ~30초
TECHWORLD 100개:      ~30초
BUSINESSPOST 100개:   ~30초
병렬 실행:            ~30-60초
```

**예상 향상: 15-30배** 🚀

---

## 🚨 흔한 문제 해결

### 1. ImportError: No module named 'scrapling'

```bash
pip install "scrapling[fetchers]"
```

### 2. ModuleNotFoundError: No module named 'crawler_common'

`crawler_common.py`를 `news_collector.py`와 같은 디렉토리에 두었는지 확인.

### 3. 0개 수집됨

→ 사이트 셀렉터가 변경됐을 가능성. 코드 내 셀렉터 확인:
- `aitimes_crawler.py`: `li.altlist-text-item`
- `techworld_crawler.py`: `h2.titles a`
- `businesspost_crawler.py`: `div.left_post`

브라우저에서 해당 사이트 열고 F12로 확인.

### 4. 본문이 비어있음

→ 본문 셀렉터 확인:
- AITIMES: `#article-view-content-div`
- TECHWORLD: `#article-view-content-div`
- BUSINESSPOST: `div.detail_editor`

### 5. workflow가 실행 안 됨

→ `.github/workflows/daily-crawler-scrapling.yml` 파일이 test_scrapling 브랜치에 있는지 확인

---

## 🎯 Phase 1 성공 기준

✅ 3개 사이트 모두 수집 성공  
✅ 각 사이트 100개 기사 1분 이내 완료  
✅ CSV 파일 생성 + Artifact 업로드  
✅ 데이터 품질 (제목, 본문, URL) 정상

성공하면 **Phase 2** 진행:
- 나머지 8개 사이트 마이그레이션
- 또는 안정화 운영

---

## 📞 문제 발생 시

각 단계마다 결과를 확인하면서 진행해주세요:

1. 로컬 테스트 결과 → 알려주기
2. Push 후 GitHub Actions 로그 → 알려주기
3. Artifact 다운로드해서 CSV 품질 → 확인

문제 있으면 로그와 함께 공유해주세요.
