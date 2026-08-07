"""Publish-Doppeltipp-Schutz (Audit-Befund P0.4).

Zwei parallele Upload-Läufe für denselben Entwurf würden dieselbe Karte
zweimal auf eBay stellen — echtes Geld, echte Gebühren. Der Schutz ist ein
atomarer Status-Claim in SQLite: genau EIN Aufrufer gewinnt.
"""
import inspect
import threading
from pathlib import Path

import pytest

from bot.drafts import Store

VERBOTEN = ("publishing", "published", "ended")


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "test.db")


def neuer_draft(store, status="ready"):
    return store.create_draft(1, {"status": status, "listing": {"title": "T"}})


def test_claim_gewinnt_genau_einer(store):
    draft_id = neuer_draft(store)
    ergebnisse = []

    def versuch():
        ergebnisse.append(store.claim_draft(draft_id, "publishing", verboten=VERBOTEN))

    threads = [threading.Thread(target=versuch) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert ergebnisse.count(True) == 1, "Genau EIN Lauf darf den Claim gewinnen"
    assert store.get_draft(draft_id)["status"] == "publishing"


def test_published_nicht_claimbar(store):
    for endzustand in ("published", "ended", "publishing"):
        draft_id = neuer_draft(store, status=endzustand)
        assert store.claim_draft(draft_id, "publishing", verboten=VERBOTEN) is False
        assert store.get_draft(draft_id)["status"] == endzustand


def test_release_setzt_zurueck(store):
    draft_id = neuer_draft(store)
    assert store.claim_draft(draft_id, "publishing", verboten=VERBOTEN)
    assert store.release_draft_claim(draft_id, "ready") is True
    assert store.get_draft(draft_id)["status"] == "ready"
    # Nach dem Release ist ein neuer Versuch möglich (Retry nach Fehler).
    assert store.claim_draft(draft_id, "publishing", verboten=VERBOTEN)


def test_release_laesst_endzustand_stehen(store):
    """Der Lauf hat selbst published gesetzt — das finally darf das nicht kippen."""
    draft_id = neuer_draft(store)
    assert store.claim_draft(draft_id, "publishing", verboten=VERBOTEN)
    d = store.get_draft(draft_id)
    d["status"] = "published"
    store.update_draft(draft_id, d)
    assert store.release_draft_claim(draft_id, "ready") is False
    assert store.get_draft(draft_id)["status"] == "published"


def test_claim_erhaelt_uebrige_felder(store):
    draft_id = store.create_draft(1, {"status": "ready", "price": "9,99",
                                      "listing": {"title": "Karte"}})
    store.claim_draft(draft_id, "publishing", verboten=VERBOTEN)
    d = store.get_draft(draft_id)
    assert d["price"] == "9,99"
    assert d["listing"]["title"] == "Karte"


def test_upload_pfad_nutzt_claim():
    """Quelltext-Wache: Wer den Claim aus app_run_upload entfernt, öffnet den
    Doppel-Listing-Bug wieder — dieser Test schlägt dann an."""
    quelle = (Path(__file__).parent.parent / "web" / "app_api.py").read_text()
    start = quelle.index("async def app_run_upload")
    ende = quelle.index("async def app_run_update")
    upload = quelle[start:ende]
    assert "claim_draft" in upload, "app_run_upload muss den atomaren Claim setzen"
    assert "release_draft_claim" in upload, "app_run_upload muss den Claim im finally lösen"
    assert upload.index("claim_draft") < upload.index("upload_image"), \
        "Der Claim muss VOR der ersten eBay-Arbeit stehen"
