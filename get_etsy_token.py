"""
Etsy OAuth 2.0 토큰 발급 스크립트
실행하면 브라우저가 열리고 Etsy 로그인 후 자동으로 토큰이 .env에 저장됨
"""
import sys
import os
import hashlib
import base64
import secrets
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# ── 설정 ──
API_KEY    = "klf7gn70u2975bxbxcv7lzkt"
API_SECRET = "rhzbka46yl"
REDIRECT_PORT = 3000
REDIRECT_URI  = f"http://localhost:{REDIRECT_PORT}/callback"
ENV_PATH = Path(__file__).parent / ".env"

SCOPES = "listings_r listings_w shops_r shops_w transactions_r"

# ── PKCE ──
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()

# ── 인증 URL 생성 ──
params = {
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPES,
    "client_id": API_KEY,
    "state": secrets.token_urlsafe(16),
    "code_challenge": code_challenge,
    "code_challenge_method": "S256",
}
auth_url = f"https://www.etsy.com/oauth/connect?{urlencode(params)}"

print("=" * 60)
print("Etsy OAuth 인증 시작")
print("=" * 60)
print(f"\n브라우저가 열립니다. Etsy 로그인 후 '허용'을 눌러주세요.")
print(f"URL: {auth_url}\n")


# ── 콜백 서버 ──
class CallbackHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        CallbackHandler.auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>OK! Token received. You can close this tab.</h2>")

    def log_message(self, *args):
        pass


print("\n" + "=" * 60)
print("아래 URL을 복사해서 브라우저 주소창에 직접 붙여넣으세요:")
print("=" * 60)
print(auth_url)
print("=" * 60 + "\n")
input("브라우저에서 Etsy 로그인 + 허용 완료 후 Enter 키를 누르세요...")
print("콜백 대기 중...")

server = HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
server.handle_request()

auth_code = CallbackHandler.auth_code
if not auth_code:
    print("ERROR: 인증 코드를 받지 못했습니다.")
    sys.exit(1)

print(f"인증 코드 수신 완료.")

# ── 토큰 교환 ──
token_resp = requests.post(
    "https://api.etsy.com/v3/public/oauth/token",
    data={
        "grant_type": "authorization_code",
        "client_id": API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code,
        "code_verifier": code_verifier,
    },
    timeout=30,
)

if not token_resp.ok:
    print(f"ERROR: 토큰 교환 실패 — {token_resp.status_code}: {token_resp.text}")
    sys.exit(1)

tokens = token_resp.json()
access_token  = tokens.get("access_token", "")
refresh_token = tokens.get("refresh_token", "")

print(f"\nAccess Token:  {access_token[:30]}...")
print(f"Refresh Token: {refresh_token[:30]}...")

# ── Shop ID 조회 ──
shop_resp = requests.get(
    "https://openapi.etsy.com/v3/application/users/me",
    headers={
        "Authorization": f"Bearer {access_token}",
        "x-api-key": API_KEY,
    },
    timeout=20,
)
shop_id = ""
if shop_resp.ok:
    user_data = shop_resp.json()
    # shop_id는 /users/me 에 없을 수 있음 — shops 엔드포인트로 조회
    shops_resp = requests.get(
        f"https://openapi.etsy.com/v3/application/users/{user_data.get('user_id', 0)}/shops",
        headers={
            "Authorization": f"Bearer {access_token}",
            "x-api-key": API_KEY,
        },
        timeout=20,
    )
    if shops_resp.ok:
        shops_data = shops_resp.json()
        shop_id = str(shops_data.get("shop_id", ""))
        print(f"Shop ID: {shop_id}  ({shops_data.get('shop_name', '')})")

# ── .env 업데이트 ──
env_text = ENV_PATH.read_text(encoding="utf-8")

def update_env(text, key, value):
    import re
    pattern = rf'^{key}=.*$'
    replacement = f'{key}={value}'
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, replacement, text, flags=re.MULTILINE)
    return text + f'\n{key}={value}'

env_text = update_env(env_text, "ETSY_ACCESS_TOKEN",  access_token)
env_text = update_env(env_text, "ETSY_REFRESH_TOKEN", refresh_token)
if shop_id:
    env_text = update_env(env_text, "ETSY_SHOP_ID", shop_id)

ENV_PATH.write_text(env_text, encoding="utf-8")
print(f"\n.env 업데이트 완료!")
print("=" * 60)
print("이제 자동화를 실행할 수 있습니다.")
print("=" * 60)
