# -*- coding: utf-8 -*-
"""
monitor/order_alert.py — Etsy 새 주문 감지 → 텔레그램 알림.

사용:
    python -m monitor.order_alert
"""
import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_DIR    = Path(__file__).resolve().parent.parent
_STATE_FILE  = _BASE_DIR / "db" / "order_alert_state.json"
_TG_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT     = os.getenv("TELEGRAM_CHAT_ID", "")
_SHOP_ID     = os.getenv("ETSY_SHOP_ID", "")


# ── 상태 저장/로드 ────────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"seen_receipt_ids": []}


def _save_state(state: dict) -> None:
    """원자적 쓰기: tmp → replace."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_STATE_FILE)
    except Exception as e:
        logger.warning("상태 저장 실패: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


# ── Etsy 주문 조회 ────────────────────────────────────────────────────────────

def _get_recent_receipts(limit: int = 25) -> list:
    """최근 주문(receipts) 목록 반환."""
    if not _SHOP_ID:
        logger.error("ETSY_SHOP_ID 없음")
        return []
    try:
        from publisher.etsy_api import _api_request
        result = _api_request(
            "GET",
            f"/application/shops/{_SHOP_ID}/receipts",
            params={"limit": limit, "was_paid": "true"},
        )
        if result is None:
            logger.warning("주문 조회 실패")
            return []
        return result.get("results", [])
    except Exception as e:
        logger.error("주문 조회 예외: %s", e)
        return []


# ── 텔레그램 알림 ─────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    if not _TG_TOKEN or not _TG_CHAT:
        logger.warning("텔레그램 설정 없음 — 알림 스킵")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            json={"chat_id": _TG_CHAT, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        if resp.ok:
            logger.info("텔레그램 알림 전송 완료")
        else:
            logger.warning("텔레그램 알림 실패: %s", resp.text[:200])
    except Exception as e:
        logger.error("텔레그램 전송 예외: %s", e)


def _esc(text: str) -> str:
    """Telegram HTML 파싱 모드용 특수문자 이스케이프."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_order_message(receipt: dict) -> str:
    receipt_id  = receipt.get("receipt_id", "?")
    buyer       = _esc(receipt.get("name", "익명"))
    country     = _esc(receipt.get("country_iso", ""))
    total       = receipt.get("grandtotal", {})
    amount      = total.get("amount", 0) / max(total.get("divisor", 100), 1)
    currency    = _esc(total.get("currency_code", "USD"))
    items       = receipt.get("transactions", [])
    item_count  = len(items)
    item_titles = "\n".join(f"  • {_esc(t.get('title', '?')[:60])}" for t in items[:5])
    order_url   = f"https://www.etsy.com/your/orders/{receipt_id}"
    flag        = f" 🌍 {country}" if country else ""

    return (
        f"🛍 <b>새 주문 들어왔어요!</b>{flag}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 <b>${amount:.2f} {currency}</b>  ({item_count}개 상품)\n"
        f"👤 구매자: {buyer}\n"
        f"📦 상품:\n{item_titles}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href='{order_url}'>주문 확인하기 #{receipt_id}</a>"
    )


# ── 메인 체크 ─────────────────────────────────────────────────────────────────

def check_new_orders() -> int:
    """새 주문 확인 후 텔레그램 알림. 새 주문 수 반환."""
    state    = _load_state()
    seen_ids = set(state.get("seen_receipt_ids", []))

    receipts = _get_recent_receipts(limit=25)
    new_count = 0

    for receipt in receipts:
        rid = str(receipt.get("receipt_id", ""))
        if not rid or rid in seen_ids:
            continue
        # 새 주문 발견
        msg = _format_order_message(receipt)
        logger.info("새 주문 감지: #%s", rid)
        _send_telegram(msg)
        seen_ids.add(rid)
        new_count += 1
        time.sleep(0.5)

    state["seen_receipt_ids"] = list(seen_ids)[-200:]  # 최근 200개만 유지
    _save_state(state)

    if new_count == 0:
        logger.info("새 주문 없음")

    return new_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    count = check_new_orders()
    print(f"새 주문 {count}건 알림 전송 완료")
