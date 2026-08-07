import tempfile
from pathlib import Path

from bot.drafts import Store
from bot.main import extract_oauth_code


def _tmp_store():
    return Store(Path(tempfile.mkstemp(suffix=".db")[1]))


def test_extract_oauth_code_variants():
    url = ("https://auth2.ebay.com/oauth2/ThirdPartyAuthSucessFailure?isAuthSuccessful=true"
           "&code=v%5E1.1%23i%5E1%23p%5E3%23t%5EUl41&expires_in=299")
    assert extract_oauth_code(url) == "v^1.1#i^1#p^3#t^Ul41"
    # Roher Code direkt
    assert extract_oauth_code("v^1.1#i^1#p^3#t^Ul41") == "v^1.1#i^1#p^3#t^Ul41"
    # Normaler Text ist kein Code
    assert extract_oauth_code("Hallo, was kostet das?") is None
    assert extract_oauth_code("16,90") is None


def test_users_table_roundtrip():
    store = _tmp_store()
    assert store.get_user(111) is None
    store.upsert_user(111, status="connecting")
    assert store.get_user(111)["status"] == "connecting"
    # Policies unvollständig -> None
    assert store.user_policies(111) is None
    store.upsert_user(111, status="ready", merchant_location_key="listo-111",
                      fulfillment_policy_id="f", payment_policy_id="p", return_policy_id="r")
    pol = store.user_policies(111)
    assert pol == {"merchant_location_key": "listo-111", "fulfillment_policy_id": "f",
                   "payment_policy_id": "p", "return_policy_id": "r"}
    # Zweiter Nutzer ist unabhängig
    store.upsert_user(222, status="ready")
    assert store.user_policies(222) is None
    assert store.get_user(111)["merchant_location_key"] == "listo-111"


def test_user_token_isolation():
    from bot.ebay.auth import _token_key
    store = _tmp_store()
    store.kv_set(_token_key(111), {"access_token": "A", "access_expires": 9999999999,
                                   "refresh_token": "RA", "refresh_expires": 9999999999})
    store.kv_set(_token_key(222), {"access_token": "B", "access_expires": 9999999999,
                                   "refresh_token": "RB", "refresh_expires": 9999999999})
    assert store.kv_get(_token_key(111))["access_token"] == "A"
    assert store.kv_get(_token_key(222))["access_token"] == "B"


def test_offer_payload_uses_per_user_policies():
    from bot.ebay.inventory import build_offer_payload
    pol_a = {"merchant_location_key": "listo-111", "fulfillment_policy_id": "fa",
             "payment_policy_id": "pa", "return_policy_id": "ra"}
    pol_b = {"merchant_location_key": "listo-222", "fulfillment_policy_id": "fb",
             "payment_policy_id": "pb", "return_policy_id": "rb"}
    a = build_offer_payload(pol_a, "S1", category_id="1", price_eur="5.00", listing_description="x")
    b = build_offer_payload(pol_b, "S2", category_id="1", price_eur="5.00", listing_description="x")
    assert a["merchantLocationKey"] == "listo-111" and b["merchantLocationKey"] == "listo-222"
    assert a["listingPolicies"]["fulfillmentPolicyId"] == "fa"
    assert b["listingPolicies"]["fulfillmentPolicyId"] == "fb"


def test_listings_monthly_limit_counting():
    store = _tmp_store()
    for i in range(3):
        store.log_listing(f"SKU{i}", "Titel", "1.00", None, f"lid{i}", dry_run=False, telegram_id=111)
    store.log_listing("SKUDRY", "Titel", "1.00", None, None, dry_run=True, telegram_id=111)
    store.log_listing("SKUX", "Titel", "1.00", None, "lidx", dry_run=False, telegram_id=222)
    assert store.listings_this_month(111) == 3   # Dry-Runs zählen nicht
    assert store.listings_this_month(222) == 1
    assert store.listings_this_month(999) == 0


def test_plan_limits_table():
    from bot.main import PLAN_LIMITS
    assert PLAN_LIMITS == {"starter": 30, "reseller": 200, "shop": None}
    assert "trial" not in PLAN_LIMITS  # Trial darf NICHT veröffentlichen


def test_stale_draft_ids(tmp_path):
    """Unfertige Drafts altern raus, veröffentlichte behalten den DB-Eintrag."""
    import time
    from bot.drafts import Store

    store = Store.__new__(Store)
    import sqlite3, threading
    store._conn = sqlite3.connect(":memory:", check_same_thread=False)
    store._conn.row_factory = sqlite3.Row
    store._lock = threading.Lock()
    from bot.drafts import _SCHEMA
    store._conn.executescript(_SCHEMA)

    old = time.time() - 10 * 86400
    fresh = time.time()
    store._conn.execute("INSERT INTO drafts VALUES ('a', 1, 'ready', '{}', ?, ?)", (old, old))
    store._conn.execute("INSERT INTO drafts VALUES ('b', 1, 'published', '{}', ?, ?)", (old, old))
    store._conn.execute("INSERT INTO drafts VALUES ('c', 1, 'ready', '{}', ?, ?)", (fresh, fresh))
    store._conn.commit()

    dead, old_pub = store.stale_draft_ids(unfinished_older_than_s=7 * 86400,
                                          published_older_than_s=14 * 86400)
    assert dead == ["a"]          # alt + unfertig -> löschen
    assert old_pub == []          # published erst nach 14 Tagen (b ist 10 Tage alt)
    dead2, old_pub2 = store.stale_draft_ids(unfinished_older_than_s=7 * 86400,
                                            published_older_than_s=7 * 86400)
    assert old_pub2 == ["b"]      # jetzt fällig — aber nur Fotos, kein DB-Delete
