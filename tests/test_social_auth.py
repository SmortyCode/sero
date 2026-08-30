"""Unit-Tests für Telegram-Hash, Telefon-Normalisierung, Provider-Flags."""
from __future__ import annotations

import hashlib
import hmac
import time

from web.social_auth import (
    normalize_phone,
    phone_auth_enabled,
    phone_auth_mode,
    synthetic_email_phone,
    synthetic_email_telegram,
    telegram_login_enabled,
    verify_telegram_login,
)


def test_normalize_phone_de_local():
    assert normalize_phone("0176 12345678") == "+4917612345678"
    assert normalize_phone("+49 176 12345678") == "+4917612345678"
    assert normalize_phone("not-a-phone") is None
    assert normalize_phone("") is None


def test_synthetic_emails():
    assert synthetic_email_telegram(42) == "tg_42@telegram.sero.local"
    assert synthetic_email_phone("+4917612345678").startswith("ph_49176")


def _tg_hash(data: dict, token: str) -> str:
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data) if k != "hash")
    secret = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()


def test_verify_telegram_login_roundtrip():
    token = "123456:ABC-DEF"
    data = {
        "id": 99,
        "first_name": "Sven",
        "username": "sven",
        "auth_date": int(time.time()),
    }
    data["hash"] = _tg_hash(data, token)
    assert verify_telegram_login(dict(data), token) is True
    bad = dict(data)
    bad["hash"] = "0" * 64
    assert verify_telegram_login(bad, token) is False
    old = {
        "id": 99,
        "first_name": "Sven",
        "username": "sven",
        "auth_date": int(time.time()) - 999999,
    }
    old["hash"] = _tg_hash(old, token)
    assert verify_telegram_login(old, token, max_age_s=60) is False


def test_provider_flags_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("LISTO_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_USERNAME", raising=False)
    monkeypatch.delenv("SERO_TELEGRAM_LOGIN", raising=False)
    monkeypatch.delenv("SERO_PHONE_AUTH", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM", raising=False)
    assert telegram_login_enabled() is False
    assert phone_auth_enabled() is False
    assert phone_auth_mode() == "off"

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x:y")
    monkeypatch.setenv("LISTO_BOT_USERNAME", "EBAYSERO_bot")
    assert telegram_login_enabled() is True
    monkeypatch.setenv("SERO_TELEGRAM_LOGIN", "0")
    assert telegram_login_enabled() is False

    monkeypatch.setenv("SERO_PHONE_AUTH", "stub")
    assert phone_auth_enabled() is True
    assert phone_auth_mode() == "stub"


def test_admin_login_email_default_and_override(monkeypatch):
    from web.social_auth import admin_login_email, is_admin_login_email
    monkeypatch.delenv("SERO_ADMIN_EMAIL", raising=False)
    assert admin_login_email() == "adminsero@sero.com"
    assert is_admin_login_email("ADMINSERO@SERO.com")
    assert is_admin_login_email("  adminsero@sero.com  ")
    assert not is_admin_login_email("kollege@example.org")
    assert not is_admin_login_email("adminsero")
    monkeypatch.setenv("SERO_ADMIN_EMAIL", "chef@example.org")
    assert is_admin_login_email("Chef@Example.org")
    assert not is_admin_login_email("adminsero@sero.com")
