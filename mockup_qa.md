# Mockup QA — 상위 1% 비교 검증 기록
> 9점 이상 확정된 항목만 기록. 미달→수정→재검증 후 추가.
> 세션 압축 후에도 이 파일로 중복검증 방지.

---

## 검증 기준
- 비교 대상: Etsy 상위 1% 디지털 플래너 셀러 (BestSelf, Pashion Planner, Clever Fox 수준)
- 합격 기준: 10점 만점 9점 이상
- 테스트 조합: daily × sage_green × [sobriety, ADHD_teacher 등 다수]

---

## ✅ 확정 완료 항목 (9점+)

### 슬롯별

| 슬롯 | 항목 | 점수 | 확정일 | 비고 |
|------|------|------|--------|------|
| 01_hero | 페이지 콘텐츠 품질 (니치별 ghost text) | 9 | 2026-04-01 | 소브리에티/ADHD Teacher 모두 확인 |
| 01_hero | 배지 가독성 (153 Pages + 니치명) | 9 | 2026-04-01 | Bold 64 / SemiBold 40, 좌초록+우청록 |
| 01_hero | 전체 전문성 (태블릿 목업) | 9 | 2026-04-01 | 나무 배경, 소품, 하단 브랜드바 |
| 02_flatlay | 배경 품질 (나무 flatlay_desk) | 8 | 2026-04-01 | AI 생성, 자연스러움. 9점 못됨→재검증 대상 |
| 02_flatlay | 페이퍼 표현 (크기·그림자) | 8 | 2026-04-01 | art_w=66%, paper_y=22%. 9점 못됨→재검증 대상 |
| 02_flatlay | 배지 스타일 (01과 동일 초록+청록) | 9 | 2026-04-01 | 브랜드 일관성 확보 |
| 03_detail | 콜아웃 디자인 (차콜 배경+흰 숫자) | 9 | 2026-04-01 | 4개 버블, sub_f=28, label_f=34, num_f=32 |
| 03_detail | 콘텐츠 가시성 (15%~80% 크롭) | 9 | 2026-04-01 | preview_w=1080(PLANNER), 헤더 제거 후 내용 |
| 03_detail | 니치별 callout 텍스트 | 9 | 2026-04-01 | _NICHE_CALLOUTS dict 19개 니치 |
| 04_bedroom | Monthly Review ghost text | 9 | 2026-04-01 | _REVIEW_SAMPLES 12개 니치 확인 |
| 04_bedroom | Life Balance 별점 (26px) | 9 | 2026-04-01 | planner_html.py font-size:26px |
| 04_bedroom | 배지 가독성 | 9 | 2026-04-01 | 01과 동일 스타일 |
| 05_included | 레이아웃 (2카드 나란히) | 9 | 2026-04-01 | CARD_W~940px, CARD_H~1522px |
| 05_included | 콘텐츠 미리보기 (전체 페이지, 크롭 없음) | 9 | 2026-04-01 | full_page resize (no 1/3 crop) |
| 05_included | 카드 라벨 (Daily Log / Monthly Review) | 9 | 2026-04-01 | _planner_labels = ["Monthly Overview","Monthly Review"] |
| 05_included | 하단 피처 배지 4개 | 9 | 2026-04-01 | Instant Download / Print Ready / No App / Multiple Sizes |
| 06_spread | 카드 크기 (pad=36, gap=36) | 9 | 2026-04-01 | card_w~946px (이전 890 → 확대), 라벨 배지 62px |
| 06_spread | 페이지 선택 (Monthly Overview + Daily Log) | 9 | 2026-04-01 | converted_paths[0] + converted_paths[-1] |
| 06_spread | 헤더 ("WHAT'S INSIDE") | 9 | 2026-04-01 | Bold 54 |
| 07_dark | 배경 품질 (다크 차콜 마블) | 9 | 2026-04-01 | 프로그래밍 방식, AI 우회. base(38,38,43)+대각선 24줄 |
| 07_dark | 페이퍼 대비 (흰 종이 vs 어두운 배경) | 9 | 2026-04-01 | 배경 어두워서 종이 강조됨 |
| 07_dark | 배지 (01과 동일) | 9 | 2026-04-01 | |
| 08_size | 크기 명확성 (US Letter + A4) | 9 | 2026-04-01 | CARD_W=min(860,...), 카드 비율 1.42 |
| 08_size | 인쇄 안내 (4개 옵션) | 9 | 2026-04-01 | Print at Home / Staples / Any Print Shop / Adobe Reader |
| 08_size | 미니 페이지 미리보기 | 9 | 2026-04-01 | mini_h=(CARD_H-110)*0.94 |
| 09_proof | 리뷰 진정성 (니치별 3개) | 9 | 2026-04-01 | _NICHE_REVIEWS 18개 니치 |
| 09_proof | 헤드라인 (니치별, "5-Star Rated...") | 9 | 2026-04-01 | _PROOF_HEADLINES dict |
| 09_proof | 별점 UI | 9 | 2026-04-01 | 금색 ★★★★★ |
| 10_cta | 피처 (니치별 5개) | 9 | 2026-04-01 | _NICHE_CTA_FEATURES 19개 니치 |
| 10_cta | 썸네일 (art_path 좌측) | 9 | 2026-04-01 | _thumb_w=38%W |
| 10_cta | CTA 버튼 ("SHOP THIS ITEM") | 9 | 2026-04-01 | |
| 전체 | 브랜드 일관성 (sage green + teal) | 9 | 2026-04-01 | 전 슬롯 동일 배지 색상 |
| 전체 | 니치 특화도 | 9 | 2026-04-01 | 10장 전부 니치 메시지 포함 |
| 전체 | 타이포그래피 위계 | 9 | 2026-04-01 | |
| 전체 | 가치 전달력 (153페이지+피처) | 9 | 2026-04-01 | |

---

## ⚠️ 재검증 필요 항목 (8점 이하)

| 슬롯 | 항목 | 현점수 | 문제 | 담당 |
|------|------|--------|------|------|
| 02_flatlay | 페이퍼 크기감 | 8 | 66%로 충분하지만 상위 1%는 70%+ 경우 있음 | 미완 (우선순위 낮음) |
| 전체 | PDF 폰트 임베딩 | 7 | web font(Google Fonts) HTML→PDF 시 임베딩 불완전 가능성 | 미완 |
| 전체 | PDF 압축 | 7 | 압축 미적용, 파일 크기 큼 | 미완 |

---

## ✅ 추가 확정 항목 (2026-04-01 2차)

| 단계 | 항목 | 점수 | 확정일 | 구현 |
|------|------|------|--------|------|
| 2.PDF | 주간 플래너 ghost text | 9 | 2026-04-01 | `_WEEKLY_GHOST` 20개 니치, 요일당 2줄 |
| 2.PDF | 감사일기 ghost text | 9 | 2026-04-01 | `_GRATITUDE_GHOST` 20개 니치, 섹션별 순환 |
| 2.PDF | 페이지 수 검증 | 9 | 2026-04-01 | 153페이지 불일치 시 WARNING 출력 |
| 3.목업 | 02_flatlay wood 배경 | 9 | 2026-04-01 | 프로그래밍 방식 월넛 우드 v2: 비네트+대형소품 (식물잎맥+줄기, 머그컵, 펜44px) |
| 3.목업 | 04_bedroom Monthly Review 마감 프롬프트 | 9 | 2026-04-01 | 니치별 3개 closing prompt — nurse 확인 ("What kept me from burnout?") |
| 3.목업 | 06_spread Monthly Goals ghost text | 9 | 2026-04-01 | Monthly Overview 카드에 MONTHLY GOALS 니치별 ghost text 표시 확인 |
| 4.영상 | 슬라이드 선택 | 9 | 2026-04-01 | HTML 캡처 → 목업 10장 중 6장 선택 (01,03,05,07,09,10) |
| 4.영상 | 슬라이드 순서 | 9 | 2026-04-01 | hero→detail→included→dark→proof→cta 순 |
| 4.영상 | 마지막 CTA 프레임 | 9 | 2026-04-01 | `_make_cta_frame()` — 다크 + ★★★★★ + SHOP THIS ITEM |
| 4.영상 | 총 영상 길이 | 9 | 2026-04-01 | 7슬라이드 × 1.4s + fade = 10.8초 |
| 8.발행 | 피크타임 US EST | 9 | 2026-04-01 | `_to_peak_utc()` — 14~18 UTC(9am~1pm EST) 조정 |

---

## 수정 이력 (주요 변경점)

| 날짜 | 슬롯 | 변경 내용 | 이유 |
|------|------|-----------|------|
| 2026-04-01 | 07_dark | AI 마블 → 프로그래밍 다크 차콜 | Together AI 폴백이 흰색/크림으로 나옴 (5점) |
| 2026-04-01 | 06_spread | pad 80→36, gap 60→36 | 카드 너무 작아 배경 여백 과다 (7점) |
| 2026-04-01 | 04_bedroom | Monthly Review ghost text 추가 | 빈 줄만 보여 비전문적 (7점) |
| 2026-04-01 | 01/02/04/07 | 배지 크기 Bold48→64 / SemiBold28→40 | 썸네일에서 너무 작아 안 보임 |
| 2026-04-01 | 03_detail | 크롭 0~60% → 15~80%, preview_w 780→1080 | 헤더만 보이고 콘텐츠 안 보임 |
| 2026-04-01 | 05_included | 1/3 크롭 → 전체 페이지 | Life Balance 별점 안 보임 |
| 2026-04-01 | 09_proof | 헤드라인 "Crafted with Care" → 니치별 | 니치 무관 제목 (7점) |
| 2026-04-01 | 08_size | CARD_W cap 860, CARD_H*1.42 | 카드 너무 작음 |
| 2026-04-01 | 10_cta | _niche_cta_applied 플래그 추가 | generic desc가 니치 피처 옆에 혼용됨 |

---

| 2026-04-01 | 02_flatlay | 프로그래밍 wood v2: 잎맥+줄기+비네트+머그컵 추가 | 소품이 140px로 2000px 캔버스에서 너무 작아 안 보임 (6점) |

---

## 다음 검증 우선순위

1. **02_flatlay wood 배경** — AI 생성 품질 불안정, 프로그래밍 방식 전환 검토
2. 다른 테마(pastel_pink, lavender 등) 목업 품질 — sage_green만 검증됨
3. daily 외 타입(weekly, habit_tracker 등) 슬롯별 검증
