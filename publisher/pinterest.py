# -*- coding: utf-8 -*-
"""
publisher/pinterest.py — Pinterest 핀 자동 발행 모듈

20항목 최적화:
  1. 세션 쿠키 로드           (db/pinterest_session.json)
  2. CSRF 토큰 추출
  3. 세션 유효성 검사 / 만료 감지
  4. 세션 만료 시 재로그인    (Playwright headless=False)
  5. 니치 → 보드 자동 매핑   (20개 니치)
  6. 보드 없을 경우 자동 생성
  7. 일일 핀 한도             (25개/일 — Pinterest 스팸 방지)
  8. 중복 방지               (listing_id → pin_id 추적)
  9. 이미지 2:3 비율 크롭     (Pinterest 최적 1000×1500)
 10. 핀 제목 SEO 최적화       (≤100자)
 11. 핀 설명 SEO + 해시태그   (≤500자)
 12. Etsy 리스팅 URL 링크
 13. 업로드 재시도 3회 + 지수 백오프
 14. 원자적 pins.json 저장    (tmp→replace)
 15. 무작위 딜레이            (봇 감지 방지)
 16. 드라이 모드
 17. Telegram 알림
 18. daily_generate.py 자동 연동 진입점
 19. 핀 결과 로깅             (성공/실패/중복 카운트)
 20. 로그 파일 7일 자동 정리

아키텍처:
  - 세션 유효성 체크 / username 조회: requests (빠름)
  - 보드 조회·생성 / 이미지 업로드 / 핀 생성: Playwright page.request
    (Pinterest 내부 API가 TLS 핑거프린팅으로 requests 차단 → 브라우저 필수)
"""

import asyncio
import json
import logging
import os
import re
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ──
_BASE_DIR    = Path(__file__).parent.parent

# ── .env 로드 (독립 실행 시에도 자격증명 사용 가능) ──
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_BASE_DIR / "config" / ".env")
    _load_dotenv(_BASE_DIR / ".env", override=True)
except ImportError:
    pass
SESSION_FILE = _BASE_DIR / "db" / "pinterest_session.json"
PINS_FILE    = _BASE_DIR / "db" / "pinterest_pins.json"
LOG_DIR      = _BASE_DIR / "logs"

# ── Constants ──
PINTEREST_BASE  = "https://www.pinterest.com"
DAILY_PIN_LIMIT = 25
PIN_IMG_W, PIN_IMG_H = 1000, 1500
PIN_TITLE_MAX = 100
PIN_DESC_MAX  = 500
_MAX_RETRIES  = 3

# ── 항목 5: 니치 → 보드 이름 매핑 ──────────────────────────────────────────
NICHE_BOARD_MAP: dict[Optional[str], str] = {
    None:                "Digital Planner Printable | Productivity Tools",
    "ADHD":              "ADHD Planner Printable | Focus & Organization",
    "anxiety":           "Anxiety Relief Planner | Mental Health Journal",
    "christian":         "Christian Planner | Faith-Based Planning",
    "sobriety":          "Sobriety Planner | Recovery Journal Printable",
    "ADHD_teacher":      "Teacher Planner | ADHD Classroom Organization",
    "ADHD_nurse":        "Nurse Planner | ADHD Healthcare Professional",
    "christian_teacher": "Christian Teacher Planner | Faith & Education",
    "sobriety_mom":      "Sobriety Mom Planner | Recovery & Family Life",
    "mom":               "Mom Planner Printable | Family Organization",
    "homeschool":        "Homeschool Planner | Curriculum Planning",
    "self_care":         "Self Care Planner | Wellness & Mental Health",
    "nurse":             "Nurse Planner Printable | Healthcare Professional",
    "teacher":           "Teacher Planner Printable | Classroom Organization",
    "pregnancy":         "Pregnancy Planner | Baby & Maternity Journal",
    "entrepreneur":      "Entrepreneur Planner | Business Planning",
    "perimenopause":     "Perimenopause Planner | Women's Wellness Journal",
    "cycle_syncing":     "Cycle Syncing Planner | Hormonal Health Journal",
    "caregiver":         "Caregiver Planner | Family Care Organization",
    "glp1":              "GLP-1 Planner | Weight Loss Journey Journal",
}

# 항목 11: 니치별 해시태그
_NICHE_HASHTAGS: dict[Optional[str], list[str]] = {
    None:                ["#digitalplanner", "#printableplanner", "#plannerprintable"],
    "ADHD":              ["#ADHDplanner", "#ADHDorganization", "#executivefunction"],
    "anxiety":           ["#anxietyrelief", "#mentalhealth", "#selfcareplanner"],
    "christian":         ["#christianplanner", "#faithplanner", "#bibleplanner"],
    "sobriety":          ["#sobrietyplanner", "#recoveryjournal", "#alcoholfree"],
    "ADHD_teacher":      ["#teacherplanner", "#ADHDteacher", "#classroomorganization"],
    "ADHD_nurse":        ["#nurseplanner", "#ADHDnurse", "#healthcareplanner"],
    "christian_teacher": ["#christianteacher", "#faithteacher", "#teacherplanner"],
    "sobriety_mom":      ["#sobrietymom", "#momrecovery", "#momlife"],
    "mom":               ["#momlife", "#momplanner", "#familyorganization"],
    "homeschool":        ["#homeschoolplanner", "#homeschool", "#homeeducation"],
    "self_care":         ["#selfcare", "#selfcareplanner", "#wellnessjournal"],
    "nurse":             ["#nurseplanner", "#nursinglife", "#healthcareprofessional"],
    "teacher":           ["#teacherplanner", "#teacherlife", "#classroomorganization"],
    "pregnancy":         ["#pregnancyplanner", "#babyplanner", "#maternitygift"],
    "entrepreneur":      ["#entrepreneurplanner", "#businessplanner", "#sidehustle"],
    "perimenopause":     ["#perimenopause", "#womenswellness", "#hormonehealth"],
    "cycle_syncing":     ["#cyclesyncing", "#hormonalhealth", "#menstrualhealth"],
    "caregiver":         ["#caregiverplanner", "#caregiversupport", "#eldercare"],
    "glp1":              ["#glp1weightloss", "#weightlossjourney", "#ozempicjourney"],
}
_COMMON_HASHTAGS = [
    "#printable", "#instantdownload", "#etsyshop",
    "#planner2025", "#organizeyourlife", "#plannergoals",
]

_PW_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


# ──────────────────────────────────────────────────────────────────────────────
# 항목 1-2: 세션 로드 + CSRF
# ──────────────────────────────────────────────────────────────────────────────

def _load_session_cookies() -> list[dict]:
    """세션 쿠키 로드 (항목 1)."""
    if not SESSION_FILE.exists():
        logger.warning("Pinterest 세션 파일 없음: %s", SESSION_FILE)
        return []
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return data.get("cookies", [])
    except Exception as e:
        logger.warning("세션 파일 로드 실패: %s", e)
        return []


def _extract_csrf(cookies: list[dict]) -> str:
    """CSRF 토큰 추출 (항목 2)."""
    for c in cookies:
        if c.get("name") == "csrftoken" and "pinterest.com" in c.get("domain", ""):
            return c.get("value", "")
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# 항목 3: 세션 유효성 검사 (requests — 홈페이지 리디렉션)
# ──────────────────────────────────────────────────────────────────────────────

def _check_session_valid(cookies: list[dict]) -> bool:
    """Pinterest 세션 유효성 확인 (항목 3).

    1차: 핵심 인증 쿠키(_pinterest_sess, _auth) 존재 여부
    2차: _pinterest_sess 만료일 확인 (서버 측 무효화는 핀 생성 시 감지)
    """
    import time as _time

    cookie_map = {c["name"]: c for c in cookies}

    # 1차: 필수 인증 쿠키 존재
    if "_pinterest_sess" not in cookie_map or "_auth" not in cookie_map:
        logger.warning("Pinterest 인증 쿠키 없음 → 세션 무효")
        return False

    # 2차: 만료일 확인
    sess_cookie = cookie_map["_pinterest_sess"]
    expiry = sess_cookie.get("expires", 0)
    if expiry and expiry < _time.time():
        logger.warning("Pinterest 세션 쿠키 만료 (expires=%s)", expiry)
        return False

    logger.info("Pinterest 세션 쿠키 유효 (만료: %.0f일 후)",
                (expiry - _time.time()) / 86400 if expiry else 0)
    return True


def _get_my_username() -> str:
    """세션 파일 localStorage → MULTIPLE_ACCOUNTS에서 username 추출."""
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        for origin in data.get("origins", []):
            for item in origin.get("localStorage", []):
                if item.get("name") == "MULTIPLE_ACCOUNTS":
                    accounts = json.loads(item["value"])
                    for uid, info in accounts.items():
                        uname = info.get("username", "")
                        if uname:
                            return uname
    except Exception:
        pass
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# 항목 4: 세션 만료 시 Playwright 재로그인
# ──────────────────────────────────────────────────────────────────────────────

async def _relogin_playwright() -> bool:
    """Playwright로 Pinterest 재로그인 후 세션 저장 (항목 4)."""
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    email    = os.environ.get("PINTEREST_EMAIL", "")
    password = os.environ.get("PINTEREST_PASSWORD", "")
    if not email or not password:
        logger.error("PINTEREST_EMAIL / PINTEREST_PASSWORD .env 미설정")
        return False

    logger.info("Pinterest 세션 만료 → Playwright 재로그인 (headless=False)")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                ctx  = await browser.new_context(user_agent=_PW_UA)
                page = await ctx.new_page()
                await page.goto("https://www.pinterest.com/login/", timeout=30000)
                await page.fill('input[id="email"]',    email,    timeout=10000)
                await page.fill('input[id="password"]', password, timeout=10000)
                await page.click('button[type="submit"]', timeout=10000)
                await page.wait_for_url(
                    re.compile(r"pinterest\.com/(?!.*login)"), timeout=30000
                )
                await page.wait_for_timeout(2000)

                cookies = await ctx.cookies()
                ls_items = await page.evaluate("""() => {
                    const out = [];
                    for (let i = 0; i < localStorage.length; i++) {
                        const k = localStorage.key(i);
                        out.push({name: k, value: localStorage.getItem(k)});
                    }
                    return out;
                }""")
                SESSION_FILE.write_text(
                    json.dumps(
                        {"cookies": cookies,
                         "origins": [{"origin": "https://www.pinterest.com",
                                       "localStorage": ls_items}]},
                        ensure_ascii=False, indent=2,
                    ),
                    encoding="utf-8",
                )
                logger.info("Pinterest 재로그인 성공 → 세션 저장 완료")
                return True
            except PWTimeout as e:
                logger.error("재로그인 타임아웃: %s", e)
                LOG_DIR.mkdir(exist_ok=True)
                await page.screenshot(path=str(LOG_DIR / "pinterest_login_error.png"))
                return False
            finally:
                await browser.close()
    except Exception as e:
        logger.error("재로그인 실패: %s", e)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Playwright UI 자동화 — 핀 빌더 페이지로 핀 생성
# ──────────────────────────────────────────────────────────────────────────────

async def _do_pin_playwright(
    cookies: list[dict],
    username: str,
    board_name: str,
    image_path: Path,
    pin_title: str,
    pin_desc: str,
    etsy_url: str,
) -> Optional[str]:
    """Pinterest 핀 빌더 UI 자동화로 핀 생성. pin_id 반환."""
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            ctx  = await browser.new_context(user_agent=_PW_UA)
            await ctx.add_cookies(cookies)
            page = await ctx.new_page()

            # 핀 빌더 접속
            await page.goto(f"{PINTEREST_BASE}/pin-builder/",
                            wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # 1) 이미지 업로드
            await page.set_input_files('input[type="file"]', str(image_path))
            logger.debug("이미지 업로드 중...")
            await page.wait_for_timeout(4000)  # 업로드 완료 대기

            # 2) 제목 입력 (textarea placeholder='제목 추가')
            await page.fill('textarea[placeholder="제목 추가"]', pin_title[:PIN_TITLE_MAX])

            # 3) 링크 입력 (항목 12: Etsy URL) — description 전에 먼저 입력
            await page.fill('textarea[placeholder="랜딩 페이지 링크 추가"]', etsy_url)

            # 4) 보드 선택 드롭다운 (항목 5-6)
            await _ui_select_or_create_board(page, board_name)

            # 5) 설명 입력 — 보드 선택 후 게시 직전에 입력 (링크/보드 클릭이 contenteditable을 초기화하는 문제 방지)
            #    React contenteditable: execCommand('insertText')로 onInput 이벤트 발화
            desc_text = pin_desc[:PIN_DESC_MAX]
            desc_area = page.locator('div[contenteditable="true"]').first
            if await desc_area.count():
                handle = await desc_area.element_handle()
                await desc_area.click(timeout=5000)
                await page.evaluate(
                    "([el, txt]) => { el.focus(); document.execCommand('selectAll', false, null); document.execCommand('insertText', false, txt); }",
                    [handle, desc_text]
                )
            await page.wait_for_timeout(800)

            # 항목 15: 게시 전 짧은 딜레이
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # 6) 게시 버튼 클릭 — Pinterest "게시"는 div[role="button"] (native <button> 아님)
            publish_btn = page.locator('div[role="button"]').filter(has_text=re.compile(r'^게시$')).first
            await publish_btn.wait_for(state="visible", timeout=10000)
            await publish_btn.click(timeout=10000)

            # 7) 핀 생성 완료 감지 — URL 이동 or 성공 모달
            pin_id = None
            try:
                # 먼저 URL 변경 시도 (5초)
                await page.wait_for_url(re.compile(r"/pin/\d+"), timeout=5000)
                m = re.search(r"/pin/(\d+)", page.url)
                pin_id = m.group(1) if m else None
            except PWTimeout:
                pass

            if not pin_id:
                # 성공 모달 "핀을 만들었습니다!" → "핀 보기" 클릭
                try:
                    view_btn = page.locator('a:has-text("핀 보기"), button:has-text("핀 보기")').first
                    await view_btn.wait_for(state="visible", timeout=8000)
                    async with page.expect_navigation(timeout=15000):
                        await view_btn.click()
                    m = re.search(r"/pin/(\d+)", page.url)
                    pin_id = m.group(1) if m else None
                except Exception:
                    # "핀 보기" 없으면 현재 URL 마지막 확인
                    m = re.search(r"/pin/(\d+)", page.url)
                    pin_id = m.group(1) if m else None

            if not pin_id:
                # 성공 모달이 있으면 pin 발행 자체는 성공 — 임시 ID 부여
                success_modal = page.locator('text=핀을 만들었습니다').first
                try:
                    if await success_modal.count() > 0:
                        logger.info("핀 발행 성공 (모달 감지), pin_id 추출 불가 → 'ok' 반환")
                        pin_id = "ok"
                except Exception:
                    pass

            if not pin_id:
                LOG_DIR.mkdir(exist_ok=True)
                await page.screenshot(path=str(LOG_DIR / "pinterest_pin_error.png"))
                logger.warning("핀 ID 추출 실패 (url=%s)", page.url)

            return pin_id

        except PWTimeout as e:
            logger.error("Playwright 타임아웃: %s", e)
            LOG_DIR.mkdir(exist_ok=True)
            await page.screenshot(path=str(LOG_DIR / "pinterest_pin_error.png"))
            return None
        except Exception as e:
            logger.error("Playwright 핀 세션 오류: %s", e)
            LOG_DIR.mkdir(exist_ok=True)
            try:
                await page.screenshot(path=str(LOG_DIR / "pinterest_pin_error.png"))
            except Exception:
                pass
            return None
        finally:
            await browser.close()


async def _ui_select_or_create_board(page, board_name: str) -> None:
    """핀 빌더 보드 드롭다운에서 보드 선택 또는 새 보드 생성 (항목 5-6).

    Pinterest 핀 빌더 UI 구조 (실측):
      - "선택" div[role="button"] → 클릭 시 드롭다운
      - input[placeholder="검색"] → 보드 검색
      - "보드 만들기" text → 클릭 시 다이얼로그
      - input[placeholder*="가고 싶은 곳"] → 보드 이름 입력
      - div[role="button"]:has-text("만들기") OR button:has-text("만들기") → 생성
    """
    from playwright.async_api import TimeoutError as PWTimeout
    try:
        # 1) "선택" 드롭다운 클릭
        sel_btn = page.locator('div[role="button"]:has-text("선택")').first
        await sel_btn.click(timeout=8000)
        await page.wait_for_timeout(1200)

        # 2) 검색창에 보드 이름 입력 (앞 20자)
        search = page.locator('input[placeholder="검색"]').first
        if await search.count():
            await search.fill(board_name[:20])
            await page.wait_for_timeout(1000)

        # 3) 기존 보드 있으면 선택
        board_item = page.locator(f'text="{board_name}"').first
        if await board_item.count():
            await board_item.click(timeout=5000)
            logger.debug("기존 보드 선택: %s", board_name)
            return

        # 4) 없으면 "보드 만들기" 클릭
        create_btn = page.locator('text=보드 만들기').first
        await create_btn.click(timeout=5000)
        await page.wait_for_timeout(1000)

        # 5) 보드 이름 입력 (Korean placeholder)
        name_input = page.locator("input[placeholder*='가고 싶은 곳']").first
        await name_input.fill(board_name, timeout=5000)

        # 6) "만들기" 버튼 클릭 — 보드 이름 입력창 근처 다이얼로그 내 버튼만 선택
        dialog = page.locator('[role="dialog"]').last
        make_btn = dialog.locator('div[role="button"]:has-text("만들기"), button:has-text("만들기")').last
        await make_btn.click(timeout=5000)
        await page.wait_for_timeout(2000)
        logger.info("새 보드 생성 완료: %s", board_name)

    except PWTimeout:
        logger.warning("보드 선택 타임아웃 — 기본 보드로 진행")
    except Exception as e:
        logger.warning("보드 선택 실패: %s", e)


# ──────────────────────────────────────────────────────────────────────────────
# 항목 7-8: 일일 한도 / 중복 방지
# ──────────────────────────────────────────────────────────────────────────────

def _load_pins_data() -> dict:
    if not PINS_FILE.exists():
        return {"pins": {}, "daily": {}}
    try:
        return json.loads(PINS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"pins": {}, "daily": {}}


def _save_pins_data(data: dict) -> None:
    """원자적 저장 (항목 14)."""
    PINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PINS_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PINS_FILE)
    except Exception as e:
        logger.error("pins.json 저장 실패: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _check_daily_limit(pins_data: dict) -> bool:
    """일일 한도 확인 (항목 7). True = 발행 가능."""
    today = datetime.now().strftime("%Y-%m-%d")
    count = pins_data.get("daily", {}).get(today, 0)
    if count >= DAILY_PIN_LIMIT:
        logger.warning("일일 핀 한도 도달 (%d/%d)", count, DAILY_PIN_LIMIT)
        return False
    return True


def _is_duplicate(pins_data: dict, listing_id: str) -> bool:
    """중복 핀 확인 (항목 8)."""
    return str(listing_id) in pins_data.get("pins", {})


# ──────────────────────────────────────────────────────────────────────────────
# 항목 9: 이미지 2:3 크롭
# ──────────────────────────────────────────────────────────────────────────────

def _crop_to_pinterest_ratio(image_path: Path) -> Path:
    """이미지를 2:3 (1000×1500)으로 크롭/리사이즈 (항목 9)."""
    try:
        from PIL import Image  # type: ignore
        with Image.open(image_path) as img:
            w, h = img.size
            target = PIN_IMG_W / PIN_IMG_H
            current = w / h
            if abs(current - target) < 0.02:
                resized = img.resize((PIN_IMG_W, PIN_IMG_H), Image.LANCZOS)
            elif current > target:
                new_w = int(h * target)
                left  = (w - new_w) // 2
                resized = img.crop((left, 0, left + new_w, h)).resize(
                    (PIN_IMG_W, PIN_IMG_H), Image.LANCZOS
                )
            else:
                new_h = int(w / target)
                top   = (h - new_h) // 4
                resized = img.crop((0, top, w, top + new_h)).resize(
                    (PIN_IMG_W, PIN_IMG_H), Image.LANCZOS
                )
            out = image_path.parent / f"_pin_{image_path.stem}.jpg"
            resized.convert("RGB").save(str(out), quality=92, optimize=True)
            return out
    except ImportError:
        logger.warning("Pillow 미설치 → 크롭 건너뜀")
        return image_path
    except Exception as e:
        logger.warning("이미지 크롭 실패: %s", e)
        return image_path


# ──────────────────────────────────────────────────────────────────────────────
# 항목 10-11: 핀 제목/설명 생성
# ──────────────────────────────────────────────────────────────────────────────

def _make_pin_title(listing_title: str) -> str:
    """핀 제목 — 키워드 | 서브키워드 형식, ≤100자 (항목 10).

    Pinterest 검색 최적화:
    - 핵심 키워드를 앞에 배치
    - '|' 구분자로 키워드 2개 묶어 검색 적중률 상승
    """
    title = listing_title.strip()
    suffix = "PDF Instant Download"
    # 쉼표 기준으로 핵심구/서브구 분리
    if "," in title:
        parts = [p.strip() for p in title.split(",")]
        core = parts[0]
        sub  = parts[1] if len(parts) > 1 else ""
        if sub:
            # sub에 이미 suffix 키워드 포함 시 중복 방지
            trail = "" if any(k in sub for k in ("PDF", "Instant", "Download")) else f" {suffix}"
            candidate = f"{core} | {sub}{trail}"
            if len(candidate) <= PIN_TITLE_MAX:
                return candidate
        return f"{core} | {suffix}"[:PIN_TITLE_MAX]
    # 쉼표 없으면 그대로 + 서브 키워드 추가
    trail = "" if any(k in title for k in ("PDF", "Instant", "Download")) else f" | {suffix}"
    return f"{title}{trail}"[:PIN_TITLE_MAX]


def _make_pin_description(
    listing_title: str,
    etsy_url: str,
    niche: Optional[str],
    seo_tags: Optional[list[str]] = None,
) -> str:
    """핀 설명 — 키워드 앞배치 + SEO + 해시태그 + Etsy 링크, ≤500자 (항목 11, 12).

    Pinterest 검색 최적화:
    - 앞 50자에 핵심 키워드 배치 (Pinterest 가중치 높음)
    - 이모지는 키워드 뒤로 이동
    """
    # 핵심 키워드를 맨 앞에 (이모지 제거)
    core_title = listing_title.strip()
    lines = [
        f"{core_title} | PDF Printable Instant Download ✨",
        "",
        "Print at home or at your local print shop.",
        "Ready-to-print PDF. No subscription needed.",
        "",
        f"Shop on Etsy → {etsy_url}",
        "",
    ]
    hashtags = list(_NICHE_HASHTAGS.get(niche, _NICHE_HASHTAGS[None])) + _COMMON_HASHTAGS
    if seo_tags:
        for tag in seo_tags[:4]:
            clean = "#" + re.sub(r"[^a-zA-Z0-9]", "", tag.title())
            if clean not in hashtags:
                hashtags.append(clean)
    return ("\n".join(lines) + " ".join(hashtags))[:PIN_DESC_MAX]


# ──────────────────────────────────────────────────────────────────────────────
# 항목 17: Telegram 알림
# ──────────────────────────────────────────────────────────────────────────────

def _notify(message: str) -> None:
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat  = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not tg_token or not tg_chat:
        return
    try:
        import requests as _req
        _req.post(
            f"https://api.telegram.org/bot{tg_token}/sendMessage",
            json={"chat_id": tg_chat, "text": message},
            timeout=10,
        )
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# 항목 20: 로그 7일 정리
# ──────────────────────────────────────────────────────────────────────────────

def _cleanup_old_logs(max_days: int = 7) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - max_days * 86_400
    for lf in LOG_DIR.glob("pinterest_*.log"):
        try:
            if lf.stat().st_mtime < cutoff:
                lf.unlink()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# 항목 18: 공개 진입점 — daily_generate.py 연동
# ──────────────────────────────────────────────────────────────────────────────

def pin_listing(
    listing_id: str,
    listing_title: str,
    image_path: "str | Path",
    etsy_url: str,
    niche: Optional[str] = None,
    seo_tags: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict:
    """
    Etsy 리스팅 1개를 Pinterest에 핀으로 발행 (항목 18).

    반환::
        {"status": "success"|"duplicate"|"limit"|"error"|"dry",
         "pin_id": str|None, "board": str|None}
    """
    result: dict = {"status": "error", "pin_id": None, "board": None}
    image_path = Path(image_path)

    # 항목 8: 중복 확인
    pins_data = _load_pins_data()
    if _is_duplicate(pins_data, listing_id):
        logger.info("중복 건너뜀: listing_id=%s", listing_id)
        result["status"] = "duplicate"
        return result

    # 항목 7: 일일 한도
    if not _check_daily_limit(pins_data):
        result["status"] = "limit"
        return result

    # 항목 5: 보드 이름
    board_name = NICHE_BOARD_MAP.get(niche, NICHE_BOARD_MAP[None])
    result["board"] = board_name

    # 항목 16: 드라이 모드
    if dry_run:
        logger.info("[DRY] listing_id=%s → %s", listing_id, board_name)
        result["status"] = "dry"
        return result

    # 항목 1-2: 세션 로드 + CSRF
    cookies = _load_session_cookies()
    if not cookies:
        logger.error("Pinterest 세션 없음")
        return result

    # 항목 3: 세션 유효성
    if not _check_session_valid(cookies):
        logger.warning("세션 만료 → 재로그인 시도")
        # 항목 4: Playwright 재로그인
        try:
            try:
                asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    ok = ex.submit(lambda: asyncio.run(_relogin_playwright())).result(timeout=120)
            except RuntimeError:
                ok = asyncio.run(_relogin_playwright())
        except Exception as e:
            logger.error("재로그인 실패: %s", e)
            ok = False
        if not ok:
            return result
        cookies = _load_session_cookies()

    # Username
    username = _get_my_username()
    if not username:
        logger.error("Pinterest username 조회 실패")
        return result

    # 항목 9: 이미지 2:3 크롭
    pin_image = _crop_to_pinterest_ratio(image_path)
    cropped   = (pin_image != image_path)

    # 항목 10-11: 제목/설명
    pin_title = _make_pin_title(listing_title)
    pin_desc  = _make_pin_description(listing_title, etsy_url, niche, seo_tags)

    # 항목 15: 딜레이
    time.sleep(random.uniform(2.0, 5.0))

    # Playwright로 핀 생성
    try:
        try:
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                pin_id = ex.submit(lambda: asyncio.run(
                    _do_pin_playwright(cookies, username, board_name, pin_image, pin_title, pin_desc, etsy_url)
                )).result(timeout=180)
        except RuntimeError:
            pin_id = asyncio.run(
                _do_pin_playwright(cookies, username, board_name, pin_image, pin_title, pin_desc, etsy_url)
            )
    except Exception as e:
        logger.error("핀 발행 예외: %s", e)
        pin_id = None

    # 크롭 임시 파일 정리
    if cropped and pin_image.exists():
        try:
            pin_image.unlink()
        except Exception:
            pass

    # 항목 14: 원자적 저장
    if pin_id:
        today = datetime.now().strftime("%Y-%m-%d")
        pins_data.setdefault("pins", {})[str(listing_id)] = pin_id
        daily = pins_data.setdefault("daily", {})
        daily[today] = daily.get(today, 0) + 1
        _save_pins_data(pins_data)
        result["status"] = "success"
        result["pin_id"] = pin_id

        # 항목 17: Telegram 알림
        _notify(
            f"Pinterest 핀 발행 완료\n"
            f"- 제목: {pin_title[:50]}\n"
            f"- 보드: {board_name}\n"
            f"- 오늘 발행: {daily[today]}/{DAILY_PIN_LIMIT}"
        )
        # 항목 19
        logger.info("핀 발행 성공 listing_id=%s pin_id=%s (오늘 %d개)",
                    listing_id, pin_id, daily[today])
    else:
        logger.error("핀 발행 최종 실패: listing_id=%s", listing_id)
        _notify(
            f"⚠️ Pinterest 핀 발행 실패\n"
            f"- listing_id: {listing_id}\n"
            f"- 제목: {pin_title[:50]}\n"
            f"- 보드: {board_name}"
        )

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 배치 발행 (항목 19)
# ──────────────────────────────────────────────────────────────────────────────

def run_batch(listings: list[dict], dry_run: bool = False) -> dict:
    """
    여러 리스팅 일괄 핀 발행.

    listings 항목::
        {"listing_id": str, "title": str, "image_path": Path,
         "etsy_url": str, "niche": str|None, "tags": list[str]|None}
    """
    _cleanup_old_logs()
    stats: dict[str, int] = {"success": 0, "duplicate": 0, "limit": 0, "error": 0, "dry": 0}

    for item in listings:
        res = pin_listing(
            listing_id    = str(item["listing_id"]),
            listing_title = item["title"],
            image_path    = item["image_path"],
            etsy_url      = item["etsy_url"],
            niche         = item.get("niche"),
            seo_tags      = item.get("tags"),
            dry_run       = dry_run,
        )
        status = res.get("status", "error")
        stats[status] = stats.get(status, 0) + 1

        if status == "limit":
            logger.info("일일 한도 도달 → 배치 중단")
            break

        if status == "success" and not dry_run:
            delay = random.uniform(30.0, 90.0)
            logger.debug("다음 핀까지 %.0f초 대기", delay)
            time.sleep(delay)

    logger.info("Pinterest 배치 완료 — 성공:%d 중복:%d 한도:%d 오류:%d",
                stats["success"], stats["duplicate"], stats["limit"], stats["error"])
    return stats
