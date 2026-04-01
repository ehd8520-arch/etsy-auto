"""
Etsy API v3 Publisher -- OAuth 2.0 인증 + 리스팅 자동 생성.

Flow:
1. OAuth 2.0 token (first time: browser auth, then refresh token)
2. Create draft listing (type=download)
3. Upload listing images (mockups)
4. Upload digital file (the actual product)
5. Activate listing
"""
import json
import logging
import time
import random
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from config.settings import (
    ETSY_API_KEY, ETSY_API_SECRET, ETSY_ACCESS_TOKEN, ETSY_REFRESH_TOKEN,  # noqa: F401
    ETSY_SHOP_ID, ETSY_API_BASE_URL, ETSY_OAUTH_URL, ETSY_TOKEN_URL,
    ETSY_LISTING_TYPE, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, MAX_RETRIES,
    RETRY_BACKOFF_BASE,
)
from models import Product, Listing, SEOData, Platform, ProductStatus

logger = logging.getLogger(__name__)

# Module-level token storage (refreshed at runtime)
_access_token: str = ETSY_ACCESS_TOKEN
_refresh_token: str = ETSY_REFRESH_TOKEN


def _rate_limit():
    """Sleep random interval to avoid rate limiting."""
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


def _api_request(method: str, endpoint: str, **kwargs) -> Optional[dict]:
    """Make API request with retry and exponential backoff."""
    url = f"{ETSY_API_BASE_URL}{endpoint}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {_access_token}"
    headers["x-api-key"] = f"{ETSY_API_KEY}:{ETSY_API_SECRET}"

    for attempt in range(MAX_RETRIES):
        try:
            _rate_limit()
            resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)

            if resp.status_code == 401:
                logger.warning("Token expired, refreshing...")
                if refresh_access_token():
                    headers["Authorization"] = f"Bearer {_access_token}"
                    continue
                else:
                    logger.error("Token refresh failed")
                    return None

            if resp.status_code == 429:
                wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                logger.warning("Rate limited, waiting %ds...", wait)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            if not resp.text:
                return {}
            try:
                return resp.json()
            except ValueError as _je:
                logger.warning("API response JSON parse failed: %s (body: %.100s)", _je, resp.text)
                return {}

        except requests.RequestException as e:
            wait = RETRY_BACKOFF_BASE ** (attempt + 1)
            logger.warning("API request failed (attempt %d): %s. Retry in %ds", attempt + 1, e, wait)
            time.sleep(wait)

    logger.error("API request failed after %d attempts: %s %s", MAX_RETRIES, method, endpoint)
    return None


# ── OAuth 2.0 ──

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback to capture authorization code."""
    auth_code: Optional[str] = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        _OAuthCallbackHandler.auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Authorization successful! You can close this tab.</h1>")

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def authorize_first_time(redirect_port: int = 3000) -> bool:
    """
    First-time OAuth flow. Opens browser for user authorization.
    Only needed once -- after that, refresh token is used.
    """
    global _access_token, _refresh_token

    redirect_uri = f"http://localhost:{redirect_port}/callback"
    # Etsy OAuth uses PKCE
    import hashlib
    import base64
    import secrets
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    params = {
        "response_type": "code",
        "client_id": ETSY_API_KEY,
        "redirect_uri": redirect_uri,
        "scope": "listings_r listings_w listings_d",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{ETSY_OAUTH_URL}?{urlencode(params)}"

    print(f"\nOpening browser for Etsy authorization...")
    print(f"URL: {auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to catch callback
    server = HTTPServer(("localhost", redirect_port), _OAuthCallbackHandler)
    server.handle_request()

    auth_code = _OAuthCallbackHandler.auth_code
    if not auth_code:
        logger.error("No authorization code received")
        return False

    # Exchange code for tokens
    token_data = {
        "grant_type": "authorization_code",
        "client_id": ETSY_API_KEY,
        "redirect_uri": redirect_uri,
        "code": auth_code,
        "code_verifier": code_verifier,
    }
    try:
        resp = requests.post(ETSY_TOKEN_URL, data=token_data, timeout=30)
        resp.raise_for_status()
        tokens = resp.json()
        _access_token = tokens["access_token"]
        _refresh_token = tokens["refresh_token"]

        # Save tokens to .env for persistence
        _save_tokens(_access_token, _refresh_token)
        logger.info("OAuth authorization successful")
        return True
    except Exception as e:
        logger.error("Token exchange failed: %s", e)
        return False


def refresh_access_token() -> bool:
    """Refresh expired access token."""
    global _access_token, _refresh_token

    if not _refresh_token:
        logger.error("No refresh token available. Run authorize_first_time() first.")
        return False

    data = {
        "grant_type": "refresh_token",
        "client_id": ETSY_API_KEY,
        "refresh_token": _refresh_token,
    }
    try:
        resp = requests.post(ETSY_TOKEN_URL, data=data, timeout=30)
        resp.raise_for_status()
        tokens = resp.json()
        _access_token = tokens["access_token"]
        _refresh_token = tokens["refresh_token"]
        _save_tokens(_access_token, _refresh_token)
        logger.info("Token refreshed successfully")
        return True
    except Exception as e:
        logger.error("Token refresh failed: %s", e)
        return False


def _save_tokens(access: str, refresh: str) -> None:
    """Save tokens to root .env (loaded with override=True, so must be saved there).

    Why: config/.env is loaded first WITHOUT override, then root .env WITH override=True.
         If tokens were saved to config/.env, root .env would overwrite them on next startup.
    원자적 쓰기: tmp → replace — .env 쓰기 중 크래시 시 기존 파일 보존.
    토큰 라인 없는 경우: 파일 끝에 추가 (silent drop 방지).
    """
    root_env = Path(__file__).parent.parent / ".env"
    config_env = Path(__file__).parent.parent / "config" / ".env"
    env_path = root_env if root_env.exists() else config_env
    if not env_path.exists():
        return
    content = env_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = []
    found_access = False
    found_refresh = False
    for line in lines:
        if line.startswith("ETSY_ACCESS_TOKEN="):
            new_lines.append(f"ETSY_ACCESS_TOKEN={access}")
            found_access = True
        elif line.startswith("ETSY_REFRESH_TOKEN="):
            new_lines.append(f"ETSY_REFRESH_TOKEN={refresh}")
            found_refresh = True
        else:
            new_lines.append(line)
    # 라인 없으면 끝에 추가 (silent drop 방지)
    if not found_access:
        new_lines.append(f"ETSY_ACCESS_TOKEN={access}")
    if not found_refresh:
        new_lines.append(f"ETSY_REFRESH_TOKEN={refresh}")
    # 원자적 쓰기
    tmp = env_path.with_suffix(".tmp")
    try:
        tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        tmp.replace(env_path)
    except Exception as e:
        logger.error("토큰 저장 실패: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    # GitHub Actions 환경이면 Secrets도 업데이트
    _update_github_secrets(access, refresh)


def _update_github_secrets(access: str, refresh: str) -> None:
    """GitHub Actions 환경에서 갱신된 토큰을 Secrets에 업데이트."""
    import subprocess
    if not os.getenv("GITHUB_ACTIONS"):
        return
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not repo:
        return
    for name, value in [("ETSY_ACCESS_TOKEN", access), ("ETSY_REFRESH_TOKEN", refresh)]:
        try:
            result = subprocess.run(
                ["gh", "secret", "set", name, "--body", value, "--repo", repo],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                logger.info("GitHub Secret 업데이트 완료: %s", name)
            else:
                logger.warning("GitHub Secret 업데이트 실패: %s — %s", name, result.stderr[:100])
        except Exception as e:
            logger.warning("GitHub Secret 업데이트 예외: %s", e)


# ── Shop Section System ──

_NICHE_SECTION_MAP: dict[str | None, str] = {
    None:               "Digital Planners",
    "ADHD":             "ADHD Planners",
    "ADHD_teacher":     "ADHD Planners",
    "ADHD_nurse":       "ADHD Planners",
    "anxiety":          "Wellness Planners",
    "self_care":        "Wellness Planners",
    "perimenopause":    "Wellness Planners",
    "cycle_syncing":    "Wellness Planners",
    "glp1":             "Wellness Planners",
    "christian":        "Christian Planners",
    "christian_teacher":"Christian Planners",
    "sobriety":         "Recovery Planners",
    "sobriety_mom":     "Recovery Planners",
    "mom":              "Mom & Family Planners",
    "pregnancy":        "Mom & Family Planners",
    "caregiver":        "Mom & Family Planners",
    "nurse":            "Healthcare Planners",
    "teacher":          "Teacher Planners",
    "homeschool":       "Teacher Planners",
    "entrepreneur":     "Business Planners",
}

# 런타임 캐시: section_name → shop_section_id
_section_cache: dict[str, str] = {}


def get_niche_section_name(style: str) -> str:
    """product.style ('daily_sage_green_ADHD' 형태)에서 섹션명 반환."""
    if not style:
        return _NICHE_SECTION_MAP[None]
    for niche in sorted(_NICHE_SECTION_MAP.keys(), key=lambda k: len(k or ""), reverse=True):
        if niche and (style.endswith("_" + niche) or style == niche):
            return _NICHE_SECTION_MAP[niche]
    return _NICHE_SECTION_MAP[None]


def create_or_get_section(shop_id: str, section_name: str) -> Optional[str]:
    """섹션명으로 shop_section_id 조회 또는 생성. 실패 시 None."""
    if section_name in _section_cache:
        return _section_cache[section_name]
    try:
        # 기존 섹션 목록 조회
        result = _api_request("GET", f"/application/shops/{shop_id}/sections")
        if result and "results" in result:
            for sec in result["results"]:
                if sec.get("title", "").strip().lower() == section_name.lower():
                    sid = str(sec["shop_section_id"])
                    _section_cache[section_name] = sid
                    return sid
        # 없으면 생성
        create_result = _api_request(
            "POST",
            f"/application/shops/{shop_id}/sections",
            json={"title": section_name},
        )
        if create_result and "shop_section_id" in create_result:
            sid = str(create_result["shop_section_id"])
            _section_cache[section_name] = sid
            logger.info("샵 섹션 생성: %s (id=%s)", section_name, sid)
            return sid
    except Exception as e:
        logger.warning("섹션 조회/생성 실패 (섹션 없이 발행 계속): %s", e)
    return None


# ── Listing Operations ──

def get_shop_id() -> Optional[str]:
    """Get the shop ID for the authenticated user."""
    if ETSY_SHOP_ID:
        return ETSY_SHOP_ID
    result = _api_request("GET", "/application/users/me")
    if result and "user_id" in result:
        user_id = result["user_id"]
        shop_result = _api_request("GET", f"/application/users/{user_id}/shops")
        if shop_result and shop_result.get("results"):
            return str(shop_result["results"][0]["shop_id"])
    return None


def create_draft_listing(
    shop_id: str,
    title: str,
    description: str,
    price: float,
    tags: list[str],
    taxonomy_id: int = 2078,  # Art & Collectibles > Prints > Digital Prints
    style: str = "",          # product.style — 섹션 자동 배정용
) -> Optional[str]:
    """
    Create a draft listing on Etsy.
    Returns listing_id if successful.
    style 파라미터로 니치 기반 샵 섹션 자동 배정.
    """
    data = {
        "title": title,
        "description": description,
        "price": price,
        "quantity": 999,
        "taxonomy_id": taxonomy_id,
        "who_made": "i_did",
        "when_made": "2020_2025",
        "is_supply": False,
        "type": ETSY_LISTING_TYPE,
        "tags": tags[:13],
        "should_auto_renew": True,
        "is_digital": True,
    }

    # 샵 섹션 자동 배정 (실패해도 발행 계속)
    if style:
        section_name = get_niche_section_name(style)
        section_id   = create_or_get_section(shop_id, section_name)
        if section_id:
            data["shop_section_id"] = int(section_id)
            logger.info("섹션 배정: %s → %s (id=%s)", style, section_name, section_id)

    result = _api_request(
        "POST",
        f"/application/shops/{shop_id}/listings",
        json=data,
    )
    if result and "listing_id" in result:
        listing_id = str(result["listing_id"])
        logger.info("Draft listing created: %s", listing_id)
        return listing_id
    logger.error("Failed to create listing: %s", result)
    return None


def upload_listing_image(shop_id: str, listing_id: str, image_path: str,
                          rank: int = 1) -> bool:
    """Upload an image to a listing. rank=1 is the primary/hero image."""
    path = Path(image_path)
    if not path.exists():
        logger.error("Image not found: %s", image_path)
        return False

    import mimetypes
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    files = {"image": (path.name, path.read_bytes(), mime_type)}
    data = {"rank": rank}

    result = _api_request(
        "POST",
        f"/application/shops/{shop_id}/listings/{listing_id}/images",
        files=files,
        data=data,
    )
    if result and "listing_image_id" in result:
        logger.info("Image uploaded: rank=%d for listing %s", rank, listing_id)
        return True
    logger.error("Image upload failed for listing %s", listing_id)
    return False


def upload_listing_file(shop_id: str, listing_id: str, file_path: str,
                         name: str = "") -> bool:
    """Upload a digital file (the actual product) to a listing."""
    path = Path(file_path)
    if not path.exists():
        logger.error("File not found: %s", file_path)
        return False

    if not name:
        name = path.name

    files = {"file": (name, path.read_bytes(), "application/octet-stream")}
    data = {"name": name}

    result = _api_request(
        "POST",
        f"/application/shops/{shop_id}/listings/{listing_id}/files",
        files=files,
        data=data,
    )
    if result and "listing_file_id" in result:
        logger.info("Digital file uploaded: %s for listing %s", name, listing_id)
        return True
    logger.error("File upload failed for listing %s", listing_id)
    return False


def activate_listing(shop_id: str, listing_id: str) -> bool:
    """Activate a draft listing (make it live).
    Etsy v3 OpenAPI spec: PATCH /application/shops/{shop_id}/listings/{listing_id}
    (PUT /application/listings/{id} 는 GET+DELETE만 지원, PUT 없음)
    """
    result = _api_request(
        "PATCH",
        f"/application/shops/{shop_id}/listings/{listing_id}",
        data="state=active",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if result is not None:
        logger.info("Listing activated: %s", listing_id)
        return True
    logger.error("Failed to activate listing %s", listing_id)
    return False


def get_shop_reviews(shop_id: str) -> Optional[int]:
    """샵 총 리뷰 수 반환. 실패 시 None."""
    result = _api_request("GET", f"/application/shops/{shop_id}")
    if result is None:
        return None
    # review_count가 0인 경우도 정확히 반환 (num_favorers는 찜 수 — 리뷰 수 아님)
    rc = result.get("review_count")
    return rc if rc is not None else 0


def get_listing_review_count(listing_id: str) -> int:
    """리스팅 개별 리뷰 수 반환. API 실패 시 -1 반환."""
    result = _api_request("GET", f"/application/listings/{listing_id}/reviews")
    if result is None:
        return -1
    return result.get("count", len(result.get("results", [])))


def get_active_listing_count(shop_id: str) -> Optional[int]:
    """샵 활성 리스팅 수 반환."""
    result = _api_request(
        "GET",
        f"/application/shops/{shop_id}/listings/active",
        params={"limit": 1},
    )
    if result:
        return result.get("count") or len(result.get("results", []))
    return None


def update_listing_price(shop_id: str, listing_id: str, price: float) -> bool:
    """리스팅 가격 업데이트."""
    result = _api_request(
        "PUT",
        f"/application/shops/{shop_id}/listings/{listing_id}",
        json={"price": round(price, 2)},
    )
    if result:
        logger.info("Price updated: listing=%s → $%.2f", listing_id, price)
        return True
    logger.error("Price update failed: listing=%s", listing_id)
    return False


def get_all_active_listings(shop_id: str) -> list[dict]:
    """샵의 모든 활성 리스팅 반환 (페이지네이션 처리)."""
    listings = []
    offset = 0
    limit = 100
    while True:
        result = _api_request(
            "GET",
            f"/application/shops/{shop_id}/listings/active",
            params={"limit": limit, "offset": offset},
        )
        if not result or not result.get("results"):
            break
        batch = result["results"]
        listings.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return listings


def get_listing_stats(shop_id: str, listing_id: str) -> Optional[dict]:
    """Get views, favorites, etc. for a listing."""
    result = _api_request(
        "GET",
        f"/application/listings/{listing_id}",
    )
    return result


def get_listing_transaction_count(shop_id: str, listing_id: str) -> int:
    """리스팅의 누적 판매(거래) 수 반환. API 실패 시 -1 반환 (삭제 보수적 처리)."""
    result = _api_request(
        "GET",
        f"/application/shops/{shop_id}/listings/{listing_id}/transactions",
    )
    if result is None:
        return -1  # API 실패 → 삭제 건너뜀 (안전 우선)
    return result.get("count", len(result.get("results", [])))


def upload_listing_video(shop_id: str, listing_id: str, video_path: str) -> bool:
    """리스팅 영상 업로드 (Etsy v3). MP4/MOV, 5~15초, 최소 720p."""
    try:
        with open(video_path, "rb") as vf:
            result = _api_request(
                "POST",
                f"/application/shops/{shop_id}/listings/{listing_id}/videos",
                files={"file": (Path(video_path).name, vf, "video/mp4")},
            )
        if result is not None:
            logger.info("Video uploaded: listing=%s", listing_id)
            return True
        logger.warning("Video upload failed: listing=%s", listing_id)
        return False
    except Exception as e:
        logger.error("Video upload exception: %s", e)
        return False


def delete_listing(shop_id: str, listing_id: str) -> bool:
    """리스팅 영구 삭제 (복구 불가)."""
    result = _api_request(
        "DELETE",
        f"/application/shops/{shop_id}/listings/{listing_id}",
    )
    return result is not None


# ── Full Publish Pipeline ──

def publish_product(product: Product, seo: SEOData, shop_id: str) -> Optional[Listing]:
    """
    Full publish pipeline:
    1. Create draft listing
    2. Upload mockup images (up to 10)
    3. Upload digital files
    4. Activate listing
    """
    # 1. Create draft
    listing_id = create_draft_listing(
        shop_id=shop_id,
        title=seo.title,
        description=seo.description,
        price=seo.price_usd,
        tags=seo.tags,
    )
    if not listing_id:
        return None

    # 2. Upload mockup images
    for rank, mockup_path in enumerate(product.mockup_paths[:10], start=1):
        if not upload_listing_image(shop_id, listing_id, mockup_path, rank):
            logger.warning("Mockup upload failed at rank %d, continuing...", rank)

    # 3. Upload digital files
    for file_path in product.file_paths:
        fname = Path(file_path).name
        if not upload_listing_file(shop_id, listing_id, file_path, fname):
            logger.warning("File upload failed: %s, continuing...", fname)

    # 4. Activate
    activated = activate_listing(shop_id, listing_id)

    listing = Listing(
        listing_id=listing_id,
        product_id=product.product_id,
        platform=Platform.ETSY,
        seo=seo,
        price_usd=seo.price_usd,
        published_at=None,  # set after confirmed active
    )

    if activated:
        from datetime import datetime
        listing.published_at = datetime.now()
        logger.info("Product %s published as listing %s", product.product_id, listing_id)
    else:
        logger.warning("Product %s created as draft %s (activation failed)", product.product_id, listing_id)

    return listing


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Etsy API module ready.")
    print("Run authorize_first_time() to authenticate with Etsy.")
