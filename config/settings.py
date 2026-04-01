"""
Etsy Digital Shop - Configuration
All magic numbers, API settings, and schedules live here.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")        # config/.env 먼저 (Pinterest 등)
load_dotenv(Path(__file__).parent.parent / ".env", override=True)  # root .env 최종 우선 (Etsy 토큰)

# ── Paths ──
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
MOCKUP_TEMPLATES_DIR = BASE_DIR / "assets" / "mockup_templates"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = BASE_DIR / "db" / "etsy_auto.db"

# ── API Keys (Gemini 10-key rotation) ──
GEMINI_API_KEYS = [
    os.getenv(f"GEMINI_API_KEY_{i}", "")
    for i in range(1, 11)
    if os.getenv(f"GEMINI_API_KEY_{i}", "")
]
_gemini_key_index = 0

def get_next_gemini_key() -> str:
    """Round-robin rotation across 10 API keys."""
    global _gemini_key_index
    if not GEMINI_API_KEYS:
        return ""
    key = GEMINI_API_KEYS[_gemini_key_index % len(GEMINI_API_KEYS)]
    _gemini_key_index += 1
    return key

# ── API Keys (Groq 10-key rotation) ──
GROQ_API_KEYS = [
    os.getenv(f"GROQ_API_KEY_{i}", "")
    for i in range(1, 11)
    if os.getenv(f"GROQ_API_KEY_{i}", "")
]
_groq_key_index = 0
_groq_exhausted: set = set()   # 429 소진된 키 인덱스 임시 제외

def get_next_groq_key() -> str:
    """Round-robin rotation across up to 10 Groq API keys.
    429 소진 키는 _groq_exhausted에 등록해 건너뜀.
    전부 소진되면 exhausted 리셋 후 처음부터 재시도.
    """
    global _groq_key_index
    if not GROQ_API_KEYS:
        return ""
    n = len(GROQ_API_KEYS)
    # 사용 가능한 키 탐색
    for _ in range(n):
        idx = _groq_key_index % n
        _groq_key_index += 1
        if idx not in _groq_exhausted:
            return GROQ_API_KEYS[idx]
    # 전부 소진 → 리셋 후 첫 번째 키 반환
    _groq_exhausted.clear()
    _groq_key_index = 1
    return GROQ_API_KEYS[0]

def mark_groq_key_exhausted(key: str) -> None:
    """429 받은 키를 소진 목록에 추가."""
    if key in GROQ_API_KEYS:
        _groq_exhausted.add(GROQ_API_KEYS.index(key))
# ── Cloudflare Workers AI (최대 10계정 로테이션) ──
CLOUDFLARE_ACCOUNTS = [
    {
        "account_id": os.getenv(f"CLOUDFLARE_ACCOUNT_ID_{i}", ""),
        "api_token":  os.getenv(f"CLOUDFLARE_API_TOKEN_{i}", ""),
    }
    for i in range(1, 11)
    if os.getenv(f"CLOUDFLARE_ACCOUNT_ID_{i}", "")
]
_cf_index = 0

def get_next_cloudflare_account() -> dict:
    """Round-robin으로 Cloudflare 계정 순환."""
    global _cf_index
    if not CLOUDFLARE_ACCOUNTS:
        return {}
    acct = CLOUDFLARE_ACCOUNTS[_cf_index % len(CLOUDFLARE_ACCOUNTS)]
    _cf_index += 1
    return acct

ETSY_API_KEY = os.getenv("ETSY_API_KEY", "")
ETSY_API_SECRET = os.getenv("ETSY_API_SECRET", "")
ETSY_ACCESS_TOKEN = os.getenv("ETSY_ACCESS_TOKEN", "")
ETSY_REFRESH_TOKEN = os.getenv("ETSY_REFRESH_TOKEN", "")
ETSY_SHOP_ID = os.getenv("ETSY_SHOP_ID", "")
GUMROAD_ACCESS_TOKEN = os.getenv("GUMROAD_ACCESS_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Groq Settings (primary text generation -- LPU 초고속) ──
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"                   # 최고 성능 모델 고정 (변경 금지)

# ── Gemini Settings ──
GEMINI_IMAGE_MODEL = "imagen-4.0-ultra-generate-001"      # wall art image generation only
GEMINI_TEXT_MODEL = "gemini-2.0-flash"                    # text generation (review replies etc)
GEMINI_MAX_TOKENS = 500
GEMINI_TEMPERATURE = 0.7

# ── Pricing Strategy (USD) ──
# 플래너 스윗스팟: $9-12 / 니치별 시장 평균 -20~30% 런칭 → 리뷰 쌓일수록 단계 인상
PRICING = {
    # ── 가격 전략 (2025 Etsy 리서치 기반) ──
    # 구조: launch(0리뷰) → single(10리뷰) → mid(50리뷰) → premium(100리뷰+)
    # list_price = Etsy 대시보드에서 "원가"로 설정 → sale 배지 표시용
    # 실제 결제가 = launch/single (list_price 대비 20-25% 할인처럼 보임)
    #
    # Etsy 세일 설정 방법: 대시보드 → Marketing → Sales & Discounts
    # list_price를 정가로 올리고, launch 가격으로 20% 할인 쿠폰 적용
    "planner": {
        # 리서치: 153p 올인원 프리미엄 → 시장 $7-15, 상위 $10-20
        # .97 엔딩 = 전환율 24% 향상 / 번들 앵커 = $29.97이 $9.97을 싸보이게 함
        "list_price":  8.99,  # Etsy 정가 (세일 배지용)
        "launch":      4.97,  # 0 리뷰 — 전환 극대화, 리뷰 빠르게 모으기
        "single":      6.99,  # 10 리뷰 — 1차 인상
        "mid":         9.97,  # 50 리뷰 — 시장 중상위
        "premium":    12.99,  # 100 리뷰 — 확립 단계
        "bundle":     17.97,  # 3타입 번들 (daily+weekly+habit) — 하위 호환용
        "bundle_all": 29.97,  # 전체 번들 앵커 (8타입 전부 — 비싸보이게 해서 $9.97을 싸보이게)
    },
    # ── 번들 상품 가격 전략 ──
    # daily + weekly + habit_tracker × 같은 niche × 같은 theme → 3-Pack 번들
    # list_price는 Etsy 정가 표시용 (단품 3개 합산 대비 25% 절약처럼 보임)
    "bundle": {
        "types":      ["daily", "weekly", "habit_tracker"],
        "list_price": 24.97,   # Etsy 정가 표시용 (할인 배지)
        "launch":     17.97,   # 0 리뷰 — 단품 3개($4.97×3=$14.91) 대비 약간 높은 번들 프리미엄
        "single":     19.97,   # 10 리뷰
        "mid":        21.97,   # 30 리뷰
        "premium":    23.97,   # 100 리뷰
    },
    # ── 니치별 가격 티어 ──
    # 전략: 시장 평균 -20% 런칭 → 리뷰 쌓일수록 단계 인상
    # 리뷰 티어: launch(0~) → single(10~) → mid(30~) → premium(100~)
    # 근거: 2025 Etsy 실제 시장 조사 기반 .97 엔딩
    "planner_niche_price": {
        # 시장평균 $7-10  → 런치 시장평균 -30%
        "sobriety":    {"launch": 5.97, "single": 7.97, "mid":  9.97, "premium": 12.97},
        # 시장평균 $8-12  → 런치 시장평균 -30%
        "nurse":       {"launch": 5.97, "single": 7.97, "mid":  9.97, "premium": 12.97},
        # 시장평균 $10-13 → 런치 시장평균 -30%
        "teacher":     {"launch": 6.97, "single": 8.97, "mid": 11.97, "premium": 14.97},
        # 시장평균 $6-8   → 런치 시장평균 -25%
        "ADHD":        {"launch": 4.97, "single": 5.97, "mid":  7.97, "premium": 10.97},
        "entrepreneur":{"launch": 4.97, "single": 6.97, "mid":  8.97, "premium": 11.97},
        # 시장평균 $4-5   → 런치 시장평균 -20%
        "christian":   {"launch": 3.47, "single": 4.97, "mid":  6.97, "premium":  8.97},
        "mom":         {"launch": 3.47, "single": 4.97, "mid":  6.97, "premium":  8.97},
        "pregnancy":   {"launch": 3.47, "single": 4.97, "mid":  6.97, "premium":  8.97},
        # 시장평균 $3-4   → 런치 시장평균 -20%
        "anxiety":     {"launch": 2.97, "single": 3.97, "mid":  5.97, "premium":  7.97},
        "homeschool":  {"launch": 2.97, "single": 3.97, "mid":  5.97, "premium":  7.97},
        "self_care":   {"launch": 2.97, "single": 3.97, "mid":  5.97, "premium":  7.97},
        # 2024-2025 트렌드 니치 — 경쟁 극소 + 건강/웰니스 높은 지불 의향
        # 시장평균 $8-15 → 런치 -40% (얼리무버 어드밴티지 극대화)
        "perimenopause":{"launch": 4.97, "single": 6.97, "mid":  9.97, "premium": 12.97},
        "cycle_syncing":{"launch": 4.97, "single": 6.97, "mid":  9.97, "premium": 12.97},
        "glp1":         {"launch": 4.97, "single": 6.97, "mid":  9.97, "premium": 12.97},
        # caregiver: 감성 니치, 시장평균 $6-10 → 런치 -35%
        "caregiver":    {"launch": 3.97, "single": 5.97, "mid":  7.97, "premium": 10.97},
        # 시장평균 $2-5   → 런치 시장평균 -20%
        None:          {"launch": 2.97, "single": 4.97, "mid":  6.97, "premium":  8.97},
    },
    # 리뷰 수 → 가격 티어 매핑
    "planner_review_tiers": {
        "launch":  0,    # 0~9 리뷰
        "single":  10,   # 10~29 리뷰
        "mid":     30,   # 30~99 리뷰
        "premium": 100,  # 100+ 리뷰
    },
}


# ── Planner Types & Config ──
# Why: Top sellers offer 200+ page all-in-one planners with hyperlink navigation.
PLANNER_TYPES = [
    "daily", "weekly", "monthly", "yearly",
    "budget", "meal", "fitness", "habit_tracker",
    "goal_setting", "gratitude", "reading_log",
]
PLANNER_INCLUDE_COVER = True            # always generate cover page
PLANNER_INCLUDE_TOC = True              # table of contents with hyperlinks
PLANNER_UNDATED = True                  # generate undated version (sells year-round)

# ── Seasonal Event Calendar (Planner) ──
# list_by_month = month to publish listing (8-10 weeks before peak_month)
CATEGORY_EVENTS = {
    "planner": [
        {"key": "new_year",       "name": "New Year Planning",   "peak_month": 1,  "list_by_month": 10,
         "planner_type": "goal_setting",
         "niches": ["ADHD", "christian", "sobriety", "mom", "entrepreneur", None],
         "title_angle": "2027 Goal Setting",
         "keywords": ["2027 planner", "new year planner", "goal setting planner", "yearly planner printable"]},
        {"key": "dry_january",    "name": "Dry January",         "peak_month": 1,  "list_by_month": 11,
         "planner_type": "habit_tracker",
         "niches": ["sobriety", "sobriety_mom", "anxiety", None],
         "title_angle": "Dry January Habit Tracker",
         "keywords": ["dry january tracker", "sober january planner", "alcohol free planner", "sobriety tracker"]},
        {"key": "valentines",     "name": "Valentine's Day",     "peak_month": 2,  "list_by_month": 12,
         "planner_type": "gratitude",
         "niches": ["self_care", "mom", "pregnancy", None],
         "title_angle": "Self Care Valentine",
         "keywords": ["self care planner", "valentine gift", "love journal printable", "couples planner"]},
        {"key": "mothers_day",    "name": "Mother's Day",        "peak_month": 5,  "list_by_month": 3,
         "planner_type": "daily",
         "niches": ["mom", "sobriety_mom", "pregnancy", "caregiver", None],
         "title_angle": "Gift for Mom",
         "keywords": ["mom planner printable", "gift for mom", "self care planner", "mom life planner"]},
        {"key": "nurses_week",    "name": "Nurses Week",         "peak_month": 5,  "list_by_month": 3,
         "planner_type": "daily",
         "niches": ["nurse", "ADHD_nurse"],
         "title_angle": "Gift for Nurses",
         "keywords": ["nurse planner printable", "gift for nurse", "nurses week gift", "nurse appreciation gift"]},
        {"key": "back_to_school", "name": "Back to School",      "peak_month": 8,  "list_by_month": 6,
         "planner_type": "daily",
         "niches": ["teacher", "ADHD_teacher", "christian_teacher", "homeschool", "ADHD", None],
         "title_angle": "Student Academic Planner 2025-2026",
         "keywords": ["student planner", "academic planner", "teacher planner 2025-2026", "homework planner"]},
        {"key": "christmas",      "name": "Christmas Holiday",   "peak_month": 12, "list_by_month": 9,
         "planner_type": "daily",
         "niches": ["christian", "christian_teacher", "mom", "caregiver", None],
         "title_angle": "Holiday Gift Planner",
         "keywords": ["holiday planner", "christmas planner", "advent planner", "gift tracker printable"]},
    ],
}

# ── SEO Settings ──
SEO_TITLE_MAX_LENGTH = 140
SEO_TAG_COUNT = 13
SEO_TAG_MAX_LENGTH = 20
SEO_DESC_HOOK_LENGTH = 160      # first 160 chars shown in Etsy preview

# ── Etsy API ──
ETSY_API_BASE_URL = "https://openapi.etsy.com/v3"
ETSY_OAUTH_URL = "https://www.etsy.com/oauth/connect"
ETSY_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
ETSY_LISTING_TYPE = "download"  # digital product

# ── Gumroad API ──
GUMROAD_API_BASE_URL = "https://api.gumroad.com/v2"

# ── Anti-Bot / Rate Limiting ──
REQUEST_DELAY_MIN = 2.0         # seconds
REQUEST_DELAY_MAX = 5.0         # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2          # exponential backoff base

# ── Logging ──
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_RETENTION_DAYS = 7

# ── Telegram Alert Thresholds ──
ALERT_ON_NEGATIVE_REVIEW = True     # alert on rating <= 2
ALERT_ON_SALE = True                # alert on every sale
DAILY_REPORT_HOUR = 21              # send daily report at 9 PM
