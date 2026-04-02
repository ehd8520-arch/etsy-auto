# -*- coding: utf-8 -*-
"""
monitor/review_monitor.py — 매시간 새 리뷰 감지 → Telegram 알림 + Groq 답글 초안.

실행:
    python -m monitor.review_monitor
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

_BASE_DIR    = Path(__file__).resolve().parent.parent
_STATE_FILE  = _BASE_DIR / "db" / "review_history.json"
_TG_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT     = os.getenv("TELEGRAM_CHAT_ID", "")
_SHOP_ID     = os.getenv("ETSY_SHOP_ID", "")

MAX_RETRIES  = 3


# ── 상태 저장/로드 ─────────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            # 구 포맷 호환 (responded 키 기반 → seen_review_ids 기반)
            if "seen_review_ids" not in data:
                data["seen_review_ids"] = list(data.get("responded", {}).keys())
            return data
    except Exception:
        pass
    return {"seen_review_ids": [], "stats": {"total": 0, "replied": 0, "alerted": 0}}


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

def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
        if not resp.ok:
            logger.warning("텔레그램 전송 실패: %s", resp.text[:100])
    except Exception as e:
        logger.warning("텔레그램 예외: %s", e)


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


# ── 별점별 답글 프롬프트 ───────────────────────────────────────────────────────

_REPLY_TONE = {
    5: "enthusiastic and personal. Pick out ONE specific thing they mentioned and respond to it directly. Feel free to share a tiny moment of joy.",
    4: "warm and genuine. Acknowledge something specific they said. Keep it real — don't over-thank.",
    3: "sincere and grounded. Don't be defensive. Thank them honestly and show you heard them.",
    2: "empathetic and calm. Acknowledge the frustration without being defensive. Offer a concrete next step.",
    1: "deeply empathetic and solution-focused. Apologize sincerely. Offer a specific remedy — refund, replacement, or direct help.",
}

# Few-shot 예시: 별점별 실제 자연스러운 답글
_REPLY_EXAMPLES = {
    5: {
        "review": "Love this planner! The habit tracker is exactly what I needed.",
        "reply":  "The habit tracker is honestly my favorite section too — so glad it clicked for you! Enjoy every week 🌿",
    },
    4: {
        "review": "Really nice design, just wish it had more space for notes.",
        "reply":  "Thank you — and that's really helpful to know about the notes section. I'll look into expanding it in the next version!",
    },
    3: {
        "review": "It's fine but not quite what I expected.",
        "reply":  "I appreciate you being honest — that helps me more than you know. If you want to tell me more about what you were hoping for, I'm all ears.",
    },
    2: {
        "review": "The file wouldn't open properly on my iPad.",
        "reply":  "Oh no, I'm sorry about that! Please message me directly — I'll send you a version that works, or refund you, whichever you prefer.",
    },
    1: {
        "review": "Terrible, nothing like the pictures.",
        "reply":  "I'm really sorry this wasn't what you expected. Please reach out to me and I'll make it right — a refund or a different product, your choice.",
    },
}


def _generate_reply_draft(review_text: str, rating: int, listing_title: str) -> str | None:
    """Groq로 별점별 답글 초안 생성."""
    from config.settings import get_next_groq_key, mark_groq_key_exhausted, GROQ_BASE_URL, GROQ_MODEL

    tone = _REPLY_TONE.get(rating, _REPLY_TONE[3])
    ex   = _REPLY_EXAMPLES.get(rating, _REPLY_EXAMPLES[3])

    prompt = f"""You are a solo Etsy seller replying to a customer review. You care deeply about your buyers.

Product sold: {listing_title[:80] or "Digital Planner"}
Customer left this review: "{review_text[:300]}"

How to reply: {tone}

Here is an example of the style you should match (different product, same energy):
Customer said: "{ex['review']}"
Good reply: "{ex['reply']}"

Now write a reply to the ACTUAL review above. Do NOT copy the example.

Critical rules:
- English only, 1-3 sentences
- Pick out at least ONE specific detail from their review and react to it — this is what makes it feel human
- Do NOT start with "Thank you for your review" or "I'm glad you enjoyed" — too generic
- Do NOT mention star ratings or numbers
- Write like you're texting a friend who just told you something — genuine, not formal

Respond ONLY with this JSON (no markdown):
{{
  "reply": "the actual reply text",
  "score": {{
    "naturalness": 0-10,
    "appropriateness": 0-10,
    "empathy": 0-10
  }}
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
                    "temperature": 0.75,
                    "max_tokens": 250,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                mark_groq_key_exhausted(key)
                time.sleep(2 ** attempt)
                continue
            if not resp.ok:
                time.sleep(2 ** attempt)
                continue

            raw = resp.json()["choices"][0]["message"]["content"]
            data = _parse_json(raw)
            if not data or "reply" not in data:
                continue

            scores = data.get("score", {})
            avg = sum(scores.values()) / len(scores) if scores else 0
            logger.info("  답글 점수: %s → 평균 %.1f", scores, avg)
            return data["reply"]

        except Exception as e:
            logger.warning("Groq 예외: %s, 재시도 %d/%d", e, attempt + 1, MAX_RETRIES)
            time.sleep(2 ** attempt)

    return None


# ── 리뷰 알림 포맷 ─────────────────────────────────────────────────────────────

def _star_bar(rating: int) -> str:
    return "⭐" * rating + "☆" * (5 - rating)


def _format_review_alert(review: dict, listing_title: str = "") -> str:
    rating       = review.get("rating", 0)
    review_text  = review.get("review", "(내용 없음)")
    listing_id   = review.get("listing_id", "")
    created_ts   = review.get("create_timestamp", 0)
    created_str  = datetime.fromtimestamp(created_ts).strftime("%m/%d %H:%M") if created_ts else "?"
    listing_url  = f"https://www.etsy.com/listing/{listing_id}"
    title_line   = f"\n📦 <b>{_esc(listing_title[:60])}</b>" if listing_title else ""

    if rating <= 2:
        header = f"🚨 <b>부정 리뷰 긴급 대응 필요!</b>"
    elif rating == 3:
        header = f"😐 <b>보통 리뷰</b>"
    elif rating == 4:
        header = f"😊 <b>좋은 리뷰</b>"
    else:
        header = f"🌟 <b>5점 만점 리뷰!</b>"

    return (
        f"{header}{title_line}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{_star_bar(rating)}  <b>{rating}/5</b>  · {created_str}\n\n"
        f"💬 <i>{_esc(review_text[:300])}</i>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href='{listing_url}'>리스팅 바로가기</a>"
    )


# ── 메인 체크 ──────────────────────────────────────────────────────────────────

def check_new_reviews() -> int:
    """새 리뷰 감지 → 알림 + 초안 전송. 처리 수 반환."""
    if not _SHOP_ID:
        logger.error("ETSY_SHOP_ID 없음 — 종료")
        return 0

    try:
        from publisher.etsy_api import get_shop_reviews_list
        reviews = get_shop_reviews_list(_SHOP_ID, limit=50)
    except Exception as e:
        logger.error("리뷰 조회 예외: %s", e)
        return 0

    if not reviews:
        logger.info("리뷰 없음")
        return 0

    state    = _load_state()
    seen_ids = set(str(x) for x in state.get("seen_review_ids", []))
    new_count = 0

    for review in reviews:
        # review_id 없는 경우 listing_id + create_timestamp 조합으로 식별
        rid = str(review.get("review_id") or
                  f"{review.get('listing_id')}_{review.get('create_timestamp', 0)}")
        if rid in seen_ids:
            continue

        rating      = review.get("rating", 0)
        review_text = review.get("review", "")
        listing_id  = str(review.get("listing_id", ""))

        # 리스팅 제목 조회 (없으면 빈 문자열)
        listing_title = ""
        try:
            from publisher.etsy_api import get_listing_stats
            detail = get_listing_stats(_SHOP_ID, listing_id) or {}
            listing_title = detail.get("title", "")
        except Exception:
            pass

        logger.info("새 리뷰 감지: rating=%d, rid=%s", rating, rid)

        # ① 리뷰 알림 전송
        alert_msg = _format_review_alert(review, listing_title)
        _send_telegram(alert_msg)
        time.sleep(0.5)

        # ② Groq 답글 초안 생성
        draft = _generate_reply_draft(review_text, rating, listing_title)
        if draft:
            _send_telegram(
                f"📝 <b>답글 초안</b> — 복붙 후 바로 사용 가능\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"<i>{_esc(draft)}</i>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"⚡ Etsy에서 직접 답글 달기: https://www.etsy.com/your/shops/me/reviews"
            )
            logger.info("  답글 초안 전송 완료")
        else:
            logger.warning("  답글 초안 생성 실패")

        seen_ids.add(rid)
        new_count += 1
        time.sleep(1)

    state["seen_review_ids"] = list(seen_ids)[-500:]  # 최근 500개만 유지
    state.setdefault("stats", {})["alerted"] = state["stats"].get("alerted", 0) + new_count
    _save_state(state)

    if new_count == 0:
        logger.info("새 리뷰 없음")
    else:
        logger.info("처리 완료: %d개 리뷰 알림 전송", new_count)

    return new_count


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    count = check_new_reviews()
    print(f"새 리뷰 {count}건 처리 완료")
