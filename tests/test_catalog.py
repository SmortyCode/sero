"""Der globale Preis-Katalog — das Modul, das den von allen Nutzern geteilten
Marktwert schreibt, und bis 03.08.2026 ohne einen einzigen Test.

Diese Datei hält das HEUTIGE Verhalten der Kaskade, der Wächter und der
TTL-Staffelung fest. Sie ist das Netz für den Umbau des Katalog-Schlüssels
(Stufe 1) und des PriceCharting-Gates (Stufe 2): wenn dort etwas reißt, das
hier nicht reißen darf, schlägt einer dieser Tests an.

Alles läuft gegen eine Wegwerf-Datenbank im Speicher. Kein Test berührt je
Svens data.db (Lehre vom 02.08.).
"""

import sqlite3

import pytest

from web import catalog


class FakeStore:
    """Minimal-Store: catalog.py braucht nur `_conn`."""

    def __init__(self):
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row


@pytest.fixture
def store():
    catalog._ready = False          # Tabellen je Test frisch anlegen
    s = FakeStore()
    catalog.ensure_tables(s)
    yield s
    catalog._ready = False
    s._conn.close()


# ────────────────────────── Schlüssel-Vertrag ──────────────────────────
# card_key_of wird in Stufe 1 umgebaut. Diese Zusagen müssen den Umbau
# überleben, sonst kollidieren fremde Karten auf einer Katalogzeile.

def test_schluessel_ist_immer_ein_string():
    """Der Rückgabewert landet als PRIMARY KEY in der Tabelle. Niemals None,
    niemals leer — sonst schlägt der INSERT fehl und der Preis geht verloren."""
    for card in ({}, {"name": None}, {"name": ""}, {"ref_id": None},
                 {"name": "Glurak"}, {"game": "pokemon", "ref_id": "sv03.5-199"}):
        k = catalog.card_key_of(card)
        assert isinstance(k, str) and k, f"Leerer Schlüssel für {card}"


def test_referenz_id_schlaegt_den_hash():
    """Hat die Karten-Datenbank eine ID, ist sie die Identität — sie ist
    stabiler als jeder Name, den die Analyse formuliert."""
    k = catalog.card_key_of({"game": "pokemon", "ref_id": "sv03.5-199",
                             "name": "Glurak ex"})
    assert k == "pokemon:sv03.5-199"
    # Ein anderer Name unter derselben ID ändert nichts
    k2 = catalog.card_key_of({"game": "pokemon", "ref_id": "sv03.5-199",
                              "name": "Charizard ex"})
    assert k == k2


def test_fehlmatch_nummer_wird_erkannt():
    """Charizard-Fall 07.08.: deutsches Fatale-Flammen-#013 darf nicht als
    Treffer für japanisch Mega-Dream-#223 gelten — sonst zwei Preise."""
    falsch = {"game": "pokemon", "name": "Mega-Glurak X-ex", "number": "013",
              "total": 130, "ref_id": "me02-013"}
    info = {"name": "Mega Charizard X ex", "number": "223", "set_total": "193"}
    assert catalog.card_passt_zu_info(falsch, info) is False
    assert catalog.card_passt_zu_info(
        {"number": "223", "total": 193}, info) is True
    assert catalog.card_passt_zu_info(None, info) is False
    assert catalog.card_passt_zu_info(falsch, None) is True


def test_fehlmatch_set_groesse_wird_erkannt():
    """Gyarados-Fall: TURBOfieber (126) passt nicht zu Scarlet ex (78)."""
    falsch = {"number": "14", "total": 126, "ref_id": "xy9-26"}
    info = {"number": "14", "set_total": "78"}
    assert catalog.card_passt_zu_info(falsch, info) is False


def test_fehlmatch_parallel_vs_basis():
    """OP10-111: Basis-Rare (~1 $) und Parallel/Alt Art (~19 $) teilen die Nummer."""
    basis = {"name": "Monkey.D.Luffy (111)", "number": "111", "ref_id": "617160"}
    parallel = {"name": "Monkey.D.Luffy (111) (Parallel)", "number": "111",
                "ref_id": "617161"}
    info_basis = {"number": "111", "name": "Monkey D. Luffy"}
    info_par = {"number": "111", "name": "Monkey D. Luffy", "edition": "Parallel"}
    assert catalog.card_passt_zu_info(basis, info_basis) is True
    assert catalog.card_passt_zu_info(parallel, info_basis) is False
    assert catalog.card_passt_zu_info(parallel, info_par) is True
    # Parallel gewünscht, nur Basis in der DB → Rückfall ok (Preis näher als nichts)
    assert catalog.card_passt_zu_info(basis, info_par) is True


def test_fehlmatch_parallel_nicht_sp():
    """Luffy-Tarou Parallel darf nicht den OP11-SP-Preis (~270 $) bekommen."""
    sp = {"name": "Luffy-Tarou (SP)", "number": None, "ref_id": "632509"}
    basis = {"name": "Luffy-Tarou", "number": None, "ref_id": "581035"}
    info = {"name": "Luffy-Tarou", "number": "5", "set_hint": "ST18",
            "edition": "Parallel"}
    assert catalog.card_passt_zu_info(sp, info) is False
    # Keine Parallel-SKU bei TCGplayer → Basis ist erlaubter Rückfall
    assert catalog.card_passt_zu_info(basis, info) is True


def test_secret_rare_official_set_total():
    """Iono 199/165: TCGdex total=207 (mit Secrets), Analyse liefert official 165.
    set_total muss gegen total ODER official passen (Claude-Review A2)."""
    card = {"number": "199", "total": 207, "official": 165, "ref_id": "sv03.5-199"}
    info = {"number": "199", "set_total": "165"}
    assert catalog.card_passt_zu_info(card, info) is True
    # Nur total ohne official — 207 ≠ 165 → False
    nur_total = {"number": "199", "total": 207}
    assert catalog.card_passt_zu_info(nur_total, info) is False
    # Passt über total (wenn Analyse total 207 liefert)
    info_total = {"number": "199", "set_total": "207"}
    assert catalog.card_passt_zu_info(nur_total, info_total) is True


def test_gleiche_karte_gleicher_schluessel():
    """Ohne Referenz-ID entscheidet der Inhalt — zweimal dasselbe Stück muss
    denselben Schlüssel ergeben, sonst teilt der Katalog nichts."""
    c = {"game": "onepiece", "name": "Portgas D. Ace", "number": "OP02-013",
         "set_name": "Paramount War"}
    assert catalog.card_key_of(dict(c)) == catalog.card_key_of(dict(c))


def test_verschiedene_karten_verschiedene_schluessel():
    """Der Gegen-Test: Nummer oder Set unterschiedlich heißt anderes Stück."""
    a = {"game": "pokemon", "name": "Glurak", "number": "4/102", "set_name": "Base"}
    b = {**a, "number": "5/102"}
    c = {**a, "set_name": "Base Set 2"}
    keys = {catalog.card_key_of(a), catalog.card_key_of(b), catalog.card_key_of(c)}
    assert len(keys) == 3


def test_schluessel_ist_deterministisch_auch_ohne_karten_db():
    """Der 239-von-247-Befund (03.08.): uuid4 machte jeden Aufruf zu einer
    frischen Wegwerf-Identität. Jetzt gilt: gleicher Inhalt, gleicher
    Schlüssel — über Aufrufe, Prozesse und Nutzer hinweg."""
    c = {"name": "One Piece #103 Manga Japanisch Beckett BGS 9.4"}
    assert catalog.card_key_of(dict(c)) == catalog.card_key_of(dict(c))
    assert catalog.card_key_of(dict(c)).startswith("h:")
    # Der Fallensteller von damals: name-Schlüssel VORHANDEN, aber null
    mit_null = {"single": False, "game": "other", "name": None, "number": None}
    k = catalog.card_key_of(mit_null, solo_id="stueck123")
    assert k == "solo:stueck123", "Ohne Namen muss der Solo-Schlüssel stabil sein"
    assert catalog.card_key_of(mit_null, solo_id="stueck123") == k


def test_gta_paar_teilt_denselben_schluessel():
    """Svens zwei GTA-Vice-City-Stücke — identische Ware, bis 03.08. zwei
    getrennte Katalogzeilen. Die Prüfvorgabe aus dem Umsetzungsplan."""
    ref = {"name": "Grand Theft Auto Vice City PS2 USA WATA 9.8"}
    assert catalog.card_key_of(dict(ref)) == catalog.card_key_of(dict(ref))


def test_sprache_und_auflage_trennen():
    """Japanische Erstauflage und deutsche Neuauflage sind NICHT dieselbe
    Ware — Sprache und Auflage gehören in die Identität."""
    a = {"name": "One Piece Band 1", "language": "ja", "edition": "1st"}
    b = {"name": "One Piece Band 1", "language": "de", "edition": "1st"}
    c = {"name": "One Piece Band 1", "language": "ja", "edition": "2nd"}
    assert len({catalog.card_key_of(a), catalog.card_key_of(b),
                catalog.card_key_of(c)}) == 3


def test_solo_schluessel_verschmutzt_das_register_nicht(store):
    """Wegwerf-Identitäten (kein Name, keine ref_id) bekommen keine Zeile im
    globalen cards-Register — 239 Müllzeilen waren genug."""
    k = catalog.upsert_card(store, {"name": None}, solo_id="abc")
    assert k == "solo:abc"
    n = store._conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
    assert n == 0


def test_upsert_legt_an_und_aktualisiert(store):
    """upsert darf einen bestehenden Eintrag nie leerräumen — COALESCE schützt
    Felder, die der neue Aufruf nicht kennt."""
    k = catalog.upsert_card(store, {"game": "pokemon", "ref_id": "x1",
                                    "name": "Glurak", "set_name": "Base",
                                    "image": "http://bild"})
    catalog.upsert_card(store, {"game": "pokemon", "ref_id": "x1", "name": "Glurak"})
    row = store._conn.execute("SELECT * FROM cards WHERE card_key = ?", (k,)).fetchone()
    assert row["set_name"] == "Base", "set_name wurde vom zweiten Aufruf gelöscht"
    assert row["image"] == "http://bild", "image wurde vom zweiten Aufruf gelöscht"
    anzahl = store._conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
    assert anzahl == 1, "Zweiter upsert legte eine zweite Zeile an"


# ────────────────────────── Grade-Eimer ──────────────────────────

@pytest.mark.parametrize("graded,erwartet", [
    (None, "raw"),
    ({}, "raw"),
    ({"grader": "PSA"}, "raw"),                 # ohne Note kein Slab-Eimer
    ({"grader": "PSA", "grade": "10"}, "PSA 10"),
    ({"grader": "psa", "grade": "10"}, "PSA 10"),
    ({"grader": None, "grade": "9"}, "9"),
])
def test_grade_bucket(graded, erwartet):
    assert catalog.grade_bucket(graded) == erwartet


# ────────────────────────── Kaskade ──────────────────────────
# Svens Entscheid vom 30.07.: echte Verkäufe schlagen alles. Die Reihenfolge
# ist das Versprechen auf dem Anmeldeschirm — „Marktwert aus echten
# eBay-Verkäufen". Diese Tests sind der Wächter darüber.

def _quellen(monkeypatch, sold=None, pc=None):
    """fetch_sold und lookup_pc ersetzen — keine Netzzugriffe im Test."""
    import web.pricecharting
    import web.sold

    async def fake_sold(*a, **k):
        return sold

    async def fake_pc(*a, **k):
        return pc

    monkeypatch.setattr(web.sold, "fetch_sold", fake_sold)
    monkeypatch.setattr(web.pricecharting, "lookup_pc", fake_pc)


VERKAUF = {"avg3": 100.0, "n_avg": 3}
# Achtung bei der Wahl der Kartennummer: „4/102" trägt KEIN prüfbares Token
# (die 4 ist einstellig, die 102 ist der Nenner) — siehe den xfail-Test unten.
# Für die Kaskaden-Tests deshalb eine Nummer mit dreistelligem Zähler.
PC_TREFFER = {"value": 50.0, "source": "pricecharting", "source_label": "PriceCharting",
              "detail": {"pc_product": "Glurak 199/165", "pc_console": "Pokemon 151"}}


@pytest.mark.asyncio
async def test_verkaeufe_schlagen_pricecharting(store, monkeypatch):
    _quellen(monkeypatch, sold=VERKAUF, pc=PC_TREFFER)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 4/102", None, 1.0)
    assert row["value_eur"] == 100.0 and row["source"] == "ebay_sold"
    assert "eBay-Verkäufe" in row["source_label"]


@pytest.mark.asyncio
async def test_stale_wird_im_label_genannt(store, monkeypatch):
    """Belege älter als 90 Tage zählen, aber der Nutzer muss es sehen."""
    _quellen(monkeypatch, sold={**VERKAUF, "stale": True})
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0)
    assert "älter als 90 Tage" in row["source_label"]


@pytest.mark.asyncio
async def test_basis_nur_fuer_ungegradete(store, monkeypatch):
    """Die Karten-Datenbank (Cardmarket & Co.) kennt nur rohe Karten. Für
    einen Slab darf ihr Preis nicht durchschlagen."""
    _quellen(monkeypatch)   # keine Quelle liefert etwas
    basis = {"value": 12.0, "source": "cardmarket", "label": "Cardmarket", "detail": {}}
    roh = await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0, base=basis)
    assert roh["value_eur"] == 12.0 and roh["source"] == "cardmarket"
    slab = await catalog.refresh_price(store, "k2", "PSA 10", "Glurak PSA 10",
                                       {"grader": "PSA", "grade": "10"}, 1.0, base=basis)
    assert slab is None, "Cardmarket-Rohpreis wurde einem PSA-10-Slab gegeben"


@pytest.mark.asyncio
async def test_unbelegter_pc_treffer_wird_markiert(store, monkeypatch):
    """Ein Fuzzy-Treffer ohne übereinstimmende Hard-Tokens ist kein Beweis —
    er darf zwar als letzter Rückfall dienen, aber nur ehrlich benannt."""
    fremd = {**PC_TREFFER, "detail": {"pc_product": "Nami OP01-016",
                                      "pc_console": "One Piece Romance Dawn"}}
    _quellen(monkeypatch, pc=fremd)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 4/102", None, 1.0)
    assert row["source"] == "pricecharting_weak"
    assert "unsicher" in row["source_label"]


@pytest.mark.asyncio
async def test_belegter_pc_treffer_zaehlt_normal(store, monkeypatch):
    """Der Gegen-Test: stimmen die Zahlen-Tokens überein, ist der Treffer gut."""
    _quellen(monkeypatch, pc=PC_TREFFER)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 199/165", None, 1.0)
    assert row["source"] == "pricecharting" and row["value_eur"] == 50.0


@pytest.mark.asyncio
async def test_einstellige_kartennummer_verliert_die_belegbarkeit(store, monkeypatch):
    """Einstellige Kartennummer (4/102) ist Hard-Token — PC-Treffer gilt als belegt."""
    treffer = {**PC_TREFFER,
               "detail": {"pc_product": "Charizard 4/102", "pc_console": "Pokemon Base Set"}}
    _quellen(monkeypatch, pc=treffer)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 4/102", None, 1.0)
    assert row["source"] == "pricecharting", "einstellige Nummer verliert die Belegbarkeit"


# ────────────────────────── Wächter ──────────────────────────

@pytest.mark.asyncio
async def test_einzelner_ausreisser_wird_korrigiert(store, monkeypatch):
    """EIN Verkaufsbeleg, der das Sechsfache der belegten Referenz zeigt, ist
    fast immer ein Fehl-Match der Suche."""
    _quellen(monkeypatch, sold={"avg3": 900.0, "n_avg": 1}, pc=PC_TREFFER)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 199/165", None, 1.0)
    assert row["value_eur"] == 50.0, "Ausreißer wurde nicht korrigiert"
    assert "unplausibel" in row["source_label"]


@pytest.mark.asyncio
async def test_mehrere_belege_stehen_ueber_der_referenz(store, monkeypatch):
    """Ab zwei Belegen gilt der Markt, auch wenn PriceCharting weit darunter
    liegt — genau Svens Glurak-Fall (51,61 € Katalog gegen 138,99 € Markt)."""
    _quellen(monkeypatch, sold={"avg3": 900.0, "n_avg": 3}, pc=PC_TREFFER)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 199/165", None, 1.0)
    assert row["value_eur"] == 900.0 and row["source"] == "ebay_sold"


@pytest.mark.asyncio
async def test_unsicherer_pc_wert_faellt_auf_die_basis(store, monkeypatch):
    """Svens Manga Band 103: PriceCharting fand die Sammelkarte statt des Buchs
    und lieferte 603 €. Eine BELEGTE Basis (hier: alte Verkaufsbelege des
    Stücks) steht in der Kaskade über dem unsicheren Treffer. (Bis 07.08.
    durfte hier auch eine KI-Schätzung stehen — seit ADR-002 nicht mehr.)"""
    fremd = {"value": 603.0, "source": "pricecharting", "source_label": "PriceCharting",
             "detail": {"pc_product": "Nami [Manga] OP01-016",
                        "pc_console": "One Piece Romance Dawn"}}
    _quellen(monkeypatch, pc=fremd)
    basis = {"value": 80.0, "source": "ebay_sold", "label": "Ø letzte 3 eBay-Verkäufe",
             "detail": {}}
    row = await catalog.refresh_price(store, "k1", "BGS 9.4", "One Piece Band 103",
                                      {"grader": "BGS", "grade": "9.4"}, 1.0, base=basis)
    assert row["value_eur"] == 80.0, "603-€-Fehler kam durch"
    assert row["source"] == "ebay_sold"


@pytest.mark.asyncio
async def test_anker_aus_der_raw_zeile_faengt_weak_ohne_basis(store, monkeypatch):
    """Stufe 4: Auch OHNE Basis hat ein Slab jetzt einen Anker — die
    raw-Zeile derselben Karte. Ein unsicherer Treffer, der das Vierfache
    daneben liegt, wird verworfen."""
    _quellen(monkeypatch, sold=VERKAUF)
    await catalog.refresh_price(store, "k1", "raw", "One Piece Band 103", None, 1.0)
    fremd = {"value": 900.0, "source": "pricecharting", "source_label": "PriceCharting",
             "detail": {"pc_product": "Nami [Manga] OP01-016",
                        "pc_console": "One Piece Romance Dawn"}}
    _quellen(monkeypatch, pc=fremd)
    row = await catalog.refresh_price(store, "k1", "BGS 9.4", "One Piece Band 103 BGS 9.4",
                                      {"grader": "BGS", "grade": "9.4"}, 1.0)
    assert row["value_eur"] == 100.0, "Anker aus der raw-Zeile griff nicht"
    assert row["detail"]["verworfen_pc"]["wert"] == 900.0


@pytest.mark.asyncio
async def test_estimate_basis_ist_ueberall_tabu(store, monkeypatch):
    """ADR-002 (07.08.): Werte aus der abgeschafften KI-Schätzung dürfen NIE
    wieder in die geteilte Katalogzeile — auch nicht als letzter Rückfall.
    Ohne echte Quelle gibt es ehrlich KEINEN Katalogpreis."""
    _quellen(monkeypatch)
    basis = {"value": 150.0, "source": "estimate", "label": "KI-Schätzung", "detail": {}}
    row = await catalog.refresh_price(store, "k9", "PSA 10", "Glurak PSA 10",
                                      {"grader": "PSA", "grade": "10"}, 1.0, base=basis)
    assert row is None, "KI-Schätzung landete wieder im Katalog"


@pytest.mark.asyncio
async def test_alte_estimate_zeile_wird_nicht_mehr_serviert(store, monkeypatch):
    """Alt-Zeilen mit source=estimate (vor dem 07.08. entstanden) dürfen weder
    als Cache-Treffer zurückkommen noch als Fallback überleben."""
    catalog.ensure_tables(store)
    import time as _t
    store._conn.execute(
        "INSERT INTO card_prices (card_key, grade, value_eur, source, source_label, "
        "detail, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k7", "PSA 10", 65.0, "estimate", "KI-Schätzung", "{}", _t.time()))
    store._conn.commit()
    _quellen(monkeypatch)
    row = await catalog.refresh_price(store, "k7", "PSA 10", "Irgendwas PSA 10",
                                      {"grader": "PSA", "grade": "10"}, 1.0)
    assert row is None or row.get("source") != "estimate"


@pytest.mark.asyncio
async def test_streuungs_waechter_faengt_fehl_match_gemisch(store, monkeypatch):
    """Stufe 4, T3: Der alte Auslöser (n_avg < 2) war praktisch tot. Drei
    „Belege", die um mehr als das Sechsfache auseinanderliegen, sind ein
    Fehl-Match-Gemisch — die belegte Referenz korrigiert."""
    gemisch = {"avg3": 900.0, "n_avg": 3,
               "sales": [{"price_eur": 60.0}, {"price_eur": 900.0},
                         {"price_eur": 1740.0}]}
    _quellen(monkeypatch, sold=gemisch, pc=PC_TREFFER)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 199/165", None, 1.0)
    assert row["value_eur"] == 50.0, "Streuungs-Wächter griff nicht"
    assert row["detail"]["streuung"] > 6


@pytest.mark.asyncio
async def test_konsistente_belege_bleiben_unangetastet(store, monkeypatch):
    """Der Gegen-Test: drei enge Belege sind ein Markt — auch wenn
    PriceCharting weit darunter liegt (Svens Glurak-Fall)."""
    eng = {"avg3": 900.0, "n_avg": 3,
           "sales": [{"price_eur": 850.0}, {"price_eur": 900.0},
                     {"price_eur": 950.0}]}
    _quellen(monkeypatch, sold=eng, pc=PC_TREFFER)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak 199/165", None, 1.0)
    assert row["value_eur"] == 900.0 and row["source"] == "ebay_sold"


@pytest.mark.asyncio
async def test_price_state_je_quelle(store, monkeypatch):
    """Stufe 5: Der ehrliche Anzeigezustand wandert in die Katalogzeile.
    belegt = echte Verkäufe · spanne = Angebote oder alte Belege ·
    unbekannt = unsichere Zuordnung."""
    _quellen(monkeypatch, sold=VERKAUF)
    row = await catalog.refresh_price(store, "z1", "raw", "Glurak 199/165", None, 1.0)
    assert row["detail"]["price_state"] == "belegt"

    _quellen(monkeypatch, sold={**VERKAUF, "stale": True})
    row = await catalog.refresh_price(store, "z2", "raw", "Glurak 199/165", None, 1.0)
    assert row["detail"]["price_state"] == "spanne"
    assert row["detail"]["price_reason"] == "BELEGE_ALT"

    fremd = {"value": 50.0, "source": "pricecharting", "source_label": "PriceCharting",
             "detail": {"pc_product": "Anderes Produkt", "pc_console": "Sonstwas"}}
    _quellen(monkeypatch, pc=fremd)
    row = await catalog.refresh_price(store, "z3", "raw", "Glurak 199/165", None, 1.0)
    assert row["detail"]["price_state"] == "unbekannt"
    assert row["detail"]["price_reason"] == "UNBEKANNT_ZUORDNUNG"


def test_override_entgiftet_die_zeile(store):
    """Stufe 4: Wächter-Korrekturen erreichen die GETEILTE Zeile — vorher
    servierte sie den Fehlwert jedem weiteren Nutzer bis zum TTL-Ablauf."""
    import json as _json
    store._conn.execute(
        "INSERT INTO card_prices (card_key, grade, value_eur, source, source_label, detail, updated_at) "
        "VALUES ('kx', 'BGS 9.4', 603.0, 'pricecharting_weak', 'PriceCharting', '{}', 0)")
    store._conn.commit()
    catalog.override_price(store, "kx", "BGS 9.4", 119.38, "ebay",
                           "eBay-Median (aktive Angebote)",
                           {"verworfen_pc": {"wert": 603.0}})
    row = catalog.get_price(store, "kx", "BGS 9.4")
    assert row["value_eur"] == 119.38 and row["source"] == "ebay"
    assert row["detail"]["poisoned_cleared"] is True
    assert row["detail"]["verworfen_pc"]["wert"] == 603.0


@pytest.mark.asyncio
async def test_eu_markt_braucht_genug_angebote(store, monkeypatch):
    """Riegel vom 03.08.: unter 5 Angeboten (roh) bzw. 4 (Slab) ist der
    Angebots-Median Zufall, kein Markt — gemessen an Svens GTA (1 Angebot zu
    380 € gegen 98 € real) und Mega Charizard (2 Angebote, Spanne 180–2.339 €)."""
    _quellen(monkeypatch)   # keine Verkäufe, kein PriceCharting

    async def probe_duenn(q):
        return {"median": 380.0, "count": 2, "estimated": False}

    async def probe_dick(q):
        return {"median": 100.0, "count": 7, "estimated": False}

    row = await catalog.refresh_price(store, "k1", "raw", "GTA Vice City",
                                      None, 1.0, eu_probe=probe_duenn)
    assert row is None, "2 Angebote wurden als Marktwert übernommen"
    row = await catalog.refresh_price(store, "k2", "raw", "Glurak 199/165",
                                      None, 1.0, eu_probe=probe_dick)
    assert row["source"] == "ebay_eu" and row["value_eur"] == 88.0


# ────────────────────────── TTL-Staffelung ──────────────────────────

@pytest.mark.asyncio
async def test_belegter_wert_haelt_laenger_als_ein_notbehelf(store, monkeypatch):
    """Selbstheilung: ein Wert ohne Verkaufsbelege gilt nur eine Stunde, damit
    die Suche bald erneut nach echten Belegen greift. Ein belegter Wert hält
    24 Stunden."""
    import time
    _quellen(monkeypatch, sold=VERKAUF)
    await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0)
    # Zwei Stunden zurückdatieren — der belegte Wert muss stehen bleiben
    store._conn.execute("UPDATE card_prices SET updated_at = ? WHERE card_key = 'k1'",
                        (time.time() - 2 * 3600,))
    store._conn.commit()
    _quellen(monkeypatch, sold={"avg3": 555.0, "n_avg": 3})
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0)
    assert row["value_eur"] == 100.0, "Belegter Wert wurde vorzeitig neu geholt"

    # Derselbe Ablauf mit einem Notbehelf-Wert: der MUSS erneuert werden
    _quellen(monkeypatch, pc=PC_TREFFER)
    await catalog.refresh_price(store, "k2", "raw", "Glurak 4/102", None, 1.0, force=True)
    store._conn.execute("UPDATE card_prices SET updated_at = ?, source = 'estimate' "
                        "WHERE card_key = 'k2'", (time.time() - 2 * 3600,))
    store._conn.commit()
    _quellen(monkeypatch, sold={"avg3": 77.0, "n_avg": 2})
    row2 = await catalog.refresh_price(store, "k2", "raw", "Glurak 4/102", None, 1.0)
    assert row2["value_eur"] == 77.0, "Notbehelf wurde nicht erneuert"


@pytest.mark.asyncio
async def test_force_umgeht_die_wartezeit(store, monkeypatch):
    """Svens Refresh-Knopf muss immer durchgreifen."""
    _quellen(monkeypatch, sold=VERKAUF)
    await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0)
    _quellen(monkeypatch, sold={"avg3": 222.0, "n_avg": 3})
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0, force=True)
    assert row["value_eur"] == 222.0


@pytest.mark.asyncio
async def test_alte_zeile_schlaegt_gar_keine_zeile(store, monkeypatch):
    """Fällt jede Quelle aus, bleibt der letzte bekannte Wert stehen — die App
    darf nie von einem Preis auf „kein Preis" zurückfallen."""
    _quellen(monkeypatch, sold=VERKAUF)
    await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0)
    _quellen(monkeypatch)   # alle Quellen tot
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0, force=True)
    assert row is not None and row["value_eur"] == 100.0


@pytest.mark.asyncio
async def test_quellen_ausfall_wirft_nicht(store, monkeypatch):
    """Wirft eine Quelle, muss die andere trotzdem zählen — gather läuft mit
    return_exceptions, und das darf niemand versehentlich zurückbauen."""
    import web.pricecharting
    import web.sold

    async def kaputt(*a, **k):
        raise RuntimeError("Netz weg")

    async def guter_verkauf(*a, **k):
        return VERKAUF

    monkeypatch.setattr(web.sold, "fetch_sold", guter_verkauf)
    monkeypatch.setattr(web.pricecharting, "lookup_pc", kaputt)
    row = await catalog.refresh_price(store, "k1", "raw", "Glurak", None, 1.0)
    assert row["value_eur"] == 100.0


@pytest.mark.asyncio
async def test_grader_wandert_in_die_suchanfrage(store, monkeypatch):
    """PSA 9 ist nicht CGC 9. Ohne Grader in der Anfrage mischt die
    Verkaufssuche fremde Slabs — der Kern des 603-€-Themas."""
    gesehen = {}
    import web.pricecharting
    import web.sold

    async def merke(store_, query, *a, **k):
        gesehen["q"] = query
        return None

    async def kein_pc(*a, **k):
        return None

    monkeypatch.setattr(web.sold, "fetch_sold", merke)
    monkeypatch.setattr(web.pricecharting, "lookup_pc", kein_pc)
    await catalog.refresh_price(store, "k1", "PSA 10", "Glurak 4/102",
                                {"grader": "PSA", "grade": "10"}, 1.0)
    assert "PSA" in gesehen["q"] and "10" in gesehen["q"]
