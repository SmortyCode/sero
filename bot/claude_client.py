"""Claude Vision: Fotos + Nutzertext -> strukturierter Listing-Entwurf (JSON)."""

from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Optional

from anthropic import AsyncAnthropic
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()   # iPhone-HEIC lesbar machen
except ImportError:
    import logging as _logging
    _logging.getLogger("claude").warning("pillow-heif fehlt — HEIC nicht lesbar!")

from bot.config import Config

log = logging.getLogger("claude")

MAX_IMAGES = 5
CLAUDE_MAX_EDGE = 2048  # Opus 4.7+ liest hochauflösend — mehr Detail = bessere Erkennung

SYSTEM_PROMPT = """Du bist ein Weltklasse-Produkterkennungs- und eBay-Listing-Experte für ALLE \
Produktkategorien — Elektronik, Fashion, Haushalt, Spielzeug, Möbel, Werkzeug — mit besonderer \
Spezialtiefe bei Sammlerware (Trading Cards, graded Slabs, Plüschfiguren, Videospiele).

PRODUKTERKENNUNG — dein wichtigster Job:
- Identifiziere Marke und EXAKTES Modell aus allen visuellen Hinweisen: Logos, Schriftzüge, \
Kamera-Anordnung, Anschlüsse, Tasten, Form, Material, Farbe, Größenverhältnisse (eine Hand im \
Bild ist eine Größenreferenz!).
- Nutze dein Produktwissen aktiv: Bei Smartphones verraten Kamera-Layout und Gehäusedetails die \
Generation (z.B. unterscheidet sich das Kamera-Plateau zwischen iPhone-Generationen), bei \
Sneakern Silhouette und Details, bei Konsolen Anschlüsse und Gehäuse.
- Sind mehrere Modelle plausibel: Wähle das WAHRSCHEINLICHSTE und vermerke die Annahme knapp im \
Feld "assumptions" (z.B. "Als iPhone 17 Pro Max erkannt — Pro/Pro Max vom Foto nicht 100% \
unterscheidbar. Speichergröße unbekannt."). NIEMALS ein generisches Listing ("Smartphone \
schwarz") schreiben, wenn das Modell erkennbar ist.
- Angaben des Verkäufers (Text/Caption) haben IMMER Vorrang vor der Bilderkennung.

TITEL-FORMEL (IMMER exakt diese Reihenfolge, deutsch, Ziel 60-70 Zeichen, max 80):
Marke → Produkt/Modell → Variante/Setnummer → wichtigstes Merkmal → Größe/Farbe → Zustandskeyword.
- Natürliche Käufersprache (was Käufer wirklich suchen), KEINE GROSSBUCHSTABEN-Wörter, keine \
Füller wie "TOP", "RAR", "L@@K", "WOW", keine Sonderzeichen-Deko, kein Keyword-Stuffing.
- Kategorie-Muster: Trading Card: "[TCG] [Kartenname] [Setnr.] [Set] [Sprache] [Grade oder NM]" \
(z.B. "Pokémon Glurak ex 199/165 151 Deutsch PSA 10"). Elektronik: "[Marke] [Modell] [Speicher/\
Variante] [Farbe] [Zustand]". Fashion/Sneaker: "[Marke] [Modell] [Colorway] [Größe]". \
Plüsch/Spielzeug: "[Marke/Serie] [Figur] [Größe cm] [Merkmal]".

BESCHREIBUNGS-TEMPLATE (IMMER exakt diese HTML-Struktur, nichts anderes):
<p>[2-3 Sätze: was ist es, was macht es besonders — ehrlich, keine Superlative]</p>
<p><b>Details</b></p>
<ul><li>[je ein Fakt pro Zeile: Marke, Modell, Set/Nummer, Größe, Farbe, Sprache …]</li></ul>
<p><b>Zustand</b></p>
<p>[ehrliche Zustandsbeschreibung anhand der Fotos; bei Neuware "Neu und ungeöffnet"]</p>
<p><b>Versand</b></p>
<p>Schneller Versand, sicher und sorgfältig verpackt.</p>
Ehrlich bleiben: nur beschreiben, was auf den Fotos erkennbar ist oder vom Verkäufer angegeben \
wurde. KEINE erfundenen Details (Speichergröße, Jahr, OVP) — Unbekanntes weglassen.

Antworte AUSSCHLIESSLICH mit validem JSON. Keine Markdown-Fences, kein Vortext, kein Nachtext.

Schema:
{
  "title": "nach der TITEL-FORMEL oben, deutsch, Ziel 60-70 Zeichen",
  "subtitle": null,
  "description_html": "exakt nach dem BESCHREIBUNGS-TEMPLATE oben",
  "category_query": "Suchbegriff für eBay-Kategorievorschlag, z.B. 'iPhone 17 Pro Max' oder 'Pokemon Plüschtier'",
  "condition": "NEW | USED_EXCELLENT | USED_GOOD | USED_ACCEPTABLE",
  "condition_description": "nur bei Gebraucht: kurze ehrliche Zustandsbeschreibung, sonst null",
  "aspects": {"Marke": ["..."], "Modell": ["..."]},  // Bei Videospielen/DVDs/Blu-rays: NUR wenn ein deutsches USK-Logo auf dem Cover zu sehen ist (Farbe: weiß/grün=0, gelb=6, blau=12, rot=16, schwarz=18), das Merkmal "USK-Einstufung": ["USK ab X Jahren"] setzen — verhindert eBays 18-Sperre bei niedriger eingestuften Spielen. OHNE sichtbares deutsches USK-Logo (z. B. US-Importe mit ESRB, japanische mit CERO) das Merkmal KOMPLETT WEGLASSEN — kein Feld „USK", keine Ersatzangabe, auch nicht "nicht vorhanden" oder "keine". Niemals ESRB/PEGI/CERO in ein Alters-Merkmal schreiben: eBay.de liest das als Erwachsenen-Kennzeichen und sperrt das Listing.
  "search_query_for_pricing": "präzise Query für Preisvergleich auf eBay (Marke + Modell + Variante)",
  "estimated_price_range_eur": "{\"low\": 1.0, \"high\": 3.0} — dein EHRLICHER Marktwert-Rahmen aus Produktwissen: wofür verkauft sich GENAU dieser Artikel in diesem Zustand realistisch auf eBay? Alltagsware ehrlich niedrig ansetzen (eine Flasche Apfelschorle ist ~1-2 €, kein Sammlerstück). Bei Sammlerware den echten Marktwert. Pflichtfeld — dient als Plausibilitäts-Check gegen falsche Vergleichsangebote.",
  "user_price": "Preis als String z.B. '70.00', NUR wenn der Verkäufer AUSDRÜCKLICH einen Preis nennt ('für 70€', 'Sofortkauf 70', 'Startpreis 5€') — dieser Preis hat IMMER Vorrang. Sonst null.",
  "best_offer": "null, oder {\"enabled\": true, \"min_price\": \"50.00\"} wenn der Verkäufer Preisvorschläge/Best Offer erwähnt ('mit Preisvorschlag', 'VB'). min_price = genannte Untergrenze ('bis 50€' / 'ab 50€' / 'nicht unter 50' = '50.00'), sonst null.",
  "format": "FIXED_PRICE | AUCTION — FIXED_PRICE ist der Default. AUCTION NUR, wenn der Verkäufer es ausdrücklich verlangt (z.B. 'Auktion', 'versteigern', 'Startpreis').",
  "auction_days": "Ganzzahl 1|3|5|7|10 — Auktionslaufzeit NUR wenn der Verkäufer sie nennt ('1 Tag', '3 Tage Auktion'), sonst 7. Nur relevant bei format=AUCTION.",
  "quantity": "Ganzzahl >= 1, Default 1. NUR wenn der Verkäufer MEHRERE identische Artikel oder Sets in EINEM Listing anbietet (z.B. '10 Stück verfügbar', '5er Pack Sleeves', '3 Sets à 3 Toploader'): verfügbare Stückzahl setzen. Titel und Beschreibung beschreiben dann EIN Exemplar/Set, der Preis gilt pro Exemplar/Set.",
  "main_image_index": "0-basierter Index des Fotos, das die VORDERSEITE des Produkts zeigt (bei Karten die Bildseite, bei Verpacktem die Front) — das wird das eBay-Hauptbild. Reihenfolge = Reihenfolge der angehängten Bilder. Im Zweifel 0.",
  "graded_info": "NUR wenn die Karte/das Spiel sichtbar in einem Grading-Slab (Plastikgehäuse mit Bewertungslabel) steckt, sonst null: {\"grader\": \"PSA\", \"grade\": \"9.5\", \"cert_number\": \"12345678\"} — Werte exakt vom Slab-Label ablesen, nicht lesbare Felder null. Eine LOSE Karte ist NIEMALS graded.",
  "assumptions": "string oder null — knappe, ehrliche Annahmen bei der Erkennung (Modellvariante, unbekannte Speichergröße o.ä.). Wird dem Verkäufer in der Vorschau angezeigt.",
  "estimated_weight_grams": 300,
  "uncertain": false,
  "question": null
}

"uncertain": true + "question" NUR, wenn du das Produkt überhaupt nicht zuordnen kannst oder eine \
Info fehlt, ohne die das Listing irreführend wäre (z.B. echt vs. Replika bei Luxusware). \
Varianten-Unsicherheiten (Speicher, Pro/Pro Max, Größe) gehören in "assumptions", NICHT in eine \
blockierende Rückfrage. Rate niemals bei wertrelevanten Details — benenne Unbekanntes ehrlich."""


class ClaudeError(Exception):
    pass


def prepare_image_for_claude(path: str | Path) -> tuple[str, str]:
    """(base64-Daten, media_type) — auf CLAUDE_MAX_EDGE lange Kante skaliert (spart Tokens)."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > CLAUDE_MAX_EDGE:
        img.thumbnail((CLAUDE_MAX_EDGE, CLAUDE_MAX_EDGE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode(), "image/jpeg"


def parse_listing_json(text: str) -> dict:
    """Defensiv parsen: ```json-Fences strippen, dann json.loads."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = parse_fence(cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise json.JSONDecodeError("Top-Level ist kein Objekt", cleaned, 0)
    for field in ("title", "description_html", "category_query", "condition",
                  "search_query_for_pricing"):
        if field not in data:
            raise json.JSONDecodeError(f"Pflichtfeld fehlt: {field}", cleaned, 0)
    _grader_im_titel_richtigstellen(data)
    return data


# Die echten Kürzel der Bewertungsdienste — seit Stufe 3 aus dem zentralen
# Kanon (web/slab.py). Die Analyse liest sie vom Slab-Label ab und trifft
# dabei gelegentlich daneben — Svens One-Piece-Band-1 stand als „BGC 8.5"
# im Titel, obwohl das Label Beckett zeigte (Kürzel: BGS). Käufer suchen
# nach dem richtigen Kürzel; ein falsches macht das Angebot unauffindbar.
from web.slab import GRADER_KANON as _GRADER_KUERZEL  # noqa: E402


def _fast_gleich(a: str, b: str) -> bool:
    """Editierdistanz ≤ 1 — „BGC"→„BGS" ja, „Band"→„BGS" nein."""
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    kurz, lang = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(lang)):
        if lang[:i] + lang[i + 1:] == kurz:
            return True
    return False


def _grader_im_titel_richtigstellen(data: dict) -> None:
    """Falsch geschriebenes Grader-Kürzel im Titel gegen das echte tauschen.

    Ersetzt wird NUR, wenn das getroffene Wort selbst ein bekanntes Kürzel
    oder eine plausible Verschreibung davon ist (Editierdistanz 1). Die alte
    Regex nahm blind das Wort vor der Note — aus „One Piece Band 9" wäre
    „One Piece BGS 9" geworden. Lieber ein unkorrigierter Titel als ein
    zerstörter (Stufe-3-Entscheid)."""
    g = (data.get("graded_info") or {}).get("grader")
    if not g or not data.get("title"):
        return
    richtig = _GRADER_KUERZEL.get(str(g).strip().lower())
    if not richtig:
        return
    import re as _re
    titel = data["title"]
    if _re.search(rf"\b{richtig}\b", titel, _re.I):
        return                                   # steht schon korrekt drin
    bekannte = set(_GRADER_KUERZEL) | {v.lower() for v in _GRADER_KUERZEL.values()}

    getauscht = {"n": 0}

    def _tausch(m: "_re.Match") -> str:
        wort = m.group(0)
        if getauscht["n"]:
            return wort
        wl = wort.lower()
        if wl in bekannte or any(_fast_gleich(wort, k) for k in
                                 set(_GRADER_KUERZEL.values())):
            getauscht["n"] += 1
            return richtig
        return wort

    # Kandidaten sind Kürzel aus 2-5 Buchstaben direkt vor einer Note; ohne
    # count, damit ein harmloses „Band 9" früh im Titel den echten Treffer
    # („BGC 8.5" weiter hinten) nicht verbraucht — getauscht wird nur einmal.
    neu = _re.sub(r"\b[A-Za-z]{2,5}(?=\s*\d{1,2}(?:\.\d)?\b)", _tausch, titel)
    if neu != titel:
        data["title"] = neu


class ClaudeAnalyzer:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = AsyncAnthropic(api_key=cfg.anthropic_api_key,
                                     timeout=90.0, max_retries=2)

    async def analyze(self, photo_paths: list[str], user_text: Optional[str]) -> dict:
        content: list[dict] = []
        for path in photo_paths[:MAX_IMAGES]:
            data, media_type = prepare_image_for_claude(path)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })
        prompt = "Erstelle den Listing-Entwurf für dieses Produkt."
        if user_text:
            prompt += f"\n\nAngaben des Verkäufers (haben Vorrang): {user_text}"
        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]
        text = await self._call(messages)
        try:
            return parse_listing_json(text)
        except json.JSONDecodeError as e:
            log.warning("Claude-JSON ungültig (%s) — ein Retry mit Fehlermeldung", e)
            messages.append({"role": "assistant", "content": text})
            messages.append({
                "role": "user",
                "content": f"Deine Antwort war kein valides JSON ({e}). "
                           "Antworte erneut, AUSSCHLIESSLICH mit validem JSON nach dem Schema.",
            })
            return parse_listing_json(await self._call(messages))

    async def fill_aspects(self, photo_paths: list[str], listing: dict,
                           missing_aspects: list[str]) -> dict:
        """Zweiter kurzer Call: fehlende Pflicht-Aspects ergänzen."""
        content: list[dict] = []
        for path in photo_paths[:2]:
            data, media_type = prepare_image_for_claude(path)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })
        content.append({
            "type": "text",
            "text": (
                f"Produkt: {listing.get('title')}\n"
                f"Fülle diese eBay-Pflichtfelder anhand der Fotos. Wenn ein Wert nicht "
                f"erkennbar ist, verwende 'Nicht zutreffend'.\n"
                f"Felder: {', '.join(missing_aspects)}\n\n"
                'Antworte AUSSCHLIESSLICH mit validem JSON: {"Feldname": ["Wert"], ...}'
            ),
        })
        messages = [{"role": "user", "content": content}]
        text = await self._call(messages, max_tokens=1024)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = parse_fence(cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning("Aspect-Fill-Antwort unparsbar, fülle mit 'Nicht zutreffend'")
            return {name: ["Nicht zutreffend"] for name in missing_aspects}

    async def reformat_listing(self, title: str, aspects: dict, condition: str,
                               category_name: str | None) -> dict:
        """Bestehendes Listing (nur Text, keine Fotos) auf einheitlichen Titel +
        Beschreibungs-Template umformen. Erfindet nichts — nutzt nur vorhandene Infos."""
        prompt = (
            "Formuliere Titel und Beschreibung für ein BEREITS eingestelltes eBay-Listing "
            "in EINHEITLICHES Format um (TITEL-FORMEL + BESCHREIBUNGS-TEMPLATE aus deinen "
            "Anweisungen). Erfinde NICHTS Neues — nutze nur die vorhandenen Angaben.\n\n"
            f"Aktueller Titel: {title}\n"
            f"Kategorie: {category_name or 'unbekannt'}\n"
            f"Zustand: {condition}\n"
            f"Merkmale: {json.dumps(aspects, ensure_ascii=False)}\n\n"
            'Antworte AUSSCHLIESSLICH mit validem JSON: '
            '{"title": "…", "description_html": "…"}'
        )
        messages = [{"role": "user", "content": prompt}]
        text = await self._call(messages, max_tokens=1500)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = parse_fence(cleaned)
        data = json.loads(cleaned)
        if not data.get("title") or not data.get("description_html"):
            raise ClaudeError("Reformat lieferte kein title/description_html")
        return {"title": str(data["title"])[:80], "description_html": str(data["description_html"])}

    async def _call(self, messages: list, max_tokens: int = 4096) -> str:
        resp = await self.client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        log.debug("Claude-Antwort (%s in / %s out Tokens): %s",
                  resp.usage.input_tokens, resp.usage.output_tokens, text[:500])
        if not text:
            raise ClaudeError("Claude hat keinen Text geliefert.")
        return text


def parse_fence(text: str) -> str:
    first_newline = text.find("\n")
    out = text[first_newline + 1:] if first_newline != -1 else text.lstrip("`")
    if out.rstrip().endswith("```"):
        out = out.rstrip().removesuffix("```")
    return out.strip()
