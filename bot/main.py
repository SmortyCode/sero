"""ListingPunk — Telegram-Bot: Fotos rein, eBay-Listing raus (nach Bestätigung)."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import shutil
import sys
import time
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.album import AlbumBuffer
from bot.claude_client import ClaudeAnalyzer, ClaudeError
from bot.deepseek_client import DeepSeekAnalyzer
from bot.ebay.account import AccountSetupError, create_location, get_or_create_policies
from bot.config import LOG_FILE, TMP_DIR, Config, load_config
from bot.drafts import Store
from bot.ebay.auth import EbayAuthError, EbayClient
from bot.ebay.browse import research_price
from bot.fees import estimate_fee
from bot.ebay.inventory import (
    InventoryError,
    create_inventory_item,
    create_offer,
    generate_sku,
    get_inventory_item,
    publish_offer,
    update_offer,
    withdraw_offer,
)
from bot.ebay.media import MediaError, upload_image
from bot.ebay.metadata import (
    build_condition_descriptors,
    get_condition_policy,
    resolve_condition,
)
from bot.ebay.taxonomy import (TaxonomyError, get_required_aspects,
                               get_single_value_aspects, suggest_category)
from bot.render import (
    DEFAULT_BG_COLOR,
    RenderError,
    background_available,
    normalize_hex_color,
    render_product,
    save_background,
)

log = logging.getLogger("bot")

CAPTION_FOLLOWUP_WINDOW_S = 60  # Text kurz nach den Fotos gilt als Produktbeschreibung

ONBOARDING_TEXT = (
    "👋 Willkommen bei Listo!\n\n"
    "Ich erstelle eBay-Listings aus deinen Fotos — aber dafür brauchst du erst "
    "ein Listo-Konto (14 Tage kostenlos):\n\n"
    "1. Registriere dich auf der Listo-Website\n"
    "2. Verbinde dort dein eBay-Konto\n"
    "3. Schick mir deinen Verbindungscode (sieht so aus: L-123456)\n\n"
    "Ohne Code kann ich leider nichts für dich tun. 🔒"
)

LINK_CODE_REGEX = re.compile(r"^L-\d{6}$")

# Monatslimits pro Plan (None = unbegrenzt). Veröffentlichen geht erst NACH Planwahl.
PLAN_LIMITS = {"starter": 30, "reseller": 200, "shop": None}

# USK-Altersfreigabe (Item-Merkmal bei Spielen/Medien) — steuert eBays 18er-Sperre
# eBay nennt das Feld je nach Kategorie unterschiedlich; „Altersfreigabe" gibt es
# in der Spiele-Kategorie (139973) GAR NICHT — dort heißt es „USK-Einstufung".
USK_ASPECT = "USK-Einstufung"
USK_ALIASES = ("USK-Einstufung", "USK Einstufung", "Altersfreigabe", "FSK-Einstufung")
# Exakt die Werte, die eBay.de vorschlägt. Vorher stand hier „USK ab 18 freigegeben" —
# eine Schreibweise, die eBay nicht kennt.
USK_VALUES = {
    0: "USK ab 0 Jahren",
    6: "USK ab 6 Jahren",
    12: "USK ab 12 Jahren",
    16: "USK ab 16 Jahren",
    18: "USK ab 18 Jahren",
}
GAME_CATEGORY_HINTS = ("spiel", "game", "konsole", "video", "dvd", "blu-ray", "blu ray", "usk")


def current_usk(draft: dict) -> int | None:
    """Gesetzte USK-Stufe — erkennt auch die alte Schreibweise und Alias-Felder,
    damit bestehende Entwürfe nach der Umstellung weiter richtig angezeigt werden."""
    import re as _re
    aspects = (draft.get("listing") or {}).get("aspects") or {}
    for feld in USK_ALIASES:
        for wert in aspects.get(feld) or []:
            treffer = _re.search(r"USK\s*ab\s*(\d{1,2})", str(wert), _re.I)
            if treffer and int(treffer.group(1)) in USK_VALUES:
                return int(treffer.group(1))
    return None


def is_media_category(category_name: str | None) -> bool:
    if not category_name:
        return False
    n = category_name.lower()
    return any(h in n for h in GAME_CATEGORY_HINTS)


def build_usk_menu(draft: dict) -> InlineKeyboardMarkup:
    """Untermenü zur USK-Altersfreigabe."""
    did = draft["id"]
    cur = current_usk(draft)
    rows = [[InlineKeyboardButton(("✅ " if cur == k else "") + f"USK ab {k}",
                                  callback_data=f"uskset:{did}:{k}")]
            for k in (0, 6, 12, 16, 18)]
    rows.append([InlineKeyboardButton("Keine Angabe (entfernen)", callback_data=f"uskset:{did}:none")])
    rows.append([InlineKeyboardButton("‹ Zurück zur Vorschau", callback_data=f"imgback:{did}")])
    return InlineKeyboardMarkup(rows)


def is_admin(app: Application, user_id: int) -> bool:
    return user_id == _ctx(app)["cfg"].allowed_user_id


def get_ready_user(app: Application, user_id: int) -> dict | None:
    user = _ctx(app)["store"].get_user(user_id)
    return user if user and user.get("status") == "ready" else None


def extract_oauth_code(text: str) -> str | None:
    """eBay-Redirect-URL (oder roher Code) aus einer Chat-Nachricht ziehen."""
    import urllib.parse
    text = text.strip()
    if "code=" in text:
        query = urllib.parse.urlparse(text).query or text.split("?", 1)[-1]
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            return params["code"][0]
    if text.startswith("v^1.1"):
        return text
    return None


def setup_logging() -> None:
    from logging.handlers import RotatingFileHandler
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setLevel(logging.INFO)
    # Rotation: Log wächst sonst unbegrenzt (DEBUG-Level, Dauerbetrieb)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024,
                                       backupCount=3, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stdout.setFormatter(fmt)
    file_handler.setFormatter(fmt)
    root.addHandler(stdout)
    root.addHandler(file_handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Anthropic-SDK loggt bei DEBUG komplette Request-Payloads (inkl. Base64-Bilder!) — bot.log explodiert sonst
    logging.getLogger("anthropic").setLevel(logging.INFO)
    logging.getLogger("PIL").setLevel(logging.INFO)
    logging.getLogger("telegram").setLevel(logging.INFO)


# ---------------------------------------------------------------- Hilfen

def _ctx(app: Application) -> dict:
    return app.bot_data


AUCTION_START_PRICE = "1.00"  # Svens Regel: Auktionen starten immer bei 1 €


def suggest_fixed_price(median: float) -> str:
    """Sofortkauf: fairer Preis UNTER Markt — ~5 % unter Median, auf .90 endend.
    Die alte Rechnung int(target)-0,10 verschenkte bei kleinen Preisen bis zu
    18 % statt 5 (Median 6,00 -> 4,90) und sprang nicht monoton (5,26 -> 5,00,
    aber 5,27 -> 4,90). Jetzt: nächstliegende .90-Stufe zu 95 % des Medians,
    nie auf oder über Markt; unter ~6 € glatt 5 % ohne .90-Endung."""
    target = median * 0.95
    if target < 5.90:
        return f"{max(target, 1.0):.2f}"
    stufe = round(target - 0.90) + 0.90
    if stufe >= median:
        stufe -= 1.0
    return f"{stufe:.2f}"


def apply_price_rule(draft: dict) -> None:
    """Rangfolge: Nutzerpreis > Verkaufs-Vorlage > BELEGTER Marktwert >
    eBay-Vergleichsangebote. Der Marktwert des Stücks (aus dem Preis-Katalog)
    schlägt die Blind-Recherche der Pipeline — sonst entstehen Vorschläge weit
    unter Wert (Svens Glurak 307,90 statt 653,02 €). Gibt es KEINE dieser
    Quellen, bleibt der Preis leer und der Nutzer trägt ihn selbst ein
    (ehrlich statt geraten, ADR-002)."""
    listing = draft.get("listing") or {}

    def _num(v):
        try:
            return parse_price(str(v)) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    user_price = _num(listing.get("user_price"))
    tpl_price = _num(listing.get("tpl_price"))
    market = _num(listing.get("market_value"))

    if draft.get("format") == "AUCTION":
        draft["price"] = user_price or tpl_price or AUCTION_START_PRICE
        draft["price_basis"] = ("Dein Preis" if user_price
                                else "Verkaufs-Vorlage" if tpl_price else "Auktionsstart 1 €")
        return
    research = draft.get("price_research")
    if user_price:
        draft["price"], draft["price_basis"] = user_price, "Dein Preis"
    elif tpl_price:
        draft["price"], draft["price_basis"] = tpl_price, "Verkaufs-Vorlage"
    elif market:
        draft["price"] = suggest_fixed_price(float(market))   # parse_price liefert einen String
        draft["price_basis"] = listing.get("market_source") or "Marktwert"
    elif research:
        draft["price"] = suggest_fixed_price(research["median"])
        draft["price_basis"] = f"eBay-Median aus {research['count']} Angeboten"
    else:
        draft["price"], draft["price_basis"] = None, None


def comps_verwertbar(research: dict | None) -> dict | None:
    """Mindestbeleg-Regel: Unter 3 Vergleichsangeboten wird NICHT gerechnet —
    lieber ehrlich kein Preisvorschlag als einer aus 1-2 Zufallstreffern.
    (Audit P0.2: Vorher ersetzte hier eine KI-Preisspanne die dünnen Comps.
    Preise aus dem Sprachmodell sind seit 07.08. produktweit verboten, ADR-002 —
    ohne Belege trägt der Nutzer den Preis selbst ein.)"""
    if not research or research.get("count", 0) < 3:
        if research:
            log.info("Preis: zu wenige Comps (%s) -> kein Vorschlag", research.get("count"))
        return None
    return research


def reorder_photos(photos: list[str], main_index) -> list[str]:
    """Foto mit der Vorderseite (Claude: main_image_index) nach vorn — wird eBay-Hauptbild."""
    try:
        idx = int(main_index)
    except (TypeError, ValueError):
        return photos
    if not 0 < idx < len(photos):
        return photos
    return [photos[idx]] + photos[:idx] + photos[idx + 1:]


def parse_price(text: str) -> str | None:
    """Preis-Eingabe robust lesen — deutsch UND englisch geschrieben.

    Der alte Weg ersetzte nur Komma durch Punkt. Damit wurde aus dem deutschen
    „1.500" (= 1500 €) der Betrag 1,50 € — Faktor 1000 zu wenig, ohne Warnung.
    Regeln: kommen beide Trennzeichen vor, ist das LETZTE das Dezimaltrennzeichen.
    Steht nur ein Punkt mit genau drei Ziffern dahinter, ist es ein Tausenderpunkt
    (Geldbeträge haben keine drei Nachkommastellen).
    """
    import math
    import re as _re
    cleaned = str(text).replace("€", "").replace("EUR", "").replace("\u00a0", "")
    cleaned = _re.sub(r"\s+", "", cleaned).strip()
    if not cleaned:
        return None
    neg = cleaned.startswith("-")
    cleaned = cleaned.lstrip("+-")
    if not _re.fullmatch(r"[0-9.,]+", cleaned):
        return None            # „nan", „1e99", Buchstaben — nichts davon ist ein Preis
    komma, punkt = cleaned.rfind(","), cleaned.rfind(".")
    if komma >= 0 and punkt >= 0:
        dez = max(komma, punkt)                      # das letzte trennt die Cent ab
        cleaned = _re.sub(r"[.,]", "", cleaned[:dez]) + "." + cleaned[dez + 1:]
    elif komma >= 0:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif punkt >= 0:
        ganz, _, rest = cleaned.rpartition(".")
        cleaned = (ganz.replace(".", "") + rest) if len(rest) == 3 else cleaned.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if neg:
        value = -value
    # isfinite fängt nan/inf ab: „nan" bestand früher BEIDE Vergleiche und
    # legte damit die komplette Sammlung lahm (JSON kann kein NaN).
    if not math.isfinite(value) or value <= 0 or value > 1_000_000:
        return None
    return f"{value:.2f}"


def build_preview(draft: dict, published: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    listing = draft["listing"]
    price = draft.get("price")
    price_info = draft.get("price_research")

    head = "🟢 LIVE auf eBay" if published else None
    lines = [f"<b>{html.escape(listing['title'])}</b>", ""]
    if head:
        lines = [head, f"<b>{html.escape(listing['title'])}</b>", ""]
    if draft.get("category_name"):
        lines.append(f"📁 {html.escape(draft['category_name'])} ({draft.get('category_id')})")
    lines.append(f"🏷 Zustand: {listing['condition']}")
    usk = current_usk(draft)
    if usk is not None:
        lines.append(f"🔞 Altersfreigabe: USK ab {usk}")
    if listing.get("assumptions"):
        lines.append(f"⚠️ Annahme: {html.escape(str(listing['assumptions']))} — falls falsch: "
                     f"Korrektur als Text schicken + 🔁")
    if price_info:
        lines.append(
            f"📊 Vergleichbare Angebote ({price_info['count']}): "
            f"{price_info['min']:.0f}–{price_info['max']:.0f} €, Median {price_info['median']:.2f} €"
        )
    else:
        lines.append("📊 Keine vergleichbaren Angebote gefunden — Preis bitte manuell setzen.")
    fmt = draft.get("format", "FIXED_PRICE")
    quantity = draft.get("quantity", 1)
    price_label = price + " €" if price else "— (fehlt!)"
    auction_days = int(draft.get("auction_days") or 7)
    if fmt == "AUCTION":
        lines.append(f"🔨 Auktion ({auction_days} {'Tag' if auction_days == 1 else 'Tage'}) "
                     f"— Startpreis: {price_label}")
    else:
        per_unit = " pro Stück/Set" if quantity > 1 else ""
        lines.append(f"💶 Festpreis: {price_label}{per_unit}")
        best_offer = draft.get("best_offer")
        if best_offer:
            bo_line = "🤝 Preisvorschlag: an"
            if best_offer.get("min_price"):
                bo_line += f" (auto-ablehnen unter {best_offer['min_price']} €)"
            lines.append(bo_line)
        if quantity > 1:
            lines.append(f"📦 Stückzahl: {quantity}")
    # eBay-Gebühren VOR dem Upload sichtbar machen (gewerblich: überall; privat: Karten)
    if price:
        try:
            fee = estimate_fee(draft.get("category_name"), float(price.replace(",", ".")),
                               quantity, business=bool(draft.get("business")))
            if fee["applies"]:
                lines.append(
                    f"💸 eBay-Gebühr ({fee['label']}, ~{fee['rate']:.0%}): ~{fee['fee']:.2f} € "
                    f"→ Netto ~{fee['net']:.2f} €"
                )
        except (TypeError, ValueError):
            pass
    n_photos = len(draft.get("photos") or [])
    if n_photos > 1:
        lines.append(f"📸 {n_photos} Fotos werden hochgeladen")
    lines.append("")
    # Kurzfassung der Beschreibung (ohne HTML-Tags)
    import re
    desc_plain = re.sub(r"<[^>]+>", " ", listing.get("description_html", ""))
    desc_plain = re.sub(r"\s+", " ", desc_plain).strip()
    lines.append(html.escape(desc_plain[:300] + ("…" if len(desc_plain) > 300 else "")))

    did = draft["id"]
    fmt_btn = "🔨 Als Auktion" if fmt == "FIXED_PRICE" else "💶 Als Festpreis"
    main_btn = (InlineKeyboardButton("💾 Änderungen speichern", callback_data=f"save:{did}")
                if published else
                InlineKeyboardButton("✅ Hochladen", callback_data=f"upload:{did}"))
    last_row = ([InlineKeyboardButton("🛑 Listing beenden", callback_data=f"end:{did}"),
                 InlineKeyboardButton("‹ Fertig", callback_data=f"done:{did}")]
                if published else
                [InlineKeyboardButton("🔁 Komplett neu", callback_data=f"regen:{did}"),
                 InlineKeyboardButton("❌ Verwerfen", callback_data=f"discard:{did}")])
    rows = [
        [main_btn],
        [InlineKeyboardButton("✏️ Preis", callback_data=f"price:{did}"),
         InlineKeyboardButton("✏️ Menge", callback_data=f"qty:{did}")],
        [InlineKeyboardButton("✏️ Titel", callback_data=f"title:{did}"),
         InlineKeyboardButton("✏️ Beschreibung", callback_data=f"desc:{did}")],
        # Bei Auktion: Laufzeit statt Preisvorschlag (Best Offer geht nur bei Festpreis)
        [InlineKeyboardButton("🏷 Zustand", callback_data=f"cond:{did}"),
         (InlineKeyboardButton(f"⏱ Laufzeit ({auction_days} T.)", callback_data=f"dur:{did}")
          if fmt == "AUCTION" else
          InlineKeyboardButton("🤝 Preisvorschlag", callback_data=f"offer:{did}"))],
        [InlineKeyboardButton("🖼 Bilder", callback_data=f"img:{did}"),
         InlineKeyboardButton(fmt_btn, callback_data=f"fmt:{did}")],
    ]
    # USK-Freigabe-Button nur bei Spiele-/Medien-Kategorien (dort greift eBays 18-Sperre)
    if is_media_category(draft.get("category_name")) or current_usk(draft) is not None:
        usk_label = f"🔞 Altersfreigabe (USK {usk})" if usk is not None else "🔞 Altersfreigabe setzen"
        rows.append([InlineKeyboardButton(usk_label, callback_data=f"usk:{did}")])
    rows.append(last_row)
    return "\n".join(lines)[:1024], InlineKeyboardMarkup(rows)


def build_published_actions(draft: dict) -> InlineKeyboardMarkup:
    """Knöpfe an der „Listing ist live“-Nachricht: bearbeiten / ansehen / beenden."""
    did = draft["id"]
    rows = [[InlineKeyboardButton("✏️ Listing bearbeiten", callback_data=f"edit:{did}")]]
    if draft.get("item_url"):
        rows.append([InlineKeyboardButton("🔗 Auf eBay ansehen", url=draft["item_url"])])
    rows.append([InlineKeyboardButton("🛑 Listing beenden", callback_data=f"end:{did}")])
    return InlineKeyboardMarkup(rows)


def build_images_menu(draft: dict) -> InlineKeyboardMarkup:
    """Untermenü: pro Foto zwischen freigestelltem Render und Original umschalten."""
    did = draft["id"]
    photos = draft.get("photos") or []
    originals = draft.get("original_photos") or []
    rendered = draft.get("rendered_photos") or []
    rows = []
    for i in range(len(photos)):
        is_orig = bool(originals) and i < len(originals) and photos[i] == originals[i]
        has_render = (bool(rendered) and i < len(rendered)
                      and bool(originals) and rendered[i] != originals[i])
        if not has_render:
            label = f"📷 Bild {i+1}: Original (kein Freisteller)"
        elif is_orig:
            label = f"📷 Bild {i+1}: Original  →  ✨ freistellen"
        else:
            label = f"✨ Bild {i+1}: Freigestellt  →  📷 Original"
        rows.append([InlineKeyboardButton(label, callback_data=f"imgtog:{did}:{i}")])
    rows.append([InlineKeyboardButton("🔄 Alle neu rendern", callback_data=f"imgren:{did}")])
    rows.append([InlineKeyboardButton("‹ Zurück zur Vorschau", callback_data=f"imgback:{did}")])
    return InlineKeyboardMarkup(rows)


async def send_preview(app: Application, chat_id: int, draft: dict) -> None:
    """Vorschau senden. Bei mehreren Fotos: erst alle (gerendert) als Album zeigen,
    dann Text + Buttons (Telegram erlaubt keine Buttons an Alben)."""
    text, keyboard = build_preview(draft, published=draft.get("status") == "published")
    photos = [p for p in (draft.get("photos") or []) if Path(p).exists()]
    if not photos:
        # Lokale Fotos bereits aufgeräumt (bei eBay liegen sie weiter) -> Text-Vorschau
        await app.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=keyboard)
        return
    if len(photos) > 1:
        files = []
        try:
            media = []
            for p in photos[:10]:  # Telegram: max. 10 pro Album
                f = open(p, "rb")
                files.append(f)
                media.append(InputMediaPhoto(f))
            await app.bot.send_media_group(chat_id, media)
        finally:
            for f in files:
                f.close()
        await app.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=keyboard)
    else:
        with open(photos[0], "rb") as f:
            await app.bot.send_photo(chat_id, photo=f, caption=text,
                                     parse_mode="HTML", reply_markup=keyboard)


def cleanup_photos(draft: dict) -> None:
    folder = TMP_DIR / draft["id"]
    shutil.rmtree(folder, ignore_errors=True)


def cleanup_stale_drafts(store: Store) -> None:
    """Unfertige Drafts nach 7 Tagen löschen, lokale Fotos veröffentlichter Listings
    nach 14 Tagen entsorgen (liegen längst bei eBay). Verhindert unbegrenztes Wachstum
    von tmp/ und der drafts-Tabelle. Läuft beim Start und täglich."""
    dead, old_published = store.stale_draft_ids(
        unfinished_older_than_s=7 * 86400, published_older_than_s=14 * 86400)
    for draft_id in dead:
        shutil.rmtree(TMP_DIR / draft_id, ignore_errors=True)
        store.delete_draft(draft_id)
    for draft_id in old_published:
        shutil.rmtree(TMP_DIR / draft_id, ignore_errors=True)
    # verwaiste Ordner ohne DB-Eintrag (z.B. nach Abstürzen)
    known = {d for lst in (dead, old_published) for d in lst}
    if TMP_DIR.exists():
        alive = {r["id"] for r in store._conn.execute("SELECT id FROM drafts").fetchall()}  # noqa: SLF001
        for folder in TMP_DIR.iterdir():
            if folder.is_dir() and folder.name not in alive and folder.name not in known:
                shutil.rmtree(folder, ignore_errors=True)
    if dead or old_published:
        log.info("Aufgeräumt: %d alte Drafts gelöscht, %d Foto-Ordner entsorgt",
                 len(dead), len(old_published))


# ---------------------------------------------------------------- Pipeline

async def run_pipeline(app: Application, draft_id: str) -> None:
    """Claude-Analyse -> Kategorie -> Pflicht-Aspects -> Preisrecherche -> Vorschau."""
    store: Store = _ctx(app)["store"]
    analyzer: ClaudeAnalyzer = _ctx(app)["analyzer"]
    ebay: EbayClient = _ctx(app)["ebay"]
    draft = store.get_draft(draft_id)
    if not draft:
        return
    chat_id = draft["chat_id"]

    status_msg = await app.bot.send_message(chat_id, "⏳ Analysiere Fotos…")
    try:
        listing = await analyzer.analyze(
            draft.get("original_photos") or draft["photos"], draft.get("caption"))

        if listing.get("uncertain") and listing.get("question"):
            draft["status"] = "uncertain"
            draft["listing"] = listing
            store.update_draft(draft_id, draft)
            await status_msg.edit_text(
                f"❓ {listing['question']}\n\nAntworte einfach mit einer Textnachricht — "
                "ich generiere den Entwurf dann neu."
            )
            return

        reordered = reorder_photos(draft["photos"], listing.get("main_image_index"))
        if reordered != draft["photos"]:
            mi = listing.get("main_image_index")
            draft["photos"] = reordered
            if draft.get("original_photos"):
                draft["original_photos"] = reorder_photos(draft["original_photos"], mi)
            if draft.get("rendered_photos"):
                draft["rendered_photos"] = reorder_photos(draft["rendered_photos"], mi)
            draft["image_urls"] = None  # Upload-Cache passt nicht mehr zur neuen Reihenfolge
            log.info("Hauptbild erkannt: Foto %s nach vorn sortiert", mi)

        await status_msg.edit_text("⏳ Suche Kategorie & Pflichtfelder…")
        # Fallback: liefert der Claude-Suchbegriff nichts, mit dem Titel probieren
        category = (await suggest_category(ebay, store, listing["category_query"])
                    or await suggest_category(ebay, store, listing["title"]))
        if category:
            draft["category_id"] = category["categoryId"]
            draft["category_name"] = category["categoryName"]
            required = await get_required_aspects(ebay, store, category["categoryId"])
            aspects = listing.get("aspects") or {}
            missing = [a for a in required if a not in aspects]
            if missing:
                filled = await analyzer.fill_aspects(
                    draft.get("original_photos") or draft["photos"], listing, missing)
                for name in missing:
                    aspects[name] = filled.get(name, ["Nicht zutreffend"])
            listing["aspects"] = aspects
        else:
            draft["category_id"] = None
            draft["category_name"] = None

        await status_msg.edit_text("⏳ Recherchiere Preise…")
        price_research = await research_price(ebay, listing["search_query_for_pricing"])
        draft["price_research"] = comps_verwertbar(price_research)
        draft["format"] = listing.get("format") if listing.get("format") in ("FIXED_PRICE", "AUCTION") else "FIXED_PRICE"
        try:
            draft["quantity"] = max(1, min(int(listing.get("quantity") or 1), 1000))
        except (TypeError, ValueError):
            draft["quantity"] = 1
        # Auktionslaufzeit aus dem Verkäufertext (1/3/5/7/10 Tage), Default 7
        from bot.ebay.inventory import AUCTION_DURATIONS
        try:
            days = int(listing.get("auction_days") or 7)
        except (TypeError, ValueError):
            days = 7
        draft["auction_days"] = days if days in AUCTION_DURATIONS else 7
        # Best Offer (Preisvorschlag) aus dem Verkäufertext übernehmen
        best_offer = listing.get("best_offer")
        draft["best_offer"] = None
        if isinstance(best_offer, dict) and best_offer.get("enabled"):
            min_price = (parse_price(str(best_offer.get("min_price")))
                         if best_offer.get("min_price") else None)
            draft["best_offer"] = {"enabled": True, "min_price": min_price}
        draft["listing"] = listing  # vor apply_price_rule — user_price kommt aus dem Listing
        apply_price_rule(draft)

        draft["listing"] = listing
        draft["status"] = "ready"
        store.update_draft(draft_id, draft)

        await status_msg.delete()
        await send_preview(app, chat_id, draft)

    except (ClaudeError, TaxonomyError, EbayAuthError) as e:
        log.exception("Pipeline-Fehler für Draft %s", draft_id)
        draft["status"] = "error"
        store.update_draft(draft_id, draft)
        await status_msg.edit_text(f"❌ Fehler bei der Analyse:\n{e}\n\nDraft bleibt erhalten — "
                                   "🔁 mit /retry oder Fotos neu senden.")
    except Exception as e:  # noqa: BLE001 — alles muss im Chat landen, nie nur im Log
        log.exception("Unerwarteter Pipeline-Fehler für Draft %s", draft_id)
        await status_msg.edit_text(f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}")


async def run_upload(app: Application, draft_id: str, chat_id: int) -> None:
    """Media-Upload -> InventoryItem -> Offer -> Publish (oder Dry-Run-Log)."""
    store: Store = _ctx(app)["store"]
    ebay: EbayClient = _ctx(app)["ebay"]
    dry_run: bool = _ctx(app)["dry_run"]
    draft = store.get_draft(draft_id)
    if not draft:
        await app.bot.send_message(chat_id, "Draft nicht mehr vorhanden.")
        return
    user_id = chat_id  # privater Chat: Chat-ID == Telegram-User-ID
    policies = store.user_policies(user_id)
    if not policies:
        await app.bot.send_message(chat_id, "Dein eBay-Setup ist unvollständig — bitte /verbinden ausführen.")
        return

    listing = draft["listing"]
    status_msg = await app.bot.send_message(chat_id, "⏳ Lade Bilder zu eBay hoch…")
    try:
        # Bereits hochgeladene EPS-URLs wiederverwenden (z.B. Retry nach Dry-Run)
        image_urls = draft.get("image_urls") or []
        if not image_urls:
            for i, path in enumerate(draft["photos"], 1):
                await status_msg.edit_text(f"⏳ Lade Bild {i}/{len(draft['photos'])} hoch…")
                image_urls.append(await upload_image(ebay, path, user_id))
            draft["image_urls"] = image_urls
            store.update_draft(draft_id, draft)

        sku = draft.get("sku") or generate_sku()
        draft["sku"] = sku
        store.update_draft(draft_id, draft)

        # Merkmale, die nur EINEN Wert erlauben, auf den ersten kürzen (sonst 25002,
        # z.B. "Verlag darf nur einen Wert enthalten")
        singles = await get_single_value_aspects(ebay, store, draft["category_id"])
        aspects = listing.get("aspects") or {}
        for name in singles:
            vals = aspects.get(name)
            if isinstance(vals, list) and len(vals) > 1:
                aspects[name] = vals[:1]
                log.info("Aspect '%s' auf einen Wert gekürzt (Kategorie erlaubt nur einen)", name)
        listing["aspects"] = aspects

        # Zustand gegen die erlaubten Conditions der Kategorie prüfen (z.B. Karten: nur Graded/Ungraded)
        policy = await get_condition_policy(ebay, store, draft["category_id"])
        allowed = [str(c["conditionId"]) for c in policy]
        item_text = " ".join([listing.get("title", ""), draft.get("caption") or "",
                              str(listing.get("aspects") or "")])
        condition, adjusted = resolve_condition(
            listing["condition"], allowed, item_text,
            is_graded=bool(listing.get("graded_info")),  # Claude hat einen Slab auf den Fotos erkannt
        )
        if adjusted:
            listing["condition"] = condition
            draft["listing"] = listing
            store.update_draft(draft_id, draft)
            await app.bot.send_message(
                chat_id,
                f"ℹ️ Zustand angepasst auf {condition} — die Kategorie erlaubt den "
                f"ursprünglichen Zustand nicht (bei Einzelkarten gibt es nur Graded/Ungraded).",
            )

        # Pflicht-Descriptors der Kategorie (z.B. Graded: Bewerter + Note, Ungraded: Kartenzustand)
        descriptors, frage = build_condition_descriptors(listing["condition"], policy, listing, item_text)
        if frage:
            _ctx(app).setdefault("pending_edits", {})[chat_id] = (draft_id, "graded")
            await status_msg.edit_text(frage)
            return

        quantity = 1 if draft.get("format") == "AUCTION" else int(draft.get("quantity") or 1)

        await status_msg.edit_text("⏳ Lege Inventory Item an…")
        await create_inventory_item(
            ebay, sku,
            user_id=user_id,
            title=listing["title"],
            description=listing["description_html"],
            condition=listing["condition"],
            condition_description=listing.get("condition_description"),
            aspects=listing.get("aspects") or {},
            image_urls=image_urls,
            condition_descriptors=descriptors,
            quantity=quantity,
        )

        if draft.get("offer_id"):
            # Offer existiert schon (Dry-Run/Retry) — aktualisieren statt neu anlegen
            await status_msg.edit_text("⏳ Aktualisiere bestehendes Offer…")
            offer_id = draft["offer_id"]
            await update_offer(
                ebay, policies, offer_id, sku,
                user_id=user_id,
                category_id=draft["category_id"],
                price_eur=draft["price"],
                listing_description=listing["description_html"],
                listing_format=draft.get("format", "FIXED_PRICE"),
                quantity=quantity,
                best_offer=draft.get("best_offer"),
                auction_days=int(draft.get("auction_days") or 7),
                title=listing.get("title"),
            )
        else:
            await status_msg.edit_text("⏳ Erstelle Offer…")
            offer_id = await create_offer(
                ebay, policies, sku,
                user_id=user_id,
                category_id=draft["category_id"],
                price_eur=draft["price"],
                listing_description=listing["description_html"],
                listing_format=draft.get("format", "FIXED_PRICE"),
                quantity=quantity,
                best_offer=draft.get("best_offer"),
                auction_days=int(draft.get("auction_days") or 7),
                title=listing.get("title"),
            )
            draft["offer_id"] = offer_id
            store.update_draft(draft_id, draft)

        if dry_run:
            payload_summary = json.dumps(
                {"sku": sku, "offerId": offer_id, "title": listing["title"],
                 "price": draft["price"], "categoryId": draft["category_id"],
                 "imageUrls": image_urls},
                ensure_ascii=False, indent=2,
            )
            log.info("DRY_RUN — publishOffer übersprungen. Payload:\n%s", payload_summary)
            store.log_listing(sku, listing["title"], draft["price"], offer_id, None,
                              dry_run=True, telegram_id=user_id)
            draft["status"] = "dry_run_done"
            store.update_draft(draft_id, draft)
            await status_msg.edit_text(
                f"🧪 DRY RUN: Alles bis auf publishOffer erledigt.\n"
                f"SKU: {sku}\nOffer: {offer_id}\n"
                f"Zum echten Veröffentlichen: /dryrun off, dann ✅ erneut drücken."
            )
            return

        await status_msg.edit_text("⏳ Veröffentliche Listing…")
        listing_id = await publish_offer(ebay, offer_id, user_id)
        store.log_listing(sku, listing["title"], draft["price"], offer_id, listing_id,
                          dry_run=False, telegram_id=user_id)
        # Draft + Fotos BEHALTEN: ermöglicht nachträgliches Bearbeiten über Telegram
        draft["status"] = "published"
        draft["listing_id"] = listing_id
        draft["item_url"] = f"https://www.ebay.de/itm/{listing_id}"
        store.update_draft(draft_id, draft)
        await status_msg.edit_text(
            f"✅ <b>Listing ist live!</b>\n{html.escape(listing['title'])}\n"
            f"💶 {draft['price']} €\n{draft['item_url']}\n\n"
            "Du kannst das Listing jederzeit bearbeiten — die Änderungen gehen sofort live.",
            parse_mode="HTML", reply_markup=build_published_actions(draft),
        )

    except (MediaError, InventoryError, EbayAuthError) as e:
        log.exception("Upload-Fehler für Draft %s", draft_id)
        # Sicherheitsnetz "nur einen Wert": betroffenes Merkmal aus der Meldung
        # parsen und selbst kürzen, falls die Taxonomy es nicht als SINGLE meldete
        m = re.search(r"([A-ZÄÖÜ][\w\säöüß/-]*?) darf nur einen Wert", str(e))
        if m:
            name = m.group(1).strip()
            aspects = (draft.get("listing") or {}).get("aspects") or {}
            if isinstance(aspects.get(name), list) and len(aspects[name]) > 1:
                aspects[name] = aspects[name][:1]
                draft["listing"]["aspects"] = aspects
                store.update_draft(draft_id, draft)
                await status_msg.edit_text(
                    f"⚠️ „{name}“ erlaubt nur einen Wert — habe ich korrigiert. "
                    f"Einfach ✅ erneut drücken."
                )
                return
        await status_msg.edit_text(
            f"❌ eBay-Fehler:\n{e}\n\nDraft bleibt erhalten — ✅ erneut drücken für Retry."
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Unerwarteter Upload-Fehler für Draft %s", draft_id)
        await status_msg.edit_text(f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------- Onboarding

async def complete_ebay_connection(app: Application, chat_id: int, code: str) -> None:
    """OAuth-Code einlösen, Richtlinien automatisch einrichten, Adresse abfragen."""
    store: Store = _ctx(app)["store"]
    ebay: EbayClient = _ctx(app)["ebay"]
    status = await app.bot.send_message(chat_id, "⏳ Verbinde dein eBay-Konto…")
    try:
        await ebay.exchange_code(code, chat_id)
        # Neuer Consent enthält sell.fulfillment — 403-Marke vom Sales-Sync weg.
        store.kv_set(f"ebay_fulfillment_fehlt_{chat_id}", None)
        await continue_account_setup(app, chat_id, status)
    except (EbayAuthError, AccountSetupError) as e:
        log.exception("Onboarding-Fehler für %s", chat_id)
        await status.edit_text(
            f"❌ Verbindung fehlgeschlagen:\n{e}\n\nEinfach erneut versuchen — "
            "der eBay-Code ist nur ~5 Minuten gültig, hol dir ggf. einen frischen."
        )


async def continue_account_setup(app: Application, chat_id: int, status=None) -> None:
    """Nach vorhandenem eBay-Token: Richtlinien einrichten + Adresse abfragen."""
    store: Store = _ctx(app)["store"]
    ebay: EbayClient = _ctx(app)["ebay"]
    if status is None:
        status = await app.bot.send_message(chat_id, "⏳ Richte dein eBay-Setup ein…")
    else:
        await status.edit_text("✅ eBay verbunden!\n⏳ Richte Verkaufsrichtlinien ein…")
    policies = await get_or_create_policies(ebay, chat_id)
    store.upsert_user(chat_id, status="connecting", **policies)

    if store.get_user(chat_id).get("merchant_location_key"):
        store.upsert_user(chat_id, status="ready")
        await status.edit_text("🎉 Alles eingerichtet! Schick mir Produktfotos — los geht's.")
        return

    _ctx(app).setdefault("pending_edits", {})[chat_id] = (None, "address")
    await status.edit_text(
        "✅ eBay verbunden, Richtlinien eingerichtet!\n\n"
        "📍 Letzter Schritt — deine Versandadresse (wird nicht öffentlich angezeigt, "
        "eBay braucht sie als Versandstandort):\n\n"
        "Format:  Straße Hausnr, PLZ, Stadt\n"
        "Beispiel:  Marbachstrasse 9A, 81369, München"
    )


async def handle_link_code(app: Application, update: Update, code: str) -> None:
    """Code von der Website einlösen: Telegram-Konto mit dem Listo-Account verknüpfen."""
    from bot.ebay.auth import _token_key
    store: Store = _ctx(app)["store"]
    chat_id = update.message.chat_id

    account_id = store.redeem_link_code(code, "telegram")
    if not account_id:
        await update.message.reply_text(
            "❌ Dieser Code ist ungültig oder abgelaufen. Hol dir auf der Website "
            "einen neuen (Codes gelten 1 Stunde)."
        )
        return
    store.update_account(account_id, telegram_id=chat_id)
    account = store.get_account(account_id)
    log.info("Account %s (%s) mit Telegram %s verknüpft", account_id, account["email"], chat_id)

    # Hat der Account auf der Website schon eBay verbunden? Token übernehmen.
    synthetic_uid = 10 ** 15 + account_id
    web_token = store.kv_get(_token_key(synthetic_uid))
    if web_token:
        store.kv_set(_token_key(chat_id), web_token)
        await update.message.reply_text(f"✅ Konto verknüpft ({account['email']})!")
        await continue_account_setup(app, chat_id)
    else:
        await update.message.reply_text(
            f"✅ Konto verknüpft ({account['email']})!\n\n"
            "Jetzt noch auf der Website „Mit eBay verbinden“ klicken — "
            "danach melde ich mich hier automatisch."
        )


async def handle_address(app: Application, update: Update, text: str) -> None:
    store: Store = _ctx(app)["store"]
    ebay: EbayClient = _ctx(app)["ebay"]
    chat_id = update.message.chat_id

    parts = [p.strip() for p in text.split(",")]
    plz_match = re.search(r"\b(\d{5})\b", text)
    if len(parts) < 2 or not plz_match:
        _ctx(app)["pending_edits"][chat_id] = (None, "address")
        await update.message.reply_text(
            "Das konnte ich nicht lesen. Format:  Straße Hausnr, PLZ, Stadt\n"
            "Beispiel:  Marbachstrasse 9A, 81369, München"
        )
        return
    street = parts[0]
    plz = plz_match.group(1)
    city = parts[-1].replace(plz, "").strip() or "Unbekannt"

    try:
        location_key = f"listo-{chat_id}"
        await create_location(ebay, chat_id, location_key, street, plz, city)
        store.upsert_user(chat_id, merchant_location_key=location_key, status="ready")
        await update.message.reply_text(
            "🎉 Fertig — dein Konto ist startklar!\n\n"
            "Schick mir jetzt Produktfotos (gern als Album) mit kurzer Beschreibung. "
            "Preis, Auktion, Stückzahl? Einfach dazuschreiben — ich versteh's."
        )
    except (AccountSetupError, EbayAuthError) as e:
        _ctx(app)["pending_edits"][chat_id] = (None, "address")
        await update.message.reply_text(f"❌ Standort konnte nicht angelegt werden:\n{e}\n\nBitte erneut senden.")


async def cmd_farbe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    store: Store = _ctx(app)["store"]
    chat_id = update.message.chat_id
    if not get_ready_user(app, chat_id):
        await update.message.reply_text(ONBOARDING_TEXT)
        return
    arg = context.args[0] if context.args else ""
    color = normalize_hex_color(arg)
    if not color:
        current = (store.get_user(chat_id) or {}).get("render_color") or DEFAULT_BG_COLOR
        await update.message.reply_text(
            f"🎨 Deine Hintergrundfarbe: {current}\n\n"
            "Ändern mit:  /farbe #RRGGBB\n"
            "Beispiele:  /farbe #ffffff (weiß) · /farbe #f5f5f7 (hellgrau) · /farbe #75aae7 (blau)"
        )
        return
    store.upsert_user(chat_id, render_color=color)
    await update.message.reply_text(
        f"🎨 Hintergrundfarbe auf {color} gesetzt — gilt ab dem nächsten Foto."
    )


async def cmd_verbinden(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    if not is_admin(app, update.message.from_user.id):
        await update.message.reply_text(ONBOARDING_TEXT)
        return
    store: Store = _ctx(app)["store"]
    chat_id = update.message.chat_id
    if not store.get_user(chat_id):
        store.upsert_user(chat_id, status="connecting")
    url = _ctx(app)["ebay"].build_consent_url()
    await update.message.reply_text(
        "So verbindest du dein eBay-Konto (30 Sekunden):\n\n"
        "1. Öffne den Link unten\n"
        "2. Logge dich mit DEM eBay-Konto ein, auf dem deine Listings erscheinen sollen\n"
        "3. Bestätige den Zugriff (inkl. Bestellungen lesen — braucht der Verkaufs-Abgleich)\n"
        "4. Kopiere danach die KOMPLETTE Adresse aus der Browser-Adresszeile "
        "und schick sie mir hierher\n\n"
        "Wichtig: Einmal neu verbinden, wenn Verkäufe nicht erkannt werden "
        "(Fehler 403 / Scope sell.fulfillment).\n\n"
        "Ich sehe dabei nie dein Passwort — der Login passiert direkt bei eBay."
    )
    await update.message.reply_text(url)


# ---------------------------------------------------------------- Foto-Empfang

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    app = context.application

    # Bild mit Caption "hintergrund" = neuer Render-Hintergrund (global, nur Admin)
    if msg.caption and msg.caption.strip().lower() in ("hintergrund", "background"):
        if not is_admin(app, msg.from_user.id):
            return
        tg_file = await context.bot.get_file(msg.photo[-1].file_id)
        tmp_path = TMP_DIR / "background_upload.jpg"
        TMP_DIR.mkdir(exist_ok=True)
        await tg_file.download_to_drive(str(tmp_path))
        width, height = save_background(tmp_path)
        tmp_path.unlink(missing_ok=True)
        await msg.reply_text(
            f"🖼 Hintergrund gespeichert ({width}x{height}). Alle neuen Produktfotos werden "
            f"jetzt freigestellt und einheitlich darauf gesetzt. Abschalten mit /render off."
        )
        return

    if not get_ready_user(app, msg.from_user.id):
        await msg.reply_text(ONBOARDING_TEXT)
        return

    if not is_admin(app, msg.from_user.id):
        store: Store = _ctx(app)["store"]
        account = store.get_account_by_telegram(msg.from_user.id)
        if not account or not store.account_active(account):
            await msg.reply_text(
                "⏸ Dein Testzeitraum ist abgelaufen (oder dein Konto ist nicht aktiv). "
                "Wähle auf der Listo-Website einen Plan, dann geht's sofort weiter."
            )
            return

    item = {
        "file_id": msg.photo[-1].file_id,  # grösste Auflösung
        "caption": msg.caption,
        "chat_id": msg.chat_id,
    }
    if msg.media_group_id:
        buffer: AlbumBuffer = _ctx(context.application)["album_buffer"]
        buffer.add(msg.media_group_id, item)
    else:
        await process_photo_group(context.application, [item])


def render_kwargs_for(app: Application, chat_id: int) -> dict:
    """Render-Hintergrund je Nutzer: eigenes Template > Admin-Datei-Template > Farb-Canvas."""
    store: Store = _ctx(app)["store"]
    admin = chat_id == _ctx(app)["cfg"].allowed_user_id
    account = store.get_account_by_telegram(chat_id)
    if account and account.get("render_bg_path") and Path(account["render_bg_path"]).exists():
        return {"bg_path": account["render_bg_path"]}
    if admin and background_available():
        return {}
    user_row = store.get_user(chat_id) or {}
    return {"bg_color": user_row.get("render_color") or DEFAULT_BG_COLOR}


async def rerender_draft(app: Application, draft: dict) -> int:
    """Alle Originalfotos eines Drafts neu freistellen. Gibt Anzahl Fehlschläge zurück."""
    originals = draft.get("original_photos") or draft.get("photos") or []
    if not originals:
        return 0
    render_kwargs = render_kwargs_for(app, draft["chat_id"])
    folder = TMP_DIR / draft["id"]
    folder.mkdir(parents=True, exist_ok=True)
    new_rendered, failed = [], 0
    for i, src in enumerate(originals):
        out = folder / f"render_{i:02d}.jpg"
        try:
            new_rendered.append(await asyncio.to_thread(
                lambda p=src, o=out: render_product(p, o, **render_kwargs)))
        except Exception as e:  # noqa: BLE001 — Original als Fallback
            log.warning("Neu-Rendern fehlgeschlagen für %s: %s", src, e)
            new_rendered.append(src)
            failed += 1
    draft["rendered_photos"] = new_rendered
    draft["photos"] = list(new_rendered)
    draft["image_urls"] = None
    return failed


async def process_photo_group(app: Application, items: list[dict]) -> None:
    store: Store = _ctx(app)["store"]
    chat_id = items[0]["chat_id"]
    caption = next((i["caption"] for i in items if i["caption"]), None)

    draft_data = {"status": "downloading", "photos": [], "caption": caption}
    draft_id = store.create_draft(chat_id, draft_data)
    folder = TMP_DIR / draft_id
    folder.mkdir(parents=True, exist_ok=True)

    try:
        paths = []
        for i, item in enumerate(items):
            tg_file = await app.bot.get_file(item["file_id"])
            path = folder / f"{i:02d}.jpg"
            await tg_file.download_to_drive(str(path))
            paths.append(str(path))
    except Exception as e:  # noqa: BLE001
        log.exception("Foto-Download fehlgeschlagen")
        await app.bot.send_message(chat_id, f"❌ Konnte Fotos nicht laden: {e}")
        store.delete_draft(draft_id)
        return

    render_kwargs = render_kwargs_for(app, chat_id)
    originals = list(paths)
    if _ctx(app).get("render", True):
        rendered, failed = [], 0
        for i, path in enumerate(paths):
            out = folder / f"render_{i:02d}.jpg"
            try:
                rendered.append(await asyncio.to_thread(
                    lambda p=path, o=out: render_product(p, o, **render_kwargs)))
            except (RenderError, Exception) as e:  # noqa: BLE001 — Original ist immer der Fallback
                log.warning("Rendering fehlgeschlagen für %s: %s", path, e)
                rendered.append(path)
                failed += 1
        if failed:
            await app.bot.send_message(
                chat_id,
                f"⚠️ Freisteller hat bei {failed}/{len(paths)} Bild(ern) nicht funktioniert — "
                f"dort wird das Original verwendet.",
            )
        paths = rendered

    draft = store.get_draft(draft_id)
    # Analyse läuft auf den ORIGINALEN (Hand als Größenreferenz, Umgebung, Details!),
    # gerendert wird nur für eBay-Upload und Vorschau.
    draft["original_photos"] = originals
    draft["rendered_photos"] = list(paths)  # für Original↔Freigestellt-Umschalter
    draft["photos"] = paths
    user_row = store.get_user(chat_id) or {}
    draft["business"] = bool(user_row.get("business"))  # gewerblich -> Gebühr überall anzeigen
    draft["status"] = "analyzing"
    store.update_draft(draft_id, draft)
    await run_pipeline(app, draft_id)


# ---------------------------------------------------------------- Text & Buttons

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    store: Store = _ctx(app)["store"]
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    # 0a) Website-Verbindungscode (L-123456)?
    if LINK_CODE_REGEX.match(text.upper()):
        await handle_link_code(app, update, text.upper())
        return

    # 0b) eBay-Redirect-URL — nur Admin oder verknüpfte Konten (Schutz vor Fremdnutzung)
    code = extract_oauth_code(text)
    if code:
        if is_admin(app, chat_id) or store.get_account_by_telegram(chat_id):
            await complete_ebay_connection(app, chat_id, code)
        else:
            await update.message.reply_text(ONBOARDING_TEXT)
        return

    # 1) Wartet ein ✏️-Edit auf Eingabe?
    pending = _ctx(app).setdefault("pending_edits", {}).pop(chat_id, None)
    if pending:
        draft_id, field = pending
        if field == "address":
            await handle_address(app, update, text)
            return
        draft = store.get_draft(draft_id)
        if not draft:
            await update.message.reply_text("Draft existiert nicht mehr.")
            return
        if field == "price":
            price = parse_price(text)
            if not price:
                _ctx(app)["pending_edits"][chat_id] = pending
                await update.message.reply_text("Das ist kein gültiger Preis. Beispiel: 16,90")
                return
            draft["price"] = price
        elif field == "title":
            if len(text) > 80:
                _ctx(app)["pending_edits"][chat_id] = pending
                await update.message.reply_text(f"Titel hat {len(text)} Zeichen — max. 80. Bitte kürzen.")
                return
            draft["listing"]["title"] = text
        elif field == "quantity":
            try:
                qty = int(text.strip())
            except ValueError:
                qty = 0
            if not 1 <= qty <= 1000:
                _ctx(app)["pending_edits"][chat_id] = pending
                await update.message.reply_text("Bitte eine Zahl zwischen 1 und 1000 senden.")
                return
            draft["quantity"] = qty
        elif field == "description":
            safe = html.escape(text.strip()).replace("\n", "<br>")
            draft["listing"]["description_html"] = f"<p>{safe}</p>"
            draft["image_urls"] = None  # Beschreibung ändert sich -> Offer neu aufbauen
        elif field == "condition":
            draft["listing"]["condition"] = text.strip()
            draft.pop("condition_id", None)        # erzwingt Neu-Auflösung beim Upload
            draft.pop("condition_descriptors", None)
        elif field == "graded":
            # Vorhandene Angaben behalten — Antwort kann auch nur die fehlende Nummer sein
            info = draft["listing"].get("graded_info") or {}
            tokens = text.replace(",", ".").split()
            grader = next((t for t in tokens if t.isalpha()), None) or info.get("grader")
            grade = next((t for t in tokens if re.fullmatch(r"\d{1,2}(\.5)?", t)), None) or info.get("grade")
            cert = next((t for t in tokens
                         if len(t) >= 5 and t.isalnum() and any(c.isdigit() for c in t)),
                        None) or info.get("cert_number")
            missing = [name for name, val in (("Bewerter", grader), ("Note", grade),
                                              ("Zertifikatsnummer", cert)) if not val]
            if missing:
                _ctx(app)["pending_edits"][chat_id] = pending
                await update.message.reply_text(
                    f"Mir fehlt noch: {', '.join(missing)}. Beispiel:  PSA 9.5 12345678"
                )
                return
            draft["listing"]["graded_info"] = {"grader": str(grader).upper(), "grade": grade,
                                               "cert_number": cert}
            store.update_draft(draft_id, draft)
            await update.message.reply_text(
                f"👍 {str(grader).upper()} {grade}, Zert. {cert} übernommen — "
                "jetzt ✅ Hochladen erneut drücken."
            )
            return
        store.update_draft(draft_id, draft)
        await send_preview(app, chat_id, draft)
        return

    # 2) Noch nicht verbunden? Evtl. wartet ein Website-eBay-Token auf das Setup
    if not get_ready_user(app, chat_id):
        from bot.ebay.auth import _token_key
        account = store.get_account_by_telegram(chat_id)
        if account and store.kv_get(_token_key(chat_id)):
            await continue_account_setup(app, chat_id)
            return
        await update.message.reply_text(ONBOARDING_TEXT)
        return

    # 3) Antwort auf Rückfrage oder Nachzügler-Caption (innerhalb 60 s)
    draft = store.latest_draft_for_chat(chat_id)
    if draft:
        age = time.time() - draft["created_at"]
        if draft["status"] == "uncertain" or (age < CAPTION_FOLLOWUP_WINDOW_S
                                              and not draft.get("caption")):
            extra = (draft.get("caption") or "")
            draft["caption"] = (extra + "\n" + text).strip()
            store.update_draft(draft["id"], draft)
            await update.message.reply_text("👍 Info übernommen — generiere neu…")
            await run_pipeline(app, draft["id"])
            return

    await update.message.reply_text(
        "Schick mir Produktfotos (gern als Album) mit kurzer Beschreibung als Caption."
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    cfg: Config = _ctx(app)["cfg"]
    query = update.callback_query
    store: Store = _ctx(app)["store"]
    parts = query.data.split(":")
    action, draft_id = parts[0], parts[1]
    extra = parts[2:]

    # Bulk-Überarbeitung (keine Draft-ID)
    if action == "rework":
        if draft_id == "no":
            await query.answer("Abgebrochen.")
            await query.edit_message_text("Abgebrochen — nichts geändert.")
            return
        await query.answer("Los geht's…")
        await run_rework_listings(app, query.from_user.id, query.message)
        return

    draft = store.get_draft(draft_id)
    if not draft:
        await query.answer("Draft existiert nicht mehr.", show_alert=True)
        return
    if query.from_user.id != draft["chat_id"]:
        return  # fremder Draft: keinerlei Reaktion

    if action == "upload":
        if draft.get("status") == "published":
            await query.answer("Schon veröffentlicht — nutze ✏️ Bearbeiten.", show_alert=True)
            return
        if not draft.get("price"):
            await query.answer("Bitte zuerst einen Preis setzen (✏️ Preis).", show_alert=True)
            return
        if not draft.get("category_id"):
            await query.answer("Keine Kategorie gefunden — 🔁 Neu generieren versuchen.", show_alert=True)
            return
        if not is_admin(app, query.from_user.id):
            account = store.get_account_by_telegram(draft["chat_id"])
            plan = (account or {}).get("plan")
            if plan not in PLAN_LIMITS:
                await query.answer(
                    "Zum Veröffentlichen brauchst du einen Plan (14 Tage gratis) — "
                    "wähle ihn auf der Listo-Website in Schritt 5.", show_alert=True)
                return
            limit = PLAN_LIMITS[plan]
            used = store.listings_this_month(draft["chat_id"])
            if limit is not None and used >= limit:
                await query.answer(
                    f"Monatslimit erreicht ({used}/{limit} Listings im {plan.capitalize()}-Plan). "
                    "Upgrade auf der Website — dann geht's sofort weiter.", show_alert=True)
                return
        await query.answer("Starte Upload…")
        await run_upload(app, draft_id, draft["chat_id"])
    elif action == "price":
        _ctx(app).setdefault("pending_edits", {})[draft["chat_id"]] = (draft_id, "price")
        await query.answer()
        await app.bot.send_message(draft["chat_id"], "Neuen Preis senden, z.B. 16,90")
    elif action == "title":
        _ctx(app).setdefault("pending_edits", {})[draft["chat_id"]] = (draft_id, "title")
        await query.answer()
        await app.bot.send_message(draft["chat_id"], "Neuen Titel senden (max. 80 Zeichen)")
    elif action == "qty":
        if draft.get("format") == "AUCTION":
            await query.answer("Auktionen haben immer Stückzahl 1.", show_alert=True)
            return
        _ctx(app).setdefault("pending_edits", {})[draft["chat_id"]] = (draft_id, "quantity")
        await query.answer()
        await app.bot.send_message(draft["chat_id"], "Verfügbare Stückzahl senden (z.B. 5)")
    elif action == "fmt":
        draft["format"] = "AUCTION" if draft.get("format", "FIXED_PRICE") == "FIXED_PRICE" else "FIXED_PRICE"
        apply_price_rule(draft)  # 1 € Auktionsstart bzw. fairer Sofortkauf-Preis
        store.update_draft(draft_id, draft)
        text, keyboard = build_preview(draft, published=draft.get('status') == 'published')
        await query.answer("Auktion 🔨" if draft["format"] == "AUCTION" else "Festpreis 💶")
        # Album-Vorschau: Buttons hängen an einer Textnachricht, nicht an einem Foto
        if query.message.photo:
            await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    elif action == "dur":
        # Auktionslaufzeit durchschalten: 1 -> 3 -> 5 -> 7 -> 10 -> 1
        from bot.ebay.inventory import AUCTION_DURATIONS
        options = sorted(AUCTION_DURATIONS)  # [1, 3, 5, 7, 10]
        cur = int(draft.get("auction_days") or 7)
        nxt = options[(options.index(cur) + 1) % len(options)] if cur in options else 1
        draft["auction_days"] = nxt
        store.update_draft(draft_id, draft)
        await query.answer(f"Laufzeit: {nxt} {'Tag' if nxt == 1 else 'Tage'}")
        text, keyboard = build_preview(draft, published=draft.get('status') == 'published')
        if query.message.photo:
            await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    elif action == "usk":
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=build_usk_menu(draft))
    elif action == "uskset":
        val = extra[0] if extra else "none"
        aspects = draft["listing"].setdefault("aspects", {})
        if val == "none":
            aspects.pop(USK_ASPECT, None)
            note = "Altersfreigabe entfernt"
        else:
            aspects[USK_ASPECT] = [USK_VALUES[int(val)]]
            note = f"USK ab {val} gesetzt"
        store.update_draft(draft_id, draft)
        await query.answer(note)
        # zurück in die Vorschau (Text zeigt jetzt die Freigabe)
        text, keyboard = build_preview(draft, published=draft.get("status") == "published")
        if query.message.photo:
            await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    elif action == "desc":
        _ctx(app).setdefault("pending_edits", {})[draft["chat_id"]] = (draft_id, "description")
        await query.answer()
        await app.bot.send_message(draft["chat_id"],
            "Neue Beschreibung als Text senden — sie ersetzt die automatische komplett.")
    elif action == "cond":
        _ctx(app).setdefault("pending_edits", {})[draft["chat_id"]] = (draft_id, "condition")
        await query.answer()
        await app.bot.send_message(draft["chat_id"],
            "Zustand als Text senden, z. B.: Neu · Neuwertig · Gebraucht · Sehr gut · "
            "Near Mint · Akzeptabel. (Bei gegradeten Karten bleibt das Grading erhalten.)")
    elif action == "offer":
        bo = draft.get("best_offer")
        if bo and bo.get("enabled"):
            draft["best_offer"] = None
            note = "Preisvorschlag aus"
        else:
            draft["best_offer"] = {"enabled": True, "min_price": None}
            note = "Preisvorschlag an"
        store.update_draft(draft_id, draft)
        await query.answer(note)
        text, keyboard = build_preview(draft, published=draft.get('status') == 'published')
        if query.message.photo:
            await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    elif action == "img":
        if not any(Path(p).exists() for p in (draft.get("photos") or [])):
            await query.answer(
                "Die lokalen Fotos wurden bereits aufgeräumt — Bilder lassen sich nur "
                "kurz nach dem Upload tauschen. Alles andere ist weiter editierbar.",
                show_alert=True)
            return
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=build_images_menu(draft))
    elif action == "imgtog":
        i = int(extra[0]) if extra else 0
        photos = draft.get("photos") or []
        originals = draft.get("original_photos") or []
        rendered = draft.get("rendered_photos") or []
        if i < len(photos) and i < len(originals) and i < len(rendered):
            if photos[i] == originals[i] and rendered[i] != originals[i]:
                photos[i] = rendered[i]   # -> Freigestellt
            else:
                photos[i] = originals[i]  # -> Original
            draft["photos"] = photos
            draft["image_urls"] = None    # Upload-Cache passt nicht mehr
            store.update_draft(draft_id, draft)
        await query.answer("Umgeschaltet")
        await query.edit_message_reply_markup(reply_markup=build_images_menu(draft))
    elif action == "imgren":
        await query.answer("Rendere neu…")
        failed = await rerender_draft(app, draft)
        store.update_draft(draft_id, draft)
        msg = "🖼 Bilder neu gerendert — neue Vorschau unten."
        if failed:
            msg = f"🖼 Neu gerendert ({failed} ohne Freisteller) — neue Vorschau unten."
        if query.message.photo:
            await query.edit_message_caption(caption=msg)
        else:
            await query.edit_message_text(text=msg)
        await send_preview(app, draft["chat_id"], draft)
    elif action == "imgback":
        await query.answer()
        _, keyboard = build_preview(draft, published=draft.get('status') == 'published')
        await query.edit_message_reply_markup(reply_markup=keyboard)
    elif action == "regen":
        await query.answer("Generiere neu…")
        await run_pipeline(app, draft_id)
    elif action == "discard":
        cleanup_photos(draft)
        store.delete_draft(draft_id)
        await query.answer("Verworfen.")
        if query.message.photo:
            await query.edit_message_caption(caption="❌ Entwurf verworfen.")
        else:
            await query.edit_message_text(text="❌ Entwurf verworfen.")
    elif action == "edit":
        # Veröffentlichtes Listing bearbeiten: editierbare Vorschau senden
        await query.answer()
        await send_preview(app, draft["chat_id"], draft)
    elif action == "save":
        await query.answer("Speichere Änderungen…")
        await run_update(app, draft_id, draft["chat_id"])
    elif action == "done":
        await query.answer("Fertig.")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
    elif action == "end":
        await query.answer()
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Ja, beenden", callback_data=f"endyes:{draft_id}"),
            InlineKeyboardButton("Abbrechen", callback_data=f"done:{draft_id}")]])
        msg = "🛑 Listing wirklich beenden? Es wird von eBay genommen."
        if query.message.photo:
            await query.edit_message_caption(caption=msg, reply_markup=kb)
        else:
            await query.edit_message_text(text=msg, reply_markup=kb)
    elif action == "endyes":
        await run_end_listing(app, draft_id, draft["chat_id"], query)


async def run_update(app: Application, draft_id: str, chat_id: int) -> None:
    """Änderungen an einem bereits veröffentlichten Listing live zu eBay schieben."""
    store: Store = _ctx(app)["store"]
    ebay: EbayClient = _ctx(app)["ebay"]
    draft = store.get_draft(draft_id)
    if not draft or not draft.get("offer_id"):
        await app.bot.send_message(chat_id, "Listing nicht mehr auffindbar.")
        return
    user_id = chat_id
    policies = store.user_policies(user_id)
    listing = draft["listing"]
    status = await app.bot.send_message(chat_id, "⏳ Aktualisiere Listing…")
    try:
        # Bilder geändert (Umschalter/neu gerendert)? -> neu hochladen
        image_urls = draft.get("image_urls")
        if not image_urls:
            existing = [p for p in draft["photos"] if Path(p).exists()]
            if existing:
                image_urls = []
                for i, path in enumerate(existing, 1):
                    await status.edit_text(f"⏳ Lade Bild {i}/{len(existing)} hoch…")
                    image_urls.append(await upload_image(ebay, path, user_id))
            else:
                # Lokale Fotos schon aufgeräumt -> Bild-URLs vom Live-Listing übernehmen
                inv = await get_inventory_item(ebay, draft["sku"], user_id)
                image_urls = ((inv or {}).get("product") or {}).get("imageUrls") or []
                if not image_urls:
                    await status.edit_text("❌ Keine Bilder auffindbar — bitte Listing neu erstellen.")
                    return
            draft["image_urls"] = image_urls
            store.update_draft(draft_id, draft)

        # Single-Value-Merkmale kürzen (sonst 25002 beim Aktualisieren)
        singles = await get_single_value_aspects(ebay, store, draft["category_id"])
        aspects = listing.get("aspects") or {}
        for name in singles:
            vals = aspects.get(name)
            if isinstance(vals, list) and len(vals) > 1:
                aspects[name] = vals[:1]
        listing["aspects"] = aspects

        policy = await get_condition_policy(ebay, store, draft["category_id"])
        allowed = [str(c["conditionId"]) for c in policy]
        item_text = " ".join([listing.get("title", ""), draft.get("caption") or "",
                              str(listing.get("aspects") or "")])
        condition, _ = resolve_condition(listing["condition"], allowed, item_text,
                                         is_graded=bool(listing.get("graded_info")))
        listing["condition"] = condition
        descriptors, frage = build_condition_descriptors(condition, policy, listing, item_text)
        if frage:
            _ctx(app).setdefault("pending_edits", {})[chat_id] = (draft_id, "graded")
            await status.edit_text(frage)
            return
        quantity = 1 if draft.get("format") == "AUCTION" else int(draft.get("quantity") or 1)

        await status.edit_text("⏳ Aktualisiere Artikeldaten…")
        await create_inventory_item(
            ebay, draft["sku"], user_id=user_id,
            title=listing["title"], description=listing["description_html"],
            condition=condition, condition_description=listing.get("condition_description"),
            aspects=listing.get("aspects") or {}, image_urls=image_urls,
            condition_descriptors=descriptors, quantity=quantity,
        )
        await status.edit_text("⏳ Aktualisiere Preis & Angebot…")
        await update_offer(
            ebay, policies, draft["offer_id"], draft["sku"], user_id=user_id,
            category_id=draft["category_id"], price_eur=draft["price"],
            listing_description=listing["description_html"],
            listing_format=draft.get("format", "FIXED_PRICE"),
            quantity=quantity, best_offer=draft.get("best_offer"),
            auction_days=int(draft.get("auction_days") or 7),
            title=listing.get("title"),
        )
        store.update_draft(draft_id, draft)
        await status.edit_text(
            f"✅ <b>Änderungen sind live!</b>\n{html.escape(listing['title'])}\n"
            f"💶 {draft['price']} €\n{draft.get('item_url', '')}",
            parse_mode="HTML", reply_markup=build_published_actions(draft),
        )
    except (MediaError, InventoryError, EbayAuthError) as e:
        log.exception("Update-Fehler für Listing %s", draft_id)
        await status.edit_text(
            f"❌ eBay-Fehler beim Aktualisieren:\n{e}\n\n"
            "Tipp: Format (Auktion↔Festpreis) lässt sich bei einem laufenden Listing "
            "oft nicht ändern — dafür Listing beenden und neu einstellen."
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Unerwarteter Update-Fehler für Listing %s", draft_id)
        await status.edit_text(f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}")


async def run_end_listing(app: Application, draft_id: str, chat_id: int, query) -> None:
    store: Store = _ctx(app)["store"]
    ebay: EbayClient = _ctx(app)["ebay"]
    draft = store.get_draft(draft_id)
    if not draft or not draft.get("offer_id"):
        await query.answer("Listing nicht mehr auffindbar.", show_alert=True)
        return
    await query.answer("Beende Listing…")
    try:
        await withdraw_offer(ebay, draft["offer_id"], chat_id)
        draft["status"] = "ended"
        store.update_draft(draft_id, draft)
        cleanup_photos(draft)
        text = "🛑 Listing beendet — es ist nicht mehr auf eBay aktiv."
    except (InventoryError, EbayAuthError) as e:
        text = f"❌ Konnte das Listing nicht beenden:\n{e}"
    if query.message.photo:
        await query.edit_message_caption(caption=text)
    else:
        await query.edit_message_text(text=text)


# ---------------------------------------------------------------- Commands

async def cmd_ueberarbeiten(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Alle veröffentlichten Listings auf einheitliche Titel + Beschreibungen umformen."""
    app = context.application
    store: Store = _ctx(app)["store"]
    chat_id = update.message.chat_id
    if not get_ready_user(app, chat_id):
        await update.message.reply_text(ONBOARDING_TEXT)
        return
    if not is_admin(app, chat_id):
        account = store.get_account_by_telegram(chat_id)
        if not account or account.get("plan") not in PLAN_LIMITS:
            await update.message.reply_text(
                "Die Bulk-Überarbeitung gibt es ab dem Starter-Plan — "
                "wähle ihn auf der Listo-Website."
            )
            return
    items = store.published_listings_for_chat(chat_id)
    if not items:
        await update.message.reply_text("Keine veröffentlichten Listings gefunden.")
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Ja, alle {len(items)} überarbeiten", callback_data="rework:go"),
        InlineKeyboardButton("Abbrechen", callback_data="rework:no")]])
    await update.message.reply_text(
        f"🧹 Ich überarbeite {len(items)} Listings: einheitliche Titel & Beschreibungen "
        "im neuen Format. Bilder, Preise und Zustand bleiben unverändert. "
        "Das kann ein paar Minuten dauern.",
        reply_markup=kb,
    )


async def run_rework_listings(app: Application, chat_id: int, status_msg) -> None:
    store: Store = _ctx(app)["store"]
    ebay: EbayClient = _ctx(app)["ebay"]
    analyzer = _ctx(app)["reformat_analyzer"]
    items = store.published_listings_for_chat(chat_id)
    done, failed = 0, 0
    for i, it in enumerate(items, 1):
        sku = it["sku"]
        try:
            await status_msg.edit_text(f"🧹 Überarbeite {i}/{len(items)}: {it['title'][:40]}…")
            inv = await get_inventory_item(ebay, sku, chat_id)
            if not inv:
                failed += 1
                continue
            product = inv.get("product") or {}
            aspects = product.get("aspects") or {}
            condition = inv.get("condition") or "USED_GOOD"
            new = await analyzer.reformat_listing(
                product.get("title") or it["title"], aspects, condition, None)
            qty = (inv.get("availability", {}).get("shipToLocationAvailability", {})
                   .get("quantity") or 1)
            await create_inventory_item(
                ebay, sku, user_id=chat_id,
                title=new["title"], description=new["description_html"],
                condition=condition, condition_description=inv.get("conditionDescription"),
                aspects=aspects, image_urls=product.get("imageUrls") or [],
                condition_descriptors=inv.get("conditionDescriptors"), quantity=qty,
            )
            done += 1
        except Exception as e:  # noqa: BLE001 — einzelne Fehler überspringen, Rest läuft weiter
            log.warning("Rework fehlgeschlagen für %s: %s", sku, e)
            failed += 1
    summary = f"✅ Fertig — {done} Listings überarbeitet."
    if failed:
        summary += f" {failed} übersprungen (Fehler)."
    await status_msg.edit_text(summary)


async def cmd_gewerblich(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gewerblich-Modus pro Nutzer: Gebühren-Schätzung gilt dann für ALLE Kategorien."""
    app = context.application
    store: Store = _ctx(app)["store"]
    chat_id = update.message.chat_id
    if not get_ready_user(app, chat_id):
        await update.message.reply_text(ONBOARDING_TEXT)
        return
    arg = (context.args[0].lower() if context.args else "")
    if arg in ("on", "an", "ja"):
        store.upsert_user(chat_id, business=1)
        await update.message.reply_text(
            "🏢 Gewerblich-Modus AN — ich rechne dir ab jetzt bei JEDEM Listing die "
            "eBay-Verkaufsprovision (~11 %) in der Vorschau vor."
        )
    elif arg in ("off", "aus", "nein"):
        store.upsert_user(chat_id, business=0)
        await update.message.reply_text(
            "🏠 Privat-Modus — Gebühren-Hinweis erscheint nur noch bei Sammelkarten "
            "(die kosten auch privat 11 %)."
        )
    else:
        user_row = store.get_user(chat_id) or {}
        state = "gewerblich 🏢" if user_row.get("business") else "privat 🏠"
        await update.message.reply_text(
            f"Aktuell: {state}\nUmschalten mit /gewerblich on oder /gewerblich off"
        )


async def cmd_listings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zuletzt veröffentlichte Listings auflisten — mit Knopf zum Bearbeiten."""
    app = context.application
    store: Store = _ctx(app)["store"]
    chat_id = update.message.chat_id
    if not get_ready_user(app, chat_id):
        await update.message.reply_text(ONBOARDING_TEXT)
        return
    drafts = store.published_drafts_for_chat(chat_id)
    if not drafts:
        await update.message.reply_text(
            "Noch keine veröffentlichten Listings. Sobald du eins hochlädst, "
            "kannst du es hier jederzeit bearbeiten."
        )
        return
    await update.message.reply_text(f"🟢 Deine letzten {len(drafts)} Listings — zum Bearbeiten antippen:")
    for d in drafts:
        title = d["listing"]["title"]
        price = d.get("price", "—")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ Bearbeiten", callback_data=f"edit:{d['id']}"),
            InlineKeyboardButton("🔗 eBay", url=d.get("item_url") or "https://www.ebay.de"),
        ]])
        await app.bot.send_message(
            chat_id, f"<b>{html.escape(title)}</b>\n💶 {price} €",
            parse_mode="HTML", reply_markup=kb,
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    if not get_ready_user(app, update.message.chat_id):
        await update.message.reply_text(ONBOARDING_TEXT)
        return
    await update.message.reply_text(
        "Listo 🤖 — Fotos + kurze Beschreibung schicken, ich baue daraus "
        "einen eBay-Listing-Entwurf. Veröffentlicht wird NUR nach ✅-Bestätigung.\n\n"
        "/listings — veröffentlichte Listings bearbeiten\n"
        "/ueberarbeiten — alle Titel & Beschreibungen vereinheitlichen\n"
        "/status — Konto & Zähler\n/verbinden — eBay-Konto (neu) verknüpfen\n/help — Hilfe"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "1. Fotos als Album senden (Beschreibung als Caption des Albums oder als "
        "Textnachricht direkt danach).\n"
        "2. Entwurf prüfen, ggf. ✏️ Preis/Titel anpassen.\n"
        "3. ✅ Hochladen — erst dann geht etwas zu eBay.\n"
        "4. Schon live? Mit /listings jederzeit bearbeiten (Preis, Titel, "
        "Beschreibung, Zustand, Menge, Bilder) — Änderungen gehen sofort live.\n\n"
        f"DRY_RUN ist aktuell {'AN 🧪' if _ctx(context.application)['dry_run'] else 'AUS 🔴'}."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    ebay: EbayClient = _ctx(app)["ebay"]
    store: Store = _ctx(app)["store"]
    token = ebay.user_token_status(update.message.chat_id)
    if token["ok"]:
        token_line = (f"✅ User-Token ok (Access noch {token['access_valid_s'] // 60} min, "
                      f"Refresh noch ~{token['refresh_valid_d']} Tage)")
    else:
        token_line = f"❌ User-Token: {token['detail']}"
    chat_id = update.message.chat_id
    render_state = "an" if _ctx(app).get("render", True) else "aus"
    plan_line = ""
    if not is_admin(app, chat_id):
        account = store.get_account_by_telegram(chat_id)
        if account:
            plan = account.get("plan", "trial")
            limit = PLAN_LIMITS.get(plan)
            used = store.listings_this_month(chat_id)
            usage = f"{used}/{limit}" if limit is not None else f"{used} (unbegrenzt)"
            plan_line = f"\n💳 Plan: {plan.capitalize()} — diesen Monat {usage} Listings"
    color = (store.get_user(chat_id) or {}).get("render_color") or DEFAULT_BG_COLOR
    await update.message.reply_text(
        f"{token_line}{plan_line}\n"
        f"📦 Listings heute: {store.listings_today()}\n"
        f"🧪 DRY_RUN: {'an' if _ctx(app)['dry_run'] else 'aus'}\n"
        f"🖼 Rendering: {render_state} · Hintergrund: {color} (/farbe)"
    )


async def cmd_dryrun(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    if not is_admin(app, update.message.from_user.id):
        return
    store: Store = _ctx(app)["store"]
    arg = (context.args[0].lower() if context.args else "")
    if arg == "on":
        _ctx(app)["dry_run"] = True
        store.kv_set("dry_run", True)  # überlebt Neustarts
        await update.message.reply_text("🧪 DRY_RUN an — publishOffer wird übersprungen.")
    elif arg == "off":
        _ctx(app)["dry_run"] = False
        store.kv_set("dry_run", False)
        await update.message.reply_text("🔴 DRY_RUN aus — Listings gehen LIVE zu eBay!")
    else:
        await update.message.reply_text("Benutzung: /dryrun on|off")


async def cmd_render(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    if not is_admin(app, update.message.from_user.id):
        return
    store: Store = _ctx(app)["store"]
    arg = (context.args[0].lower() if context.args else "")
    if arg == "on":
        if not background_available():
            await update.message.reply_text(
                "Kein Hintergrund gespeichert — erst ein Bild mit Caption „hintergrund“ schicken."
            )
            return
        _ctx(app)["render"] = True
        store.kv_set("render", True)
        await update.message.reply_text("🖼 Rendering an — Produkte werden freigestellt.")
    elif arg == "off":
        _ctx(app)["render"] = False
        store.kv_set("render", False)
        await update.message.reply_text("📷 Rendering aus — Fotos gehen unbearbeitet zu eBay.")
    else:
        await update.message.reply_text("Benutzung: /render on|off")


# ---------------------------------------------------------------- Start

def main() -> None:
    setup_logging()
    cfg = load_config()
    TMP_DIR.mkdir(exist_ok=True)
    store = Store()

    app = ApplicationBuilder().token(cfg.telegram_bot_token).build()
    ebay = EbayClient(cfg, store)
    analyzer = ClaudeAnalyzer(cfg)
    # Reine Text-Umformulierung (kein Foto nötig) günstiger über DeepSeek, falls Key gesetzt —
    # Fotoanalyse bleibt IMMER bei Claude (DeepSeek kann keine Bilder lesen).
    reformat_analyzer = DeepSeekAnalyzer(cfg) if cfg.deepseek_api_key else analyzer
    if cfg.deepseek_api_key:
        log.info("DeepSeek aktiv (%s) für Listing-Umformulierung (Rework)", cfg.deepseek_model)

    # Migration aus der Single-User-Ära: Admin bekommt sein Token + .env-Setup als User-Record
    ebay.migrate_legacy_token(cfg.allowed_user_id)
    if not store.get_user(cfg.allowed_user_id):
        store.upsert_user(
            cfg.allowed_user_id, status="ready",
            merchant_location_key=cfg.merchant_location_key,
            fulfillment_policy_id=cfg.fulfillment_policy_id,
            payment_policy_id=cfg.payment_policy_id,
            return_policy_id=cfg.return_policy_id,
        )
        log.info("Admin-Nutzer %s aus .env angelegt", cfg.allowed_user_id)

    async def on_album_complete(group_id: str, items: list[dict]) -> None:
        await process_photo_group(app, items)

    # Persistente Schalter aus SQLite (überleben Neustarts); .env ist nur der Default
    stored_dry_run = store.kv_get("dry_run")
    stored_render = store.kv_get("render")
    app.bot_data.update({
        "cfg": cfg,
        "store": store,
        "ebay": ebay,
        "analyzer": analyzer,
        "reformat_analyzer": reformat_analyzer,
        "dry_run": cfg.dry_run if stored_dry_run is None else bool(stored_dry_run),
        "render": True if stored_render is None else bool(stored_render),
        "album_buffer": AlbumBuffer(on_album_complete, delay=2.5),
        "pending_edits": {},
    })

    # Multi-Tenant: alle dürfen schreiben, Funktionen gibt es erst nach /verbinden.
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("verbinden", cmd_verbinden))
    app.add_handler(CommandHandler("farbe", cmd_farbe))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("listings", cmd_listings))
    app.add_handler(CommandHandler("gewerblich", cmd_gewerblich))
    app.add_handler(CommandHandler("ueberarbeiten", cmd_ueberarbeiten))
    app.add_handler(CommandHandler("dryrun", cmd_dryrun))
    app.add_handler(CommandHandler("render", cmd_render))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    cleanup_stale_drafts(store)  # beim Start; danach täglich
    if app.job_queue:
        app.job_queue.run_repeating(lambda ctx: cleanup_stale_drafts(store),
                                    interval=86400, first=86400)

    if app.bot_data["dry_run"]:
        log.info("🧪 DRY_RUN aktiv — publishOffer wird übersprungen.")
    else:
        log.info("🔴 DRY_RUN aus — Listings gehen live zu eBay.")
    log.info("Bot startet (Modell: %s, Rendering: %s)…", cfg.claude_model,
             "an" if app.bot_data["render"] and background_available() else "aus")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
