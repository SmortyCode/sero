"""Echte End-zu-End-Tests gegen die FastAPI-App — mit Wegwerf-Datenbank.

Läuft in einem SUBPROZESS mit SERO_DB auf einer Temp-Datei: web.server legt
seinen Store beim Import an, und andere Tests im selben Prozess hätten ihn
längst auf die echte data.db gebunden. Der Subprozess garantiert: kein Test
berührt je Svens Live-Daten (Lehre vom 02.08.).
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

TESTCODE = r"""
import json
from fastapi.testclient import TestClient
from web.server import app, store

client = TestClient(app)

# 1) Auth-Gates: alles Sensible verlangt Anmeldung
for pfad in ("/api/app/collection", "/api/app/dashboard", "/api/me"):
    r = client.get(pfad)
    assert r.status_code == 401, f"{pfad}: {r.status_code}"

# 2) Konto anlegen + Session-Cookie über den echten Signier-Weg
account = store.create_account("test@example.org")
from web.server import signer
client.cookies.set("listo_session", signer.dumps(account["id"]))
r = client.get("/api/me")
assert r.status_code == 200 and r.json()["email"] == "test@example.org"

# 3) Sammlung: leer, aber wohlgeformt (rev/total/stats vorhanden)
r = client.get("/api/app/collection")
d = r.json()
assert r.status_code == 200 and d["items"] == [] and "rev" in d and d["total"] == 0

# 4) PATCH-Längendeckel: 10-MB-Notiz prallt ab (422 von Pydantic)
import uuid, time
item_id = uuid.uuid4().hex[:12]
store._conn.execute(
    "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) "
    "VALUES (?, ?, ?, ?, ?)",
    (item_id, account["id"], time.time(), time.time(),
     json.dumps({"status": "ready", "name": "Testkarte", "photos": []})))
store._conn.commit()
r = client.post(f"/api/app/collection/item/{item_id}", json={"notes": "x" * 100000})
assert r.status_code == 422, f"Riesen-Notiz kam durch: {r.status_code}"
r = client.post(f"/api/app/collection/item/{item_id}", json={"notes": "kurz", "quantity": 3})
assert r.status_code == 200 and r.json()["quantity"] == 3

# 5) Kaufpreis: deutsche Schreibweise korrekt, Müll prallt ab
r = client.post(f"/api/app/collection/item/{item_id}", json={"purchase_price": "1.500"})
assert r.status_code == 200 and r.json()["purchase_price"] == "1500.00"
r = client.post(f"/api/app/collection/item/{item_id}", json={"purchase_price": "nan"})
assert r.status_code == 400

# 6) Fremdes Konto sieht das Item nicht (Mandanten-Trennung)
fremd = store.create_account("angreifer@example.org")
client.cookies.set("listo_session", signer.dumps(fremd["id"]))
r = client.get(f"/api/app/collection/item/{item_id}")
assert r.status_code == 404, "Fremdes Konto konnte das Item lesen!"

print("INTEGRATION-OK")
"""


def test_api_endpunkte_mit_wegwerf_db():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "test.db")}
        r = subprocess.run([sys.executable, "-c", TESTCODE], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "INTEGRATION-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-3000:]}"


UPLOAD_TEST = r"""
import io, json
from fastapi.testclient import TestClient
from PIL import Image
from web.server import app, store, signer

client = TestClient(app)
account = store.create_account("upload@example.org")
client.cookies.set("listo_session", signer.dumps(account["id"]))

# Ein echtes JPEG bauen (kein Fake-Byte-String — der Endpunkt dekodiert wirklich)
buf = io.BytesIO()
Image.new("RGB", (600, 840), (30, 46, 90)).save(buf, "JPEG")
buf.seek(0)

r = client.post("/api/app/collection/items",
                files={"files": ("karte.jpg", buf, "image/jpeg")},
                data={"notes": "Testkarte"})
assert r.status_code == 200, f"Upload gab {r.status_code}: {r.text[:400]}"
item_id = r.json()["item_id"]

# Das Stück muss angelegt UND eingereiht sein. Genau hier lag der Fehler vom
# 03.08.: enqueue_scan warf NameError, das Stück blieb ohne status_text liegen
# und die App zeigte für immer „wird analysiert".
row = store._conn.execute("SELECT data FROM collection_items WHERE id = ?", (item_id,)).fetchone()
d = json.loads(row["data"])
assert d["status"] == "analyzing", d
assert d.get("status_text"), (
    "Kein status_text — enqueue_scan hat das Stück nicht angefasst. "
    "Genau dieser Zustand hieß in der App: analysiert ewig.")

print("UPLOAD-OK")
"""


def test_upload_reiht_wirklich_ein():
    """Der Upload-Pfad Ende zu Ende — inklusive Einreihen in die Warteschlange."""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "up.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", UPLOAD_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=180)
        assert "UPLOAD-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-3000:]}"


LOESCH_TEST = r"""
import json
from fastapi.testclient import TestClient
from web.server import app, store, signer

client = TestClient(app)
acc = store.create_account("loesch@example.org")
client.cookies.set("listo_session", signer.dumps(acc["id"]))
uid = 10**15 + acc["id"]

import uuid, time
def stueck_mit_entwurf(draft_status):
    did = store.create_draft(uid, {"status": draft_status, "listing": {"title": "Test"}})
    iid = uuid.uuid4().hex[:12]
    store._conn.execute(
        "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
        (iid, acc["id"], time.time(), time.time(),
         json.dumps({"status": "ready", "name": "Testkarte", "photos": [], "draft_id": did})))
    store._conn.commit()
    return iid, did

# 1) Offener Entwurf muss mit dem Stück verschwinden — sonst Karteileiche
iid, did = stueck_mit_entwurf("ready")
assert client.post(f"/api/app/collection/item/{iid}/delete").status_code == 200
assert store.get_draft(did) is None, "Offener Entwurf blieb als Karteileiche liegen"

# 2) Veröffentlichter Entwurf muss ÜBERLEBEN — daran hängt echtes Geld
iid2, did2 = stueck_mit_entwurf("published")
assert client.post(f"/api/app/collection/item/{iid2}/delete").status_code == 200
assert store.get_draft(did2) is not None, "Veröffentlichter Entwurf wurde geloescht!"

# 3) Beendeter Entwurf ebenfalls (Verkaufshistorie)
iid3, did3 = stueck_mit_entwurf("ended")
assert client.post(f"/api/app/collection/item/{iid3}/delete").status_code == 200
assert store.get_draft(did3) is not None, "Beendeter Entwurf wurde geloescht!"

print("LOESCH-OK")
"""


def test_loeschen_raeumt_entwurf_auf_aber_schont_live():
    """Ein gelöschtes Stück darf keinen verwaisten Entwurf hinterlassen — aber
    was live war, bleibt. (Svens vier GTA-III-Karteileichen vom 03.08.)"""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "del.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", LOESCH_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "LOESCH-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"


ABSTURZ_TEST = r"""
import json, time, uuid
from fastapi.testclient import TestClient
from web.server import app, store, signer

client = TestClient(app)
acc = store.create_account("race@example.org")
client.cookies.set("listo_session", signer.dumps(acc["id"]))
uid = 10**15 + acc["id"]

# Entwurf mitten im Lauf: darf beim Löschen des Stücks NICHT verschwinden,
# sonst stürzt die laufende Aufbereitung beim Zurückschreiben ab.
for lauf_status, soll_bleiben in (("downloading", True), ("analyzing", True),
                                  ("ready", False), ("error", False)):
    did = store.create_draft(uid, {"status": lauf_status, "listing": {"title": "T"}})
    iid = uuid.uuid4().hex[:12]
    store._conn.execute(
        "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
        (iid, acc["id"], time.time(), time.time(),
         json.dumps({"status": "ready", "name": "T", "photos": [], "draft_id": did})))
    store._conn.commit()
    assert client.post(f"/api/app/collection/item/{iid}/delete").status_code == 200
    da = store.get_draft(did) is not None
    assert da == soll_bleiben, f"{lauf_status}: bleibt={da}, erwartet={soll_bleiben}"

# Fremder Entwurf darf NIE über eine manipulierte draft_id gelöscht werden
fremd = store.create_account("fremd@example.org")
fremd_did = store.create_draft(10**15 + fremd["id"], {"status": "ready", "listing": {"title": "F"}})
iid = uuid.uuid4().hex[:12]
store._conn.execute(
    "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
    (iid, acc["id"], time.time(), time.time(),
     json.dumps({"status": "ready", "name": "X", "photos": [], "draft_id": fremd_did})))
store._conn.commit()
assert client.post(f"/api/app/collection/item/{iid}/delete").status_code == 200
assert store.get_draft(fremd_did) is not None, "FREMDER Entwurf wurde geloescht!"

print("RACE-OK")
"""


ZUSTAND_TEST = r"""
import json, time, uuid
from fastapi.testclient import TestClient
from web.server import app, store, signer
import web.app_api as A
import web.sold, web.pricecharting, web.prices

client = TestClient(app)
acc = store.create_account("zustand@example.org")
client.cookies.set("listo_session", signer.dumps(acc["id"]))

async def nix(*a, **k): return None
async def kurs(): return 0.9
A.research_price = nix
web.sold.fetch_sold = nix
web.pricecharting.lookup_pc = nix
web.prices.usd_eur = kurs

# Der Selbsttest-Befund vom 03.08.: PSA-10-Slab mit TCGplayer-ROHPREIS —
# der Refresh muss ihn als Spanne ausweisen, nie als „belegt".
iid = uuid.uuid4().hex[:12]
store._conn.execute(
    "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
    (iid, acc["id"], time.time(), time.time(),
     json.dumps({"status": "ready", "name": "Ace OP08-013 PSA 10", "photos": [],
                 "est_value": 233.11, "price_source": "tcgplayer",
                 "graded": {"grader": "PSA", "grade": "10"},
                 "card_info": {"single": False, "game": "onepiece", "name": None},
                 "analysis": {"search_query_for_pricing": "Ace OP08-013 PSA 10"}})))
store._conn.commit()
r = client.post(f"/api/app/collection/item/{iid}/refresh-price")
d = r.json()
assert r.status_code == 200, r.text[:300]
# Neue Spec 07.08. (Review-Fund): Der Rohpreis der UNGEGRADETEN Karte ist am
# Slab um Größenordnungen falsch — ehrlich ist est_value=None/unbekannt, die
# Zahl steht nur noch als Untergrenze im Detail. Vorher stand hier ein
# 0,06-€-„Richtwert" im Portfolio und im Preisalarm.
assert d["est_value"] is None, f"Rohpreis blieb als Wert am Slab: {d['est_value']}"
assert d["price_state"] == "unbekannt", d["price_state"]
assert d["price_reason"] == "ROHPREIS_SLAB", d["price_reason"]

# Dieselbe Quelle an einer ROHEN Karte bleibt belegt
iid2 = uuid.uuid4().hex[:12]
store._conn.execute(
    "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
    (iid2, acc["id"], time.time(), time.time(),
     json.dumps({"status": "ready", "name": "Glurak 199/165", "photos": [],
                 "est_value": 40.0, "price_source": "cardmarket",
                 "card_info": {"single": False, "game": "pokemon", "name": None},
                 "analysis": {"search_query_for_pricing": "Glurak 199/165"}})))
store._conn.commit()
d2 = client.post(f"/api/app/collection/item/{iid2}/refresh-price").json()
assert d2["price_state"] == "belegt", d2["price_state"]

print("ZUSTAND-OK")
"""


def test_rohpreis_am_slab_ist_nie_belegt():
    """Selbsttest-Befund 03.08.: Der TCGplayer-Rohpreis ist für einen Slab
    nur die Untergrenze — price_state muss das ehrlich sagen."""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "zu.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", ZUSTAND_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "ZUSTAND-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"


OFFERS_TEST = r"""
import json, time, uuid
from fastapi.testclient import TestClient
from web.server import app, store, signer
import web.app_api as A
import web.prices

client = TestClient(app)
acc = store.create_account("offers@example.org")
client.cookies.set("listo_session", signer.dumps(acc["id"]))

iid = uuid.uuid4().hex[:12]
store._conn.execute(
    "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
    (iid, acc["id"], time.time(), time.time(),
     json.dumps({"status": "ready", "name": "Glurak 199/165", "photos": []})))
store._conn.commit()

# Externe Abrufe kappen: Browse und Wechselkurs werden gezählt statt gerufen
aufrufe = {"n": 0}
async def fake_research(client_, query, limit=20, market="eu", title_filter=None):
    aufrufe["n"] += 1
    w = "USD" if market in ("us", "jp") else "EUR"
    return {"count": 6, "min": 80.0, "max": 120.0, "median": 100.0,
            "query": query, "currency": w, "market": market,
            "samples": [{"title": "Glurak 199/165", "price": 100.0, "url": None, "image": None}]}
async def fake_rate():
    return 0.9
A.research_price = fake_research
web.prices.usd_eur = fake_rate

# 1) USA-Markt: USD plus EUR-Umrechnung, Median ab 5 Angeboten belastbar
r = client.get(f"/api/app/collection/item/{iid}/offers?market=us")
d = r.json()
assert r.status_code == 200, r.text[:300]
assert d["currency"] == "USD" and d["median"] == 100.0
assert d["median_eur"] == 90.0, d
assert d["solid"] is True
assert d["samples"][0]["price_eur"] == 90.0

# 2) Cache: zweiter Abruf desselben Markts darf NICHT erneut zu eBay gehen
vorher = aufrufe["n"]
r2 = client.get(f"/api/app/collection/item/{iid}/offers?market=us")
assert r2.status_code == 200 and aufrufe["n"] == vorher, "Cache griff nicht"

# 3) Anderer Markt = eigener Cache-Eintrag = neuer Abruf
client.get(f"/api/app/collection/item/{iid}/offers?market=jp")
assert aufrufe["n"] == vorher + 1

# 4) Unbekannter Markt prallt ab
assert client.get(f"/api/app/collection/item/{iid}/offers?market=xx").status_code == 400

# 5) Fremdes Konto sieht die Angebote nicht (Mandanten-Trennung)
fremd = store.create_account("fremd2@example.org")
client.cookies.set("listo_session", signer.dumps(fremd["id"]))
assert client.get(f"/api/app/collection/item/{iid}/offers?market=eu").status_code == 404

print("OFFERS-OK")
"""


def test_angebotslage_maerkte_cache_und_besitz():
    """Der Markt-Umschalter (03.08.): USD-Umrechnung, 6-h-Cache je Markt,
    Median erst ab 5 Angeboten, Besitzprüfung."""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "off.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", OFFERS_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "OFFERS-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"


KATALOG_TEST = r"""
import json, time, uuid
from fastapi.testclient import TestClient
from web.server import app, store, signer
import web.app_api as A
import web.sold, web.pricecharting, web.prices

client = TestClient(app)
acc = store.create_account("katalog@example.org")
client.cookies.set("listo_session", signer.dumps(acc["id"]))

async def kein_research(*a, **k): return None
async def kein_sold(*a, **k): return None
async def kein_pc(*a, **k): return None
async def kurs(): return 0.9
A.research_price = kein_research
web.sold.fetch_sold = kein_sold
web.pricecharting.lookup_pc = kein_pc
web.prices.usd_eur = kurs

def stueck(name):
    iid = uuid.uuid4().hex[:12]
    store._conn.execute(
        "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
        (iid, acc["id"], time.time(), time.time(),
         json.dumps({"status": "ready", "name": name, "photos": [],
                     "card_info": {"single": False, "game": "other", "name": None},
                     "analysis": {"search_query_for_pricing": name}})))
    store._conn.commit()
    return iid

# Svens GTA-Paar: identischer Name, zwei Stücke — EIN Katalogschlüssel
a = stueck("Grand Theft Auto Vice City PS2 USA WATA 9.8")
b = stueck("Grand Theft Auto Vice City PS2 USA WATA 9.8")
for iid in (a, b):
    r = client.post(f"/api/app/collection/item/{iid}/refresh-price")
    assert r.status_code == 200, r.text[:300]

def key_of(iid):
    row = store._conn.execute("SELECT data FROM collection_items WHERE id=?", (iid,)).fetchone()
    return json.loads(row["data"]).get("card_key")

ka, kb = key_of(a), key_of(b)
# Genau der NameError vom 03.08.: der Refresh-Pfad warf still und ließ den
# alten Schlüssel stehen. Ein solo:-Schlüssel heißt hier: Pfad kaputt.
assert ka and ka.startswith("h:"), f"card_key nicht deterministisch gesetzt: {ka}"
assert ka == kb, f"GTA-Paar teilt den Schlüssel nicht: {ka} != {kb}"

# Zweiter Refresh desselben Stücks: keine neue Katalogzeile
n1 = store._conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
client.post(f"/api/app/collection/item/{a}/refresh-price")
n2 = store._conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
assert n1 == n2 == 1, f"Katalog wächst beim zweiten Lauf: {n1} -> {n2}"
assert key_of(a) == ka

print("KATALOG-OK")
"""


def test_katalog_schluessel_ende_zu_ende():
    """Stufe 1 (03.08.): Der Refresh-Pfad muss den deterministischen Schlüssel
    wirklich setzen — nicht nur card_key_of isoliert. Der erste Umbau warf im
    Pfad einen NameError, der still im Log verschwand."""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "kat.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", KATALOG_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "KATALOG-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-3000:]}"


RETTUNG_TEST = r"""
import time
from web.server import store       # web.server baut den Router beim Import
import web.app_api as A

acc = store.create_account("rettung@example.org")
uid = 10**15 + acc["id"]

# Ein Entwurf, der seit 11 Stunden in „analyzing" hängt (Svens Ace, 03.08.)
alt = store.create_draft(uid, {"status": "analyzing", "listing": {"title": "Ace"}})
store._conn.execute("UPDATE drafts SET updated_at = ? WHERE id = ?",
                    (time.time() - 11 * 3600, alt))
# Und einer, der gerade WIRKLICH läuft — den darf die Rettung nicht anfassen
frisch = store.create_draft(uid, {"status": "analyzing", "listing": {"title": "Neu"}})
store._conn.commit()

n = A.drafts_retten_einmal()
assert n == 1, f"erwartet 1 Rettung, war {n}"
assert store.get_draft(alt)["status"] == "error"
assert "unterbrochen" in (store.get_draft(alt).get("error") or "")
assert store.get_draft(frisch)["status"] == "analyzing", "Frischer Lauf wurde angefasst"
print("RETTUNG-OK")
"""


AUTONOM_TEST = r"""
import json, time, uuid
from fastapi.testclient import TestClient
from web.server import app, store, signer
from web import health
import web.app_api as A

client = TestClient(app)
acc = store.create_account("autonom@example.org")
client.cookies.set("listo_session", signer.dumps(acc["id"]))

def stueck(status, err=None):
    iid = uuid.uuid4().hex[:12]
    d = {"status": status, "name": None, "photos": ["/tmp/a.jpg"]}
    if err:
        d["error"] = err
    store._conn.execute(
        "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
        (iid, acc["id"], time.time(), time.time(), json.dumps(d)))
    store._conn.commit()
    return iid

# 1) Guthaben leer -> die Quelle ist krank, ein Stück wartet
health.zuruecksetzen()
grund = health.melde("ki", Exception("Your credit balance is too low"))
assert grund == "kein_guthaben"
wartend = stueck("waiting", health.GRUND_TEXTE[grund])

# 2) Der Systemstatus sagt es EINMAL — mit Klartext und Zahl
r = client.get("/api/app/systemstatus")
st = r.json()
assert r.status_code == 200, r.text[:200]
assert st["ok"] is False and st["grund"] == "kein_guthaben"
assert "console.anthropic.com" in st["meldung"]
assert st["wartende"] == 1, st

# 3) Fremde Konten sehen die eigenen Wartenden nicht
fremd = store.create_account("fremd3@example.org")
client.cookies.set("listo_session", signer.dumps(fremd["id"]))
assert client.get("/api/app/systemstatus").json()["wartende"] == 0
client.cookies.set("listo_session", signer.dumps(acc["id"]))

# 4) Genesung -> Status wieder grün, Weckruf genau einmal
health.melde("ki", None)
st2 = client.get("/api/app/systemstatus").json()
assert st2["ok"] is True and st2["meldung"] is None
assert st2["wartende"] == 1, "Wartendes Stück verschwindet nicht von allein"
assert health.genesung_abholen("ki") is True
assert health.genesung_abholen("ki") is False

# 5) Ohne Anmeldung kein Status
client.cookies.clear()
assert client.get("/api/app/systemstatus").status_code == 401

print("AUTONOM-OK")
"""


def test_autonomer_betrieb_ende_zu_ende():
    """Svens Auftrag 04.08.: Ein Infrastruktur-Ausfall lässt Stücke WARTEN
    (nicht scheitern), die App sagt die gemeinsame Ursache einmal oben, und
    nach der Genesung läuft alles von selbst weiter."""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "auto.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", AUTONOM_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "AUTONOM-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"


def test_draft_rettung_loest_haenger_und_schont_laufende():
    """Der 11-Stunden-Hänger von Svens Vorführung (03.08.): abgerissene
    Entwurfs-Pipelines werden auf error gesetzt (App zeigt Retry), frische
    Läufe bleiben unangetastet."""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "ret.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", RETTUNG_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "RETTUNG-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"


def test_loeschen_reisst_keine_laufenden_ab_und_schont_fremde():
    """Vom Prüfteam gefunden: Der erste Lösch-Fix riss laufende Aufbereitungen ab
    (Absturz beim Zurückschreiben) und prüfte den Besitz des Entwurfs nicht."""
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "race.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", ABSTURZ_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "RACE-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"
