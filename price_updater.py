# -*- coding: utf-8 -*-
"""
price_updater.py — 리뷰 수 기반 기존 리스팅 가격 자동 인상.

Windows Task Scheduler가 매일 1회 실행:
    python price_updater.py

수동 실행:
    python price_updater.py          # 가격 업데이트 실행
    python price_updater.py --dry    # 실제 변경 없이 미리보기
"""
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"price_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("price_updater")

sys.path.insert(0, str(Path(__file__).parent))


def _detect_niche(title: str, tags: list[str]) -> str | None:
    """리스팅 타이틀/태그에서 니치 감지.
    더블니치(sobriety_mom 등)를 단일니치보다 먼저 검사 — 긴 것 우선.
    Why: 단순 순회 시 ADHD가 ADHD_teacher보다 먼저 매칭되어 가격 오적용.
    """
    text = (title + " " + " ".join(tags or [])).lower()
    # 더블니치 먼저 (단일니치 오매칭 방지)
    niche_keywords = {
        "sobriety_mom":     ["sober mom", "recovery mom", "sobriety mom", "sobriety for moms"],
        "ADHD_teacher":     ["adhd teacher", "adhd classroom", "neurodivergent teacher"],
        "ADHD_nurse":       ["adhd nurse", "adhd nursing", "neurodivergent nurse"],
        "christian_teacher":["christian teacher", "faith teacher", "christian classroom", "scripture teacher"],
        # 단일니치
        "ADHD":        ["adhd", "executive function", "neurodivergent", "dopamine"],
        "anxiety":     ["anxiety", "calm", "grounding", "stress relief", "mental health"],
        "christian":   ["christian", "faith", "prayer", "scripture", "bible"],
        "sobriety":    ["sobriety", "sober", "recovery", "aa planner", "clean and sober"],
        "mom":         ["mom", "mommy", "family planner", "busy mom"],
        "homeschool":  ["homeschool", "curriculum", "unschool"],
        "self_care":   ["self care", "self-care", "wellness", "glow up", "self love"],
        "nurse":       ["nurse", "nursing", "rn planner", "healthcare", "shift planner"],
        "teacher":     ["teacher", "lesson plan", "classroom", "educator"],
        "pregnancy":   ["pregnancy", "prenatal", "bump", "baby shower", "maternity"],
        "entrepreneur":["entrepreneur", "boss", "side hustle", "ceo planner", "hustle"],
        "perimenopause":["perimenopause", "menopause", "hormone", "midlife"],
        "glp1":        ["glp-1", "glp1", "ozempic", "wegovy", "semaglutide", "weight loss shot"],
        "cycle_syncing":["cycle syncing", "cycle sync", "hormone cycle", "seed cycling"],
        "caregiver":   ["caregiver", "caregiving", "caring for", "eldercare"],
    }
    for niche, keywords in niche_keywords.items():
        if any(kw in text for kw in keywords):
            return niche
    return None


def _get_target_price(niche: str | None, listing_reviews: int) -> float | None:
    """리뷰 수 + 니치 기반 목표 가격 반환.
    더블니치(sobriety_mom 등) → 구성 단일니치 중 높은 가격 적용.
    pricing에 없는 니치 → generic(None) fallback.
    """
    from config.settings import PRICING
    niche_prices = PRICING.get("planner_niche_price", {})
    review_tiers = PRICING.get("planner_review_tiers", {})

    # 더블니치 분해: sobriety_mom → ["sobriety", "mom"] 중 높은 가격
    _DOUBLE_NICHE_PARTS = {
        "sobriety_mom":     ["sobriety", "mom"],
        "ADHD_teacher":     ["ADHD", "teacher"],
        "ADHD_nurse":       ["ADHD", "nurse"],
        "christian_teacher":["christian", "teacher"],
    }
    if niche in _DOUBLE_NICHE_PARTS:
        # 구성 니치별 가격 계산 후 최댓값 사용
        candidates = []
        for part in _DOUBLE_NICHE_PARTS[niche]:
            tp = niche_prices.get(part)
            if tp:
                candidates.append(tp)
        tier_prices = max(candidates, key=lambda d: d.get("premium", 0)) if candidates else {}
    else:
        tier_prices = niche_prices.get(niche) or niche_prices.get(None) or {}
    if not tier_prices:
        return None

    tier = "launch"
    for tier_name, min_reviews in sorted(review_tiers.items(), key=lambda x: x[1]):
        if listing_reviews >= min_reviews:
            tier = tier_name

    return tier_prices.get(tier)


def run(dry: bool = False) -> int:
    """전체 활성 리스팅 가격 검토 후 필요 시 인상. 업데이트 수 반환.

    가격 기준: 리스팅 개별 리뷰 수 (샵 전체 아님).
    Why: 리뷰 없는 신규 리스팅은 launch 가격 유지,
         리뷰 쌓인 리스팅만 선별적으로 인상 → 신뢰도/전환율 모두 최적화.
    """
    try:
        from config.settings import ETSY_SHOP_ID
        from publisher.etsy_api import (
            get_shop_id, get_all_active_listings,
            get_listing_review_count, update_listing_price,
        )
    except ImportError as e:
        logger.error("임포트 실패: %s", e)
        return 0

    shop_id = ETSY_SHOP_ID or get_shop_id()
    if not shop_id:
        logger.error("ETSY_SHOP_ID 미설정")
        return 0

    listings = get_all_active_listings(shop_id)
    if not listings:
        logger.info("활성 리스팅 없음")
        return 0

    logger.info("활성 리스팅 %d개 가격 검토 시작 (리스팅별 개별 리뷰 기준)", len(listings))
    updated = 0
    skipped_no_reviews  = 0
    skipped_already_max = 0
    skipped_api_err     = 0

    for listing in listings:
        listing_id    = str(listing.get("listing_id") or "")
        if not listing_id:
            continue  # listing_id 없는 항목 무시
        title         = listing.get("title", "")
        current_price = float(listing.get("price", {}).get("amount", 0) or
                              listing.get("price", 0) or 0)
        tags          = listing.get("tags", [])

        # 리스팅 개별 리뷰 수 조회
        listing_reviews = get_listing_review_count(listing_id)
        if listing_reviews < 0:
            logger.warning("  ⚠️ 리뷰 조회 실패, 건너뜀: %s", title[:45])
            skipped_api_err += 1
            continue

        if listing_reviews == 0:
            skipped_no_reviews += 1
            continue  # 리뷰 0개 = launch 가격 유지, 손대지 않음

        niche  = _detect_niche(title, tags)
        target = _get_target_price(niche, listing_reviews)

        if target is None:
            continue

        # 목표가가 현재가보다 높을 때만 인상 (절대 내리지 않음)
        if target <= current_price:
            skipped_already_max += 1
            continue

        niche_label = niche or "generic"
        if dry:
            logger.info("  [DRY] %s | %s | 리뷰 %d개 → $%.2f (현재 $%.2f)",
                        title[:45], niche_label, listing_reviews, target, current_price)
            updated += 1
        else:
            if update_listing_price(shop_id, listing_id, target):
                logger.info("  ✅ 인상: %s | %s | 리뷰 %d개 | $%.2f → $%.2f",
                            title[:45], niche_label, listing_reviews, current_price, target)
                updated += 1
            else:
                logger.warning("  ⚠️ 실패: %s", title[:45])

    action = "예정" if dry else "완료"
    logger.info("")
    logger.info("=" * 55)
    logger.info("  가격 인상 %s", action)
    logger.info("  전체 리스팅: %d개", len(listings))
    logger.info("  리뷰 0개 (유지): %d개", skipped_no_reviews)
    logger.info("  이미 최적가 (스킵): %d개", skipped_already_max)
    logger.info("  API 오류 (건너뜀): %d개", skipped_api_err)
    logger.info("  가격 인상 %s: %d개", action, updated)
    logger.info("=" * 55)
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="리뷰 기반 리스팅 가격 자동 인상")
    parser.add_argument("--dry", action="store_true", help="미리보기만 (실제 변경 없음)")
    args = parser.parse_args()
    run(dry=args.dry)
