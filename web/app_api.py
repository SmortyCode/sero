"""SERO-App-API: die komplette Telegram-Bot-Logik als Chat-API für die Mobile-App.

Gleiche Pipeline, gleiche Bausteine (Claude-Analyse, Taxonomy, Preisrecherche,
Rendering, Inventory/Offer/Publish) — nur dass Status & Vorschau nicht als
Telegram-Nachrichten rausgehen, sondern als Chat-Events in der DB landen,
die die App pollt. Drafts teilen sich die ID-Welt mit dem Telegram-Bot
(chat_id = Telegram-ID des Accounts), d.h. App und Telegram sehen dieselben
Listings und können sie beide bearbeiten.
"""

from __future__ import annotations

import asyncio
import json
import os
import logging
import math

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()   # iPhone-HEIC lesbar machen
except ImportError:
    import logging as _logging
    _logging.getLogger("app_api").warning(
        "pillow-heif fehlt — iPhone-HEIC-Fotos werden abgewiesen!")

# Dekompressionsbomben-Deckel: 40 MP reichen für jedes iPhone-Foto; ohne den
# Deckel entpackt ein präpariertes Bild Hunderte MB in den RAM.
from PIL import Image as _PILImage
_PILImage.MAX_IMAGE_PIXELS = 40_000_000

import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import (FileResponse, JSONResponse, RedirectResponse,
                               StreamingResponse)
from pydantic import BaseModel, Field

from bot.claude_client import ClaudeAnalyzer, ClaudeError
from bot.config import TMP_DIR
from bot.drafts import Store
from bot.ebay.auth import EbayAuthError, EbayClient, EbayTimeout
from bot.ebay.browse import research_price
from bot.ebay.inventory import (
    AUCTION_DURATIONS,
    InventoryError,
    create_inventory_item,
    create_offer,
    generate_sku,
    get_active_buyer_offers,
    get_inventory_item,
    live_price_from_offer,
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
from bot.ebay.taxonomy import (
    TaxonomyError,
    get_required_aspects,
    get_single_value_aspects,
    suggest_category,
)
from bot.fees import estimate_fee
from bot.main import (
    PLAN_LIMITS,
    USK_ASPECT,
    USK_VALUES,
    apply_price_rule,
    comps_verwertbar,
    cleanup_photos,
    current_usk,
    is_media_category,
    parse_price,
    reorder_photos,
)
from bot.render import DEFAULT_BG_COLOR, background_available, render_product
from web.prices import identify_card, lookup_card_price

log = logging.getLogger("app_api")

ACCOUNT_UID_OFFSET = 10 ** 15


# Auf Modulebene, nicht im Router-Closure: wegen `from __future__ import annotations`
# löst FastAPI Annotationen über die Modul-Globals auf — lokale Klassen fände es nicht
# und würde den Body als Query-Parameter deuten (422).
class ActionBody(BaseModel):
    action: str
    value: str | None = None


class AnswerBody(BaseModel):
    text: str


class ItemPatchBody(BaseModel):
    # Längen-Deckel: das Item landet als JSON-Blob in der DB und wird bei JEDEM
    # Sammlungs-Abruf an alle Geräte ausgeliefert — ohne Deckel bläht ein einziger
    # manipulierter Request Traffic und Datenbank des ganzen Kontos dauerhaft auf.
    name: str | None = Field(None, max_length=160)
    category: str | None = Field(None, max_length=40)
    condition: str | None = Field(None, max_length=60)
    quantity: int | None = None
    purchase_price: str | None = Field(None, max_length=20)
    notes: str | None = Field(None, max_length=2000)
    favorite: bool | None = None
    wishlist: bool | None = None
    tags: list[str] | None = Field(None, max_length=12)


class AlertBody(BaseModel):
    threshold: str | None = None    # None = Alarm löschen
    direction: str = "above"        # above | below


class SettingsBody(BaseModel):
    notifications: bool | None = None


class ListOptionsBody(BaseModel):
    format: str | None = None          # FIXED_PRICE | AUCTION
    auction_days: int | None = None    # 1/3/5/7/10
    price_mode: str | None = None      # market | market_minus10 | auction1 | fixed
    price_value: float | None = None


class RenderBgBody(BaseModel):
    mode: str                          # white | warm | black | logo


class MatchBody(BaseModel):
    game: str
    name: str
    number: str | None = None
    ref_id: str | None = None
    tcgcsv: dict | None = None


class RotateBody(BaseModel):
    index: int = 0
    degrees: int = 90  # 90 | 180 | 270 (Uhrzeigersinn)


# Sammlungs-Fotos NICHT in TMP_DIR: der Bot-Cleanup räumt dort verwaiste Ordner ab.
# Über SERO_COL_DIR umlenkbar, damit Tests NIE in die echten Fotos schreiben
# (dieselbe Vorsichtsmaßnahme wie SERO_DB — Svens Sammlung ist produktiv).
COL_DIR = Path(os.environ.get("SERO_COL_DIR")) if os.environ.get("SERO_COL_DIR") \
    else Path(__file__).resolve().parent.parent / "collection_photos"
COL_DIR.mkdir(exist_ok=True)

CATEGORY_RULES = [
    ("Pokémon", ("pokemon", "pokémon", "pikachu", "glurak", "charizard")),
    ("One Piece", ("one piece", "onepiece", "ruffy", "luffy")),
    ("Magic", ("magic: the gathering", "magic the gathering", "mtg ")),
    ("Yu-Gi-Oh!", ("yugioh", "yu-gi-oh")),
    ("Lorcana", ("lorcana",)),
    ("Sport", ("panini", "topps", "match attax", "fußballkarte", "nba ", "nfl ")),
    ("Games", ("videospiel", "nintendo", "playstation", "ps1", "ps2", "ps3", "ps4", "ps5",
               "xbox", "game boy", "gameboy", "wata", "sega", "switch")),
    ("LEGO", ("lego",)),
]


def guess_category(*texts: str) -> str:
    blob = " ".join(t or "" for t in texts).lower()
    for name, keys in CATEGORY_RULES:
        if any(k in blob for k in keys):
            return name
    if any(k in blob for k in ("karte", "card", "tcg", "trading card", "booster", "display", "psa", "cgc", "bgs")):
        return "TCG Sonstiges"
    return "Sonstiges"
_tasks: set[asyncio.Task] = set()  # Referenzen halten, sonst räumt GC laufende Pipelines ab


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def build_router(store: Store, ebay: EbayClient, cfg) -> APIRouter:
    router = APIRouter(prefix="/api/app")
    analyzer = ClaudeAnalyzer(cfg)

    store._conn.execute(  # noqa: SLF001 — gleiche Konvention wie Analytics-Tabellen
        "CREATE TABLE IF NOT EXISTS app_chat ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, "
        "ts REAL NOT NULL, role TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL)")
    store._conn.execute(  # noqa: SLF001
        "CREATE TABLE IF NOT EXISTS collection_items ("
        "id TEXT PRIMARY KEY, account_id INTEGER NOT NULL, "
        "created_at REAL NOT NULL, updated_at REAL NOT NULL, data TEXT NOT NULL)")
    store._conn.execute(  # noqa: SLF001
        "CREATE TABLE IF NOT EXISTS price_history ("
        "item_id TEXT NOT NULL, account_id INTEGER NOT NULL, "
        "ts REAL NOT NULL, value REAL NOT NULL, source TEXT)")
    store._conn.execute(  # noqa: SLF001
        "CREATE INDEX IF NOT EXISTS idx_ph_item ON price_history (item_id, ts)")
    # Ohne diese beiden macht SQLite bei jeder Sammlung einen Full Scan samt
    # Sortier-B-Baum — bei 5.000 Stücken auf jedem einzelnen Abruf.
    store._conn.execute(  # noqa: SLF001
        "CREATE INDEX IF NOT EXISTS idx_col_acc ON collection_items (account_id, created_at DESC)")
    store._conn.execute(  # noqa: SLF001
        "CREATE INDEX IF NOT EXISTS idx_ph_acc ON price_history (account_id, ts)")
    store._conn.execute(  # noqa: SLF001
        "CREATE TABLE IF NOT EXISTS price_alerts ("
        "item_id TEXT PRIMARY KEY, account_id INTEGER NOT NULL, "
        "threshold REAL NOT NULL, direction TEXT NOT NULL, "
        "created_at REAL NOT NULL, triggered_at REAL)")
    store._conn.commit()  # noqa: SLF001

    # ------------------------------------------------------------ Helfer

    def uid_for(account: dict) -> int:
        """Effektive Nutzer-ID für eBay-Tokens/Policies/Drafts: die Telegram-ID,
        falls verknüpft (dann teilen sich App und Bot alles), sonst synthetisch."""
        return account.get("telegram_id") or (ACCOUNT_UID_OFFSET + account["id"])

    def is_admin(account: dict) -> bool:
        return account.get("telegram_id") == cfg.allowed_user_id

    def chat_add(account_id: int, role: str, kind: str, body: dict) -> int:
        with store._lock:  # noqa: SLF001
            cur = store._conn.execute(  # noqa: SLF001
                "INSERT INTO app_chat (account_id, ts, role, kind, body) VALUES (?, ?, ?, ?, ?)",
                (account_id, time.time(), role, kind, json.dumps(body, ensure_ascii=False)))
            store._conn.commit()  # noqa: SLF001
        notify(account_id, "chat", str(cur.lastrowid))
        return cur.lastrowid

    def chat_set(msg_id: int, body: dict) -> None:
        with store._lock:  # noqa: SLF001
            store._conn.execute(  # noqa: SLF001
                "UPDATE app_chat SET body = ? WHERE id = ?",
                (json.dumps(body, ensure_ascii=False), msg_id))
            store._conn.commit()  # noqa: SLF001

    def require_account(request: Request) -> dict | JSONResponse:
        from web.server import current_account
        account = current_account(request)
        if not account:
            return JSONResponse({"error": "nicht angemeldet"}, status_code=401)
        return account

    def setup_ready(account: dict) -> bool:
        user = store.get_user(uid_for(account))
        return bool(user and user.get("status") == "ready")

    def render_kwargs_for(account: dict) -> dict:
        """Wie bot.main.render_kwargs_for, nur ohne Telegram-Application."""
        if account.get("render_bg_path") and Path(account["render_bg_path"]).exists():
            return {"bg_path": account["render_bg_path"]}
        if is_admin(account) and background_available():
            return {}
        user_row = store.get_user(uid_for(account)) or {}
        return {"bg_color": user_row.get("render_color") or DEFAULT_BG_COLOR}

    def dry_run_active() -> bool:
        stored = store.kv_get("dry_run")
        return cfg.dry_run if stored is None else bool(stored)

    def draft_payload(draft: dict) -> dict:
        """Strukturierte Vorschau — das JSON-Gegenstück zu bot.main.build_preview."""
        listing = draft.get("listing") or {}
        price = draft.get("price")
        fee = None
        if price and draft.get("category_id"):
            try:
                fee = estimate_fee(draft.get("category_name"), float(str(price).replace(",", ".")),
                                   int(draft.get("quantity") or 1), business=bool(draft.get("business")))
                fee = fee if fee.get("applies") else None
            except (TypeError, ValueError):
                fee = None
        photos, originals, rendered = (draft.get("photos") or [],
                                       draft.get("original_photos") or [],
                                       draft.get("rendered_photos") or [])
        photo_info = []
        for i, p in enumerate(photos):
            exists = Path(p).exists()
            is_orig = bool(originals) and i < len(originals) and p == originals[i]
            has_render = (bool(rendered) and i < len(rendered) and bool(originals)
                          and i < len(originals) and rendered[i] != originals[i])
            url = f"/api/app/photo/{draft['id']}/{i}?f={Path(p).name}" if exists else None
            if not url and draft.get("image_urls") and i < len(draft["image_urls"]):
                url = draft["image_urls"][i]
            photo_info.append({"url": url, "is_original": is_orig, "has_render": has_render})
        desc_plain = re.sub(r"<[^>]+>", " ", listing.get("description_html", ""))
        desc_plain = re.sub(r"\s+", " ", desc_plain).strip()
        return {
            "id": draft["id"],
            "status": draft.get("status"),
            "error_text": draft.get("error_text"),
            "published": draft.get("status") == "published",
            "title": listing.get("title"),
            "category_id": draft.get("category_id"),
            "category_name": draft.get("category_name"),
            "condition": listing.get("condition"),
            "assumptions": listing.get("assumptions"),
            "usk": current_usk(draft),
            "show_usk": is_media_category(draft.get("category_name")) or current_usk(draft) is not None,
            "price": price,
            "price_basis": draft.get("price_basis"),
            "price_research": draft.get("price_research"),
            "format": draft.get("format", "FIXED_PRICE"),
            "auction_days": int(draft.get("auction_days") or 7),
            "quantity": int(draft.get("quantity") or 1),
            "best_offer": draft.get("best_offer"),
            "buyer_offers": draft.get("buyer_offers") or [],
            "fee": fee,
            "photos": photo_info,
            "description_plain": desc_plain,
            "item_url": draft.get("item_url"),
            "question": (listing.get("question")
                         if draft.get("status") == "uncertain" else None),
            "pending": draft.get("app_pending"),
        }

    def own_draft(draft_id: str, account: dict) -> dict | None:
        draft = store.get_draft(draft_id)
        if not draft or draft["chat_id"] != uid_for(account):
            return None
        return draft

    def latest_stage(account_id: int) -> dict | None:
        """Jüngste Status-Zeile des Kontos — als Fortschrittsanzeige im Item-Detail."""
        row = store._conn.execute(  # noqa: SLF001
            "SELECT body FROM app_chat WHERE account_id = ? AND kind = 'status' "
            "ORDER BY id DESC LIMIT 1", (account_id,)).fetchone()
        return json.loads(row["body"]) if row else None

    # ------------------------------------------------------------ Sammlung: Helfer

    def col_get(item_id: str, account: dict) -> dict | None:
        row = store._conn.execute(  # noqa: SLF001
            "SELECT * FROM collection_items WHERE id = ? AND account_id = ?",
            (item_id, account["id"])).fetchone()
        if not row:
            return None
        data = json.loads(row["data"])
        data["id"] = row["id"]
        data["created_at"] = row["created_at"]
        return data

    # ── Server-Push (Baustein 2): jede Änderung wird sofort an alle offenen
    # Geräte des Kontos gepusht. col_save ist das Schreib-Nadelöhr für Items.
    _subs: dict[int, dict] = {}   # Queue -> Verbindungszeit

    def notify(account_id: int, scope: str, obj_id: str | None = None) -> None:
        for q in list(_subs.get(account_id, ())):
            try:
                q.put_nowait({"scope": scope, "id": obj_id, "ts": time.time()})
            except asyncio.QueueFull:
                pass   # Client hängt — beim Reconnect lädt er eh voll nach

    def col_save(item_id: str, account_id: int, data: dict, *, create: bool = False) -> None:
        clean = {k: v for k, v in data.items() if k not in ("id", "created_at")}
        now = time.time()
        with store._lock:  # noqa: SLF001
            if create:
                store._conn.execute(  # noqa: SLF001
                    "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) "
                    "VALUES (?, ?, ?, ?, ?)", (item_id, account_id, now, now, json.dumps(clean)))
            else:
                store._conn.execute(  # noqa: SLF001
                    "UPDATE collection_items SET data = ?, updated_at = ? WHERE id = ? AND account_id = ?",
                    (json.dumps(clean), now, item_id, account_id))
            store._conn.commit()  # noqa: SLF001

        notify(account_id, "item", item_id)
    def _num(v, default=0.0) -> float:
        """Zahl aus gespeicherten Daten — NaN/Unendlich/Müll werden zu default.
        Ohne das legt ein einziger kaputter Wert die ganze Sammlung lahm
        (JSON kann kein NaN → HTTP 500 bei JEDEM Abruf)."""
        try:
            f = float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return default
        return f if math.isfinite(f) else default

    def col_all(account_id: int) -> list[dict]:
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT * FROM collection_items WHERE account_id = ? ORDER BY created_at DESC",
            (account_id,)).fetchall()
        out = []
        for r in rows:
            d = json.loads(r["data"])
            d["id"] = r["id"]
            d["created_at"] = r["created_at"]
            out.append(d)
        return out

    def aehnliches_stueck(account_id: int, item: dict) -> dict | None:
        """Gibt es dieses Produkt schon einmal in der Sammlung?

        Svens Wunsch: „Wenn ich ein Produkt hochlade, soll er erkennen, ob's
        dafür schon einen Entwurf gibt." Bewusst nur ein HINWEIS, kein
        automatisches Zusammenführen — Sammler besitzen Dubletten absichtlich
        (zwei gleiche Karten sind zwei Stücke), und ein falsch verschmolzenes
        Stück wäre schwer wieder auseinanderzunehmen.
        """
        def kennung(i: dict) -> tuple:
            """Fingerabdruck eines Stücks: die ersten bedeutsamen Wörter PLUS
            alle Zahlen. Die Zahlen sind entscheidend — „Glurak ex 199/165" und
            „Glurak ex 200/165" sind zwei verschiedene Karten, obwohl die
            ersten Wörter gleich sind."""
            n = re.sub(r"[^\w\s./]", " ", (i.get("name") or "").lower())
            woerter = [w for w in n.split() if len(w) > 1]
            zahlen = frozenset(re.findall(r"\d+(?:[./]\d+)*", n))
            return (tuple(woerter[:4]), zahlen)

        # „solo:" heißt: kein Katalog-Treffer, der Schlüssel ist für dieses eine
        # Stück erzeugt worden — als Vergleich taugt er nicht.
        eigen = (item.get("card_key") or "").strip()
        katalog = eigen if eigen and not eigen.startswith("solo:") else None
        meine = kennung(item)
        if not katalog and len(meine[0]) < 2:
            return None
        for anderer in col_all(account_id):
            if anderer["id"] == item.get("id") or anderer.get("sold_ts"):
                continue
            fremd = (anderer.get("card_key") or "").strip()
            if katalog and fremd == katalog:
                return anderer
            if kennung(anderer) == meine:
                return anderer
        return None

    def item_by_draft(account_id: int, draft_id: str) -> dict | None:
        for it in col_all(account_id):
            if it.get("draft_id") == draft_id:
                return it
        return None

    def melde_fehler(account_id: int, draft_id: str, text: str) -> None:
        """Ein eBay-Fehler muss am Stück sichtbar werden. Vorher stand er nur im
        Chat-Verlauf, den die App gar nicht abruft — für den Nutzer blieb das
        Stück ewig bei „wird gelistet" stehen, ohne dass irgendwo ein Grund stand."""
        draft = store.get_draft(draft_id)
        if draft:
            draft["error_text"] = text
            store.update_draft(draft_id, draft)
        it = item_by_draft(account_id, draft_id)
        if it:
            # NICHT status="error" setzen: das bedeutet in der Sammlung
            # „nicht erkannt" und würde dem Nutzer den falschen Fehler samt
            # falschem Knopf zeigen. Ein misslungenes Listing ist kein
            # misslungener Scan — die Karte ist einwandfrei erfasst.
            it["error"] = text
            col_save(it["id"], account_id, it)

    def loesche_fehler(account_id: int, draft_id: str) -> None:
        """Beim neuen Versuch die alte Fehlermeldung wegräumen."""
        draft = store.get_draft(draft_id)
        if draft and draft.get("error_text"):
            draft.pop("error_text", None)
            store.update_draft(draft_id, draft)
        it = item_by_draft(account_id, draft_id)
        if it and it.get("error"):
            it["error"] = None
            col_save(it["id"], account_id, it)

    def item_value(item: dict) -> float | None:
        v = item.get("est_value")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    THUMB_SIZES = {240, 480, 720, 1100}

    _MIME = {".png": "image/png", ".webp": "image/webp",
             ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

    def thumb_path(path: str, w: int) -> str:
        """Foto verkleinert ausliefern (einmalig erzeugt, dann von Platte) —
        iPhone-Fotos sind mehrere MB groß; ohne Thumbnails lädt die App spürbar."""
        if w not in THUMB_SIZES:
            return path
        p = Path(path)
        alpha = p.suffix.lower() == ".png"   # Cutouts sind transparente Bilder
        # Transparente Thumbs als WEBP statt PNG: gleiche Optik, 5-10× kleiner.
        # Ein 1,6-MB-PNG-Thumb wurde so zum 150-KB-WEBP — bei jedem Kachel-Load.
        tp = p.with_name(f"{p.stem}_w{w}{'.webp' if alpha else '.jpg'}")
        alt_png = p.with_name(f"{p.stem}_w{w}.png")
        if tp.exists():
            return str(tp)
        if alpha and alt_png.exists():
            return str(alt_png)              # Alt-Thumbs weiterverwenden, nicht doppeln
        try:
            from PIL import Image, ImageOps
            img = ImageOps.exif_transpose(Image.open(path))
            img = img.convert("RGBA" if alpha else "RGB")
            img.thumbnail((w, w * 2))
            if alpha:
                img.save(tp, "WEBP", quality=88, method=4)
            else:
                img.save(tp, "JPEG", quality=84)
            return str(tp)
        except Exception:  # noqa: BLE001
            return path

    def item_public(item: dict, account: dict) -> dict:
        photos = []
        for i, p in enumerate(item.get("photos") or []):
            if Path(p).exists():
                photos.append(f"/api/app/citem-photo/{item['id']}/{i}?f={Path(p).name}")
        for url in (item.get("remote_photos") or []):
            photos.append(url)
        draft_status = None
        item_url = None
        if item.get("draft_id"):
            draft = store.get_draft(item["draft_id"])
            if draft and draft["chat_id"] == uid_for(account):
                draft_status = draft.get("status")
                item_url = draft.get("item_url")
        return {
            "id": item["id"],
            "status": item.get("status", "ready"),
            "status_text": item.get("status_text"),
            "error": item.get("error"),
            "name": item.get("name") or "Wird analysiert …",
            "category": item.get("category") or "Sonstiges",
            "condition": item.get("condition"),
            "graded": item.get("graded"),
            "quantity": int(item.get("quantity") or 1),
            "purchase_price": item.get("purchase_price"),
            "est_value": item_value(item),
            "market": item.get("market"),
            # „sold" hieß hier zweimal etwas anderes — einmal die Verkaufsbelege,
            # einmal „ist verkauft". Der zweite Eintrag hat den ersten stumm
            # überschrieben, weshalb ein verkauftes Stück seine eigenen Belege
            # nie zu sehen bekam. Jetzt getrennt.
            "sold_comps": item.get("sold"),
            "card": item.get("card"),
            # Der ehrliche Anzeigezustand (Stufe 5) — bewusst in der LISTE:
            # zwei kurze Strings, die Kachel braucht sie fürs „~"
            "price_state": item.get("price_state"),
            "price_reason": item.get("price_reason"),
            "price_source": item.get("price_source"),
            "price_label": item.get("price_label"),
            "price_detail": item.get("price_detail"),
            "price_updated": item.get("price_updated"),
            "grading": item.get("grading"),
            "graded_market": item.get("graded_market"),
            "notes": item.get("notes"),
            "favorite": bool(item.get("favorite")),
            "wishlist": bool(item.get("wishlist")),
            "sold": bool(item.get("sold_ts")),
            "tags": item.get("tags") or [],
            "photos": photos,
            "draft_id": item.get("draft_id"),
            "draft_status": draft_status,
            "item_url": item_url,
            "created_at": item.get("created_at"),
        }

    # Felder, die nur die Detailansicht braucht: in der LISTE machten sie bei
    # großen Sammlungen über 80 % der Antwort aus — und die Liste wird bei jedem
    # Push neu geladen, auf jedem offenen Gerät.
    _DETAIL_ONLY = ("market", "sold_comps", "graded_market", "grading", "price_detail")

    def item_list_public(item: dict, account: dict) -> dict:
        out = item_public(item, account)
        for k in _DETAIL_ONLY:
            out.pop(k, None)
        c = item.get("card") or {}
        out["card"] = ({"image": c.get("image"), "set_name": c.get("set_name"),
                        "rarity": c.get("rarity"), "set_total": c.get("set_total"),
                        "number": c.get("number")} if c else None)
        return out

    def get_alert(item_id: str) -> dict | None:
        row = store._conn.execute(  # noqa: SLF001
            "SELECT * FROM price_alerts WHERE item_id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def check_alert(item: dict, account_id: int) -> None:
        """Nach jedem Preis-Refresh: Alarm auslösen, wenn die Schwelle gerissen wurde."""
        alert = get_alert(item["id"])
        value = item.get("est_value")
        if not alert or value is None or alert["triggered_at"]:
            return
        hit = (value >= alert["threshold"] if alert["direction"] == "above"
               else value <= alert["threshold"])
        if hit:
            with store._lock:  # noqa: SLF001
                store._conn.execute(  # noqa: SLF001
                    "UPDATE price_alerts SET triggered_at = ? WHERE item_id = ?",
                    (time.time(), item["id"]))
                store._conn.commit()  # noqa: SLF001

    def snapshot_price(item_id: str, account_id: int, value: float | None, source: str | None) -> None:
        """Wert-Snapshot für den Preisverlauf — max. einer pro 6 h und Item."""
        if value is None:
            return
        last = store._conn.execute(  # noqa: SLF001
            "SELECT ts, value FROM price_history WHERE item_id = ? ORDER BY ts DESC LIMIT 1",
            (item_id,)).fetchone()
        if last and time.time() - last["ts"] < 6 * 3600 and abs(last["value"] - value) < 0.005:
            return
        with store._lock:  # noqa: SLF001
            store._conn.execute(  # noqa: SLF001
                "INSERT INTO price_history (item_id, account_id, ts, value, source) VALUES (?, ?, ?, ?, ?)",
                (item_id, account_id, time.time(), float(value), source))
            store._conn.commit()  # noqa: SLF001

    def item_history(item_id: str, days: int = 30) -> list[dict]:
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT ts, value FROM price_history WHERE item_id = ? AND ts > ? ORDER BY ts",
            (item_id, time.time() - days * 86400)).fetchall()
        return [{"ts": r["ts"], "value": r["value"]} for r in rows]

    def portfolio_history(account_id: int, days: int = 30) -> list[dict]:
        """Sammlungswert pro Tag: letzter Snapshot je Item und Tag, vorwärts aufgefüllt."""
        import datetime
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT item_id, ts, value FROM price_history WHERE account_id = ? AND ts > ? ORDER BY ts",
            (account_id, time.time() - days * 86400)).fetchall()
        if not rows:
            return []
        account = store.get_account(account_id)
        live_draft_ids = set()
        if account:
            live_draft_ids = {r["id"] for r in store._conn.execute(  # noqa: SLF001
                "SELECT id FROM drafts WHERE chat_id = ? AND status = 'published'",
                (uid_for(account),)).fetchall()}
        qty = {i["id"]: int(i.get("quantity") or 1) for i in col_all(account_id)
               if not (i.get("draft_id") in live_draft_ids)}
        per_day: dict[str, dict[str, float]] = {}
        for r in rows:
            day = datetime.date.fromtimestamp(r["ts"]).isoformat()
            per_day.setdefault(day, {})[r["item_id"]] = r["value"]
        out, current = [], {}
        for day in sorted(per_day):
            current.update(per_day[day])
            total = sum(v * qty.get(iid, 1) for iid, v in current.items() if iid in qty)
            out.append({"day": day, "value": round(total, 2)})
        return out

    # Genau diese Felder darf der Preis-Vorgang überschreiben — alles andere
    # (Notizen, Menge, Kaufpreis, Favorit, draft_id, Status) gehört dem Nutzer.
    PREIS_FELDER = ("card", "card_key", "card_info", "est_value", "price_source",
                    "price_label", "price_detail", "market", "sold", "price_updated",
                    "price_state", "price_reason")

    # Was die Analyse überschreiben darf. Nutzerfelder (notes, quantity,
    # purchase_price, favorite, wishlist, tags, draft_id, sold_ts) stehen
    # bewusst in KEINER Liste — die gehören dem Nutzer, immer.
    ANALYSE_FELDER = PREIS_FELDER + ("status", "status_text", "error", "analysis",
                                     "photos", "photos_raw", "graded",
                                      "grading")
    NUR_WENN_LEER = ("name", "category", "condition")

    def col_save_analyse(item_id: str, account: dict, item: dict) -> dict | None:
        """Analyse-Stand sichern, ohne parallele Nutzer-Eingaben zu zerstören.
        Die Analyse dauert 30-90 s und speicherte ihr veraltetes Komplett-Bild
        SIEBEN Mal — wer währenddessen favorisierte oder den Kaufpreis eintrug,
        verlor das kommentarlos. Jetzt: frisch lesen, nur Analyse-Felder setzen."""
        frisch = col_get(item_id, account)
        if frisch is None:
            return None                    # während der Analyse gelöscht — so lassen
        for feld in ANALYSE_FELDER:
            if feld in item:
                frisch[feld] = item[feld]
        for feld in NUR_WENN_LEER:
            if not frisch.get(feld) and item.get(feld):
                frisch[feld] = item[feld]
        col_save(item_id, account["id"], frisch)
        item.clear()
        item.update(frisch)                # Analyse rechnet mit dem echten Stand weiter
        return item

    def setze_preiszustand(item: dict) -> None:
        """price_state (Stufe 5): der ehrliche Anzeigezustand neben est_value.

        belegt = echte Verkäufe oder Kartendatenbank · spanne = Richtwert aus
        Angeboten oder alten Belegen · unbekannt = kein tragfähiger Wert,
        Grund im geschlossenen Enum.

        Seit dem 07.08. (ADR-002) darf est_value auch None sein: ohne Belege
        gibt es keine Zahl mehr, und ein Rohkarten-Preis am Slab wird
        verworfen. Die Listing-Pipeline bekommt dann bewusst keine Preisbasis
        — der Nutzer trägt den Preis selbst ein, statt dass blind recherchiert
        wird (die alte 307,90-€-Regel gilt nur noch für BELEGTE Werte)."""
        src = item.get("price_source")
        ist_slab = bool((item.get("graded") or {}).get("grade"))
        _roh = ("cardmarket", "tcgplayer", "scryfall", "ygoprodeck", "tcgdex", "tcgcsv")
        if item.get("est_value") is None:
            zustand = ("unbekannt", "UNBEKANNT_KEINE_BELEGE")
        elif src == "ebay_sold":
            zustand = (("spanne", "BELEGE_ALT")
                       if (item.get("sold") or {}).get("stale") else ("belegt", None))
        elif src in _roh and ist_slab:
            # Selbsttest 03.08. + Review 07.08.: Der Rohpreis der UNGEGRADETEN
            # Karte ist am Slab um Größenordnungen falsch (CGC 10 für 0,06 €).
            # Ehrlich ist „unbekannt" — die Zahl wandert als Untergrenze ins
            # Detail statt in Portfolio, Preisalarm und Verlauf.
            item["price_detail"] = {**(item.get("price_detail") or {}),
                                    "rohwert_untergrenze": {"wert": item.get("est_value"),
                                                            "quelle": src}}
            item["est_value"] = None
            zustand = ("unbekannt", "ROHPREIS_SLAB")
        elif src in _roh + ("pricecharting",):
            # Kartendatenbank-Preise (Cardmarket direkt oder über Scryfall/
            # YGOPRODeck/TCGdex) sind BELEGTE Rohkarten-Preise — vorher fielen
            # scryfall/ygoprodeck in „unbekannt" und verloren den Listing-Preis.
            zustand = ("belegt", None)
        elif src in ("ebay", "ebay_eu"):
            zustand = ("spanne", "NUR_ANGEBOTE")
        elif src == "pricecharting_weak":
            zustand = ("unbekannt", "UNBEKANNT_ZUORDNUNG")
        else:
            zustand = ("unbekannt", "UNBEKANNT_KEINE_BELEGE")
        item["price_state"], item["price_reason"] = zustand

    def waechter_c(item: dict, research: dict | None) -> bool:
        """Unsichere PriceCharting-Zuordnung gegen den eBay-Markt prüfen.

        „weak" heißt: der Treffer passt nicht sauber zum Stück. Liegt so ein
        Wert um ein Vielfaches neben dem Markt, ist es fast immer ein anderes
        Produkt — Svens Manga Band 103 bekam 603 €, weil PriceCharting die
        SAMMELKARTE „Nami [Manga] OP01-016" fand. Seit Stufe 4 läuft der
        Wächter in BEIDEN Pfaden (Scan UND Refresh) und entgiftet die
        geteilte Katalogzeile gleich mit — vorher servierte die den Fehlwert
        jedem weiteren Nutzer bis zum TTL-Ablauf weiter."""
        if not (item.get("price_source") == "pricecharting_weak" and research
                and research.get("median") and item.get("est_value")):
            return False
        markt, pc_wert = research["median"], item["est_value"]
        if not (markt > 0 and (pc_wert > markt * 4 or pc_wert < markt / 4)):
            return False
        log.warning("Unsicherer PriceCharting-Wert verworfen: %.2f vs. Markt %.2f (%s)",
                    pc_wert, markt, (item.get("price_detail") or {}).get("pc_product", "?"))
        item["price_detail"] = {**(item.get("price_detail") or {}),
                                "verworfen_pc": pc_wert}
        item["est_value"] = markt
        item["price_source"] = "ebay"
        item["price_label"] = "eBay-Median (aktive Angebote)"
        ckey = item.get("card_key")
        if ckey and not str(ckey).startswith("solo:"):
            try:
                from web import catalog
                catalog.override_price(store, ckey,
                                       catalog.grade_bucket(item.get("graded")),
                                       markt, item["price_source"], item["price_label"],
                                       {"verworfen_pc": {"wert": pc_wert}})
            except Exception:  # noqa: BLE001
                log.exception("Katalog-Entgiftung fehlgeschlagen für %s", ckey)
        return True

    async def refresh_item_price(account: dict, item: dict, force: bool = False) -> bool:
        """Preis eines Items neu ziehen (Karten-DB, sonst eBay). True = Wert aktualisiert."""

        # Alt-Daten-Entgiftung (Audit P0.2): Werte, die noch aus der abgeschafften
        # KI-Preisspanne stammen (source=estimate), werden verworfen und das
        # Stück wird komplett neu bewertet — echte Quellen oder ehrlich unbekannt.
        if item.get("price_source") == "estimate":
            item["price_detail"] = {**(item.get("price_detail") or {}),
                                    "ki_schaetzung_verworfen": item.get("est_value")}
            item["est_value"] = None
            item["price_source"] = None
            item["price_label"] = None
        updated = False
        # Einmalige Identifikation nachholen (z. B. bei importierten Items)
        if not item.get("card_info") and item.get("analysis"):
            info = await identify_card(cfg.anthropic_api_key, item["analysis"], item.get("notes"))
            if info:
                item["card_info"] = info
        card_info = item.get("card_info")
        if card_info and card_info.get("single"):
            ci = dict(card_info)
            ci["set_hint"] = " ".join(x for x in [ci.get("set_hint"), item.get("name")] if x)
            src = await lookup_card_price(ci, store)
            from web import catalog as _cat_chk
            if src and _cat_chk.card_passt_zu_info(src.get("card"), card_info):
                item["card"] = src["card"]
                item["est_value"] = src["value"]
                item["price_source"] = src["source"]
                item["price_label"] = src["source_label"]
                item["price_detail"] = src["detail"]
                updated = True
            elif src:
                # DB-Treffer widerspricht Nummer/Set-Größe — nicht übernehmen
                # (sonst landet z. B. deutsches #013 unter japanisch #223).
                log.warning("Karten-DB-Treffer verworfen (passt nicht zu card_info): %s vs %s",
                            (src.get("card") or {}).get("ref_id"),
                            f"{card_info.get('name')} #{card_info.get('number')}")
                src = None
            elif item.get("price_source") == "tcgplayer":
                # Der lokale TCGplayer-Index liefert deterministisch — kein Treffer mehr
                # heißt: die alte Zuordnung war falsch. Verwerfen, eBay/Schätzung übernimmt.
                item["card"] = None
                item["price_detail"] = None
                item["price_source"] = None
                item["price_label"] = None
                item["est_value"] = None
        # Sticky-Fehl-Match entsorgen: alte card mit anderer Nummer als card_info
        # würde einen fremden card_key erzeugen (Charizard-Fall 07.08.: me02-013
        # vs. h:… für dieselbe JP-#223).
        try:
            from web import catalog as _cat_sticky
            if item.get("card") and card_info and not _cat_sticky.card_passt_zu_info(
                    item.get("card"), card_info):
                log.warning("Alte Karten-Zuordnung verworfen für %s: %s ≠ #%s",
                            item.get("id"), (item.get("card") or {}).get("ref_id"),
                            card_info.get("number"))
                item["card"] = None
        except Exception:  # noqa: BLE001
            pass
        # Globaler Preis-Katalog: EINE Karte, EIN Preis — geteilt über alle Items
        # und Nutzer. Extern wird nur bei abgelaufenem TTL (24 h) oder auf Svens
        # Refresh-Knopf (force) gefragt; sonst ist das ein reiner Datenbank-Read.
        try:
            from web import catalog
            from web.prices import usd_eur
            # Nur passende DB-Treffer dürfen den Schlüssel bestimmen — sonst
            # card_info (Hash), damit gleiche Identifikation denselben Preis teilt.
            _card_ok = (item.get("card")
                        if catalog.card_passt_zu_info(item.get("card"), card_info)
                        else None)
            card_ref = dict(_card_ok or card_info or {})
            # NICHT setdefault: card_info trägt oft {"name": null} — der
            # Schlüssel existiert dann, setdefault tut nichts, und card_key_of
            # sah keine Identität. Folge waren 239 Wegwerf-Schlüssel im
            # Katalog (Befund 03.08.) — jedes Stück zahlte jede Abfrage allein.
            if not card_ref.get("name"):
                card_ref["name"] = item.get("name")
            ckey = catalog.upsert_card(store, card_ref, solo_id=item.get("id"))
            item["card_key"] = ckey
            grade = catalog.grade_bucket(item.get("graded"))
            _lst = item.get("analysis") or {}
            base = ({"value": item.get("est_value"), "source": item.get("price_source"),
                     "label": item.get("price_label"), "detail": item.get("price_detail")}
                    if updated else None)
            from web.pricecharting import domain_of_item
            row = await catalog.refresh_price(
                store, ckey, grade, _lst.get("search_query_for_pricing") or item.get("name"),
                item.get("graded"), await usd_eur(), base=base, force=force,
                eu_probe=lambda q: research_price(ebay, q),
                domain=domain_of_item(item))
        except Exception:  # noqa: BLE001
            log.exception("Katalog-Refresh fehlgeschlagen für %s", item.get("id"))
            row = None
        if row and row.get("value_eur") is not None:
            item["est_value"] = row["value_eur"]
            item["price_source"] = row["source"]
            item["price_label"] = row["source_label"]
            det = row.get("detail") or {}
            if det.get("sold"):
                item["sold"] = det["sold"]
            if det.get("pc"):
                item["price_detail"] = {**(item.get("price_detail") or {}), **det["pc"]}
            if det.get("extra"):
                item["price_detail"] = {**(item.get("price_detail") or {}), **det["extra"]}
            updated = True

        # eBay-Vergleichsangebote immer mitziehen (Zweitmeinung + Beispiel-Links);
        # den Wert bestimmen sie nur, wenn keine bessere Quelle gegriffen hat.
        listing = item.get("analysis") or {}
        query = listing.get("search_query_for_pricing") or item.get("name")
        if query:
            research = comps_verwertbar(await research_price(ebay, query))
            # Kein verwertbarer Markt -> auch die ALTE market-Anzeige leeren;
            # sonst stehen KI-Spannen-Reste oder veraltete Mediane neben
            # einem ehrlichen „Wert unbekannt" (Review-Fund).
            item["market"] = ({k: research.get(k)
                               for k in ("count", "min", "max", "median", "samples")}
                              if research else None)
            if waechter_c(item, research):
                updated = True
            if not updated and research:
                item["est_value"] = research.get("median")
                item["price_source"] = "ebay"
                item["price_label"] = "eBay-Median (aktive Angebote)"
                updated = True
        setze_preiszustand(item)
        item["price_updated"] = time.time()
        # Zwischen Einlesen und Schreiben liegen hier Netz-Abfragen, oft Minuten.
        # Wer in der Zwischenzeit den Preis geändert, das Stück gelistet oder
        # umbenannt hat, verlor das bisher lautlos: der alte Stand wurde komplett
        # zurückgeschrieben. Deshalb frisch lesen und nur die Preis-Felder setzen,
        # für die dieser Vorgang zuständig ist.
        frisch = col_get(item["id"], account)
        if frisch is None:
            return updated              # in der Zwischenzeit gelöscht — nicht wiederbeleben
        for feld in PREIS_FELDER:
            if feld in item:
                frisch[feld] = item[feld]
        col_save(item["id"], account["id"], frisch)
        item.clear()
        item.update(frisch)             # Aufrufer arbeitet mit dem echten Stand weiter
        snapshot_price(item["id"], account["id"], item.get("est_value"), item.get("price_source"))
        check_alert(item, account["id"])
        return updated

    async def analyze_collection_item(account: dict, item_id: str) -> None:
        """Claude-Analyse + Preisrecherche für ein neues Sammlungsstück."""
        item = col_get(item_id, account)
        if not item:
            return
        try:
            _orig_photos = list(item.get("photos") or [])
            _listing_task = asyncio.create_task(
                analyzer.analyze(_orig_photos, item.get("notes")))
            try:
                # Karte freistellen: Slab bleibt mit Case, aus Hülle/Toploader nur die Karte
                if not item.get("photos_raw"):
                    item["status_text"] = "Stelle Karte frei …"
                    if col_save_analyse(item_id, account, item) is None:
                        return
                    try:
                        from web import cardscan
                        cropped, cinfo = await cardscan.crop_photos(
                            cfg.anthropic_api_key, item.get("photos") or [])
                        if cinfo["cropped"]:
                            item["photos_raw"] = list(item.get("photos") or [])
                            item["photos"] = cropped
                            if col_save_analyse(item_id, account, item) is None:
                                return
                    except Exception:  # noqa: BLE001 — Freisteller darf den Scan nie blockieren
                        log.exception("Freistellen fehlgeschlagen für %s", item_id)
                item["status_text"] = "Erkenne Karte …"
                if col_save_analyse(item_id, account, item) is None:
                    return
            finally:
                # Full-Scan-Befund 03.08.: Bei den frühen Returns (Stück in der
                # Zwischenzeit gelöscht) lief die Claude-Analyse verwaist weiter
                # — bezahlte Arbeit für den Papierkorb.
                if col_get(item_id, account) is None and not _listing_task.done():
                    _listing_task.cancel()
            listing = await _listing_task
            listing.pop("uncertain", None)
            title = listing.get("title") or item.get("name") or "Unbenannt"
            item["name"] = item.get("name") or title
            item["condition"] = item.get("condition") or listing.get("condition")
            if listing.get("graded_info"):
                from web.slab import normalize_graded
                item["graded"] = normalize_graded(listing["graded_info"]) or listing["graded_info"]
                # Slab-Garantie: Cutout mit Case-Ecken wiederholen, falls der
                # Segmentierer nur die innere Karte erwischt hat — ODER (häufiger
                # auf Holztischen) RemBG Tisch+Slab als „Objekt" behält und der
                # Flächenvergleich die Rettung blockiert (Sven CGC 07.08.).
                # Deshalb: bei erkanntem Grading IMMER Warp versuchen; ein
                # erfolgreicher Warp ersetzt den Zuschnitt.
                def _zuschnitt_anteil(cur_p: str, raw_p: str) -> float:
                    """Objektfläche des Zuschnitts als Anteil am Rohbild — auf
                    derselben 2000er-Arbeitsgröße, in der der Freisteller
                    rechnet, damit der Vergleich mit den Case-Ecken stimmt."""
                    try:
                        import numpy as _np
                        from PIL import Image as _I
                        with _I.open(raw_p) as roh:
                            rw, rh = roh.size
                        s = min(1.0, 2000 / max(rw, rh))
                        basis = (rw * s) * (rh * s)
                        with _I.open(cur_p) as im:
                            if im.mode != "RGBA":
                                return 0.0   # kein Zuschnitt da — Warp lohnt immer
                            a = _np.array(im.split()[3])
                        return float((a > 8).sum()) / max(basis, 1.0)
                    except Exception:  # noqa: BLE001
                        return 0.0

                def _tischnachbar(cur_p: str) -> bool:
                    """Opaker Bildrand in Tischfarbe? RemBG hat den Untergrund
                    mitgenommen — Warp muss ersetzen, egal wie groß die Fläche."""
                    try:
                        import numpy as _np
                        from PIL import Image as _I
                        with _I.open(cur_p) as im:
                            if im.mode != "RGBA":
                                return True
                            a = _np.asarray(im)
                        H, W = a.shape[:2]
                        by, bx = max(4, H // 12), max(4, W // 12)
                        ring = _np.zeros(H * W, dtype=bool).reshape(H, W)
                        ring[:by, :] = True
                        ring[-by:, :] = True
                        ring[:, :bx] = True
                        ring[:, -bx:] = True
                        mask = (a[:, :, 3] > 8) & ring
                        if mask.mean() < 0.15:
                            return False
                        rgb = a[:, :, :3][mask].astype(_np.float32).mean(axis=0)
                        # Studio-Weiß / hellgrau = ok; braun/grau-Tisch = Rettung
                        return not (rgb.min() > 200 or (rgb.mean() > 210 and rgb.std() < 25))
                    except Exception:  # noqa: BLE001
                        return False

                roh = item.get("photos_raw") or item.get("photos") or []
                if roh:
                    from web import cardscan as _cs
                    pairs = list(zip(roh, item.get("photos") or roh))[:2]

                    async def _one_slab(raw_p, cur_p):
                        outp = str(Path(raw_p).with_name(Path(raw_p).stem + "_slab.png"))
                        # Tischrand oder kein sauberer Cutout → min_area 0 (immer ersetzen)
                        min_frac = 0.0 if _tischnachbar(cur_p) else (
                            _zuschnitt_anteil(cur_p, raw_p) * 1.35)
                        try:
                            # Warp-only: rembg frisst klares Case-Plastik
                            # (Label+Karte schweben getrennt — Sven 07.08.).
                            if (await _cs.slab_recut(
                                cfg.anthropic_api_key, raw_p, outp,
                                min_area_frac=min_frac,
                            ) and _cs.bild_ok(outp, "slab")):
                                return outp
                            return cur_p
                        except Exception:  # noqa: BLE001
                            return cur_p

                    fixed = list(await asyncio.gather(
                        *(_one_slab(rp, cp) for rp, cp in pairs)))
                    if any(f.endswith("_slab.png") for f in fixed):
                        rest = list(item.get("photos") or roh)[len(fixed):]
                        item.setdefault("photos_raw", list(roh))
                        item["photos"] = fixed + rest
                # Pristine/Perfect im Anzeigenamen, falls der alte Name es nicht trägt
                from web.slab import label_display as _ld
                _wort = _ld((item.get("graded") or {}).get("label_type")) or ""
                if (_wort and _wort != "Gem Mint"
                        and _wort.lower() not in (item.get("name") or "").lower()
                        and listing.get("title")
                        and _wort.lower() in listing["title"].lower()):
                    item["name"] = listing["title"]
            item["category"] = (item.get("category")
                                or guess_category(title, listing.get("category_query", ""),
                                                  str(listing.get("aspects") or "")))
            item["analysis"] = listing

            # 1) Einzelkarte? -> echte Karten-Datenbanken (Cardmarket-Preise)
            item["status_text"] = "Suche in Karten-Datenbanken …"
            if col_save_analyse(item_id, account, item) is None:
                return
            card_info = await identify_card(cfg.anthropic_api_key, listing, item.get("notes"))
            if card_info:
                item["card_info"] = card_info
            src = None
            if card_info:
                ci = dict(card_info)
                ci["set_hint"] = " ".join(x for x in [ci.get("set_hint"), title] if x)
                src = await lookup_card_price(ci, store)
                from web import catalog as _cat_an
                if src and not _cat_an.card_passt_zu_info(src.get("card"), card_info):
                    log.warning("Analyse: Karten-DB-Treffer verworfen (%s ≠ #%s)",
                                (src.get("card") or {}).get("ref_id"),
                                card_info.get("number"))
                    src = None
            if src:
                item["card"] = src["card"]
                item["est_value"] = src["value"]
                item["price_source"] = src["source"]
                item["price_label"] = src["source_label"]
                item["price_detail"] = src["detail"]
            elif item.get("card") and card_info:
                from web import catalog as _cat_clr
                if not _cat_clr.card_passt_zu_info(item.get("card"), card_info):
                    item["card"] = None

            # 2) eBay-Vergleichsangebote (als Zweitmeinung bzw. Fallback)
            item["status_text"] = "Recherchiere eBay-Angebote …"
            if col_save_analyse(item_id, account, item) is None:
                return
            research = comps_verwertbar(
                await research_price(ebay, listing.get("search_query_for_pricing") or title))
            item["market"] = ({k: research.get(k)
                               for k in ("count", "min", "max", "median", "samples")}
                              if research else None)
            # KEIN Rückfall auf eine KI-Preisspanne mehr (Audit P0.2, ADR-002):
            # ohne Karten-DB-Treffer, Katalogzeile oder >=3 Vergleichsangebote
            # bleibt est_value leer und das Stück zeigt ehrlich „Wert unbekannt".
            if not src and research:
                item["est_value"] = research.get("median")
                item["price_source"] = "ebay"
                item["price_label"] = "eBay-Median (aktive Angebote)"

            # Globaler Preis-Katalog: hat IRGENDWER diese Karte schon, ist der Preis
            # sofort da (Datenbank-Read) — sonst holt der Katalog ihn EINMAL für alle.
            item["status_text"] = "Hole Marktpreis …"
            if col_save_analyse(item_id, account, item) is None:
                return
            try:
                from web import catalog
                from web.prices import usd_eur
                _cinfo = item.get("card_info")
                _card_ok = (item.get("card")
                            if catalog.card_passt_zu_info(item.get("card"), _cinfo)
                            else None)
                card_ref = dict(_card_ok or _cinfo or {})
                # NICHT setdefault — card_info liefert oft {"name": null},
                # siehe refresh_item_price (Befund 03.08.)
                if not card_ref.get("name"):
                    card_ref["name"] = item.get("name") or title
                ckey = catalog.upsert_card(store, card_ref, solo_id=item_id)
                item["card_key"] = ckey
                if item.get("price_source") == "estimate":
                    item["est_value"] = None
                    item["price_source"] = None
                    item["price_label"] = None
                base = ({"value": item.get("est_value"), "source": item.get("price_source"),
                         "label": item.get("price_label"), "detail": item.get("price_detail")}
                        if item.get("est_value") is not None else None)
                from web.pricecharting import domain_of_item
                row = await catalog.refresh_price(
                    store, ckey, catalog.grade_bucket(item.get("graded")),
                    listing.get("search_query_for_pricing") or title,
                    item.get("graded"), await usd_eur(), base=base,
                    eu_probe=lambda q: research_price(ebay, q),
                    domain=domain_of_item(item))
            except Exception:  # noqa: BLE001
                log.exception("Katalog fehlgeschlagen für %s", item_id)
                row = None
            if row and row.get("value_eur") is not None:
                item["est_value"] = row["value_eur"]
                item["price_source"] = row["source"]
                item["price_label"] = row["source_label"]
                det = row.get("detail") or {}
                if det.get("sold"):
                    item["sold"] = det["sold"]
                if det.get("pc"):
                    item["price_detail"] = {**(item.get("price_detail") or {}), **det["pc"]}

            # Wächter C auch beim ERSTEN Scan — dem einzigen Lauf, den der
            # Nutzer live sieht. Bis Stufe 4 lief er nur beim Refresh.
            waechter_c(item, research)
            setze_preiszustand(item)

            item["status"] = "ready"
            item["status_text"] = None
            item["error"] = None
            item.pop("wartet_seit", None)
            item["price_updated"] = time.time()
            from web import health
            health.melde("ki", None)          # Quelle antwortet — Zustand grün
            if col_save_analyse(item_id, account, item) is None:
                return
            snapshot_price(item_id, account["id"], item.get("est_value"), item.get("price_source"))
        except Exception as e:  # noqa: BLE001 — Item bleibt bearbeitbar, Fehler sichtbar
            from web import health
            grund = health.melde("ki", e)
            item = col_get(item_id, account) or item
            item["status_text"] = None
            if grund:
                # INFRASTRUKTUR (Guthaben, Überlast, Netz): Nicht das Stück ist
                # schuld — es WARTET. Sobald die Quelle wieder da ist, nimmt der
                # Rettungsdienst es von selbst auf. Svens Auftrag vom 04.08.:
                # „ein festes, autonomes System, das immer gleich gut läuft."
                log.warning("Analyse pausiert für %s — %s", item_id, grund)
                item["status"] = "waiting"
                item["wartet_seit"] = item.get("wartet_seit") or time.time()
                item["error"] = health.GRUND_TEXTE.get(grund)
            else:
                log.exception("Sammlungs-Analyse fehlgeschlagen für %s", item_id)
                item["status"] = "error"
                item.pop("wartet_seit", None)
                item["error"] = (f"Analyse fehlgeschlagen: {type(e).__name__}. "
                                 "Du kannst alles manuell eintragen.")
            if col_save_analyse(item_id, account, item) is None:
                return

    # ------------------------------------------------------------ Pipeline (Portierung von run_pipeline)

    async def app_run_pipeline(account: dict, draft_id: str, preset_listing: dict | None = None,
                               market: dict | None = None) -> None:
        aid = account["id"]
        draft = store.get_draft(draft_id)
        if not draft:
            return
        status_id = chat_add(aid, "bot", "status", {"text": "Analysiere Fotos …", "done": False})
        try:
            if preset_listing:
                # Analyse liegt schon vor (Sammlungs-Item) — direkt zu Kategorie/Preis
                listing = dict(preset_listing)
                listing.pop("uncertain", None)
                listing.pop("question", None)
            else:
                listing = await analyzer.analyze(
                    draft.get("original_photos") or draft["photos"], draft.get("caption"))
            if market:
                # Belegter Marktwert/Vorlagen-Preis gilt auch, wenn die Pipeline
                # selbst analysiert hat — sonst greift die Preisregel ins Leere
                listing.update({k: v for k, v in market.items() if v})

            if listing.get("uncertain") and listing.get("question"):
                draft["status"] = "uncertain"
                draft["listing"] = listing
                store.update_draft(draft_id, draft)
                chat_set(status_id, {"text": "Analyse abgeschlossen", "done": True})
                chat_add(aid, "bot", "question",
                         {"text": listing["question"], "draft_id": draft_id,
                          "hint": "Antworte unten im Chat — ich generiere den Entwurf dann neu."})
                return

            reordered = reorder_photos(draft["photos"], listing.get("main_image_index"))
            if reordered != draft["photos"]:
                mi = listing.get("main_image_index")
                draft["photos"] = reordered
                if draft.get("original_photos"):
                    draft["original_photos"] = reorder_photos(draft["original_photos"], mi)
                if draft.get("rendered_photos"):
                    draft["rendered_photos"] = reorder_photos(draft["rendered_photos"], mi)
                draft["image_urls"] = None

            chat_set(status_id, {"text": "Suche Kategorie & Pflichtfelder …", "done": False})
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

            chat_set(status_id, {"text": "Recherchiere Preise …", "done": False})
            price_research = await research_price(ebay, listing["search_query_for_pricing"])
            draft["price_research"] = comps_verwertbar(price_research)
            draft["format"] = (listing.get("format")
                               if listing.get("format") in ("FIXED_PRICE", "AUCTION") else "FIXED_PRICE")
            try:
                draft["quantity"] = max(1, min(int(listing.get("quantity") or 1), 1000))
            except (TypeError, ValueError):
                draft["quantity"] = 1
            try:
                days = int(listing.get("auction_days") or 7)
            except (TypeError, ValueError):
                days = 7
            draft["auction_days"] = days if days in AUCTION_DURATIONS else 7
            best_offer = listing.get("best_offer")
            draft["best_offer"] = None
            if isinstance(best_offer, dict) and best_offer.get("enabled"):
                min_price = (parse_price(str(best_offer.get("min_price")))
                             if best_offer.get("min_price") else None)
                draft["best_offer"] = {"enabled": True, "min_price": min_price}
            draft["listing"] = listing
            apply_price_rule(draft)

            draft["status"] = "ready"
            store.update_draft(draft_id, draft)
            chat_set(status_id, {"text": "Entwurf fertig", "done": True})
            chat_add(aid, "bot", "preview", {"draft_id": draft_id})

        except (ClaudeError, TaxonomyError, EbayAuthError) as e:
            log.exception("App-Pipeline-Fehler für Draft %s", draft_id)
            draft["status"] = "error"
            store.update_draft(draft_id, draft)
            chat_set(status_id, {"text": "Analyse fehlgeschlagen", "done": True})
            chat_add(aid, "bot", "error",
                     {"text": f"Fehler bei der Analyse:\n{e}", "draft_id": draft_id, "retryable": True})
            melde_fehler(aid, draft_id, str(e))
        except Exception as e:  # noqa: BLE001 — alles muss im Chat landen, nie nur im Log
            log.exception("Unerwarteter App-Pipeline-Fehler für Draft %s", draft_id)
            chat_set(status_id, {"text": "Fehler", "done": True})
            chat_add(aid, "bot", "error", {"text": f"Unerwarteter Fehler: {type(e).__name__}: {e}"})

    # ------------------------------------------------------------ Upload (Portierung von run_upload)

    async def app_run_upload(account: dict, draft_id: str) -> None:
        aid = account["id"]
        user_id = uid_for(account)
        draft = store.get_draft(draft_id)
        if not draft:
            chat_add(aid, "bot", "error", {"text": "Draft nicht mehr vorhanden."})
            return
        policies = store.user_policies(user_id)
        if not policies:
            chat_add(aid, "bot", "error",
                     {"text": "Dein eBay-Setup ist unvollständig — tippe im Profil auf "
                              "„Setup“ und trag deine Versandadresse ein."})
            return

        listing = draft["listing"]
        if draft.get("status") == "published":
            return              # schon live — ein zweiter Lauf würde doppelt listen
        # Atomarer Claim: von hier bis zum finally darf nur EIN Lauf existieren.
        # Ohne ihn erzeugt ein Doppeltipp auf „Listen" zwei parallele Tasks und
        # damit zwei eBay-Listings derselben Karte (Audit-Befund P0.4).
        status_vorher = draft.get("status") or "ready"
        if not store.claim_draft(draft_id, "publishing",
                                 verboten=("publishing", "published", "ended")):
            aktuell = (store.get_draft(draft_id) or {}).get("status")
            if aktuell == "publishing":
                chat_add(aid, "bot", "info",
                         {"text": "Der Upload läuft bereits — einen Moment."})
            return
        draft["status"] = "publishing"   # lokal mitziehen, damit Zwischenspeicherungen
        loesche_fehler(aid, draft_id)    # den Claim nicht wieder überschreiben
        status_id = chat_add(aid, "bot", "status", {"text": "Lade Bilder zu eBay hoch …", "done": False})
        try:
            pfade = [p for p in (draft.get("photos") or []) if Path(p).exists()]
            if not pfade and not draft.get("image_urls"):
                chat_set(status_id, {"text": "Fehler", "done": True})
                chat_add(aid, "bot", "error",
                         {"text": "eBay verlangt mindestens ein Foto — bitte ein Bild "
                                  "hinzufügen.", "draft_id": draft_id})
                melde_fehler(aid, draft_id, "Kein Foto vorhanden — bitte eins hinzufügen.")
                return
            image_urls = draft.get("image_urls") or []
            if len(image_urls) < len(pfade):
                # Ab dort weitermachen, wo der letzte Versuch stand: jede fertige
                # URL wird SOFORT gespeichert. Vorher warf ein Abbruch beim vierten
                # Bild alle drei schon hochgeladenen weg.
                for i, path in enumerate(pfade[len(image_urls):], len(image_urls) + 1):
                    chat_set(status_id, {"text": f"Lade Bild {i}/{len(pfade)} hoch …",
                                         "done": False})
                    image_urls.append(await upload_image(ebay, path, user_id))
                    draft["image_urls"] = image_urls
                    store.update_draft(draft_id, draft)

            sku = draft.get("sku") or generate_sku()
            draft["sku"] = sku
            store.update_draft(draft_id, draft)

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
            condition, adjusted = resolve_condition(
                listing["condition"], allowed, item_text,
                is_graded=bool(listing.get("graded_info")))
            if adjusted:
                listing["condition"] = condition
                draft["listing"] = listing
                store.update_draft(draft_id, draft)
                chat_add(aid, "bot", "info",
                         {"text": f"Zustand angepasst auf {condition} — die Kategorie erlaubt den "
                                  "ursprünglichen Zustand nicht."})

            descriptors, frage = build_condition_descriptors(listing["condition"], policy,
                                                             listing, item_text)
            if frage:
                draft["app_pending"] = "graded"
                store.update_draft(draft_id, draft)
                chat_set(status_id, {"text": "Angaben fehlen", "done": True})
                chat_add(aid, "bot", "question",
                         {"text": frage, "draft_id": draft_id,
                          "hint": "Beispiel: PSA 9.5 12345678 — danach lade ich automatisch hoch."})
                return

            quantity = 1 if draft.get("format") == "AUCTION" else int(draft.get("quantity") or 1)

            chat_set(status_id, {"text": "Lege Inventory Item an …", "done": False})
            await create_inventory_item(
                ebay, sku, user_id=user_id,
                title=listing["title"], description=listing["description_html"],
                condition=listing["condition"],
                condition_description=listing.get("condition_description"),
                aspects=listing.get("aspects") or {}, image_urls=image_urls,
                condition_descriptors=descriptors, quantity=quantity)

            if draft.get("offer_id"):
                chat_set(status_id, {"text": "Aktualisiere bestehendes Offer …", "done": False})
                offer_id = draft["offer_id"]
                await update_offer(
                    ebay, policies, offer_id, sku, user_id=user_id,
                    category_id=draft["category_id"], price_eur=draft["price"],
                    listing_description=listing["description_html"],
                    listing_format=draft.get("format", "FIXED_PRICE"), quantity=quantity,
                    best_offer=draft.get("best_offer"),
                    auction_days=int(draft.get("auction_days") or 7),
                    title=listing.get("title"))
            else:
                chat_set(status_id, {"text": "Erstelle Offer …", "done": False})
                offer_id = await create_offer(
                    ebay, policies, sku, user_id=user_id,
                    category_id=draft["category_id"], price_eur=draft["price"],
                    listing_description=listing["description_html"],
                    listing_format=draft.get("format", "FIXED_PRICE"), quantity=quantity,
                    best_offer=draft.get("best_offer"),
                    auction_days=int(draft.get("auction_days") or 7),
                    title=listing.get("title"))
                draft["offer_id"] = offer_id
                store.update_draft(draft_id, draft)

            if dry_run_active():
                store.log_listing(sku, listing["title"], draft["price"], offer_id, None,
                                  dry_run=True, telegram_id=user_id)
                draft["status"] = "dry_run_done"
                store.update_draft(draft_id, draft)
                chat_set(status_id, {"text": "Dry-Run abgeschlossen", "done": True})
                chat_add(aid, "bot", "info",
                         {"text": f"🧪 DRY RUN: Alles bis auf publishOffer erledigt.\n"
                                  f"SKU: {sku} · Offer: {offer_id}"})
                return

            chat_set(status_id, {"text": "Veröffentliche Listing …", "done": False})
            listing_id = await publish_offer(ebay, offer_id, user_id)
            store.log_listing(sku, listing["title"], draft["price"], offer_id, listing_id,
                              dry_run=False, telegram_id=user_id)
            draft["status"] = "published"
            draft["listing_id"] = listing_id
            draft["item_url"] = f"https://www.ebay.de/itm/{listing_id}"
            store.update_draft(draft_id, draft)
            chat_set(status_id, {"text": "Veröffentlicht", "done": True})
            chat_add(aid, "bot", "published",
                     {"draft_id": draft_id, "title": listing["title"],
                      "price": draft["price"], "item_url": draft["item_url"]})

        except (MediaError, InventoryError, EbayAuthError, EbayTimeout) as e:
            log.exception("App-Upload-Fehler für Draft %s", draft_id)
            m = re.search(r"([A-ZÄÖÜ][\w\säöüß/-]*?) darf nur einen Wert", str(e))
            if m:
                name = m.group(1).strip()
                aspects = (draft.get("listing") or {}).get("aspects") or {}
                if isinstance(aspects.get(name), list) and len(aspects[name]) > 1:
                    aspects[name] = aspects[name][:1]
                    draft["listing"]["aspects"] = aspects
                    store.update_draft(draft_id, draft)
                    chat_set(status_id, {"text": "Korrigiert", "done": True})
                    chat_add(aid, "bot", "info",
                             {"text": f"„{name}“ erlaubt nur einen Wert — habe ich korrigiert. "
                                      "Einfach erneut auf Hochladen tippen.", "draft_id": draft_id})
                    return
            chat_set(status_id, {"text": "eBay-Fehler", "done": True})
            chat_add(aid, "bot", "error",
                     {"text": f"eBay-Fehler:\n{e}", "draft_id": draft_id, "retryable": True})
            melde_fehler(aid, draft_id, str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("Unerwarteter App-Upload-Fehler für Draft %s", draft_id)
            chat_set(status_id, {"text": "Fehler", "done": True})
            chat_add(aid, "bot", "error", {"text": f"Unerwarteter Fehler: {type(e).__name__}: {e}"})
            melde_fehler(aid, draft_id,
                         "Beim Listen ist etwas schiefgegangen. Versuch es noch einmal.")
        finally:
            # Claim lösen, falls kein Endzustand erreicht wurde (Fehler, Rückfrage,
            # fehlendes Foto) — sonst bliebe der Entwurf für immer „publishing".
            store.release_draft_claim(draft_id, status_vorher)

    # ------------------------------------------------------------ Live-Update (Portierung von run_update)

    async def app_run_update(account: dict, draft_id: str) -> None:
        aid = account["id"]
        user_id = uid_for(account)
        draft = store.get_draft(draft_id)
        if not draft or not draft.get("offer_id"):
            chat_add(aid, "bot", "error", {"text": "Listing nicht mehr auffindbar."})
            return
        policies = store.user_policies(user_id)
        listing = draft["listing"]
        if not policies:
            # OHNE diesen frühen Abbruch liefe create_inventory_item zuerst durch
            # (Titel/Bilder/Zustand wären auf eBay schon geändert) und erst
            # update_offer würde krachen — ein halb geändertes Live-Listing.
            text = ("Dein eBay-Setup ist unvollständig (Versand-/Zahlungs-/"
                    "Rücknahmerichtlinie oder Standort fehlt). Bitte einmal neu "
                    "einrichten — das Listing wurde NICHT verändert.")
            chat_add(aid, "bot", "error", {"text": text, "draft_id": draft_id})
            melde_fehler(aid, draft_id, text)
            return
        status_id = chat_add(aid, "bot", "status", {"text": "Aktualisiere Listing …", "done": False})
        try:
            image_urls = draft.get("image_urls")
            if not image_urls:
                existing = [p for p in draft["photos"] if Path(p).exists()]
                if existing:
                    image_urls = []
                    for i, path in enumerate(existing, 1):
                        chat_set(status_id, {"text": f"Lade Bild {i}/{len(existing)} hoch …",
                                             "done": False})
                        image_urls.append(await upload_image(ebay, path, user_id))
                        # Teilerfolg sofort sichern — ein Abbruch wirft sonst alles weg
                        draft["image_urls"] = image_urls
                        store.update_draft(draft_id, draft)
                else:
                    inv = await get_inventory_item(ebay, draft["sku"], user_id)
                    image_urls = ((inv or {}).get("product") or {}).get("imageUrls") or []
                    if not image_urls:
                        chat_set(status_id, {"text": "Fehler", "done": True})
                        chat_add(aid, "bot", "error",
                                 {"text": "Keine Bilder auffindbar — bitte Listing neu erstellen."})
                        return
                draft["image_urls"] = image_urls
                store.update_draft(draft_id, draft)

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
                draft["app_pending"] = "graded_update"
                store.update_draft(draft_id, draft)
                chat_set(status_id, {"text": "Angaben fehlen", "done": True})
                chat_add(aid, "bot", "question", {"text": frage, "draft_id": draft_id})
                return
            quantity = 1 if draft.get("format") == "AUCTION" else int(draft.get("quantity") or 1)

            chat_set(status_id, {"text": "Aktualisiere Artikeldaten …", "done": False})
            await create_inventory_item(
                ebay, draft["sku"], user_id=user_id,
                title=listing["title"], description=listing["description_html"],
                condition=condition, condition_description=listing.get("condition_description"),
                aspects=listing.get("aspects") or {}, image_urls=image_urls,
                condition_descriptors=descriptors, quantity=quantity)
            chat_set(status_id, {"text": "Aktualisiere Preis & Angebot …", "done": False})
            await update_offer(
                ebay, policies, draft["offer_id"], draft["sku"], user_id=user_id,
                category_id=draft["category_id"], price_eur=draft["price"],
                listing_description=listing["description_html"],
                listing_format=draft.get("format", "FIXED_PRICE"),
                quantity=quantity, best_offer=draft.get("best_offer"),
                auction_days=int(draft.get("auction_days") or 7),
                    title=listing.get("title"))
            # Frisch lesen — Sync kann inzwischen Felder gesetzt haben.
            frisch = store.get_draft(draft_id) or draft
            frisch["price"] = draft.get("price")
            frisch.pop("price_dirty", None)
            frisch["ebay_price"] = draft.get("price")
            store.update_draft(draft_id, frisch)
            chat_set(status_id, {"text": "Änderungen sind live", "done": True})
            chat_add(aid, "bot", "published",
                     {"draft_id": draft_id, "title": listing["title"], "price": draft["price"],
                      "item_url": draft.get("item_url"), "updated": True})
        except (MediaError, InventoryError, EbayAuthError, EbayTimeout) as e:
            log.exception("App-Update-Fehler für Listing %s", draft_id)
            chat_set(status_id, {"text": "eBay-Fehler", "done": True})
            chat_add(aid, "bot", "error",
                     {"text": f"eBay-Fehler beim Aktualisieren:\n{e}\n\nTipp: Das Format "
                              "(Auktion↔Festpreis) lässt sich bei laufenden Listings oft nicht "
                              "ändern — dafür beenden und neu einstellen.", "draft_id": draft_id})
            melde_fehler(aid, draft_id, f"Aktualisieren fehlgeschlagen: {e}")
        except Exception as e:  # noqa: BLE001
            log.exception("Unerwarteter App-Update-Fehler für Listing %s", draft_id)
            chat_set(status_id, {"text": "Fehler", "done": True})
            chat_add(aid, "bot", "error", {"text": f"Unerwarteter Fehler: {type(e).__name__}: {e}"})
            melde_fehler(aid, draft_id,
                         "Beim Aktualisieren ist etwas schiefgegangen. Versuch es noch einmal.")

    # ------------------------------------------------------------ Endpunkte

    @router.get("/draft/{draft_id}")
    async def get_draft(request: Request, draft_id: str):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        draft = own_draft(draft_id, account)
        if not draft:
            return JSONResponse({"error": "Draft existiert nicht mehr."}, status_code=404)
        payload = draft_payload(draft)
        payload["stage"] = latest_stage(account["id"])
        return payload

    @router.post("/draft/{draft_id}/action")
    async def draft_action(request: Request, draft_id: str, body: ActionBody):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        draft = own_draft(draft_id, account)
        if not draft:
            return JSONResponse({"error": "Draft existiert nicht mehr."}, status_code=404)
        action, value = body.action, (body.value or "").strip()
        published = draft.get("status") == "published"

        if action == "price":
            price = parse_price(value)
            if not price:
                return JSONResponse({"error": "Kein gültiger Preis. Beispiel: 16,90"}, status_code=400)
            draft["price"] = price
            # Lokal geändert — Sales-Sync darf den eBay-Preis nicht zurückholen,
            # bis „Speichern" den neuen Preis live geschickt hat (Claude-Review A1).
            draft["price_dirty"] = True
        elif action == "title":
            if not value or len(value) > 80:
                return JSONResponse({"error": f"Titel: 1–80 Zeichen (aktuell {len(value)})."},
                                    status_code=400)
            draft["listing"]["title"] = value
        elif action == "qty":
            if draft.get("format") == "AUCTION":
                return JSONResponse({"error": "Auktionen haben immer Stückzahl 1."}, status_code=400)
            try:
                qty = int(value)
            except ValueError:
                qty = 0
            if not 1 <= qty <= 1000:
                return JSONResponse({"error": "Stückzahl: Zahl zwischen 1 und 1000."}, status_code=400)
            draft["quantity"] = qty
        elif action == "desc":
            if not value:
                return JSONResponse({"error": "Beschreibung darf nicht leer sein."}, status_code=400)
            import html as _html
            safe = _html.escape(value).replace("\n", "<br>")
            draft["listing"]["description_html"] = f"<p>{safe}</p>"
            draft["image_urls"] = None
        elif action == "cond":
            if not value:
                return JSONResponse({"error": "Zustand darf nicht leer sein."}, status_code=400)
            draft["listing"]["condition"] = value
            draft.pop("condition_id", None)
            draft.pop("condition_descriptors", None)
        elif action == "fmt":
            draft["format"] = ("AUCTION" if draft.get("format", "FIXED_PRICE") == "FIXED_PRICE"
                               else "FIXED_PRICE")
            apply_price_rule(draft)
        elif action == "dur":
            options = sorted(AUCTION_DURATIONS)
            if value and value.isdigit() and int(value) in AUCTION_DURATIONS:
                draft["auction_days"] = int(value)
            else:
                cur = int(draft.get("auction_days") or 7)
                draft["auction_days"] = (options[(options.index(cur) + 1) % len(options)]
                                         if cur in options else 1)
        elif action == "offer":
            bo = draft.get("best_offer")
            if bo and bo.get("enabled"):
                draft["best_offer"] = None
            else:
                min_price = parse_price(value) if value else None
                draft["best_offer"] = {"enabled": True, "min_price": min_price}
        elif action == "uskset":
            aspects = draft["listing"].setdefault("aspects", {})
            if value == "none":
                aspects.pop(USK_ASPECT, None)
            elif value.isdigit() and int(value) in USK_VALUES:
                aspects[USK_ASPECT] = [USK_VALUES[int(value)]]
            else:
                return JSONResponse({"error": "Ungültige USK-Stufe."}, status_code=400)
        elif action == "imgtog":
            i = int(value) if value.isdigit() else 0
            photos = draft.get("photos") or []
            originals = draft.get("original_photos") or []
            rendered = draft.get("rendered_photos") or []
            if i < len(photos) and i < len(originals) and i < len(rendered):
                if photos[i] == originals[i] and rendered[i] != originals[i]:
                    photos[i] = rendered[i]
                else:
                    photos[i] = originals[i]
                draft["photos"] = photos
                draft["image_urls"] = None
        elif action == "imgren":
            originals = draft.get("original_photos") or draft.get("photos") or []
            render_kwargs = render_kwargs_for(account)
            folder = TMP_DIR / draft_id
            folder.mkdir(parents=True, exist_ok=True)
            new_rendered, failed = [], 0
            for i, src in enumerate(originals):
                out = folder / f"render_{i:02d}.jpg"
                try:
                    new_rendered.append(await asyncio.to_thread(
                        lambda p=src, o=out: render_product(p, o, **render_kwargs)))
                except Exception as e:  # noqa: BLE001
                    log.warning("App-Neu-Rendern fehlgeschlagen für %s: %s", src, e)
                    new_rendered.append(src)
                    failed += 1
            draft["rendered_photos"] = new_rendered
            draft["photos"] = list(new_rendered)
            draft["image_urls"] = None
            store.update_draft(draft_id, draft)
            if failed:
                chat_add(account["id"], "bot", "info",
                         {"text": f"Neu gerendert — {failed} Bild(er) ohne Freisteller."})
            return draft_payload(store.get_draft(draft_id))
        elif action == "regen":
            store.update_draft(draft_id, draft)
            _spawn(app_run_pipeline(account, draft_id))
            return {"ok": True, "processing": True}
        elif action == "discard":
            if published:
                return JSONResponse({"error": "Veröffentlichte Listings beendest du mit 🛑."},
                                    status_code=400)
            cleanup_photos(draft)
            store.delete_draft(draft_id)
            chat_add(account["id"], "bot", "info", {"text": "❌ Entwurf verworfen."})
            return {"ok": True, "discarded": True}
        elif action == "edit":
            chat_add(account["id"], "bot", "preview", {"draft_id": draft_id})
            return {"ok": True}
        elif action == "upload":
            if published:
                return JSONResponse({"error": "Schon veröffentlicht — nutze Speichern."},
                                    status_code=400)
            if draft.get("status") == "publishing":
                return {"ok": True, "processing": True}   # läuft schon — kein zweiter Task
            if not draft.get("price"):
                return JSONResponse({"error": "Bitte zuerst einen Preis setzen."}, status_code=400)
            if not draft.get("category_id"):
                return JSONResponse({"error": "Keine Kategorie gefunden — erst neu generieren."},
                                    status_code=400)
            if not is_admin(account):
                plan = account.get("plan")
                if plan not in PLAN_LIMITS:
                    return JSONResponse({"error": "Zum Veröffentlichen brauchst du einen Plan "
                                                  "(14 Tage gratis) — Website, Schritt 5."},
                                        status_code=402)
                limit = PLAN_LIMITS[plan]
                used = store.listings_this_month(uid_for(account))
                if limit is not None and used >= limit:
                    return JSONResponse({"error": f"Monatslimit erreicht ({used}/{limit})."},
                                        status_code=402)
            _spawn(app_run_upload(account, draft_id))
            return {"ok": True, "processing": True}
        elif action == "save":
            if not published:
                return JSONResponse({"error": "Noch nicht veröffentlicht — nutze Hochladen."},
                                    status_code=400)
            store.update_draft(draft_id, draft)
            _spawn(app_run_update(account, draft_id))
            return {"ok": True, "processing": True}
        elif action == "end":
            if not draft.get("offer_id"):
                return JSONResponse({"error": "Listing nicht mehr auffindbar."}, status_code=404)
            try:
                await withdraw_offer(ebay, draft["offer_id"], uid_for(account))
            except (InventoryError, EbayAuthError) as e:
                return JSONResponse({"error": f"Konnte das Listing nicht beenden:\n{e}"},
                                    status_code=502)
            draft["status"] = "ended"
            store.update_draft(draft_id, draft)
            cleanup_photos(draft)
            chat_add(account["id"], "bot", "info",
                     {"text": "🛑 Listing beendet — es ist nicht mehr auf eBay aktiv."})
            return {"ok": True, "ended": True}
        else:
            return JSONResponse({"error": f"Unbekannte Aktion: {action}"}, status_code=400)

        store.update_draft(draft_id, draft)
        return draft_payload(store.get_draft(draft_id))

    @router.post("/draft/{draft_id}/answer")
    async def draft_answer(request: Request, draft_id: str, body: AnswerBody):
        """Antwort auf eine Bot-Rückfrage (Unsicherheits-Frage oder Grading-Angaben)."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        draft = own_draft(draft_id, account)
        if not draft:
            return JSONResponse({"error": "Draft existiert nicht mehr."}, status_code=404)
        text = body.text.strip()
        if not text:
            return JSONResponse({"error": "Leere Antwort."}, status_code=400)
        chat_add(account["id"], "user", "user_text", {"text": text})

        pending = draft.pop("app_pending", None)
        if pending in ("graded", "graded_update"):
            info = draft["listing"].get("graded_info") or {}
            tokens = text.replace(",", ".").split()
            grader = next((t for t in tokens if t.isalpha()), None) or info.get("grader")
            grade = (next((t for t in tokens if re.fullmatch(r"\d{1,2}(\.5)?", t)), None)
                     or info.get("grade"))
            cert = next((t for t in tokens
                         if len(t) >= 5 and t.isalnum() and any(c.isdigit() for c in t)),
                        None) or info.get("cert_number")
            missing = [name for name, val in (("Bewerter", grader), ("Note", grade),
                                              ("Zertifikatsnummer", cert)) if not val]
            if missing:
                draft["app_pending"] = pending
                store.update_draft(draft_id, draft)
                return JSONResponse({"error": f"Mir fehlt noch: {', '.join(missing)}. "
                                              "Beispiel: PSA 9.5 12345678"}, status_code=400)
            draft["listing"]["graded_info"] = {"grader": str(grader).upper(), "grade": grade,
                                               "cert_number": cert}
            store.update_draft(draft_id, draft)
            chat_add(account["id"], "bot", "info",
                     {"text": f"👍 {str(grader).upper()} {grade}, Zert. {cert} übernommen."})
            _spawn(app_run_update(account, draft_id) if pending == "graded_update"
                   else app_run_upload(account, draft_id))
            return {"ok": True, "processing": True}

        # Unsicherheits-Frage oder Zusatzinfo: Caption ergänzen, Pipeline neu
        extra = (draft.get("caption") or "")
        draft["caption"] = (extra + "\n" + text).strip()
        store.update_draft(draft_id, draft)
        _spawn(app_run_pipeline(account, draft_id))
        return {"ok": True, "processing": True}

    @router.get("/photo/{draft_id}/{idx}")
    async def get_photo(request: Request, draft_id: str, idx: int, f: str = "", w: int = 0):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        draft = own_draft(draft_id, account)
        if not draft:
            return JSONResponse({"error": "not found"}, status_code=404)
        photos = draft.get("photos") or []
        if not 0 <= idx < len(photos):
            return JSONResponse({"error": "not found"}, status_code=404)
        p = Path(photos[idx])
        if p.exists():
            tp = thumb_path(str(p), w)
            return FileResponse(tp, media_type=_MIME.get(Path(tp).suffix.lower(), "image/jpeg"))
        urls = draft.get("image_urls") or []
        if idx < len(urls):
            return RedirectResponse(urls[idx])
        return JSONResponse({"error": "not found"}, status_code=404)

    # ------------------------------------------------------------ Sammlung (Portfolio)

    @router.get("/collection")
    async def get_collection(request: Request, offset: int = 0, limit: int = 1000):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        # Schlanke Item-Sicht (Detail-Felder lädt die Detailansicht selbst) und
        # Seiten-Zugriff: bei 5.000 Karten war die Antwort sonst ~13 MB — bei
        # JEDEM Push, auf jedem Gerät. Stats rechnen bewusst über ALLE Stücke.
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        items = [item_list_public(i, account) for i in col_all(account["id"])]
        # Besitz = nicht Wunschliste UND nicht live im Verkauf (Svens Drei-Stufen-Modell:
        # Sammlung -> Verkauf -> Geld; Entwürfe zählen noch als Besitz)
        owned = [i for i in items if not i["wishlist"] and i["draft_status"] != "published" and not i.get("sold")]
        total = sum((i["est_value"] or 0) * i["quantity"] for i in owned)
        invested = 0.0
        has_invest = False
        for i in owned:
            try:
                if i["purchase_price"] not in (None, ""):
                    invested += _num(i["purchase_price"]) * i["quantity"]
                    has_invest = True
            except ValueError:
                pass
        cats: dict[str, int] = {}
        for i in items:
            cats[i["category"]] = cats.get(i["category"], 0) + 1
        listed = sum(1 for i in items if i["draft_status"] == "published")
        # 7-Tage-Trend je Item (für Pfeile im Grid). Früher eine Datenbank-Abfrage
        # PRO Stück — bei 5.000 Karten also 5.000 Abfragen für einen einzigen
        # Seitenaufruf. Jetzt eine einzige, die den letzten Wert je Stück holt.
        week_ago = time.time() - 7 * 86400
        vorher = {r["item_id"]: r["value"] for r in store._conn.execute(  # noqa: SLF001
            "SELECT item_id, value FROM price_history WHERE account_id = ? AND ts <= ? "
            "AND ts = (SELECT MAX(ts) FROM price_history p2 WHERE p2.item_id = price_history.item_id "
            "          AND p2.ts <= ?) GROUP BY item_id",
            (account["id"], week_ago, week_ago)).fetchall()}
        for i in items:
            alt = vorher.get(i["id"])
            if alt and i["est_value"]:
                i["delta7"] = round(i["est_value"] - alt, 2)
        all_tags: dict[str, int] = {}
        for i in items:
            for t in i["tags"]:
                all_tags[t] = all_tags.get(t, 0) + 1
        seite = items[offset:offset + limit]
        rev_row = store._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) AS n, MAX(updated_at) AS m FROM collection_items "
            "WHERE account_id = ?", (account["id"],)).fetchone()
        return {
            "items": seite,
            "total": len(items),
            "offset": offset,
            "limit": limit,
            "rev": f"{rev_row['n']}:{rev_row['m'] or 0}",
            "stats": {
                "count": len(owned),
                "total_value": round(total, 2),
                "invested": round(invested, 2) if has_invest else None,
                "listed": listed,
                "favorites": sum(1 for i in items if i["favorite"]),
                "wishlist": sum(1 for i in items if i["wishlist"]),
                "duplicates": sum(1 for i in owned if i["quantity"] > 1),
                "categories": sorted(cats.items(), key=lambda kv: -kv[1]),
                "tags": sorted(all_tags.items(), key=lambda kv: -kv[1]),
            },
            "history": portfolio_history(account["id"]),
            "ready": setup_ready(account),
            "dry_run": dry_run_active(),
        }

    @router.post("/collection/items")
    async def add_collection_item(request: Request, files: list[UploadFile] = File(...),
                                  notes: str = Form("")):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = claim_scans(account)
        if limited:
            return limited
        files = files[:8]
        item_id = uuid.uuid4().hex[:12]
        folder = COL_DIR / item_id
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, f in enumerate(files):
            raw = await _read_limited(f, 20 * 1024 * 1024)
            if raw is None:
                refund_scans(account)
                shutil.rmtree(folder, ignore_errors=True)
                return JSONResponse({"error": f"Bild {i + 1} ist zu groß (max. 20 MB)."},
                                    status_code=400)
            path = folder / f"{i:02d}.jpg"
            try:
                await asyncio.to_thread(_to_jpeg, raw, path)
            except Exception as e:  # noqa: BLE001
                # Kaputte Bytes wurden früher stumm als .jpg gespeichert — die
                # Analyse lief dann gegen Datenmüll und scheiterte unerklärlich.
                log.warning("Foto %d nicht lesbar (%s)", i + 1, type(e).__name__)
                refund_scans(account)
                shutil.rmtree(folder, ignore_errors=True)
                return JSONResponse({"error": "Dieses Foto-Format kann SERO nicht lesen. "
                                              "Stelle in den iPhone-Einstellungen Kamera → Formate "
                                              "auf „Maximal kompatibel“ oder wähle ein JPEG."},
                                    status_code=400)
            paths.append(str(path))
        if not paths:
            refund_scans(account)
            shutil.rmtree(folder, ignore_errors=True)
            return JSONResponse({"error": "Kein verwertbares Foto angekommen."}, status_code=400)
        item = {"status": "analyzing", "photos": paths,
                "notes": notes.strip() or None, "quantity": 1}
        col_save(item_id, account["id"], item, create=True)
        enqueue_scan(account, item_id)
        return {"ok": True, "item_id": item_id}

    # ── Foto-Ablage: iOS-PWAs verlieren den JS-Speicher beim Kamera-Wechsel —
    # deshalb wird JEDES Foto sofort serverseitig geparkt, bis „Analysieren" kommt.
    STAGE_DIR = COL_DIR / "_stage"
    STAGE_TTL = 30 * 60           # Reste abgebrochener Scans verfallen schnell —
    #                               sonst landen sie im NÄCHSTEN Item (Svens Fall:
    #                               11:46 ein Testfoto, 12:09 zwei neue → 3 im Item)
    STAGE_GAP = 10 * 60           # Ein Scan-Vorgang hängt zeitlich zusammen: liegt
    #                               das jüngste Foto länger zurück, war es ein
    #                               abgebrochener Vorgang → Ablage startet frisch.
    _stage_lock = asyncio.Lock()  # iOS feuert Events doppelt: ohne Lock prüfen
    #                               zwei parallele Uploads die Dedupe-Liste,
    #                               BEVOR einer geschrieben hat → Duplikat.

    def _stage_log(account_id: int, event: str, **kw) -> None:
        """Ablage-Protokoll: jeder Vorfall („5 Bilder!") ist damit rekonstruierbar."""
        try:
            STAGE_DIR.mkdir(parents=True, exist_ok=True)
            rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "acc": account_id,
                   "event": event, **kw}
            with (STAGE_DIR / "protocol.log").open("a") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _to_jpeg(raw: bytes, dest: Path) -> None:
        """PIL-Arbeit (Decode, EXIF-Drehung, JPEG-Encode) — läuft via to_thread,
        damit der Event-Loop währenddessen SSE-Pings und Logins bedienen kann.
        Lange Kante 2400 px: eBay rendert maximal 1600, die Analyse braucht 1400 —
        ein 48-MP-Original (3,5 MB+) kostete pro Karte nur Platte, nie Qualität."""
        from PIL import Image, ImageOps
        import io
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        if max(img.size) > 2400:
            img.thumbnail((2400, 2400))
        img.save(dest, "JPEG", quality=92)

    async def _read_limited(f, limit: int) -> bytes | None:
        """Datei chunkweise einlesen; None sobald das Limit reißt (RAM-Schutz)."""
        chunks, total = [], 0
        while True:
            chunk = await f.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                return None
            chunks.append(chunk)
        return b"".join(chunks)

    # Thumbnail-Cache-Dateien (name_w240.png …) liegen NEBEN den Originalen —
    # sie dürfen NIE als eigene Fotos zählen (DAS war der „5 Bilder"-Bug!)
    _THUMB_RE = re.compile(r"_w\d+\.(?:png|jpe?g|webp)$", re.I)

    # Die Ablage war pro KONTO: fotografierten iPhone und iPad gleichzeitig,
    # mischten sich die Fotos in ein Stück — und ein „Abbrechen" auf dem einen
    # Gerät löschte die Aufnahmen des anderen. Jetzt hat jedes Gerät seinen
    # eigenen Unterordner; TTL und Aufräumen wirken automatisch pro Gerät.
    _DEV_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

    def stage_dir(account_id: int, device: str) -> Path:
        dev = device if _DEV_RE.match(device or "") else "default"
        return STAGE_DIR / str(account_id) / dev

    def _stage_list(account_id: int, device: str) -> list[dict]:
        d = stage_dir(account_id, device)
        if not d.exists():
            return []
        out = []
        for p in sorted(d.iterdir()):
            if not p.is_file() or _THUMB_RE.search(p.name):
                continue
            if time.time() - p.stat().st_mtime > STAGE_TTL:
                p.unlink(missing_ok=True)
                _stage_log(account_id, "expired", name=p.name)
                continue
            out.append({"name": p.name,
                        "url": f"/api/app/collection/stage-photo/{p.name}?device={d.name}"})
        return out

    @router.get("/collection/stage")
    async def stage_get(request: Request, device: str = "default"):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        return {"photos": _stage_list(account["id"], device)}

    @router.post("/collection/stage")
    async def stage_add(request: Request, files: list[UploadFile] = File(...),
                        device: str = "default"):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        d = stage_dir(account["id"], device)
        d.mkdir(parents=True, exist_ok=True)
        import hashlib as _hl
        async with _stage_lock:
            # Frischer Scan-Vorgang? Dann Reste des abgebrochenen vorher wegräumen.
            old = [p for p in d.iterdir()
                   if p.is_file() and not _THUMB_RE.search(p.name)] if d.exists() else []
            if old and time.time() - max(p.stat().st_mtime for p in old) > STAGE_GAP:
                for p in d.iterdir():
                    if p.is_file():
                        p.unlink(missing_ok=True)
                _stage_log(account["id"], "stale_reset", dropped=len(old))
            seen = {_hl.sha1(p.read_bytes()).hexdigest()
                    for p in d.iterdir()
                    if p.is_file() and not _THUMB_RE.search(p.name)} if d.exists() else set()
            for f in files[:8]:
                raw = await _read_limited(f, 20 * 1024 * 1024)
                if raw is None:
                    _stage_log(account["id"], "too_big")
                    continue
                h = _hl.sha1(raw).hexdigest()
                if h in seen:
                    # iOS feuert Aufnahmen gern doppelt — Inhalt schon da
                    _stage_log(account["id"], "dupe_skip", sha=h[:10], size=len(raw))
                    continue
                seen.add(h)
                ext = Path(f.filename or "x.jpg").suffix.lower() or ".jpg"
                if ext not in (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"):
                    ext = ".jpg"
                name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}{ext}"
                (d / name).write_bytes(raw)
                _stage_log(account["id"], "add", sha=h[:10], size=len(raw),
                           name=name, count=len(seen), dev=d.name)
        return {"photos": _stage_list(account["id"], device)}

    @router.post("/collection/stage/remove")
    async def stage_remove(request: Request, name: str = Form(...),
                           device: str = "default"):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        if "/" not in name and ".." not in name:
            (stage_dir(account["id"], device) / name).unlink(missing_ok=True)
            _stage_log(account["id"], "remove", name=name, dev=device)
        return {"photos": _stage_list(account["id"], device)}

    @router.post("/collection/stage/clear")
    async def stage_clear(request: Request, device: str = "default"):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        # Nur den EIGENEN Geräte-Ordner — nie die Aufnahmen des anderen Geräts
        shutil.rmtree(stage_dir(account["id"], device), ignore_errors=True)
        _stage_log(account["id"], "clear", dev=device)
        return {"ok": True}

    @router.get("/collection/stage-photo/{name}")
    async def stage_photo(request: Request, name: str, w: int = 0,
                          device: str = "default"):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        if "/" in name or ".." in name:
            return JSONResponse({"error": "?"}, status_code=400)
        p = stage_dir(account["id"], device) / name
        if not p.exists():
            return JSONResponse({"error": "weg"}, status_code=404)
        tp = thumb_path(str(p), w)
        return FileResponse(tp, media_type=_MIME.get(Path(tp).suffix.lower(), "image/jpeg"))

    @router.post("/collection/items-from-stage")
    async def items_from_stage(request: Request, notes: str = Form(""),
                               order: str = Form(""), device: str = "default"):
        """Alle geparkten Fotos werden EIN Sammlungsstück (Vorder-/Rückseite).

        `order` ist die vom Nutzer im Sammler festgelegte Reihenfolge
        (Dateinamen, kommagetrennt). Das erste Foto wird das Hauptbild —
        ohne diese Angabe sortiert der Server nach Aufnahmezeit."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = claim_scans(account)
        if limited:
            return limited
        d = stage_dir(account["id"], device)
        staged = sorted([p for p in d.iterdir()
                         if p.is_file() and not _THUMB_RE.search(p.name)]) if d.exists() else []
        wunsch = [n.strip() for n in (order or "").split(",") if n.strip()]
        if wunsch:
            # Nur nach der Wunschreihenfolge sortieren, nichts hinzufügen oder
            # weglassen: unbekannte Namen ignorieren, fehlende hinten anhängen.
            rang = {n: i for i, n in enumerate(wunsch)}
            staged.sort(key=lambda p: rang.get(p.name, len(rang)))
        if not staged:
            return JSONResponse({"error": "Keine Fotos in der Ablage."}, status_code=400)
        from PIL import Image, ImageOps
        import io
        item_id = uuid.uuid4().hex[:12]
        folder = COL_DIR / item_id
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, sp in enumerate(staged[:8]):
            path = folder / f"{i:02d}.jpg"
            try:
                raw = await asyncio.to_thread(sp.read_bytes)
                await asyncio.to_thread(_to_jpeg, raw, path)
            except Exception as e:  # noqa: BLE001
                log.warning("Geparktes Foto %s nicht lesbar (%s)", sp.name, type(e).__name__)
                continue            # lieber ein Foto weniger als Datenmüll in der Analyse
            paths.append(str(path))
        if not paths:
            refund_scans(account)
            return JSONResponse({"error": "Keines der geparkten Fotos war lesbar — "
                                          "bitte neu fotografieren."}, status_code=400)
        shutil.rmtree(d, ignore_errors=True)
        _stage_log(account["id"], "item", item_id=item_id, n=len(paths),
                   files=[p.name for p in staged[:8]], dev=device)
        item = {"status": "analyzing", "photos": paths,
                "notes": notes.strip() or None, "quantity": 1}
        col_save(item_id, account["id"], item, create=True)
        enqueue_scan(account, item_id)
        return {"ok": True, "item_id": item_id, "photo_count": len(paths)}

    @router.post("/collection/scan-batch")
    async def scan_batch(request: Request, files: list[UploadFile] = File(...),
                         notes: str = Form("")):
        """Viele Fotos auf einmal: KI gruppiert Vorder-/Rückseiten zu Objekten,
        dann läuft je Objekt die normale Analyse (inkl. Freistellen)."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        from web import cardscan
        files = files[:cardscan.MAX_BATCH]
        limited = claim_scans(account, len(files))
        if limited:
            return limited
        _claimed = len(files)
        batch = COL_DIR / f"batch_{uuid.uuid4().hex[:10]}"
        batch.mkdir(parents=True, exist_ok=True)
        from PIL import Image, ImageOps
        import io
        paths = []
        for i, f in enumerate(files):
            raw = await _read_limited(f, 20 * 1024 * 1024)
            if raw is None:
                refund_scans(account, _claimed)
                shutil.rmtree(batch, ignore_errors=True)
                return JSONResponse({"error": f"Bild {i + 1} ist zu groß (max. 20 MB)."},
                                    status_code=400)
            path = batch / f"{i:02d}.jpg"
            try:
                await asyncio.to_thread(_to_jpeg, raw, path)
            except Exception as e:  # noqa: BLE001
                log.warning("Stapel-Foto %d nicht lesbar (%s)", i + 1, type(e).__name__)
                continue            # ein Schrott-Foto stoppt nicht den ganzen Stapel
            paths.append(str(path))
        if not paths:
            refund_scans(account, _claimed)
            shutil.rmtree(batch, ignore_errors=True)
            return JSONResponse({"error": "Keines der Fotos war lesbar. Stelle in den "
                                          "iPhone-Einstellungen Kamera → Formate auf "
                                          "„Maximal kompatibel“."}, status_code=400)
        groups = await cardscan.group_photos(cfg.anthropic_api_key, paths)
        item_ids = []
        for g in groups:
            item_id = uuid.uuid4().hex[:12]
            folder = COL_DIR / item_id
            folder.mkdir(parents=True, exist_ok=True)
            gp = []
            for j, idx in enumerate(g):
                dest = folder / f"{j:02d}.jpg"
                shutil.move(paths[idx], dest)
                gp.append(str(dest))
            item = {"status": "analyzing", "photos": gp,
                    "notes": notes.strip() or None, "quantity": 1}
            col_save(item_id, account["id"], item, create=True)
            enqueue_scan(account, item_id)
            item_ids.append(item_id)
        shutil.rmtree(batch, ignore_errors=True)
        # Reserviert war len(files) — verarbeitet wurde len(paths). Differenz zurück.
        refund_scans(account, _claimed - len(paths))
        return {"ok": True, "item_ids": item_ids,
                "photo_count": len(paths), "group_count": len(groups)}

    @router.get("/collection/item/{item_id}")
    async def get_collection_item(request: Request, item_id: str):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        out = item_public(item, account)
        if not out.get("sold_comps") and item.get("card_key"):
            from web import catalog
            _rowp = catalog.get_price(store, item["card_key"],
                                      catalog.grade_bucket(item.get("graded")))
            if _rowp and (_rowp.get("detail") or {}).get("sold"):
                out["sold_comps"] = _rowp["detail"]["sold"]
        out["history"] = item_history(item_id)
        # Hinweis auf ein gleiches Stück in der Sammlung — die App zeigt ihn,
        # entscheiden tut der Nutzer.
        zwilling = aehnliches_stueck(account["id"], item)
        if zwilling:
            out["dublette"] = {"id": zwilling["id"],
                               "name": (zwilling.get("name") or "")[:60],
                               "draft_id": zwilling.get("draft_id")}
        alert = get_alert(item_id)
        out["alert"] = ({"threshold": alert["threshold"], "direction": alert["direction"],
                         "triggered": bool(alert["triggered_at"])} if alert else None)
        if item.get("draft_id"):
            draft = own_draft(item["draft_id"], account)
            if draft:
                out["draft"] = draft_payload(draft)
                out["draft"]["stage"] = latest_stage(account["id"])
        return out

    @router.get("/collection/item/{item_id}/offers")
    async def collection_item_offers(request: Request, item_id: str, market: str = "eu"):
        """Angebotslage auf drei Märkten — EU (eBay.de), USA (eBay.com),
        Japan (Händler mit Standort Japan auf eBay.com).

        Das ist bewusst KEIN Marktwert: eBays Lizenz (ALA §8.1(d)/§9) verbietet,
        aus eBay-Daten eine Preisempfehlung zu rechnen. Angezeigt wird die rohe
        Angebotslage, klar getrennt, höchstens 6 Stunden alt (§8.1(b)) — der
        Cache-TTL ist deshalb keine Stellschraube, sondern eine Auflage.
        """
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        from bot.ebay.browse import MAERKTE
        if market not in MAERKTE:
            return JSONResponse({"error": "Unbekannter Markt."}, status_code=400)

        query = ((item.get("analysis") or {}).get("search_query_for_pricing")
                 or item.get("name") or "").strip()
        if not query:
            return JSONResponse({"error": "Noch keine Suchanfrage für dieses Stück."},
                                status_code=409)

        # Cache je Anfrage UND Markt — geteilt über alle Nutzer mit demselben Stück
        import hashlib as _hl
        key = ("offers3_" + market + "_"
               + _hl.sha1(query.lower().encode()).hexdigest()[:16])
        cached = store.kv_get(key)
        if cached and time.time() - cached.get("ts", 0) < cached.get("ttl", 6 * 3600):
            return cached["v"]

        try:
            from web.sold import fits
            res = await research_price(ebay, query, limit=50, market=market,
                                       title_filter=lambda t: fits(query, t))
        except Exception as e:  # noqa: BLE001
            log.warning("offers: Browse-Abruf (%s) fehlgeschlagen: %s", market, e)
            res = None

        out = {"market": market, "query": query, "count": 0, "samples": [],
               "updated": time.time()}
        ttl = 6 * 3600
        if res:
            out.update({k: res.get(k) for k in
                        ("count", "min", "max", "median", "currency", "samples")})
            # Median erst ab 5 Angeboten hervorheben — darunter ist es Zufall,
            # kein Markt (Messung 03.08.: 1 GTA-Angebot zu 380 € vs. 98 € real)
            out["solid"] = (res.get("count") or 0) >= 5
            if res.get("currency") == "USD" and res.get("median"):
                from web.prices import usd_eur
                rate = await usd_eur()
                if rate:
                    out["median_eur"] = round(res["median"] * rate, 2)
                    for s in out["samples"] or []:
                        if s.get("price") is not None:
                            s["price_eur"] = round(s["price"] * rate, 2)
                else:
                    # Kurs gerade nicht da (passiert direkt nach Serverstart) —
                    # die Antwort ohne EUR-Umrechnung nicht 6 h festnageln
                    ttl = 600
        elif res is None:
            ttl = 600   # eBay-Ausfall ebenfalls nur kurz merken
        store.kv_set(key, {"ts": time.time(), "ttl": ttl, "v": out})
        return out

    @router.post("/collection/item/{item_id}")
    async def patch_collection_item(request: Request, item_id: str, body: ItemPatchBody):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if body.name is not None:
            if not body.name.strip():
                return JSONResponse({"error": "Name darf nicht leer sein."}, status_code=400)
            item["name"] = body.name.strip()
        if body.category is not None:
            item["category"] = body.category.strip() or "Sonstiges"
        if body.condition is not None:
            item["condition"] = body.condition.strip() or None
        if body.quantity is not None:
            if not 1 <= body.quantity <= 1000:
                return JSONResponse({"error": "Stückzahl: 1–1000."}, status_code=400)
            item["quantity"] = body.quantity
        if body.purchase_price is not None:
            p = body.purchase_price.strip()
            if p:
                parsed = parse_price(p)
                if not parsed:
                    return JSONResponse({"error": "Kaufpreis ungültig. Beispiel: 12,50"}, status_code=400)
                item["purchase_price"] = parsed
            else:
                item["purchase_price"] = None
        if body.notes is not None:
            item["notes"] = body.notes.strip() or None
        if body.favorite is not None:
            item["favorite"] = body.favorite
        if body.wishlist is not None:
            item["wishlist"] = body.wishlist
        if body.tags is not None:
            item["tags"] = [t.strip()[:30] for t in body.tags if t.strip()][:12]
        col_save(item_id, account["id"], item)
        return item_public(item, account)

    @router.post("/collection/item/{item_id}/delete")
    async def delete_collection_item(request: Request, item_id: str):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        # PAPIERKORB statt Endgültig-Löschen: Fotos + Item-JSON wandern 30 Tage
        # in _trash — ein Fehl-Tipp (oder Fehl-Agent …) vernichtet nie wieder Daten.
        trash = COL_DIR / "_trash" / item_id
        try:
            trash.mkdir(parents=True, exist_ok=True)
            (trash / "item.json").write_text(
                json.dumps({**item, "account_id": account["id"]}, ensure_ascii=False))
            src = COL_DIR / item_id
            if src.exists():
                shutil.move(str(src), str(trash / "photos"))
        except OSError:
            shutil.rmtree(COL_DIR / item_id, ignore_errors=True)
        # Den zugehörigen Entwurf mitnehmen — sonst bleibt er als Karteileiche
        # im Verkauf-Tab stehen. Svens vier GTA-III-Entwürfe kamen genau so
        # zustande: Stück gelöscht, Entwurf blieb liegen.
        # ABER: Was live ist oder war, bleibt unangetastet — an einem
        # veröffentlichten Listing hängt echtes Geld.
        did = item.get("draft_id")
        if did:
            # own_draft statt store.get_draft: prüft, dass der Entwurf wirklich
            # zu diesem Konto gehört — eine manipulierte draft_id darf keinen
            # fremden Entwurf löschen.
            entwurf = own_draft(did, account)
            zustand = (entwurf or {}).get("status")
            if entwurf and zustand in ("new", "ready", "error", "uncertain"):
                store.delete_draft(did)
                log.info("Entwurf %s mit dem Stück %s entfernt", did, item_id)
            elif entwurf and zustand in ("downloading", "analyzing"):
                # Läuft gerade — abreißen hieße Absturz mitten im Rendern.
                # Nur markieren; der Lauf endet von selbst und findet kein Stück mehr.
                entwurf["item_deleted"] = time.time()
                store.update_draft(did, entwurf)
                log.info("Entwurf %s läuft noch — nur markiert statt gelöscht", did)
        notify(account["id"], "item", item_id)
        with store._lock:  # noqa: SLF001
            store._conn.execute("DELETE FROM collection_items WHERE id = ? AND account_id = ?", (item_id, account["id"]))  # noqa: SLF001
            store._conn.commit()  # noqa: SLF001
        notify(account["id"], "sales")
        return {"ok": True}

    # Ein zweiter Tipp (oder ein zweites Gerät) darf kein zweites Angebot
    # erzeugen. Die Prüfung „gibt es schon einen Entwurf?" und das Anlegen
    # müssen deshalb zusammen unter einer Sperre laufen.
    _list_locks: dict[str, asyncio.Lock] = {}

    @router.post("/collection/item/{item_id}/list")
    async def list_collection_item(request: Request, item_id: str,
                                   body: ListOptionsBody | None = None):
        """Sammlungs-Item auf eBay listen: Draft aus dem Item bauen, Pipeline ab Kategorie."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        schluessel = f"{account['id']}:{item_id}"
        sperre = _list_locks.setdefault(schluessel, asyncio.Lock())
        if len(_list_locks) > 500:          # nicht unbegrenzt wachsen lassen
            for k in [k for k, v in list(_list_locks.items()) if not v.locked()][:250]:
                _list_locks.pop(k, None)
        async with sperre:
            return await _list_collection_item(account, item_id, body)

    async def _list_collection_item(account: dict, item_id: str,
                                    body: ListOptionsBody | None = None):
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if not setup_ready(account):
            return JSONResponse({"error": "Dein eBay-Setup ist noch nicht fertig — bitte erst "
                                          "das Onboarding auf der Website abschließen."}, status_code=409)
        if not is_admin(account) and not store.account_active(account):
            return JSONResponse({"error": "Dein Testzeitraum ist abgelaufen — wähle auf der "
                                          "Website einen Plan."}, status_code=402)
        # Bestehender, noch aktiver Draft? Dann den weiterverwenden.
        if item.get("draft_id"):
            existing = own_draft(item["draft_id"], account)
            if existing and existing.get("status") not in ("ended",):
                return {"ok": True, "draft_id": item["draft_id"], "existing": True}
        photos = [p for p in (item.get("photos") or []) if Path(p).exists()]
        if not photos:
            return JSONResponse({"error": "Keine lokalen Fotos für dieses Stück — bitte neu "
                                          "fotografieren."}, status_code=400)
        uid = uid_for(account)
        draft_id = store.create_draft(uid, {"status": "downloading", "photos": [],
                                            "caption": item.get("notes")})
        # Zuerst die Zuordnung festhalten, dann erst die Fotos kopieren: das
        # Kopieren dauert bei großen Bildern spürbar, und in dieser Zeit darf
        # kein zweiter Anlauf denselben Artikel noch einmal anlegen.
        item["draft_id"] = draft_id
        col_save(item_id, account["id"], item)
        folder = TMP_DIR / draft_id
        folder.mkdir(parents=True, exist_ok=True)
        copies = []
        for i, src in enumerate(photos):
            dst = folder / f"{i:02d}{Path(src).suffix.lower() or '.jpg'}"
            await asyncio.to_thread(shutil.copyfile, src, dst)
            copies.append(str(dst))

        # Verkaufs-Vorlage (Svens Scanner-Cockpit): Format/Laufzeit/Preisregel
        if body and (body.format or body.price_mode):
            d0 = store.get_draft(draft_id)
            if body.format in ("FIXED_PRICE", "AUCTION"):
                d0["format"] = body.format
            if body.auction_days in (1, 3, 5, 7, 10):
                d0["auction_days"] = body.auction_days
                # Pipeline liest auction_days aus dem listing — dort mitschreiben,
                # sonst überschreibt sie die Vorlage mit dem 7-Tage-Default
                d0.setdefault("listing", {})["auction_days"] = body.auction_days
            store.update_draft(draft_id, d0)

        preset = dict(item.get("analysis") or {})
        # Die Analyse enthielt früher eine KI-Preisspanne — falls Alt-Daten sie
        # noch tragen, darf sie NIE in die Listing-Pipeline reisen (ADR-002).
        preset.pop("estimated_price_range_eur", None)
        # Der BELEGTE Marktwert des Stücks gehört IMMER ins Listing — sonst
        # recherchiert die Pipeline blind neu und landet weit daneben
        # (Svens Glurak: 307,90 € statt 653,02 €, 02.08.). Ein Alt-Wert aus
        # der abgeschafften KI-Schätzung zählt NICHT als Marktwert.
        # Gesperrt als Listing-Basis: Alt-KI-Werte (estimate), unbelegte Werte
        # und der Rohpreis am Slab (nur eine Untergrenze — sonst wird ein
        # PSA-10-Slab zum Preis der ungegradeten Karte gelistet).
        ist_slab = bool((item.get("graded") or {}).get("grade"))
        preisbasis_ok = (item.get("price_source") != "estimate"
                         and item.get("price_state") != "unbekannt"
                         and item.get("price_reason") != "ROHPREIS_SLAB"
                         # Alte Belege am SLAB stammen oft von der rohen Karte
                         # oder Schein-Verkäufen — Review-Fund: CGC-10-Slab
                         # wäre für 4,11 € gelistet worden.
                         and not (ist_slab and item.get("price_reason") == "BELEGE_ALT"))
        est = item_value(item) if preisbasis_ok else None
        if est:
            preset["market_value"] = f"{est:.2f}"
            # Der Zustand reist mit (Stufe 5): die Herkunft sagt ehrlich,
            # wie belastbar der Preis ist.
            zustand = item.get("price_state")
            if zustand == "spanne":
                preset["market_source"] = ((item.get("price_label") or "Marktwert")
                                           + " · Spanne, Zuordnung grob")
            else:
                preset["market_source"] = item.get("price_label") or "Marktwert"
        if body and body.price_mode:
            if body.price_mode == "auction1":
                preset["tpl_price"] = "1.00"
            elif body.price_mode == "fixed" and body.price_value:
                preset["tpl_price"] = f"{body.price_value:.2f}"
            elif body.price_mode == "market_minus10" and est:
                preset["tpl_price"] = f"{round(est * 0.9, 2):.2f}"
            elif body.price_mode == "market" and est:
                preset["tpl_price"] = f"{est:.2f}"
        if item.get("name"):
            preset["title"] = item["name"][:80]
        if item.get("condition"):
            preset["condition"] = item["condition"]
        if item.get("graded"):
            preset["graded_info"] = item["graded"]
        try:
            preset["quantity"] = int(item.get("quantity") or 1)
        except (TypeError, ValueError):
            pass

        async def prepare_and_run():
            # Zwischen hier und dem Schreiben unten liegt das Rendern — Sekunden
            # bis Minuten. Wird das Stück in der Zeit gelöscht, ist der Entwurf
            # weg und jeder Zugriff darauf ein Absturz.
            if not store.get_draft(draft_id):
                return
            render_kwargs = render_kwargs_for(account)
            originals = list(copies)
            stored_render = store.kv_get("render")
            if True if stored_render is None else bool(stored_render):
                rendered = []
                for i, p in enumerate(copies):
                    out = folder / f"render_{i:02d}.jpg"
                    try:
                        rendered.append(await asyncio.to_thread(
                            lambda src=p, o=out: render_product(src, o, **render_kwargs)))
                    except Exception as e:  # noqa: BLE001
                        log.warning("Render fehlgeschlagen für %s: %s", p, e)
                        rendered.append(p)
                use = rendered
            else:
                use = copies
            draft = store.get_draft(draft_id)     # frisch lesen, nicht am alten Stand weiterschreiben
            if not draft:
                log.info("Entwurf %s wurde während der Aufbereitung entfernt", draft_id)
                return
            draft["original_photos"] = originals
            draft["rendered_photos"] = list(use)
            draft["photos"] = list(use)
            user_row = store.get_user(uid) or {}
            draft["business"] = bool(user_row.get("business"))
            draft["status"] = "analyzing"
            store.update_draft(draft_id, draft)
            market = {k: preset.get(k) for k in ("market_value", "market_source", "tpl_price")}
            if preset.get("title") and preset.get("description_html"):
                await app_run_pipeline(account, draft_id, preset_listing=preset, market=market)
            else:
                await app_run_pipeline(account, draft_id, market=market)

        _spawn(prepare_and_run())
        return {"ok": True, "draft_id": draft_id}

    @router.post("/collection/item/{item_id}/rescan")
    async def rescan_item(request: Request, item_id: str):
        """Analyse für ein Stück neu anstoßen — der Knopf unter „Nicht erkannt"."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = app_bremse(account, "rescan", 30) or claim_scans(account)
        if limited:
            return limited
        item = col_get(item_id, account)
        if not item:
            refund_scans(account)
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if item.get("status") == "analyzing":
            refund_scans(account)
            return {"ok": True, "already": True}
        if not [p for p in (item.get("photos") or []) if Path(p).exists()]:
            refund_scans(account)
            return JSONResponse({"error": "Die Fotos zu diesem Stück sind nicht mehr da — "
                                          "bitte neu fotografieren."}, status_code=400)
        item["status"] = "analyzing"
        item["error"] = None
        item["status_text"] = "Erneuter Versuch …"
        col_save(item_id, account["id"], item)
        enqueue_scan(account, item_id)
        return {"ok": True}

    def _clear_thumbs_neben(path: str) -> None:
        p = Path(path)
        stem = p.stem
        for tp in p.parent.glob(stem + "_w*"):
            tp.unlink(missing_ok=True)

    @router.post("/collection/item/{item_id}/photos")
    async def item_photos(request: Request, item_id: str,
                          files: list[UploadFile] = File(...),
                          replace: str = Form("1")):
        """Fotos am Stück ersetzen oder anhängen (max. 8). Keine Analyse —
        nur Dateien; Freistellen läuft über /recrop."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = app_bremse(account, "item-photos", 20)
        if limited:
            return limited
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if item.get("status") == "analyzing":
            return JSONResponse(
                {"error": "Die Analyse läuft noch — bitte warten, bevor du Fotos änderst."},
                status_code=409)
        files = files[:8]
        folder = COL_DIR / item_id
        folder.mkdir(parents=True, exist_ok=True)
        new_paths: list[str] = []
        for i, f in enumerate(files):
            raw = await _read_limited(f, 20 * 1024 * 1024)
            if raw is None:
                return JSONResponse({"error": f"Bild {i + 1} ist zu groß (max. 20 MB)."},
                                    status_code=400)
            path = folder / f"u{int(time.time())}_{i:02d}.jpg"
            try:
                await asyncio.to_thread(_to_jpeg, raw, path)
            except Exception as e:  # noqa: BLE001
                log.warning("Neues Item-Foto nicht lesbar (%s)", type(e).__name__)
                return JSONResponse({"error": "Dieses Foto-Format kann SERO nicht lesen."},
                                    status_code=400)
            new_paths.append(str(path))
        if not new_paths:
            return JSONResponse({"error": "Kein verwertbares Foto angekommen."}, status_code=400)
        frisch = col_get(item_id, account)
        if frisch is None:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if (replace or "1").strip() not in ("0", "false", "False"):
            frisch["photos"] = new_paths
            frisch.pop("photos_raw", None)
        else:
            alt = [p for p in (frisch.get("photos") or []) if Path(p).exists()]
            frisch["photos"] = (alt + new_paths)[:8]
            frisch.pop("photos_raw", None)
        col_save(item_id, account["id"], frisch)
        return {"ok": True, "photo_count": len(frisch["photos"]),
                "item": item_public(frisch, account)}

    @router.post("/collection/item/{item_id}/recrop")
    async def recrop_item(request: Request, item_id: str):
        """Freisteller erneut: nur Hintergrund weg und gerade ziehen — keine Kosmetik."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = app_bremse(account, "recrop", 30)
        if limited:
            return limited
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if item.get("status") == "analyzing":
            return JSONResponse(
                {"error": "Die Analyse läuft noch — bitte warten, bevor du freistellst."},
                status_code=409)
        roh = [p for p in (item.get("photos_raw") or item.get("photos") or [])
               if Path(p).exists()]
        if not roh:
            return JSONResponse({"error": "Keine Fotos zum Freistellen vorhanden."},
                                status_code=400)
        from web import cardscan
        try:
            cropped, cinfo = await cardscan.crop_photos(cfg.anthropic_api_key, roh)
        except Exception:  # noqa: BLE001
            log.exception("Recrop fehlgeschlagen für %s", item_id)
            return JSONResponse({"error": "Freistellen ist fehlgeschlagen — bitte nochmal versuchen."},
                                status_code=500)
        frisch = col_get(item_id, account)
        if frisch is None:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if cinfo.get("cropped"):
            frisch["photos_raw"] = list(roh)
            frisch["photos"] = cropped
        else:
            frisch["photos"] = list(roh)
            frisch.pop("photos_raw", None)
        for p in frisch["photos"]:
            _clear_thumbs_neben(p)
        col_save(item_id, account["id"], frisch)
        return {"ok": True, "cropped": bool(cinfo.get("cropped")),
                "item": item_public(frisch, account)}

    @router.post("/collection/item/{item_id}/rotate")
    async def rotate_item_photo(request: Request, item_id: str, body: RotateBody):
        """Foto um 90°-Schritte drehen (Uhrzeigersinn). Schreibt neue Datei,
        kein Weichzeichnen/Aufhellen — nur Rotation."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = app_bremse(account, "rotate", 60)
        if limited:
            return limited
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if item.get("status") == "analyzing":
            return JSONResponse(
                {"error": "Die Analyse läuft noch — bitte warten, bevor du drehst."},
                status_code=409)
        photos = [p for p in (item.get("photos") or []) if Path(p).exists()]
        idx = int(body.index or 0)
        if not photos or not 0 <= idx < len(photos):
            return JSONResponse({"error": "Foto nicht gefunden."}, status_code=400)
        deg = int(body.degrees or 90)
        if deg not in (90, 180, 270, -90, -180, -270):
            return JSONResponse({"error": "Nur 90-, 180- oder 270-Grad-Schritte."},
                                status_code=400)
        # PIL: positiv = gegen Uhrzeigersinn → Uhrzeigersinn = negativ
        pil_deg = -deg if deg > 0 else abs(deg)

        def _rotate_file(src: str) -> str:
            from PIL import Image, ImageOps
            src_p = Path(src)
            img = ImageOps.exif_transpose(Image.open(src_p))
            # RGBA behalten (Freisteller mit Alpha), sonst RGB/JPEG
            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info)
            if has_alpha:
                img = img.convert("RGBA")
                out = src_p.with_name(f"{src_p.stem}_r{int(time.time())}.png")
                img.rotate(pil_deg, expand=True, resample=Image.Resampling.BICUBIC).save(
                    out, "PNG")
            else:
                img = img.convert("RGB")
                out = src_p.with_name(f"{src_p.stem}_r{int(time.time())}.jpg")
                img.rotate(pil_deg, expand=True, resample=Image.Resampling.BICUBIC).save(
                    out, "JPEG", quality=92)
            _clear_thumbs_neben(str(src_p))
            return str(out)

        try:
            new_path = await asyncio.to_thread(_rotate_file, photos[idx])
        except Exception:  # noqa: BLE001
            log.exception("Rotate fehlgeschlagen für %s/%s", item_id, idx)
            return JSONResponse({"error": "Drehen ist fehlgeschlagen."}, status_code=500)

        frisch = col_get(item_id, account)
        if frisch is None:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        # photos-Liste inkl. fehlender Pfade neu aufbauen und Index ersetzen
        all_photos = list(frisch.get("photos") or [])
        # Index bezieht sich auf existierende Fotos — denselben Slot finden
        exist_i = -1
        slot = None
        for i, p in enumerate(all_photos):
            if Path(p).exists():
                exist_i += 1
                if exist_i == idx:
                    slot = i
                    break
        if slot is None:
            return JSONResponse({"error": "Foto nicht gefunden."}, status_code=400)
        all_photos[slot] = new_path
        frisch["photos"] = all_photos
        # Rohfoto am gleichen Index mitdrehen, falls vorhanden
        raw = list(frisch.get("photos_raw") or [])
        if slot < len(raw) and Path(raw[slot]).exists():
            try:
                raw[slot] = await asyncio.to_thread(_rotate_file, raw[slot])
                frisch["photos_raw"] = raw
            except Exception:  # noqa: BLE001
                log.warning("Rohfoto-Rotate übersprungen für %s", item_id)
        col_save(item_id, account["id"], frisch)
        return {"ok": True, "index": idx, "item": item_public(frisch, account)}

    @router.post("/collection/item/{item_id}/refresh-price")
    async def refresh_price(request: Request, item_id: str):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = app_bremse(account, "refresh", 60)
        if limited:
            return limited
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        # Noch nie identifiziert (z. B. Import-Item)? Einmalig nachholen.
        if not item.get("card_info") and item.get("analysis"):
            info = await identify_card(cfg.anthropic_api_key, item["analysis"], item.get("notes"))
            if info:
                item["card_info"] = info
        await refresh_item_price(account, item, force=True)
        out = item_public(col_get(item_id, account), account)
        out["history"] = item_history(item_id)
        return out

    @router.post("/collection/refresh")
    async def refresh_all(request: Request):
        """Alle Preise der Sammlung aktualisieren (auch vom 12h-Auto-Refresh genutzt)."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = app_bremse(account, "refresh-all", 4)
        if limited:
            return limited
        items = col_all(account["id"])
        updated = 0
        for item in items:
            if item.get("status") != "ready":
                continue
            try:
                if await refresh_item_price(account, item):
                    updated += 1
            except Exception:  # noqa: BLE001 — ein kaputtes Item stoppt nicht den Rest
                log.exception("Preis-Refresh fehlgeschlagen für %s", item["id"])
        return {"ok": True, "updated": updated, "total": len(items)}

    async def periodic_refresh() -> None:
        """Alle 12 h die Preise sämtlicher Sammlungen aktualisieren (Preisverlauf!)."""
        await asyncio.sleep(120)  # Server erst in Ruhe hochfahren lassen
        while True:
            try:
                account_ids = [r["account_id"] for r in store._conn.execute(  # noqa: SLF001
                    "SELECT DISTINCT account_id FROM collection_items").fetchall()]
                for aid in account_ids:
                    account = store.get_account(aid)
                    if not account:
                        continue
                    # Nur die IDs merken: die Runde dauert bei großen Sammlungen
                    # Stunden, ein Schnappschuss aller Daten wäre längst veraltet.
                    for iid in [i["id"] for i in col_all(aid)]:
                        item = col_get(iid, account)
                        if not item or item.get("status") != "ready":
                            continue
                        if time.time() - (item.get("price_updated") or 0) < 11 * 3600:
                            continue    # nach einem Neustart nicht alles noch mal
                        try:
                            await refresh_item_price(account, item)
                        except Exception:  # noqa: BLE001
                            log.exception("Auto-Refresh fehlgeschlagen für %s", iid)
                        await asyncio.sleep(1.5)  # sanft zu den freien APIs
                log.info("Auto-Preis-Refresh fertig (%d Konten)", len(account_ids))
            except Exception:  # noqa: BLE001
                log.exception("Auto-Preis-Refresh-Runde fehlgeschlagen")
            await asyncio.sleep(12 * 3600)

    # ── Baustein 3: Scan-Warteschlange — begrenzte Parallelität (Server bleibt
    # flott), Position sichtbar, überlebt Neustarts (rescue enqueued neu).
    # Fair statt FIFO: eine Warteschlange pro Konto, die Worker gehen reihum.
    # Vorher stand Konto B mit seiner EINEN Karte hinter dem 20er-Stapel von
    # Konto A — bis zu einer Stunde „In Warteschlange" für einen einzigen Scan.
    from collections import deque as _deque
    _scan_queues: dict[int, _deque] = {}
    _scan_rr: _deque = _deque()          # Konto-Reihenfolge (Round-Robin)
    _scan_wake = asyncio.Event()
    # Was bereits wartet oder läuft — verhindert, dass Rettungsdienst und
    # Nutzer-Retry dasselbe Stück doppelt einreihen.
    # (Diese Zeile ging beim Umbau auf Round-Robin verloren: enqueue_scan warf
    #  dadurch NameError, jedes hochgeladene Stück blieb ewig auf „analysiert".)
    _scan_pending: set[str] = set()

    def _scan_next() -> tuple[int, str] | None:
        """Nächstes (Konto, Item) reihum — synchron, also atomar im Event-Loop."""
        while _scan_rr:
            aid = _scan_rr[0]
            q = _scan_queues.get(aid)
            if q:
                item_id = q.popleft()
                _scan_rr.rotate(-1)      # danach ist das nächste Konto dran
                return aid, item_id
            _scan_rr.popleft()           # Konto ohne Arbeit austragen
            _scan_queues.pop(aid, None)
        return None

    # Ein einzelner Scan dauert gemessen ~75 s. Warten mehrere Stücke, kommt die
    # Wartezeit vor dem Freisteller-Schloss dazu (nur einer rechnet gleichzeitig)
    # und die 4-Sekunden-Drossel der Verkaufsabfragen. 360 s waren zu knapp:
    # Svens vier gleichzeitig hochgeladene Stücke liefen am 03.08. alle hinein.
    SCAN_TIMEOUT = 900

    async def _scan_worker(n: int):
        log.info("Scan-Worker %d bereit", n)
        while True:
            naechster = _scan_next()
            if naechster is None:
                _scan_wake.clear()
                await _scan_wake.wait()
                continue
            account_id, item_id = naechster
            account = store.get_account(account_id)
            if account:
                t0 = time.time()
                try:
                    # Harte Obergrenze: sonst hält ein einziger hängender
                    # Netzwerk-Aufruf einen von nur zwei Workern über eine Stunde
                    await asyncio.wait_for(
                        analyze_collection_item(account, item_id), SCAN_TIMEOUT)
                    # Echte Dauer festhalten — daraus rechnet die App später die
                    # gesparte Zeit aus WIRKLICHEN Werten statt aus Werbezahlen
                    done = col_get(item_id, account)
                    if done is not None and done.get("status") != "analyzing":
                        done["scan_seconds"] = round(time.time() - t0, 1)
                        col_save(item_id, account["id"], done)
                except asyncio.TimeoutError:
                    it = col_get(item_id, account)
                    if it:
                        it["status"], it["status_text"] = "error", None
                        it["error"] = "Die Analyse hat zu lange gedauert. Versuch es noch einmal."
                        col_save(item_id, account["id"], it)
                    log.warning("Scan-Worker: %s nach %ds abgebrochen", item_id, SCAN_TIMEOUT)
                except Exception:  # noqa: BLE001
                    log.exception("Scan-Worker: %s fehlgeschlagen", item_id)
            _scan_pending.discard(item_id)

    def enqueue_scan(account: dict, item_id: str) -> None:
        if item_id in _scan_pending:
            # Rettungsdienst und Nutzer-Retry können sich überschneiden — zwei
            # Worker auf demselben Item hieße doppelte Claude-Kosten und ein
            # Wettrennen beim Zurückschreiben.
            return
        _scan_pending.add(item_id)
        item = col_get(item_id, account)
        if item is not None:
            # Position aus Sicht DIESES Kontos — fremde Stapel stehen nicht mehr davor
            pos = len(_scan_queues.get(account["id"], ()))
            item["status_text"] = f"In Warteschlange (Platz {pos + 1}) …" if pos >= 2 else "Gleich dran …"
            col_save(item_id, account["id"], item)
        _scan_queues.setdefault(account["id"], _deque()).append(item_id)
        if account["id"] not in _scan_rr:
            _scan_rr.append(account["id"])
        _scan_wake.set()

    # ── Baustein 4: Abo-Fundament — 50 Gratis-Scans, Premium-Flag, Zähler
    FREE_SCANS = 50

    def is_premium(account_id: int) -> bool:
        return bool((store.kv_get(f"premium_{account_id}") or {}).get("on"))

    def scan_count(account_id: int) -> int:
        return int((store.kv_get(f"scans_{account_id}") or {}).get("n", 0))

    # Zahlende Kunden zahlten bisher UMSONST: der Stripe-Webhook setzt nur
    # accounts.plan, geprüft wurde aber ausschließlich das kv "premium_…", das
    # nirgends im Code je gesetzt wird. Ein starter/reseller/shop-Kunde blieb
    # also trotz Zahlung auf dem Gratis-Limit sitzen.
    def app_bremse(account: dict, was: str, max_hits: int, window_s: float = 3600):
        """Per-Konto-Limiter für Endpunkte, die externe Kosten auslösen (Claude,
        eBay-Suchen). Bisher konnte ein einzelner Gratis-Nutzer mit einem Skript
        unbegrenzt Kosten erzeugen — kein einziger /api/app-Endpunkt war gebremst."""
        from web.server import rate_limited
        if is_admin(account):
            return None
        if rate_limited(f"app:{account['id']}:{was}", max_hits, window_s):
            return JSONResponse({"error": "Zu viele Anfragen — bitte warte einen Moment "
                                          "und versuch es dann noch einmal."}, status_code=429)
        return None

    def scan_freigeschaltet(account: dict) -> bool:
        return (is_admin(account)
                or account.get("plan") in ("starter", "reseller", "shop")
                or is_premium(account["id"]))

    def claim_scans(account: dict, n: int = 1):
        """Prüfen UND reservieren in EINEM Schritt. Vorher lagen dazwischen
        Foto-Verarbeitung und awaits — N gleichzeitige Anfragen kamen alle an
        der Prüfung vorbei, bevor die erste zählte. Diese Funktion enthält
        bewusst kein await: im Event-Loop ist sie damit unteilbar."""
        if scan_freigeschaltet(account):
            return None
        cur = scan_count(account["id"])
        if cur + n > FREE_SCANS:
            return JSONResponse({"error": f"Kostenloses Scan-Limit ({FREE_SCANS}) erreicht. "
                                          "Premium schaltet unbegrenzte Scans frei."},
                                status_code=402)
        store.kv_set(f"scans_{account['id']}", {"n": cur + n})
        return None

    def refund_scans(account: dict, n: int = 1) -> None:
        """Reservierung zurückgeben, wenn nach dem Claim doch nichts gescannt wurde."""
        if scan_freigeschaltet(account) or n <= 0:
            return
        cur = scan_count(account["id"])
        store.kv_set(f"scans_{account['id']}", {"n": max(0, cur - n)})

    async def sync_sales_status(only_account: dict | None = None) -> int:
        """Verkaufs-Routine: published-Listings gegen eBay abgleichen.

        - Listenpreis aus dem eBay-Offer übernehmen (keine Schätzungen)
        - Aktive Käufer-Preisvorschläge (Best Offer) laden
        - Verkaufte/beendete Angebote auf 'ended' stellen
        """
        from bot.config import EBAY_API
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT id FROM drafts WHERE status IN ('published', 'ended')").fetchall()
        changed = 0
        # Verkaufte SKUs je Nutzer über die Bestell-API (das unterscheidet
        # „wirklich verkauft" von „nur abgelaufen")
        sold_skus: dict[int, set] = {}
        buyer_offers_cache: dict[int, list] = {}

        async def skus_for(uid: int) -> set:
            if uid not in sold_skus:
                s: set = set()
                try:
                    resp = await ebay.request(
                        "GET", f"{EBAY_API}/sell/fulfillment/v1/order",
                        params={"limit": "200"}, user_id=uid)
                    resp.raise_for_status()
                    for o in resp.json().get("orders", []):
                        for li in o.get("lineItems", []):
                            if li.get("sku"):
                                s.add(li["sku"])
                            if li.get("legacyItemId"):
                                s.add(str(li["legacyItemId"]))
                except Exception as e:  # noqa: BLE001
                    err = str(e)
                    # 403 = typisch Scope fehlt. Marke bei Erfolg wieder löschen (B2).
                    if "403" in err or "Forbidden" in err or "forbidden" in err.lower():
                        store.kv_set(f"ebay_fulfillment_fehlt_{uid}", {
                            "ts": time.time(),
                            "detail": "Orders-API 403 — eBay neu verbinden",
                        })
                        log.warning(
                            "Sales-Sync: Orders für %s nicht lesbar (403) "
                            "— eBay neu verbinden. %s", uid, e)
                    else:
                        log.warning("Sales-Sync: Orders für %s nicht lesbar: %s", uid, e)
                else:
                    with store._lock:  # noqa: SLF001
                        store._conn.execute(  # noqa: SLF001
                            "DELETE FROM kv WHERE key = ?",
                            (f"ebay_fulfillment_fehlt_{uid}",))
                        store._conn.commit()  # noqa: SLF001
                sold_skus[uid] = s
            return sold_skus[uid]

        async def offers_for(uid: int) -> list:
            if uid not in buyer_offers_cache:
                buyer_offers_cache[uid] = await get_active_buyer_offers(ebay, uid)
            return buyer_offers_cache[uid]

        def mark_item_sold(draft_id: str) -> None:
            row2 = store._conn.execute(  # noqa: SLF001
                "SELECT id, account_id, data FROM collection_items").fetchall()
            for it in row2:
                d2 = json.loads(it["data"])
                if d2.get("draft_id") == draft_id and not d2.get("sold_ts"):
                    d2["sold_ts"] = time.time()
                    col_save(it["id"], it["account_id"], d2)

        for r in rows:
            draft = store.get_draft(r["id"])
            if not draft or not draft.get("offer_id"):
                continue
            uid = draft["chat_id"]
            if only_account and uid != uid_for(only_account):
                continue
            if draft.get("status") == "ended":
                # Rückwirkend: war das ein VERKAUF? (Bestell-API weiß es)
                skus = await skus_for(uid)
                if (draft.get("sku") in skus
                        or str(draft.get("listing_id") or draft.get("item_id") or "") in skus):
                    if draft.get("ended_reason") != "Verkauft":
                        draft["ended_reason"] = "Verkauft"
                        store.update_draft(r["id"], draft)
                        changed += 1
                    mark_item_sold(r["id"])
                continue
            try:
                resp = await ebay.request(
                    "GET", f"{EBAY_API}/sell/inventory/v1/offer/{draft['offer_id']}",
                    user_id=uid)
                if resp.status_code == 404:
                    status = "GONE"
                    data = {}
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    status = ((data.get("listing") or {}).get("listingStatus")
                              or data.get("status") or "").upper()
            except Exception as e:  # noqa: BLE001
                log.warning("Sales-Sync: Offer %s nicht prüfbar: %s", draft.get("offer_id"), e)
                continue
            if status in ("ACTIVE", "PUBLISHED"):
                # Nach den awaits FRISCH lesen — sonst überschreibt der Sync
                # eingetippte Preise / Status (AGENTS.md + Claude-Review A1).
                frisch = store.get_draft(r["id"])
                if not frisch:
                    continue
                st = frisch.get("status") or ""
                if st in ("ended", "publishing", "ending"):
                    continue
                dirty = False
                live_price = live_price_from_offer(data) if data else None
                if (live_price and not frisch.get("price_dirty")
                        and str(frisch.get("price") or "") != live_price):
                    frisch["price"] = live_price
                    frisch["ebay_price"] = live_price
                    dirty = True
                elif live_price and not frisch.get("ebay_price"):
                    frisch["ebay_price"] = live_price
                    dirty = True
                lid = str((data.get("listing") or {}).get("listingId")
                          or frisch.get("listing_id") or frisch.get("item_id") or "")
                if lid and str(frisch.get("listing_id") or "") != lid:
                    frisch["listing_id"] = lid
                    dirty = True
                all_bo = await offers_for(uid)
                # Nochmal frisch — GetBestOffers kann dauern
                frisch = store.get_draft(r["id"]) or frisch
                if (frisch.get("status") or "") in ("ended", "publishing", "ending"):
                    continue
                if all_bo is None:
                    # Call fehlgeschlagen — angezeigte Vorschläge behalten (B3)
                    mine = frisch.get("buyer_offers") or []
                else:
                    mine = [o for o in all_bo
                            if o.get("listing_id") and str(o.get("listing_id")) == lid]
                prev = frisch.get("buyer_offers") or []
                if mine != prev:
                    frisch["buyer_offers"] = mine
                    dirty = True
                frisch["ebay_synced_at"] = time.time()
                store.update_draft(r["id"], frisch)
                if dirty:
                    changed += 1
                    if uid >= 10 ** 15:
                        notify(uid - 10 ** 15, "sales")
                continue
            # Listing nicht mehr aktiv — frisch lesen, Endzustände respektieren
            frisch = store.get_draft(r["id"])
            if not frisch:
                continue
            if (frisch.get("status") or "") in ("ended", "publishing"):
                continue
            skus = await skus_for(uid)
            frisch = store.get_draft(r["id"]) or frisch
            if (frisch.get("status") or "") in ("ended", "publishing"):
                continue
            is_sold = (status == "OUT_OF_STOCK"
                       or frisch.get("sku") in skus
                       or str(frisch.get("listing_id") or frisch.get("item_id") or "") in skus)
            frisch["status"] = "ended"
            frisch["ended_reason"] = "Verkauft" if is_sold else f"Beendet ({status})"
            frisch["buyer_offers"] = []
            store.update_draft(r["id"], frisch)
            if is_sold:
                mark_item_sold(r["id"])
            changed += 1
            if uid >= 10 ** 15:
                notify(uid - 10 ** 15, "item", None)
            log.warning("Sales-Sync: Listing %s -> ended (%s)", r["id"], status)
        if changed:
            log.warning("Sales-Sync: %d Listings aktualisiert", changed)
        return changed

    async def periodic_sales_sync():
        await asyncio.sleep(120)
        while True:
            try:
                await sync_sales_status()
            except Exception:  # noqa: BLE001
                log.exception("Sales-Sync-Runde fehlgeschlagen")
            await asyncio.sleep(30 * 60)

    async def ki_gesundheitswache():
        """Prüft eine ausgefallene KI-Quelle aktiv auf Genesung.

        Ohne diesen Dienst würde die Wiederaufnahme erst durch einen neuen
        Nutzer-Scan ausgelöst — genau das Warten, das Sven am 04.08. erlebt
        hat. Hier fragt das System selbst nach, mit wachsendem Abstand, und
        weckt die wartende Arbeit, sobald die Quelle antwortet."""
        from web import health
        await asyncio.sleep(30)
        while True:
            try:
                q = health.quelle("ki")
                if not q.gesund and time.time() >= q.naechster_test:
                    from anthropic import AsyncAnthropic
                    try:
                        c = AsyncAnthropic(api_key=cfg.anthropic_api_key, timeout=20.0,
                                           max_retries=0)
                        await c.messages.create(
                            model="claude-haiku-4-5-20251001", max_tokens=4,
                            messages=[{"role": "user", "content": "ok"}])
                        health.melde("ki", None)
                    except Exception as e:  # noqa: BLE001
                        health.melde("ki", e)
            except Exception:  # noqa: BLE001
                log.exception("Gesundheitswache: Durchlauf fehlgeschlagen")
            await asyncio.sleep(20)

    async def rescue_stuck_scans():
        """Dauerdienst: liegengebliebene Scans wieder anstoßen.

        Drei Fälle: (1) „analyzing" seit über 10 Minuten — abgerissen,
        (2) „error" ohne Ergebnis — der alte Rettungsfall, (3) „waiting" —
        pausiert wegen Infrastruktur-Ausfall.

        Der Fall (3) wird NUR angefasst, wenn die Quelle wieder gesund ist —
        sonst rennt die Rettung im Kreis. Nach einer Genesung läuft sie
        SOFORT los statt am Ende der 5-Minuten-Runde."""
        from web import health
        await asyncio.sleep(5)
        while True:
            try:
                ki_ok = health.quelle("ki").gesund
                genesen = health.genesung_abholen("ki")
                if genesen:
                    log.warning("Scan-Rettung: KI ist wieder da — wartende Stücke werden geweckt")
                rows = store._conn.execute(  # noqa: SLF001
                    "SELECT id, account_id, data, updated_at FROM collection_items").fetchall()
                for r in rows:
                    try:
                        d = json.loads(r["data"])
                    except Exception:  # noqa: BLE001
                        continue
                    st = d.get("status")
                    if st == "waiting":
                        if not ki_ok:
                            continue          # Quelle noch krank — weiter warten
                        wartezeit = 0         # nach Genesung sofort
                    elif st == "analyzing" or (
                            st == "error" and not d.get("analysis") and d.get("photos")):
                        wartezeit = 600       # nur wirklich Liegengebliebenes
                    else:
                        continue
                    if time.time() - (r["updated_at"] or 0) < wartezeit:
                        continue
                    account = store.get_account(r["account_id"])
                    if not account:
                        continue
                    d["status"], d["error"] = "analyzing", None
                    d.pop("wartet_seit", None)
                    col_save(r["id"], r["account_id"], d)
                    enqueue_scan(account, r["id"])
                    log.info("Scan-Rettung: Analyse neu gestartet für %s (war %s)", r["id"], st)
            except Exception:  # noqa: BLE001
                log.exception("Scan-Rettung: Durchlauf fehlgeschlagen")
            # Kurzer Takt, solange etwas wartet — sonst der ruhige 5-Minuten-Takt
            wartende = store._conn.execute(  # noqa: SLF001
                "SELECT COUNT(*) c FROM collection_items "
                "WHERE json_extract(data, '$.status') = 'waiting'").fetchone()["c"]
            await asyncio.sleep(20 if wartende else 300)

    async def rescue_stuck_drafts():
        """Dauerdienst: Entwurfs-Pipelines, die ein Server-Neustart abgerissen
        hat, ehrlich auf Fehler setzen — die App zeigt dann den Retry an,
        statt ewig zu laden. Svens Ace-Entwurf hing so 11 Stunden in
        „analyzing" (03.08., Vorführung). Bewusst KEIN automatischer
        Neustart der Pipeline: an Entwürfen hängt echtes Geld, ein doppelt
        angestoßenes Listing wäre schlimmer als ein Retry-Knopf."""
        await asyncio.sleep(20)
        while True:
            try:
                drafts_retten_einmal()
            except Exception:  # noqa: BLE001
                log.exception("Draft-Rettung: Durchlauf fehlgeschlagen")
            await asyncio.sleep(300)

    def drafts_retten_einmal() -> int:
        """Ein Rettungs-Durchlauf; gibt die Zahl der geretteten Entwürfe zurück."""
        gerettet = 0
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT id, updated_at FROM drafts "
            "WHERE status IN ('downloading', 'analyzing')").fetchall()
        for r in rows:
            if time.time() - (r["updated_at"] or 0) < 20 * 60:
                continue                  # läuft vielleicht wirklich noch
            d = store.get_draft(r["id"])
            if not d:
                continue
            d["status"] = "error"
            d["error"] = ("Der Vorgang wurde unterbrochen. "
                          "Tipp auf das Stück und stoße das Listing neu an.")
            store.update_draft(r["id"], d)
            gerettet += 1
            log.warning("Draft-Rettung: %s hing seit %.0f min — auf error gesetzt",
                        r["id"], (time.time() - (r["updated_at"] or 0)) / 60)
        return gerettet
    # Für Tests erreichbar machen — build_router läuft einmal pro Prozess
    globals()["drafts_retten_einmal"] = drafts_retten_einmal

    @router.on_event("startup")
    async def _start_refresher():
        # Papierkorb-Pflege: gelöschte Items nach 30 Tagen endgültig entfernen
        def _purge_trash():
            trash_root = COL_DIR / "_trash"
            if not trash_root.exists():
                return
            for d in trash_root.iterdir():
                try:
                    if d.is_dir() and time.time() - d.stat().st_mtime > 30 * 86400:
                        shutil.rmtree(d, ignore_errors=True)
                except OSError:
                    pass
        _purge_trash()
        _spawn(periodic_refresh())
        _spawn(rescue_stuck_scans())
        _spawn(rescue_stuck_drafts())
        _spawn(ki_gesundheitswache())
        _spawn(_scan_worker(1))
        _spawn(_scan_worker(2))
        _spawn(periodic_sales_sync())

        async def _warm_model():
            def _load():
                try:
                    from web import cardscan as _c
                    from rembg import new_session
                    if _c._rembg_session is None:
                        _c._rembg_session = new_session("birefnet-general")
                except Exception:  # noqa: BLE001
                    log.exception("Modell-Warmup fehlgeschlagen")
            await asyncio.get_running_loop().run_in_executor(None, _load)
            log.warning("BiRefNet vorgeladen — Erstscan startet ohne Wartezeit")
        _spawn(_warm_model())

    @router.post("/collection/adopt/{draft_id}")
    async def adopt_draft(request: Request, draft_id: str):
        """Ein einzelnes (altes) Listing ohne Sammlungsstück in die Sammlung übernehmen —
        Ein-Objekt-Prinzip: es gibt danach nur noch die Item-Detailansicht."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        existing = next((i for i in col_all(account["id"]) if i.get("draft_id") == draft_id), None)
        if existing:
            return {"ok": True, "item_id": existing["id"], "existed": True}
        d = own_draft(draft_id, account)
        if not d or not d.get("listing"):
            return JSONResponse({"error": "Listing nicht gefunden."}, status_code=404)
        listing = d["listing"]
        title = listing.get("title") or "Ohne Titel"
        item_id = uuid.uuid4().hex[:12]
        photos, remote = [], []
        local = [p for p in (d.get("photos") or []) if Path(p).exists()]
        if local:
            folder = COL_DIR / item_id
            folder.mkdir(parents=True, exist_ok=True)
            for i, src in enumerate(local):
                dst = folder / f"{i:02d}.jpg"
                try:
                    await asyncio.to_thread(shutil.copyfile, src, dst)
                    photos.append(str(dst))
                except OSError:
                    pass
        if not photos:
            remote = list(d.get("image_urls") or [])
        try:
            value = float(str(d.get("price")).replace(",", ".")) if d.get("price") else None
        except ValueError:
            value = None
        item = {
            "status": "ready", "name": title,
            "category": guess_category(title, d.get("category_name") or "",
                                       str(listing.get("aspects") or "")),
            "condition": listing.get("condition"), "graded": listing.get("graded_info"),
            "quantity": int(d.get("quantity") or 1), "est_value": value,
            "photos": photos, "remote_photos": remote,
            "analysis": listing, "draft_id": draft_id,
        }
        col_save(item_id, account["id"], item, create=True)
        snapshot_price(item_id, account["id"], value, "listing")
        return {"ok": True, "item_id": item_id, "existed": False}

    @router.post("/collection/import")
    async def import_listings(request: Request):
        """Bestehende (veröffentlichte) eBay-Listings als Sammlungs-Items übernehmen."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        existing_draft_ids = {i.get("draft_id") for i in col_all(account["id"]) if i.get("draft_id")}
        drafts = store.published_drafts_for_chat(uid_for(account), limit=200)
        imported = 0
        for d in drafts:
            if d["id"] in existing_draft_ids:
                continue
            listing = d.get("listing") or {}
            title = listing.get("title") or "Ohne Titel"
            item_id = uuid.uuid4().hex[:12]
            photos, remote = [], []
            local = [p for p in (d.get("photos") or []) if Path(p).exists()]
            if local:
                folder = COL_DIR / item_id
                folder.mkdir(parents=True, exist_ok=True)
                for i, src in enumerate(local):
                    dst = folder / f"{i:02d}.jpg"
                    try:
                        await asyncio.to_thread(shutil.copyfile, src, dst)
                        photos.append(str(dst))
                    except OSError:
                        pass
            if not photos:
                remote = list(d.get("image_urls") or [])
            try:
                value = float(str(d.get("price")).replace(",", ".")) if d.get("price") else None
            except ValueError:
                value = None
            item = {
                "status": "ready",
                "name": title,
                "category": guess_category(title, d.get("category_name") or "",
                                           str(listing.get("aspects") or "")),
                "condition": listing.get("condition"),
                "graded": listing.get("graded_info"),
                "quantity": int(d.get("quantity") or 1),
                "est_value": value,
                "photos": photos,
                "remote_photos": remote,
                "analysis": listing,
                "draft_id": d["id"],
            }
            col_save(item_id, account["id"], item, create=True)
            snapshot_price(item_id, account["id"], value, "listing")
            imported += 1
        return {"ok": True, "imported": imported}

    @router.get("/citem-photo/{item_id}/{idx}")
    async def get_citem_photo(request: Request, item_id: str, idx: int, f: str = "", w: int = 0):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "not found"}, status_code=404)
        photos = item.get("photos") or []
        if 0 <= idx < len(photos) and Path(photos[idx]).exists():
            tp = thumb_path(photos[idx], w)
            return FileResponse(tp, media_type=_MIME.get(Path(tp).suffix.lower(), "image/jpeg"))
        return JSONResponse({"error": "not found"}, status_code=404)

    # ------------------------------------------------------------ Dashboard, Verkauf, Alarme, Export

    @router.post("/account/delete")
    async def delete_account(request: Request):
        """DSGVO ab Tag 1: Konto löschen = alles weg (Items, Fotos, Drafts, Verlauf)."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        aid = account["id"]
        uid = uid_for(account)
        for i in col_all(aid):
            shutil.rmtree(COL_DIR / i["id"], ignore_errors=True)
        # „Vollständig" hieß bisher: ohne eBay-Refresh-Token (gewährt weiter
        # Zugriff aufs eBay-Konto!), ohne users-/listings-Zeilen, ohne Wallet,
        # ohne geparkte Fotos, Papierkorb, Avatare und Render-Hintergründe.
        # Ein Konto hat bis zu ZWEI Identitäten: die Telegram-ID (falls verknüpft)
        # und die synthetische App-ID. Der eBay-Token liegt nach dem Verbinden
        # unter BEIDEN Schlüsseln — nur einen zu löschen ließe ein gültiges
        # Refresh-Token zurück (Audit-Befund P1: Token-Leiche).
        uids = {uid, ACCOUNT_UID_OFFSET + aid}
        with store._lock:  # noqa: SLF001
            for tbl in ("collection_items", "price_history", "price_alerts", "app_chat"):
                store._conn.execute(f"DELETE FROM {tbl} WHERE account_id = ?", (aid,))  # noqa: SLF001
            for u in uids:
                store._conn.execute("DELETE FROM drafts WHERE chat_id = ?", (u,))  # noqa: SLF001
                store._conn.execute("DELETE FROM listings WHERE telegram_id = ?", (u,))  # noqa: SLF001
                store._conn.execute("DELETE FROM users WHERE telegram_id = ?", (u,))  # noqa: SLF001
                store._conn.execute("DELETE FROM kv WHERE key = ?", (f"ebay_user_token_{u}",))  # noqa: SLF001
            store._conn.execute(  # noqa: SLF001
                "DELETE FROM kv WHERE key IN (?, ?, ?, ?)",
                (f"premium_{aid}", f"scans_{aid}", f"wallet_{aid}",
                 f"wallet_provider_{aid}"))
            store._conn.execute("DELETE FROM accounts WHERE id = ?", (aid,))  # noqa: SLF001
            store._conn.commit()  # noqa: SLF001
        shutil.rmtree(STAGE_DIR / str(aid), ignore_errors=True)
        trash = COL_DIR / "_trash"
        if trash.exists():
            for t in trash.iterdir():
                try:
                    wem = json.loads((t / "item.json").read_text()).get("account_id")
                except (OSError, ValueError):
                    continue        # Alt-Einträge ohne Zuordnung räumt die 30-Tage-Routine
                if wem == aid:
                    shutil.rmtree(t, ignore_errors=True)
        from web.server import UPLOADS_DIR as _up
        for muster in (f"avatar-{aid}-*.jpg", f"bg-{aid}-*.jpg",
                       f"avatar-{aid}.jpg", f"bg-{aid}.jpg"):
            for f in _up.glob(muster):
                f.unlink(missing_ok=True)
        for f in COL_DIR.glob(f"render_*_{aid}.*"):
            f.unlink(missing_ok=True)
        log.info("Konto %s vollständig gelöscht (DSGVO)", aid)
        return {"ok": True, "deleted": True}

    @router.get("/events")
    async def sse_events(request: Request):
        """Server-Push: stehende Verbindung pro Gerät. Regel für Konsistenz:
        bei (Re-)Connect lädt der Client einmal voll — danach reichen Pushes."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        subs = _subs.setdefault(account["id"], dict())
        if len(subs) >= 5:
            # Nicht abweisen, sondern die ÄLTESTE Verbindung verdrängen: auf dem
            # iPhone sterben SSE-Verbindungen oft still (App-Wechsel ohne FIN) —
            # die Slots waren dann von Zombies belegt, und das 429 an den echten
            # Client machte den Live-Sync für die ganze Sitzung stumm.
            aelteste = min(subs, key=subs.get)
            try:
                aelteste.put_nowait({"__evict": True})
            except asyncio.QueueFull:
                pass
            subs.pop(aelteste, None)
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        subs[q] = time.time()

        async def gen():
            try:
                yield "retry: 3000\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        # Ping alle 10 s statt 25: still gekappte Verbindungen
                        # (Funkloch, iOS-Suspend) fallen dreimal schneller auf.
                        ev = await asyncio.wait_for(q.get(), timeout=10)
                        if isinstance(ev, dict) and ev.get("__evict"):
                            break
                        yield f"data: {json.dumps(ev)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                _subs.get(account["id"], {}).pop(q, None)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    @router.get("/systemstatus")
    async def systemstatus(request: Request):
        """Ein Satz statt zehn roter Kacheln: Klemmt eine Außenquelle, sagt es
        die App EINMAL oben — samt Zahl der wartenden Stücke, die von selbst
        weiterlaufen (Svens Auftrag 04.08.)."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        from web import health
        st = health.status()
        st["wartende"] = store._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) c FROM collection_items "
            "WHERE account_id = ? AND json_extract(data, '$.status') = 'waiting'",
            (account["id"],)).fetchone()["c"]
        return st

    @router.get("/dashboard")
    async def dashboard(request: Request):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        items = [item_public(i, account) for i in col_all(account["id"])]
        owned = [i for i in items if not i["wishlist"] and i["draft_status"] != "published" and not i.get("sold")]
        total = round(sum((i["est_value"] or 0) * i["quantity"] for i in owned), 2)
        hist = portfolio_history(account["id"])

        def delta_days(days: int) -> float | None:
            if not hist:
                return None
            import datetime
            cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
            past = [p for p in hist if p["day"] <= cutoff]
            base = past[-1]["value"] if past else (hist[0]["value"] if len(hist) > 1 else None)
            return round(total - base, 2) if base is not None else None

        # Top-Mover (7 Tage)
        week_ago = time.time() - 7 * 86400
        movers = []
        for i in owned:
            if i["est_value"] is None:
                continue
            old = store._conn.execute(  # noqa: SLF001
                "SELECT value FROM price_history WHERE item_id = ? AND ts <= ? "
                "ORDER BY ts DESC LIMIT 1", (i["id"], week_ago)).fetchone()
            if old and old["value"]:
                d = round(i["est_value"] - old["value"], 2)
                i["delta7"] = d  # für Kategorien-/Top-Aggregation weiter unten
                if abs(d) >= 0.01:
                    movers.append({"id": i["id"], "name": i["name"],
                                   "photo": (i.get("card") or {}).get("image") or (i["photos"] or [None])[0],
                                   "value": i["est_value"], "delta": d,
                                   "pct": round(d / old["value"] * 100, 1)})
        movers.sort(key=lambda m: -abs(m["delta"]))

        drafts = [d for d in (store.get_draft(r["id"]) for r in store._conn.execute(  # noqa: SLF001
            "SELECT id FROM drafts WHERE chat_id = ?", (uid_for(account),)).fetchall()) if d]
        active = sum(1 for d in drafts if d.get("status") == "published")
        pending = sum(1 for d in drafts if d.get("status") in ("ready", "dry_run_done", "error", "uncertain"))
        value_active = 0.0
        for dd in drafts:
            if dd.get("status") == "published" and dd.get("price"):
                try:
                    value_active += float(str(dd["price"]).replace(",", "."))
                except ValueError:
                    pass

        alerts = [dict(r) for r in store._conn.execute(  # noqa: SLF001
            "SELECT * FROM price_alerts WHERE account_id = ? AND triggered_at IS NOT NULL "
            "ORDER BY triggered_at DESC LIMIT 5", (account["id"],)).fetchall()]
        by_id = {i["id"]: i for i in items}
        triggered = [{"item_id": a["item_id"], "name": by_id[a["item_id"]]["name"],
                      "threshold": a["threshold"], "direction": a["direction"],
                      "value": by_id[a["item_id"]]["est_value"]}
                     for a in alerts if a["item_id"] in by_id]

        # Wertentwicklung pro Kategorie (wie Collectr „Collections")
        cat_values: dict[str, dict] = {}
        for i in owned:
            c = cat_values.setdefault(i["category"], {"value": 0.0, "delta7": 0.0, "count": 0})
            c["value"] += (i["est_value"] or 0) * i["quantity"]
            c["delta7"] += (i.get("delta7") or 0) * i["quantity"]
            c["count"] += 1
        categories = sorted(
            ({"name": k, "value": round(v["value"], 2), "delta7": round(v["delta7"], 2),
              "count": v["count"]} for k, v in cat_values.items()),
            key=lambda c: -c["value"])

        top = sorted((i for i in owned if i["est_value"]), key=lambda i: -i["est_value"])[:4]

        recent = sorted(owned, key=lambda i: -(i["created_at"] or 0))[:8]
        return {
            "total_value": total,
            "categories_value": categories,
            "top_items": [{"id": i["id"], "name": i["name"], "value": i["est_value"],
                           "delta7": i.get("delta7"), "condition": i["condition"],
                           "photo": (i.get("card") or {}).get("image") or (i["photos"] or [None])[0],
                           "qty": i["quantity"]}
                          for i in top],
            "grand_total": total,
            "deltas": {"d1": delta_days(1), "d7": delta_days(7), "d30": delta_days(30)},
            "history": portfolio_history(account["id"], days=365),
            "count": len(owned),
            "movers_up": [m for m in movers if m["delta"] > 0][:3],
            "movers_down": [m for m in movers if m["delta"] < 0][:3],
            "recent": [{"id": i["id"], "name": i["name"],
                        "photo": (i.get("card") or {}).get("image") or (i["photos"] or [None])[0],
                        "value": i["est_value"], "status": i["status"]} for i in recent],
            "sales": {"active": active, "pending": pending, "value_active": round(value_active, 2)},
            "alerts_triggered": triggered,
        }

    @router.get("/sales")
    async def sales(request: Request, refresh: int = 0):
        """Verkaufs-Hub: alle Listing-Entwürfe/aktiven/beendeten Verkäufe."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        # Beim Reinschauen frisch abgleichen (Standard 90 s; mit refresh=1 alle 30 s)
        last = store.kv_get(f"sales_sync_ts_{account['id']}") or {}
        throttle = 30 if refresh else 90
        if time.time() - last.get("t", 0) > throttle:
            store.kv_set(f"sales_sync_ts_{account['id']}", {"t": time.time()})
            _spawn(sync_sales_status(account))
        uid = uid_for(account)
        item_by_draft = {i.get("draft_id"): i for i in col_all(account["id"]) if i.get("draft_id")}
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT id FROM drafts WHERE chat_id = ? ORDER BY updated_at DESC", (uid,)).fetchall()
        buckets = {"draft": [], "active": [], "ended": []}
        value_active = 0.0
        for r in rows:
            d = store.get_draft(r["id"])
            if not d or not d.get("listing"):
                continue
            status = d.get("status")
            bucket = ("active" if status == "published"
                      else "ended" if status == "ended"
                      else "draft" if status in ("ready", "dry_run_done", "error", "uncertain")
                      else None)
            if not bucket:
                continue
            item = item_by_draft.get(d["id"])
            photo = None
            local = [p for p in (d.get("photos") or []) if Path(p).exists()]
            if local:
                photo = f"/api/app/photo/{d['id']}/0?f={Path(local[0]).name}"
            elif d.get("image_urls"):
                photo = d["image_urls"][0]
            elif item and item.get("photos"):
                photo = f"/api/app/citem-photo/{item['id']}/0"
            buyer_offers = d.get("buyer_offers") or []
            top_offer = None
            if buyer_offers:
                try:
                    top_offer = max(float(o.get("price") or 0) for o in buyer_offers)
                except (TypeError, ValueError):
                    top_offer = None
            entry = {
                "draft_id": d["id"], "title": d["listing"].get("title"),
                "price": d.get("price"), "format": d.get("format", "FIXED_PRICE"),
                "status": status, "photo": photo, "item_url": d.get("item_url"),
                "item_id": item["id"] if item else None,
                "buyer_offers": buyer_offers,
                "offer_count": len(buyer_offers),
                "top_offer": f"{top_offer:.2f}" if top_offer else None,
                "ebay_synced_at": d.get("ebay_synced_at"),
            }
            buckets[bucket].append(entry)
            if bucket == "active":
                try:
                    value_active += float(str(d.get("price") or 0).replace(",", "."))
                except ValueError:
                    pass
        # Verkaufshistorie (Log-Tabelle: echte Veröffentlichungen)
        month_start = time.time() - 30 * 86400
        published_30d = store._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) FROM listings WHERE telegram_id = ? AND dry_run = 0 AND created_at > ?",
            (uid, month_start)).fetchone()[0]
        reconnect = bool(
            store.kv_get(f"ebay_fulfillment_fehlt_{uid}")
            or (account.get("telegram_id")
                and store.kv_get(f"ebay_fulfillment_fehlt_{account['telegram_id']}"))
            or store.kv_get(f"ebay_fulfillment_fehlt_{ACCOUNT_UID_OFFSET + account['id']}"))
        return {"drafts": buckets["draft"], "active": buckets["active"], "ended": buckets["ended"],
                "stats": {"active": len(buckets["active"]), "value_active": round(value_active, 2),
                          "drafts": len(buckets["draft"]), "published_30d": published_30d},
                "ebay_needs_reconnect": reconnect,
                "synced_at": (store.kv_get(f"sales_sync_ts_{account['id']}") or {}).get("t")}

    @router.post("/collection/item/{item_id}/alert")
    async def set_alert(request: Request, item_id: str, body: AlertBody):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        if body.threshold is None:
            with store._lock:  # noqa: SLF001
                store._conn.execute("DELETE FROM price_alerts WHERE item_id = ? AND account_id = ?", (item_id, account["id"]))  # noqa: SLF001
                store._conn.commit()  # noqa: SLF001
            return {"ok": True, "alert": None}
        threshold = parse_price(body.threshold)
        if not threshold:
            return JSONResponse({"error": "Ungültiger Schwellwert. Beispiel: 25"}, status_code=400)
        direction = body.direction if body.direction in ("above", "below") else "above"
        with store._lock:  # noqa: SLF001
            store._conn.execute(  # noqa: SLF001
                "INSERT INTO price_alerts (item_id, account_id, threshold, direction, created_at, triggered_at) "
                "VALUES (?, ?, ?, ?, ?, NULL) "
                "ON CONFLICT(item_id) DO UPDATE SET threshold=excluded.threshold, "
                "direction=excluded.direction, triggered_at=NULL",
                (item_id, account["id"], float(threshold), direction, time.time()))
            store._conn.commit()  # noqa: SLF001
        return {"ok": True, "alert": {"threshold": float(threshold), "direction": direction}}

    @router.get("/export")
    async def export_collection(request: Request):
        """Sammlungs-Backup als JSON-Download (Datenexport)."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        items = [item_public(i, account) for i in col_all(account["id"])]
        payload = json.dumps({"exported_at": time.time(), "account": account["email"],
                              "items": items}, ensure_ascii=False, indent=1)
        return Response(content=payload, media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=sero-sammlung.json"})

    RENDER_COLORS = {"white": "#FFFFFF", "warm": "#F5EFE3", "black": "#0B0B0D"}

    def _set_render_bg(account_id: int, path: str | None) -> None:
        with store._lock:  # noqa: SLF001
            store._conn.execute("UPDATE accounts SET render_bg_path = ? WHERE id = ?",  # noqa: SLF001
                                (path, account_id))
            store._conn.commit()  # noqa: SLF001

    @router.post("/settings/render")
    async def set_render_bg(request: Request, body: RenderBgBody):
        """Listing-Hintergrund: Weiß/Warmweiß/Schwarz (erzeugte Farbfläche) oder
        eigenes Logo-Bild (separat hochgeladen)."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        if body.mode == "logo":
            p = COL_DIR / f"render_bg_{account['id']}.png"
            if not p.exists():
                return JSONResponse({"error": "Bitte zuerst ein Hintergrund-/Logo-Bild "
                                              "hochladen."}, status_code=400)
            _set_render_bg(account["id"], str(p))
        elif body.mode in RENDER_COLORS:
            from PIL import Image
            p = COL_DIR / f"render_color_{account['id']}.png"
            Image.new("RGB", (1600, 1600), RENDER_COLORS[body.mode]).save(p, "PNG")
            _set_render_bg(account["id"], str(p))
        else:
            return JSONResponse({"error": "Unbekannter Modus."}, status_code=400)
        store.kv_set(f"render_mode_{account['id']}", {"mode": body.mode})
        return {"ok": True, "mode": body.mode}

    @router.post("/settings/render-logo")
    async def upload_render_logo(request: Request, files: list[UploadFile] = File(...)):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        raw = await _read_limited(files[0], 15 * 1024 * 1024)
        if raw is None:
            return JSONResponse({"error": "Bild zu groß (max. 15 MB)."}, status_code=400)
        from PIL import Image, ImageOps
        import io
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        except Exception:  # noqa: BLE001 — kaputtes Bild ist kein Server-Fehler
            return JSONResponse({"error": "Bild konnte nicht gelesen werden."}, status_code=400)
        img.thumbnail((1600, 1600))
        canvas = Image.new("RGB", (1600, 1600), "#FFFFFF")
        canvas.paste(img, ((1600 - img.width) // 2, (1600 - img.height) // 2))
        p = COL_DIR / f"render_bg_{account['id']}.png"
        canvas.save(p, "PNG")
        _set_render_bg(account["id"], str(p))
        store.kv_set(f"render_mode_{account['id']}", {"mode": "logo"})
        return {"ok": True}

    # Ein zweiter Tipp auf „Alle listen" (oder ein zweites Gerät) startete einen
    # zweiten Durchlauf über dieselben Drafts — mit frischen SKUs, also echten
    # Doppel-Listings. Eine Sperre pro Konto, solange ein Lauf aktiv ist.
    _bulk_aktiv: set[int] = set()

    @router.post("/sales/publish-drafts")
    async def publish_all_drafts(request: Request):
        """Bulk: alle fertigen Entwürfe nacheinander live stellen — mit denselben
        Prüfungen wie der Einzel-Upload. Vorher umging der Bulk-Weg Preis-,
        Kategorie-, Plan- und Monatslimit-Prüfung komplett."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        uid = uid_for(account)
        if uid in _bulk_aktiv:
            return JSONResponse({"error": "Es läuft bereits ein Bulk-Listing — "
                                          "bitte warten, bis es fertig ist."}, status_code=409)
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT id FROM drafts WHERE chat_id = ? AND status = 'ready'",
            (uid,)).fetchall()
        if not rows:
            return {"ok": True, "count": 0}
        _bulk_aktiv.add(uid)

        async def run_all(ids):
            geschafft, fehler = 0, []
            try:
                for did in ids:
                    draft = store.get_draft(did)
                    if not draft or draft.get("status") == "published":
                        continue
                    titel = ((draft.get("listing") or {}).get("title")
                             or "Unbenannter Entwurf")[:60]
                    # Dieselben Hürden wie beim Einzel-Upload
                    if not draft.get("price"):
                        fehler.append((titel, "kein Preis festgelegt"))
                        continue
                    if not draft.get("category_id"):
                        fehler.append((titel, "keine Kategorie bestimmt"))
                        continue
                    if not is_admin(account):
                        plan = account.get("plan")
                        if plan not in PLAN_LIMITS:
                            fehler.append((titel, "kein aktiver Plan"))
                            break
                        limit = PLAN_LIMITS[plan]
                        # Live lesen: jeder Publish erhöht den Zähler
                        if limit is not None and store.listings_this_month(uid) >= limit:
                            fehler.append((titel, f"Monatslimit ({limit}) erreicht"))
                            break
                    try:
                        await app_run_upload(account, did)
                    except Exception:  # noqa: BLE001
                        log.exception("Bulk-Publish: %s fehlgeschlagen", did)
                    nachher = store.get_draft(did) or {}
                    if nachher.get("status") in ("published", "dry_run_done"):
                        geschafft += 1
                    else:
                        fehler.append((titel, nachher.get("error_text") or "Fehler beim Listen"))
                    await asyncio.sleep(3)
            finally:
                _bulk_aktiv.discard(uid)
                text = f"Bulk fertig: {geschafft} von {len(ids)} gelistet."
                if fehler:
                    text += "\n\nNicht gelistet:\n" + "\n".join(
                        f"• {t} — {grund}" for t, grund in fehler[:10])
                chat_add(account["id"], "bot", "info", {"text": text})
                notify(account["id"], "sales")

        _spawn(run_all([r["id"] for r in rows]))
        return {"ok": True, "count": len(rows)}

    @router.get("/settings")
    async def get_settings(request: Request):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        notif = store.kv_get(f"app_notif_{account['id']}")
        return {"notifications": True if notif is None else bool(notif),
                "language": "Deutsch", "currency": "EUR",
                # Derselbe Status wie beim Scan-Limit — nicht das tote kv-Flag
                "premium": scan_freigeschaltet(account),
                "scans_used": scan_count(account["id"]), "scans_limit": FREE_SCANS}

    @router.post("/settings")
    async def set_settings(request: Request, body: SettingsBody):
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        if body.notifications is not None:
            store.kv_set(f"app_notif_{account['id']}", bool(body.notifications))
        return {"ok": True}

    # ------------------------------------------------------------ Grading (PSA) + Markt

    @router.post("/collection/item/{item_id}/graded-market")
    async def graded_market(request: Request, item_id: str):
        """Echte PSA-10/9-Angebotspreise (eBay) für die identifizierte Karte."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        limited = app_bremse(account, "graded-market", 30)
        if limited:
            return limited
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        card = item.get("card") or {}
        name = card.get("name") or item.get("name")
        if not name:
            return JSONResponse({"error": "Karte noch nicht identifiziert."}, status_code=400)
        # Englischen Namen ggf. nachholen (Graded-Listings laufen fast immer englisch)
        if not card.get("name_en") and card.get("ref_id") and card.get("game") == "pokemon":
            try:
                import httpx as _hx
                async with _hx.AsyncClient(timeout=10) as c:
                    en = await c.get(f"https://api.tcgdex.net/v2/en/cards/{card['ref_id']}")
                    if en.status_code == 200 and (en.json() or {}).get("name"):
                        card["name_en"] = en.json()["name"]
                        item["card"] = card
            except Exception:  # noqa: BLE001
                pass
        out = {}
        for grade in ("10", "9"):
            variants = []
            if card.get("name_en"):
                variants.append(f"PSA {grade} {card['name_en']}")
            variants += [f"PSA {grade} {name}", f"{name} PSA {grade}"]
            for q in variants:
                r = await research_price(ebay, q)
                if r and r["count"] >= 3:
                    out[f"psa{grade}"] = {"median": r["median"], "count": r["count"],
                                          "query": q, "samples": (r.get("samples") or [])[:2]}
                    break
        # Bis zu 6 eBay-Suchen liegen zwischen Lesen und Schreiben — das komplette
        # alte Item zurückzuschreiben würde parallele Änderungen auslöschen.
        frisch = col_get(item_id, account)
        if frisch is None:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        frisch["graded_market"] = {**out, "ts": time.time()}
        col_save(item_id, account["id"], frisch)
        return frisch["graded_market"]

    @router.get("/cardsearch")
    async def cardsearch(request: Request, game: str = "pokemon", q: str = ""):
        """Manuelle Kartensuche für den Korrektur-Flow — je Spiel die passende Quelle."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        q = q.strip()
        if len(q) < 2:
            return {"results": []}
        import httpx as _hx
        results = []
        try:
            if game == "pokemon":
                async with _hx.AsyncClient(timeout=12) as c:
                    for lang in ("de", "en"):
                        r = await c.get(f"https://api.tcgdex.net/v2/{lang}/cards", params={"name": q})
                        hits = r.json() if r.status_code == 200 else []
                        for h in hits[:8]:
                            img = h.get("image")
                            results.append({
                                "label": h.get("name"), "sub": f"Nr. {h.get('localId')} · {h['id']}",
                                "image": f"{img}/low.webp" if img else None,
                                "match": {"game": "pokemon", "name": h.get("name"),
                                          "number": h.get("localId"), "ref_id": h["id"]},
                            })
                        if results:
                            break
            elif game == "magic":
                async with _hx.AsyncClient(timeout=12) as c:
                    r = await c.get("https://api.scryfall.com/cards/search",
                                    params={"q": q, "unique": "prints"})
                    for h in (r.json().get("data") or [])[:10] if r.status_code == 200 else []:
                        results.append({
                            "label": h.get("printed_name") or h.get("name"),
                            "sub": f"{h.get('set_name')} · {h.get('collector_number')}",
                            "image": (h.get("image_uris") or {}).get("small"),
                            "match": {"game": "magic", "name": h.get("name"),
                                      "number": h.get("collector_number")},
                        })
            elif game == "yugioh":
                async with _hx.AsyncClient(timeout=12) as c:
                    r = await c.get("https://db.ygoprodeck.com/api/v7/cardinfo.php",
                                    params={"fname": q})
                    for h in ((r.json() or {}).get("data") or [])[:10] if r.status_code == 200 else []:
                        imgs = h.get("card_images") or [{}]
                        results.append({
                            "label": h.get("name"), "sub": h.get("type", ""),
                            "image": imgs[0].get("image_url_small"),
                            "match": {"game": "yugioh", "name": h.get("name")},
                        })
            else:
                from web.tcgcsv import category_ids, ensure_index, search_products
                cats = await category_ids(store, game)
                for cat in cats:
                    await ensure_index(store, cat)
                for p in search_products(store, cats, q):
                    results.append({
                        "label": p["name"], "sub": p["group_name"], "image": p.get("image"),
                        "match": {"game": game, "name": p["name"],
                                  "tcgcsv": {"product_id": p["product_id"]}},
                    })
        except Exception:  # noqa: BLE001
            log.exception("cardsearch fehlgeschlagen (%s, %r)", game, q)
        return {"results": results[:12]}

    @router.post("/collection/item/{item_id}/match")
    async def match_item(request: Request, item_id: str, body: MatchBody):
        """Vom Nutzer gewählte Karte fest zuordnen — überschreibt die Auto-Erkennung."""
        account = require_account(request)
        if isinstance(account, JSONResponse):
            return account
        item = col_get(item_id, account)
        if not item:
            return JSONResponse({"error": "Artikel nicht gefunden."}, status_code=404)
        item["card_info"] = {"single": True, "game": body.game, "name": body.name,
                             "number": body.number, "set_total": None,
                             "manual": True,
                             **({"tcgcsv": body.tcgcsv} if body.tcgcsv else {})}
        item.pop("card", None)
        item.pop("price_detail", None)
        col_save(item_id, account["id"], item)
        await refresh_item_price(account, item, force=True)
        out = item_public(col_get(item_id, account), account)
        out["history"] = item_history(item_id)
        return out


    return router
