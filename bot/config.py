"""Konfiguration aus .env — fehlt etwas Kritisches, bricht der Start laut ab."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Tests können mit SERO_DB auf eine Wegwerf-Datenbank zeigen — vorher war der
# Pfad beim Import festgetackert und jeder Test lief gegen die echten Daten.
DB_PATH = Path(os.environ["SERO_DB"]) if os.environ.get("SERO_DB") else PROJECT_ROOT / "data.db"
TMP_DIR = PROJECT_ROOT / "tmp"
LOG_FILE = PROJECT_ROOT / "bot.log"

EBAY_API = "https://api.ebay.com"
EBAY_APIM = "https://apim.ebay.com"  # Media API laeuft auf eigenem Host
EBAY_AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"

SCOPE_PUBLIC = "https://api.ebay.com/oauth/api_scope"
# ROLLBACK 31.07.: fulfillment-Scope bricht das BESTEHENDE Token (invalid_scope) —
# erst wieder aktivieren, wenn Sven eBay neu verbindet (dann beide Scopes).
SCOPE_INVENTORY = "https://api.ebay.com/oauth/api_scope/sell.inventory"
SCOPE_ACCOUNT = "https://api.ebay.com/oauth/api_scope/sell.account"
# Fulfillment = Bestellungen lesen — braucht der Verkaufs-Abgleich (sonst 403).
# Gefahrlos erweiterbar, seit der Refresh KEINEN scope-Parameter mehr schickt;
# wirksam wird er aber erst mit dem nächsten /verbinden (neuer Consent).
SCOPE_FULFILLMENT = "https://api.ebay.com/oauth/api_scope/sell.fulfillment"
USER_SCOPES = [SCOPE_INVENTORY, SCOPE_ACCOUNT, SCOPE_FULFILLMENT]


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    allowed_user_id: int
    anthropic_api_key: str
    claude_model: str
    deepseek_api_key: str
    deepseek_model: str
    ebay_client_id: str
    ebay_client_secret: str
    ebay_ru_name: str
    merchant_location_key: str
    fulfillment_policy_id: str
    payment_policy_id: str
    return_policy_id: str
    dry_run: bool


def _fail(missing: list[tuple[str, str]]) -> None:
    print("FEHLER: Konfiguration unvollständig — Bot startet nicht.\n", file=sys.stderr)
    for var, hint in missing:
        print(f"  - {var}: {hint}", file=sys.stderr)
    sys.exit(1)


def load_config(*, require_policies: bool = True) -> Config:
    """require_policies=False erlaubt den Setup-Skripten den Start,
    bevor Policies/Location konfiguriert sind."""
    load_dotenv(PROJECT_ROOT / ".env")

    missing: list[tuple[str, str]] = []

    def need(var: str, hint: str) -> str:
        val = os.environ.get(var, "").strip()
        if not val:
            missing.append((var, hint))
        return val

    token = need("TELEGRAM_BOT_TOKEN", "Bot bei @BotFather anlegen und Token eintragen.")
    user_id_raw = need("ALLOWED_USER_ID", "Eigene User-ID via @userinfobot holen.")
    api_key = need("ANTHROPIC_API_KEY", "Key auf console.anthropic.com erstellen.")
    # Optional: nur für textbasierte Schritte (kein Vision-Support bei DeepSeek) — fehlt der Key,
    # läuft alles wie bisher über Claude.
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    client_id = need("EBAY_CLIENT_ID", "Production Keyset auf developer.ebay.com erstellen.")
    client_secret = need("EBAY_CLIENT_SECRET", "Production Keyset auf developer.ebay.com erstellen.")
    ru_name = need("EBAY_RU_NAME", "RuName im Developer-Portal anlegen (für OAuth-Consent).")

    location_key = os.environ.get("EBAY_MERCHANT_LOCATION_KEY", "").strip()
    fulfillment = os.environ.get("EBAY_FULFILLMENT_POLICY_ID", "").strip()
    payment = os.environ.get("EBAY_PAYMENT_POLICY_ID", "").strip()
    returns = os.environ.get("EBAY_RETURN_POLICY_ID", "").strip()

    if require_policies:
        if not location_key:
            missing.append(("EBAY_MERCHANT_LOCATION_KEY", "python setup_location.py ausführen."))
        if not fulfillment:
            missing.append(("EBAY_FULFILLMENT_POLICY_ID", "python setup_policies.py ausführen und ID eintragen."))
        if not payment:
            missing.append(("EBAY_PAYMENT_POLICY_ID", "python setup_policies.py ausführen und ID eintragen."))
        if not returns:
            missing.append(("EBAY_RETURN_POLICY_ID", "python setup_policies.py ausführen und ID eintragen."))

    if missing:
        _fail(missing)

    allowed_user_id = 0
    if user_id_raw:
        try:
            allowed_user_id = int(user_id_raw)
        except ValueError:
            _fail([("ALLOWED_USER_ID", f"muss eine Zahl sein, ist aber: {user_id_raw!r}")])

    return Config(
        telegram_bot_token=token,
        allowed_user_id=allowed_user_id,
        anthropic_api_key=api_key,
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6").strip(),
        deepseek_api_key=deepseek_key,
        deepseek_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
        ebay_client_id=client_id,
        ebay_client_secret=client_secret,
        ebay_ru_name=ru_name,
        merchant_location_key=location_key,
        fulfillment_policy_id=fulfillment,
        payment_policy_id=payment,
        return_policy_id=returns,
        dry_run=os.environ.get("DRY_RUN", "false").strip().lower() != "false",
    )
