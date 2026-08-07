"""Listo Web-Backend: Login, eBay-/Telegram-Verifizierung, Abo (Stripe-ready).

Lokaler Start:  ./.venv/bin/python -m uvicorn web.server:app --port 8484

Modi:
- DEV (Default, kein SMTP/Stripe konfiguriert): Magic-Links werden direkt in der
  API-Antwort zurückgegeben statt gemailt; "Zahlung" aktiviert den Plan sofort.
- PROD: STRIPE_SECRET_KEY + STRIPE_PRICE_* in .env -> echtes Stripe Checkout;
  RESEND_API_KEY o.ä. für Mails (TODO beim Deploy); eBay-Callback verlangt
  eine öffentliche HTTPS-URL im RuName ("Auth Accepted URL").

Sicherheits-Kern: Der Telegram-Bot akzeptiert neue Nutzer NUR noch über
Link-Codes, die hier nach Registrierung erzeugt werden. Ohne Website-Konto
(Trial oder bezahlt) ignoriert der Bot jeden Fremden.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, File, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from bot.config import load_config
from bot.drafts import Store
from bot.ebay.account import AccountSetupError, create_location, get_or_create_policies
from bot.ebay.auth import EbayAuthError, EbayClient, _token_key

log = logging.getLogger("web")

SITE_DIR = Path(os.environ.get("LISTO_SITE_DIR", str(Path.home() / "listo-website")))
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
BOT_USERNAME = os.environ.get("LISTO_BOT_USERNAME", "EBAYSERO_bot")
PLANS = {"starter": "9,90 €", "reseller": "24,90 €", "shop": "59,90 €"}

# Synthetischer Token-Schlüssel für Accounts, die eBay vor Telegram verbinden:
# weit ausserhalb des Telegram-ID-Bereichs, Kollision ausgeschlossen.
ACCOUNT_UID_OFFSET = 10 ** 15

# Umgebungs-Schalter (Audit-Befund P1): "production" schaltet fail-closed —
# Checkout ohne Stripe-Key wird abgelehnt statt still gratis freizuschalten,
# Session-Cookies bekommen das Secure-Flag. Default "dev" = lokaler
# HTTP-Betrieb im LAN (Handy-PWA), dort darf Secure nicht gesetzt sein.
APP_ENV = os.environ.get("APP_ENV", "dev").strip().lower()
IS_PROD = APP_ENV == "production"

# Kanonische Basis-URL (Audit-Befund P1 „Host-Header"): Links, die das Haus
# verlassen (Login-Mail, Stripe-Redirects, OAuth-Callbacks), dürfen NIE aus dem
# Host-Header des Requests gebaut werden — der ist Angreifer-kontrolliert und
# würde z.B. den Magic-Link auf eine fremde Domain umbiegen. In Produktion ist
# PUBLIC_BASE_URL Pflicht; im Dev-Betrieb fällt sie auf request.base_url zurück
# (LAN-IP und localhost sollen beide funktionieren).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
if IS_PROD and not PUBLIC_BASE_URL:
    raise RuntimeError("APP_ENV=production verlangt PUBLIC_BASE_URL in der .env")


def public_base_url(request: Request) -> str:
    """Basis-URL ohne Slash am Ende, z.B. 'https://sero.app'."""
    return PUBLIC_BASE_URL or str(request.base_url).rstrip("/")


def account_token_uid(account_id: int) -> int:
    return ACCOUNT_UID_OFFSET + account_id


cfg = load_config(require_policies=False)
store = Store()
ebay = EbayClient(cfg, store)

_secret = store.kv_get("web_secret")
if not _secret:
    _secret = secrets.token_hex(32)
    store.kv_set("web_secret", _secret)
signer = URLSafeTimedSerializer(_secret, salt="listo-session")

app = FastAPI(title="Listo")

# Antworten komprimieren: die Sammlungs-Antwort schrumpft damit um ~80 %.
# SSE (text/event-stream) schließt Starlette selbst von der Kompression aus.
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ---------------------------------------------------------------- Sicherheit

# CSRF-Schutz (Audit P1): Browser senden bei Cross-Site-POSTs IMMER einen
# Origin-Header — stimmt der nicht mit unserem Host (oder PUBLIC_BASE_URL,
# oder der Capacitor-App) überein, ist es ein fremdes Formular: 403.
# Requests OHNE Origin (curl, Smoke-Test, ältere Clients) passieren — die
# Angriffsklasse ist browserbasiert und trägt den Header immer.
_SCHREIBEND = ("POST", "PUT", "PATCH", "DELETE")


def _netloc_norm(netloc: str, schema: str = "") -> str:
    """Host:Port mit wegnormalisierten Default-Ports (:80/:443) — hinter
    TLS-Terminierung trägt sonst eine Seite den Port und die andere nicht."""
    netloc = netloc.lower()
    if schema == "https" and netloc.endswith(":443"):
        return netloc[:-4]
    if schema == "http" and netloc.endswith(":80"):
        return netloc[:-3]
    return netloc


def _origin_erlaubt(request: Request) -> bool:
    origin = request.headers.get("origin", "")
    if not origin or origin == "null":
        return not origin           # "null" ist verdächtig (Sandbox/File) -> 403
    if origin.startswith("capacitor://") or origin.startswith("ionic://"):
        return True                 # native App-Hülle
    o = urllib.parse.urlparse(origin)
    host = _netloc_norm(o.netloc, o.scheme)
    # Hinter einem Proxy steht der echte Außen-Host in X-Forwarded-Host —
    # ohne diesen Fallback wäre JEDER POST 403, sobald der Proxy den
    # Host-Header nicht durchreicht (Review-Fund).
    kandidaten = {_netloc_norm(request.headers.get("host", "")),
                  _netloc_norm(request.headers.get("x-forwarded-host", ""))}
    if PUBLIC_BASE_URL:
        p = urllib.parse.urlparse(PUBLIC_BASE_URL)
        kandidaten.add(_netloc_norm(p.netloc, p.scheme))
    kandidaten.discard("")
    return host in kandidaten


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method in _SCHREIBEND and not _origin_erlaubt(request):
        log.warning("CSRF abgewehrt: Origin %s auf %s %s",
                    request.headers.get("origin"), request.method, request.url.path)
        return JSONResponse({"error": "Ungültige Anfrage-Herkunft."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self'")
    return response


def is_local_request(request: Request) -> bool:
    """Dev-Komfort (Codes in der API-Antwort) NUR für localhost.
    Der Schalter war standardmäßig AN und musste zum Deploy ausgeschaltet werden —
    wer das vergisst, verschenkt hinter jedem Reverse-Proxy (client.host ist dort
    immer 127.0.0.1) den Login-Code JEDES Kontos an jeden, der eine E-Mail-Adresse
    kennt. Jetzt umgekehrt: aus, außer man schaltet ihn bewusst ein — und selbst
    dann nie, wenn die Anfrage erkennbar durch einen Proxy kam."""
    if os.environ.get("SERO_DEV_CODES", "0") != "1":
        return False
    if request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip"):
        return False
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")


_rate: dict[str, list[float]] = {}


def rate_limited(key: str, max_hits: int, window_s: float = 900) -> bool:
    """Simpler In-Memory-Limiter (pro Prozess) gegen Code-Brute-Force."""
    now = time.time()
    hits = [t for t in _rate.get(key, []) if now - t < window_s]
    if len(hits) >= max_hits:
        _rate[key] = hits
        return True
    hits.append(now)
    _rate[key] = hits
    return False


# ---------------------------------------------------------------- Session

def current_account(request: Request) -> dict | None:
    cookie = request.cookies.get("listo_session")
    if not cookie:
        return None
    try:
        account_id = signer.loads(cookie, max_age=30 * 86400)
    except (BadSignature, SignatureExpired):
        return None
    return store.get_account(account_id)


def set_session(response: Response, account_id: int) -> None:
    response.set_cookie(
        "listo_session", signer.dumps(account_id),
        httponly=True, samesite="lax", max_age=30 * 86400, secure=IS_PROD,
    )


def require_account(request: Request) -> dict | JSONResponse:
    account = current_account(request)
    if not account:
        return JSONResponse({"error": "nicht angemeldet"}, status_code=401)
    return account


# ---------------------------------------------------------------- E-Mail (Resend)

EMAIL_FROM = os.environ.get("EMAIL_FROM", "SERO <onboarding@resend.dev>")


async def send_email(to: str, subject: str, body_html: str) -> bool:
    """Versand über Resend. Ohne RESEND_API_KEY: False (Aufrufer nutzt DEV-Modus)."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return False
    import httpx
    html = f"""
    <div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:440px;margin:0 auto;padding:32px 24px;">
      <div style="margin-bottom:28px;">
        <span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#102e5a;"></span>
        <span style="font-size:20px;font-weight:700;color:#111;vertical-align:2px;"> SERO</span>
      </div>
      {body_html}
      <p style="color:#999;font-size:12px;margin-top:32px;">Du hast diese E-Mail nicht erwartet? Dann kannst du sie einfach ignorieren.</p>
    </div>"""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
        )
    if resp.status_code >= 300:
        log.error("Resend-Fehler %s: %s", resp.status_code, resp.text[:300])
        return False
    return True


# ---------------------------------------------------------------- Auth

class EmailBody(BaseModel):
    email: str


@app.post("/api/signup")
@app.post("/api/login")
async def signup(request: Request, body: EmailBody):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email:
        return JSONResponse({"error": "Bitte eine gültige E-Mail angeben."}, status_code=400)
    # Der EINZIGE Auth-Endpunkt ohne Bremse: ohne die hier kann jeder beliebige
    # Fremdadressen zumüllen (jede Anfrage = eine echte Mail über unsere Domain)
    # und die Konten-Tabelle unbegrenzt aufblähen.
    ip = request.client.host if request.client else "?"
    if rate_limited(f"signup:{ip}", 5) or rate_limited(f"signup:{email}", 3):
        return JSONResponse({"error": "Zu viele Anfragen — bitte später erneut."}, status_code=429)
    account = store.create_account(email)
    code = store.create_link_code(account["id"], "login", ttl_s=900)
    login_url = f"/auth/{code}"
    sent = await send_email(
        email, "Dein SERO-Anmeldelink",
        f"""<h2 style="color:#111;">Willkommen bei SERO!</h2>
        <p style="color:#444;">Klick auf den Button, um dich anzumelden — der Link ist 15 Minuten gültig.</p>
        <a href="{public_base_url(request)}{login_url}"
           style="display:inline-block;background:#102e5a;color:#fff;font-weight:600;
                  padding:13px 28px;border-radius:10px;text-decoration:none;">Jetzt anmelden</a>""",
    )
    if sent:
        return {"sent": True}
    if is_local_request(request):
        log.info("DEV-Login-Link für %s ausgegeben (nur lokal)", email)
        return {"sent": True, "dev_login_url": login_url}
    log.warning("Kein Mail-Versand möglich für %s — Login-Link NICHT zugestellt", email)
    return {"sent": True}


class LoginBody(BaseModel):
    identifier: str


@app.post("/api/login-code")
async def login_code(request: Request, body: LoginBody):
    """Login-Schritt 1: E-Mail ODER Username -> Code wird verschickt (DEV: zurückgegeben)."""
    ip = request.client.host if request.client else "?"
    if rate_limited(f"code:{ip}", 6) or rate_limited(f"code:{body.identifier.lower()}", 6):
        return JSONResponse({"error": "Zu viele Versuche — bitte in 15 Minuten erneut."},
                            status_code=429)
    account = store.get_account_by_identifier(body.identifier)
    if not account:
        return JSONResponse({"error": "Kein Konto mit dieser E-Mail / diesem Usernamen gefunden."},
                            status_code=404)
    code = store.create_link_code(account["id"], "login", ttl_s=900)
    sent = await send_email(
        account["email"], f"{code} ist dein SERO-Anmeldecode",
        f"""<h2 style="color:#111;">Dein Anmeldecode</h2>
        <p style="color:#444;">Gib diesen Code auf der Anmeldeseite ein — er ist 15 Minuten gültig:</p>
        <div style="font-family:ui-monospace,monospace;font-size:28px;letter-spacing:4px;
                    background:#f2f5f9;border-radius:10px;padding:16px;text-align:center;
                    color:#111;font-weight:700;">{code}</div>""",
    )
    if sent:
        return {"sent": True}
    # Lokal (Dev): Code direkt zurückgeben — NICHT erst Telegram anstoßen
    if is_local_request(request):
        log.info("DEV-Login-Code für %s ausgegeben (nur lokal)", account["email"])
        return {"sent": True, "dev_code": code}
    # Kein E-Mail-Dienst konfiguriert? Konten mit verknüpftem Telegram bekommen
    # den Code über den SERO-Bot — funktioniert überall, auch auf dem iPhone.
    if account.get("telegram_id"):
        try:
            import os as _os
            import httpx as _httpx
            _tok = _os.environ.get("TELEGRAM_BOT_TOKEN")
            if _tok:
                async with _httpx.AsyncClient(timeout=10) as _c:
                    _r = await _c.post(
                        f"https://api.telegram.org/bot{_tok}/sendMessage",
                        json={"chat_id": account["telegram_id"],
                              "text": (f"🔐 Dein SERO-Anmeldecode: {code}"
                                       "\n\nGültig für 15 Minuten.")})
                if _r.status_code == 200:
                    log.info("Login-Code an Telegram %s gesendet", account["telegram_id"])
                    return {"sent": True, "via": "telegram"}
        except Exception:  # noqa: BLE001
            log.exception("Telegram-Code-Versand fehlgeschlagen")
    if is_local_request(request):
        log.info("DEV-Login-Code für %s ausgegeben (nur lokal)", account["email"])
        return {"sent": True, "dev_code": code}
    log.warning("Kein Zustellweg für Login-Code von Konto %s — weder Mail noch Telegram",
                account["id"])
    return {"sent": True}


class VerifyBody(BaseModel):
    identifier: str
    code: str


@app.post("/api/login-verify")
async def login_verify(request: Request, body: VerifyBody):
    """Login-Schritt 2: Code prüfen, Session setzen."""
    ip = request.client.host if request.client else "?"
    if rate_limited(f"verify:{ip}", 10):
        return JSONResponse({"error": "Zu viele Versuche — bitte in 15 Minuten erneut."},
                            status_code=429)
    account = store.get_account_by_identifier(body.identifier)
    if not account:
        return JSONResponse({"error": "Konto nicht gefunden."}, status_code=404)
    redeemed = store.redeem_link_code(body.code.strip().upper(), "login")
    if redeemed != account["id"]:
        return JSONResponse({"error": "Code ungültig oder abgelaufen."}, status_code=400)
    response = JSONResponse({"ok": True})
    set_session(response, account["id"])
    return response


@app.post("/api/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("listo_session")
    return response


class ProfileBody(BaseModel):
    display_name: str | None = None
    username: str | None = None
    ebay_shop: str | None = None
    render_color: str | None = None


@app.post("/api/profile")
async def update_profile(request: Request, body: ProfileBody):
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    ip = request.client.host if request.client else "?"
    if rate_limited(f"profile:{ip}", 20, window_s=600):
        return JSONResponse({"error": "Zu viele Änderungen — kurz warten."}, status_code=429)
    fields = {}
    if body.username is not None:
        username = body.username.strip()
        if username:
            if not username.replace("_", "").replace("-", "").isalnum() or len(username) < 3:
                return JSONResponse({"error": "Username: min. 3 Zeichen, nur Buchstaben/Zahlen/-/_"},
                                    status_code=400)
            existing = store.get_account_by_username(username)
            if existing and existing["id"] != account["id"]:
                return JSONResponse({"error": "Dieser Username ist schon vergeben."}, status_code=409)
            fields["username"] = username
    if body.display_name is not None:
        dn = body.display_name.strip()[:40]
        fields["display_name"] = dn or None
    if body.ebay_shop is not None:
        fields["ebay_shop"] = body.ebay_shop.strip().lstrip("@") or None
    if fields:
        store.update_account(account["id"], **fields)
    if body.render_color and account.get("telegram_id"):
        from bot.render import normalize_hex_color
        color = normalize_hex_color(body.render_color)
        if color:
            store.upsert_user(account["telegram_id"], render_color=color)
    return {"ok": True}


async def _save_upload(account: dict, file: UploadFile, kind: str, max_px: int) -> str:
    from PIL import Image, ImageOps
    import io
    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise ValueError("Datei zu groß (max. 15 MB).")
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_px, max_px))
    # Unratbarer Name: /uploads liegt ohne Login offen — mit "avatar-1.jpg",
    # "avatar-2.jpg" … konnte jeder die Profilbilder aller Konten durchzählen.
    import secrets
    name = f"{kind}-{account['id']}-{secrets.token_hex(12)}.jpg"
    for alt in UPLOADS_DIR.glob(f"{kind}-{account['id']}-*.jpg"):
        alt.unlink(missing_ok=True)          # alte Fassung nicht liegen lassen
    legacy = UPLOADS_DIR / f"{kind}-{account['id']}.jpg"
    legacy.unlink(missing_ok=True)
    img.save(UPLOADS_DIR / name, "JPEG", quality=90)
    return str(UPLOADS_DIR / name)


@app.post("/api/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    try:
        path = await _save_upload(account, file, "avatar", 512)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"Bild konnte nicht verarbeitet werden: {e}"}, status_code=400)
    store.update_account(account["id"], avatar_path=path)
    return {"ok": True, "avatar_url": f"/uploads/{Path(path).name}"}


@app.post("/api/background")
async def upload_background(request: Request, file: UploadFile = File(...)):
    """Eigener Render-Hintergrund (z.B. Weißton mit Logo) — der Bot nutzt ihn ab sofort."""
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    try:
        path = await _save_upload(account, file, "bg", 1600)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"Bild konnte nicht verarbeitet werden: {e}"}, status_code=400)
    store.update_account(account["id"], render_bg_path=path)
    return {"ok": True, "bg_url": f"/uploads/{Path(path).name}"}


@app.post("/api/background-remove")
async def remove_background(request: Request):
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    store.update_account(account["id"], render_bg_path=None)
    return {"ok": True}


@app.get("/auth/{code}")
async def auth(code: str, request: Request):
    ip = request.client.host if request.client else "?"
    if rate_limited(f"auth:{ip}", 10):
        return RedirectResponse("/login.html?expired=1")
    account_id = store.redeem_link_code(code, "login")
    if not account_id:
        return RedirectResponse("/login.html?expired=1")
    response = RedirectResponse("/onboarding.html?logged_in=1")
    set_session(response, account_id)
    return response


@app.get("/api/me")
async def me(request: Request):
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    has_token = bool(
        store.kv_get(_token_key(account_token_uid(account["id"])))
        or (account.get("telegram_id") and store.kv_get(_token_key(account["telegram_id"])))
    )
    # Effektive Nutzer-ID wie in app_api.uid_for: Telegram-ID falls verknüpft,
    # sonst die synthetische App-ID. Vorher lief das nur über telegram_id —
    # reine App-Nutzer bekamen dadurch IMMER setup_ready=false (Audit P0.3).
    uid = account.get("telegram_id") or account_token_uid(account["id"])
    user = store.get_user(uid)
    trial_days = max(0, int((account.get("trial_until", 0) - time.time()) / 86400))
    plan_limits = {"starter": 30, "reseller": 200, "shop": None}
    limit = plan_limits.get(account["plan"])
    used = store.listings_this_month(uid)
    return {
        "email": account["email"],
        "username": account.get("username"),
        "display_name": account.get("display_name"),
        "member_since": account.get("created_at"),
        "avatar_url": f"/uploads/{Path(account['avatar_path']).name}" if account.get("avatar_path") else None,
        "bg_url": f"/uploads/{Path(account['render_bg_path']).name}" if account.get("render_bg_path") else None,
        "render_color": (user or {}).get("render_color") or "#ffffff",
        "ebay_shop": account.get("ebay_shop"),
        "plan": account["plan"],
        "plan_limit": limit,
        "used_this_month": used,
        "trial_days_left": trial_days,
        "active": store.account_active(account),
        "ebay_connected": has_token,
        "telegram_linked": bool(account.get("telegram_id")),
        "setup_ready": bool(user and user.get("status") == "ready"),
        "bot_username": BOT_USERNAME,
        "is_admin": account["email"] == ADMIN_EMAIL,
    }


# ---------------------------------------------------------------- eBay verbinden

@app.get("/connect/ebay")
async def connect_ebay(request: Request):
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    state = signer.dumps({"a": account["id"], "t": time.time()})
    url = ebay.build_consent_url() + "&state=" + urllib.parse.quote(state)
    return RedirectResponse(url)


async def _store_ebay_token(account: dict, code: str) -> None:
    uid = account_token_uid(account["id"])
    await ebay.exchange_code(code, uid)
    # Telegram schon verknüpft? Token direkt dem Telegram-Nutzer zuordnen.
    if account.get("telegram_id"):
        store.kv_set(_token_key(account["telegram_id"]), store.kv_get(_token_key(uid)))


@app.get("/callback/ebay")
async def callback_ebay(request: Request, code: str = "", state: str = ""):
    """Automatischer Rückweg — funktioniert erst, wenn die RuName 'Auth Accepted URL'
    auf die deployte HTTPS-Domain zeigt. Lokal: Paste-Flow unten."""
    try:
        payload = signer.loads(state)
    except BadSignature:
        return RedirectResponse("/onboarding.html?ebay=invalid")
    account = store.get_account(payload["a"])
    if not account or not code:
        return RedirectResponse("/onboarding.html?ebay=invalid")
    try:
        await _store_ebay_token(account, code)
    except EbayAuthError:
        return RedirectResponse("/onboarding.html?ebay=failed")
    return RedirectResponse("/onboarding.html?ebay=ok")


class RedirectBody(BaseModel):
    url: str


@app.post("/api/ebay-redirect")
async def ebay_redirect_paste(request: Request, body: RedirectBody):
    """Lokaler Fallback: Nutzer pastet die eBay-Redirect-URL ins Formular."""
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    query = urllib.parse.urlparse(body.url.strip()).query or body.url.split("?", 1)[-1]
    params = urllib.parse.parse_qs(query)
    code = params.get("code", [None])[0]
    if not code:
        return JSONResponse({"error": "Kein code= in der URL gefunden."}, status_code=400)
    try:
        await _store_ebay_token(account, code)
    except EbayAuthError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}


class EbaySetupBody(BaseModel):
    street: str = ""
    postal_code: str = ""
    city: str = ""


_setup_locks: dict[int, "asyncio.Lock"] = {}


@app.post("/api/ebay-setup")
async def ebay_setup(request: Request, body: EbaySetupBody):
    """eBay-Verkaufs-Setup komplett im Web (Audit P0.3): Verkaufsrichtlinien
    anlegen bzw. übernehmen und den Versandstandort setzen. Vorher existierte
    dieser Schritt NUR im Telegram-Bot — ein App-Nutzer ohne Telegram kam bis
    zum Listing-Knopf und scheiterte dort."""
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    uid = account.get("telegram_id") or account_token_uid(account["id"])
    if not store.kv_get(_token_key(uid)):
        return JSONResponse({"error": "Bitte zuerst dein eBay-Konto verbinden."},
                            status_code=400)

    import asyncio
    async with _setup_locks.setdefault(uid, asyncio.Lock()):
        return await _ebay_setup_innen(account, uid, body)


async def _ebay_setup_innen(account: dict, uid: int, body: EbaySetupBody):
    # Pro uid serialisiert (Review-Fund: Doppel-POST von zwei Geräten legte
    # Richtlinien doppelt an — eBay lehnt den zweiten mit Duplicate-Name ab
    # und der Nutzer sah einen Fehler auf einem erfolgreichen Onboarding).
    try:
        policies = await get_or_create_policies(ebay, uid)
    except (AccountSetupError, EbayAuthError) as e:
        log.exception("Web-Onboarding: Richtlinien für uid %s fehlgeschlagen", uid)
        return JSONResponse({"error": f"Richtlinien-Einrichtung fehlgeschlagen:\n{e}"},
                            status_code=502)
    store.upsert_user(uid, status="connecting", **policies)

    if store.get_user(uid).get("merchant_location_key"):
        store.upsert_user(uid, status="ready")
        return {"ok": True, "ready": True}

    street = body.street.strip()
    plz = body.postal_code.strip()
    city = body.city.strip()
    if not (street and plz.isdigit() and len(plz) == 5 and city):
        # Richtlinien sind angelegt; es fehlt nur noch die Adresse. Die UI
        # zeigt daraufhin das Adressformular (need_address).
        return JSONResponse({"error": "Deine Versandadresse fehlt noch: Straße mit "
                                      "Hausnummer, fünfstellige PLZ und Stadt.",
                             "need_address": True}, status_code=400)
    try:
        await create_location(ebay, uid, f"listo-{uid}", street, plz, city)
    except (AccountSetupError, EbayAuthError) as e:
        log.exception("Web-Onboarding: Standort für uid %s fehlgeschlagen", uid)
        return JSONResponse({"error": f"Versandstandort konnte nicht angelegt werden:\n{e}"},
                            status_code=502)
    store.upsert_user(uid, merchant_location_key=f"listo-{uid}", status="ready")
    log.info("Web-Onboarding komplett für uid %s (Account %s)", uid, account["id"])
    return {"ok": True, "ready": True}


# ---------------------------------------------------------------- Telegram verbinden

@app.post("/api/telegram-code")
async def telegram_code(request: Request):
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    code = store.create_link_code(account["id"], "telegram", ttl_s=3600)
    return {"code": code, "bot": BOT_USERNAME, "url": f"https://t.me/{BOT_USERNAME}"}


# ---------------------------------------------------------------- Abo / Zahlung

class CheckoutBody(BaseModel):
    plan: str


@app.post("/api/checkout")
async def checkout(request: Request, body: CheckoutBody):
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    if body.plan not in PLANS:
        return JSONResponse({"error": "Unbekannter Plan."}, status_code=400)

    stripe_key = os.environ.get("STRIPE_SECRET_KEY")
    if stripe_key:
        import stripe  # pip install stripe — erst beim Deploy nötig
        stripe.api_key = stripe_key
        price_id = os.environ.get(f"STRIPE_PRICE_{body.plan.upper()}")
        if not price_id:
            return JSONResponse({"error": f"STRIPE_PRICE_{body.plan.upper()} fehlt in .env"},
                                status_code=500)
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=account["email"],
            subscription_data={"trial_period_days": 14},
            success_url=public_base_url(request) + "/onboarding.html?paid=1&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=public_base_url(request) + "/onboarding.html?paid=0",
            metadata={"account_id": account["id"], "plan": body.plan},
        )
        return {"checkout_url": session.url}

    # Ohne Stripe-Key: in Produktion HART ablehnen (vorher: Plan wurde still
    # gratis aktiviert — Audit-Befund P1 „Stripe fail-open"). Nur im
    # Dev-Betrieb wird die Zahlung simuliert.
    if IS_PROD:
        log.error("Checkout ohne STRIPE_SECRET_KEY in Produktion abgelehnt (Account %s)",
                  account["id"])
        return JSONResponse({"error": "Bezahlung ist gerade nicht verfügbar."},
                            status_code=503)
    store.update_account(account["id"], plan=body.plan)
    log.info("DEV-Checkout: Account %s -> Plan %s", account["id"], body.plan)
    return {"ok": True, "dev": True, "plan": body.plan}


class CheckoutConfirmBody(BaseModel):
    session_id: str


@app.post("/api/checkout-confirm")
async def checkout_confirm(request: Request, body: CheckoutConfirmBody):
    """Nach Rückkehr vom Stripe-Checkout: Session serverseitig verifizieren und Plan
    aktivieren. Nötig, solange der Webhook den Server nicht erreichen kann (lokal);
    in Produktion zusätzlich zum Webhook unschädlich (idempotent)."""
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    stripe_key = os.environ.get("STRIPE_SECRET_KEY")
    if not stripe_key:
        return JSONResponse({"error": "Stripe nicht konfiguriert"}, status_code=501)
    import stripe
    stripe.api_key = stripe_key
    try:
        session = stripe.checkout.Session.retrieve(body.session_id)
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "Checkout-Session nicht gefunden."}, status_code=400)
    meta = getattr(session, "metadata", None)
    meta_account = getattr(meta, "account_id", None) if meta else None
    if str(meta_account) != str(account["id"]):
        return JSONResponse({"error": "Session gehört nicht zu diesem Konto."}, status_code=403)
    if getattr(session, "status", None) != "complete":
        return JSONResponse({"error": "Zahlung noch nicht abgeschlossen."}, status_code=400)
    plan = getattr(meta, "plan", None) or "starter"
    store.update_account(account["id"], plan=plan,
                         stripe_customer_id=getattr(session, "customer", None))
    log.info("Checkout bestätigt: Account %s -> Plan %s", account["id"], plan)
    return {"ok": True, "plan": plan}


@app.post("/api/billing-portal")
async def billing_portal(request: Request):
    """Stripe-Kundenportal: Zahlungsmethode ändern, Rechnungen, kündigen, upgraden."""
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    stripe_key = os.environ.get("STRIPE_SECRET_KEY")
    if not stripe_key:
        return {"dev": True,
                "message": "Test-Modus: Das echte Stripe-Kundenportal (Rechnungen, Kündigung, "
                           "Zahlungsmethode) erscheint hier, sobald Stripe live geschaltet ist."}
    if not account.get("stripe_customer_id"):
        return JSONResponse({"error": "Noch keine Zahlung hinterlegt — erst einen Plan abschließen."},
                            status_code=400)
    import stripe
    stripe.api_key = stripe_key
    session = stripe.billing_portal.Session.create(
        customer=account["stripe_customer_id"],
        return_url=public_base_url(request) + "/app.html",
    )
    return {"portal_url": session.url}


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        return JSONResponse({"error": "Webhook nicht konfiguriert"}, status_code=501)
    import stripe
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "ungültige Signatur"}, status_code=400)
    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        meta = obj.get("metadata") or {}
        if meta.get("account_id"):
            store.update_account(int(meta["account_id"]), plan=meta.get("plan", "starter"),
                                 stripe_customer_id=obj.get("customer"))
    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        row = store._conn.execute(  # noqa: SLF001 — kleiner Direktzugriff, bewusst
            "SELECT id FROM accounts WHERE stripe_customer_id = ?", (obj.get("customer"),)
        ).fetchone()
        if row:
            store.update_account(row["id"], plan="cancelled")
    return {"ok": True}


# ---------------------------------------------------------------- Analytics & Launch-Liste

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "sven.manuel@aol.com")

store._conn.execute(  # noqa: SLF001
    "CREATE TABLE IF NOT EXISTS pageviews (ts REAL, path TEXT, ref TEXT, lang TEXT)")
store._conn.execute(  # noqa: SLF001
    "CREATE TABLE IF NOT EXISTS launch_emails (email TEXT PRIMARY KEY, ts REAL)")
store._conn.commit()  # noqa: SLF001


class EventBody(BaseModel):
    path: str
    ref: str = ""
    lang: str = ""


@app.post("/api/event")
async def track_event(body: EventBody, request: Request):
    """Cookiefreier Pageview-Zähler — keine IP, keine User-Kennung (DSGVO-schonend)."""
    import time
    ip = request.client.host if request.client else "?"
    if rate_limited(f"event:{ip}", 60, window_s=60):
        return {"ok": True}   # still schlucken — Zähler ist unkritisch
    with store._lock:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "INSERT INTO pageviews (ts, path, ref, lang) VALUES (?, ?, ?, ?)",
            (time.time(), body.path[:120], body.ref[:200], body.lang[:8]))
        store._conn.commit()  # noqa: SLF001
    return {"ok": True}


@app.post("/api/launch-notify")
async def launch_notify(body: EmailBody, request: Request):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email:
        return JSONResponse({"error": "Bitte eine gültige E-Mail angeben."}, status_code=400)
    import time
    ip = request.client.host if request.client else "?"
    if rate_limited(f"notify:{ip}", 10, window_s=3600):
        return {"ok": True}
    with store._lock:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "INSERT OR IGNORE INTO launch_emails (email, ts) VALUES (?, ?)", (email, time.time()))
        store._conn.commit()  # noqa: SLF001
    return {"ok": True}


@app.get("/api/stats")
async def stats(request: Request):
    """KPI-Überblick, nur für den Admin-Account."""
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    if account["email"] != ADMIN_EMAIL:
        return JSONResponse({"error": "nur für den Admin"}, status_code=403)
    import time
    now = time.time()
    q = store._conn.execute  # noqa: SLF001
    views_today = q("SELECT COUNT(*) FROM pageviews WHERE ts > ?", (now - 86400,)).fetchone()[0]
    views_7d = q("SELECT COUNT(*) FROM pageviews WHERE ts > ?", (now - 7 * 86400,)).fetchone()[0]
    top_refs = q("SELECT ref, COUNT(*) c FROM pageviews WHERE ref != '' AND ts > ? "
                 "GROUP BY ref ORDER BY c DESC LIMIT 10", (now - 30 * 86400,)).fetchall()
    accounts_total = q("SELECT COUNT(*) FROM accounts").fetchone()[0]
    paid = q("SELECT COUNT(*) FROM accounts WHERE plan IN ('starter','reseller','shop')").fetchone()[0]
    listings_30d = q("SELECT COUNT(*) FROM listings WHERE created_at > ? AND dry_run = 0",
                     (now - 30 * 86400,)).fetchone()[0] if _table_has(q, "listings", "created_at") else None
    launch_list = q("SELECT COUNT(*) FROM launch_emails").fetchone()[0]
    return {
        "pageviews_24h": views_today, "pageviews_7d": views_7d,
        "top_referrers": [{"ref": r[0], "count": r[1]} for r in top_refs],
        "accounts": accounts_total, "paid_accounts": paid,
        "published_listings_30d": listings_30d,
        "launch_list": launch_list,
    }


def _table_has(q, table: str, column: str) -> bool:
    return any(r[1] == column for r in q(f"PRAGMA table_info({table})").fetchall())


# ---------------------------------------------------------------- Website-Texte (Admin-Editor)

SITE_LANGS = ["de", "en", "es", "it", "fr"]

store._conn.execute(  # noqa: SLF001
    "CREATE TABLE IF NOT EXISTS i18n_overrides ("
    "page TEXT, key TEXT, lang TEXT, text TEXT, PRIMARY KEY (page, key, lang))")
store._conn.commit()  # noqa: SLF001


@app.get("/api/i18n")
async def i18n_get(page: str):
    """Text-Überschreibungen einer Seite — öffentlich, wird von jedem Besucher geladen."""
    rows = store._conn.execute(  # noqa: SLF001
        "SELECT key, lang, text FROM i18n_overrides WHERE page = ?", (page,)).fetchall()
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        out.setdefault(r["key"], {})[r["lang"]] = r["text"]
    return out


class I18nBody(BaseModel):
    page: str
    key: str
    text: str
    source_lang: str = "de"


async def _translate_text(text: str, source_lang: str) -> dict[str, str]:
    """Übersetzt einen Website-Text in alle anderen Sprachen (Claude)."""
    import anthropic
    targets = [lg for lg in SITE_LANGS if lg != source_lang]
    client = anthropic.AsyncAnthropic()
    msg = await client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-opus-4-8"),
        max_tokens=1500,
        system=(
            "Du übersetzt Marketing-Texte einer Website für einen eBay-Listing-Service. "
            "Behalte HTML-Tags (<br>, <strong>, …), Emojis und Platzhalter wie {plan} exakt bei. "
            "Ton: locker, direkt, du-Form bzw. landesüblich. Antworte NUR mit einem JSON-Objekt, "
            "Keys sind die Sprachcodes, Values die Übersetzungen."
        ),
        messages=[{"role": "user", "content":
                   f"Quellsprache: {source_lang}\nZielsprachen: {', '.join(targets)}\n\nText:\n{text}"}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    import json as _json
    data = _json.loads(raw)
    return {lg: str(data[lg]) for lg in targets if lg in data}


@app.post("/api/i18n")
async def i18n_set(request: Request, body: I18nBody):
    """Admin speichert geänderten Text -> automatische Übersetzung in alle Sprachen."""
    account = require_account(request)
    if isinstance(account, JSONResponse):
        return account
    if account["email"] != ADMIN_EMAIL:
        return JSONResponse({"error": "nur für den Admin"}, status_code=403)
    text = body.text.strip()
    if not text:
        return JSONResponse({"error": "Leerer Text."}, status_code=400)
    try:
        translations = await _translate_text(text, body.source_lang)
    except Exception:  # noqa: BLE001
        log.exception("Übersetzung fehlgeschlagen")
        return JSONResponse({"error": "Übersetzung fehlgeschlagen — bitte nochmal versuchen."},
                            status_code=502)
    translations[body.source_lang] = text
    for lg, txt in translations.items():
        store._conn.execute(  # noqa: SLF001
            "INSERT INTO i18n_overrides (page, key, lang, text) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(page, key, lang) DO UPDATE SET text = excluded.text",
            (body.page, body.key, lg, txt))
    store._conn.commit()  # noqa: SLF001
    log.info("i18n-Override gespeichert: %s %s (%d Sprachen)", body.page, body.key, len(translations))
    return {"ok": True, "translations": translations}


# ---------------------------------------------------------------- Social Login (OAuth)
# Aktiviert sich selbst, sobald die Keys in .env liegen:
#   Google: GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET  (console.cloud.google.com -> OAuth-Client "Web",
#           Redirect-URI: https://DOMAIN/auth/google/callback — lokal geht http://localhost:8484/...)
#   Apple:  APPLE_CLIENT_ID + APPLE_CLIENT_SECRET    (Apple-Developer-Konto nötig; Secret = signiertes JWT)
#   X:      X_CLIENT_ID + X_CLIENT_SECRET            (developer.x.com, OAuth 2.0 mit PKCE)

OAUTH_PROVIDERS = {
    "google": (os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")),
    "apple": (os.environ.get("APPLE_CLIENT_ID"), os.environ.get("APPLE_CLIENT_SECRET")),
    "x": (os.environ.get("X_CLIENT_ID"), os.environ.get("X_CLIENT_SECRET")),
}


@app.get("/api/auth-providers")
async def auth_providers():
    """Welche Social-Logins sind konfiguriert? (Login-Seite blendet Buttons entsprechend ein.)"""
    return {"providers": [k for k, (cid, sec) in OAUTH_PROVIDERS.items() if cid and sec]}


@app.get("/auth/google/start")
async def google_start(request: Request):
    cid, sec = OAUTH_PROVIDERS["google"]
    if not (cid and sec):
        return JSONResponse({"error": "Google-Login ist noch nicht konfiguriert "
                                      "(GOOGLE_CLIENT_ID/SECRET in .env eintragen)."}, status_code=501)
    state = signer.dumps({"p": "google", "t": time.time()})
    redirect_uri = public_base_url(request) + "/auth/google/callback"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": "openid email", "state": state, "prompt": "select_account",
    })
    return RedirectResponse(url)


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", state: str = ""):
    import httpx as _httpx
    cid, sec = OAUTH_PROVIDERS["google"]
    try:
        payload = signer.loads(state)
        assert payload.get("p") == "google" and time.time() - payload.get("t", 0) < 600
    except Exception:  # noqa: BLE001
        return RedirectResponse("/app/?login=invalid")
    if not code:
        return RedirectResponse("/app/?login=cancelled")
    redirect_uri = public_base_url(request) + "/auth/google/callback"
    async with _httpx.AsyncClient(timeout=15) as client:
        tok = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": cid, "client_secret": sec,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
        if tok.status_code != 200:
            log.error("Google-Token-Tausch fehlgeschlagen: %s", tok.text[:300])
            return RedirectResponse("/app/?login=failed")
        id_token = tok.json().get("id_token", "")
        info = await client.get("https://oauth2.googleapis.com/tokeninfo",
                                params={"id_token": id_token})
    data = info.json() if info.status_code == 200 else {}
    if data.get("aud") != cid or data.get("email_verified") not in ("true", True) or not data.get("email"):
        return RedirectResponse("/app/?login=failed")
    account = store.create_account(data["email"])
    response = RedirectResponse("/app/")
    set_session(response, account["id"])
    log.info("Google-Login: %s", data["email"])
    return response


@app.get("/auth/{provider}/start")
async def oauth_not_ready(provider: str):
    if provider in ("apple", "x"):
        return JSONResponse({"error": f"{provider.title()}-Login ist vorbereitet, braucht aber "
                                      "noch Entwickler-Zugangsdaten in .env."}, status_code=501)
    return JSONResponse({"error": "Unbekannter Anbieter."}, status_code=404)


# ---------------------------------------------------------------- SERO-App (Chat-API + Frontend)

from web.app_api import build_router  # noqa: E402 — braucht store/ebay/cfg von oben

app.include_router(build_router(store, ebay, cfg))

# Frontend liegt im selben Repo unter frontend/ (früher ~/sero-app/web).
_REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(os.environ.get("SERO_APP_DIR", str(_REPO_ROOT / "frontend")))

# ---------------------------------------------------------------- Statische Dateien (zuletzt!)

class NoCacheHTML(StaticFiles):
    """HTML immer neu validieren — die iOS-Homescreen-App cachte index.html
    sonst tagelang und sah Updates (neue ?v=-Pins) nie. Assets bleiben cachebar,
    ihre Frische steuern die Versions-Pins."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if "text/html" in (resp.headers.get("content-type") or ""):
            resp.headers["Cache-Control"] = "no-cache"
        return resp


if APP_DIR.exists():
    app.mount("/app", NoCacheHTML(directory=str(APP_DIR), html=True), name="seroapp")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(SITE_DIR), html=True), name="site")
