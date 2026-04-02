# -*- coding: utf-8 -*-
"""
monitor/sale_message_updater.py — 매월 1일 Etsy 구매 감사 메시지 자동 교체.

Groq로 자연스러운 영어 감사 메시지 3가지 변형 생성 → 최고 품질 선택 →
Etsy 샵 digital_sale_message 업데이트 → Telegram 알림.

실행:
    python -m monitor.sale_message_updater
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_DIR   = Path(__file__).resolve().parent.parent
_STATE_FILE = _BASE_DIR / "db" / "sale_message_state.json"
_TG_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT    = os.getenv("TELEGRAM_CHAT_ID", "")
_SHOP_ID    = os.getenv("ETSY_SHOP_ID", "")

MIN_SCORE   = 9.0
MAX_RETRIES = 3


# ── 상태 저장/로드 ─────────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"last_updated": "", "current_message": ""}


def _save_state(state: dict) -> None:
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


# ── Telegram 알림 ──────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    if not _TG_TOKEN or not _TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            json={"chat_id": _TG_CHAT, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        logger.warning("텔레그램 전송 실패: %s", e)


# ── JSON 파싱 방어 ──────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict | None:
    try:
        text = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text.strip(), flags=re.MULTILINE)
        start = text.find('{')
        end   = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
    except Exception as e:
        logger.warning("JSON 파싱 실패: %s", e)
    return None


# ── Groq 메시지 생성 ───────────────────────────────────────────────────────────

_TONE_PROMPTS = {
    "casual":       "Write in a casual, friendly, like-a-friend tone.",
    "warm":         "Write in a warm, heartfelt, personal tone.",
    "professional": "Write in a polished, professional but still human tone.",
}


def _generate_one_message(tone: str) -> dict | None:
    """Groq로 감사 메시지 1개 생성. 자가채점 포함."""
    from config.settings import get_next_groq_key, mark_groq_key_exhausted, GROQ_BASE_URL, GROQ_MODEL

    # Few-shot 예시: 실제 Etsy 상위 셀러들의 실제 문체
    examples = {
        "casual": (
            "Hey! Your planner is ready to download — hope it makes your days a little easier 🙂 "
            "If you end up loving it, a quick honest review means the world to a small shop like mine. Either way, enjoy!"
        ),
        "warm": (
            "Thank you so much for your purchase — it genuinely means a lot to me! "
            "Your file is all set to download whenever you're ready. "
            "If the planner brings you even a little more calm or clarity, I'd love to hear about it in a review ☀️"
        ),
        "professional": (
            "Thank you for your order! Your digital planner is available for download now. "
            "I put a lot of care into designing each page, and your honest feedback in a review "
            "helps me keep improving. Hope it serves you well!"
        ),
    }

    prompt = f"""You are a solo Etsy seller who handcrafts digital planners. A customer just bought one of your planners.
Write the automatic purchase thank-you message they will receive.

Tone: {tone} — example of this tone:
"{examples.get(tone, '')}"

Write a NEW message in the same tone. Do NOT copy the example — write something fresh but equally natural.

Hard rules:
- English only, 2-3 sentences
- Must feel like a SPECIFIC human wrote it, not a form letter
- Reference downloading the file + a gentle honest-review ask
- NO "5-star", NO "please rate us", NO "click here"
- Max 1 emoji

Respond ONLY with this JSON (no markdown):
{{
  "message": "the actual message text",
  "score": {{
    "naturalness": 0-10,
    "warmth": 0-10,
    "review_nudge": 0-10
  }},
  "score_reason": "one sentence why — would a real buyer feel this was written by a person?"
}}"""

    for attempt in range(MAX_RETRIES):
        key = get_next_groq_key()
        if not key:
            logger.error("Groq API 키 없음")
            return None
        try:
            resp = requests.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.85,
                    "max_tokens": 300,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                mark_groq_key_exhausted(key)
                logger.warning("Groq 429 키 소진, 재시도 %d/%d", attempt + 1, MAX_RETRIES)
                time.sleep(2 ** attempt)
                continue
            if not resp.ok:
                logger.warning("Groq 오류 %s, 재시도 %d/%d", resp.status_code, attempt + 1, MAX_RETRIES)
                time.sleep(2 ** attempt)
                continue

            raw = resp.json()["choices"][0]["message"]["content"]
            data = _parse_json(raw)
            if not data or "message" not in data:
                logger.warning("응답 파싱 실패, 재시도")
                continue

            scores = data.get("score", {})
            avg = sum(scores.values()) / len(scores) if scores else 0
            logger.info("  [%s] 점수: %s → 평균 %.1f (%s)",
                        tone, scores, avg, data.get("score_reason", ""))
            data["_avg_score"] = avg
            data["_tone"] = tone
            return data

        except Exception as e:
            logger.warning("Groq 예외 %s, 재시도 %d/%d", e, attempt + 1, MAX_RETRIES)
            time.sleep(2 ** attempt)

    return None


def generate_best_message() -> str | None:
    """3가지 톤 중 최고 점수 메시지 반환. 모두 9점 미만이면 최고점 그대로 사용."""
    candidates = []
    for tone in _TONE_PROMPTS:
        result = _generate_one_message(tone)
        if result:
            candidates.append(result)
        time.sleep(1)  # Groq rate limit 방어

    if not candidates:
        logger.error("메시지 생성 실패 — 후보 없음")
        return None

    best = max(candidates, key=lambda d: d.get("_avg_score", 0))
    logger.info("최고 선택: [%s] 점수=%.1f", best.get("_tone"), best.get("_avg_score", 0))
    logger.info("메시지: %s", best["message"])
    return best["message"]


# ── 메인 실행 ──────────────────────────────────────────────────────────────────

def run() -> bool:
    """감사 메시지 생성 + 샵 업데이트. 성공 시 True 반환."""
    shop_id = _SHOP_ID
    if not shop_id:
        logger.error("ETSY_SHOP_ID 없음 — 종료")
        return False

    logger.info("구매 감사 메시지 생성 시작 (3가지 톤 비교)")
    message = generate_best_message()
    if not message:
        _send_telegram("⚠️ 감사 메시지 생성 실패 — Groq 오류")
        return False

    try:
        from publisher.etsy_api import update_shop_sale_message
        ok = update_shop_sale_message(shop_id, message)
    except Exception as e:
        logger.error("update_shop_sale_message 예외: %s", e)
        ok = False

    if not ok:
        _send_telegram("⚠️ Etsy 감사 메시지 업데이트 실패 — API 오류")
        return False

    state = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "current_message": message,
    }
    _save_state(state)
    logger.info("상태 저장 완료")

    _send_telegram(
        f"✉️ <b>구매 감사 메시지 교체 완료</b>\n\n"
        f"<i>{message}</i>"
    )
    return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    success = run()
    print("완료" if success else "실패")
