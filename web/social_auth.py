"""Social-Login-Helfer: Telegram-Widget-Hash, Telefon-Normalisierung.

Keine Secrets hier — Keys kommen aus der Umgebung. Google-OAuth bleibt in
web/server.py (bereits implementiert).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from typing import Any


def google_configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def telegram_bot_token() -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def telegram_bot_username() -> str:
    return (os.environ.get("LISTO_BOT_USERNAME") or os.environ.get("TELEGRAM_BOT_USERNAME") or "").strip().lstrip("@")


def telegram_login_enabled() -> bool:
    """Widget-Login an, sobald Bot-Token da ist (Domain bei BotFather setzen)."""
    flag = (os.environ.get("SERO_TELEGRAM_LOGIN") or "1").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    return bool(telegram_bot_token() and telegram_bot_username())


def phone_sms_configured() -> bool:
    """Twilio (oder kompatibel) — ohne Keys kein echter SMS-Versand."""
    return bool(
        os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and os.environ.get("TWILIO_FROM")
    )


def phone_auth_enabled() -> bool:
    """UI/API: an mit SMS-Keys, oder lokal mit SERO_PHONE_AUTH=stub."""
    mode = (os.environ.get("SERO_PHONE_AUTH") or "").strip().lower()
    if mode in ("0", "false", "off", "no"):
        return False
    if phone_sms_configured():
        return True
    if mode in ("1", "true", "on", "stub", "dev"):
        return True
    return False


def phone_auth_mode() -> str:
    if phone_sms_configured():
        return "twilio"
    if phone_auth_enabled():
        return "stub"
    return "off"


def normalize_phone(raw: str) -> str | None:
    """E.164-ähnlich: nur Ziffern und führendes +. DE-Kurzform 017… → +4917…"""
    s = (raw or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not s:
        return None
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("0") and not s.startswith("+"):
        s = "+49" + s[1:]
    if not s.startswith("+"):
        s = "+" + s
    digits = re.sub(r"\D", "", s)
    if len(digits) < 10 or len(digits) > 15:
        return None
    return "+" + digits


def verify_telegram_login(data: dict[str, Any], bot_token: str, *, max_age_s: int = 86400) -> bool:
    """Prüft Telegram Login Widget /hash laut Bot-API-Doku."""
    if not bot_token or not isinstance(data, dict):
        return False
    recv_hash = str(data.get("hash") or "")
    if not recv_hash:
        return False
    try:
        auth_date = int(data.get("auth_date") or 0)
    except (TypeError, ValueError):
        return False
    if auth_date <= 0 or abs(time.time() - auth_date) > max_age_s:
        return False
    pairs = []
    for k in sorted(data.keys()):
        if k == "hash":
            continue
        v = data.get(k)
        if v is None or v == "":
            continue
        pairs.append(f"{k}={v}")
    check = "\n".join(pairs)
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calc = hmac.new(secret, check.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, recv_hash)


# Operator-Login ohne OTP (keine zweite Nutzer-Tabelle). Default ist Svens
# Admin-Mail; überschreibbar per SERO_ADMIN_EMAIL. Nicht im Frontend hardcoden.
DEFAULT_ADMIN_LOGIN_EMAIL = "adminsero@sero.com"


def admin_login_email() -> str:
    return (os.environ.get("SERO_ADMIN_EMAIL") or DEFAULT_ADMIN_LOGIN_EMAIL).strip().lower()


def is_admin_login_email(identifier: str | None) -> bool:
    """True nur bei der Admin-Mail (case-insensitive). Username zählt nicht."""
    raw = (identifier or "").strip()
    if "@" not in raw:
        return False
    return raw.lower() == admin_login_email()


def synthetic_email_telegram(telegram_id: int) -> str:
    return f"tg_{int(telegram_id)}@telegram.sero.local"


def synthetic_email_phone(phone_e164: str) -> str:
    digits = re.sub(r"\D", "", phone_e164)
    return f"ph_{digits}@phone.sero.local"
