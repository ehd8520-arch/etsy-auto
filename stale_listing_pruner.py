# -*- coding: utf-8 -*-
"""
stale_listing_pruner.py — 100일 경과 + 0판매 리스팅 자동 삭제.

Etsy 갱신 주기 = 120일($0.20/개). 100일에 미리 정리 → 갱신비 0원.

삭제 기준:
    - 등록 후 100일 이상 경과
    - 누적 판매 0개 (1판매 이상은 무조건 유지)

실행:
    python stale_listing_pruner.py        # 실제 삭제
    python stale_listing_pruner.py --dry  # 미리보기 (변경 없음)
"""
import sys
import logging
import argparse
import time
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"pruner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("stale_pruner")

sys.path.insert(0, str(Path(__file__).parent))

STALE_DAYS       = 100   # 이 일수 이상 경과한 리스팅 검토
MAX_SALES_DELETE = 0     # 0판매만 삭제 (1판매 이상은 무조건 유지)
LOCK_FILE        = Path(__file__).parent / "pruner.lock"


def _cleanup_old_logs(max_days: int = 7) -> None:
    cutoff = time.time() - max_days * 86400
    for lf in LOG_DIR.glob("pruner_*.log"):
        try:
            if lf.stat().st_mtime < cutoff:
                lf.unlink()
        except Exception:
            pass


def _notify(message: str) -> None:
    """알림 전송 — Telegram 우선, Discord 폴백. 미설정 시 무음."""
    import os as _os
    try:
        import requests as _req
    except ImportError:
        return
    tg_token = _os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat  = _os.environ.get("TELEGRAM_CHAT_ID", "")
    if tg_token and tg_chat:
        try:
            _req.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat, "text": message},
                timeout=10,
            )
            return
        except Exception:
            pass
    url = _os.environ.get("DISCORD_WEBHOOK_URL", "")
    if url:
        try:
            _req.post(url, json={"content": message}, timeout=10)
        except Exception:
            pass


def _acquire_lock() -> bool:
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < 3600:  # 1시간 미만 = 실행 중으로 판단
            return False
    import os as _os
    LOCK_FILE.write_text(str(_os.getpid()), encoding="utf-8")
    return True


def _release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def _add_pruned_combo(listing_id: str) -> None:
    """삭제된 listing_id에 대응하는 combo_key를 pruned_combos에 기록.
    Why: v2 재발행 로직이 pruned_combos를 참조해 v1 삭제분만 v2로 재발행.
    Etsy 중복 패널티 방지 — 삭제 확인 후에만 v2 후보 등록.
    """
    try:
        from daily_generate import _load_progress, _save_progress, _backup_progress
        progress = _load_progress()
        # listing_ids 역방향 조회: listing_id → combo_key
        listing_ids_map = progress.get("listing_ids", {})
        combo_key = next((k for k, v in listing_ids_map.items() if v == listing_id), None)
        if not combo_key:
            return  # 추적 정보 없음 — 무시
        pruned = progress.setdefault("pruned_combos", [])
        if combo_key not in pruned:
            pruned.append(combo_key)
            _save_progress(progress)
            _backup_progress()
            logger.info("  pruned_combos 등록: %s (v2 재발행 후보)", combo_key)
    except Exception as e:
        logger.warning("pruned_combos 기록 실패 (무시): %s", e)


def run(dry: bool = False) -> int:
    """100일 경과 + 0판매 리스팅 삭제. 삭제 수 반환."""
    try:
        from config.settings import ETSY_SHOP_ID
        from publisher.etsy_api import (
            get_shop_id, get_all_active_listings,
            get_listing_transaction_count, delete_listing,
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

    logger.info("활성 리스팅 %d개 검토 시작 (기준: %d일 경과 + 0판매)",
                len(listings), STALE_DAYS)

    now_ts  = time.time()
    checked = 0
    deleted = 0
    skipped_young  = 0
    skipped_selling = 0
    skipped_api_err = 0

    for listing in listings:
        listing_id  = str(listing.get("listing_id") or "")
        if not listing_id:
            continue
        title       = listing.get("title", "")
        created_ts  = listing.get("created_timestamp", 0)

        # created_timestamp 없는 경우 개별 조회
        if not created_ts:
            from publisher.etsy_api import get_listing_stats
            detail = get_listing_stats(shop_id, listing_id) or {}
            created_ts = detail.get("created_timestamp", 0)

        if not created_ts:
            logger.warning("  ⚠️ 생성일 조회 불가, 건너뜀: %s", title[:45])
            skipped_api_err += 1
            continue

        age_days = (now_ts - created_ts) / 86400

        if age_days < STALE_DAYS:
            skipped_young += 1
            continue

        # 100일 이상 — 판매 수 조회
        checked += 1
        tx_count = get_listing_transaction_count(shop_id, listing_id)

        if tx_count < 0:
            # API 오류 → 삭제 건너뜀 (보수적 처리)
            logger.warning("  ⚠️ 판매 수 조회 실패, 건너뜀: %s", title[:45])
            skipped_api_err += 1
            continue

        if tx_count > 0:
            logger.info("  ✅ 유지: %s | %d일 경과 | %d판매",
                        title[:45], int(age_days), tx_count)
            skipped_selling += 1
            continue

        # 삭제 대상: 100일+ 경과 + 0판매
        if dry:
            logger.info("  [DRY] 삭제 예정: %s | %d일 경과 | %d판매",
                        title[:45], int(age_days), tx_count)
            deleted += 1
        else:
            if delete_listing(shop_id, listing_id):
                logger.info("  🗑️  삭제 완료: %s | %d일 경과 | %d판매",
                            title[:45], int(age_days), tx_count)
                _add_pruned_combo(listing_id)
                deleted += 1
            else:
                logger.warning("  ⚠️ 삭제 실패: %s", title[:45])

    action = "예정" if dry else "완료"
    logger.info("")
    logger.info("=" * 55)
    logger.info("  정리 %s", action)
    logger.info("  전체 리스팅: %d개", len(listings))
    logger.info("  100일 미만 (유지): %d개", skipped_young)
    logger.info("  100일+ 검토: %d개", checked)
    logger.info("  1판매+ (유지): %d개", skipped_selling)
    logger.info("  API 오류 (건너뜀): %d개", skipped_api_err)
    logger.info("  삭제 %s: %d개", action, deleted)
    logger.info("=" * 55)
    if not dry:
        _notify(
            f"🗑️ 리스팅 정리 완료 | 전체 {len(listings)}개 검토 | 삭제 {deleted}개 | "
            f"유지(판매중) {skipped_selling}개 | API오류 건너뜀 {skipped_api_err}개"
        )
    return deleted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="100일 경과 + 0판매 리스팅 자동 삭제")
    parser.add_argument("--dry", action="store_true", help="미리보기만 (실제 삭제 없음)")
    args = parser.parse_args()

    if not args.dry:
        if not _acquire_lock():
            logger.error("❌ 이미 실행 중 (락 파일 존재). 중복 실행 차단됨.")
            sys.exit(1)
    _cleanup_old_logs()

    try:
        run(dry=args.dry)
    except Exception as e:
        logger.exception("❌ 치명적 오류: %s", e)
        _notify(f"❌ 리스팅 정리 오류: {e}")
        raise
    finally:
        if not args.dry:
            _release_lock()
