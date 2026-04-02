# -*- coding: utf-8 -*-
"""
SEO Generator -- 3콜 분리 아키텍처 (타이틀 | 태그 | 설명).

Why: 한 콜에 모든 지시를 몰아넣으면 LLM이 후반부 지시를 무시.
     각 콜이 단 하나의 작업에만 집중 -> 품질 최대화.

검증 루프: 각 컴포넌트 8점 미달 시 자동 재생성 (최대 5회).
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional

from config.settings import (
    get_next_groq_key, mark_groq_key_exhausted,
    GROQ_BASE_URL, GROQ_MODEL,
    SEO_TITLE_MAX_LENGTH, SEO_TAG_COUNT, SEO_TAG_MAX_LENGTH,
    CATEGORY_EVENTS,
)
from models import Product, Category

try:
    from openai import OpenAI as _OpenAI
    _GROQ_CLIENT_AVAILABLE = True
except ImportError:
    _GROQ_CLIENT_AVAILABLE = False

try:
    from seo.keyword_research import get_top_keywords
    _KEYWORD_RESEARCH_AVAILABLE = True
except ImportError:
    _KEYWORD_RESEARCH_AVAILABLE = False


logger = logging.getLogger(__name__)

# ── 점수 기준 ──
MIN_SCORE = 8.0
MAX_ATTEMPTS = 5

# ── 카테고리별 시즌 태그 풀 (10 에버그린 + 3 시즌 로테이션) ──
# Why: 상위 1% = 에버그린 70% + 시즌 30% 전략 (eRank/Marmalead 검증)
SEASONAL_TAG_POOLS = {
    "planner": {
        "new_year":       ["2027 planner goal",   "new year planner",    "resolution tracker"],
        "dry_january":    ["dry january tracker",  "sober planner",       "sobriety challenge"],
        "valentines":     ["valentine gift print", "self care gift",      "love journal print"],
        "mothers_day":    ["gift for mom print",   "mom life planner",    "mothers day gift"],
        "nurses_week":    ["nurse week gift",       "nurse planner print", "nurse appreciation"],
        "back_to_school": ["student planner pdf",  "academic planner",    "homework planner"],
        "christmas":      ["holiday gift planner", "christmas planner",   "advent planner"],
    },
}


def _get_upcoming_event(category: Category, month: int, niche: str | None = None) -> dict | None:
    """다음 3개월 내 피크가 오는 이벤트 반환. niche가 있으면 event.niches 필터 적용."""
    cat_key = category.value
    events = CATEGORY_EVENTS.get(cat_key, [])
    for ev in events:
        diff = (ev["peak_month"] - month) % 12
        if diff <= 3:
            ev_niches = ev.get("niches")
            if ev_niches is not None:
                # 현재 니치가 이벤트 대상 niches에 없으면 건너뜀
                # (None in ev_niches = 니치 없는 generic 제품 대상)
                if niche not in ev_niches:
                    continue
            return ev
    return None


def _get_seasonal_context(category: Category, month: int,
                          niche: str | None = None) -> tuple[list[str], list[str], str]:
    """(title_keywords, seasonal_tags_3, title_angle) 반환.

    title_keywords: 제목에 넣을 시즌 각도 힌트
    seasonal_tags_3: 태그 3개 (시즌 로테이션)
    title_angle: 제목 첫 구절 뒤에 자연스럽게 삽입할 앵글
    """
    event = _get_upcoming_event(category, month, niche=niche)
    if not event:
        return [], [], ""

    cat_key = category.value
    pool = SEASONAL_TAG_POOLS.get(cat_key, {})
    tags = pool.get(event["key"], [])[:3]
    return event["keywords"][:3], tags, event.get("title_angle", "")

# ── 플래너 카테고리 예시 (fallback용) ──
CATEGORY_EXAMPLES = {
    Category.PLANNER: {
        "title": "Daily Planner PDF for Busy Moms, Undated Hyperlinked GoodNotes iPad Notability Instant Download PDF",
        "tags": ["digital planner", "printable organizer", "weekly layout", "monthly calendar",
                 "productivity tool", "tablet planner pdf", "undated planner", "digital notebook",
                 "life organizer", "habit tracker", "self care journal", "goal setting", "instant download"],
    },
}

# ── 플래너 검증된 고볼륨 태그 풀 ──
VERIFIED_TAG_POOL = {
    Category.PLANNER: [
        "digital planner", "printable planner", "daily planner pdf",
        "weekly planner", "undated planner", "tablet planner pdf",
        "habit tracker", "goal setting planner", "budget planner pdf",
        "meal planner pdf", "self care planner", "instant download",
        "digital notebook pdf", "printable organizer", "productivity planner",
        "mom planner", "adhd planner", "gratitude journal",
        "fitness planner", "life planner",
        "goodnotes planner", "ipad planner pdf", "notability planner",
        "hyperlinked planner", "digital planner pdf",
    ],
}

COMPAT_INFO = {
    Category.PLANNER: "PDF, works with GoodNotes, Notability, or print on US Letter/A4",
}

_GENERIC_SKIP = {
    "instant download", "digital download", "printable pdf", "pdf",
    "instant access", "pages", "digital file",
}

_STYLE_WORDS = {"pastel", "sage", "navy", "rose", "classic", "ocean", "blue",
                "pink", "green", "lavender", "beige", "warm", "neutral"}

# ── Dynamic Keyword Injection (DKI) ──
# Why: 1600 리스팅이 모두 같은 SEO 문구를 쓰면 Etsy 중복 페널티 위험.
#      테마 × 타입별 키워드 각도를 주입 → 각 리스팅이 고유 검색 패턴 공략.
_THEME_KEYWORD_ANGLES: dict[str, tuple[str, str]] = {
    # theme_key: (design_angle, aesthetic_phrase)
    # Keys must match PLANNER_THEMES in daily_generate.py exactly
    "sage_green":    ("minimalist wellness design",   "sage green aesthetic"),
    "pastel_pink":   ("soft feminine aesthetic",      "pastel pink planner"),
    "lavender":      ("calming lavender aesthetic",   "lavender wellness planner"),
    "warm_beige":    ("cozy boho design",             "warm beige planner"),
    "ocean_blue":    ("coastal calm design",          "ocean blue planner"),
    "dark_elegant":  ("sleek dark luxury layout",     "dark elegant planner"),
    "minimal_mono":  ("ultra minimal clean layout",   "minimalist monochrome planner"),
    "terracotta":    ("earthy boho design",           "terracotta planner"),
    "forest_green":  ("nature-inspired design",       "forest green planner"),
    "coral_peach":   ("warm sunrise energy design",   "coral peach planner"),
}

_TYPE_TITLE_ANGLES: dict[str, str] = {
    # planner_type: description angle for title variation
    "daily":         "day-by-day structure",
    "weekly":        "week-at-a-glance layout",
    "monthly":       "monthly overview calendar",
    "yearly":        "full year planning system",
    "budget":        "budget tracking made simple",
    "meal":          "meal prep and nutrition planning",
    "fitness":       "workout and fitness tracking",
    "habit_tracker": "habit stacking daily routine",
    "goal_setting":  "goal clarity and action plan",
    "gratitude":     "daily gratitude and mindset",
    "reading_log":   "reading list and book tracker",
}

_THEME_TAGS: dict[str, list[str]] = {
    # theme_key: up to 2 extra tags (injected into fixed_tags pool)
    # Keys must match PLANNER_THEMES in daily_generate.py exactly
    # All tags must be ≤20 characters (Etsy limit)
    "sage_green":    ["sage green planner", "minimalist wellness"],
    "pastel_pink":   ["pastel pink planner", "feminine planner pdf"],
    "lavender":      ["lavender planner pdf", "calming planner"],
    "warm_beige":    ["boho planner pdf", "warm beige planner"],
    "ocean_blue":    ["ocean blue planner", "coastal planner pdf"],
    "dark_elegant":  ["dark mode planner", "luxury planner pdf"],
    "minimal_mono":  ["minimal planner pdf", "modern planner pdf"],
    "terracotta":    ["terracotta planner", "earthy planner pdf"],
    "forest_green":  ["forest green planner", "nature planner pdf"],
    "coral_peach":   ["coral planner pdf", "peach planner print"],
}


def _extract_theme_key(style: str) -> str | None:
    """product.style 문자열에서 테마 키 추출.
    style 형식: {planner_type}_{theme}_{niche} (e.g. daily_sage_green_ADHD)
    테마 키는 style 내 부분문자열로 존재함.
    Why: startswith 오용 수정 — theme은 두 번째 세그먼트이므로 in 연산자 사용.
    """
    for theme in sorted(_THEME_KEYWORD_ANGLES.keys(), key=len, reverse=True):
        if theme in style:
            return theme
    return None


def _extract_type_key(style: str) -> str | None:
    """product.style에서 planner_type 키 추출."""
    for ptype in sorted(_TYPE_TITLE_ANGLES.keys(), key=len, reverse=True):
        # 타입은 theme 다음에 등장 (언더스코어 구분)
        if f"_{ptype}" in style or style == ptype:
            return ptype
    return None


# ══════════════════════════════════════════════
# LLM 호출 레이어
# ══════════════════════════════════════════════

def _call_llm(prompt: str, attempt: int = 0, json_mode: bool = False) -> str:
    """Groq llama-3.3-70b-versatile 전용 (10계정 429 자동 순환).

    429 → 해당 키 소진 등록 → 다음 키로 재시도 (최대 계정 수만큼).
    전 계정 소진 시 RuntimeError.
    """
    if not _GROQ_CLIENT_AVAILABLE:
        raise RuntimeError("openai 패키지 없음 — pip install openai")

    from config.settings import GROQ_API_KEYS
    n_keys = len(GROQ_API_KEYS)
    if n_keys == 0:
        raise RuntimeError("GROQ_API_KEY_1~10 미설정 — .env 확인")

    last_key = None
    for _ in range(n_keys):
        key = get_next_groq_key()
        if not key or key == last_key:
            continue
        last_key = key
        try:
            client = _OpenAI(api_key=key, base_url=GROQ_BASE_URL)
            kwargs = dict(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content.strip()
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                logger.warning("Groq 키 429 — 다음 키로 순환: %s", err_str[:80])
                mark_groq_key_exhausted(key)
                continue
            logger.warning("Groq 호출 오류: %s", err_str[:120])
            raise

    raise RuntimeError("Groq 전 계정 429 소진 — 잠시 후 재시도 필요")


# ══════════════════════════════════════════════
# 헬퍼
# ══════════════════════════════════════════════

def _get_trending_keywords(category: Category, n: int = 8) -> list[str]:
    if not _KEYWORD_RESEARCH_AVAILABLE:
        return []
    try:
        return get_top_keywords(category, n=n, max_competition="medium")
    except Exception as e:
        logger.warning("Keyword research unavailable: %s", e)
        return []


def _primary_search_phrase(product: Product, verified_pool: list[str]) -> str:
    kws_lower = [k.lower() for k in product.keywords
                 if k.lower() not in _GENERIC_SKIP and "pages" not in k.lower()]
    kw_words = set(w for k in kws_lower for w in k.split())

    def _pool_score(tag: str) -> int:
        if tag.lower() in _GENERIC_SKIP:
            return -1
        return sum(1 for w in tag.lower().split() if w in kw_words)

    pool_sorted = sorted(verified_pool, key=_pool_score, reverse=True)
    for v in pool_sorted:
        if _pool_score(v) >= 2 and v.lower() not in _GENERIC_SKIP:
            return v.title()

    for k in kws_lower:
        if 2 <= len(k.split()) <= 4:
            return k.title()

    defaults = {
        Category.WORKSHEET:             "Printable Worksheet",
        Category.PLANNER:               "Printable Planner PDF",
        Category.SPREADSHEET:           "Budget Spreadsheet Template",
        Category.WALL_ART:              "Printable Wall Art",
        Category.SOCIAL_MEDIA_TEMPLATE: "Social Media Template Bundle",
        Category.RESUME_TEMPLATE:       "Resume Template Bundle",
    }
    return defaults.get(product.category, "Printable PDF")


# ══════════════════════════════════════════════
# 콜 1 -- 타이틀 생성
# ══════════════════════════════════════════════

_NICHE_PERSONA: dict[str, str] = {
    "ADHD":              "people with ADHD who struggle with focus and time management",
    "anxiety":           "people managing anxiety who need gentle, calming structure",
    "christian":         "faith-based women who want to plan with Scripture and prayer",
    "sobriety":          "people in recovery who want to track their sober journey",
    "mom":               "busy moms juggling family, kids, and their own self-care",
    "homeschool":        "homeschool parents planning curriculum and daily lessons",
    "self_care":         "women prioritizing their wellness, rituals, and self-love",
    "nurse":             "nurses and healthcare workers with demanding shift schedules",
    "teacher":           "teachers who need to manage lessons, students, and self-care",
    "pregnancy":         "expecting moms tracking their pregnancy week by week",
    "entrepreneur":      "entrepreneurs and side hustlers scaling their business",
    "perimenopause":     "women navigating perimenopause symptoms and hormonal changes",
    "cycle_syncing":     "women who want to sync their schedule with their menstrual cycle",
    "caregiver":         "family caregivers balancing loved one's needs with their own",
    "glp1":              "people on GLP-1 medication tracking their wellness journey",
    "ADHD_teacher":      "teachers with ADHD managing classrooms and their own focus",
    "ADHD_nurse":        "nurses with ADHD staying safe and organized on demanding shifts",
    "christian_teacher": "faith-based teachers who teach with purpose and prayer",
    "sobriety_mom":      "moms in recovery balancing sobriety milestones and family life",
}


def _gen_title(product: Product, primary_phrase: str,
               seasonal_kws: list[str], seasonal_angle: str, examples: dict,
               attempt: int = 0, feedback: str = "") -> str:
    page_count = next((k for k in product.keywords if "pages" in k.lower()), "")
    style = product.style.replace("_", " ")
    feedback_block = f"\nPrevious attempt was rejected. Fix these issues:\n{feedback}\n" if feedback else ""

    seasonal_block = ""
    if seasonal_angle:
        seasonal_block = f'- Seasonal angle to include naturally in middle clause: "{seasonal_angle}"'
    elif seasonal_kws:
        seasonal_block = f'- Weave in ONE seasonal keyword naturally: {", ".join(seasonal_kws[:2])}'

    # 니치 페르소나 감지 → 제목에 타깃 독자 명시
    persona_block = ""
    for niche in sorted(_NICHE_PERSONA, key=len, reverse=True):  # 긴 것 먼저 → 더블니치 우선
        if product.style.endswith(f"_{niche}"):
            persona_block = f'- Target audience (weave naturally after primary phrase): "{_NICHE_PERSONA[niche]}"'
            break

    # DKI: 테마 × 타입별 제목 각도 주입 → 리스팅마다 고유 검색 패턴 공략
    dki_block = ""
    _theme_key = _extract_theme_key(product.style)
    _type_key  = _extract_type_key(product.style)
    _dki_parts = []
    if _theme_key and _theme_key in _THEME_KEYWORD_ANGLES:
        _design_angle, _ = _THEME_KEYWORD_ANGLES[_theme_key]
        _dki_parts.append(f'design style = "{_design_angle}"')
    if _type_key and _type_key in _TYPE_TITLE_ANGLES:
        _dki_parts.append(f'layout angle = "{_TYPE_TITLE_ANGLES[_type_key]}"')
    if _dki_parts:
        dki_block = (
            f'- REQUIRED: Rephrase ONE of these angles into your benefit clause '
            f'(paraphrase — never copy word-for-word, make it flow naturally): '
            f'{"; ".join(_dki_parts)}'
        )

    # Category-specific title suffix
    _title_suffix = {
        Category.SOCIAL_MEDIA_TEMPLATE: "PNG Bundle",
        Category.WALL_ART: "Instant Download",
    }
    title_end = _title_suffix.get(product.category, "PDF")

    prompt = f"""Generate ONE Etsy listing title. Return ONLY the title text, no quotes, no explanation.
{feedback_block}
MUST start with exactly: "{primary_phrase}"
Format: {primary_phrase} for [Target Persona], [Emotional Benefit or Niche Qualifier], [Secondary Keyword] {title_end}

Rules (ALL must be followed):
- FIRST 40 CHARACTERS = primary search keyword (already set by starting with "{primary_phrase}")
- After the first 40 chars: write in natural, conversational language — maximum 2 commas total
- MUST include AT LEAST 1 COMMA to separate main keyword from benefit (e.g. "Keyword for Audience, Benefit PDF")
- MUST include "for [specific audience]" (e.g. "for Busy Moms", "for People with ADHD", "for Teachers")
- Use "long-tail sandwich": [Main keyword] + for [Audience] + [Emotional benefit] + {title_end}
- TOTAL LENGTH: 80-140 characters (HARD REQUIREMENT)
- Last word(s) must be "{title_end}"
- No color/style/theme words (pastel, sage, navy, pink, classic, ocean)
- No banned phrases: Best Seller, Sale, Free Shipping, Limited Time
- No trademarked brand names: Canva, Kindle (GoodNotes, Notability, iPad는 허용 — Etsy 베스트셀러 표준)
{persona_block}
{seasonal_block}
{dki_block}

Product:
- Category: {product.category.value}
- Type: {style}
{f'- Pages: {page_count}' if page_count else ''}

Example (same format):
{examples['title']}

Title:"""

    raw = _call_llm(prompt, attempt=attempt).strip().strip('"').strip("'")
    for prefix in ["Title:", "title:", "TITLE:"]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()
    return raw


# ══════════════════════════════════════════════
# 콜 2 -- 태그 생성
# ══════════════════════════════════════════════

def _gen_tags(product: Product, title: str, verified_pool: list[str],
              seasonal_tags: list[str], trending_kws: list[str],
              attempt: int = 0, feedback: str = "") -> list[str]:
    """에버그린 9개(LLM 선택) + 시즌/테마/니치 4개(알고리즘 고정) = 13태그.
    Why: LLM이 시즌/니치 태그 선택하면 품질 불안정 -> 알고리즘이 직접 삽입.
         DKI 테마 태그 1개 추가 → 리스팅마다 고유 검색 패턴 공략.
    """
    # 니치별 고정 태그 (gift 키워드 등 전환율 높은 태그)
    _NICHE_BONUS_TAGS: dict[str, list[str]] = {
        "pregnancy":        ["baby shower gift", "pregnancy journal", "new mom gift"],
        "mom":              ["gift for mom", "mom gift idea", "mother gift"],
        "nurse":            ["nurse gift idea", "gift for nurse", "nursing school gift"],
        "teacher":          ["teacher gift idea", "gift for teacher", "end of year gift"],
        "christian":        ["christian gift idea", "faith gift for her", "prayer journal gift"],
        "sobriety":         ["sobriety gift", "recovery gift idea", "sober anniversary gift"],
        "sobriety_mom":     ["sobriety mom planner", "recovery mom gift", "aa 12 steps planner"],
        "caregiver":        ["caregiver gift idea", "gift for caregiver", "caregiver support"],
        "ADHD":             ["adhd gift idea", "adhd awareness gift", "adhd planner gift"],
        "anxiety":          ["anxiety relief gift", "mental health gift", "self care gift idea"],
        "entrepreneur":     ["boss babe gift", "entrepreneur gift idea", "business owner gift"],
        "perimenopause":    ["menopause gift idea", "hormone health gift", "midlife wellness gift"],
        "glp1":             ["weight loss journal", "wellness gift for her", "healthy lifestyle gift"],
        "cycle_syncing":    ["cycle syncing journal", "hormone health gift"],
        "homeschool":       ["homeschool gift idea", "gift for homeschool"],
        "self_care":        ["self care gift idea", "wellness gift idea"],
        "ADHD_teacher":     ["adhd teacher gift", "teacher gift idea"],
        "ADHD_nurse":       ["adhd nurse gift", "nurse gift idea"],
        "christian_teacher":["christian teacher gift", "faith teacher gift"],
    }
    _style = product.style or ""
    _known_niches_bonus = sorted(_NICHE_BONUS_TAGS.keys(), key=len, reverse=True)
    _niche_bonus: list[str] = []
    for _nk in _known_niches_bonus:
        if _style.endswith("_" + _nk) or _style == _nk:
            _niche_bonus = [t.lower()[:SEO_TAG_MAX_LENGTH] for t in _NICHE_BONUS_TAGS[_nk]][:2]
            break

    seasonal_clean = [t.lower()[:SEO_TAG_MAX_LENGTH] for t in seasonal_tags if t][:3]

    # DKI 테마 태그 — 테마별 1개 최대 주입 (고정 슬롯 4개로 확장)
    # Why: 13 태그 중 4개 고정 = 에버그린 9개 LLM 선택 → 중복 위험 없이 테마 차별화
    _theme_key_tag = _extract_theme_key(_style)
    _theme_bonus: list[str] = []
    if _theme_key_tag and _theme_key_tag in _THEME_TAGS:
        _theme_bonus = [t.lower()[:SEO_TAG_MAX_LENGTH] for t in _THEME_TAGS[_theme_key_tag]][:1]

    # 시즌(우선) + 테마 + 니치 합산 → 최대 4개 고정 (총 13태그 = LLM 9 + 고정 4)
    fixed_tags = (seasonal_clean + _theme_bonus + _niche_bonus)[:4]
    n_evergreen = SEO_TAG_COUNT - len(fixed_tags)
    _fixed_set = set(fixed_tags)
    pool_str = "\n".join(f"  {t}" for t in verified_pool[:25] if t not in _fixed_set)
    trending_str = ", ".join(trending_kws[:4]) if trending_kws else "none"
    feedback_block = f"\nPrevious attempt failed. Fix these:\n{feedback}\n" if feedback else ""

    prompt = f"""Select exactly {n_evergreen} evergreen Etsy tags. Return ONLY a JSON array of strings.
{feedback_block}
Product title: "{title}"
Product type: {product.category.value}
Product keywords: {", ".join(product.keywords[:5])}

Choose ONLY from this list -- copy EXACT phrases word for word:
{pool_str}

Trending (use if relevant): {trending_str}

Rules:
- Exactly {n_evergreen} tags
- All lowercase, max 20 characters each
- Most relevant FIRST
- EXACT copy only -- wrong: "preschool", right: "preschool printable"
- Tag mix ratio 3:7 = 3 broad high-volume tags (e.g. "wall art print", "instant download", "home decor print") + 7 niche long-tail tags (e.g. "minimalist line art", "nursery wall decor", "gallery wall set")
- NO duplicate words across tags (e.g. don't use both "wall art print" and "printable wall art")

Return (JSON array only):
["tag1", "tag2", ..., "tag{n_evergreen}"]"""

    raw = _call_llm(prompt, attempt=attempt).strip()
    arr_match = re.search(r'\[[\s\S]*?\]', raw)
    evergreen = []
    if arr_match:
        try:
            parsed = json.loads(arr_match.group(0))
            evergreen = [str(t).strip().lower() for t in parsed if t]
        except Exception:
            pass
    if not evergreen:
        evergreen = [l.strip().strip('",').lower() for l in raw.split("\n") if l.strip().strip('",')]

    return (evergreen[:n_evergreen] + fixed_tags)[:SEO_TAG_COUNT]


# ══════════════════════════════════════════════
# 콜 3 -- 설명 생성
# ══════════════════════════════════════════════

COMPAT_DETAIL = {
    Category.WORKSHEET: "PDF (US Letter 8.5x11 + A4 included) -- print at home or any print shop, laminate-friendly",
    Category.PLANNER:   "PDF -- works with GoodNotes 5, Notability, iPad, Android tablets, or print on US Letter/A4",
    Category.SPREADSHEET: "Google Sheets (link delivered via PDF) + Microsoft Excel .xlsx -- auto-calculating formulas, no macros needed",
    Category.WALL_ART:  "High-resolution 300 DPI JPG files -- print at home, Walgreens, Staples, CVS, or any professional print shop. Sizes included: 5x7, 8x10, 11x14, A4, A3. Please note: printed colors may vary slightly depending on your monitor settings and printer. We recommend using a print shop for best color accuracy.",
    Category.SOCIAL_MEDIA_TEMPLATE: "ZIP bundle: 75 high-res PNG templates -- 30x Instagram Post (1080x1080) + 10x Pinterest Pin (1000x1500) + 15x Instagram Story (1080x1920) + 10x TikTok/Reels (1080x1920) + 5x Facebook (1200x628) + 5x LinkedIn (1200x628) + Bonus: Brand Kit PNG, Content Calendar, Canva Guide",
    Category.RESUME_TEMPLATE: "ZIP bundle: DOCX (editable in Microsoft Word + Google Docs) + PDF (print-ready) + Cover Letter DOCX + References page + Resume Guide TXT -- ATS-friendly single-column layout, 3 industry versions",
}

USAGE_RIGHTS = {
    Category.WORKSHEET:    "For personal and classroom use only. Not for resale or redistribution.",
    Category.PLANNER:      "For personal use only. Not for resale.",
    Category.SPREADSHEET:           "For personal or single-business use only. Not for resale or redistribution.",
    Category.WALL_ART:              "For personal use only. Print for your own home. Not for commercial resale.",
    Category.SOCIAL_MEDIA_TEMPLATE: "Personal and small business commercial use license included. Not for resale as templates.",
    Category.RESUME_TEMPLATE:       "For personal use only. Use to apply for your own job positions. Not for resale.",
}


def _gen_description(product: Product, title: str, compat: str,
                     seasonal_kws: list[str], attempt: int = 0, feedback: str = "") -> str:
    page_count = next((k for k in product.keywords if "pages" in k.lower()), "")
    feedback_block = f"\nPrevious attempt failed. Fix these:\n{feedback}\n" if feedback else ""
    compat_detail = COMPAT_DETAIL.get(product.category, compat)
    usage_rights  = USAGE_RIGHTS.get(product.category, "For personal use only.")

    hook_examples = {
        Category.WORKSHEET:            "Stop searching -- this {pages}printable bundle is ready as an instant download today.",
        Category.PLANNER:              "Get organized today -- this undated printable planner is an instant download, ready for GoodNotes or print.",
        Category.SPREADSHEET:          "Take control of your finances -- this auto-calculating spreadsheet is an instant download, open in Google Sheets today.",
        Category.WALL_ART:             "Transform your walls today -- this 300 DPI printable art is an instant download, ready to print and frame in minutes.",
        Category.SOCIAL_MEDIA_TEMPLATE: "Level up your feed today -- this 75-template PNG bundle is an instant download, ready to post on Instagram, TikTok, Pinterest, LinkedIn, and Stories.",
        Category.RESUME_TEMPLATE:      "Land your next job today -- this ATS-friendly resume bundle is an instant download, ready to customize and send.",
    }
    hook_tmpl = hook_examples.get(product.category, "Premium instant download, ready to use today.")
    hook_ex = hook_tmpl.format(pages=f"{page_count} " if page_count else "")

    seasonal_line = f"Seasonal use case: {', '.join(seasonal_kws[:2])}" if seasonal_kws else ""

    # 카테고리+타입별 실제 스펙 (LLM 숫자 날조 방지)
    _PLANNER_TYPE_SPECS = {
        "daily": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 153 pages total
- Sections: 2 Yearly Overview, 1 Vision Board, 12 Monthly Calendars, 12 Monthly Reviews, 52 Weekly Planners, 52 Daily Pages, 6 Habit Trackers, 1 Mood Tracker, 10 Notes pages
- Daily page layout: Top 3 Priorities + hourly Schedule (6AM-9PM) + To-Do checklist + Notes
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
        "weekly": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 102 pages total
- Sections: 2 Yearly Overview, 1 Vision Board, 12 Monthly Calendars, 12 Monthly Reviews, 52 Weekly Spreads, 6 Habit Trackers, 15 Notes pages
- Weekly spread: Mon-Sun columns + Goals box + Top Priorities + Week reflection
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
        "budget": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 62 pages total
- Sections: 2 Yearly Overview, 12 Monthly Calendars, 24 Budget Pages (Income + Expenses + Savings), 12 Monthly Reviews, 10 Notes pages
- Budget page layout: Income tracker + 8 expense categories + Savings goal + Net balance
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
        "meal": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 65 pages total
- Sections: 1 Yearly Overview, 52 Weekly Meal Spreads, 10 Notes pages
- Each weekly spread: Breakfast/Lunch/Dinner/Snack for Mon-Sun + Grocery List section
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
        "habit_tracker": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 60 pages total
- Sections: 2 Yearly Overview, 12 Monthly Calendars, 24 Habit Tracker pages (10 habits x 31 days), 12 Monthly Reviews, 8 Notes pages
- Habit tracker: 10 custom habits per month + 31-day checkbox grid
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
        "gratitude": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 110 pages total
- Sections: 1 Vision Board, 1 Yearly Overview, 90 Daily Gratitude pages, 6 Monthly Reviews, 10 Notes pages
- Daily page: 3 Gratitude prompts + What would make today great + Daily affirmation + Evening reflection
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
        "goal_setting": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 41 pages total
- Sections: 2 Vision Board, 2 Yearly Overview, 6 Monthly Planners, 13 Weekly Planners, 3 Project Trackers, 3 Habit Trackers, 10 Notes pages
- Goal page: Annual goals x 5 life areas + quarterly milestones + weekly action steps
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
        "fitness": """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 97 pages total
- Sections: 2 Yearly Overview, 1 Vision Board, 2 Body Measurement pages, 12 Monthly Calendars, 52 Workout Logs, 6 Habit Trackers, 12 Monthly Reviews, 8 Notes pages
- Workout log: 8 exercises x 7 days (sets/reps/weight) + Cardio log (distance/time/calories)
- Body measurement: Weight + chest + waist + hips + bicep + thigh x 12 months + progress photos
- Undated -- works for any year
- Both US Letter (8.5x11) and A4 sizes included""",
    }
    _PLANNER_TYPE_HOOKS = {
        "daily":        "Get organized today -- this undated daily planner is an instant download, ready for GoodNotes or print.",
        "weekly":       "Plan your whole year today -- this 52-week undated planner is an instant download, open in GoodNotes or print.",
        "budget":       "Take control of your money today -- this undated budget planner is an instant download, ready to track every dollar.",
        "meal":         "Meal prep made easy -- this 52-week meal planner is an instant download, ready to plan your whole year of dinners.",
        "habit_tracker":"Build better habits today -- this 12-month habit tracker is an instant download, start your streak this week.",
        "gratitude":    "Start your gratitude practice today -- this 90-day mindfulness journal is an instant download, ready to transform your mindset.",
        "goal_setting": "Crush your goals today -- this 90-day goal planner is an instant download, map your vision to daily action steps.",
        "fitness":      "Hit your fitness goals today -- this 12-month workout planner is an instant download, track every rep and every inch.",
    }
    _PLANNER_TYPE_COMPAT = {
        "daily":        "PDF -- works with GoodNotes 5, Notability, iPad, Android tablets, or print on US Letter/A4",
        "weekly":       "PDF -- works with GoodNotes 5, Notability, iPad, Android tablets, or print on US Letter/A4",
        "budget":       "PDF -- print on US Letter/A4, or use with GoodNotes / Notability on iPad",
        "meal":         "PDF -- print on US Letter/A4, or annotate digitally in GoodNotes / Notability",
        "habit_tracker":"PDF -- works with GoodNotes 5, Notability, iPad, or print on US Letter/A4",
        "gratitude":    "PDF -- print on US Letter/A4, or use with GoodNotes / Notability on iPad",
        "goal_setting": "PDF -- works with GoodNotes 5, Notability, iPad, Android tablets, or print on US Letter/A4",
        "fitness":      "PDF -- print on US Letter/A4, or annotate digitally in GoodNotes / Notability on iPad",
    }

    # Detect planner type + niche from product.style
    # format: "{planner_type}_{theme_name}" or "{planner_type}_{theme_name}_{niche}"
    _known_planner_types = list(_PLANNER_TYPE_SPECS.keys())
    _known_niches = sorted([
        "ADHD", "anxiety", "christian", "sobriety",
        "mom", "homeschool", "self_care", "nurse",
        "teacher", "pregnancy", "entrepreneur",
        # 더블니치 (경쟁 극소 ★★★)
        "ADHD_teacher", "ADHD_nurse", "christian_teacher", "sobriety_mom",
        # 2024-2025 트렌드 (경쟁 거의없음 ★★★)
        "perimenopause", "cycle_syncing", "caregiver", "glp1",
    ], key=len, reverse=True)  # 긴 것(더블니치) 먼저 → sobriety_mom이 mom보다 먼저 매칭
    detected_planner_type = next(
        (pt for pt in _known_planner_types if product.style.startswith(pt)), None
    )
    detected_niche = next(
        (n for n in _known_niches if product.style.endswith(f"_{n}")), None
    )

    # 니치별 훅/설명 오버라이드
    _NICHE_HOOKS = {
        "ADHD":        "Finally, a planner designed FOR your ADHD brain -- this instant download gives you time blocks, task breakdowns, and dopamine-boosting streaks.",
        "anxiety":     "Quiet the overwhelm -- this calming instant-download planner gives you gentle structure, breathing space, and daily grounding to ease anxiety.",
        "christian":   "Plan your days with faith at the center -- this Scripture-inspired instant download includes prayer logs, Bible reading streaks, and daily gratitude.",
        "sobriety":    "Honor every sober day -- this instant-download recovery planner tracks your streaks, triggers, and wins to keep your momentum strong.",
        "mom":         "Mom life, organized -- this instant-download family planner keeps meals, schedules, and your precious me-time all in one beautiful place.",
        "homeschool":  "Homeschool with confidence -- this instant-download curriculum planner organizes lessons, subjects, and learning goals for every child.",
        "self_care":   "Put yourself first -- this instant-download self-care planner builds your morning ritual, wellness habits, and glow-up routine day by day.",
        "nurse":       "Made for nurses, by design -- this instant-download shift planner fits your healthcare life with patient notes, medication logs, and self-care space.",
        "teacher":     "The teacher planner your classroom deserves -- this instant download covers lesson plans, grade tracking, and parent communication all year long.",
        "pregnancy":   "Cherish every bump moment -- this instant-download pregnancy planner tracks appointments, symptoms, baby prep, and your journey week by week.",
        "entrepreneur":     "Run your empire -- this instant-download boss planner tracks revenue goals, client notes, daily tasks, and CEO habits to grow your business.",
        # 더블니치
        "ADHD_teacher":     "ADHD brain meets classroom — finally a planner built for neurodivergent educators with time-blocked lessons, transition cues, and a brain-dump space.",
        "ADHD_nurse":       "ADHD on the floor — this shift planner gives neurodivergent nurses time-boxed tasks, handoff checklists, and a guilt-free brain-dump to stay safe and sane.",
        "christian_teacher":"Teach with purpose and prayer — this faith-filled classroom planner weaves Scripture, student prayer logs, and grace-first lesson planning into every page.",
        "sobriety_mom":     "Sober and thriving as a mom — this instant download tracks your recovery days, family wins, and the small brave moments that prove you are exactly the mom your kids need.",
        # 2024-2025 트렌드
        "perimenopause":    "Your body is changing — this hormone-friendly planner tracks symptoms, energy windows, HRT logs, and daily self-compassion to navigate perimenopause with confidence.",
        "cycle_syncing":    "Work with your cycle, not against it — this phase-aligned planner maps your energy, nutrition, and tasks to each phase of your menstrual cycle.",
        "caregiver":        "You give so much — this caregiver planner holds space for their needs AND yours, with care schedules, medication logs, and daily reminders that you are enough.",
        "glp1":             "Your GLP-1 journey deserves a plan — track injections, protein goals, non-scale victories, and weekly progress in this wellness-first instant-download planner.",
    }
    _NICHE_AUDIENCE = {
        "ADHD":        "Designed specifically for ADHD and neurodivergent brains. Time-blocking layouts, short task lists, and visual progress trackers reduce executive function load.",
        "anxiety":     "Designed for anxiety management and mental wellness. Gentle structure, worry-release prompts, and calming daily rituals to reduce overwhelm.",
        "christian":   "Designed for faith-based planning. Scripture reflection, prayer tracking, and gratitude journaling woven into every page.",
        "sobriety":    "Designed for recovery and sober living. Day-count tracking, trigger logs, and meeting reminders to support your sobriety journey.",
        "mom":         "Designed for busy moms. Family schedule, meal planning, kids activities, and dedicated me-time blocks -- all in one place.",
        "homeschool":  "Designed for homeschool families. Curriculum tracking, lesson scheduling, and individual subject logs for multiple children.",
        "self_care":   "Designed for your wellness journey. Morning rituals, body check-ins, gratitude prompts, and wind-down routines for whole-person care.",
        "nurse":       "Designed for nurses and healthcare workers. Shift scheduling, patient note space, medication log, and self-care tracker for demanding work lives.",
        "teacher":     "Designed for educators. Lesson plan templates, grade tracker, parent communication log, and classroom routine planner for a smooth school year.",
        "pregnancy":   "Designed for expecting moms. Week-by-week tracking, appointment log, symptom notes, baby prep checklist, and birth plan pages.",
        "entrepreneur":     "Designed for entrepreneurs and side hustlers. Revenue tracking, client notes, daily CEO habits, and income goals to scale your business.",
        # 더블니치
        "ADHD_teacher":     "Designed for teachers with ADHD. ADHD-friendly time blocks for lessons, transition cue reminders, end-of-day desk-reset checklists, and a brain-dump section to offload working memory.",
        "ADHD_nurse":       "Designed for nurses with ADHD. Shift-safe task prioritization, visual pre-shift checklists, hyperfocus break reminders, and post-shift decompression prompts.",
        "christian_teacher":"Designed for faith-based educators. Daily Scripture reflection, prayer over students, grace-first classroom management notes, and a weekly surrender practice.",
        "sobriety_mom":     "Designed for moms in recovery. Dual-track layout: sobriety milestones AND family wins, trigger check-ins, sponsor contact reminders, and quality-time logs with kids.",
        # 2024-2025 트렌드
        "perimenopause":    "Designed for women navigating perimenopause. Symptom logging (hot flashes, brain fog, mood, sleep), HRT tracking, hormone-supportive habit reminders, and self-compassion daily.",
        "cycle_syncing":    "Designed for cycle-syncing practitioners. Phase tracker (Menstrual/Follicular/Ovulatory/Luteal), phase-aligned nutrition and movement cues, seed cycling log, and cycle wisdom journal.",
        "caregiver":        "Designed for family caregivers. Care schedule coordination, medication management tracker, respite break reminders, emotional check-ins, and affirming daily self-care space.",
        "glp1":             "Designed for GLP-1 medication users. Injection day tracker, protein and hydration goals, hunger/fullness scale, non-scale victory log, and weekly wellness reflection.",
    }
    if detected_niche:
        hook_tmpl = _NICHE_HOOKS.get(detected_niche, hook_tmpl)

    _category_specs = {
        Category.SOCIAL_MEDIA_TEMPLATE: """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 75 PNG templates total
- 30 Instagram Posts (1080x1080 px)
- 15 Instagram Stories (1080x1920 px)
- 10 Pinterest Pins (1000x1500 px)
- 10 TikTok/Reels covers (1080x1920 px)
- 5 Facebook covers (1200x628 px)
- 5 LinkedIn banners (1200x628 px)
- Bonus files: Brand Kit PNG, 30-day Content Calendar, Canva How-To Guide
- High-res PNG, ready to post immediately""",
        Category.WALL_ART: """ACTUAL PRODUCT SPECS (use these EXACT numbers -- do NOT invent others):
- 9 unique designs
- 45 JPG files total (9 designs x 5 sizes)
- Sizes: 5x7, 8x10, 11x14, A4, A3
- 300 DPI print-ready resolution
- CMYK + RGB color profiles included""",
    }
    niche_audience_block = ""
    if product.category == Category.PLANNER and detected_planner_type:
        spec_block = _PLANNER_TYPE_SPECS[detected_planner_type]
        compat_detail = _PLANNER_TYPE_COMPAT.get(detected_planner_type, compat_detail)
        if not detected_niche:
            hook_tmpl = _PLANNER_TYPE_HOOKS.get(detected_planner_type, hook_tmpl)
        hook_ex = hook_tmpl
        if detected_niche:
            niche_audience_block = f"\nNICHE AUDIENCE (must appear in description):\n{_NICHE_AUDIENCE.get(detected_niche, '')}"
    else:
        spec_block = _category_specs.get(product.category, "")

    prompt = f"""Write an Etsy product description. Plain text only -- no markdown, no asterisks, no # headers.
{feedback_block}
Product: {title}
Format: {compat_detail}
{f'Pages: {page_count}' if page_count else ''}
{seasonal_line}
{spec_block}{niche_audience_block}

EXACT structure to follow:

[HOOK: 1-2 sentences, max 155 chars]
Lead with buyer desire. Include "instant download". No generic phrases.
Example: "{hook_ex}"

KEY FEATURES:
v [Feature with EXACT number from the specs above -- do NOT invent numbers]
v [Feature with EXACT number from the specs above -- do NOT invent numbers]
v [Feature with EXACT number from the specs above -- do NOT invent numbers]
v [Feature with EXACT number from the specs above -- do NOT invent numbers]
v [Feature with EXACT number from the specs above -- do NOT invent numbers]

WHY CHOOSE US?
[2-3 sentences. Focus on: no-fuss instant delivery, print-from-home convenience, and one specific differentiator (e.g., 3 difficulty levels, undated so it works any year, auto-calculating formulas). Make it feel like a real human seller who stands behind the product -- not corporate copy.]

WHAT'S INCLUDED:
- {compat_detail}
{f'- {page_count.title()} of printable content' if page_count else ''}

HOW TO USE:
1. Purchase and receive instant download link in your Etsy account
2. [Specific open/print/setup step for this product type]
3. [Specific outcome or benefit the buyer gets]

SATISFACTION GUARANTEE:
We stand behind every product. If you have any issues with your download, contact us and we will make it right -- 100% satisfaction is our priority.

FAQ:
Q: Will I receive a physical product?
A: No -- this is a digital download only. You will receive an instant download link in your Etsy account after purchase.
Q: [Most relevant question for this product type -- e.g. "What software do I need?" or "Can I print at a local print shop?"]
A: [Specific, helpful answer with software names or service names]

This is a DIGITAL DOWNLOAD. No physical item will be shipped.
{usage_rights}

Length: 1100-1500 chars total. Each bullet = 1 full sentence with a concrete detail.
"""

    desc = _call_llm(prompt, attempt=attempt).strip()

    # ── 후처리: 점수 필수 항목 보장 ──
    desc_lower = desc.lower()

    # 1. 훅(첫 155자)에 instant download 없으면 맨 앞에 삽입
    if "instant download" not in desc_lower[:155] and "digital download" not in desc_lower[:155]:
        desc = "Get instant access with this instant download. " + desc

    # 2. 본문에 digital download + no physical 고지 없으면 끝에 추가
    if "digital download" not in desc_lower or "no physical" not in desc_lower:
        desc = desc.rstrip() + "\n\nThis is a DIGITAL DOWNLOAD. No physical item will be shipped."

    # 3. 이용권 미명시면 끝에 추가
    if not any(p in desc_lower for p in ["personal use", "for personal", "not for resale"]):
        desc = desc.rstrip() + "\n" + usage_rights

    return desc


# ══════════════════════════════════════════════
# 채점 함수
# ══════════════════════════════════════════════

def score_title(title: str, primary_phrase: str, product: Product) -> dict:
    score = 0
    issues = []

    # Hard-fail: too short (80자 미만이면 강제 재시도)
    if len(title) < 80:
        return {"score": 0, "max": 10, "issues": [f"제목 너무 짧음: {len(title)}자 (목표 80-140). 학년/대상/이벤트/bundle 단어 추가 필요"]}

    # Hard-fail: primary phrase not in first 40 chars (Etsy SEO critical)
    if primary_phrase.lower() not in title.lower()[:50]:
        return {"score": 0, "max": 10, "issues": [f"'{primary_phrase}' 첫 50자 안에 없음 -- Etsy 랭킹 불가"]}

    # 1. primary_phrase로 시작 (2pts)
    if title.lower().startswith(primary_phrase.lower()):
        score += 2
    else:
        issues.append(f"'{primary_phrase}'로 시작 안 함 (실제: '{title[:40]}')")

    # 2. 길이 80-140 (2pts)
    if 80 <= len(title) <= 140:
        score += 2
    elif 60 <= len(title) < 80 or 140 < len(title) <= 155:
        score += 1
        issues.append(f"길이 {len(title)}자 (목표 80-140)")
    else:
        issues.append(f"길이 오류: {len(title)}자")

    # 3. 콤마 구분 + 최대 2개 + 콜론/파이프 없음 (1pt)
    # Why: Etsy 제목 구조 = [키워드], [혜택], [suffix] — 콤마 3개+ 는 난잡해 보임
    comma_count = title.count(",")
    if "," in title and ":" not in title and " | " not in title and comma_count <= 2:
        score += 1
    else:
        if comma_count > 2:
            issues.append(f"콤마 {comma_count}개 (최대 2개 — 구조: [키워드], [혜택], PDF)")
        elif ":" in title:
            issues.append("콜론 사용 금지 (Etsy 랭킹 불이익)")
        elif " | " in title:
            issues.append("파이프 사용 금지 (Etsy 랭킹 불이익)")
        else:
            issues.append("콤마 없음 — 자연스러운 문장 구분 필요")

    # 4. 카테고리별 올바른 suffix로 끝 (1pt)
    _expected_suffix = {
        Category.SOCIAL_MEDIA_TEMPLATE: "PNG BUNDLE",
        Category.WALL_ART: "INSTANT DOWNLOAD",
    }
    expected_end = _expected_suffix.get(product.category, "PDF")
    if title.strip().upper().endswith(expected_end):
        score += 1
    else:
        issues.append(f'"{expected_end}"로 끝나지 않음 (실제: "{title.strip()[-20:]}")')

    # 5. 금지 단어 없음 (1pt)
    banned = ["best seller", "free shipping", "limited time"]
    if not any(b in title.lower() for b in banned):
        score += 1
    else:
        issues.append(f"금지 단어: {[b for b in banned if b in title.lower()]}")

    # 6. 첫 구절에 스타일 단어 없음 (2pts)
    first_clause = title.split(",")[0].lower()
    found_style = [s for s in _STYLE_WORDS if s in first_clause]
    if not found_style:
        score += 2
    else:
        issues.append(f"첫 구절 스타일 단어: {found_style}")

    # 7. 중복 단어 없음 + 페이지 수 포함 (1pt)
    # Why: Etsy 알고리즘은 제목 내 동일 단어 반복을 keyword stuffing으로 패널티
    words = [w.lower().strip(",.") for w in title.split() if len(w) > 3]
    dup_words = [w for w in set(words) if words.count(w) > 1 and w not in {"for", "and", "the", "with", "your", "that", "this", "from"}]
    page_kw = next((k for k in product.keywords if "pages" in k.lower()), "")
    has_digit = any(char.isdigit() for char in title)
    if not dup_words and (not page_kw or has_digit):
        score += 1
    else:
        if dup_words:
            issues.append(f"중복 단어: {dup_words} -- Etsy keyword stuffing 패널티 위험")
        if page_kw and not has_digit:
            issues.append("페이지 수 미포함")

    return {"score": score, "max": 10, "issues": issues}


def score_tags(tags: list, title: str, product: Product, verified_pool: list,
               seasonal_tags: list | None = None) -> dict:
    score = 0
    issues = []
    pool_lower = {v.lower() for v in verified_pool}

    # 1. 정확히 13개 (2pts)
    if len(tags) == 13:
        score += 2
    elif 11 <= len(tags) <= 14:
        score += 1
        issues.append(f"태그 {len(tags)}개 (목표 13)")
    else:
        issues.append(f"태그 {len(tags)}개 (목표 13)")

    # 2. 모두 20자 이내 (1pt)
    over = [t for t in tags if len(t) > SEO_TAG_MAX_LENGTH]
    if not over:
        score += 1
    else:
        issues.append(f"20자 초과: {over}")

    # 3. 실제 검색어 품질 (3pts)
    # bad_words: 단일 단어 태그 + 의사 마케팅 용어 (다단어 구문은 제외)
    # bad: 마케팅 fluff 단어 (실제 buyer가 검색하지 않는 단어)
    bad_fluff = {"aid", "logic", "drills", "tasks", "hacks",
                 "educational", "handwriting", "phonics", "worksheets"}
    fake = [t for t in tags if t not in pool_lower and
            any(w in bad_fluff for w in t.split())]
    if not fake:
        score += 3
    elif len(fake) <= 1:
        score += 2
        issues.append(f"의심 태그: {fake}")
    else:
        score += 1
        issues.append(f"비검색어 태그 {len(fake)}개: {fake}")

    # 4. 시즌 태그 3개 존재 + 다양성 (2pts)
    # Why: 상위 1% = 에버그린 10개 + 시즌 3개 (eRank/Marmalead 검증 전략)
    seasonal_lower = {t.lower() for t in (seasonal_tags or [])}
    season_found = [t for t in tags if t.lower() in seasonal_lower]
    unique_first_words = {t.split()[0] for t in tags}
    if len(season_found) >= 2 and len(unique_first_words) >= 6:
        score += 2
    elif len(unique_first_words) >= 5:
        score += 1
        if len(season_found) < 2:
            issues.append(f"시즌 태그 {len(season_found)}개 (목표 3개)")
    else:
        issues.append(f"태그 다양성 부족 (첫 단어 종류 {len(unique_first_words)}개, 시즌 {len(season_found)}개)")

    # 5. 상위 5개 품질 (2pts)
    # Why: verified pool에서 온 태그는 이미 검증된 buyer 검색어 -> 관련 있음으로 처리
    #      pool 외 태그는 키워드 겹침으로 체크
    kw_words = {w for k in product.keywords for w in k.lower().split() if len(w) > 2}
    seasonal_pool_lower = {t.lower() for t in (seasonal_tags or [])}
    rel = sum(1 for t in tags[:5] if (
        t.lower() in pool_lower or              # verified pool 태그 -> 자동 관련
        t.lower() in seasonal_pool_lower or     # 시즌 태그 -> 자동 관련
        any(w in kw_words for w in t.split())   # 키워드 겹침
    ))
    if rel >= 4:
        score += 2
    elif rel >= 3:
        score += 1
        issues.append(f"상위 5태그 관련도 {rel}/5")
    else:
        issues.append(f"상위 태그 관련도 낮음 {rel}/5")

    return {"score": score, "max": 10, "issues": issues}


def score_description(desc: str, product: Product) -> dict:
    score = 0
    issues = []
    desc_lower = desc.lower()

    # 1. 훅 -- 155자 내 instant download + 핵심키워드 (2pts)
    hook = desc_lower[:155]
    has_dl = "instant download" in hook or "digital download" in hook
    core_words = {w for k in product.keywords[:2] for w in k.lower().split() if len(w) > 3}
    has_kw = any(w in hook for w in core_words)
    if has_dl and has_kw:
        score += 2
    elif has_dl or has_kw:
        score += 1
        issues.append(f"훅 미흡 (download:{has_dl}, keyword:{has_kw})")
    else:
        issues.append("훅에 instant download + 핵심 키워드 없음")

    # 2. v 불릿 4-5개 (2pts)
    bullets = [l for l in desc.split("\n") if l.strip().startswith("v")]
    if 4 <= len(bullets) <= 5:
        score += 2
    elif 3 <= len(bullets) <= 6:
        score += 1
        issues.append(f"v 불릿 {len(bullets)}개 (목표 4-5)")
    else:
        issues.append(f"v 불릿 {len(bullets)}개")

    # 3. WHAT'S INCLUDED (1pt)
    if "included" in desc_lower:
        score += 1
    else:
        issues.append("WHAT'S INCLUDED 없음")

    # 4. HOW TO USE (1pt)
    if "how to use" in desc_lower or ("1." in desc and "2." in desc):
        score += 1
    else:
        issues.append("HOW TO USE 없음")

    # 5. 호환성 + 디지털 다운로드 고지 (1pt)
    # Why: 상위 1%는 호환성 명시로 환불/불만 방지 (GoodNotes, Google Sheets 등)
    has_compat = any(w in desc_lower for w in ["compatible", "works with", "goodnotes", "google sheets", "adobe", "notability", "print at home"])
    has_dl = "digital download" in desc_lower and "no physical" in desc_lower
    if has_compat and has_dl:
        score += 1
    elif has_dl:
        score += 1  # 최소 고지는 있음
        issues.append("호환성 명시 없음 (GoodNotes/Google Sheets 등 추가 권장)")
    else:
        issues.append("DIGITAL DOWNLOAD 고지 없음")

    # 6. 이용권 명시 (1pt)
    # Why: 상위 1%는 이용권 명시로 신뢰도 상승 + 상업적 오용 방지
    if any(p in desc_lower for p in ["personal use", "for personal", "commercial use", "not for resale"]):
        score += 1
    else:
        issues.append("이용권 미명시 (personal use only 추가 필요)")

    # (길이 체크 제거 -- 프롬프트가 1100-1500자 강제, 트림은 1700자 기준으로 보호)

    # 7. FAQ 섹션 + 만족 보증 (1pt)
    # Why: 상위 1% 필수 신뢰 요소 -- FAQ는 구매 전 불안 해소, 만족 보증은 환불 방지
    has_faq = "q:" in desc_lower or "faq" in desc_lower or ("?" in desc and "a:" in desc_lower)
    has_guarantee = any(w in desc_lower for w in ["satisfaction", "guarantee", "make it right", "contact us"])
    if has_faq and has_guarantee:
        score += 1
    elif has_faq or has_guarantee:
        score += 0  # 둘 다 있어야 점수 (buyer trust 핵심)
        issues.append(f"FAQ({'있음' if has_faq else '없음'}) + 만족보증({'있음' if has_guarantee else '없음'}) -- 둘 다 필요")
    else:
        issues.append("FAQ 섹션 + 만족 보증 없음 -- 신뢰도 직결, 상위 1% 필수")

    # 8. WHY CHOOSE US 섹션 + 일반적 표현 없음 (1pt)
    # Why: 상위 1% 셀러 설명에 거의 필수 -- 감성적 구매 이유 제공 -> 전환율 직결
    has_why = "why choose" in desc_lower
    generic = ["high quality", "perfect for everyone", "look no further",
               "you won't be disappointed", "one stop shop"]
    found_generic = [g for g in generic if g in desc_lower]
    if has_why and not found_generic:
        score += 1
    elif has_why or not found_generic:
        score += 1  # 하나만 충족해도 점수 (기존과 동일)
        if not has_why:
            issues.append("WHY CHOOSE US 섹션 없음 -- 전환율에 중요")
        if found_generic:
            issues.append(f"일반적 표현: {found_generic}")

    return {"score": score, "max": 10, "issues": issues}


# ══════════════════════════════════════════════
# 검증 루프 -- 각 컴포넌트 독립 재시도
# ══════════════════════════════════════════════

def _run_with_verify(gen_fn, score_fn, label: str, min_score: float = MIN_SCORE,
                     max_attempts: int = MAX_ATTEMPTS, **gen_kwargs) -> tuple:
    """생성 -> 채점 -> 미달 시 feedback 포함 재생성. best 결과 반환."""
    best_result = None
    best_score = -1
    best_detail = {}

    for attempt in range(max_attempts):
        feedback = ""
        if attempt > 0 and best_detail.get("issues"):
            feedback = "\n".join(f"- {i}" for i in best_detail["issues"])

        try:
            result = gen_fn(attempt=attempt, feedback=feedback, **gen_kwargs)
            detail = score_fn(result)
            s = detail["score"]

            logger.info("[%s] attempt %d: %d/10  issues=%s",
                        label, attempt + 1, s, detail["issues"])

            if s > best_score:
                best_score = s
                best_result = result
                best_detail = detail

            if s >= min_score:
                logger.info("[%s] PASS %d/10 (attempt %d)", label, s, attempt + 1)
                return best_result, best_score, best_detail

        except Exception as e:
            logger.warning("[%s] attempt %d error: %s", label, attempt + 1, e)

    logger.warning("[%s] 최종 점수 %d/10 (목표 %d미달, best 사용)", label, best_score, min_score)
    return best_result, best_score, best_detail


# ══════════════════════════════════════════════
# 메인 진입점
# ══════════════════════════════════════════════

def generate_seo(product: Product, min_score: float = MIN_SCORE) -> dict:
    """3콜 분리 SEO 생성 + 컴포넌트별 검증.

    Returns: {"title": str, "tags": list[str], "description": str,
              "scores": {"title": N, "tags": N, "description": N, "average": N}}
    """
    month = datetime.now().month
    # 니치 추출 — style에서 niche 파싱 (예: "daily_sage_green_entrepreneur" → "entrepreneur")
    _style = getattr(product, "style", "") or ""
    _detected_niche: str | None = None
    _KNOWN_NICHES = [
        "ADHD_teacher", "ADHD_nurse", "christian_teacher", "sobriety_mom",
        "ADHD", "anxiety", "christian", "sobriety", "mom", "nurse", "teacher",
        "pregnancy", "entrepreneur", "homeschool", "self_care",
        "caregiver", "perimenopause", "cycle_syncing", "glp1",
    ]
    for _nk in sorted(_KNOWN_NICHES, key=len, reverse=True):
        if _style.endswith("_" + _nk) or _style == _nk:
            _detected_niche = _nk
            break
    seasonal_kws, seasonal_tags, seasonal_angle = _get_seasonal_context(
        product.category, month, niche=_detected_niche)
    examples  = CATEGORY_EXAMPLES.get(product.category, CATEGORY_EXAMPLES.get(Category.PLANNER, {}))
    compat    = COMPAT_INFO.get(product.category, "Digital download")
    raw_pool = VERIFIED_TAG_POOL.get(product.category, examples.get("tags", []))
    # 제품 키워드와 관련도 순으로 정렬 -> LLM이 관련 태그를 먼저 볼 수 있게
    kw_words_set = {w for k in product.keywords for w in k.lower().split() if len(w) > 2}
    verified_pool = sorted(raw_pool, key=lambda t: sum(1 for w in t.lower().split() if w in kw_words_set), reverse=True)
    primary_phrase = _primary_search_phrase(product, verified_pool)
    # 니치별 강제 primary phrase — generic "Daily Planner Pdf" 대신 검색량 높은 키워드 삽입
    _NICHE_PRIMARY_PHRASE: dict[str, str] = {
        "sobriety_mom":      "Sobriety Mom Planner Printable",
        "sobriety":          "Sobriety Planner Printable",
        "ADHD":              "ADHD Planner Printable",
        "anxiety":           "Anxiety Planner Printable",
        "christian":         "Christian Planner Printable",
        "mom":               "Mom Planner Printable",
        "nurse":             "Nurse Planner Printable",
        "teacher":           "Teacher Planner Printable",
        "pregnancy":         "Pregnancy Planner Printable",
        "entrepreneur":      "Business Planner Printable",
        "homeschool":        "Homeschool Planner Printable",
        "self_care":         "Self Care Planner Printable",
        "perimenopause":     "Perimenopause Planner Printable",
        "cycle_syncing":     "Cycle Syncing Planner Printable",
        "caregiver":         "Caregiver Planner Printable",
        "glp1":              "GLP-1 Wellness Planner Printable",
        "ADHD_teacher":      "ADHD Teacher Planner Printable",
        "ADHD_nurse":        "ADHD Nurse Planner Printable",
        "christian_teacher": "Christian Teacher Planner Printable",
    }
    if product.category == Category.PLANNER and product.style:
        _pstyle = product.style
        for _nk in sorted(_NICHE_PRIMARY_PHRASE, key=len, reverse=True):
            if _pstyle.endswith("_" + _nk) or _pstyle == _nk:
                primary_phrase = _NICHE_PRIMARY_PHRASE[_nk]
                break
    trending_kws   = _get_trending_keywords(product.category, n=8)

    logger.info("SEO 생성 시작: %s | primary='%s' | event='%s'",
                product.product_id, primary_phrase, seasonal_angle or "none")

    # ── 콜 1: 타이틀 A/B (2개 생성 → 높은 점수 선택) ──
    # Why: 단일 생성 대비 CTR 5-15% 향상 (A/B 선별로 품질 상한선 높임)
    title_a, t_score_a, t_detail_a = _run_with_verify(
        gen_fn=lambda attempt, feedback: _gen_title(
            product, primary_phrase, seasonal_kws, seasonal_angle, examples, attempt, feedback),
        score_fn=lambda r: score_title(r, primary_phrase, product),
        label="TITLE-A", min_score=min_score,
    )
    title_b, t_score_b, t_detail_b = _run_with_verify(
        gen_fn=lambda attempt, feedback: _gen_title(
            product, primary_phrase, seasonal_kws, seasonal_angle, examples, attempt, feedback),
        score_fn=lambda r: score_title(r, primary_phrase, product),
        label="TITLE-B", min_score=min_score,
    )
    if t_score_b > t_score_a:
        title, t_score, t_detail = title_b, t_score_b, t_detail_b
        logger.info("A/B: TITLE-B 선택 (%d > %d)", t_score_b, t_score_a)
    else:
        title, t_score, t_detail = title_a, t_score_a, t_detail_a
        logger.info("A/B: TITLE-A 선택 (%d >= %d)", t_score_a, t_score_b)
    if not title:
        title = _fallback_title(product, primary_phrase, examples)
        t_score = 5

    # ── 콜 2: 태그 (에버그린 10 + 시즌 3) ──
    tags, g_score, g_detail = _run_with_verify(
        gen_fn=lambda attempt, feedback: _gen_tags(
            product, title, verified_pool, seasonal_tags, trending_kws, attempt, feedback),
        score_fn=lambda r: score_tags(r, title, product, verified_pool, seasonal_tags),
        label="TAGS", min_score=min_score,
    )
    if not tags:
        tags = _fallback_tags(product, title, verified_pool)
        if seasonal_tags:
            tags = tags[:10] + [t.lower()[:SEO_TAG_MAX_LENGTH] for t in seasonal_tags[:3]]
        g_score = 5

    # ── 콜 3: 설명 ──
    desc, d_score, d_detail = _run_with_verify(
        gen_fn=lambda attempt, feedback: _gen_description(
            product, title, compat, seasonal_kws, attempt, feedback),
        score_fn=lambda r: score_description(r, product),
        label="DESC", min_score=min_score,
    )
    if not desc:
        desc = _fallback_description(product, title, compat)
        d_score = 5

    # 1400자 초과 시 스마트 트리밍 (필수 섹션 보존)
    if len(desc) > 1400:
        desc = _trim_description(desc)
        trim_result = score_description(desc, product)
        d_score = trim_result["score"]

    avg = round((t_score + g_score + d_score) / 3, 1)
    logger.info("SEO 완료: title=%d, tags=%d, desc=%d, avg=%.1f",
                t_score, g_score, d_score, avg)

    return {
        "title": title,
        "tags": tags[:SEO_TAG_COUNT],
        "description": desc,
        "scores": {
            "title": t_score, "tags": g_score, "description": d_score, "average": avg,
            "title_issues": t_detail.get("issues", []),
            "tags_issues": g_detail.get("issues", []),
            "desc_issues": d_detail.get("issues", []),
        },
    }


# ══════════════════════════════════════════════
# Fallback (LLM 완전 실패 시)
# ══════════════════════════════════════════════

def _trim_description(desc: str, max_len: int = 1700) -> str:
    """1700자 초과 설명을 필수 섹션 보존하면서 트리밍.
    전략: 가장 긴 v 불릿을 먼저 단축. 그래도 길면 HOW TO USE 스텝 단축.
    보호 섹션: DIGITAL DOWNLOAD, usage rights, SATISFACTION GUARANTEE, FAQ.
    Why: 1700자 한도로 올림 -- FAQ+보증 섹션이 트리밍으로 잘리는 문제 방지.
    """
    if len(desc) <= max_len:
        return desc

    lines = desc.split('\n')

    # 불릿 길이 단축 -- 가장 긴 불릿부터 (최대 8회)
    for _ in range(8):
        if len('\n'.join(lines)) <= max_len:
            break
        bullet_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith('v')]
        if not bullet_lines:
            break
        longest_idx, longest_line = max(bullet_lines, key=lambda x: len(x[1]))
        first_sentence = longest_line.split('.')[0] + '.'
        if len(first_sentence) < len(longest_line) - 10:
            lines[longest_idx] = first_sentence

    result = '\n'.join(lines)
    if len(result) <= max_len:
        return result

    # 여전히 길면: 보호 섹션(마지막 블록들) 분리 후 앞부분만 자르기
    # 보호: FAQ, SATISFACTION GUARANTEE, DIGITAL DOWNLOAD, usage rights
    protected_markers = [
        "satisfaction guarantee", "faq", "q: will i",
        "this is a digital download", "for personal use", "not for resale",
    ]
    protected_lines: list[tuple[int, str]] = []
    for i, l in enumerate(lines):
        if any(m in l.lower() for m in protected_markers):
            # 해당 라인부터 끝까지 보호
            protected_lines = lines[i:]
            lines = lines[:i]
            break

    tail = '\n'.join(protected_lines)
    body = '\n'.join(lines)
    allowed_body = max_len - len(tail) - 4
    if allowed_body > 800:
        cut = body[:allowed_body].rfind('\n')
        body = body[:cut].strip() if cut > 400 else body[:allowed_body].strip()

    return (body + '\n\n' + tail).strip() if tail else body.strip()[:max_len]


_FALLBACK_TITLE_SECONDARY = {
    Category.WORKSHEET:             "Homeschool Classroom No Prep Activity",
    Category.PLANNER:               "Goodnotes Undated Life Organizer Bundle",
    Category.SPREADSHEET:           "Automated Google Sheets Dashboard Template",
    Category.WALL_ART:              "Modern Minimalist Bedroom Living Room Decor",
    Category.SOCIAL_MEDIA_TEMPLATE: "30 Instagram Story Pinterest Templates Bundle",
    Category.RESUME_TEMPLATE:       "ATS-Friendly CV Template 3 Industry Versions",
}

def _fallback_title(product: Product, primary_phrase: str, examples: dict) -> str:
    page_info = next((k.title() for k in product.keywords if "pages" in k.lower()), "")
    secondary = _FALLBACK_TITLE_SECONDARY.get(product.category, "Digital Download Printable")
    parts = [primary_phrase]
    if page_info:
        parts.append(f"{page_info} {secondary}")
    else:
        parts.append(secondary)
    _fallback_suffix = {
        Category.SOCIAL_MEDIA_TEMPLATE: "PNG Bundle",
        Category.WALL_ART: "Instant Download",
    }
    parts.append(_fallback_suffix.get(product.category, "Instant Download PDF"))
    title = ", ".join(parts)
    return title[:SEO_TITLE_MAX_LENGTH].rsplit(",", 1)[0] if len(title) > SEO_TITLE_MAX_LENGTH else title


def _fallback_tags(product: Product, title: str, verified_pool: list) -> list[str]:
    title_words = set(title.lower().replace(",", " ").split())
    kw_words = {w for k in product.keywords for w in k.lower().split() if len(w) > 2}
    sorted_pool = sorted(verified_pool, key=lambda t: sum(1 for w in t.lower().split() if w in kw_words), reverse=True)
    tags = []
    seen = set()
    for t in sorted_pool:
        tl = t.lower()
        if tl in seen or len(tl) > SEO_TAG_MAX_LENGTH:
            continue
        # 태그 자체가 타이틀에 완전히 포함된 구문인 경우만 제외 (단어 집합 아닌 exact substring)
        if tl in title.lower():
            continue
        tags.append(tl)
        seen.add(tl)
        if len(tags) >= SEO_TAG_COUNT:
            break
    return tags


_FALLBACK_HOOKS = {
    Category.WORKSHEET:             "Stop searching for quality {subject}worksheets -- this {pages}printable bundle is ready as an instant download today.",
    Category.PLANNER:               "Finally get organized with this {pages}undated printable planner -- instant download, works with GoodNotes or any printer.",
    Category.SPREADSHEET:           "Take control of your finances with this {subject}budget template -- instant download, automated formulas, ready to use today.",
    Category.WALL_ART:              "Transform any room instantly with this high-resolution printable wall art -- instant download, print and frame in minutes.",
    Category.SOCIAL_MEDIA_TEMPLATE: "Level up your social media presence with this 30-template bundle -- instant download, ready to post on Instagram, Stories, and Pinterest today.",
    Category.RESUME_TEMPLATE:       "Land your next job with this ATS-friendly resume bundle -- instant download, 3 industry versions ready to customize and send today.",
}

_FALLBACK_FEATURES = {
    Category.WORKSHEET: ["3 difficulty levels (Easy, Medium, Hard)", "Answer key included on final pages",
                         "Reward certificates every milestone", "Clean, laminate-friendly design", "Instant PDF download"],
    Category.PLANNER: ["Undated -- use any year", "Year, monthly, weekly & daily pages", "Habit tracker & goal pages",
                       "Compatible with GoodNotes & standard printers", "US Letter and A4 sizes included"],
    Category.SPREADSHEET: ["Auto-calculating formulas", "Color-coded conditional formatting (green/red)",
                           "Dashboard tab with charts", "Protected formula cells", "Step-by-step How to Use tab"],
    Category.WALL_ART: ["300 DPI -- crisp at any print size", "Multiple sizes included (2:3, 3:4, 4:5, square)",
                        "Instant digital download", "Print at home or any print shop", "Fits standard frames"],
    Category.SOCIAL_MEDIA_TEMPLATE: ["30 templates: 20 IG posts + 5 Stories + 5 Pinterest pins", "High-resolution PNG files, ready to post",
                                     "3 sizes included (1080x1080, 1080x1920, 1000x1500)", "Fully editable design elements", "Commercial use license included"],
    Category.RESUME_TEMPLATE: ["ATS-friendly layout -- passes major screening systems", "3 industry versions (e.g., Tech, Creative, Business)",
                               "Clean, professional one-page design", "Editable in free PDF readers", "Instant download -- start applying today"],
}


def _fallback_description(product: Product, title: str, compat: str) -> str:
    page_count = next((k for k in product.keywords if "pages" in k.lower()), "")
    subject_kws = [k for k in product.keywords if k.lower() not in _GENERIC_SKIP and "pages" not in k.lower() and len(k.split()) >= 2]
    _noise = {"worksheet", "worksheets", "planner", "spreadsheet", "printable", "wall", "art", "print", "template", "budget"}
    def _modifier(phrase):
        words = [w for w in phrase.lower().split() if w not in _noise and w not in _GENERIC_SKIP]
        return (" ".join(words) + " ") if words else ""
    subject = _modifier(subject_kws[0]) if subject_kws else ""
    pages_str = f"{page_count.title()} " if page_count else ""

    tmpl = _FALLBACK_HOOKS.get(product.category, "Premium digital download, ready to use instantly.")
    hook = tmpl.format(subject=subject, pages=pages_str)
    features = _FALLBACK_FEATURES.get(product.category, ["Instant digital download", compat, "High quality"])
    bullets = "\n".join(f"v {f}" for f in features)
    sizes = ", ".join(product.sizes) if product.sizes else "PDF"

    return f"""{hook}

KEY FEATURES:
{bullets}

WHAT'S INCLUDED:
- {compat}
{f'- {pages_str.strip()} of printable content' if page_count else ''}
- File format: {sizes}

HOW TO USE:
1. Purchase and receive your instant download link from Etsy
2. Open in your preferred app or send to a printer
3. Start using right away -- no waiting, no shipping

This is a DIGITAL DOWNLOAD. No physical item will be shipped.
For personal use only. Commercial use not permitted.

Have questions about your download or need help with the file? Send us a message -- we respond within 24 hours and love helping our customers get the most out of their purchase. Thank you for supporting DailyPrintHaus!"""
