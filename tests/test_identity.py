"""Phase A Schnitt 1 — Identitäts-Policy offline.

Deckt die Policy-Teile der A8-Liste ab, die ohne volle Pipeline laufen:
Smartphone ambig, Karte ohne Nummer, DE vs JP, Roh vs CGC, Pristine vs Gem Mint,
Disc vs CIB, Nutzerkorrektur, Legacy ungeprüft.
"""

from __future__ import annotations

from web.identity import (
    BlockingReason,
    Completeness,
    FieldSource,
    Identity,
    ProductKind,
    RecognitionState,
    apply_user_correction,
    build_pricing_query,
    evaluate_identity,
    field,
    normalize_legacy_analysis,
    pricing_cache_key,
    resolve_pricing_query,
)


def _raw_card(**overrides) -> Identity:
    base = dict(
        kind=ProductKind.raw_card,
        kind_source=FieldSource.visible_on_photo,
        game=field("Pokémon", FieldSource.visible_on_photo, "Logo"),
        name=field("Glurak ex", FieldSource.visible_on_photo, "Name auf Karte"),
        number=field("199", FieldSource.visible_on_photo, "unten links"),
        set_total=field("165", FieldSource.visible_on_photo, "unten links"),
        set_name=field("151", FieldSource.catalog_verified, "sv3pt5"),
        language=field("de", FieldSource.visible_on_photo, "DE-Text"),
    )
    base.update(overrides)
    return Identity(**base)


def _slab(**overrides) -> Identity:
    base = dict(
        kind=ProductKind.graded_slab,
        kind_source=FieldSource.visible_on_photo,
        game=field("Pokémon", FieldSource.visible_on_photo),
        name=field("Charizard ex", FieldSource.visible_on_photo),
        number=field("223", FieldSource.visible_on_photo),
        set_total=field("197", FieldSource.visible_on_photo),
        set_name=field("sv8a", FieldSource.catalog_verified),
        language=field("ja", FieldSource.visible_on_photo),
        grader=field("CGC", FieldSource.visible_on_photo, "Label"),
        grade=field("10", FieldSource.visible_on_photo, "Label"),
        label_type=field("pristine", FieldSource.visible_on_photo, "Goldkreis"),
        cert_number=field("12345678", FieldSource.visible_on_photo),
    )
    base.update(overrides)
    return Identity(**base)


def test_one_piece_card_game_ist_keine_videospiel_falle():
    """„Card Game" im Titel darf nicht den Videospiel-Pfad triggern."""
    from web.identity import _text_looks_like_game, identity_from_item, evaluate_identity
    assert _text_looks_like_game("One Piece Card Game Sammelkarte") is False
    assert _text_looks_like_game("Grand Theft Auto PS2 USA") is True
    item = {
        "name": "One Piece TCG Monkey.D.Luffy FILM Supernovas Alt Art Englisch",
        "card_info": {
            "single": True, "game": "onepiece", "name": "Monkey.D.Luffy",
            "language": "Englisch", "set_hint": "FILM",
        },
        "analysis": {"title": "One Piece TCG Monkey.D.Luffy FILM Supernovas Alt Art Englisch",
                     "category_query": "One Piece Card Game Sammelkarte"},
    }
    ident = identity_from_item(item)
    assert ident.kind.value == "raw_card"
    ev = evaluate_identity(ident)
    assert "MISSING_PLATFORM" not in [r.value for r in ev.blocking_reasons]
    ev = evaluate_identity(_raw_card())
    assert ev.recognition_state == RecognitionState.ready


def test_soft_rarity_question_only():
    from web.app_api import _soft_rarity_question_only
    assert _soft_rarity_question_only({
        "title": "One Piece TCG Luffy-Tarou ST18-005 Parallel Englisch NM",
        "question": "Ist die genaue Kartenseltenheit (z. B. SR) bekannt?",
    }) is True
    assert _soft_rarity_question_only({
        "title": "Irgendwas ohne Code",
        "question": "Ist die Seltenheit SR?",
    }) is False
    assert _soft_rarity_question_only({
        "title": "One Piece OP10-111 Luffy",
        "question": "Welche Kartennummer steht unten rechts?",
    }) is False


def test_setcode_in_pricing_query():
    """OP03+55 → OP03-055, P+74 → P-074 in der Preissuche."""
    from web.identity import (
        FieldSource, ProductKind, build_pricing_query, evaluate_identity, field, Identity,
    )
    ident = Identity(
        kind=ProductKind.graded_slab,
        kind_source=FieldSource.visible_on_photo,
        game=field("onepiece", FieldSource.visible_on_photo),
        name=field("Gum-Gum Giant Gavel", FieldSource.visible_on_photo),
        number=field("55", FieldSource.visible_on_photo),
        set_name=field("OP03", FieldSource.visible_on_photo),
        language=field("Englisch", FieldSource.visible_on_photo),
        edition=field("Parallel", FieldSource.visible_on_photo),
        grader=field("CGC", FieldSource.visible_on_photo),
        grade=field("10", FieldSource.visible_on_photo),
        label_type=field("gem_mint", FieldSource.visible_on_photo),
        cert_number=field("6134998058", FieldSource.visible_on_photo),
    )
    assert evaluate_identity(ident).pricing_ready is True
    q = build_pricing_query(ident) or ""
    assert "OP03-055" in q
    promo = Identity(
        kind=ProductKind.raw_card,
        kind_source=FieldSource.visible_on_photo,
        game=field("onepiece", FieldSource.visible_on_photo),
        name=field("Portgas D. Ace", FieldSource.visible_on_photo),
        number=field("74", FieldSource.visible_on_photo),
        set_name=field("P", FieldSource.visible_on_photo),
        language=field("Englisch", FieldSource.visible_on_photo),
        edition=field("Parallel", FieldSource.visible_on_photo),
    )
    qp = build_pricing_query(promo) or ""
    assert "P-074" in qp


def test_one_piece_parallel_in_pricing_query():
    """Parallel-Edition landet als Alternate Art in der Preissuche."""
    from web.identity import (
        FieldSource, ProductKind, build_pricing_query, evaluate_identity, field, Identity,
    )
    from web.prices import normalize_card_edition, wants_card_variant
    assert wants_card_variant("Parallel") is True
    info = normalize_card_edition(
        {"single": True, "game": "onepiece", "name": "Monkey D. Luffy",
         "number": "111", "set_hint": "OP10", "language": "Englisch",
         "edition": "Parallel"})
    assert info["edition"] == "Parallel"
    ident = Identity(
        kind=ProductKind.raw_card,
        kind_source=FieldSource.visible_on_photo,
        game=field("onepiece", FieldSource.visible_on_photo),
        name=field("Monkey D. Luffy", FieldSource.visible_on_photo),
        number=field("111", FieldSource.visible_on_photo),
        set_name=field("OP10", FieldSource.visible_on_photo),
        language=field("Englisch", FieldSource.visible_on_photo),
        edition=field("Parallel", FieldSource.visible_on_photo),
    )
    assert evaluate_identity(ident).pricing_ready is True
    q = build_pricing_query(ident) or ""
    assert "Parallel" in q
    assert "Alternate Art" in q


def test_tcg_display_box_kein_videospiel_ueber_game_substring():
    """„Trading Card Game Box" enthält „game" — darf nicht als Videospiel gelten."""
    from web.identity import (
        _category_suggests_video_game, normalize_legacy_analysis, evaluate_identity,
        identity_from_item,
    )
    assert _category_suggests_video_game("Azuki Trading Card Game Box") is False
    assert _category_suggests_video_game("One Piece Card Game Leader") is False
    assert _category_suggests_video_game("PS2 Spiel USA") is True
    legacy = normalize_legacy_analysis(
        {"title": "Azuki Trading Card Game Gates Awakened Box neu",
         "category_query": "Azuki Trading Card Game Box"},
        category="TCG Sonstiges",
    )
    assert legacy.kind != ProductKind.video_game
    item = {
        "name": "Azuki TCG Gates Awakened Alley Runner Display Box versiegelt",
        "category": "TCG Sonstiges",
        "analysis": {
            "title": "Azuki Trading Card Game Gates Awakened Alley Runner Box neu",
            "category_query": "Azuki Trading Card Game Box",
        },
        "card_info": {"single": True},
    }
    ident = identity_from_item(item)
    assert ident.kind != ProductKind.video_game
    ev = evaluate_identity(ident)
    assert "MISSING_PLATFORM" not in [r.value for r in ev.blocking_reasons]
    assert "MISSING_REGION" not in [r.value for r in ev.blocking_reasons]


def test_karte_ohne_nummer_nicht_pricing_ready():
    """A8.3 — Name ohne Nummer/Set: keine Preisfreigabe."""
    ev = evaluate_identity(_raw_card(
        number=field(None, FieldSource.unknown),
        set_total=field(None, FieldSource.unknown),
        set_name=field(None, FieldSource.unknown),
    ))
    assert ev.pricing_ready is False
    assert BlockingReason.MISSING_NUMBER in ev.blocking_reasons
    assert BlockingReason.MISSING_SET in ev.blocking_reasons
    assert ev.recognition_state == RecognitionState.needs_review


def test_de_und_jp_sind_verschiedene_identitaeten():
    """A8.4 — gleiche Karte DE vs JP → verschiedene Keys."""
    de = evaluate_identity(_raw_card(language=field("de", FieldSource.user_provided)))
    jp = evaluate_identity(_raw_card(language=field("ja", FieldSource.user_provided)))
    assert de.pricing_ready and jp.pricing_ready
    assert de.identity_key != jp.identity_key
    assert de.canonical["language"] == "de"
    assert jp.canonical["language"] == "ja"


def test_roh_und_cgc_niemals_gleicher_key():
    """A8.5 — Rohkarte und CGC 10 teilen keinen Preis-Bucket-Key."""
    raw = evaluate_identity(_raw_card(
        name=field("Charizard ex", FieldSource.visible_on_photo),
        number=field("223", FieldSource.visible_on_photo),
        language=field("ja", FieldSource.visible_on_photo),
    ))
    slab = evaluate_identity(_slab())
    assert raw.pricing_ready and slab.pricing_ready
    assert raw.identity_key != slab.identity_key
    assert raw.canonical.get("grading") == "raw"
    assert slab.canonical.get("grader") == "CGC"
    assert "grading=raw" not in slab.identity_key


def test_pristine_und_gem_mint_getrennt():
    """A8.6 — CGC Pristine 10 ≠ CGC Gem Mint 10."""
    pristine = evaluate_identity(_slab(
        label_type=field("pristine", FieldSource.visible_on_photo),
    ))
    gem = evaluate_identity(_slab(
        label_type=field("gem_mint", FieldSource.visible_on_photo),
    ))
    assert pristine.identity_key != gem.identity_key
    assert pristine.canonical["label_type"] == "pristine"
    assert gem.canonical["label_type"] == "gem_mint"


def test_cgc_ohne_label_type_blockiert():
    ev = evaluate_identity(_slab(label_type=field(None, FieldSource.unknown)))
    assert ev.pricing_ready is False
    assert BlockingReason.MISSING_LABEL_TYPE in ev.blocking_reasons


def test_disc_und_cib_getrennt():
    """A8.7 — Spiel Disc-only und CIB sind verschiedene Identitäten."""
    def game(comp: str) -> Identity:
        return Identity(
            kind=ProductKind.video_game,
            kind_source=FieldSource.user_provided,
            name=field("Resident Evil 4", FieldSource.visible_on_photo),
            platform=field("PS2", FieldSource.visible_on_photo),
            region=field("PAL", FieldSource.user_provided),
            completeness=field(comp, FieldSource.user_provided),
        )

    disc = evaluate_identity(game(Completeness.loose.value))
    cib = evaluate_identity(game(Completeness.cib.value))
    assert disc.pricing_ready and cib.pricing_ready
    assert disc.identity_key != cib.identity_key
    assert disc.canonical["completeness"] == "loose"
    assert cib.canonical["completeness"] == "cib"


def test_smartphone_ambig_needs_review():
    """A8.2 — ambiges Smartphone: keine Preisabfrage, needs_review."""
    ident = Identity(
        kind=ProductKind.generic,
        kind_source=FieldSource.visible_on_photo,
        brand=field("Apple", FieldSource.visible_on_photo, "Logo"),
        model=field("iPhone 17 Pro", FieldSource.inferred, "Kamera-Layout"),
        variant=field(None, FieldSource.unknown),
        candidates=["iPhone 17 Pro", "iPhone 17 Pro Max"],
    )
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is False
    assert ev.recognition_state == RecognitionState.needs_review
    assert BlockingReason.AMBIGUOUS_VARIANT in ev.blocking_reasons


def test_solana_seeker_ist_generic_pricing_ready():
    """Seed Vault + Solana-Logo auf dem Foto = Solana Seeker, Alltag, Preise frei."""
    ident = Identity(
        kind=ProductKind.generic,
        kind_source=FieldSource.visible_on_photo,
        brand=field("Solana Mobile", FieldSource.visible_on_photo, "Solana-Logo"),
        model=field("Seeker", FieldSource.visible_on_photo, "SEED VAULT"),
        name=field("Solana Seeker", FieldSource.visible_on_photo, "Rückseite"),
    )
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is True
    assert ev.recognition_state == RecognitionState.ready
    assert ev.canonical["brand"] == "Solana Mobile"
    assert ev.canonical["model"] == "Seeker"
    q = build_pricing_query(ident)
    assert q and "Seeker" in q
    assert "Smartphone 5G" not in (q or "")


def test_augustiner_flasche_ist_alltag_kein_sammler():
    """Normale 0,5-l-Flasche: generic + Marke/Sorte, keine Karten-Preisquery."""
    ident = Identity(
        kind=ProductKind.generic,
        kind_source=FieldSource.visible_on_photo,
        brand=field("Augustiner Bräu München", FieldSource.visible_on_photo, "Etikett"),
        model=field("Lagerbier Hell 0,5 l", FieldSource.visible_on_photo, "Etikett"),
        name=field("Augustiner Bräu München Lagerbier Hell 0,5 l",
                   FieldSource.visible_on_photo, "Etikett"),
    )
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is True
    q = build_pricing_query(ident)
    assert q and "Augustiner" in q
    assert "Sammler" not in (q or "")


def test_nutzerkorrektur_gibt_freigabe():
    """A8.8 — Nutzerkorrektur macht Identität freigabefähig."""
    ident = Identity(
        kind=ProductKind.generic,
        kind_source=FieldSource.visible_on_photo,
        brand=field("Apple", FieldSource.visible_on_photo),
        model=field("iPhone 17 Pro", FieldSource.inferred),
        variant=field(None, FieldSource.unknown),
        candidates=["iPhone 17 Pro", "iPhone 17 Pro Max"],
    )
    assert evaluate_identity(ident).pricing_ready is False

    fixed = apply_user_correction(ident, "model", "iPhone 17 Pro Max")
    fixed = apply_user_correction(fixed, "variant", "256 GB")
    ev = evaluate_identity(fixed)
    assert fixed.model.source == FieldSource.user_provided
    assert fixed.variant.source == FieldSource.user_provided
    assert fixed.candidates == []
    assert ev.pricing_ready is True
    assert ev.recognition_state == RecognitionState.ready


def test_inferred_pflichtfeld_blockiert_pricing():
    """inferred/unknown an preisrelevantem Feld → pricing_ready=false."""
    ev = evaluate_identity(_raw_card(
        number=field("199", FieldSource.inferred, "vermutet"),
    ))
    assert ev.pricing_ready is False
    assert BlockingReason.FIELD_UNTRUSTED in ev.blocking_reasons


def test_legacy_analysis_lesbar_aber_ungeprueft():
    """A8.15 — alte Analyseobjekte lesbar, ehrlich ungeprüft."""
    analysis = {
        "title": "Pokémon Glurak ex 199/165 151 Deutsch",
        "search_query_for_pricing": "irgendeine freie LLM-Query bitte ignorieren",
        "category_query": "Pokemon Karte",
        "aspects": {"Marke": ["Pokémon"]},
    }
    card_info = {
        "name": "Glurak ex",
        "number": "199",
        "set_total": "165",
        "set": "151",
        "language": "de",
        "game": "Pokémon",
    }
    ident = normalize_legacy_analysis(analysis, card_info=card_info)
    assert ident.legacy_unchecked is True
    assert ident.kind == ProductKind.raw_card
    assert ident.name.value == "Glurak ex"
    assert ident.number.source == FieldSource.inferred
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is False
    assert BlockingReason.LEGACY_UNCHECKED in ev.blocking_reasons
    # Freie LLM-Query steckt nicht in Canonical
    assert "irgendeine freie" not in str(ev.canonical)
    assert "search_query" not in ev.identity_key


def test_legacy_slab_inferred():
    ident = normalize_legacy_analysis(
        {"title": "Charizard CGC 10"},
        card_info={"name": "Charizard", "number": "223", "language": "ja", "game": "Pokémon"},
        graded={"grader": "CGC", "grade": "10", "label_type": "pristine"},
    )
    assert ident.kind == ProductKind.graded_slab
    assert ident.legacy_unchecked is True
    assert evaluate_identity(ident).pricing_ready is False


def test_blocking_reason_texte_geschlossen():
    from web.identity import BLOCKING_REASON_DE, BlockingReason, blocking_texts
    for reason in BlockingReason:
        assert reason in BLOCKING_REASON_DE
        assert BLOCKING_REASON_DE[reason]
    texts = blocking_texts([BlockingReason.MISSING_NUMBER, BlockingReason.AMBIGUOUS_VARIANT])
    assert len(texts) == 2
    assert "Kartennummer" in texts[0]


def test_manga_braucht_edition():
    ident = Identity(
        kind=ProductKind.manga_comic,
        kind_source=FieldSource.user_provided,
        series=field("One Piece", FieldSource.visible_on_photo),
        volume=field("1", FieldSource.visible_on_photo),
        language=field("de", FieldSource.user_provided),
        edition=field(None, FieldSource.unknown),
    )
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is False
    assert BlockingReason.MISSING_EDITION in ev.blocking_reasons


# ── A4 Query-Builder ──────────────────────────────────────────────────────────

def test_query_not_ready_gibt_none():
    assert build_pricing_query(_raw_card(
        number=field(None, FieldSource.unknown),
        set_total=field(None, FieldSource.unknown),
        set_name=field(None, FieldSource.unknown),
    )) is None
    assert pricing_cache_key(_raw_card(
        number=field(None, FieldSource.unknown),
    )) is None


def test_query_de_und_jp_verschieden():
    de = _raw_card(language=field("de", FieldSource.user_provided))
    jp = _raw_card(language=field("ja", FieldSource.user_provided))
    qd, qj = build_pricing_query(de), build_pricing_query(jp)
    assert qd and qj and qd != qj
    assert "Deutsch" in qd and "Japanisch" in qj
    assert pricing_cache_key(de) != pricing_cache_key(jp)


def test_query_roh_und_cgc_verschieden():
    raw = _raw_card(
        name=field("Charizard ex", FieldSource.visible_on_photo),
        number=field("223", FieldSource.visible_on_photo),
        language=field("ja", FieldSource.visible_on_photo),
    )
    slab = _slab()
    qr, qs = build_pricing_query(raw), build_pricing_query(slab)
    assert qr and qs and qr != qs
    assert "CGC" in qs and "Pristine" in qs
    assert "CGC" not in qr
    assert pricing_cache_key(raw) != pricing_cache_key(slab)


def test_query_pristine_und_gem_mint_verschieden():
    pristine = _slab(label_type=field("pristine", FieldSource.visible_on_photo))
    gem = _slab(label_type=field("gem_mint", FieldSource.visible_on_photo))
    qp, qg = build_pricing_query(pristine), build_pricing_query(gem)
    assert qp != qg
    assert "Pristine" in qp
    assert "Pristine" not in qg
    assert pricing_cache_key(pristine) != pricing_cache_key(gem)


def test_query_disc_und_cib_verschieden():
    def game(comp: str) -> Identity:
        return Identity(
            kind=ProductKind.video_game,
            kind_source=FieldSource.user_provided,
            name=field("Resident Evil 4", FieldSource.visible_on_photo),
            platform=field("PS2", FieldSource.visible_on_photo),
            region=field("PAL", FieldSource.user_provided),
            completeness=field(comp, FieldSource.user_provided),
        )
    qd = build_pricing_query(game(Completeness.loose.value))
    qc = build_pricing_query(game(Completeness.cib.value))
    assert qd != qc
    assert "Disc only" in qd
    assert "CIB" in qc


def test_query_ignoriert_llm_search_query():
    """Freie LLM-Query darf build_pricing_query nicht beeinflussen."""
    ident = _raw_card()
    q1 = build_pricing_query(ident)
    # Legacy-Objekt mit irrefuehrender Query — Normalisierung liefert ungeprueft
    legacy = normalize_legacy_analysis({
        "title": "irgendwas",
        "search_query_for_pricing": "VOLLKOMMEN FALSCHE LLM QUERY XYZ",
    }, card_info={
        "name": "Glurak ex", "number": "199", "set_total": "165",
        "set": "151", "language": "de", "game": "Pokémon",
    })
    assert build_pricing_query(legacy) is None  # legacy_unchecked
    assert q1 and "VOLLKOMMEN" not in q1


def test_llm_query_wird_von_resolve_ignoriert():
    """A8.9 — freie search_query steuert resolve_pricing_query nicht."""
    from web.identity import resolve_pricing_query
    item = {
        "name": "Falscher Name",
        "analysis": {"search_query_for_pricing": "VOLLKOMMEN FALSCHE QUERY",
                     "title": "x"},
        "card_info": {
            "name": "Glurak ex", "number": "199", "set_total": "165",
            "set": "151", "language": "de", "game": "Pokémon",
        },
    }
    q, ready, ident, ev = resolve_pricing_query(item)
    assert ready is True
    assert q and "VOLLKOMMEN" not in q
    assert "Glurak" in q


def test_unsichere_identity_keine_query():
    from web.identity import resolve_pricing_query
    q, ready, ident, ev = resolve_pricing_query({
        "analysis": {"search_query_for_pricing": "iPhone irgendwas",
                     "title": "Smartphone"},
    })
    assert ready is False
    assert q is None


def test_bgs_manga_ist_manga_comic_nicht_karten_slab():
    """Beckett-Manga braucht keine Kartennummer/Set — sonst hängt der Scanner."""
    from web.identity import identity_from_item, evaluate_identity, build_pricing_query, ProductKind
    item = {
        "name": "One Piece #1 Manga 1997 Jump Comics Japanisch Beckett 8.5",
        "category": "One Piece",
        "card_info": {"single": False, "game": "other", "edition": "Manga",
                      "language": "Japanisch"},
        "graded": {"grader": "BGS", "grade": "8.5"},
        "analysis": {
            "title": "One Piece #1 Manga 1997 Jump Comics Japanisch Beckett 8.5",
            "category_query": "One Piece Manga Band 1 Erstausgabe",
            "description_html": "<p>1. Druckauflage, Jump Comics, Japanisch</p>",
            "aspects": {
                "Produktart": ["Manga"],
                "Titel": ["One Piece #1"],
                "Sprache": ["Japanisch"],
            },
        },
    }
    ident = identity_from_item(item)
    assert ident.kind == ProductKind.manga_comic
    assert ident.series.value == "One Piece"
    assert ident.volume.value == "1"
    assert ident.edition.value == "1. Druckauflage"
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is True
    q = build_pricing_query(ident)
    assert q and "One Piece" in q and "BGS" in q
    assert "MISSING_NUMBER" not in [r.value for r in ev.blocking_reasons]


def test_wata_spiel_ist_video_game_nicht_karten_slab():
    """WATA-Spiele brauchen keine Kartennummer/Set — sonst Wert unbekannt."""
    from web.identity import identity_from_item, evaluate_identity, build_pricing_query, ProductKind
    item = {
        "name": "Grand Theft Auto: Vice City PS2 USA WATA 9.8 A++ Sealed",
        "category": "Games",
        "card_info": {"single": False, "game": "other", "name": None},
        "graded": {"grader": "WATA", "grade": "9.8", "cert_number": "609941-129"},
        "analysis": {"title": "Grand Theft Auto: Vice City PS2 USA WATA 9.8 A++ Sealed"},
    }
    ident = identity_from_item(item)
    assert ident.kind == ProductKind.video_game
    assert ident.platform.value == "PS2"
    assert ident.region.value == "USA"
    assert ident.completeness.value == "sealed"
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is True
    q = build_pricing_query(ident)
    assert q and "Vice City" in q and "WATA" in q
    assert "MISSING_NUMBER" not in [r.value for r in ev.blocking_reasons]


def test_wata_region_aus_beschreibung_nicht_nur_titel():
    """Vice-City-Fall: Region steht in der Beschreibung (NTSC/USA), nicht im Titel."""
    from web.identity import identity_from_item, evaluate_identity, RecognitionState
    item = {
        "name": "Grand Theft Auto Vice City PS2 WATA 9.8 A++ Sealed",
        "category": "Games",
        "status": "needs_review",
        "card_info": {"single": False, "game": "other", "name": None},
        "graded": {"grader": "WATA", "grade": "9.8", "cert_number": "609941-129"},
        "analysis": {
            "title": "Grand Theft Auto Vice City PS2 WATA 9.8 A++ Sealed",
            "description_html": (
                "<p>PlayStation 2 (NTSC U/C)</p><p>Region: USA, 2002</p>"
                "<p>Sealed, Siegel A++</p>"
            ),
            "aspects": {"Plattform": ["Sony PlayStation 2"]},
        },
    }
    ident = identity_from_item(item)
    assert ident.kind == ProductKind.video_game
    assert ident.region.value == "USA"
    ev = evaluate_identity(ident)
    assert ev.recognition_state == RecognitionState.ready
    assert ev.pricing_ready is True


def test_listing_review_edit_clears_game_needs_review():
    """Manueller Titel/Beschreibung-Sync setzt needs_review bei Games zurück."""
    from web.identity import apply_listing_review_to_item
    item = {
        "id": "x",
        "name": "Grand Theft Auto Vice City PS2 WATA 9.8 A++ Sealed",
        "category": "Games",
        "status": "needs_review",
        "card_info": {"single": False, "game": "other"},
        "graded": {"grader": "WATA", "grade": "9.8", "cert_number": "1"},
        "analysis": {
            "title": "Grand Theft Auto Vice City PS2 WATA 9.8 A++ Sealed",
        },
        "identity_eval": {"recognition_state": "needs_review", "pricing_ready": False},
    }
    draft = {
        "listing": {
            "title": "Grand Theft Auto Vice City PS2 WATA 9.8 A++ Sealed",
            "description_html": "<p>PlayStation 2 NTSC U/C USA sealed</p>",
            "aspects": {"Plattform": ["Sony PlayStation 2"]},
        },
    }
    ok, err = apply_listing_review_to_item(item, draft)
    assert err is None
    assert ok is True
    assert item["status"] == "ready"
    assert item["identity_eval"]["recognition_state"] == "ready"


def test_listing_confirm_gibt_game_frei_auch_ohne_region():
    """Games: Nutzer bestätigt Listing-Review → Publish-Blocker weg."""
    from web.identity import apply_listing_review_to_item
    item = {
        "name": "Unbekanntes Spiel",
        "category": "Games",
        "status": "needs_review",
        "card_info": {"single": False, "game": "other"},
        "graded": {"grader": "WATA", "grade": "9.8"},
        "analysis": {"title": "Unbekanntes Spiel"},
        "identity_eval": {"recognition_state": "needs_review"},
    }
    draft = {"listing": {"title": "Unbekanntes Spiel"}}
    ok, err = apply_listing_review_to_item(item, draft, user_confirmed=True)
    assert err is None
    assert ok is True
    assert item["status"] == "ready"
    assert item.get("identity_user_confirmed") is True


def test_listing_confirm_sperrt_unsichere_karte():
    """Karten ohne Zuordnung: Confirm allein darf Preflight nicht grün machen."""
    from web.identity import apply_listing_review_to_item
    item = {
        "name": "Glurak irgendwas",
        "category": "Pokémon",
        "status": "needs_review",
        "card_info": {"single": True, "game": "pokemon", "name": "Glurak"},
        "analysis": {"title": "Glurak irgendwas", "product_kind": "raw_card"},
        "identity_eval": {"recognition_state": "needs_review"},
    }
    ok, err = apply_listing_review_to_item(
        item, {"listing": {"title": "Glurak irgendwas"}}, user_confirmed=True)
    assert ok is False
    assert err and "Karte" in err
    assert item["status"] == "needs_review"


def test_game_confirm_bleibt_nach_preis_edit():
    """Nach Game-Confirm darf ein Feld-Edit listing_ready nicht wieder entziehen."""
    from web.identity import apply_listing_review_to_item
    item = {
        "name": "Unbekanntes Spiel",
        "category": "Games",
        "status": "ready",
        "identity_user_confirmed": True,
        "card_info": {"single": False, "game": "other"},
        "graded": {"grader": "WATA", "grade": "9.8"},
        "analysis": {"title": "Unbekanntes Spiel"},
        "identity_eval": {
            "recognition_state": "needs_review",
            "listing_ready": True,
            "blocking_reasons": ["MISSING_REGION"],
        },
    }
    ok, err = apply_listing_review_to_item(
        item, {"listing": {"title": "Unbekanntes Spiel", "price": "99"}},
        user_confirmed=False)
    assert err is None
    assert ok is True
    assert item.get("identity_user_confirmed") is True
    assert item["status"] == "ready"
    assert item["identity_eval"]["listing_ready"] is True


def test_wata_game_mit_region_in_beschreibung_wird_ready():
    """Vice-City-Fall: Region nur im Fließtext → Re-Eval räumt needs_review."""
    from web.identity import apply_listing_review_to_item
    item = {
        "name": "Grand Theft Auto Vice City PS2 WATA 9.8 A++ Sealed",
        "category": "Games",
        "status": "needs_review",
        "card_info": {"single": False, "game": "other"},
        "graded": {"grader": "WATA", "grade": "9.8", "cert_number": "609941-129"},
        "analysis": {
            "title": "Grand Theft Auto Vice City PS2 WATA 9.8 A++ Sealed",
            "description_html": (
                "<p>PlayStation 2</p><ul><li>Region: USA, 2002</li>"
                "<li>Plattform: PlayStation 2 (NTSC U/C)</li></ul>"
            ),
            "aspects": {"Plattform": ["Sony PlayStation 2"]},
        },
        "identity_eval": {
            "recognition_state": "needs_review",
            "pricing_ready": False,
            "blocking_reasons": ["MISSING_REGION"],
        },
    }
    ok, err = apply_listing_review_to_item(item, {"listing": item["analysis"]})
    assert err is None
    assert ok is True
    assert item["status"] == "ready"
    assert item["identity_eval"]["recognition_state"] == "ready"
    assert "MISSING_REGION" not in (item["identity_eval"].get("blocking_reasons") or [])


def test_cgc_karte_bleibt_graded_slab():
    from web.identity import identity_from_item, ProductKind
    item = {
        "name": "Charizard CGC 10",
        "category": "Sammelkarten",
        "card_info": {"name": "Charizard", "number": "223", "language": "ja", "game": "Pokémon"},
        "graded": {"grader": "CGC", "grade": "10", "label_type": "pristine"},
        "analysis": {"title": "Charizard CGC 10"},
    }
    assert identity_from_item(item).kind == ProductKind.graded_slab
