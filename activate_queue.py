# -*- coding: utf-8 -*-
"""
activate_queue.py — publish_queue.json에서 발행 시각이 된 드래프트를 활성화.

Windows Task Scheduler가 매시간 실행:
    python activate_queue.py

수동 실행:
    python activate_queue.py          # 지금 발행할 항목만
    python activate_queue.py --dry    # 실제 발행 없이 확인만
    python activate_queue.py --list   # 큐 전체 목록
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("activate_queue")

sys.path.insert(0, str(Path(__file__).parent))

QUEUE_FILE = Path(__file__).parent / "publish_queue.json"


def _load_queue() -> list:
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_queue(queue: list):
    """원자적 쓰기: 임시 파일 → rename → 크래시 시 기존 큐 보존."""
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


def print_queue():
    queue = _load_queue()
    if not queue:
        logger.info("큐가 비어 있습니다.")
        return

    now = datetime.now()
    logger.info("")
    logger.info("=" * 60)
    logger.info("  발행 큐 현황 (%d개)", len(queue))
    logger.info("=" * 60)
    for entry in queue:
        publish_at = datetime.fromisoformat(entry["publish_at"])
        status = "✅ 완료" if entry.get("done") else (
            "⏰ 대기 중" if publish_at > now else "🔴 발행 예정 (미실행)"
        )
        logger.info("  %s  %s  →  %s  [%s]",
                    entry["publish_at"][:16],
                    entry.get("label", entry["listing_id"]),
                    entry["shop_id"],
                    status)


def _fetch_etsy_image(listing_id: str, dest: "Path") -> bool:
    """로컬 이미지 없을 때 Etsy API에서 대표 이미지 다운로드. 성공 시 True."""
    try:
        import requests as _req
        from publisher.etsy_api import _api_request
        result = _api_request("GET", f"/application/listings/{listing_id}/images")
        if not result:
            return False
        images = sorted(result.get("results", []), key=lambda x: x.get("rank", 99))
        if not images:
            return False
        url = images[0].get("url_fullxfull") or images[0].get("url_570xN")
        if not url:
            return False
        resp = _req.get(url, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        logger.info("Etsy 이미지 다운로드 완료: listing=%s", listing_id)
        return True
    except Exception as e:
        logger.warning("Etsy 이미지 다운로드 실패: %s", e)
        return False


def _pin_from_queue(entry: dict) -> None:
    """큐 항목의 pinterest_info로 핀 발행. 실패해도 메인 흐름 중단 없음."""
    import tempfile
    _tmp_dir = None
    try:
        from publisher.pinterest import pin_listing
        from pathlib import Path as _Path
        info       = entry["pinterest_info"]
        listing_id = entry["listing_id"]
        image_path = info.get("image_path", "")

        # 로컬 이미지 확인
        _img = _Path(image_path) if image_path else _Path("")
        if not _img.is_absolute() and image_path:
            _img = _Path(__file__).parent / _img

        # 로컬 이미지 없으면 Etsy에서 다운로드 (GitHub Actions 재실행 시 이미지 소실 대응)
        if not _img.exists():
            if image_path:
                logger.info("로컬 이미지 없음 — Etsy에서 다운로드 시도: listing=%s", listing_id)
            _tmp_dir = tempfile.mkdtemp()
            _img = _Path(_tmp_dir) / f"{listing_id}.jpg"
            if not _fetch_etsy_image(str(listing_id), _img):
                logger.warning("Pinterest 핀 건너뜀 (이미지 없음): listing_id=%s", listing_id)
                return
        image_path = str(_img)

        etsy_url = f"https://www.etsy.com/listing/{listing_id}"
        result = pin_listing(
            listing_id    = listing_id,
            listing_title = info.get("title", "Digital Planner Printable"),
            image_path    = image_path,
            etsy_url      = etsy_url,
            niche         = info.get("niche"),
            seo_tags      = info.get("tags"),
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
        logger.warning("Pinterest 핀 실패 (건너뜀): %s", e)
    finally:
        if _tmp_dir:
            import shutil
            try:
                shutil.rmtree(_tmp_dir, ignore_errors=True)
            except Exception:
                pass


def run(dry: bool = False) -> int:
    """발행 시각이 된 드래프트 활성화. 처리한 항목 수 반환."""
    queue = _load_queue()
    if not queue:
        logger.info("큐 비어 있음 — 처리할 항목 없음")
        return 0

    now = datetime.now()
    pending = [
        e for e in queue
        if not e.get("done") and datetime.fromisoformat(e["publish_at"]) <= now
    ]

    if not pending:
        next_items = [e for e in queue if not e.get("done")]
        if next_items:
            next_time = min(e["publish_at"] for e in next_items)
            logger.info("발행 대기 중 — 다음 발행: %s", next_time[:16])
        else:
            logger.info("모든 항목 발행 완료")
        return 0

    logger.info("발행 처리: %d개", len(pending))

    if dry:
        for e in pending:
            logger.info("  [DRY] %s — %s", e.get("label", e["listing_id"]), e["publish_at"][:16])
        return len(pending)

    try:
        from publisher.etsy_api import activate_listing
    except ImportError as e:
        logger.error("etsy_api 임포트 실패: %s", e)
        return 0

    activated = 0
    for entry in queue:
        if entry.get("done"):
            continue
        publish_at = datetime.fromisoformat(entry["publish_at"])
        if publish_at > now:
            continue

        listing_id = entry["listing_id"]
        shop_id    = entry["shop_id"]
        label      = entry.get("label", listing_id)

        try:
            ok = activate_listing(shop_id, listing_id)
            if ok:
                entry["done"] = True
                entry["activated_at"] = now.strftime("%Y-%m-%dT%H:%M:%S")
                activated += 1
                logger.info("🚀 발행 완료: %s (listing_id=%s)", label, listing_id)
                # Pinterest 핀 발행 (큐 항목에 pinterest_info가 있을 때)
                if entry.get("pinterest_info"):
                    _pin_from_queue(entry)
            else:
                logger.error("❌ 발행 실패: %s (listing_id=%s)", label, listing_id)
        except Exception as e:
            logger.error("❌ 예외: %s — %s", label, e)

    # 완료 항목 정리: done=True + 7일 이상 지난 항목 제거 (큐 파일 무한 증가 방지)
    import time as _t
    cutoff = _t.time() - 7 * 86400
    queue = [
        e for e in queue
        if not e.get("done") or (
            e.get("activated_at") and
            datetime.fromisoformat(e["activated_at"]).timestamp() > cutoff
        )
    ]

    _save_queue(queue)
    logger.info("처리 완료: %d/%d개 발행", activated, len(pending))

    # 발행 성공 시 Telegram 알림
    if activated > 0:
        _notify_telegram(f"🚀 Etsy 발행 완료 | {activated}개 활성화")

    return activated


def _notify_telegram(message: str) -> None:
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="발행 큐 처리")
    parser.add_argument("--dry",  action="store_true", help="실제 발행 없이 확인만")
    parser.add_argument("--list", action="store_true", help="큐 목록 출력")
    args = parser.parse_args()

    if args.list:
        print_queue()
    else:
        run(dry=args.dry)
