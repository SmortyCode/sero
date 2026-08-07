"""eBay OAuth2: App-Token (Client Credentials) + User-Token mit Auto-Refresh.

Jeder API-Call läuft durch EbayClient.request(): bei 401 wird das Token
einmal refresht und der Call einmal wiederholt. Netz-Aussetzer, 429 und 5xx
werden mit wachsendem Abstand wiederholt — aber NUR bei wiederholbaren
Methoden. Ein POST, der ein Listing anlegt, wird nie blind wiederholt;
er meldet EbayTimeout, damit der Aufrufer erst nachsieht, was wirklich
passiert ist (sonst entstehen doppelte oder Geister-Listings).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
import urllib.parse
from typing import Any, Optional

import httpx

from bot.config import (
    Config,
    EBAY_AUTH_URL,
    EBAY_TOKEN_URL,
    SCOPE_PUBLIC,
    USER_SCOPES,
)
from bot.drafts import Store

log = logging.getLogger("ebay.auth")

KV_USER_TOKEN_LEGACY = "ebay_user_token"  # Single-User-Ära; wird beim Start migriert


def _token_key(user_id: int) -> str:
    return f"ebay_user_token_{user_id}"


class EbayAuthError(Exception):
    pass


class EbayTimeout(Exception):
    """Die Anfrage ging raus, die Antwort kam nie an. Ob eBay sie ausgeführt hat,
    ist offen — der Aufrufer muss nachsehen, statt einfach zu wiederholen."""


# Methoden, bei denen eine Wiederholung nichts doppelt anlegt
_IDEMPOTENT = {"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}
_RETRY_CODES = {429, 500, 502, 503, 504}
_BACKOFF = (1.0, 3.0, 8.0)   # Abstände zwischen den Versuchen


def _redact(text: str) -> str:
    # Tokens aus Log-Ausgaben entfernen
    for marker in ("access_token", "refresh_token"):
        idx = 0
        while (idx := text.find(marker, idx)) != -1:
            end = min(len(text), idx + 200)
            text = text[: idx + len(marker) + 3] + "***REDACTED***" + text[end:]
            idx += len(marker) + 3
    return text


class EbayClient:
    def __init__(self, cfg: Config, store: Store):
        self.cfg = cfg
        self.store = store
        self._http = httpx.AsyncClient(timeout=30)
        self._app_token: Optional[str] = None
        self._app_token_expires = 0.0
        # Ein Refresh pro Nutzer zur Zeit: Bulk-Uploads und der 2-h-Verkaufsabgleich
        # können sonst gleichzeitig refreshen — doppelte POSTs an eBay und im
        # Fehlerfall (Token widerrufen) ein Dauerfeuer vergeblicher Versuche.
        self._refresh_locks: dict[int, asyncio.Lock] = {}

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------- Token-Beschaffung ----------

    def _basic_auth(self) -> str:
        raw = f"{self.cfg.ebay_client_id}:{self.cfg.ebay_client_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    async def get_app_token(self) -> str:
        """Client-Credentials-Token für Browse/Taxonomy (2h gültig, in-memory gecacht)."""
        if self._app_token and time.time() < self._app_token_expires - 120:
            return self._app_token
        resp = await self._http.post(
            EBAY_TOKEN_URL,
            headers={"Authorization": self._basic_auth(),
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": SCOPE_PUBLIC},
        )
        if resp.status_code != 200:
            raise EbayAuthError(
                f"App-Token fehlgeschlagen ({resp.status_code}): {_redact(resp.text)}. "
                "Prüfe EBAY_CLIENT_ID/SECRET und ob die Account-Deletion-Exemption aktiviert ist."
            )
        data = resp.json()
        self._app_token = data["access_token"]
        self._app_token_expires = time.time() + int(data.get("expires_in", 7200))
        return self._app_token

    def build_consent_url(self) -> str:
        params = {
            "client_id": self.cfg.ebay_client_id,
            "redirect_uri": self.cfg.ebay_ru_name,
            "response_type": "code",
            "scope": " ".join(USER_SCOPES),
        }
        return f"{EBAY_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def migrate_legacy_token(self, user_id: int) -> None:
        """Token aus der Single-User-Ära dem (Admin-)Nutzer zuordnen."""
        legacy = self.store.kv_get(KV_USER_TOKEN_LEGACY)
        if legacy and not self.store.kv_get(_token_key(user_id)):
            self.store.kv_set(_token_key(user_id), legacy)
            log.info("Bestehendes eBay-Token auf Nutzer %s migriert", user_id)

    async def exchange_code(self, code: str, user_id: int) -> None:
        resp = await self._http.post(
            EBAY_TOKEN_URL,
            headers={"Authorization": self._basic_auth(),
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code,
                  "redirect_uri": self.cfg.ebay_ru_name},
        )
        if resp.status_code != 200:
            raise EbayAuthError(f"Code-Exchange fehlgeschlagen ({resp.status_code}): {_redact(resp.text)}")
        self._store_user_token(resp.json(), user_id)

    def _store_user_token(self, data: dict, user_id: int) -> None:
        now = time.time()
        stored = self.store.kv_get(_token_key(user_id)) or {}
        token = {
            "access_token": data["access_token"],
            "access_expires": now + int(data.get("expires_in", 7200)),
            # Beim Refresh kommt kein neues Refresh-Token: altes behalten
            "refresh_token": data.get("refresh_token", stored.get("refresh_token")),
            "refresh_expires": now + int(data["refresh_token_expires_in"])
            if "refresh_token_expires_in" in data else stored.get("refresh_expires"),
        }
        self.store.kv_set(_token_key(user_id), token)

    async def refresh_user_token(self, user_id: int) -> str:
        lock = self._refresh_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            return await self._refresh_user_token_locked(user_id)

    async def _refresh_user_token_locked(self, user_id: int) -> str:
        token = self.store.kv_get(_token_key(user_id))
        if not token or not token.get("refresh_token"):
            raise EbayAuthError("Kein Refresh-Token vorhanden — eBay-Konto mit /verbinden verknüpfen.")
        # Während wir auf die Sperre warteten, kann ein anderer bereits
        # refresht haben — dann ist nichts mehr zu tun.
        if time.time() < token.get("access_expires", 0) - 120:
            return token["access_token"]
        # Nach einem harten Fehlschlag (z. B. Token widerrufen) 10 Minuten Ruhe:
        # jeder weitere Versuch würde ohnehin scheitern und nur eBay verärgern.
        if time.time() - token.get("refresh_failed_ts", 0) < 600:
            raise EbayAuthError("eBay-Verbindung abgelaufen — bitte das eBay-Konto "
                                "neu verknüpfen.")
        resp = await self._http.post(
            EBAY_TOKEN_URL,
            headers={"Authorization": self._basic_auth(),
                     "Content-Type": "application/x-www-form-urlencoded"},
            # KEIN scope mitschicken. eBay verlangt eine Teilmenge der ursprünglich
            # erteilten Rechte — wächst USER_SCOPES später, antwortet eBay mit
            # invalid_scope und das Konto ist bis zum manuellen /verbinden tot.
            # Ohne scope verlängert eBay genau die erteilten Rechte.
            data={"grant_type": "refresh_token", "refresh_token": token["refresh_token"]},
        )
        if resp.status_code != 200:
            if resp.status_code in (400, 401):
                token["refresh_failed_ts"] = time.time()
                self.store.kv_set(_token_key(user_id), token)
            raise EbayAuthError(
                f"Token-Refresh fehlgeschlagen ({resp.status_code}): {_redact(resp.text)}. "
                "Falls das Refresh-Token abgelaufen ist (~18 Monate): eBay-Konto mit /verbinden neu verknüpfen."
            )
        token.pop("refresh_failed_ts", None)
        self._store_user_token(resp.json(), user_id)
        return self.store.kv_get(_token_key(user_id))["access_token"]

    async def get_user_token(self, user_id: int) -> str:
        token = self.store.kv_get(_token_key(user_id))
        if not token:
            raise EbayAuthError("Kein eBay-Konto verknüpft — /verbinden ausführen.")
        if time.time() < token["access_expires"] - 120:
            return token["access_token"]
        return await self.refresh_user_token(user_id)

    def user_token_status(self, user_id: int) -> dict:
        token = self.store.kv_get(_token_key(user_id))
        if not token:
            return {"ok": False, "detail": "kein eBay-Konto verknüpft (/verbinden)"}
        return {
            "ok": True,
            "access_valid_s": max(0, int(token["access_expires"] - time.time())),
            "refresh_valid_d": int((token["refresh_expires"] - time.time()) / 86400)
            if token.get("refresh_expires") else None,
        }

    # ---------- Request-Wrapper ----------

    async def request(
        self,
        method: str,
        url: str,
        *,
        auth: str = "user",  # "user" | "app"
        user_id: Optional[int] = None,  # Pflicht bei auth="user"
        headers: Optional[dict] = None,
        json_body: Any = None,
        params: Optional[dict] = None,
        content: Optional[bytes] = None,
        files: Optional[dict] = None,
        retry: Optional[bool] = None,   # None = automatisch nach Methode
    ) -> httpx.Response:
        if auth == "user" and user_id is None:
            raise EbayAuthError("Interner Fehler: user_id fehlt für User-Auth-Call.")

        async def _do(token: str) -> httpx.Response:
            h = {"Authorization": f"Bearer {token}"}
            if headers:
                h.update(headers)
            return await self._http.request(
                method, url, headers=h, json=json_body, params=params,
                content=content, files=files,
            )

        token = await (self.get_user_token(user_id) if auth == "user" else self.get_app_token())
        log.debug("eBay %s %s user=%s params=%s body=%s", method, url, user_id, params,
                  _redact(str(json_body))[:2000] if json_body else None)

        may_retry = method.upper() in _IDEMPOTENT if retry is None else retry
        resp = None
        for versuch in range(len(_BACKOFF) + 1):
            letzter = versuch == len(_BACKOFF)
            try:
                resp = await _do(token)
            except httpx.TimeoutException as e:
                # Anfrage raus, Antwort weg. Bei einem POST, der etwas anlegt, wäre
                # ein zweiter Versuch ein zweites Listing — deshalb nur melden.
                if not may_retry:
                    raise EbayTimeout(f"eBay hat nicht geantwortet ({type(e).__name__}).") from e
                if letzter:
                    raise EbayTimeout("eBay hat auch nach mehreren Versuchen nicht geantwortet.") from e
                await self._warte(_BACKOFF[versuch], f"{type(e).__name__}", method, url)
                continue
            except httpx.TransportError as e:
                if letzter or not may_retry:
                    raise EbayAuthError(f"Keine Verbindung zu eBay: {type(e).__name__}") from e
                await self._warte(_BACKOFF[versuch], f"{type(e).__name__}", method, url)
                continue

            if resp.status_code == 401 and versuch == 0:
                log.info("401 von eBay — Token wird refresht, ein Retry")
                if auth == "user":
                    token = await self.refresh_user_token(user_id)
                else:
                    self._app_token = None
                    token = await self.get_app_token()
                continue

            # 429 = zu viele Anfragen, 5xx = eBay hat gerade selbst ein Problem.
            # Beides geht meist von allein weg, wenn man kurz wartet.
            if resp.status_code in _RETRY_CODES and may_retry and not letzter:
                await self._warte(self._nach_header(resp, _BACKOFF[versuch]),
                                  f"HTTP {resp.status_code}", method, url)
                continue
            break

        log.debug("eBay Antwort %s: %s", resp.status_code, _redact(resp.text[:2000]))
        return resp

    @staticmethod
    def _nach_header(resp: httpx.Response, standard: float) -> float:
        """eBay sagt bei 429 manchmal selbst, wie lange wir warten sollen."""
        try:
            wert = float(resp.headers.get("Retry-After", ""))
        except ValueError:
            return standard
        return min(max(wert, standard), 60.0)

    @staticmethod
    async def _warte(sekunden: float, grund: str, method: str, url: str) -> None:
        log.warning("eBay %s %s: %s — neuer Versuch in %.0fs", method, url.rsplit("/", 1)[-1],
                    grund, sekunden)
        await asyncio.sleep(sekunden)
