"""Deterministisches Typ-Routing für CutoutPipelineV2.

Drei Scan-Routen (Klassifikation VOR dem Freistellen):

  product — Alltagsstück (Flasche, Schuhe, Fernbedienung, Buch): kein Warp, nur rembg.
  card    — Rohkarte / Hülle: alte Rechteck-Technik (Warp aufs Rechteck, dann rembg).
  slab    — Graded-Case: Warp aufs Case (nicht die Karte im Fenster), dann rembg.
"""
from __future__ import annotations

from typing import Any, Sequence

from web.cutout_v2.types import (
    CutoutKind,
    KindResolveState,
    KindSource,
    legacy_kind_to_cutout,
)

# Warp (Perspektive/Aufrichten) für flache Karten und Cases.
# Flasche, Sneaker, Handy: Zylinder/3D — Warp verbiegt das Motiv.
FLAT_CARD_IDENTITY = frozenset({"raw_card", "graded_slab"})
NON_CARD_IDENTITY = frozenset({"generic", "video_game", "manga_comic"})
CARD_CUTOUT_KINDS = frozenset({"slab", "sleeve", "raw"})
PRODUCT_CUTOUT_KINDS = frozenset({"other", "product", "bundle"})
SCAN_KINDS = frozenset({"product", "card", "slab"})
# Slab-Cases sind ~1,5–2,1 hoch; schlanker ist oft eine Flasche/ein Handy.
_SLAB_MAX_ASPECT = 2.2
_RAW_MAX_ASPECT = 2.0

GLANCE_PROMPT = """Du siehst ein Foto. Klassifiziere NUR den Gegenstand.
Erfinde KEINE Sammelkarte, wenn keine zu sehen ist. Antworte NUR mit JSON:
{"kind":"product"|"card"|"slab","grader":null|"PSA"|"CGC"|"BGS"|"WATA","confidence":"high"|"low"}

kind:
- product = Alltagsgegenstand oder 3D-Objekt: Flasche, Schuhe, Fernbedienung, Buch,
  Manga/Band, Dose, Sneaker, Handy, Verpackung, Konsole ohne Grading-Case.
- card = lose Sammelkarte, auch in Softsleeve/Toploader/Semi-Rigid — OHNE hartes
  Grading-Case mit Bewertungslabel.
- slab = Karte oder Spiel in hartem Grading-Case (PSA, CGC, BGS/Beckett, WATA, SGC)
  mit Bewertungslabel oben. Das Case IST das Stück.

grader: nur bei slab, sonst null. Nur setzen wenn das Label klar lesbar ist.
confidence: high nur wenn eindeutig. Im Zweifel low, kind trotzdem der beste Tipp."""


def _is_graded(item: dict[str, Any]) -> bool:
    gi = item.get("graded_info") or {}
    return bool(
        item.get("graded")
        or gi.get("grader")
        or gi.get("cert_number")
        or item.get("cert_number")
    )


def item_is_non_card(item: dict[str, Any] | None) -> bool:
    """Alltagsstück / Spiel / Manga — kein flaches Kartenfoto.

    Graded (auch WATA-Spiele im Case) bleiben Karten-Pfad: die sollen Warp.
    """
    item = item or {}
    if _is_graded(item):
        return False
    ident = item.get("canonical_identity") or {}
    kind = str(ident.get("kind") or "").strip().lower()
    if kind in FLAT_CARD_IDENTITY:
        return False
    if kind in NON_CARD_IDENTITY:
        return True
    if str(item.get("scan_kind") or "").strip().lower() == "product":
        return True
    ck = str(item.get("cutout_kind") or "").strip().lower()
    if ck in PRODUCT_CUTOUT_KINDS:
        return True
    return False


def should_warp(
    kind: str | None,
    item: dict[str, Any] | None = None,
    corners: Sequence | None = None,
) -> bool:
    """Warp für Rohkarte (Rechteck) und Graded-Case, nie für 3D-Alltag."""
    k = str(kind or "")
    if k not in ("slab", "raw"):
        return False
    if item_is_non_card(item):
        return False
    if corners and len(corners) == 4:
        try:
            xs = [float(c[0]) for c in corners]
            ys = [float(c[1]) for c in corners]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            cap = _SLAB_MAX_ASPECT if k == "slab" else _RAW_MAX_ASPECT
            if w > 0.1 and (h / w) > cap:
                return False
        except (TypeError, ValueError, IndexError):
            pass
    return True


def legacy_to_scan_kind(kind: str | None) -> str | None:
    k = str(kind or "").strip().lower()
    if k in ("product", "card", "slab"):
        return k
    if k in PRODUCT_CUTOUT_KINDS:
        return "product"
    if k in ("raw", "sleeve", "raw_card", "sleeve_toploader"):
        return "card"
    if k in ("slab", "graded_slab"):
        return "slab"
    return None


def scan_kind_to_legacy(kind: str | None) -> str | None:
    k = str(kind or "").strip().lower()
    return {"product": "other", "card": "raw", "slab": "slab"}.get(k)


def scan_kind_from_item(item: dict[str, Any] | None) -> str | None:
    """Schon bekannte Felder: graded, Identity, domain, persistierter Glance."""
    item = item or {}
    if _is_graded(item):
        return "slab"
    ident = item.get("canonical_identity") or {}
    ik = str(ident.get("kind") or "").strip().lower()
    if ik == "graded_slab":
        return "slab"
    if ik == "raw_card":
        return "card"
    if ik in NON_CARD_IDENTITY:
        return "product"
    sk = str(item.get("scan_kind") or "").strip().lower()
    if sk in SCAN_KINDS:
        return sk
    domain = str(
        item.get("domain")
        or ident.get("domain")
        or ident.get("game")
        or ""
    ).strip().lower()
    if domain == "tcg":
        return "card"
    if domain in ("comic", "game"):
        return "product"
    return legacy_to_scan_kind(item.get("cutout_kind"))


def kind_from_rectangle(aspect_hw: float, rectangularity: float) -> str | None:
    """Geometrie: flaches Rechteck → card/slab, sonst None (Alltag)."""
    if rectangularity < 0.72:
        return None
    if 1.48 <= aspect_hw <= 2.15:
        return "slab"
    if 1.15 <= aspect_hw <= 1.48:
        return "card"
    return None


def normalize_glance(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Glance-JSON auf {kind, grader, confidence} normieren."""
    if not isinstance(data, dict):
        return None
    kind = str(data.get("kind") or "").strip().lower()
    if kind in ("other", "product", "bundle", "generic"):
        kind = "product"
    elif kind in ("raw", "sleeve", "card", "raw_card"):
        kind = "card"
    elif kind in ("slab", "graded", "graded_slab"):
        kind = "slab"
    else:
        return None
    grader = data.get("grader")
    if grader is not None:
        grader = str(grader).strip().upper() or None
        if grader in ("NONE", "NULL", "N/A", "-"):
            grader = None
    conf = str(data.get("confidence") or "low").strip().lower()
    if conf not in ("high", "low"):
        conf = "low"
    return {"kind": kind, "grader": grader, "confidence": conf}


def resolve_scan_kind(
    *,
    item: dict[str, Any] | None = None,
    glance: dict[str, Any] | None = None,
    geometry_hint: str | None = None,
) -> tuple[str | None, str]:
    """product|card|slab plus Quelle. Glance unsicher + Rechteck → card/slab."""
    item = item or {}
    if _is_graded(item):
        return "slab", "item"
    ident = item.get("canonical_identity") or {}
    ik = str(ident.get("kind") or "").strip().lower()
    if ik in FLAT_CARD_IDENTITY or ik in NON_CARD_IDENTITY:
        sk = scan_kind_from_item(item)
        return sk, "item"

    g = normalize_glance(glance)
    gkind = g["kind"] if g else None
    gconf = g["confidence"] if g else "low"

    if gkind in SCAN_KINDS and gconf == "high":
        return gkind, "glance"

    geo = legacy_to_scan_kind(geometry_hint) or (
        geometry_hint if geometry_hint in SCAN_KINDS else None
    )
    if geo in ("card", "slab"):
        return geo, "geometry"

    if gkind == "product":
        return "product", "glance"

    from_item = scan_kind_from_item(item)
    if from_item:
        return from_item, "item"
    return None, "unspecified"


def apply_scan_kind(
    item: dict[str, Any],
    *,
    glance: dict[str, Any] | None = None,
    geometry_hint: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """scan_kind + cutout_kind aufs Item schreiben. Liefert Legacy-Kind für crop_photos."""
    sk, src = resolve_scan_kind(item=item, glance=glance, geometry_hint=geometry_hint)
    if sk:
        item["scan_kind"] = sk
        item["scan_kind_source"] = src
        legacy = scan_kind_to_legacy(sk)
        if legacy:
            item["cutout_kind"] = legacy
            item["cutout_kind_source"] = src
        g = normalize_glance(glance) or {}
        if sk == "slab" and g.get("grader") and not item.get("graded"):
            item["scan_grader"] = g["grader"]
        return item, legacy
    return item, None


def resolve_kind(
    *,
    item: dict[str, Any] | None = None,
    persisted_kind: str | None = None,
    geometry_hint: str | None = None,
    vision_kind: str | None = None,
    vision_error: bool = False,
) -> tuple[CutoutKind | None, KindSource, KindResolveState, float]:
    """Priorität: bestätigt → persistiert → Geometrie → ein Vision-Fallback."""
    item = item or {}

    # Alltagsstück (Identity generic): nie Karten-Warp, auch wenn Vision
    # früher "slab" persistiert hat (Augustiner-Flasche 18.08.2026).
    if item_is_non_card(item):
        return (
            CutoutKind.SEALED_PRODUCT,
            KindSource.PERSISTED,
            KindResolveState.CONFIRMED,
            0.9,
        )

    gi = item.get("graded_info") or {}
    if item.get("graded") or gi.get("grader") or gi.get("cert_number") or item.get("cert_number"):
        return CutoutKind.GRADED_SLAB, KindSource.CONFIRMED, KindResolveState.CONFIRMED, 1.0
    if item.get("cutout_kind_confirmed"):
        ck = legacy_kind_to_cutout(str(item["cutout_kind_confirmed"]))
        if ck:
            return ck, KindSource.CONFIRMED, KindResolveState.CONFIRMED, 1.0

    sk = str(item.get("scan_kind") or "").strip().lower()
    if sk in SCAN_KINDS:
        ck = legacy_kind_to_cutout(scan_kind_to_legacy(sk))
        if ck:
            src = KindSource.PERSISTED
            if item.get("scan_kind_source") == "glance":
                src = KindSource.VISION
            elif item.get("scan_kind_source") == "geometry":
                src = KindSource.GEOMETRY
            return ck, src, KindResolveState.CONFIRMED, 0.9

    pk = persisted_kind or item.get("cutout_kind")
    if pk:
        ck = legacy_kind_to_cutout(str(pk))
        if ck is None and pk in CutoutKind._value2member_map_:
            ck = CutoutKind(pk)
        if ck:
            return ck, KindSource.PERSISTED, KindResolveState.CONFIRMED, 0.95

    if geometry_hint:
        ck = legacy_kind_to_cutout(geometry_hint)
        if ck:
            return ck, KindSource.GEOMETRY, KindResolveState.INFERRED, 0.7

    if vision_error:
        return None, KindSource.VISION, KindResolveState.VISION_ERROR, 0.0
    if vision_kind:
        ck = legacy_kind_to_cutout(vision_kind)
        if ck:
            return ck, KindSource.VISION, KindResolveState.INFERRED, 0.55
        return None, KindSource.VISION, KindResolveState.UNCERTAIN, 0.2

    return None, KindSource.UNSPECIFIED, KindResolveState.UNCERTAIN, 0.0
