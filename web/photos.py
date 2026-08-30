"""Foto-Modell: sortierte Liste, Index 0 = Hauptfoto.

Alte Entwuerfe speichern photos als Pfadliste (manchmal nur ein Bild).
Neue Aufnahmen nutzen Records {id, source, original, edited, thumb, pos, isPrimary}.
Es gibt keine parallelen Felder image + images.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from bot.ebay.payload import MAX_LISTING_PHOTOS

PHOTO_KEYS = ("id", "source", "original", "edited", "thumb", "pos", "isPrimary")


def _as_path(entry: Any) -> str | None:
    if isinstance(entry, str) and entry.strip():
        return entry
    if isinstance(entry, dict):
        for k in ("edited", "original", "path", "url"):
            v = entry.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return None


def normalize_photo_records(raw: Any, *, extras: Any = None) -> list[dict]:
    """Eine sortierte Record-Liste. Alte 1-Bild-Entwuerfe werden angehoben."""
    seq: list = []
    if isinstance(raw, dict) and not any(k in raw for k in ("url", "path", "original")):
        # kaputtes Parallel-Modell image + images
        if raw.get("image"):
            seq.append(raw.get("image"))
        if isinstance(raw.get("images"), list):
            seq.extend(raw.get("images") or [])
    elif isinstance(raw, list):
        seq = list(raw)
    elif raw:
        seq = [raw]
    if extras:
        extra_list = extras if isinstance(extras, list) else [extras]
        for e in extra_list:
            if e not in seq:
                seq.append(e)
    records = []
    seen = set()
    for i, entry in enumerate(seq):
        path = _as_path(entry)
        if not path or path in seen:
            continue
        seen.add(path)
        if isinstance(entry, dict) and entry.get("id"):
            rec = {
                "id": str(entry.get("id")),
                "source": entry.get("source") or "unknown",
                "original": entry.get("original") or path,
                "edited": entry.get("edited") or path,
                "thumb": entry.get("thumb"),
                "pos": len(records),
                "isPrimary": len(records) == 0,
                "upload": entry.get("upload") or {},
            }
        else:
            rec = {
                "id": uuid.uuid4().hex[:10],
                "source": "legacy",
                "original": path,
                "edited": path,
                "thumb": None,
                "pos": len(records),
                "isPrimary": len(records) == 0,
                "upload": {},
            }
        records.append(rec)
        if len(records) >= MAX_LISTING_PHOTOS:
            break
    if records:
        records[0]["isPrimary"] = True
        for i, rec in enumerate(records):
            rec["pos"] = i
            if i:
                rec["isPrimary"] = False
    return records


def paths_from_records(records: list[dict]) -> list[str]:
    """Pfadliste in Anzeige-Reihenfolge — Hauptfoto zuerst."""
    out = []
    for rec in records or []:
        p = rec.get("edited") or rec.get("original")
        if p:
            out.append(p)
    return out


def identify_paths(records: list[dict] | list[str] | None) -> list[str]:
    """Nur das Hauptbild fuer Identify / Analyse — keine doppelten API-Kosten."""
    recs = normalize_photo_records(records)
    if not recs:
        return []
    p = recs[0].get("edited") or recs[0].get("original")
    return [p] if p else []


def listing_image_paths(records: list[dict] | list[str] | None) -> list[str]:
    """Alle Fotos in Reihenfolge fuer das Listing."""
    return paths_from_records(normalize_photo_records(records))


def existing_local_paths(paths: list[str] | None) -> list[str]:
    out = []
    for p in paths or []:
        try:
            if p and Path(p).exists():
                out.append(p)
        except OSError:
            continue
    return out
