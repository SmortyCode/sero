"""SQLite-Storage: Drafts, OAuth-Tokens, Taxonomy-Cache, Listing-Log.

Eine Datei (data.db, 0600). Drafts überleben Bot-Neustarts.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from bot.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS aspects_cache (
    category_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    telegram_id INTEGER,
    plan TEXT NOT NULL DEFAULT 'trial',
    trial_until REAL,
    stripe_customer_id TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS link_codes (
    code TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    ebay_username TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    merchant_location_key TEXT,
    fulfillment_policy_id TEXT,
    payment_policy_id TEXT,
    return_policy_id TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    listing_id TEXT,
    offer_id TEXT,
    title TEXT,
    price TEXT,
    dry_run INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Path = DB_PATH):
        self._lock = threading.Lock()
        existed = path.exists()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        # Drafts werden ständig nach Konto und Status gefiltert — ohne Index
        # heißt das: Full Scan bei jedem Verkaufs-Tab und jedem Bulk-Lauf.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_drafts_chat ON drafts (chat_id, status)")
        self._ensure_column("listings", "telegram_id", "INTEGER")
        # Verkaufs-Statistik filtert listings nach Konto + dry_run + Zeit —
        # ohne Index ein Full Scan je Dashboard-Aufruf (Full-Scan-Befund 03.08.).
        # NACH _ensure_column: Alt-Datenbanken bekommen die Spalte erst dort.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_listings_tid ON listings (telegram_id, dry_run, created_at)")
        self._ensure_column("users", "render_color", "TEXT")
        self._ensure_column("users", "business", "INTEGER DEFAULT 0")  # gewerblich = Provision überall
        self._ensure_column("accounts", "username", "TEXT")
        self._ensure_column("accounts", "display_name", "TEXT")
        self._ensure_column("accounts", "avatar_path", "TEXT")
        self._ensure_column("accounts", "render_bg_path", "TEXT")
        self._ensure_column("accounts", "ebay_shop", "TEXT")
        self._conn.commit()
        if not existed:
            os.chmod(path, 0o600)

    def _ensure_column(self, table: str, col: str, decl: str) -> None:
        cols = [r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

    # --- kv (Tokens, Category-Tree-ID, …) ---

    def kv_set(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, json.dumps(value), time.time()),
            )
            self._conn.commit()

    def kv_get(self, key: str) -> Any:
        row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else None

    # --- Accounts (Website-Kunden: E-Mail-Identität, Trial/Plan, Telegram-Zuordnung) ---

    TRIAL_DAYS = 14

    def create_account(self, email: str) -> dict:
        email = email.strip().lower()
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM accounts WHERE email = ?", (email,)
            ).fetchone()
            if existing:
                return dict(existing)
            now = time.time()
            cur = self._conn.execute(
                "INSERT INTO accounts (email, plan, trial_until, created_at) VALUES (?, 'trial', ?, ?)",
                (email, now + self.TRIAL_DAYS * 86400, now),
            )
            self._conn.commit()
            return self.get_account(cur.lastrowid)

    def get_account(self, account_id: int) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return dict(row) if row else None

    def get_account_by_email(self, email: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    def get_account_by_username(self, username: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE LOWER(username) = ?", (username.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    def get_account_by_identifier(self, identifier: str) -> Optional[dict]:
        """Login per E-Mail ODER Username."""
        if "@" in identifier:
            return self.get_account_by_email(identifier)
        return self.get_account_by_username(identifier)

    def get_account_by_telegram(self, telegram_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_account(self, account_id: int, **fields) -> None:
        if not fields:
            return
        with self._lock:
            sets = ", ".join(f"{k} = ?" for k in fields)
            self._conn.execute(
                f"UPDATE accounts SET {sets} WHERE id = ?", (*fields.values(), account_id)
            )
            self._conn.commit()

    def account_active(self, account: dict) -> bool:
        """Trial läuft noch oder bezahlter Plan aktiv."""
        if account.get("plan") in ("starter", "reseller", "shop"):
            return True
        return bool(account.get("trial_until") and account["trial_until"] > time.time())

    # --- Link-Codes (Website <-> Telegram/eBay-Verknüpfung) ---

    def create_link_code(self, account_id: int, purpose: str, ttl_s: float = 3600) -> str:
        code = f"L-{uuid.uuid4().int % 1000000:06d}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO link_codes (code, account_id, purpose, expires_at) VALUES (?, ?, ?, ?)",
                (code, account_id, purpose, time.time() + ttl_s),
            )
            self._conn.commit()
        return code

    def redeem_link_code(self, code: str, purpose: str) -> Optional[int]:
        """Gibt die account_id zurück und entwertet den Code."""
        with self._lock:
            row = self._conn.execute(
                "SELECT account_id, expires_at FROM link_codes WHERE code = ? AND purpose = ?",
                (code.strip().upper(), purpose),
            ).fetchone()
            if not row or row["expires_at"] < time.time():
                return None
            self._conn.execute("DELETE FROM link_codes WHERE code = ?", (code.strip().upper(),))
            self._conn.commit()
            return row["account_id"]

    # --- Users (Multi-Tenant: ein eBay-Konto pro Telegram-Nutzer) ---

    def get_user(self, telegram_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None

    def upsert_user(self, telegram_id: int, **fields) -> None:
        with self._lock:
            existing = self._conn.execute(
                "SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
            if existing:
                if fields:
                    sets = ", ".join(f"{k} = ?" for k in fields)
                    self._conn.execute(
                        f"UPDATE users SET {sets} WHERE telegram_id = ?",
                        (*fields.values(), telegram_id),
                    )
            else:
                cols = ["telegram_id", "created_at", *fields.keys()]
                self._conn.execute(
                    f"INSERT INTO users ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                    (telegram_id, time.time(), *fields.values()),
                )
            self._conn.commit()

    def user_policies(self, telegram_id: int) -> Optional[dict]:
        """Policies + Location eines Nutzers — None, wenn das Setup nicht komplett ist."""
        user = self.get_user(telegram_id)
        if not user:
            return None
        keys = ("merchant_location_key", "fulfillment_policy_id",
                "payment_policy_id", "return_policy_id")
        if not all(user.get(k) for k in keys):
            return None
        return {k: user[k] for k in keys}

    # --- Drafts ---

    def create_draft(self, chat_id: int, data: dict) -> str:
        draft_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO drafts (id, chat_id, status, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (draft_id, chat_id, data.get("status", "new"), json.dumps(data), now, now),
            )
            self._conn.commit()
        return draft_id

    def get_draft(self, draft_id: str) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["data"])
        data["id"] = row["id"]
        data["chat_id"] = row["chat_id"]
        data["created_at"] = row["created_at"]
        return data

    def update_draft(self, draft_id: str, data: dict) -> None:
        clean = {k: v for k, v in data.items() if k not in ("id", "chat_id", "created_at")}
        with self._lock:
            self._conn.execute(
                "UPDATE drafts SET data = ?, status = ?, updated_at = ? WHERE id = ?",
                (json.dumps(clean), clean.get("status", "new"), time.time(), draft_id),
            )
            self._conn.commit()

    def claim_draft(self, draft_id: str, neu: str, *, verboten: tuple) -> bool:
        """Atomarer Status-Wechsel: genau EIN Aufrufer gewinnt. Schützt das
        Veröffentlichen vor Doppeltipp — zwei parallele Uploads würden dieselbe
        Karte zweimal auf eBay stellen. True = der Claim gehört dir."""
        platzhalter = ",".join("?" * len(verboten))
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE drafts SET data = json_set(data, '$.status', ?), status = ?, "
                f"updated_at = ? WHERE id = ? AND "
                f"COALESCE(json_extract(data, '$.status'), '') NOT IN ({platzhalter})",
                (neu, neu, time.time(), draft_id, *verboten),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def release_draft_claim(self, draft_id: str, zurueck: str) -> bool:
        """Claim lösen, aber nur wenn er noch besteht — Endzustände wie
        published/dry_run_done, die der Lauf selbst gesetzt hat, bleiben stehen."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE drafts SET data = json_set(data, '$.status', ?), status = ?, "
                "updated_at = ? WHERE id = ? AND json_extract(data, '$.status') = 'publishing'",
                (zurueck, zurueck, time.time(), draft_id),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def delete_draft(self, draft_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            self._conn.commit()

    def latest_draft_for_chat(self, chat_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT id FROM drafts WHERE chat_id = ? ORDER BY created_at DESC LIMIT 1", (chat_id,)
        ).fetchone()
        return self.get_draft(row["id"]) if row else None

    def stale_draft_ids(self, *, unfinished_older_than_s: float,
                        published_older_than_s: float) -> tuple[list[str], list[str]]:
        """(zu löschende Draft-IDs, IDs deren Foto-Ordner weg kann).

        Unfertige Drafts (nie hochgeladen) werden nach Frist komplett gelöscht.
        Veröffentlichte behalten ihren DB-Eintrag (für /listings-Bearbeitung),
        nur die lokalen Fotos werden entsorgt — die Bilder liegen längst bei eBay."""
        now = time.time()
        dead = [r["id"] for r in self._conn.execute(
            "SELECT id FROM drafts WHERE status NOT IN ('published') AND updated_at < ?",
            (now - unfinished_older_than_s,)).fetchall()]
        old_published = [r["id"] for r in self._conn.execute(
            "SELECT id FROM drafts WHERE status = 'published' AND updated_at < ?",
            (now - published_older_than_s,)).fetchall()]
        return dead, old_published

    def published_listings_for_chat(self, chat_id: int) -> list[dict]:
        """Alle echt veröffentlichten Listings eines Chats (sku/offer/listing) —
        für Bulk-Überarbeitung. Neueste zuerst, pro SKU nur der jüngste Eintrag."""
        rows = self._conn.execute(
            "SELECT sku, listing_id, offer_id, title, price, MAX(created_at) AS ts "
            "FROM listings WHERE telegram_id = ? AND dry_run = 0 AND listing_id IS NOT NULL "
            "GROUP BY sku ORDER BY ts DESC", (chat_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def published_drafts_for_chat(self, chat_id: int, limit: int = 12) -> list[dict]:
        """Zuletzt veröffentlichte Listings eines Chats (zum nachträglichen Bearbeiten)."""
        rows = self._conn.execute(
            "SELECT id FROM drafts WHERE chat_id = ? AND status = 'published' "
            "ORDER BY updated_at DESC LIMIT ?", (chat_id, limit),
        ).fetchall()
        return [d for d in (self.get_draft(r["id"]) for r in rows) if d]

    # --- Aspect-Cache ---

    def get_aspects(self, category_id: str, max_age_s: float = 7 * 86400) -> Optional[list]:
        row = self._conn.execute(
            "SELECT data, fetched_at FROM aspects_cache WHERE category_id = ?", (category_id,)
        ).fetchone()
        if row and time.time() - row["fetched_at"] < max_age_s:
            return json.loads(row["data"])
        return None

    def set_aspects(self, category_id: str, aspects: list) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO aspects_cache (category_id, data, fetched_at) VALUES (?, ?, ?) "
                "ON CONFLICT(category_id) DO UPDATE SET data=excluded.data, fetched_at=excluded.fetched_at",
                (category_id, json.dumps(aspects), time.time()),
            )
            self._conn.commit()

    # --- Listing-Log ---

    def log_listing(self, sku: str, title: str, price: str, offer_id: str | None,
                    listing_id: str | None, dry_run: bool, telegram_id: int | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO listings (sku, listing_id, offer_id, title, price, dry_run, created_at, telegram_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sku, listing_id, offer_id, title, price, int(dry_run), time.time(), telegram_id),
            )
            self._conn.commit()

    def listings_this_month(self, telegram_id: int) -> int:
        """Echte (nicht Dry-Run) Listings des Nutzers im laufenden Kalendermonat."""
        import datetime
        month_start = datetime.datetime.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).timestamp()
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM listings WHERE telegram_id = ? AND created_at >= ? AND dry_run = 0",
            (telegram_id, month_start),
        ).fetchone()
        return int(row["n"])

    def listings_today(self) -> int:
        midnight = time.time() - (time.time() % 86400)
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM listings WHERE created_at >= ? AND dry_run = 0", (midnight,)
        ).fetchone()
        return int(row["n"])
