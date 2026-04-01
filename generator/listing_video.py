# -*- coding: utf-8 -*-
"""
listing_video.py — 플래너 HTML에서 페이지 플립 MP4 영상 자동 생성.

Etsy 요구사양: 5~15초, 최소 720p, MP4 형식.
전략:
  1. 페이지 플립 프리뷰 (실제 플래너 페이지 스크린샷 — 빠른 전환)
  2. 목업 슬라이드 5장 (전문 목업 이미지)
  3. 숫자 카운트업 ('153+ Pages · 12 Months · 52 Weeks')
  4. 컬러 펄스 CTA 프레임 (테마 색상 기반 밝기 맥동)

의존성:
    pip install imageio[ffmpeg] pillow playwright
"""
import logging
import math
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 영상 사양 ──
VIDEO_FPS     = 24
VIDEO_WIDTH   = 1080
VIDEO_HEIGHT  = 1080

# ── 목업 슬라이드 설정 ──
# 10_brand_cta는 CTA pulse 프레임이 대체 → 5장만 사용
_MOCKUP_SLIDE_ORDER = [
    "01_hero.jpg",           # 제품 전체 인상
    "03_detail.jpg",         # INSIDE LOOK 콜아웃 — 구매 설득력 최고
    "05_whats_included.jpg", # 무엇이 들어있나
    "07_lifestyle_dark.jpg", # 다크 마블 드라마틱
    "09_social_proof.jpg",   # 리뷰/신뢰
]
_MOCKUP_PAGE_DURATION = 1.3   # 목업 체류 시간(초)
_MOCKUP_FADE_FRAMES   = 8     # 목업 간 크로스페이드 프레임

# ── 페이지 플립 설정 ──
_FLIP_PAGE_DURATION = 0.45    # 빠른 전환 (0.45초)
_FLIP_FADE_FRAMES   = 4       # 짧은 페이드

# ── 테마 RGB 색상 ──
_THEME_COLORS: dict[str, tuple[int, int, int]] = {
    "sage_green":   (107, 143, 113),
    "pastel_pink":  (251, 111, 146),
    "lavender":     (123, 107, 160),
    "warm_beige":   (139, 115,  85),
    "ocean_blue":   ( 58, 107, 140),
    "dark_elegant": (201, 168,  76),
    "minimal_mono": ( 60,  60,  65),
    "terracotta":   (196, 113,  74),
    "forest_green": ( 45,  90,  39),
    "coral_peach":  (232,  97,  74),
}


def _get_theme_rgb(style: str) -> tuple[int, int, int]:
    """style 문자열(예: 'daily_sage_green_ADHD')에서 테마 RGB 추출."""
    for theme_name, rgb in _THEME_COLORS.items():
        if theme_name in style:
            return rgb
    return _THEME_COLORS["sage_green"]


def _try_font(size: int):
    """PIL 폰트 로드 — Windows/Mac/Linux 경로 순서로 시도, 실패 시 기본 폰트."""
    from PIL import ImageFont
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _niche_label_from_style(style: str) -> str:
    """style에서 니치 레이블 추출 ('ADHD' → 'ADHD Planner')."""
    if not style:
        return ""
    _known = [
        "ADHD_teacher", "ADHD_nurse", "christian_teacher", "sobriety_mom",
        "ADHD", "anxiety", "christian", "sobriety", "mom", "nurse",
        "teacher", "pregnancy", "entrepreneur", "homeschool", "self_care",
        "caregiver", "perimenopause", "cycle_syncing", "glp1",
    ]
    for nk in sorted(_known, key=len, reverse=True):
        if style.endswith("_" + nk) or style == nk:
            return nk.replace("_", " ").title() + " Planner"
    return ""


# ── 유틸리티 ──

def _collect_mockup_slides(product_dir: Path) -> list[str]:
    """mockups/ 폴더에서 정해진 순서대로 슬라이드 경로 수집."""
    mockup_dir = product_dir / "mockups"
    if not mockup_dir.exists():
        return []
    return [str(mockup_dir / f) for f in _MOCKUP_SLIDE_ORDER
            if (mockup_dir / f).exists()]


def _find_page_screenshots(product_dir: Path) -> list[Path]:
    """목업 생성 시 저장된 플래너 페이지 스크린샷 수집 (최대 3개).
    mockup.py가 _page_*.png 또는 screenshot_*.png 형태로 저장.
    """
    found: list[Path] = []
    search_dirs = [product_dir, product_dir / "mockups"]
    patterns = [
        "_page_*.png", "page_*.png",
        "_screenshot_p*.png", "screenshot_*.png",
        "_planner_page_*.png",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for pat in patterns:
            found.extend(sorted(d.glob(pat)))

    # 중복 제거 + 최대 3개
    seen: set[str] = set()
    unique: list[Path] = []
    for p in found:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:3]


def _build_frames(screenshot_paths: list[str],
                  page_dur: float = 1.3,
                  fade_f: int = 8,
                  end_hold_sec: float = 0.0) -> list:
    """스크린샷 목록 → 크로스페이드 포함 numpy 프레임 배열 목록.
    end_hold_sec: 마지막 프레임 정지 시간 (다음 세그먼트 없을 때만 사용).
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        logger.warning("pillow 미설치")
        return []

    hold_frames = max(1, int(VIDEO_FPS * page_dur) - fade_f)
    frames: list = []
    images: list = []

    for path in screenshot_paths:
        try:
            img = Image.open(path).convert("RGB").resize(
                (VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS
            )
            images.append(np.array(img, dtype=np.uint8))
        except Exception as e:
            logger.debug("이미지 로드 실패 %s: %s", path, e)

    if not images:
        return []

    for i, img in enumerate(images):
        for _ in range(hold_frames):
            frames.append(img)
        if i < len(images) - 1:
            nxt = images[i + 1]
            for f in range(fade_f):
                alpha = (f + 1) / (fade_f + 1)
                blended = (img * (1 - alpha) + nxt * alpha).astype(np.uint8)
                frames.append(blended)

    if end_hold_sec > 0 and images:
        for _ in range(int(VIDEO_FPS * end_hold_sec)):
            frames.append(images[-1])

    return frames


# ── 신규: 숫자 카운트업 애니메이션 ──

def _make_stats_frames(theme_rgb: tuple[int, int, int], style: str = "") -> list:
    """'153+ Pages · 12 Months · 52 Weeks' 카운트업 애니메이션.
    Why: 플래너의 양적 가치를 숫자로 직관적으로 전달 → 전환율 향상.
    Duration: 1.0초 (24 frames @ 24fps)
    """
    try:
        from PIL import Image, ImageDraw
        import numpy as np
    except ImportError:
        return []

    TOTAL = 24   # 1.0초
    W = H = VIDEO_WIDTH
    tr, tg, tb = theme_rgb

    font_num  = _try_font(108)
    font_unit = _try_font(30)

    # 카운트업 목표 (숫자, 단위 레이블, 색상 오버라이드)
    targets = [
        ("153", "+", "PAGES"),
        ("12",  "",  "MONTHLY\nCALENDARS"),
        ("52",  "",  "WEEKLY\nPLANNERS"),
    ]

    # 테마 컬러 밝은 버전 (숫자 색)
    num_r = min(255, tr + 80)
    num_g = min(255, tg + 80)
    num_b = min(255, tb + 80)

    frames = []
    for i in range(TOTAL):
        t = i / max(TOTAL - 1, 1)           # 0.0 → 1.0 (ease-out)
        t_eased = 1 - (1 - t) ** 2          # ease-out quad

        img  = Image.new("RGB", (W, H), (20, 20, 24))
        draw = ImageDraw.Draw(img)

        # 상단/하단 테마 컬러 바
        draw.rectangle([(0, 0),    (W, 10)],   fill=theme_rgb)
        draw.rectangle([(0, H-10), (W, H)],    fill=theme_rgb)

        col_w = W // 3
        for col_i, (num_str, suffix, label) in enumerate(targets):
            cx = col_i * col_w + col_w // 2
            cy = H // 2

            num_val  = int(num_str)
            current  = int(num_val * t_eased)
            display  = str(current) + suffix

            draw.text((cx, cy - 55), display,
                      fill=(num_r, num_g, num_b), font=font_num, anchor="mm")

            # 단위 레이블 (줄바꿈 처리)
            for li, line in enumerate(label.split("\n")):
                draw.text((cx, cy + 70 + li * 36), line,
                          fill=(170, 165, 160), font=font_unit, anchor="mm")

            # 컬럼 구분선
            if col_i < len(targets) - 1:
                lx = (col_i + 1) * col_w
                draw.line([(lx, cy - 110), (lx, cy + 120)],
                          fill=(55, 55, 60), width=2)

        frames.append(np.array(img, dtype=np.uint8))

    return frames


# ── 신규: 컬러 펄스 CTA 프레임 ──

def _make_cta_pulse_frames(theme_rgb: tuple[int, int, int], style: str = "") -> list:
    """테마 색상 기반 CTA 프레임 + 컬러 펄스 (밝기 sine 맥동).
    Why: 마지막 프레임에 구매 유도 + 컬러 펄스로 시선 집중.
         상위 1% Etsy 영상은 마지막 2초를 CTA에 집중 사용.
    Duration: 1.5초 (36 frames @ 24fps) — 3 pulse cycles
    """
    try:
        from PIL import Image, ImageDraw
        import numpy as np
    except ImportError:
        return []

    TOTAL = 36   # 1.5초
    W = H = VIDEO_WIDTH
    tr, tg, tb = theme_rgb
    niche_label = _niche_label_from_style(style)

    font_star = _try_font(44)
    font_xl   = _try_font(52)
    font_md   = _try_font(32)
    font_sm   = _try_font(24)

    frames = []
    for i in range(TOTAL):
        # 컬러 펄스: 3 사이클 sine 파 (-1 ~ +1)
        pulse     = math.sin(i / TOTAL * math.pi * 6)
        shift     = int(pulse * 18)

        bg_r = max(0, min(255, 26 + shift // 3))
        bg_g = max(0, min(255, 26 + shift // 3))
        bg_b = max(0, min(255, 30 + shift // 3))

        ac_r = max(0, min(255, tr + shift))
        ac_g = max(0, min(255, tg + shift))
        ac_b = max(0, min(255, tb + shift))
        accent = (ac_r, ac_g, ac_b)

        img  = Image.new("RGB", (W, H), (bg_r, bg_g, bg_b))
        draw = ImageDraw.Draw(img)

        # 상하 그라디언트 배너 (테마 컬러 → 배경)
        banner_h = H // 8
        for y in range(banner_h):
            ratio = 1 - (y / banner_h)
            row = (
                int(ac_r * ratio + bg_r * (1 - ratio)),
                int(ac_g * ratio + bg_g * (1 - ratio)),
                int(ac_b * ratio + bg_b * (1 - ratio)),
            )
            draw.line([(0, y),       (W, y)],       fill=row)
            draw.line([(0, H-1-y),   (W, H-1-y)],   fill=row)

        cx = W // 2

        # ★★★★★ (테마 컬러 계열)
        star_r = min(255, ac_r + 70)
        star_g = min(255, ac_g + 50)
        star_b = max(0,   ac_b - 20)
        draw.text((cx, H // 2 - 200), "★  ★  ★  ★  ★",
                  fill=(star_r, star_g, star_b), font=font_star, anchor="mm")

        # INSTANT DOWNLOAD
        draw.text((cx, H // 2 - 120), "INSTANT DOWNLOAD",
                  fill=(255, 255, 255), font=font_xl, anchor="mm")

        # 니치 레이블
        if niche_label:
            draw.text((cx, H // 2 - 45), niche_label,
                      fill=(min(255, ac_r+80), min(255, ac_g+80), min(255, ac_b+80)),
                      font=font_md, anchor="mm")

        # 페이지 정보
        draw.text((cx, H // 2 + 35), "153 Pages  ·  PDF  ·  Print Ready",
                  fill=(175, 170, 165), font=font_sm, anchor="mm")

        # 브랜드
        draw.text((cx, H // 2 + 95), "DailyPrintHaus",
                  fill=(105, 105, 115), font=font_sm, anchor="mm")

        # CTA 버튼 (펄스 컬러)
        btn_w, btn_h = 390, 74
        bx = cx - btn_w // 2
        by = H // 2 + 148
        draw.rounded_rectangle([(bx, by), (bx + btn_w, by + btn_h)],
                               radius=37, fill=accent)
        draw.text((cx, by + btn_h // 2), "SHOP THIS ITEM  →",
                  fill=(255, 255, 255), font=font_md, anchor="mm")

        frames.append(np.array(img, dtype=np.uint8))

    return frames


# ── 메인 ──

def generate_listing_video(product, output_path: str) -> Optional[str]:
    """
    목업 슬라이드 + 페이지 플립 + 카운트업 + 컬러 펄스 CTA → MP4 생성.

    영상 구조 (총 ~13초):
      [0] 페이지 플립 프리뷰   : 실제 플래너 페이지 스크린샷 (빠른 0.45초×N)
      [1] 목업 슬라이드 5장    : 전문 목업 (1.3초 × 5)
      [2] 숫자 카운트업        : 153+ Pages · 12 Months · 52 Weeks (1.0초)
      [3] 컬러 펄스 CTA        : 테마 색상 맥동 + INSTANT DOWNLOAD (1.5초)
    """
    try:
        import imageio.v3 as iio
        import numpy as np
    except ImportError:
        logger.warning("imageio[ffmpeg] 미설치 — 영상 생성 건너뜀. pip install imageio[ffmpeg]")
        return None

    if not product.file_paths:
        logger.warning("영상 생성 실패: file_paths 없음")
        return None

    zip_path    = Path(product.file_paths[0])
    product_dir = zip_path.parent
    style       = getattr(product, "style", "") or ""
    theme_rgb   = _get_theme_rgb(style)

    # ── [0] 페이지 플립 프리뷰 ──
    page_shots      = _find_page_screenshots(product_dir)
    page_flip_frames: list = []
    if page_shots:
        logger.info("페이지 플립: %d장 스크린샷 발견", len(page_shots))
        page_flip_frames = _build_frames(
            [str(p) for p in page_shots],
            page_dur=_FLIP_PAGE_DURATION,
            fade_f=_FLIP_FADE_FRAMES,
            end_hold_sec=0.0,
        )
    else:
        logger.info("페이지 플립: 스크린샷 없음 (목업만 사용)")

    # ── [1] 목업 슬라이드 ──
    slides = _collect_mockup_slides(product_dir)

    if len(slides) >= 3:
        logger.info("목업 슬라이드: %d장", len(slides))
        mockup_frames = _build_frames(
            slides,
            page_dur=_MOCKUP_PAGE_DURATION,
            fade_f=_MOCKUP_FADE_FRAMES,
            end_hold_sec=0.0,
        )
    else:
        # 폴백: HTML 페이지 캡처
        logger.info("목업 없음 — HTML 페이지 캡처 폴백")
        html_files = sorted(product_dir.glob("*.html"))
        if not html_files:
            logger.warning("영상 생성 실패: 목업도 HTML도 없음")
            return None
        screenshots = _capture_pages(html_files[0], product_dir)
        if not screenshots:
            logger.warning("영상 생성 실패: 스크린샷 없음")
            return None
        mockup_frames = _build_frames(screenshots, end_hold_sec=0.0)
        # 임시파일 정리
        for sp in screenshots:
            try:
                Path(sp).unlink(missing_ok=True)
            except Exception:
                pass

    if not mockup_frames:
        logger.warning("영상 생성 실패: 프레임 없음")
        return None

    # ── [2] 숫자 카운트업 ──
    stats_frames = _make_stats_frames(theme_rgb, style)

    # ── [3] 컬러 펄스 CTA ──
    cta_frames = _make_cta_pulse_frames(theme_rgb, style)

    # ── 전체 프레임 합산 ──
    all_frames = page_flip_frames + mockup_frames + stats_frames + cta_frames
    total_sec  = len(all_frames) / VIDEO_FPS

    if not all_frames:
        logger.warning("영상 생성 실패: 합산 프레임 없음")
        return None

    logger.info("영상 구조: 페이지플립 %d프레임 + 목업 %d프레임 + 스탯 %d프레임 + CTA %d프레임 = %.1f초",
                len(page_flip_frames), len(mockup_frames),
                len(stats_frames), len(cta_frames), total_sec)

    # Etsy 최대 15초 경고
    if total_sec > 15:
        logger.warning("⚠️ 영상 길이 %.1f초 > 15초 (Etsy 상한). 목업 슬라이드를 줄이는 것을 권장.", total_sec)

    # ── MP4 인코딩 ──
    try:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        iio.imwrite(
            str(output),
            all_frames,
            fps=VIDEO_FPS,
            codec="libx264",
            quality=8,
            pixelformat="yuv420p",
        )
        logger.info("영상 생성 완료: %s (%d프레임, %.1f초)",
                    output.name, len(all_frames), total_sec)
        return str(output)
    except Exception as e:
        logger.error("MP4 인코딩 실패: %s", e)
        return None


def _capture_pages(html_path: Path, tmp_dir: Path) -> list[str]:
    """Playwright로 플래너 HTML 주요 페이지 스크린샷 캡처 (폴백용)."""
    MAX_PAGES = 12
    PAGE_DURATION = 0.8
    FADE_FRAMES   = 6
    screenshots   = []
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("playwright 미설치")
        return []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT}
                )
                try:
                    page.goto(html_path.as_uri(), wait_until="networkidle", timeout=30000)
                except PWTimeout:
                    page.goto(html_path.as_uri(), timeout=30000)

                page_count = page.evaluate(
                    "() => document.querySelectorAll('.page').length"
                ) or 0

                if page_count <= MAX_PAGES:
                    indices = list(range(page_count))
                else:
                    step = page_count / MAX_PAGES
                    indices = [int(i * step) for i in range(MAX_PAGES)]

                pages_el = page.query_selector_all(".page")
                for idx in indices:
                    if idx >= len(pages_el):
                        break
                    try:
                        shot_path = str(tmp_dir / f"_video_frame_{idx:03d}.png")
                        pages_el[idx].screenshot(path=shot_path, timeout=10000)
                        screenshots.append(shot_path)
                    except PWTimeout:
                        logger.debug("페이지 %d 타임아웃, 건너뜀", idx)
                    except Exception as e:
                        logger.debug("페이지 %d 실패: %s", idx, e)
            finally:
                browser.close()  # 예외 발생 시에도 반드시 브라우저 종료
    except Exception as e:
        logger.error("Playwright 스크린샷 실패: %s", e)

    return screenshots
