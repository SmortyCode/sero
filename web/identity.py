"""Fachliches Identitätsmodell + Preisfreigabe-Policy (Phase A, Schnitt 1).

Das LLM darf Kandidaten und Beobachtungen liefern. Freigabe für Preisabfrage
und Listing entscheidet nur der Server über `evaluate_identity`.

Pydantic-Modelle stehen bewusst auf Modulebene (FastAPI-Body-Falle).
Keine Massmigration beim Import — Alt-Daten werden erst bei Bedarf über
`normalize_legacy_analysis` lesbar und als ungeprüft markiert.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from web.slab import kanon_grader, normalize_grade, normalize_label_type

MAX_EVIDENCE_LEN = 200

TRUSTED_SOURCES = frozenset({
    "user_provided",
    "visible_on_photo",
    "catalog_verified",
})

# WATA/VGA/CGA bewerten Spiele, keine Sammelkarten — nie als graded_slab (Kartenfelder).
_GAME_GRADERS = frozenset({"WATA", "VGA", "CGA"})


def _is_game_grader(grader: str | None) -> bool:
    g = kanon_grader(grader) if grader else None
    if not g:
        g = (grader or "").strip().upper()
    return g in _GAME_GRADERS


def _is_tcg_or_card_game_text(blob: str) -> bool:
    """Trading Card / „Card Game" ist kein Videospiel — auch nicht bei „… Game Box"."""
    return bool(re.search(
        r"\b(card\s*game|kartenspiel|trading\s*card|sammelkarte|tcg|"
        r"booster\s*box|display\s*box|booster\s*bundle)\b",
        blob.lower(),
    ))


def _category_suggests_video_game(cat: str | None) -> bool:
    """Kategorie-Hinweis auf Videospiel — ohne die TCG-Falle „Card Game" / nacktes „game"."""
    blob = (cat or "").lower()
    if not blob or _is_tcg_or_card_game_text(blob):
        return False
    if any(w in blob for w in (
        "videospiel", "ps2", "ps1", "ps3", "ps4", "ps5",
        "switch", "xbox", "gamecube", "n64", "wii", "sega",
    )):
        return True
    # „game"/„spiel" nur als Wort, nicht als Teil von „Card Game" (oben ausgeschlossen)
    return bool(re.search(r"\b(games?|spiele?)\b", blob))


def _text_looks_like_game(*parts: str | None) -> bool:
    blob = " ".join(str(p) for p in parts if p).lower()
    if not blob:
        return False
    # TCG „Card Game" / Sammelkarte ist kein Videospiel (sonst: One Piece Card Game → PS2-Pfad)
    if _is_tcg_or_card_game_text(blob):
        return False
    keys = (
        "videospiel", "video game", " games", "ps1", "ps2", "ps3", "ps4", "ps5",
        "playstation", "xbox", "switch", "gamecube", "n64", "sega",
        "nintendo 64", "wii", "dreamcast", "game boy",
    )
    return any(k in blob for k in keys)


def _text_looks_like_manga_comic(*parts: str | None) -> bool:
    """Manga/Comic — auch in Beckett/CGC-Slab, nicht als TCG-Karte behandeln."""
    blob = " ".join(str(p) for p in parts if p).lower()
    if not blob:
        return False
    if _is_tcg_or_card_game_text(blob):
        return False
    if _text_looks_like_game(blob):
        return False
    if any(k in blob for k in (
        "manga", "comic", "comics", "tankobon", "jump comics", "graphic novel",
    )):
        return True
    return bool(re.search(
        r"\b(band|volume|vol\.|heft|taschenbuch)\b",
        blob,
    ))


def _aspect_suggests_manga_comic(aspects: dict | None) -> bool:
    pt = _first_aspect(aspects or {}, "Produktart", "Product type", "Format")
    return bool(pt and pt.lower() in ("manga", "comic", "graphic novel"))


def _infer_manga_series_volume(
    title: str | None,
    aspects: dict | None,
    card_info: dict | None,
) -> tuple[str | None, str | None]:
    ci = card_info or {}
    series = ci.get("series")
    volume = ci.get("volume") or ci.get("number")
    tit = _first_aspect(aspects or {}, "Titel", "Title", "Serie", "Series")
    if tit and not series:
        m = re.match(r"^(.+?)\s*#\s*(\d+)", tit.strip(), flags=re.I)
        if m:
            series, volume = m.group(1).strip(), m.group(2)
        else:
            series = tit.strip()
    if title and not series:
        m = re.match(r"^(.+?)\s*#\s*(\d+)", title.strip(), flags=re.I)
        if m:
            series, volume = m.group(1).strip(), m.group(2)
        elif not volume:
            m = re.search(r"(?:band|vol\.?|volume)\s*(\d+)", title, flags=re.I)
            if m:
                volume = m.group(1)
    return series, volume


def _infer_edition_from_text(*parts: Any) -> str | None:
    blob = _plain_blob(*parts).lower()
    if any(w in blob for w in (
        "1. druck", "first print", "1st print", "erstausgabe", "first edition",
    )):
        return "1. Druckauflage"
    if any(w in blob for w in ("2. druck", "second print", "2nd print")):
        return "2. Druckauflage"
    return None


def _plain_blob(*parts: Any) -> str:
    """HTML/Text zu einem Such-String für Plattform/Region/Vollständigkeit."""
    chunks: list[str] = []
    for p in parts:
        if p is None or p == "":
            continue
        s = re.sub(r"<[^>]+>", " ", str(p))
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            chunks.append(s)
    return " ".join(chunks)


def _infer_platform(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    mapping = (
        ("playstation 5", "PS5"), ("ps5", "PS5"),
        ("playstation 4", "PS4"), ("ps4", "PS4"),
        ("playstation 3", "PS3"), ("ps3", "PS3"),
        ("playstation 2", "PS2"), ("ps2", "PS2"),
        ("playstation 1", "PS1"), ("ps1", "PS1"), ("psx", "PS1"),
        ("nintendo switch", "Switch"), ("switch", "Switch"),
        ("gamecube", "GameCube"), ("game cube", "GameCube"),
        ("xbox 360", "Xbox 360"), ("xbox one", "Xbox One"),
        ("xbox series", "Xbox Series"), ("xbox", "Xbox"),
        ("nintendo 64", "N64"), ("n64", "N64"),
        ("wii u", "Wii U"), ("wii", "Wii"),
        ("game boy advance", "GBA"), ("gameboy advance", "GBA"),
        ("game boy", "Game Boy"),
    )
    for token, name in mapping:
        if token in t:
            return name
    return None


def _infer_region(text: str | None) -> str | None:
    if not text:
        return None
    import re
    t = str(text)
    for raw, norm in (
        (r"\bUSA\b", "USA"), (r"\bNTSC-?U\b", "USA"), (r"\bNTSC\b", "USA"),
        (r"\bPAL\b", "PAL"), (r"\bEUR\b", "PAL"), (r"\bEurope\b", "PAL"),
        (r"\bJAPAN\b", "Japan"), (r"\bJPN\b", "Japan"), (r"\bJP\b", "Japan"),
    ):
        if re.search(raw, t, flags=re.I):
            return norm
    return None


def _infer_completeness(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    if any(w in t for w in ("sealed", "versiegelt", "factory sealed", "new sealed")):
        return "sealed"
    if any(w in t for w in ("cib", "complete in box", "komplett")):
        return "cib"
    if any(w in t for w in ("disc only", "loose", "nur disc", "cartridge only")):
        return "loose"
    if "manual" in t:
        return "manual"
    return None


def _clean_game_title(name: str | None) -> str | None:
    """Anzeigename ohne Grade-/Plattform-Rauschen für die Preis-Query."""
    if not name:
        return None
    import re
    s = str(name)
    s = re.sub(
        r"\b(WATA|VGA|CGA)\s*[0-9]+(?:\.[0-9]+)?\b.*$",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"\bA\+{0,2}\b", "", s, flags=re.I)
    s = re.sub(r"\b(Sealed|Versiegelt|CIB|Loose)\b", "", s, flags=re.I)
    s = re.sub(
        r"\b(PlayStation\s*[1-5]|PS[1-5X]|Xbox(?:\s*(?:360|One|Series))?|"
        r"Switch|GameCube|N64|Wii\s*U?|PAL|USA|Japan|JPN|EUR|NTSC-?U?)\b",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"\s{2,}", " ", s).strip(" -–|:")
    return s or str(name).strip()


class FieldSource(str, Enum):
    user_provided = "user_provided"
    visible_on_photo = "visible_on_photo"
    catalog_verified = "catalog_verified"
    inferred = "inferred"
    unknown = "unknown"


class ProductKind(str, Enum):
    raw_card = "raw_card"
    graded_slab = "graded_slab"
    video_game = "video_game"
    manga_comic = "manga_comic"
    generic = "generic"


class Completeness(str, Enum):
    """Vollständigkeit bei Spielen (lose Disc != CIB != sealed)."""
    loose = "loose"
    manual = "manual"
    cib = "cib"
    sealed = "sealed"
    unknown = "unknown"


class RecognitionState(str, Enum):
    ready = "ready"
    needs_review = "needs_review"
    unknown = "unknown"


class BlockingReason(str, Enum):
    """Geschlossene Codes — UI mappt über BLOCKING_REASON_DE."""
    MISSING_KIND = "MISSING_KIND"
    MISSING_GAME = "MISSING_GAME"
    MISSING_NAME = "MISSING_NAME"
    MISSING_NUMBER = "MISSING_NUMBER"
    MISSING_SET = "MISSING_SET"
    MISSING_LANGUAGE = "MISSING_LANGUAGE"
    MISSING_EDITION = "MISSING_EDITION"
    MISSING_GRADER = "MISSING_GRADER"
    MISSING_GRADE = "MISSING_GRADE"
    MISSING_LABEL_TYPE = "MISSING_LABEL_TYPE"
    MISSING_PLATFORM = "MISSING_PLATFORM"
    MISSING_REGION = "MISSING_REGION"
    MISSING_COMPLETENESS = "MISSING_COMPLETENESS"
    MISSING_SERIES = "MISSING_SERIES"
    MISSING_VOLUME = "MISSING_VOLUME"
    MISSING_BRAND = "MISSING_BRAND"
    MISSING_MODEL = "MISSING_MODEL"
    MISSING_VARIANT = "MISSING_VARIANT"
    FIELD_UNTRUSTED = "FIELD_UNTRUSTED"
    AMBIGUOUS_VARIANT = "AMBIGUOUS_VARIANT"
    LEGACY_UNCHECKED = "LEGACY_UNCHECKED"


BLOCKING_REASON_DE: dict[BlockingReason, str] = {
    BlockingReason.MISSING_KIND: "Produktart ist unklar",
    BlockingReason.MISSING_GAME: "Spiel oder Marke fehlt",
    BlockingReason.MISSING_NAME: "Name fehlt",
    BlockingReason.MISSING_NUMBER: "Kartennummer fehlt",
    BlockingReason.MISSING_SET: "Set oder Nenner fehlt",
    BlockingReason.MISSING_LANGUAGE: "Sprache fehlt",
    BlockingReason.MISSING_EDITION: "Auflage oder Edition fehlt",
    BlockingReason.MISSING_GRADER: "Grader fehlt",
    BlockingReason.MISSING_GRADE: "Note fehlt",
    BlockingReason.MISSING_LABEL_TYPE: "Label-Typ fehlt (z. B. Pristine oder Gem Mint)",
    BlockingReason.MISSING_PLATFORM: "Plattform fehlt",
    BlockingReason.MISSING_REGION: "Region fehlt",
    BlockingReason.MISSING_COMPLETENESS: "Vollständigkeit fehlt (lose, CIB, sealed)",
    BlockingReason.MISSING_SERIES: "Serie fehlt",
    BlockingReason.MISSING_VOLUME: "Band oder Ausgabe fehlt",
    BlockingReason.MISSING_BRAND: "Marke fehlt",
    BlockingReason.MISSING_MODEL: "Modell fehlt",
    BlockingReason.MISSING_VARIANT: "preisrelevante Variante fehlt",
    BlockingReason.FIELD_UNTRUSTED: "Ein Merkmal ist nur geraten oder ungeprüft",
    BlockingReason.AMBIGUOUS_VARIANT: "Mehrere Modelle passen — bitte tippen",
    BlockingReason.LEGACY_UNCHECKED: "Alte Erkennung — bitte prüfen",
}


def clip_evidence(text: str | None) -> str | None:
    if text is None:
        return None
    s = " ".join(str(text).split())
    if not s:
        return None
    if len(s) > MAX_EVIDENCE_LEN:
        return s[: MAX_EVIDENCE_LEN - 1] + "…"
    return s


class FieldValue(BaseModel):
    """Ein wertrelevantes Feld inkl. Herkunft und kurzer Evidenz."""
    value: Optional[str] = Field(None, max_length=160)
    source: FieldSource = FieldSource.unknown
    evidence: Optional[str] = Field(None, max_length=MAX_EVIDENCE_LEN)

    @field_validator("evidence", mode="before")
    @classmethod
    def _clip(cls, v):
        return clip_evidence(v)

    @field_validator("value", mode="before")
    @classmethod
    def _strip_value(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None


def field(
    value: Any = None,
    source: FieldSource | str = FieldSource.unknown,
    evidence: str | None = None,
) -> FieldValue:
    src = source if isinstance(source, FieldSource) else FieldSource(source)
    return FieldValue(value=value, source=src, evidence=evidence)


class Identity(BaseModel):
    """Kanonische Produkt-Identität für Erkennung, Preis und Listing."""
    kind: Optional[ProductKind] = None
    kind_source: FieldSource = FieldSource.unknown
    game: FieldValue = Field(default_factory=FieldValue)
    name: FieldValue = Field(default_factory=FieldValue)
    number: FieldValue = Field(default_factory=FieldValue)
    set_total: FieldValue = Field(default_factory=FieldValue)
    set_name: FieldValue = Field(default_factory=FieldValue)
    language: FieldValue = Field(default_factory=FieldValue)
    edition: FieldValue = Field(default_factory=FieldValue)
    platform: FieldValue = Field(default_factory=FieldValue)
    region: FieldValue = Field(default_factory=FieldValue)
    completeness: FieldValue = Field(default_factory=FieldValue)
    grader: FieldValue = Field(default_factory=FieldValue)
    grade: FieldValue = Field(default_factory=FieldValue)
    label_type: FieldValue = Field(default_factory=FieldValue)
    cert_number: FieldValue = Field(default_factory=FieldValue)
    series: FieldValue = Field(default_factory=FieldValue)
    volume: FieldValue = Field(default_factory=FieldValue)
    brand: FieldValue = Field(default_factory=FieldValue)
    model: FieldValue = Field(default_factory=FieldValue)
    variant: FieldValue = Field(default_factory=FieldValue)
    candidates: list[str] = Field(default_factory=list, max_length=12)
    legacy_unchecked: bool = False


class IdentityEvaluation(BaseModel):
    recognition_state: RecognitionState
    pricing_ready: bool
    listing_ready: bool
    blocking_reasons: list[BlockingReason] = Field(default_factory=list)
    canonical: dict[str, str] = Field(default_factory=dict)
    identity_key: str = ""


def _has_value(fv: FieldValue) -> bool:
    return bool(fv and fv.value)


def _is_trusted(fv: FieldValue) -> bool:
    return _has_value(fv) and fv.source.value in TRUSTED_SOURCES


def _require(
    fv: FieldValue,
    missing: BlockingReason,
    reasons: list[BlockingReason],
    untrusted_fields: list[str],
    name: str,
) -> None:
    if not _has_value(fv):
        if missing not in reasons:
            reasons.append(missing)
        return
    if not _is_trusted(fv):
        untrusted_fields.append(name)
        if BlockingReason.FIELD_UNTRUSTED not in reasons:
            reasons.append(BlockingReason.FIELD_UNTRUSTED)


def _canon_put(out: dict[str, str], key: str, fv: FieldValue) -> None:
    if _is_trusted(fv) and fv.value:
        out[key] = fv.value


def _normalize_completeness(raw: str | None) -> str | None:
    if not raw:
        return None
    s = " ".join(str(raw).strip().lower().replace("-", " ").split())
    aliases = {
        "loose": Completeness.loose.value,
        "disc": Completeness.loose.value,
        "disc only": Completeness.loose.value,
        "cart": Completeness.loose.value,
        "cartridge": Completeness.loose.value,
        "manual": Completeness.manual.value,
        "cib": Completeness.cib.value,
        "complete": Completeness.cib.value,
        "complete in box": Completeness.cib.value,
        "sealed": Completeness.sealed.value,
        "new sealed": Completeness.sealed.value,
        "ovp": Completeness.sealed.value,
    }
    return aliases.get(s) or (s if s in {c.value for c in Completeness} else raw.strip())


def evaluate_identity(identity: Identity) -> IdentityEvaluation:
    """Zentrale Policy: ready / needs_review / unknown + pricing-/listing-ready."""
    reasons: list[BlockingReason] = []
    untrusted: list[str] = []
    canonical: dict[str, str] = {}

    if identity.legacy_unchecked:
        reasons.append(BlockingReason.LEGACY_UNCHECKED)

    if identity.kind is None:
        reasons.append(BlockingReason.MISSING_KIND)
        return IdentityEvaluation(
            recognition_state=RecognitionState.unknown,
            pricing_ready=False,
            listing_ready=False,
            blocking_reasons=reasons,
            canonical={},
            identity_key="",
        )

    if (identity.kind_source.value not in TRUSTED_SOURCES
            and not identity.legacy_unchecked):
        if identity.kind_source in (FieldSource.inferred, FieldSource.unknown):
            reasons.append(BlockingReason.FIELD_UNTRUSTED)
            untrusted.append("kind")

    kind = identity.kind
    canonical["kind"] = kind.value

    if identity.candidates and len(identity.candidates) >= 2:
        if not _is_trusted(identity.variant) and not _is_trusted(identity.model):
            reasons.append(BlockingReason.AMBIGUOUS_VARIANT)

    if kind in (ProductKind.raw_card, ProductKind.graded_slab):
        _require(identity.game, BlockingReason.MISSING_GAME, reasons, untrusted, "game")
        _require(identity.name, BlockingReason.MISSING_NAME, reasons, untrusted, "name")
        _require(identity.number, BlockingReason.MISSING_NUMBER, reasons, untrusted, "number")
        if not _has_value(identity.set_name) and not _has_value(identity.set_total):
            reasons.append(BlockingReason.MISSING_SET)
        else:
            if _has_value(identity.set_name):
                _require(identity.set_name, BlockingReason.MISSING_SET, reasons, untrusted, "set_name")
            if _has_value(identity.set_total):
                _require(identity.set_total, BlockingReason.MISSING_SET, reasons, untrusted, "set_total")
        _require(identity.language, BlockingReason.MISSING_LANGUAGE, reasons, untrusted, "language")
        if _has_value(identity.edition):
            _require(identity.edition, BlockingReason.MISSING_EDITION, reasons, untrusted, "edition")

        for key, fv in (
            ("game", identity.game),
            ("name", identity.name),
            ("number", identity.number),
            ("set_name", identity.set_name),
            ("set_total", identity.set_total),
            ("language", identity.language),
            ("edition", identity.edition),
        ):
            _canon_put(canonical, key, fv)

        if kind == ProductKind.graded_slab:
            _require(identity.grader, BlockingReason.MISSING_GRADER, reasons, untrusted, "grader")
            _require(identity.grade, BlockingReason.MISSING_GRADE, reasons, untrusted, "grade")
            g_kanon = kanon_grader(identity.grader.value) if identity.grader.value else None
            if g_kanon in ("CGC", "BGS"):
                _require(
                    identity.label_type,
                    BlockingReason.MISSING_LABEL_TYPE,
                    reasons,
                    untrusted,
                    "label_type",
                )
            for key, fv in (
                ("grader", identity.grader),
                ("grade", identity.grade),
                ("label_type", identity.label_type),
                ("cert_number", identity.cert_number),
            ):
                _canon_put(canonical, key, fv)
            if _is_trusted(identity.grader) and _is_trusted(identity.grade):
                kg, ng = normalize_grade(identity.grader.value, identity.grade.value)
                if kg:
                    canonical["grader"] = kg
                if ng:
                    canonical["grade"] = ng
            if _is_trusted(identity.label_type):
                lt = normalize_label_type(identity.label_type.value, identity.grader.value)
                if lt:
                    canonical["label_type"] = lt
        else:
            canonical["grading"] = "raw"

    elif kind == ProductKind.video_game:
        _require(identity.name, BlockingReason.MISSING_NAME, reasons, untrusted, "name")
        _require(identity.platform, BlockingReason.MISSING_PLATFORM, reasons, untrusted, "platform")
        _require(identity.region, BlockingReason.MISSING_REGION, reasons, untrusted, "region")
        _require(
            identity.completeness,
            BlockingReason.MISSING_COMPLETENESS,
            reasons,
            untrusted,
            "completeness",
        )
        for key, fv in (
            ("name", identity.name),
            ("platform", identity.platform),
            ("region", identity.region),
            ("completeness", identity.completeness),
            ("language", identity.language),
        ):
            _canon_put(canonical, key, fv)
        if _is_trusted(identity.completeness):
            c = _normalize_completeness(identity.completeness.value)
            if c:
                canonical["completeness"] = c
        # Graded games (WATA/VGA/CGA): Note verfeinert die Query, ist aber kein
        # Karten-Slab — fehlende Note blockiert den Marktwert nicht.
        if _has_value(identity.grader) and _has_value(identity.grade):
            for key, fv in (
                ("grader", identity.grader),
                ("grade", identity.grade),
                ("cert_number", identity.cert_number),
            ):
                _canon_put(canonical, key, fv)
            if _is_trusted(identity.grader) and _is_trusted(identity.grade):
                kg, ng = normalize_grade(identity.grader.value, identity.grade.value)
                if kg:
                    canonical["grader"] = kg
                if ng:
                    canonical["grade"] = ng

    elif kind == ProductKind.manga_comic:
        _require(identity.series, BlockingReason.MISSING_SERIES, reasons, untrusted, "series")
        _require(identity.volume, BlockingReason.MISSING_VOLUME, reasons, untrusted, "volume")
        _require(identity.language, BlockingReason.MISSING_LANGUAGE, reasons, untrusted, "language")
        if _has_value(identity.edition):
            _require(identity.edition, BlockingReason.MISSING_EDITION, reasons, untrusted, "edition")
        else:
            reasons.append(BlockingReason.MISSING_EDITION)
        for key, fv in (
            ("series", identity.series),
            ("volume", identity.volume),
            ("language", identity.language),
            ("edition", identity.edition),
            ("name", identity.name),
        ):
            _canon_put(canonical, key, fv)
        # Graded Manga/Comic (Beckett/CGC): Note verfeinert die Query, kein Karten-Label.
        if _has_value(identity.grader) and _has_value(identity.grade):
            for key, fv in (
                ("grader", identity.grader),
                ("grade", identity.grade),
                ("cert_number", identity.cert_number),
            ):
                _canon_put(canonical, key, fv)
            if _is_trusted(identity.grader) and _is_trusted(identity.grade):
                kg, ng = normalize_grade(identity.grader.value, identity.grade.value)
                if kg:
                    canonical["grader"] = kg
                if ng:
                    canonical["grade"] = ng

    else:
        _require(identity.brand, BlockingReason.MISSING_BRAND, reasons, untrusted, "brand")
        _require(identity.model, BlockingReason.MISSING_MODEL, reasons, untrusted, "model")
        if identity.candidates or _has_value(identity.variant):
            _require(identity.variant, BlockingReason.MISSING_VARIANT, reasons, untrusted, "variant")
        for key, fv in (
            ("brand", identity.brand),
            ("model", identity.model),
            ("variant", identity.variant),
            ("name", identity.name),
        ):
            _canon_put(canonical, key, fv)

    seen: set[BlockingReason] = set()
    uniq: list[BlockingReason] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    reasons = uniq

    if BlockingReason.MISSING_KIND in reasons:
        state = RecognitionState.unknown
    elif not reasons:
        state = RecognitionState.ready
    else:
        state = RecognitionState.needs_review

    pricing_ready = state == RecognitionState.ready and not reasons
    listing_ready = pricing_ready

    key_parts = [f"{k}={canonical[k]}" for k in sorted(canonical)]
    identity_key = "|".join(key_parts)

    return IdentityEvaluation(
        recognition_state=state,
        pricing_ready=pricing_ready,
        listing_ready=listing_ready,
        blocking_reasons=reasons,
        canonical=canonical,
        identity_key=identity_key,
    )


def apply_user_correction(
    identity: Identity,
    field_name: str,
    value: str,
    *,
    evidence: str | None = None,
) -> Identity:
    """Nutzerkorrektur -> user_provided; Legacy-Flag wird gelöscht."""
    data = identity.model_dump()
    if field_name == "kind":
        data["kind"] = ProductKind(value)
        data["kind_source"] = FieldSource.user_provided.value
    elif field_name in data and isinstance(data[field_name], dict):
        data[field_name] = field(
            value, FieldSource.user_provided, evidence or "Nutzerkorrektur"
        ).model_dump()
    else:
        raise ValueError(f"Unbekanntes Identitätsfeld: {field_name}")
    data["legacy_unchecked"] = False
    if field_name in ("variant", "model", "kind") and data.get("candidates"):
        data["candidates"] = []
    return Identity.model_validate(data)


def _fv_from_legacy(value: Any, *, evidence: str | None = None) -> FieldValue:
    if value is None or value == "":
        return field(None, FieldSource.unknown, evidence)
    return field(value, FieldSource.inferred, evidence or "legacy_analysis")


def normalize_legacy_analysis(
    analysis: dict | None = None,
    *,
    card_info: dict | None = None,
    graded: dict | None = None,
    category: str | None = None,
) -> Identity:
    """Alte Analyse-/card_info-Objekte lesbar machen — ehrlich als ungeprüft.

    Keine Massmigration. Freie search_query_for_pricing wird nicht übernommen.
    """
    analysis = analysis or {}
    card_info = card_info or {}
    graded = graded or analysis.get("graded_info") or {}

    kind: ProductKind | None = None
    kind_source = FieldSource.unknown

    cat = (category or analysis.get("category_query") or "").lower()
    title = analysis.get("title") or card_info.get("name") or ""
    grader = graded.get("grader") if graded else None
    aspects = analysis.get("aspects") or {}
    as_game = (
        _is_game_grader(grader)
        or _text_looks_like_game(cat, title, category)
        or _category_suggests_video_game(cat)
        or _category_suggests_video_game(category)
    )
    as_manga = (
        _text_looks_like_manga_comic(cat, title, category, analysis.get("category_query"))
        or _aspect_suggests_manga_comic(aspects)
        or str(card_info.get("edition") or "").lower() in ("manga", "comic")
    )
    if card_info.get("single") or (card_info.get("number") and (
            card_info.get("set") or card_info.get("set_hint"))):
        as_manga = False
    if graded and graded.get("grade") and not as_game and not as_manga:
        kind = ProductKind.graded_slab
        kind_source = FieldSource.inferred
    elif as_manga:
        kind = ProductKind.manga_comic
        kind_source = FieldSource.inferred
    elif as_game and (
        (graded and graded.get("grade"))
        or _category_suggests_video_game(cat)
        or _category_suggests_video_game(category)
        or _text_looks_like_game(title)
    ):
        kind = ProductKind.video_game
        kind_source = FieldSource.inferred
    elif card_info.get("name") or card_info.get("number"):
        kind = ProductKind.raw_card
        kind_source = FieldSource.inferred
    elif any(w in cat for w in ("manga", "comic", "band ")):
        kind = ProductKind.manga_comic
        kind_source = FieldSource.inferred
    elif analysis.get("title") or analysis.get("category_query"):
        kind = ProductKind.generic
        kind_source = FieldSource.inferred

    name = card_info.get("name") or analysis.get("title")
    if kind == ProductKind.video_game:
        name = _clean_game_title(name) or name
    number = card_info.get("number") or card_info.get("local_id")
    set_total = card_info.get("set_total") or card_info.get("printed_total")
    set_name = (
        card_info.get("set") or card_info.get("set_name") or card_info.get("set_id")
        or card_info.get("set_hint")
    )
    language = card_info.get("language") or card_info.get("lang")
    game = card_info.get("game") or card_info.get("tcg") or card_info.get("series")

    grade = graded.get("grade") if graded else None
    label_type = graded.get("label_type") if graded else None
    cert = (graded.get("cert_number") or graded.get("cert")) if graded else None

    if not language:
        language = _first_aspect(aspects, "Sprache", "Language", "Sprachversion")
    if not language:
        language = infer_language_from_text(name, title, analysis.get("title"))
    brand = _first_aspect(aspects, "Marke", "Brand")
    model = _first_aspect(aspects, "Modell", "Model")
    # Beschreibung oft schon mit Region/NTSC — sonst hängt Games-Preflight ewig.
    hint = _plain_blob(
        title, name, analysis.get("subtitle"),
        analysis.get("description_html"), analysis.get("description_plain"),
        analysis.get("category_query"),
    )
    platform = (
        _first_aspect(aspects, "Plattform", "Platform")
        or card_info.get("platform")
        or _infer_platform(hint)
    )
    region = (
        _first_aspect(aspects, "Region", "Länderversion")
        or card_info.get("region")
        or _infer_region(hint)
    )
    completeness = (
        card_info.get("completeness")
        or card_info.get("complete")
        or _infer_completeness(hint)
    )

    manga_series, manga_volume = _infer_manga_series_volume(
        title, aspects, card_info)
    manga_edition = (
        card_info.get("edition")
        if str(card_info.get("edition") or "").lower() not in ("manga", "comic")
        else None
    ) or _infer_edition_from_text(
        title, analysis.get("description_html"), analysis.get("description_plain"),
    )

    return Identity(
        kind=kind,
        kind_source=kind_source,
        game=_fv_from_legacy(game),
        name=_fv_from_legacy(name),
        number=_fv_from_legacy(number),
        set_total=_fv_from_legacy(set_total),
        set_name=_fv_from_legacy(set_name),
        language=_fv_from_legacy(language),
        edition=_fv_from_legacy(manga_edition or card_info.get("edition") or card_info.get("rarity")),
        platform=_fv_from_legacy(platform),
        region=_fv_from_legacy(region),
        completeness=_fv_from_legacy(completeness),
        grader=_fv_from_legacy(grader),
        grade=_fv_from_legacy(grade),
        label_type=_fv_from_legacy(label_type),
        cert_number=_fv_from_legacy(cert),
        series=_fv_from_legacy(manga_series or card_info.get("series") or game),
        volume=_fv_from_legacy(manga_volume or card_info.get("volume") or card_info.get("number")),
        brand=_fv_from_legacy(brand),
        model=_fv_from_legacy(model),
        variant=_fv_from_legacy(None),
        candidates=[],
        legacy_unchecked=True,
    )


def _first_aspect(aspects: dict, *keys: str) -> str | None:
    for k in keys:
        v = aspects.get(k)
        if isinstance(v, list) and v:
            return str(v[0])
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def blocking_texts(reasons: list[BlockingReason]) -> list[str]:
    """Deutsche UI-Zeilen zu Blocking-Codes."""
    return [BLOCKING_REASON_DE[r] for r in reasons if r in BLOCKING_REASON_DE]


# ── A4: Deterministische Preis-Query aus freigegebener Identity ───────────────

_LANG_QUERY = {
    "de": "Deutsch", "ger": "Deutsch", "german": "Deutsch", "deu": "Deutsch",
    "ja": "Japanisch", "jp": "Japanisch", "jpn": "Japanisch", "japanese": "Japanisch",
    "en": "English", "eng": "English", "english": "English",
    "fr": "Francais", "fra": "Francais", "french": "Francais",
    "it": "Italiano", "ita": "Italiano",
    "es": "Espanol", "spa": "Espanol",
    "ko": "Koreanisch", "kor": "Koreanisch",
    "zh": "Chinesisch", "cn": "Chinesisch",
    "pt": "Portugues",
}

# Titel/Name enthalten oft schon die Sprache („… Japanisch CGC 10").
_LANG_HINT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Japanisch|Japanese|\bJP\b|日本語", re.I), "Japanisch"),
    (re.compile(r"Englisch|English|\bEN\b|\bENG\b", re.I), "Englisch"),
    (re.compile(r"Deutsch|German|\bDE\b", re.I), "Deutsch"),
    (re.compile(r"Koreanisch|Korean|\bKR\b", re.I), "Koreanisch"),
    (re.compile(r"Chinesisch|Chinese|\bCN\b|简体|繁體", re.I), "Chinesisch"),
    (re.compile(r"Französisch|French|\bFR\b", re.I), "Französisch"),
    (re.compile(r"Italienisch|Italian|\bIT\b", re.I), "Italienisch"),
    (re.compile(r"Spanisch|Spanish|\bES\b", re.I), "Spanisch"),
]


def infer_language_from_text(*parts: object) -> str | None:
    """Sprache aus Titel/Name ziehen — gleiche Heuristik wie die App-UI."""
    blob = " ".join(str(p) for p in parts if p)
    if not blob:
        return None
    for rx, lab in _LANG_HINT_PATTERNS:
        if rx.search(blob):
            return lab
    return None

_COMPLETENESS_QUERY = {
    "loose": "Disc only",
    "manual": "manual",
    "cib": "CIB",
    "sealed": "sealed",
}


def _lang_token(raw: str | None) -> str | None:
    if not raw:
        return None
    key = " ".join(str(raw).strip().lower().replace("_", " ").split())
    if key in _LANG_QUERY:
        return _LANG_QUERY[key]
    # schon ausgeschrieben?
    for v in _LANG_QUERY.values():
        if key == v.lower():
            return v
    return str(raw).strip()


def _parts(*tokens: str | None) -> str:
    out: list[str] = []
    for t in tokens:
        if t is None:
            continue
        s = " ".join(str(t).split())
        if s:
            out.append(s)
    return " ".join(out)


def build_pricing_query(identity: Identity) -> str | None:
    """Suchbegriff nur aus serverseitig freigegebener Identity.

    Ohne pricing_ready: None. Freier LLM-Text / search_query_for_pricing
    fließt hier nie ein.
    """
    ev = evaluate_identity(identity)
    if not ev.pricing_ready:
        return None
    c = ev.canonical
    kind = c.get("kind")

    if kind in ("raw_card", "graded_slab"):
        num = c.get("number")
        total = c.get("set_total")
        set_name = c.get("set_name")
        # OP03 + 55 → OP03-055, P + 74 → P-074 — sonst trifft PriceCharting/TCG die
        # falsche Karte oder gar keine (Slab-Rohpreis wird danach verworfen).
        code = None
        if set_name and num and not total:
            sn, nu = str(set_name).strip(), str(num).strip()
            if re.match(r"^[A-Za-z]{1,4}\d{0,2}$", sn) and nu.isdigit():
                code = f"{sn.upper()}-{int(nu):03d}"
            elif re.match(r"^[A-Za-z]{1,3}$", sn) and nu.isdigit():
                code = f"{sn.upper()}-{int(nu):03d}"
        if code:
            nummer = code
        elif num and total:
            nummer = f"{num}/{total}"
        else:
            nummer = num or ""
        lang = _lang_token(c.get("language"))
        ed = c.get("edition")
        # Parallel (One Piece) und Alternate Art (PriceCharting/TCG) sind dieselbe
        # Druckfamilie — beide Tokens in die Query, sonst landet der Basis-Rare-Preis.
        ed_parts: list[str] = []
        if ed:
            ed_parts.append(str(ed))
            low = str(ed).lower()
            if "parallel" in low and "alternate" not in low:
                ed_parts.append("Alternate Art")
            elif "alt" in low and "parallel" not in low:
                ed_parts.append("Parallel")
        base = _parts(
            c.get("game"),
            c.get("name"),
            nummer or None,
            None if code else set_name,  # Code enthält das Set schon
            lang,
            *ed_parts,
        )
        if kind == "graded_slab":
            from web.slab import grade_display
            tag = grade_display({
                "grader": c.get("grader"),
                "grade": c.get("grade"),
                "label_type": c.get("label_type"),
            })
            return _parts(base, tag) or None
        return base or None

    if kind == "video_game":
        comp = c.get("completeness")
        comp_q = _COMPLETENESS_QUERY.get(comp or "", comp)
        base = _parts(
            c.get("name"),
            c.get("platform"),
            c.get("region"),
            comp_q,
            _lang_token(c.get("language")),
        )
        if c.get("grader") and c.get("grade"):
            from web.slab import grade_display
            tag = grade_display({
                "grader": c.get("grader"),
                "grade": c.get("grade"),
            })
            return _parts(base, tag) or None
        return base or None

    if kind == "manga_comic":
        vol = c.get("volume")
        band = f"Band {vol}" if vol and not str(vol).lower().startswith("band") else vol
        base = _parts(
            c.get("series") or c.get("name"),
            band,
            _lang_token(c.get("language")),
            c.get("edition"),
        )
        if c.get("grader") and c.get("grade"):
            from web.slab import grade_display
            tag = grade_display({
                "grader": c.get("grader"),
                "grade": c.get("grade"),
            })
            return _parts(base, tag) or None
        return base or None

    # generic
    return _parts(
        c.get("brand"),
        c.get("model"),
        c.get("variant"),
        c.get("name"),
    ) or None


def pricing_cache_key(identity: Identity) -> str | None:
    """Cache-/Katalogschluessel: deterministic aus identity_key, nur wenn pricing_ready."""
    ev = evaluate_identity(identity)
    if not ev.pricing_ready or not ev.identity_key:
        return None
    return f"idv1|{ev.identity_key}"


def _fv(value, source: FieldSource, evidence: str | None = None) -> FieldValue:
    if value is None or value == "":
        return field(None, FieldSource.unknown, evidence)
    return field(value, source, evidence)


def _identity_from_facts(
    card_info: dict,
    graded: dict,
    analysis: dict,
    item: dict,
    *,
    source: FieldSource,
) -> Identity:
    """Scan-/Faktenpfad: vorhandene Felder mit trusted source (kein Legacy-Flag)."""
    aspects = analysis.get("aspects") or {}
    name = card_info.get("name") or item.get("name") or analysis.get("title")
    number = card_info.get("number") or card_info.get("local_id")
    set_total = card_info.get("set_total") or card_info.get("printed_total")
    set_name = (
        card_info.get("set") or card_info.get("set_name") or card_info.get("set_id")
        or card_info.get("set_hint")
    )
    language = card_info.get("language") or card_info.get("lang")
    if not language:
        language = _first_aspect(aspects, "Sprache", "Language", "Sprachversion")
    if not language:
        language = infer_language_from_text(
            name,
            item.get("name"),
            analysis.get("title"),
            (item.get("card") or {}).get("language") if isinstance(item.get("card"), dict) else None,
        )
    game = card_info.get("game") or card_info.get("tcg") or card_info.get("series")
    brand = _first_aspect(aspects, "Marke", "Brand") or card_info.get("brand")
    model = _first_aspect(aspects, "Modell", "Model") or card_info.get("model")
    platform = (card_info.get("platform")
                or _first_aspect(aspects, "Plattform", "Platform"))
    region = (card_info.get("region")
              or _first_aspect(aspects, "Region", "Länderversion"))
    completeness = card_info.get("completeness") or card_info.get("complete")

    kind = None
    kind_source = FieldSource.unknown
    pk_raw = (analysis.get("product_kind") or analysis.get("kind")
              or card_info.get("product_kind") or "")
    if isinstance(pk_raw, str):
        pk_raw = pk_raw.strip().lower()
    else:
        pk_raw = ""
    hint = " ".join(str(x) for x in (
        item.get("name"), item.get("category"), analysis.get("title"),
        analysis.get("category_query"), card_info.get("name"),
    ) if x)
    as_game = (
        _is_game_grader(graded.get("grader"))
        or _text_looks_like_game(hint, item.get("category"), analysis.get("category_query"))
    )
    # Einzelkarte aus card_info schlägt den Videospiel-Hinweis
    if card_info.get("single") or (str(game or "").lower() in {
        "pokemon", "onepiece", "magic", "yugioh", "lorcana", "dragonball",
        "digimon", "starwars", "fab", "sport",
    }):
        as_game = False
    as_manga = (
        _text_looks_like_manga_comic(hint, item.get("category"), analysis.get("category_query"))
        or _aspect_suggests_manga_comic(aspects)
        or str(card_info.get("edition") or "").lower() in ("manga", "comic")
    )
    if card_info.get("single") or (card_info.get("number") and (
            card_info.get("set") or card_info.get("set_hint") or set_name)):
        as_manga = False
    if graded and graded.get("grade") and not as_game and not as_manga:
        kind, kind_source = ProductKind.graded_slab, source
    elif as_manga:
        kind, kind_source = ProductKind.manga_comic, source
    elif pk_raw and not as_game and not as_manga:
        try:
            kind, kind_source = ProductKind(pk_raw), source
        except ValueError:
            kind = None
    if kind is None and as_game:
        kind, kind_source = ProductKind.video_game, source
    if kind is None:
        if card_info.get("number") or (
                card_info.get("name") and (game or card_info.get("set"))):
            kind, kind_source = ProductKind.raw_card, source
        else:
            cat = (item.get("category") or analysis.get("category_query") or "").lower()
            if any(w in cat for w in ("manga", "comic")):
                kind, kind_source = ProductKind.manga_comic, FieldSource.inferred
            elif _category_suggests_video_game(cat):
                kind, kind_source = ProductKind.video_game, FieldSource.inferred
            elif brand or model or analysis.get("title"):
                kind, kind_source = ProductKind.generic, source

    # Titel + Beschreibung + Aspects — Region steckt oft nur im Fließtext.
    hint = _plain_blob(
        item.get("name"), item.get("category"), analysis.get("title"),
        analysis.get("subtitle"), analysis.get("category_query"),
        analysis.get("description_html"), analysis.get("description_plain"),
        card_info.get("name"),
        _first_aspect(aspects, "Plattform", "Platform"),
        _first_aspect(aspects, "Region", "Länderversion"),
        _first_aspect(aspects, "Spielname"),
    )
    if kind == ProductKind.video_game:
        name = _clean_game_title(name) or name
        platform = platform or _infer_platform(hint)
        region = region or _infer_region(hint)
        completeness = completeness or _infer_completeness(hint)

    cands = analysis.get("identity_candidates")
    if not isinstance(cands, list):
        cands = []

    manga_series, manga_volume = _infer_manga_series_volume(
        name or analysis.get("title"), aspects, card_info)
    manga_edition = (
        card_info.get("edition")
        if str(card_info.get("edition") or "").lower() not in ("manga", "comic")
        else None
    ) or _infer_edition_from_text(
        name, analysis.get("title"), analysis.get("description_html"),
        analysis.get("description_plain"),
    )

    return Identity(
        kind=kind,
        kind_source=kind_source,
        game=_fv(game, source),
        name=_fv(name, source),
        number=_fv(number, source),
        set_total=_fv(set_total, source),
        set_name=_fv(set_name, source),
        language=_fv(language, source),
        edition=_fv(manga_edition or card_info.get("edition"), source),
        platform=_fv(platform, source if platform else FieldSource.unknown),
        region=_fv(region, source if region else FieldSource.unknown),
        completeness=_fv(completeness, source if completeness else FieldSource.unknown),
        grader=_fv(graded.get("grader"), source, "slab"),
        grade=_fv(graded.get("grade"), source, "slab"),
        label_type=_fv(graded.get("label_type"), source, "slab"),
        cert_number=_fv(graded.get("cert_number") or graded.get("cert"), source, "slab"),
        series=_fv(manga_series or card_info.get("series") or game, source),
        volume=_fv(manga_volume or card_info.get("volume"), source),
        brand=_fv(brand, source),
        model=_fv(model, source),
        variant=_fv(None, FieldSource.unknown),
        candidates=[str(x)[:80] for x in cands if str(x).strip()][:8],
        legacy_unchecked=False,
    )


def identity_from_item(item: dict | None) -> Identity:
    """Identity aus Sammlungsstück oder Listing-ähnlichem Dict."""
    item = item or {}
    analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else {}
    card_info = item.get("card_info") if isinstance(item.get("card_info"), dict) else {}
    graded = item.get("graded") if isinstance(item.get("graded"), dict) else {}
    if not graded:
        gi = analysis.get("graded_info")
        graded = gi if isinstance(gi, dict) else {}

    if card_info:
        from web.prices import normalize_card_edition
        card_info = normalize_card_edition(
            dict(card_info),
            item.get("name"),
            analysis.get("title"),
            (analysis.get("category_query") if isinstance(analysis, dict) else None),
        )

    if card_info or (graded and graded.get("grade")):
        src = FieldSource.catalog_verified if item.get("card") else FieldSource.visible_on_photo
        return _identity_from_facts(card_info, graded, analysis, item, source=src)

    return normalize_legacy_analysis(
        analysis,
        card_info=card_info or None,
        graded=graded or None,
        category=item.get("category"),
    )


def identity_from_listing(listing: dict | None) -> Identity:
    listing = listing or {}
    return identity_from_item({
        "analysis": listing,
        "card_info": listing.get("card_info"),
        "graded": listing.get("graded_info"),
        "name": listing.get("title"),
        "category": listing.get("category_query"),
        "card": listing.get("card"),
    })


def resolve_pricing_query(item_or_listing: dict | None, *, is_listing: bool = False
                          ) -> tuple[str | None, bool, Identity, IdentityEvaluation]:
    """(query|None, pricing_ready, identity, evaluation).

    Freie search_query_for_pricing wird bewusst ignoriert.
    """
    ident = (identity_from_listing(item_or_listing) if is_listing
             else identity_from_item(item_or_listing))
    ev = evaluate_identity(ident)
    q = build_pricing_query(ident) if ev.pricing_ready else None
    return q, ev.pricing_ready, ident, ev


def identity_eval_payload(ev: IdentityEvaluation, query: str | None = None) -> dict:
    return {
        "recognition_state": ev.recognition_state.value,
        "pricing_ready": ev.pricing_ready,
        "listing_ready": ev.listing_ready,
        "blocking_reasons": [r.value for r in ev.blocking_reasons],
        "blocking_texts": blocking_texts(ev.blocking_reasons),
        "identity_key": ev.identity_key,
        "pricing_query": query,
    }


def canonical_identity_payload(ident: Identity, ev: IdentityEvaluation) -> dict:
    """Persistierbare CanonicalItemIdentity (feldweise aus trusted Canonical)."""
    out = dict(ev.canonical or {})
    out["kind"] = ident.kind.value if ident.kind else None
    out["identity_key"] = ev.identity_key
    out["alternatives"] = list(ident.candidates or [])[:8]
    # Feld-Quellen für Debug/UI (nur trusted Werte)
    fields: dict[str, dict] = {}
    for key in (
        "game", "name", "number", "set_name", "set_total", "language", "edition",
        "platform", "region", "completeness", "grader", "grade", "label_type",
        "cert_number", "series", "volume", "brand", "model", "variant",
    ):
        fv = getattr(ident, key, None)
        if fv is None:
            continue
        if isinstance(fv, FieldValue) and fv.value not in (None, ""):
            fields[key] = {
                "value": fv.value,
                "source": fv.source.value if hasattr(fv.source, "value") else fv.source,
                "evidence": fv.evidence,
            }
    out["fields"] = fields
    return out


def apply_listing_review_to_item(
    item: dict,
    draft: dict | None = None,
    *,
    user_confirmed: bool = False,
) -> tuple[bool, str | None]:
    """Nach Listing-Review: Identity neu bewerten und Blocker ggf. freigeben.

    Nutzt aktuelle Draft-Felder (Titel, Aspects, Beschreibung). Gibt
    ``(True, None)`` wenn Publish-Blocker geklärt sind.
    Karten ohne klare Zuordnung bleiben auch nach Confirm gesperrt.
    """
    item = item  # in-place
    draft = draft or {}
    listing = draft.get("listing") or {}

    analysis = dict(item.get("analysis") or {})
    if listing.get("title"):
        analysis["title"] = listing["title"]
        item["name"] = listing["title"]
    aspects = dict(analysis.get("aspects") or {})
    for k, v in (listing.get("aspects") or {}).items():
        aspects[k] = v
    analysis["aspects"] = aspects
    for k in ("description_html", "description_plain", "subtitle"):
        if listing.get(k):
            analysis[k] = listing[k]
    item["analysis"] = analysis

    # Region/Plattform aus Aspects in card_info spiegeln (Faktenpfad liest beides).
    ci = dict(item.get("card_info") or {})
    region_asp = _first_aspect(aspects, "Region", "Länderversion")
    plat_asp = _first_aspect(aspects, "Plattform", "Platform")
    if region_asp:
        ci["region"] = region_asp
    if plat_asp:
        ci["platform"] = plat_asp
    if ci:
        item["card_info"] = ci

    was_confirmed = bool(item.get("identity_user_confirmed"))
    _pq, _ready, _ident, _ev = resolve_pricing_query(item)
    item["identity_eval"] = identity_eval_payload(_ev, _pq)
    item["canonical_identity"] = canonical_identity_payload(_ident, _ev)

    kind = _ident.kind
    is_card = kind in (ProductKind.raw_card, ProductKind.graded_slab)

    if _ev.recognition_state == RecognitionState.ready:
        item["status"] = "ready"
        item["status_text"] = None
        item["error"] = None
        item.pop("identity_user_confirmed", None)
        item.pop("review_question", None)
        return True, None

    # Frühere Listing-Confirm bei Games/Generic nicht durch Re-Eval verlieren
    # (z. B. Preis/Titel-Edit nach Bestätigung).
    if was_confirmed and not is_card and not user_confirmed:
        item["identity_user_confirmed"] = True
        item["status"] = "ready"
        item["status_text"] = None
        item["error"] = None
        payload = item["identity_eval"]
        payload["listing_ready"] = True
        item["identity_eval"] = payload
        return True, None

    # Eval aktualisiert (UI sieht aktuelle Blocker), Status nur bei Confirm.
    if not user_confirmed:
        return False, None

    if is_card:
        return False, (
            "Karte zuerst von Hand zuordnen oder fehlende Angaben tippen "
            "— Bestätigen allein reicht bei unsicherer Kartenzuordnung nicht."
        )

    # Games / Generic / Manga: Nutzer hat Listing-Review bestätigt.
    item["identity_user_confirmed"] = True
    item["status"] = "ready"
    item["status_text"] = None
    item["error"] = None
    item.pop("review_question", None)
    payload = item["identity_eval"]
    payload["listing_ready"] = True
    item["identity_eval"] = payload
    return True, None

