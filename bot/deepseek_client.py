"""DeepSeek: NUR für textbasierte Schritte — die API hat (Stand 07/2026, offiziell
geprüft) KEINEN Vision-/Bild-Input. Die Fotoanalyse (Kernfunktion von Listo) läuft
deshalb weiterhin über Claude (bot/claude_client.py). DeepSeek übernimmt hier nur
Aufgaben, die rein mit vorhandenem Text arbeiten (z.B. Listings umformulieren beim
"Rework" bestehender, bereits veröffentlichter Angebote) — deutlich günstiger pro
Token als Claude Opus/Sonnet.

API ist OpenAI-kompatibel (REST), daher reicht httpx — kein zusätzliches SDK nötig.
"""

from __future__ import annotations

import json
import logging

import httpx

from bot.config import Config

log = logging.getLogger("deepseek")

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = """Du bist ein eBay-Listing-Texter. Du bekommst Angaben zu einem \
BEREITS eingestellten Artikel (Titel, Kategorie, Zustand, Merkmale) und formulierst \
Titel + Beschreibung in ein einheitliches Format um. Erfinde NICHTS Neues — nutze nur \
die vorhandenen Angaben.

TITEL-FORMEL (exakt diese Reihenfolge, deutsch, Ziel 60-70 Zeichen, max 80):
Marke → Produkt/Modell → Variante/Setnummer → wichtigstes Merkmal → Größe/Farbe → Zustandskeyword.
Natürliche Käufersprache, KEINE GROSSBUCHSTABEN-Wörter, keine Füller wie "TOP"/"RAR"/"WOW".

BESCHREIBUNGS-TEMPLATE (exakt diese HTML-Struktur):
<p>[2-3 Sätze: was ist es, was macht es besonders — ehrlich, keine Superlative]</p>
<p><b>Details</b></p>
<ul><li>[je ein Fakt pro Zeile]</li></ul>
<p><b>Zustand</b></p>
<p>[ehrliche Zustandsbeschreibung]</p>
<p><b>Versand</b></p>
<p>Schneller Versand, sicher und sorgfältig verpackt.</p>

Antworte AUSSCHLIESSLICH mit validem JSON, keine Markdown-Fences:
{"title": "…", "description_html": "…"}"""


class DeepSeekError(Exception):
    pass


class DeepSeekAnalyzer:
    """Drop-in-Ersatz für die textbasierten Methoden von ClaudeAnalyzer."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._client = httpx.AsyncClient(timeout=60.0)

    async def reformat_listing(self, title: str, aspects: dict, condition: str,
                               category_name: str | None) -> dict:
        prompt = (
            f"Aktueller Titel: {title}\n"
            f"Kategorie: {category_name or 'unbekannt'}\n"
            f"Zustand: {condition}\n"
            f"Merkmale: {json.dumps(aspects, ensure_ascii=False)}"
        )
        resp = await self._client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {self.cfg.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.cfg.deepseek_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 1500,
                "response_format": {"type": "json_object"},
            },
        )
        if resp.status_code != 200:
            raise DeepSeekError(f"DeepSeek-Fehler {resp.status_code}: {resp.text[:400]}")
        body = resp.json()
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        log.debug("DeepSeek-Antwort (%s in / %s out Tokens): %s",
                  usage.get("prompt_tokens"), usage.get("completion_tokens"), text[:500])
        from bot.claude_client import parse_fence
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = parse_fence(cleaned)
        data = json.loads(cleaned)
        if not data.get("title") or not data.get("description_html"):
            raise DeepSeekError("Reformat lieferte kein title/description_html")
        return {"title": str(data["title"])[:80], "description_html": str(data["description_html"])}

