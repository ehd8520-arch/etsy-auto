# Etsy Auto — 완전 인수인계 문서

작성일: 2026-04-01

---

## 1. 프로젝트 개요

Etsy 디지털 플래너 자동 생성/업로드 시스템.
8 플래너 타입 × 10 테마 × 20 니치 = **1600개 조합** 자동 생성.

### 파일 구조
```
etsy_auto/
├── daily_generate.py       # 메인 오케스트레이터 (실행 진입점)
├── models.py               # 데이터 모델 (Product, SEOData, Listing, Category)
├── scheduler.py            # APScheduler — 3시간마다 5개 자동 생성
├── stale_listing_pruner.py # 100일+0판매+0리뷰 리스팅 자동 삭제
├── preview_generator.py    # 생성 결과 HTML 미리보기 (base64 self-contained)
├── generator/
│   ├── mockup.py           # 10장 목업 이미지 생성 (Pillow + Together AI)
│   ├── planner_html.py     # 플래너 HTML/PDF 생성 (153페이지)
│   └── listing_video.py    # 12초 MP4 영상 생성 (imageio)
├── seo/
│   └── generator.py        # 제목/태그/설명 생성 (Groq API, A/B테스트)
├── publisher/
│   └── etsy_api.py         # Etsy v3 API 업로드
├── daily_progress.json     # 진행 상황 추적 (완료 조합 목록)
├── .env                    # API 키 (아래 참조)
└── WORK_SUMMARY.md         # 이 파일
```

---

## 2. 1600 조합 상세

### 플래너 타입 (8개)
```
daily, weekly, habit_tracker, goal_setting,
budget, fitness, gratitude, meal
```

### 테마 (10개) — 각각 폰트/레이아웃/색상 완전히 다름
```
sage_green   → #6B8F71  Quicksand, gradient pill
pastel_pink  → #FB6F92  Playfair, gradient pill
lavender     → #7B6BA0  Raleway, minimal line
warm_beige   → #8B7355  Lora serif, side accent
ocean_blue   → #3A6B8C  Poppins, flat block
dark_elegant → #C9A84C  Cormorant, dark card
minimal_mono → #1A1A1A  Inter, minimal line
terracotta   → #C4714A  Josefin Sans, diagonal bg
forest_green → #2D5A27  Merriweather serif
coral_peach  → #E8614A  Nunito bold, side accent
```

### 니치 (20개) — None=generic 포함
```
None(generic), ADHD, anxiety, christian, sobriety,
ADHD_teacher, ADHD_nurse, christian_teacher, sobriety_mom,
mom, homeschool, self_care, nurse, teacher, pregnancy,
entrepreneur, perimenopause, cycle_syncing, caregiver, glp1
```

---

## 3. 실행 명령어

```bash
python daily_generate.py --count 1          # 1개 생성 (테스트)
python daily_generate.py --count 5 --publish # 생성 + Etsy 발행
python daily_generate.py --list             # 진행 상황 확인
python daily_generate.py --preview          # 최신 미리보기 HTML 열기
python daily_generate.py --reset            # 진행 상황 초기화

python scheduler.py                         # 자동 스케줄 실행
python stale_listing_pruner.py --dry        # 삭제 대상 확인만
python stale_listing_pruner.py              # 실제 삭제 실행
```

---

## 4. 환경변수 (.env)

```
GROQ_API_KEY=...           # SEO 생성 (무료, Llama 3.3 70B)
ETSY_API_KEY=...           # Etsy v3 API
ETSY_SHOP_ID=...
TOGETHER_API_KEY_1=...     # FLUX 이미지 생성 (CF 429 폴백)
TOGETHER_API_KEY_2=...     # (선택, 추가 키)
TELEGRAM_BOT_TOKEN=...     # 완료/에러 알림 (선택)
TELEGRAM_CHAT_ID=...
DISCORD_WEBHOOK_URL=...    # 알림 폴백 (선택)
```

**CF API**: Cloudflare Workers AI 10개 계정 사용. 429 소진 시 Together AI 자동 폴백.

---

## 5. 파이프라인 흐름 (1개 상품 기준)

```
1. ALL_COMBINATIONS에서 미완료 조합 선택
2. planner_html.py → HTML 153페이지 생성 → PDF 변환 (A4 + US Letter)
3. mockup.py → 목업 10장 생성:
   01_hero.jpg          태블릿 목업 (Daily log 페이지)
   02_lifestyle_living  플랫레이 (나무 배경)
   03_detail.jpg        INSIDE LOOK + 니치별 callout 배지 4개
   04_lifestyle_bedroom 태블릿 목업 (다른 각도)
   05_whats_included    Monthly + Monthly Review 카드 2장
   06_gallery_wall      멀티프레임
   07_lifestyle_dark    플랫레이 (마블 배경)
   08_size_guide        사이즈 가이드
   09_social_proof      ★★★★★ 니치별 리뷰 3개
   10_brand_cta         브랜드 CTA
4. listing_video.py → 12.3초 MP4 생성 (30fps, 296프레임)
5. seo/generator.py → 제목(A/B테스트)/태그 13개/설명 생성
   → 평균 점수 9.0+ (10점 만점, 8점 미만 재생성)
6. preview_generator.py → HTML 미리보기 생성 + 브라우저 자동 오픈
7. --publish 시: etsy_api.py → 리스팅 생성 + 영상 업로드
8. daily_progress.json 업데이트
```

---

## 6. 완료된 작업 목록

### models.py
- Category enum에 WORKSHEET, SPREADSHEET, WALL_ART, SOCIAL_MEDIA_TEMPLATE, RESUME_TEMPLATE 추가
  (기존 PLANNER만 있어서 KeyError 전파됨 → 전부 추가)
- Product.video_path: str = "" 필드 추가

### seo/generator.py
- `CATEGORY_EXAMPLES` fallback WORKSHEET → PLANNER 수정 (KeyError 방지)
- `_KEYWORD_RESEARCH_AVAILABLE` try/except import 추가 (NameError 방지)
- SEO 제목 자연어 개선 **완료**:
  - `_NICHE_PERSONA` 딕셔너리 추가 (19개 니치 → 영문 페르소나 문장)
  - `_gen_title()` Format: `keyword for [Persona], [Benefit], [Secondary KW]`
  - 니치 감지 시 persona_block 프롬프트 자동 삽입
  - 예시 출력: "Daily Planner Pdf for Busy Moms Juggling Family and Work, Undated All-in-One Layout, GoodNotes Ready"

### daily_generate.py
- 락 파일 (`daily_generate.lock`) — 1시간 타임아웃, 동시 실행 방지
- `_cleanup_old_logs()` — 7일 이상 로그 자동 삭제
- `_notify()` — Telegram(우선) + Discord(폴백) 알림
- `_backup_progress()` — backups/ 폴더에 30일 백업
- `_print_summary` 버그 수정 — progress 파라미터 무시하고 파일 재읽기하던 버그
- `--preview` 플래그 — 최신 preview_*.html os.startfile로 오픈

### preview_generator.py (신규 파일)
- 생성된 상품 HTML 미리보기 (base64 이미지 embedded, 외부 의존성 없음)
- 좌: 갤러리(메인+썸네일, 클릭 전환) / 우: 제목, 가격, 태그, 설명
- 영상 있으면 🎬 배지 / 이미지 클릭 줌 오버레이
- _open_file(): Windows → os.startfile, 나머지 → webbrowser.open

### stale_listing_pruner.py
- 삭제 조건: 100일 경과 AND 0판매 AND 0리뷰 (3가지 모두 충족)
- 기존 "3판매 이하" 오탐 주석/docstring 5곳 → "0판매"로 정정
- 락 파일, 로그 정리, Telegram/Discord 알림 추가

### generator/mockup.py — 품질 개선 (핵심)

#### generate_detail_mockup (03번 목업)
- **버그**: 함수 내부에서 `product` 변수 참조하는데 파라미터에 없어서 NameError
- **수정**: `style: str = ""` 파라미터 추가, 내부 `getattr(product, "style")` → `style`로 교체
- **호출부**: `generate_detail_mockup(art_path, path, category=product.category, style=product.style)`
- 니치별 callout 배지 20개 니치 정상 작동

#### generate_whats_included (05번 목업)
- **버그**: CARD_COLORS = 핑크/청록/오렌지 하드코딩 → 모든 테마에 동일한 색상
- **수정**: `style: str = ""` 파라미터 추가
- `_THEME_ACCENTS` 딕셔너리 (planner_html.py THEMES primary 색상 1:1 대응):
  ```
  pastel_pink(251,111,146)  sage_green(107,143,113)  ocean_blue(58,107,140)
  lavender(123,107,160)     warm_beige(139,115,85)   dark_elegant(201,168,76)
  minimal_mono(100,100,100) terracotta(196,113,74)   forest_green(45,90,39)
  coral_peach(232,97,74)
  ```
- 테마명 longest-match로 감지 (forest_green이 green보다 먼저 매칭)
- feature chips 색상도 테마 accent 적용
- **호출부**: `generate_whats_included(..., style=product.style)`

#### _generate_social_proof_mockup (09번 목업)
- **버그**: PLANNER 카테고리는 default_reviews("Alex P.", "Jordan M.", "Casey R.") 제네릭 사용
- **수정**: `style: str = ""` 파라미터 추가, 11개 니치별 리뷰 딕셔너리 추가
  - 커버된 니치: mom, ADHD, anxiety, christian, nurse, teacher, entrepreneur,
    sobriety, pregnancy, homeschool, self_care
  - 미커버 니치 (generic 사용): perimenopause, cycle_syncing, caregiver, glp1,
    ADHD_teacher, ADHD_nurse, christian_teacher, sobriety_mom ← 다음 작업 후보
- **호출부**: `_generate_social_proof_mockup(art_path, path, product.category, style=product.style)`

#### 멀티페이지 스크린샷 (가장 중요한 개선)
플래너 HTML 153페이지 구조 (직접 확인):
```
Page 0    = Cover
Page 1    = TOC (목차: Yearly/Vision Board/Monthly/Review/Weekly/Daily/Habit/Mood/Notes)
Page 2-3  = Year at a Glance (연간 달력 — 비어있어서 인상적이지 않음)
Page 4    = Vision Board
Page 5-16 = Monthly Overview (1-12월 달력 그리드)
Page 17-28 = Monthly Review (Life Balance Rating, Goals for Next Month)
Page 29-80 = Weekly spreads (53개 주)
Page 81-139 = Daily planner pages (시간 슬롯, 우선순위, 섹션별)
Page 140+ = Notes, Sticker Kit, Thank You
```
- **기존 문제**: `art_path`가 auto-detect(page 2 = Year at a Glance) → 모든 목업에 같은 페이지
- **수정**: `generate_all_mockups`에서 플래너 감지 시 page [5, 20, 30, 100] 4장 스크린샷
  - page 5  = January Monthly Overview
  - page 20 = Monthly Review
  - page 30 = Week 2 Weekly spread
  - page 100 = Daily planner page (가장 콘텐츠 풍부)
- `converted_paths` = 4장 (05_whats_included에서 다른 페이지 표시)
- `art_path` = page 100 (Daily log → 히어로/detail 목업에 사용)

### publisher/etsy_api.py
- `upload_listing_video(shop_id, listing_id, video_path)` 추가 **완료**
- daily_generate.py --publish 시 영상 자동 업로드 연동 **완료**

---

## 7. 현재 상태 (테스트 결과)

```
python daily_generate.py --count 1 실행 결과:
- 목업 10장 생성: ✅
- 영상 생성: ✅ (listing_video.mp4, 12.3초, 296프레임)
- SEO: 제목 9/10, 태그 10/10, 설명 8-10/10, 평균 9.0+
- 미리보기 HTML 자동 오픈: ✅
- 멀티페이지 스크린샷 4장: ✅ (Monthly/Review/Weekly/Daily)
- 니치별 배지/리뷰 적용: ✅
- 테마 색상 일치: ✅

CF API 429 → Together AI 폴백: ✅ 자동 전환 (10개 계정 모두 소진 시)
진행 현황: 약 4개 완료 / 1600개 총
```

---

## 8. 다음 작업 (우선순위 순)

### A. 플래너 Daily log 페이지 샘플 데이터 채우기 [높음]
**파일**: `generator/planner_html.py`
**문제**: Daily log 페이지가 시간 슬롯/섹션 헤더만 있고 내용이 없어서 허전함
**할 일**: daily 페이지 HTML에 샘플 할 일, 시간 블록, 노트 예시 추가
- 예: "7:00 Morning routine", "9:00 Team standup", "📌 Today's Priorities: ..."
- 니치별로 다른 샘플 데이터 (mom: 아이 픽업 일정, nurse: 근무 스케줄)

### B. Social proof 나머지 8개 니치 리뷰 추가 [높음]
**파일**: `generator/mockup.py` → `_generate_social_proof_mockup` 함수
**현재 미커버 니치** (generic 리뷰 사용 중):
perimenopause, cycle_syncing, caregiver, glp1,
ADHD_teacher, ADHD_nurse, christian_teacher, sobriety_mom
**할 일**: `_PLANNER_NICHE_REVIEWS` 딕셔너리에 위 8개 니치 리뷰 세트 추가

### C. 01_hero.jpg 확인 [중간]
art_path = page 100(Daily log)으로 바꾼 후 히어로 목업이 올바른 페이지 표시하는지
`output/planner/{최신id}/mockups/01_hero.jpg` 직접 열어서 확인

### D. 실제 --publish 테스트 [중간]
Etsy API 키 세팅 후 `python daily_generate.py --count 1 --publish`
- 리스팅 생성 → 영상 업로드 → 발행 전체 플로우 검증

### E. 번들 상품 자동 생성 [낮음]
- 같은 니치 2-3개 플래너 → 번들 리스팅 ($6.97, 개별 $2.97 × 3)
- 플랜 미작성, 별도 기획 필요

### F. video_mockup.py 경고 제거 [낮음]
`No module named 'generator.video_mockup'` 경고 발생 (non-critical)
listing_video.py (리스팅용 12초 MP4)는 작동 중
video_mockup.py (00번 목업용 짧은 MP4)는 미구현

---

## 9. 알려진 경고 (무시 가능)

```
WARNING: No module named 'generator.video_mockup'
→ 00번 MP4 목업 미구현. 리스팅 영상(listing_video.mp4)과 별개. 무시 가능.

imageio FFMPEG_WRITER WARNING: resizing 1080→1088
→ MP4 생성 정상. macro_block_size 때문에 자동 리사이즈. 무해.

CF API 429 한도 소진 (10개 계정)
→ Together AI 폴백으로 자동 전환. 정상 흐름.
```
