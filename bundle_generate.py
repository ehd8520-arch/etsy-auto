# -*- coding: utf-8 -*-
"""
bundle_generate.py — 번들 자동 생성 + Etsy 발행.

번들 = daily + weekly + habit_tracker × 같은 niche × 같은 theme
3개 단품이 모두 published에 있을 때만 번들 후보로 선정.
기존 단품 파일(ZIP)을 그대로 묶어 업로드 → Etsy 최대 5개 파일 지원.

사용법:
    python bundle_generate.py --list             # 번들 후보 목록 출력
    python bundle_generate.py --count 3          # 번들 3개 생성 (발행 안 함)
    python bundle_generate.py --count 3 --publish # 생성 + Etsy 발행
    python bundle_generate.py --mock             # 이미지 API 없이 테스트
"""
import sys
import json
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("bundle_generate")

sys.path.insert(0, str(Path(__file__).parent))

from daily_generate import (
    PLANNER_THEMES, PLANNER_NICHES, PROGRESS_FILE,
    _load_progress, _save_progress, _backup_progress,
    _notify, _combo_key,
)

BUNDLE_TYPES = ["daily", "weekly", "habit_tracker"]
BUNDLE_DIR   = Path(__file__).parent / "output" / "bundles"


# ── 테마별 primary 색상 (번들 배지용) ──
_THEME_COLORS: dict[str, str] = {
    "sage_green":   "#6B8F71",
    "pastel_pink":  "#FB6F92",
    "lavender":     "#7B6BA0",
    "warm_beige":   "#8B7355",
    "ocean_blue":   "#3A6B8C",
    "dark_elegant": "#C9A84C",
    "minimal_mono": "#1A1A1A",
    "terracotta":   "#C4714A",
    "forest_green": "#2D5A27",
    "coral_peach":  "#E8614A",
}

# ── 니치별 번들 SEO 표현 ──
_NICHE_BUNDLE_PHRASE: dict[str | None, str] = {
    None:               "Printable Planner",
    "ADHD":             "ADHD Planner",
    "anxiety":          "Anxiety Relief Planner",
    "christian":        "Christian Planner",
    "sobriety":         "Sobriety Planner",
    "ADHD_teacher":     "ADHD Teacher Planner",
    "ADHD_nurse":       "ADHD Nurse Planner",
    "christian_teacher":"Christian Teacher Planner",
    "sobriety_mom":     "Sobriety Mom Planner",
    "mom":              "Mom Planner",
    "homeschool":       "Homeschool Planner",
    "self_care":        "Self Care Planner",
    "nurse":            "Nurse Planner",
    "teacher":          "Teacher Planner",
    "pregnancy":        "Pregnancy Planner",
    "entrepreneur":     "Entrepreneur Planner",
    "perimenopause":    "Perimenopause Planner",
    "cycle_syncing":    "Cycle Syncing Planner",
    "caregiver":        "Caregiver Planner",
    "glp1":             "GLP-1 Wellness Planner",
}


def _bundle_key(theme: str, niche: str | None) -> str:
    niche_key = niche or "generic"
    return f"bundle_{theme}_{niche_key}"


def find_bundle_candidates(progress: dict) -> list[dict]:
    """published에서 3개 타입(daily+weekly+habit_tracker) 모두 완료된 niche+theme 반환."""
    published    = set(progress.get("published", []))
    bundle_done  = set(progress.get("bundle_published", []))
    candidates   = []
    for theme in PLANNER_THEMES:
        for niche in PLANNER_NICHES:
            niche_key  = niche or "generic"
            bkey       = _bundle_key(theme, niche)
            if bkey in bundle_done:
                continue
            required = [f"{bt}_{theme}_{niche_key}" for bt in BUNDLE_TYPES]
            if all(k in published for k in required):
                candidates.append({"theme": theme, "niche": niche})
    return candidates


def _get_combo_output_dir(planner_type: str, theme: str, niche: str | None) -> Optional[Path]:
    """단품 output 폴더 추론 (output/{id}/ 형태 — combo_ids 참조)."""
    niche_key = niche or "generic"
    combo_key = f"{planner_type}_{theme}_{niche_key}"
    progress  = _load_progress()
    product_id = progress.get("combo_ids", {}).get(combo_key)
    if product_id:
        candidate = Path(__file__).parent / "output" / product_id
        if candidate.exists():
            return candidate
    # combo_ids 없으면 output/ 안에서 패턴 검색
    output_root = Path(__file__).parent / "output"
    pattern = f"{planner_type}_{theme}_{niche_key}"
    for d in sorted(output_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir() and pattern in d.name:
            return d
    return None


def _find_zip(output_dir: Path) -> Optional[Path]:
    """output 디렉터리에서 ZIP 파일 첫 번째 반환."""
    zips = sorted(output_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


def _find_hero_mockup(output_dir: Path) -> Optional[Path]:
    """output/mockups/01_hero.jpg 경로 반환."""
    candidates = [
        output_dir / "mockups" / "01_hero.jpg",
        output_dir / "01_hero.jpg",
    ]
    for c in candidates:
        if c.exists():
            return c
    imgs = sorted(output_dir.glob("mockups/0*.jpg"))
    return imgs[0] if imgs else None


def _generate_bundle_hero_mockup(
    theme: str,
    niche: str | None,
    hero_paths: list[Path],
    output_dir: Path,
) -> Optional[Path]:
    """
    3개 히어로 이미지 → 3-panel 1500×1500 번들 목업 합성.
    상단: "3-PLANNER BUNDLE" 배지
    우상단: "SAVE 25%" 원형 배지 (테마 primary 색)
    하단: "Daily · Weekly · Habit Tracker" 라벨
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow 없음 — 번들 히어로 목업 건너뜀")
        return None

    try:
        SIZE       = 1500
        PANEL_W    = SIZE // 3
        panel_imgs = []
        for hp in hero_paths[:3]:
            img = Image.open(str(hp)).convert("RGB").resize((PANEL_W, SIZE))
            panel_imgs.append(img)
        while len(panel_imgs) < 3:
            panel_imgs.append(Image.new("RGB", (PANEL_W, SIZE), "#EEEEEE"))

        canvas = Image.new("RGB", (SIZE, SIZE), "#FFFFFF")
        for i, img in enumerate(panel_imgs):
            canvas.paste(img, (i * PANEL_W, 0))

        draw        = ImageDraw.Draw(canvas)
        theme_color = _THEME_COLORS.get(theme, "#6B8F71")

        # ── 상단 배너 ──
        banner_h = 90
        draw.rectangle([(0, 0), (SIZE, banner_h)], fill=theme_color)
        try:
            font_lg = ImageFont.truetype("arial.ttf", 48)
            font_sm = ImageFont.truetype("arial.ttf", 32)
        except Exception:
            font_lg = ImageFont.load_default()
            font_sm = font_lg
        draw.text((SIZE // 2, banner_h // 2), "3-PLANNER BUNDLE",
                  fill="#FFFFFF", font=font_lg, anchor="mm")

        # ── 우상단 원형 배지 ──
        badge_r  = 80
        badge_cx = SIZE - badge_r - 20
        badge_cy = banner_h + badge_r + 20
        draw.ellipse(
            [(badge_cx - badge_r, badge_cy - badge_r),
             (badge_cx + badge_r, badge_cy + badge_r)],
            fill=theme_color,
        )
        draw.text((badge_cx, badge_cy), "SAVE\n25%",
                  fill="#FFFFFF", font=font_sm, anchor="mm", align="center")

        # ── 하단 라벨 ──
        label_h = 70
        draw.rectangle([(0, SIZE - label_h), (SIZE, SIZE)], fill="#F8F8F8")
        draw.text((SIZE // 2, SIZE - label_h // 2),
                  "Daily  ·  Weekly  ·  Habit Tracker",
                  fill="#333333", font=font_sm, anchor="mm")

        # 패널 구분선
        for i in (1, 2):
            x = i * PANEL_W
            draw.line([(x, banner_h), (x, SIZE - label_h)], fill="#DDDDDD", width=2)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "01_hero.jpg"
        canvas.save(str(out_path), "JPEG", quality=92)
        logger.info("번들 히어로 목업 생성: %s", out_path.name)
        return out_path
    except Exception as e:
        logger.warning("번들 히어로 목업 생성 실패: %s", e)
        return None


def _build_bundle_seo(theme: str, niche: str | None, price: float) -> dict:
    """번들 SEO — Groq 호출 없이 템플릿 기반."""
    niche_phrase = _NICHE_BUNDLE_PHRASE.get(niche, "Printable Planner")
    title = (
        f"{niche_phrase} Bundle PDF | 3 Printable Planners: "
        f"Daily, Weekly & Habit Tracker | Instant Download"
    )[:140]

    tags = [
        "planner bundle printable",
        "digital planner bundle",
        "printable planner set",
        "daily planner printable",
        "weekly planner printable",
        "habit tracker printable",
        "planner pdf download",
        "instant download planner",
        "planner bundle pdf",
    ]
    if niche:
        niche_clean = niche.replace("_", " ").lower()
        tags.append(f"{niche_clean} planner")
        tags.append(f"{niche_clean} gift idea")
    tags = [t[:20] for t in tags][:13]

    description = (
        f"★ 3-PLANNER BUNDLE — Save 25% vs. buying individually ★\n\n"
        f"This bundle includes THREE complete printable planners in one download:\n"
        f"✅ Daily Planner (153 pages)\n"
        f"✅ Weekly Planner (153 pages)\n"
        f"✅ Habit Tracker (153 pages)\n\n"
        f"Perfect for {(niche or 'everyone').replace('_', ' ')} — "
        f"undated format works year-round.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 INSTANT DOWNLOAD — 3 ZIP files delivered immediately\n"
        f"🖨️ Print at home or at any print shop\n"
        f"📐 Available in A4 + US Letter sizes\n"
        f"♾️ Print unlimited copies for personal use\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Questions? Message us anytime — we respond within 24 hours!"
    )

    return {"title": title, "tags": tags, "description": description, "price": price}


def _get_bundle_price(niche: str | None, shop_id: str) -> float:
    """리뷰 수 기반 번들 가격 티어 자동 결정."""
    try:
        from config.settings import PRICING
        from publisher.etsy_api import get_shop_reviews, get_active_listing_count
        bundle_prices = PRICING.get("bundle", {})
        review_tiers  = PRICING.get("planner_review_tiers", {})
        total_reviews = get_shop_reviews(shop_id) or 0

        tier = "launch"
        for tier_name, min_reviews in sorted(review_tiers.items(), key=lambda x: x[1]):
            if total_reviews >= min_reviews:
                tier = tier_name

        price = bundle_prices.get(tier, bundle_prices.get("launch", 17.97))
        logger.info("번들 가격 티어: [%s] = $%.2f (리뷰 %d개)", tier, price, total_reviews)
        return price
    except Exception as e:
        logger.warning("번들 가격 결정 실패, 기본값 사용: %s", e)
        return 17.97


def mark_bundle_published(theme: str, niche: str | None, listing_id: str = ""):
    """번들 발행 완료 기록."""
    progress = _load_progress()
    progress.setdefault("bundle_published", [])
    bkey = _bundle_key(theme, niche)
    if bkey not in progress["bundle_published"]:
        progress["bundle_published"].append(bkey)
    if listing_id:
        progress.setdefault("bundle_listing_ids", {})[bkey] = listing_id
    _save_progress(progress)
    _backup_progress()


def generate_bundle(candidate: dict, publish: bool = False,
                    shop_id: str = "") -> bool:
    """번들 1개 생성 + (선택) Etsy 발행."""
    theme = candidate["theme"]
    niche = candidate["niche"]
    niche_key = niche or "generic"
    bkey  = _bundle_key(theme, niche)
    logger.info("━" * 50)
    logger.info("번들 생성: %s × %s", theme, niche_key)

    bundle_out = BUNDLE_DIR / bkey
    bundle_out.mkdir(parents=True, exist_ok=True)

    # ── 단품 파일(ZIP) + 히어로 이미지 수집 ──
    zip_paths  = []
    hero_paths = []
    for bt in BUNDLE_TYPES:
        odir = _get_combo_output_dir(bt, theme, niche)
        if not odir:
            logger.warning("단품 output 없음: %s_%s_%s — 건너뜀", bt, theme, niche_key)
            return False
        zp = _find_zip(odir)
        if zp:
            zip_paths.append(zp)
        hp = _find_hero_mockup(odir)
        if hp:
            hero_paths.append(hp)

    if len(zip_paths) < len(BUNDLE_TYPES):
        logger.warning("ZIP 파일 %d개 (필요: %d) — 번들 건너뜀", len(zip_paths), len(BUNDLE_TYPES))
        return False

    # ── 번들 히어로 목업 생성 ──
    mockup_dir  = bundle_out / "mockups"
    hero_out    = _generate_bundle_hero_mockup(theme, niche, hero_paths, mockup_dir)

    # 단품 목업들 복사 (02~05번 — Etsy 이미지 슬롯 채우기)
    import shutil
    extra_mockups: list[Path] = []
    for bt in BUNDLE_TYPES:
        odir = _get_combo_output_dir(bt, theme, niche)
        if not odir:
            continue
        for rank, mock_name in enumerate(["03_detail.jpg", "05_whats_included.jpg",
                                          "09_social_proof.jpg"], start=2):
            src = odir / "mockups" / mock_name
            if src.exists():
                dst = mockup_dir / f"{bt}_{mock_name}"
                shutil.copy2(str(src), str(dst))
                extra_mockups.append(dst)
                break  # 타입당 1장만

    mockup_paths = []
    if hero_out and hero_out.exists():
        mockup_paths.append(hero_out)
    mockup_paths.extend(extra_mockups[:9])  # Etsy 최대 10장

    if not publish:
        logger.info("✅ 번들 생성 완료 (미발행): %s", bkey)
        logger.info("   ZIP: %s", ", ".join(p.name for p in zip_paths))
        return True

    # ── Etsy 발행 ──
    if not shop_id:
        logger.error("shop_id 없음 — 번들 발행 불가")
        return False

    price = _get_bundle_price(niche, shop_id)
    seo   = _build_bundle_seo(theme, niche, price)

    try:
        from publisher.etsy_api import (
            create_draft_listing, upload_listing_image,
            upload_listing_file, activate_listing,
        )

        listing_id = create_draft_listing(
            shop_id=shop_id,
            title=seo["title"],
            description=seo["description"],
            price=seo["price"],
            tags=seo["tags"],
            style=f"bundle_{theme}_{niche_key}",
        )
        if not listing_id:
            logger.error("번들 드래프트 생성 실패: %s", bkey)
            return False

        # 이미지 업로드
        for rank, mp in enumerate(mockup_paths[:10], start=1):
            upload_listing_image(shop_id, listing_id, str(mp), rank)

        # ZIP 파일 업로드 (Etsy 최대 5개)
        for zp in zip_paths[:5]:
            upload_listing_file(shop_id, listing_id, str(zp), zp.name)

        # 즉시 활성화
        if activate_listing(shop_id, listing_id):
            logger.info("🚀 번들 발행 완료: %s (listing_id=%s)", bkey, listing_id)
            mark_bundle_published(theme, niche, listing_id)
            return True
        else:
            logger.error("번들 활성화 실패: %s", bkey)
            return False
    except Exception as e:
        logger.error("번들 발행 예외: %s — %s", bkey, e)
        return False


def main():
    parser = argparse.ArgumentParser(description="번들 자동 생성 + Etsy 발행")
    parser.add_argument("--list",    action="store_true", help="번들 후보 목록 출력 후 종료")
    parser.add_argument("--count",   type=int, default=1,  help="생성할 번들 수 (기본: 1)")
    parser.add_argument("--publish", action="store_true",  help="Etsy 실제 발행")
    parser.add_argument("--mock",    action="store_true",  help="API 없이 테스트")
    args = parser.parse_args()

    if args.mock:
        os.environ["WALL_ART_MOCK"] = "true"

    progress   = _load_progress()
    candidates = find_bundle_candidates(progress)

    if args.list:
        logger.info("번들 후보: %d개", len(candidates))
        for c in candidates:
            logger.info("  - %s × %s", c["theme"], c["niche"] or "generic")
        published_n = len(progress.get("bundle_published", []))
        logger.info("번들 발행 완료: %d개", published_n)
        return

    if not candidates:
        logger.info("번들 후보 없음. daily+weekly+habit_tracker 3개 타입이 같은 theme×niche로 발행 완료되어야 합니다.")
        return

    shop_id = ""
    if args.publish:
        try:
            from config.settings import ETSY_SHOP_ID
            from publisher.etsy_api import get_shop_id
            shop_id = ETSY_SHOP_ID or get_shop_id() or ""
        except Exception as e:
            logger.error("shop_id 조회 실패: %s", e)
            return
        if not shop_id:
            logger.error("ETSY_SHOP_ID 미설정 — 발행 불가")
            return

    targets   = candidates[:args.count]
    successes = 0
    for candidate in targets:
        if generate_bundle(candidate, publish=args.publish, shop_id=shop_id):
            successes += 1

    logger.info("번들 완료: %d/%d", successes, len(targets))
    if successes:
        _notify(f"📦 번들 생성 완료 | {successes}개 {'발행' if args.publish else '생성(미발행)'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as _e:
        logger.exception("❌ 치명적 오류: %s", _e)
        raise
