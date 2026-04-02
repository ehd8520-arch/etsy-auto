# -*- coding: utf-8 -*-
"""
daily_generate.py — 플래너 하루 N개 자동 생성 (중복 없는 로테이션).

사용법:
    python daily_generate.py              # 오늘 치 3개 생성 (기본)
    python daily_generate.py --count 5   # 5개 생성
    python daily_generate.py --mock      # 이미지 없이 빠른 테스트
    python daily_generate.py --list      # 남은 조합 목록 출력
    python daily_generate.py --reset     # 진행 상태 초기화

생성 순서: 모든 (type x theme x niche) 1600조합 소진 후 stale pruner 삭제분만 v2 재발행.
1600개 완료 후 중복 발행 없음 — Etsy 패널티 방지.
우선순위: 수요 높은 타입 먼저 (daily > weekly > ...), 니치는 수요폭발+경쟁낮음 우선
"""
import sys
import json
import os
import random
import argparse
import logging
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("daily_generate")

sys.path.insert(0, str(Path(__file__).parent))

# ── 조합 정의 ──
# 타입 순서 = Etsy 검색 수요 우선순위 (eRank 기준)
PLANNER_TYPES = [
    "daily",         # 최고 수요 — "daily planner printable" 검색량 1위
    "weekly",        # 2위 — 월간보다 주간 선호
    "habit_tracker", # 3위 — 자기계발 붐
    "goal_setting",  # 4위 — 연초/분기마다 수요 급등
    "budget",        # 5위 — 재정 플래너 꾸준한 수요
    "fitness",       # 6위 — 신년 목표 시즌에 급등
    "gratitude",     # 7위 — 마인드풀니스 니치
    "meal",          # 8위 — 다이어트 시즌 수요
]

# 테마 순서 = Etsy 인기 스타일 × 니치 매칭 우선순위
# 각 테마는 폰트/헤더/배경/체크박스/라인이 모두 다름 → 진짜 다른 디자인
PLANNER_THEMES = [
    "sage_green",    # Calm Nature    — Quicksand, gradient pill, 점선 배경
    "pastel_pink",   # Romantic Bloom — Playfair, gradient pill, 점선 배경
    "lavender",      # Dream Purple   — Raleway, minimal line, 원형 체크박스
    "warm_beige",    # Cozy Boho      — Lora serif, side accent, 실선
    "ocean_blue",    # Ocean Pro      — Poppins, flat block, 격자 배경
    "dark_elegant",  # Dark Luxury    — Cormorant, dark card, 다이아 체크박스
    "minimal_mono",  # Ultra Minimal  — Inter, minimal line, 격자 배경
    "terracotta",    # Earthy Warmth  — Josefin Sans, gradient pill, 사선 배경
    "forest_green",  # Forest Faith   — Merriweather serif, flat block
    "coral_peach",   # Sunrise Energy — Nunito bold, side accent, 원형 체크박스
]

# 니치 순서 = 수요 폭발 × 경쟁 낮음 우선
PLANNER_NICHES = [
    None,              # generic        — 최대 수요, 최고 경쟁
    "ADHD",            # 수요 폭발      + 경쟁 낮음 ★★★
    "anxiety",         # 수요 폭발      + 경쟁 낮음 ★★★
    "christian",       # 수요 높음      + 경쟁 낮음 ★★★
    "sobriety",        # 수요 급성장    + 경쟁 낮음 ★★★
    "ADHD_teacher",    # 더블니치       + 경쟁 극소 ★★★
    "ADHD_nurse",      # 더블니치       + 경쟁 극소 ★★★
    "christian_teacher",# 더블니치      + 경쟁 극소 ★★★
    "sobriety_mom",    # 더블니치       + 경쟁 극소 ★★★
    "mom",             # 수요 폭발      + 경쟁 중간 ★★
    "homeschool",      # 수요 폭발      + 경쟁 중간 ★★
    "self_care",       # 수요 폭발      + 경쟁 중간 ★★
    "nurse",           # 수요 중간      + 경쟁 낮음 ★★
    "teacher",         # 수요 중간      + 경쟁 낮음 ★★
    "pregnancy",       # 수요 높음      + 경쟁 낮음 ★★
    "entrepreneur",    # 수요 높음      + 경쟁 중간 ★★
    "perimenopause",   # 2025 신규폭발  + 경쟁 거의없음 ★★★
    "cycle_syncing",   # 2025 신규폭발  + 경쟁 거의없음 ★★★
    "caregiver",       # 수요 확인      + 경쟁 거의없음 ★★★
    "glp1",            # 2024 트렌드    + 경쟁 거의없음 ★★★
]

# 전체 조합 = 8 types x 10 themes x 20 niches = 1600개
ALL_COMBINATIONS = [
    {"planner_type": pt, "theme_name": th, "niche": ni}
    for pt in PLANNER_TYPES
    for th in PLANNER_THEMES
    for ni in PLANNER_NICHES
]

PROGRESS_FILE = Path(__file__).parent / "daily_progress.json"
LOCK_FILE     = Path(__file__).parent / "daily_generate.lock"
BACKUP_DIR    = Path(__file__).parent / "backups"


def _cleanup_old_logs(max_days: int = 7) -> None:
    """7일 이상 된 로그 파일 자동 삭제."""
    import time as _t
    cutoff = _t.time() - max_days * 86400
    for lf in LOG_DIR.glob("daily_*.log"):
        try:
            if lf.stat().st_mtime < cutoff:
                lf.unlink()
        except Exception:
            pass


def _notify(message: str, parse_mode: str = "HTML") -> None:
    """알림 전송 — Telegram 우선, Discord 폴백. 미설정 시 무음."""
    # Telegram (이미 .env에 설정됨 — 우선 사용)
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat  = os.environ.get("TELEGRAM_CHAT_ID", "")
    if tg_token and tg_chat:
        try:
            import requests as _req
            _req.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat, "text": message,
                      "parse_mode": parse_mode, "disable_web_page_preview": True},
                timeout=10,
            )
            return
        except Exception:
            pass
    # Discord 폴백
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if url:
        try:
            import requests as _req
            _req.post(url, json={"content": message}, timeout=10)
        except Exception:
            pass


def _acquire_lock() -> bool:
    """중복 실행 방지 락. 2시간 이상 된 락은 크래시 잔여물로 간주하고 덮어씀."""
    import time as _t
    if LOCK_FILE.exists():
        age = _t.time() - LOCK_FILE.stat().st_mtime
        if age < 7200:  # 2시간 미만 = 실행 중으로 판단
            return False
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def _release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def _backup_progress() -> None:
    """daily_progress.json 오늘 날짜 백업 (장애 복구용)."""
    if not PROGRESS_FILE.exists():
        return
    try:
        import shutil as _shutil
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dst = BACKUP_DIR / f"daily_progress_{datetime.now().strftime('%Y%m%d')}.bak"
        _shutil.copy2(str(PROGRESS_FILE), str(dst))
        # 30일 이상 된 백업 정리
        import time as _t
        cutoff = _t.time() - 30 * 86400
        for bf in BACKUP_DIR.glob("daily_progress_*.bak"):
            try:
                if bf.stat().st_mtime < cutoff:
                    bf.unlink()
            except Exception:
                pass
    except Exception as e:
        logger.warning("진행 백업 실패 (무시): %s", e)


def _load_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"published": [], "v2_published": [], "pruned_combos": [],
                "listing_ids": {}, "combo_ids": {}}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 구 포맷(completed 키) → 신 포맷 자동 마이그레이션
        if "completed" in data and "published" not in data:
            data["published"]     = data.pop("completed")
            data.setdefault("v2_published", [])
            data.setdefault("pruned_combos", [])
            data.setdefault("listing_ids", {})
            data.setdefault("combo_ids", {})
            data.pop("cycle", None)
        return data
    except Exception:
        return {"published": [], "v2_published": [], "pruned_combos": [],
                "listing_ids": {}, "combo_ids": {}}


def _save_progress(progress: dict):
    """원자적 쓰기: 임시 파일에 먼저 쓴 후 rename → 쓰기 도중 크래시해도 기존 파일 보존."""
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        tmp.replace(PROGRESS_FILE)
    except Exception as e:
        logger.warning("진행 상태 저장 실패: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _combo_key(combo: dict) -> str:
    niche = combo.get("niche") or "generic"
    return f"{combo['planner_type']}_{combo['theme_name']}_{niche}"


def _get_seasonal_boosts() -> list[dict]:
    """현재 월 기준 시즌 우선 조합 반환. 시즌 없으면 빈 리스트."""
    try:
        from config.settings import CATEGORY_EVENTS
    except ImportError:
        return []

    now = datetime.now()
    month = now.month
    boosted = []

    # CATEGORY_EVENTS["planner"] 에서 지금 리스팅해야 할 이벤트 찾기
    # list_by_month <= 현재월 < peak_month (또는 같은 달)
    for event in CATEGORY_EVENTS.get("planner", []):
        list_by = event.get("list_by_month", 0)
        peak    = event.get("peak_month", 0)

        # 리스팅 시작 월 ~ 피크 월 사이인지 확인 (연말→연초 경우 포함)
        if list_by <= peak:
            in_window = list_by <= month <= peak
        else:  # 연도 경계 (예: list_by=10, peak=1)
            in_window = month >= list_by or month <= peak

        if not in_window:
            continue

        planner_type = event.get("planner_type") or event.get("products", {}).get("planner")
        niche_hints  = event.get("niches", [None])  # 이벤트에 니치 힌트 있으면 사용

        for niche in niche_hints:
            for theme in PLANNER_THEMES[:2]:  # 인기 테마 2개만
                boosted.append({
                    "planner_type": planner_type or "daily",
                    "theme_name":   theme,
                    "niche":        niche,
                    "_season":      event["name"],
                })

    return boosted


def get_next_combos(count: int) -> list[dict]:
    """중복 없는 다음 N개 조합 반환.
    v1 완료 후에는 stale pruner가 삭제한 조합만 v2로 재발행 (Etsy 중복 패널티 방지).
    """
    progress = _load_progress()
    published_keys = set(progress.get("published", []))
    # listing_ids에 있는 조합 = Etsy에 드래프트 업로드 완료 → published 미기록이어도 재생성 금지
    drafted_keys = set(progress.get("listing_ids", {}).keys())

    # ── v1 미완료 조합 우선 ──
    remaining = [c for c in ALL_COMBINATIONS
                 if _combo_key(c) not in published_keys
                 and _combo_key(c) not in drafted_keys]

    if remaining:
        # 시즌 부스트: 아직 안 만든 시즌 조합을 앞으로 당김 (드래프트된 것도 제외)
        seasonal = [
            c for c in _get_seasonal_boosts()
            if _combo_key(c) not in published_keys
            and _combo_key(c) not in drafted_keys
        ]
        if seasonal:
            seasonal_keys = {_combo_key(c) for c in seasonal}
            remaining = seasonal + [c for c in remaining if _combo_key(c) not in seasonal_keys]
            logger.info("🗓️ 시즌 부스트 %d개 앞으로 우선배치", len(seasonal))
        return remaining[:count]

    # ── v1 전체 완료 → v2 후보 (stale pruner가 삭제한 조합 중 v2 미완료) ──
    v2_done   = set(progress.get("v2_published", []))
    pruned    = set(progress.get("pruned_combos", []))
    v2_candidates = [
        c for c in ALL_COMBINATIONS
        if _combo_key(c) in pruned and _combo_key(c) not in v2_done
    ]
    if v2_candidates:
        logger.info("🔄 v2 재발행 모드: %d개 후보 (stale pruner 삭제 분)", len(v2_candidates))
        return v2_candidates[:count]

    # ── 대기 ──
    logger.info("✅ 전체 1600개 발행 완료. stale pruner가 리스팅을 삭제하면 v2 자동 시작.")
    return []


def mark_published(combos: list[dict],
                   listing_ids: dict | None = None,
                   combo_product_ids: dict | None = None,
                   version: int = 1):
    """Etsy 발행 성공한 조합만 등록. 테스트 생성(--publish 없이)은 호출하지 않음."""
    progress = _load_progress()
    key_field = "published" if version == 1 else "v2_published"
    progress.setdefault(key_field, [])
    for combo in combos:
        key = _combo_key(combo)
        if key not in progress[key_field]:
            progress[key_field].append(key)
    if listing_ids:
        progress.setdefault("listing_ids", {}).update(listing_ids)
    if combo_product_ids:
        progress.setdefault("combo_ids", {}).update(combo_product_ids)
    _save_progress(progress)
    _backup_progress()


def print_status():
    progress = _load_progress()
    published = set(progress.get("published", []))
    v2_done   = set(progress.get("v2_published", []))
    pruned    = set(progress.get("pruned_combos", []))
    remaining = [c for c in ALL_COMBINATIONS if _combo_key(c) not in published]
    done = [c for c in ALL_COMBINATIONS if _combo_key(c) in published]

    logger.info("")
    logger.info("=" * 55)
    logger.info("  플래너 발행 현황")
    logger.info("=" * 55)
    total_combos = len(ALL_COMBINATIONS)
    pct = round(len(done) / total_combos * 100, 1) if total_combos else 0
    logger.info("  v1 발행: %d / %d  (%.1f%%)", len(done), total_combos, pct)
    logger.info("  v2 발행: %d개 (stale pruner 삭제 후 재발행)", len(v2_done))
    logger.info("  pruned:  %d개 (stale pruner 삭제됨)", len(pruned))
    logger.info("  남은 v1: %d개  (%.1f%% 남음)", len(remaining),
                round(len(remaining) / total_combos * 100, 1) if total_combos else 0)
    logger.info("")
    logger.info("  [v1 발행 완료]")
    for c in done:
        key = _combo_key(c)
        lid = progress.get("listing_ids", {}).get(key, "")
        suffix = f" (lid={lid})" if lid else ""
        logger.info("    ✅ %s × %s × %s%s",
                    c["planner_type"], c["theme_name"], c.get("niche") or "generic", suffix)
    logger.info("")
    logger.info("  [대기 중 — 다음 순서]")
    for i, c in enumerate(remaining[:20]):  # 최대 20개만 표시
        prefix = "  ▶ " if i == 0 else "    "
        logger.info("%s%s × %s × %s",
                    prefix, c["planner_type"], c["theme_name"], c.get("niche") or "generic")
    if len(remaining) > 20:
        logger.info("    ... 외 %d개", len(remaining) - 20)


def _generate_one(combo: dict) -> dict | None:
    """플래너 1개 생성 (PDF + 목업 + SEO). 성공 시 product/seo 반환."""
    try:
        from generator.planner_html import generate_planner_html
        from generator.mockup import generate_all_mockups
        from seo.generator import generate_seo

        product = generate_planner_html(
            planner_type=combo["planner_type"],
            theme_name=combo["theme_name"],
            niche=combo.get("niche"),
        )
        if not product:
            logger.error("생성 실패: %s × %s", combo["planner_type"], combo["theme_name"])
            return None

        product.mockup_paths = generate_all_mockups(product)

        # 리스팅 영상 생성 (실패해도 전체 흐름 중단 안 함)
        try:
            from generator.listing_video import generate_listing_video
            from pathlib import Path as _Path
            _video_out = str(_Path(product.file_paths[0]).parent / "listing_video.mp4") if product.file_paths else None
            if _video_out:
                product.video_path = generate_listing_video(product, _video_out) or ""
                if product.video_path:
                    logger.info("🎬 영상 생성 완료: %s", _Path(product.video_path).name)
        except Exception as _ve:
            logger.warning("영상 생성 실패 (건너뜀): %s", _ve)

        seo_result = generate_seo(product)

        # 가격은 main()에서 shop_id 확보 후 결정 — 여기선 임시값
        price = combo.get("_price", 2.97)

        from models import SEOData
        seo = SEOData(
            title=seo_result["title"],
            tags=seo_result["tags"],
            description=seo_result["description"],
            price_usd=price,
        )
        niche_tag = f"[{combo.get('niche')}] " if combo.get("niche") else ""
        logger.info("✅ 생성 완료: %s%s × %s — %s ($%.2f)",
                    niche_tag, combo["planner_type"], combo["theme_name"], seo.title[:50], price)
        return {"product": product, "seo": seo, "combo": combo}
    except Exception as e:
        logger.error("❌ 생성 예외: %s × %s — %s", combo["planner_type"], combo["theme_name"], e)
        return None


def _upload_draft(item: dict, shop_id: str) -> str | None:
    """상품을 Etsy 드래프트로 업로드. listing_id 반환."""
    try:
        from publisher.etsy_api import (
            create_draft_listing, upload_listing_image, upload_listing_file,
            upload_listing_video,
        )
        product, seo = item["product"], item["seo"]

        listing_id = create_draft_listing(
            shop_id=shop_id,
            title=seo.title,
            description=seo.description,
            price=seo.price_usd,
            tags=seo.tags,
            style=getattr(product, "style", ""),
        )
        if not listing_id:
            return None

        for rank, path in enumerate(product.mockup_paths[:10], start=1):
            upload_listing_image(shop_id, listing_id, path, rank)

        from pathlib import Path as _Path
        for fp in getattr(product, "file_paths", []):
            upload_listing_file(shop_id, listing_id, fp, _Path(fp).name)

        # 리스팅 영상 업로드 -- Etsy 디지털 리스팅은 video 미지원, 건너뜀

        logger.info("📝 드래프트 업로드 완료: listing_id=%s", listing_id)
        return listing_id
    except Exception as e:
        logger.error("❌ 드래프트 업로드 실패: %s", e)
        return None


def _activate(listing_id: str, shop_id: str) -> bool:
    """드래프트 → 활성 발행."""
    try:
        from publisher.etsy_api import activate_listing
        return activate_listing(shop_id, listing_id)
    except Exception as e:
        logger.error("❌ 활성화 실패 %s: %s", listing_id, e)
        return False


QUEUE_FILE = Path(__file__).parent / "publish_queue.json"

# ── 오토스케일 + 가격 자동 결정 ──
MAX_COUNT    = 10
MIN_INTERVAL = 2.0


def _get_shop_stats(shop_id: str) -> dict:
    """Etsy API로 샵 통계 조회. 실패 시 기본값 반환."""
    try:
        from publisher.etsy_api import get_shop_reviews, get_active_listing_count
        total_reviews  = get_shop_reviews(shop_id) or 0
        active_listings = get_active_listing_count(shop_id) or 1
        return {"reviews": total_reviews, "listings": active_listings}
    except Exception as e:
        logger.warning("샵 통계 조회 실패 (기본값 사용): %s", e)
        return {"reviews": 0, "listings": 1}


def _auto_count_interval(shop_id: str) -> tuple[int, float]:
    """샵 총 리뷰 수 기반 최적 생성 수 + 발행 간격 반환.
    리뷰가 쌓일수록 Etsy 신뢰도 상승 → 더 많이 발행해도 노출 유지.
    """
    stats         = _get_shop_stats(shop_id)
    total_reviews = stats["reviews"]

    if   total_reviews < 10:   count, interval = 4,  3.0
    elif total_reviews < 30:   count, interval = 6,  3.0
    elif total_reviews < 100:  count, interval = 8,  2.0
    else:                      count, interval = 10, 2.0

    count    = min(count, MAX_COUNT)
    interval = max(interval, MIN_INTERVAL)

    logger.info("📊 오토스케일: 총 리뷰 %d개 → %d개/일, %.1f시간 간격",
                total_reviews, count, interval)
    return count, interval


def _get_niche_price(niche: str | None, shop_id: str) -> float:
    """신규 리스팅 발행 시 초기 가격 결정 — 항상 launch 가격.
    Why: 신규 리스팅은 리뷰 0개 → launch 가격으로 전환율 극대화.
         리뷰 쌓인 후 가격 인상은 price_updater.py가 담당.
    더블니치(ADHD_teacher 등) → 구성 단일니치 중 높은 launch 가격 적용.
    """
    _DOUBLE_NICHE_PARTS = {
        "sobriety_mom":     ["sobriety", "mom"],
        "ADHD_teacher":     ["ADHD", "teacher"],
        "ADHD_nurse":       ["ADHD", "nurse"],
        "christian_teacher":["christian", "teacher"],
    }
    try:
        from config.settings import PRICING
        niche_prices = PRICING.get("planner_niche_price", {})

        if niche in _DOUBLE_NICHE_PARTS:
            candidates = [niche_prices[p] for p in _DOUBLE_NICHE_PARTS[niche] if p in niche_prices]
            tier_prices = max(candidates, key=lambda d: d.get("launch", 0)) if candidates else {}
        else:
            tier_prices = niche_prices.get(niche) or niche_prices.get(None) or {}

        price = tier_prices.get("launch", 2.97)
        logger.info("💰 신규 발행 가격: %s[launch] = $%.2f",
                    niche or "generic", price)
        return price
    except Exception as e:
        logger.warning("가격 결정 실패, 기본값 사용: %s", e)
        return 2.97


def _ensure_queue_scheduler():
    """매시간 activate_queue.py 실행 Task가 없으면 자동 등록 (Windows 전용)."""
    import platform
    if platform.system() != "Windows":
        logger.info("Task Scheduler 등록 건너뜀 (Windows 전용, 현재: %s)", platform.system())
        return
    import subprocess, sys as _sys
    task_name = "EtsyQueueActivate"
    check = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True, text=True
    )
    if check.returncode == 0:
        return  # 이미 등록됨
    queue_script = Path(__file__).parent / "activate_queue.py"
    cmd = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", f'"{_sys.executable}" "{queue_script}"',
        "/SC", "HOURLY", "/MO", "1", "/F",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("✅ Task Scheduler 자동 등록 완료 (매시간 큐 처리)")
    else:
        logger.warning("⚠️ Task Scheduler 등록 실패: %s", result.stderr.strip())


def _to_peak_utc(ts: float) -> float:
    """발행 타임스탬프를 US EST 피크타임(14~18 UTC = 오전 9~1시 EST)으로 조정.
    Why: Etsy 신규 리스팅은 미국 동부 오전에 노출될 때 초기 조회수 최대화.
    이미 피크 구간이면 그대로 반환, 아니면 다음 피크 시작(14:00 UTC)으로 이동.
    """
    from datetime import timezone, timedelta
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    h = dt.hour
    if 14 <= h < 18:
        return ts  # 이미 피크 구간
    if h < 14:
        target = dt.replace(hour=14, minute=0, second=0, microsecond=0)
    else:  # h >= 18 — 다음날 14:00 UTC
        target = (dt + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    return target.timestamp()


def _load_queue() -> list:
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_queue(queue: list):
    """원자적 쓰기: 임시 파일 → rename."""
    tmp = QUEUE_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        tmp.replace(QUEUE_FILE)
    except Exception as e:
        logger.warning("큐 저장 실패: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _append_queue(listing_id: str, shop_id: str, publish_at: str, label: str,
                  pinterest_info: dict | None = None):
    """발행 대기 큐에 추가. publish_at = ISO datetime 문자열.
    동일 listing_id가 이미 큐에 있으면 중복 추가하지 않음.
    """
    queue = _load_queue()
    # 중복 방지: 동일 listing_id가 이미 등록되어 있으면 스킵
    existing_ids = {e["listing_id"] for e in queue}
    if listing_id in existing_ids:
        logger.info("📋 큐 중복 스킵: %s (listing_id=%s 이미 등록됨)", label, listing_id)
        return
    entry: dict = {
        "listing_id": listing_id,
        "shop_id":    shop_id,
        "publish_at": publish_at,
        "label":      label,
        "done":       False,
    }
    if pinterest_info:
        entry["pinterest_info"] = pinterest_info
    queue.append(entry)
    _save_queue(queue)
    logger.info("📋 큐 등록: %s → %s 발행 예정", label, publish_at)


def _pin_to_pinterest(item: dict, listing_id: str, dry_run: bool = False) -> None:
    """Etsy 활성 리스팅을 Pinterest에 핀 발행. 실패해도 메인 흐름 중단 없음."""
    try:
        from publisher.pinterest import pin_listing
        product = item["product"]
        seo     = item["seo"]
        combo   = item["combo"]
        image_path = (getattr(product, "mockup_paths", []) or [None])[0]
        if not image_path:
            logger.warning("Pinterest 핀 건너뜀 (목업 없음): listing_id=%s", listing_id)
            return
        etsy_url = f"https://www.etsy.com/listing/{listing_id}"
        result = pin_listing(
            listing_id    = listing_id,
            listing_title = seo.title,
            image_path    = image_path,
            etsy_url      = etsy_url,
            niche         = combo.get("niche"),
            seo_tags      = getattr(seo, "tags", []),
            dry_run       = dry_run,
        )
        status = result.get("status", "error")
        if status == "success":
            logger.info("📌 Pinterest 핀 완료: listing_id=%s pin_id=%s",
                        listing_id, result.get("pin_id"))
        elif status == "duplicate":
            logger.info("📌 Pinterest 중복 건너뜀: listing_id=%s", listing_id)
        else:
            logger.warning("📌 Pinterest 핀 상태=%s: listing_id=%s", status, listing_id)
    except Exception as e:
        logger.warning("Pinterest 핀 실패 (건너뜀, 메인 흐름 유지): %s", e)


def main():
    parser = argparse.ArgumentParser(
        description="플래너 일일 자동 생성 — 1개 즉시 발행, 나머지 N시간 간격 예약 드래프트"
    )
    parser.add_argument("--count",    type=int,   default=4,   help="오늘 생성할 개수 (기본: 4)")
    parser.add_argument("--interval", type=float, default=3.0, help="발행 간격 시간 (기본: 3시간)")
    parser.add_argument("--publish",  action="store_true",     help="Etsy 실제 업로드 (없으면 생성만)")
    parser.add_argument("--mock",     action="store_true",     help="이미지 API 없이 테스트 (비용 $0)")
    parser.add_argument("--list",     action="store_true",     help="남은 조합 목록 출력 후 종료")
    parser.add_argument("--reset",    action="store_true",     help="진행 상태 초기화")
    parser.add_argument("--preview",       action="store_true", help="최근 미리보기 HTML 브라우저로 오픈")
    parser.add_argument("--no-pinterest",  action="store_true", help="Pinterest 핀 발행 건너뜀")
    args = parser.parse_args()

    if args.preview:
        previews = sorted(Path(__file__).parent.glob("preview_*.html"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        if previews:
            import platform as _plat, subprocess as _sub
            path_str = str(previews[0].resolve())
            if _plat.system() == "Windows":
                import os as _os
                _os.startfile(path_str)
            elif _plat.system() == "Darwin":
                _sub.Popen(["open", path_str])
            else:
                _sub.Popen(["xdg-open", path_str])
            logger.info("미리보기 오픈: %s", previews[0].name)
        else:
            logger.warning("미리보기 파일 없음. 먼저 daily_generate.py 를 실행하세요.")
        return

    # 중복 실행 방지 (--list/--reset은 락 불필요)
    if not args.list and not args.reset:
        if not _acquire_lock():
            logger.error("❌ 이미 실행 중 (락 파일 존재). 중복 실행 차단됨.")
            return
    _cleanup_old_logs()

    if args.reset:
        fresh = {"published": [], "v2_published": [], "pruned_combos": [],
                 "listing_ids": {}, "combo_ids": {}}
        _save_progress(fresh)
        logger.info("✅ 진행 상태 초기화 완료 (published=0, v2=0, pruned=0)")
        return

    if args.list:
        print_status()
        return

    if args.mock:
        os.environ["WALL_ART_MOCK"] = "true"
        logger.info("*** MOCK 모드 — 이미지 API 없음, 비용 $0 ***")

    # ── 오토스케일: --count/--interval 미지정 시 자동 결정 ──
    count    = args.count
    interval = args.interval
    if args.publish and count == 4 and interval == 3.0:
        # 기본값 그대로면 오토스케일 시도
        try:
            from config.settings import ETSY_SHOP_ID
            from publisher.etsy_api import get_shop_id
            _sid = ETSY_SHOP_ID or get_shop_id()
            if _sid:
                count, interval = _auto_count_interval(_sid)
        except Exception:
            pass  # 조회 실패 시 기본값 유지

    combos = get_next_combos(count)
    logger.info("오늘 생성할 %d개 (%.0f시간 간격 예약):", len(combos), interval)
    for i, c in enumerate(combos, 1):
        logger.info("  %d. %s × %s [%s]", i, c["planner_type"], c["theme_name"],
                    c.get("niche") or "generic")

    # ── 1단계: 전체 생성 (일괄) ──
    import time as _time_mod
    _stage1_start = _time_mod.time()
    logger.info("")
    logger.info("━" * 55)
    logger.info("  1단계: 전체 생성")
    logger.info("━" * 55)
    generated = []
    for combo in combos:
        item = _generate_one(combo)
        if item:
            generated.append(item)

    _stage1_elapsed = _time_mod.time() - _stage1_start
    logger.info("생성 완료: %d/%d개  (%.0f초 소요)", len(generated), len(combos), _stage1_elapsed)

    if not generated:
        logger.error("생성된 상품 없음 — 종료")
        _release_lock()
        return

    if not args.publish:
        # 발행 안 함 = progress에 기록 안 함. 다음번 --publish 실행 시 동일 조합 재생성.
        logger.info("")
        logger.info("생성만 완료 (Etsy 미발행 — progress 기록 없음).")
        logger.info("발행하려면 --publish 추가:")
        logger.info("  python daily_generate.py --count %d --publish", args.count)
        _open_preview(generated)
        _print_summary(generated, _load_progress())
        _release_lock()
        return

    # ── 2단계: 전체 드래프트 업로드 ──
    from config.settings import ETSY_SHOP_ID
    from publisher.etsy_api import get_shop_id
    shop_id = ETSY_SHOP_ID or get_shop_id()
    if not shop_id:
        logger.error("ETSY_SHOP_ID 미설정 — 발행 불가")
        _release_lock()
        return

    logger.info("")
    logger.info("━" * 55)
    logger.info("  2단계: 드래프트 업로드 (%d개)", len(generated))
    logger.info("━" * 55)

    drafted = []  # [(item, listing_id), ...]
    for item in generated:
        # 리뷰 기반 가격 주입 (업로드 직전 최신 리뷰 수 반영)
        item["seo"].price_usd = _get_niche_price(item["combo"].get("niche"), shop_id)
        label = f"{item['combo']['planner_type']}×{item['combo']['theme_name']}"
        listing_id = _upload_draft(item, shop_id)
        if listing_id:
            drafted.append((item, listing_id))
        else:
            logger.warning("⚠️ 드래프트 실패, 건너뜀: %s", label)

    if not drafted:
        logger.error("드래프트 업로드 전부 실패 — 종료")
        _release_lock()
        return

    # ── 3단계: 1번째 즉시 활성화, 나머지 큐 등록 ──
    logger.info("")
    logger.info("━" * 55)
    logger.info("  3단계: 발행 스케줄 설정")
    logger.info("━" * 55)

    import time as _time
    now_ts = _time.time()
    successful_combos = []

    # 첫 번째 예약 항목의 피크타임 기준점 계산 (나머지는 여기서 interval씩 추가)
    # Why: 각 항목을 독립적으로 _to_peak_utc 처리하면 모두 14:00으로 스냅됨
    _queue_base_ts: float | None = None

    for idx, (item, listing_id) in enumerate(drafted):
        label = f"{item['combo']['planner_type']}×{item['combo']['theme_name']}"
        if idx == 0:
            # 첫 번째: 즉시 활성화
            if _activate(listing_id, shop_id):
                logger.info("🚀 즉시 발행 완료: %s (listing_id=%s)", label, listing_id)
                successful_combos.append(item["combo"])
                # Pinterest 즉시 핀 발행 (--no-pinterest 없을 때)
                if not args.no_pinterest:
                    _pin_to_pinterest(item, listing_id)
            else:
                logger.error("❌ 즉시 발행 실패: %s", label)
        else:
            # 나머지: 큐에 예약 — 첫 예약 항목만 피크타임으로 스냅, 나머지는 거기서 interval씩 추가
            # Why: 각각 독립 스냅하면 전부 14:00이 되어 동시 발행 버그 발생
            if _queue_base_ts is None:
                _queue_base_ts = _to_peak_utc(now_ts + interval * 3600)
            jitter_sec = random.randint(-20 * 60, 20 * 60)
            publish_ts = _queue_base_ts + (idx - 1) * interval * 3600 + jitter_sec
            publish_at = datetime.utcfromtimestamp(publish_ts).strftime("%Y-%m-%dT%H:%M:%S")
            # Pinterest 정보를 큐에 저장 → activate_queue.py가 활성화 후 핀 발행
            _pin_info: dict | None = None
            if not args.no_pinterest:
                _prod = item["product"]
                _seo  = item["seo"]
                _imgs = getattr(_prod, "mockup_paths", []) or []
                # 상대경로로 저장 (Windows/Linux 모두 호환)
                _img_abs = Path(_imgs[0]) if _imgs else None
                try:
                    _img_rel = str(_img_abs.relative_to(Path(__file__).parent)) if _img_abs else ""
                except ValueError:
                    _img_rel = str(_img_abs) if _img_abs else ""
                _pin_info = {
                    "title":      _seo.title,
                    "image_path": _img_rel,
                    "niche":      item["combo"].get("niche"),
                    "tags":       getattr(_seo, "tags", []),
                }
            _append_queue(listing_id, shop_id, publish_at, label, pinterest_info=_pin_info)
            successful_combos.append(item["combo"])
            logger.info("📅 %d번째 예약: %s → %s 발행",
                        idx + 1, label,
                        datetime.fromtimestamp(publish_ts).strftime("%H:%M"))

    # v2 여부 판단: 이미 v1 published에 있으면 v2
    _progress_snap = _load_progress()
    _v1_published  = set(_progress_snap.get("published", []))
    _listing_ids_map = {
        _combo_key(item["combo"]): lid
        for item, lid in drafted
        if lid
    }
    _combo_product_ids = {
        _combo_key(item["combo"]): getattr(item["product"], "product_id", "")
        for item in generated
    }
    _v2_combos = [c for c in successful_combos if _combo_key(c) in _v1_published]
    _v1_combos = [c for c in successful_combos if _combo_key(c) not in _v1_published]
    if _v1_combos:
        mark_published(_v1_combos, listing_ids=_listing_ids_map, combo_product_ids=_combo_product_ids, version=1)
    if _v2_combos:
        mark_published(_v2_combos, listing_ids=_listing_ids_map, combo_product_ids=_combo_product_ids, version=2)

    # ── 발행 스케줄 요약 ──
    logger.info("")
    logger.info("━" * 55)
    logger.info("  발행 예정 시각")
    logger.info("━" * 55)
    for idx, (item, listing_id) in enumerate(drafted):
        label = f"{item['combo']['planner_type']}×{item['combo']['theme_name']}"
        if idx == 0:
            logger.info("  ✅ 즉시 발행: %s", label)
        else:
            t = datetime.fromtimestamp(now_ts + idx * interval * 3600).strftime("%H:%M")
            logger.info("  📅 %s 발행: %s", t, label)

    logger.info("")
    logger.info("  ※ 예약 발행은 activate_queue.py 가 매시간 자동 처리합니다.")
    _total_elapsed = _time_mod.time() - _stage1_start
    logger.info("  총 소요 시간: %.0f초 (%.1f분)", _total_elapsed, _total_elapsed / 60)
    _ensure_queue_scheduler()
    _open_preview(generated)
    _print_summary(generated, _load_progress())
    _release_lock()


def _open_preview(generated: list) -> None:
    """생성된 상품 HTML 미리보기 생성 + 브라우저 자동 오픈."""
    try:
        from preview_generator import generate_preview
        preview_path = str(Path(__file__).parent / f"preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        generate_preview(generated, output_path=preview_path, open_browser=True)
    except Exception as e:
        logger.warning("미리보기 생성 실패 (건너뜀): %s", e)


def _print_summary(generated: list, progress: dict):
    published_n = len(progress.get("published", []))
    v2_n        = len(progress.get("v2_published", []))
    logger.info("")
    logger.info("=" * 55)
    logger.info("  완료: %d개", len(generated))
    logger.info("  v1 발행 누적: %d/%d", published_n, len(ALL_COMBINATIONS))
    if v2_n:
        logger.info("  v2 재발행 누적: %d개", v2_n)
    logger.info("=" * 55)

    # 생성된 상품 목록 라인
    items_lines = ""
    for i, item in enumerate(generated):
        combo = item.get("combo", {})
        seo   = item.get("seo")
        niche = combo.get("niche", "")
        ptype = combo.get("planner_type", "")
        theme = combo.get("theme_name", "")
        title = (seo.title[:45] if seo and seo.title else f"{ptype}×{theme}")
        niche_tag = f"[{niche}] " if niche else ""
        items_lines += f"  {i+1}. {niche_tag}<b>{title}</b>\n"

    progress_bar = f"{published_n}/{len(ALL_COMBINATIONS)}"
    v2_line = f"\n🔁 v2 재발행 누적: {v2_n}개" if v2_n else ""

    _notify(
        f"✅ <b>Etsy 오늘의 상품 생성 완료!</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📦 오늘 생성: <b>{len(generated)}개</b>\n"
        f"{items_lines}"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 전체 진행: {progress_bar} 조합 완료{v2_line}\n"
        f"⏰ 예약 발행은 매시간 자동 처리"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as _e:
        logger.exception("❌ 치명적 오류: %s", _e)
        _notify(f"❌ Etsy 자동생성 오류: {_e}")
        _release_lock()
        raise
