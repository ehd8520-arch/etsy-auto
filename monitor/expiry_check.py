# -*- coding: utf-8 -*-
"""
monitor/expiry_check.py — Etsy 토큰 + Pinterest 세션 만료 사전 알림.

매일 GitHub Actions에서 실행:
    python -m monitor.expiry_check

만료 7일 전 → Telegram 경고 알림 전송.
"""
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_DIR   = Path(__file__).resolve().parent.parent
_TG_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT    = os.getenv("TELEGRAM_CHAT_ID", "")

WARN_DAYS   = 7   # 만료 N일 전부터 경고
ETSY_TOKEN_EXPIRE_DAYS = 90  # Etsy 리프레시 토큰 유효기간


# ── Telegram 알림 ─────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    if not _TG_TOKEN or not _TG_CHAT:
        logger.warning("텔레그램 미설정 — 알림 스킵")
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
            logger.warning("텔레그램 알림 실패: %s", resp.text[:100])
    except Exception as e:
        logger.error("텔레그램 전송 예외: %s", e)


# ── Etsy 토큰 만료 체크 ────────────────────────────────────────────────────────

def check_etsy_token_expiry() -> int:
    """Etsy 리프레시 토큰 남은 일수 반환. 파일 없으면 -1."""
    meta_path = _BASE_DIR / "db" / "token_meta.json"

    # 파일 없으면 오늘 날짜로 초기화 (첫 실행)
    if not meta_path.exists():
        logger.info("token_meta.json 없음 → 오늘 날짜로 초기화")
        try:
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(
                json.dumps({"refresh_token_updated_at": datetime.now().isoformat()},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("token_meta 초기화 실패: %s", e)
        return ETSY_TOKEN_EXPIRE_DAYS  # 오늘 갱신한 것으로 간주

    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        updated_at = datetime.fromisoformat(data["refresh_token_updated_at"])
        elapsed = (datetime.now() - updated_at).days
        remaining = ETSY_TOKEN_EXPIRE_DAYS - elapsed
        logger.info("Etsy 리프레시 토큰: 갱신 후 %d일 경과, 남은 유효기간 %d일", elapsed, remaining)
        return remaining
    except Exception as e:
        logger.error("token_meta 읽기 실패: %s", e)
        return -1


# ── Pinterest 세션 만료 체크 ───────────────────────────────────────────────────

def check_pinterest_session_expiry() -> int:
    """Pinterest 세션 쿠키 남은 일수 반환. 파일/쿠키 없으면 -1."""
    session_path = _BASE_DIR / "db" / "pinterest_session.json"
    if not session_path.exists():
        logger.warning("Pinterest 세션 파일 없음")
        return -1
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
        cookies = data.get("cookies", [])
        for c in cookies:
            if c.get("name") == "_pinterest_sess":
                expiry = c.get("expires", 0)
                if not expiry:
                    logger.info("Pinterest 세션 만료일 정보 없음")
                    return -1
                remaining = int((expiry - time.time()) / 86400)
                logger.info("Pinterest 세션 남은 유효기간: %d일", remaining)
                return remaining
        logger.warning("_pinterest_sess 쿠키 없음")
        return -1
    except Exception as e:
        logger.error("Pinterest 세션 읽기 실패: %s", e)
        return -1


# ── 메인 ──────────────────────────────────────────────────────────────────────

def run() -> None:
    etsy_days      = check_etsy_token_expiry()
    pinterest_days = check_pinterest_session_expiry()

    alerts = []

    # Etsy 토큰 경고
    if etsy_days < 0:
        alerts.append(
            "⚠️ <b>[Etsy 토큰]</b> 만료 정보를 읽을 수 없습니다.\n"
            "→ 로컬 PC에서 <code>python get_etsy_token.py</code> 실행 후\n"
            "  GitHub Secrets에 토큰 업데이트 필요"
        )
    elif etsy_days <= WARN_DAYS:
        alerts.append(
            f"🚨 <b>[Etsy 토큰 만료 {etsy_days}일 전!]</b>\n"
            f"\n"
            f"지금 바로 갱신하세요:\n"
            f"1️⃣ 로컬 PC 켜기\n"
            f"2️⃣ <code>python get_etsy_token.py</code> 실행\n"
            f"3️⃣ 새 토큰 → GitHub Secrets 업데이트\n"
            f"   (ETSY_ACCESS_TOKEN / ETSY_REFRESH_TOKEN)\n"
            f"\n"
            f"⏰ 방치하면 {etsy_days}일 후 Etsy 발행 전부 중단됩니다!"
        )

    # Pinterest 세션 경고
    if pinterest_days < 0:
        alerts.append(
            "⚠️ <b>[Pinterest 세션]</b> 만료 정보를 읽을 수 없습니다.\n"
            "→ 로컬 PC에서 Pinterest 재로그인 후\n"
            "  세션 파일을 GitHub Secret에 업데이트 필요"
        )
    elif pinterest_days <= WARN_DAYS:
        alerts.append(
            f"🚨 <b>[Pinterest 세션 만료 {pinterest_days}일 전!]</b>\n"
            f"\n"
            f"지금 바로 갱신하세요:\n"
            f"1️⃣ 로컬 PC 켜기\n"
            f"2️⃣ <code>python publisher/pinterest.py</code> 실행\n"
            f"   (브라우저 열리면 Pinterest 로그인)\n"
            f"3️⃣ 새 세션 → GitHub Secret PINTEREST_SESSION 업데이트\n"
            f"\n"
            f"⏰ 방치하면 {pinterest_days}일 후 Pinterest 핀 발행 중단됩니다!"
        )

    if not alerts:
        logger.info("✅ 만료 임박 항목 없음 (Etsy %d일, Pinterest %s일 남음)",
                    etsy_days, pinterest_days if pinterest_days >= 0 else "?")
        return

    for msg in alerts:
        _send_telegram(msg)
        logger.info("만료 경고 알림 전송: %s", msg[:60])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
