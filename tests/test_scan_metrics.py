"""Scan-Metriken, SERO-Effekt-Rechnung und Aufmerksamkeit — ohne echte data.db."""
from __future__ import annotations

import json
import sqlite3
import time
import unittest
from pathlib import Path

from web import scan_metrics as sm


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    sm.ensure_table(c)
    c.execute(
        "CREATE TABLE collection_items ("
        "id TEXT PRIMARY KEY, account_id INTEGER NOT NULL, "
        "created_at REAL NOT NULL, updated_at REAL NOT NULL, data TEXT NOT NULL)")
    c.execute(
        "CREATE TABLE drafts ("
        "id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, status TEXT NOT NULL, "
        "data TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)")
    return c


class TestScanMetricsCounting(unittest.TestCase):
    def test_success_counted_once(self):
        c = _conn()
        self.assertTrue(sm.record_success(c, 1, "a", scan_seconds=70, completed_at=100.0))
        c.commit()
        self.assertEqual(sm.build_impact(c, 1)["successful_scans"], 1)

    def test_retry_same_item_not_double(self):
        c = _conn()
        self.assertTrue(sm.record_success(c, 1, "a", scan_seconds=70, completed_at=100.0))
        self.assertFalse(sm.record_success(c, 1, "a", scan_seconds=90, completed_at=200.0))
        self.assertEqual(sm.build_impact(c, 1)["successful_scans"], 1)

    def test_errors_timeouts_not_counted_without_record(self):
        """Fehler/Timeouts rufen record_success nicht auf — Zähler bleibt 0."""
        c = _conn()
        self.assertEqual(sm.build_impact(c, 1)["successful_scans"], 0)

    def test_premium_and_free_same_counting(self):
        c = _conn()
        sm.record_success(c, 7, "free-1", scan_seconds=60, completed_at=1.0)
        sm.record_success(c, 8, "prem-1", scan_seconds=60, completed_at=1.0)
        self.assertEqual(sm.build_impact(c, 7)["successful_scans"], 1)
        self.assertEqual(sm.build_impact(c, 8)["successful_scans"], 1)

    def test_delete_sell_does_not_lower_lifetime(self):
        c = _conn()
        sm.record_success(c, 1, "gone", scan_seconds=55, completed_at=10.0)
        c.execute(
            "INSERT INTO collection_items VALUES (?,?,?,?,?)",
            ("gone", 1, 1.0, 1.0, json.dumps({"scan_seconds": 55, "status": "ready"})))
        c.execute("DELETE FROM collection_items WHERE id = ?", ("gone",))
        c.commit()
        self.assertEqual(sm.build_impact(c, 1)["successful_scans"], 1)

    def test_account_delete_removes_metrics(self):
        c = _conn()
        sm.record_success(c, 1, "a", scan_seconds=40, completed_at=1.0)
        sm.record_success(c, 2, "b", scan_seconds=40, completed_at=1.0)
        sm.delete_account_metrics(c, 1)
        c.commit()
        self.assertEqual(sm.build_impact(c, 1)["successful_scans"], 0)
        self.assertEqual(sm.build_impact(c, 2)["successful_scans"], 1)


class TestBackfill(unittest.TestCase):
    def test_backfill_repeatable_no_double(self):
        c = _conn()
        c.execute(
            "INSERT INTO collection_items VALUES (?,?,?,?,?)",
            ("x", 3, 1.0, 1.0, json.dumps({"scan_seconds": 81.2, "status": "ready"})))
        c.commit()
        self.assertEqual(sm.backfill_from_collection(c), 1)
        self.assertEqual(sm.backfill_from_collection(c), 0)
        self.assertEqual(sm.build_impact(c, 3)["successful_scans"], 1)

    def test_historical_backfill_not_in_7d(self):
        c = _conn()
        c.execute(
            "INSERT INTO collection_items VALUES (?,?,?,?,?)",
            ("old", 4, 1.0, 1.0, json.dumps({"scan_seconds": 50, "status": "ready"})))
        c.commit()
        sm.backfill_from_collection(c)
        now = time.time()
        self.assertEqual(sm.activity_scanned_7d(c, 4, now=now), 0)
        sm.record_success(c, 4, "new", scan_seconds=40, completed_at=now - 100)
        self.assertEqual(sm.activity_scanned_7d(c, 4, now=now), 1)


class TestImpactMath(unittest.TestCase):
    def test_examples_1_10_37_100(self):
        cases = {
            1: (900, 120, 780),
            10: (9000, 1200, 7800),
            37: (33300, 4440, 28860),
            100: (90000, 12000, 78000),
        }
        for n, (man, sero, saved) in cases.items():
            with self.subTest(n=n):
                i = sm.impact_from_count(n)
                self.assertEqual(i["manual_seconds"], man)
                self.assertEqual(i["sero_seconds"], sero)
                self.assertEqual(i["saved_seconds"], saved)
        self.assertEqual(sm.format_duration_de(780), "13 Min")
        self.assertEqual(sm.format_duration_de(7800), "2 Std 10 Min")
        self.assertEqual(sm.format_duration_de(28860), "8 Std 1 Min")
        self.assertEqual(sm.format_duration_de(78000), "21 Std 40 Min")
        self.assertEqual(sm.format_duration_de(3600), "1 Std")

    def test_avg_needs_three_samples(self):
        c = _conn()
        sm.record_success(c, 1, "a", scan_seconds=60, completed_at=1.0)
        sm.record_success(c, 1, "b", scan_seconds=80, completed_at=2.0)
        self.assertIsNone(sm.build_impact(c, 1)["avg_analysis_seconds"])
        sm.record_success(c, 1, "c", scan_seconds=70, completed_at=3.0)
        self.assertEqual(sm.build_impact(c, 1)["avg_analysis_seconds"], 70)

    def test_saved_not_from_scan_seconds(self):
        c = _conn()
        sm.record_success(c, 1, "a", scan_seconds=900, completed_at=1.0)
        i = sm.build_impact(c, 1)
        self.assertEqual(i["saved_seconds"], 780)
        self.assertNotEqual(i["saved_seconds"], 900)


class TestAttention(unittest.TestCase):
    def test_unknown_and_stale_count(self):
        items = [
            {"status": "ready", "price_state": "unbekannt", "price_reason": "UNBEKANNT_KEINE_BELEGE"},
            {"status": "ready", "price_state": "spanne", "price_reason": "BELEGE_ALT"},
            {"status": "error"},
            {"status": "ready", "identity_eval": {"pricing_ready": False}},
        ]
        self.assertEqual(sm.attention_count(items), 4)

    def test_belegt_current_not_problem(self):
        items = [
            {"status": "ready", "price_state": "belegt", "price_reason": None, "est_value": 12},
            {"status": "ready", "price_state": "spanne", "price_reason": "NUR_ANGEBOTE"},
            {"wishlist": True, "price_state": "unbekannt"},
            {"sold": True, "price_state": "unbekannt"},
        ]
        self.assertEqual(sm.attention_count(items), 0)


class TestActivityPublished(unittest.TestCase):
    def test_published_7d_excludes_dry_run(self):
        c = _conn()
        now = time.time()
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("p1", 99, "published",
             json.dumps({"published_at": now - 100}), now - 100, now - 100))
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("d1", 99, "dry_run_done", "{}", now - 100, now - 100))
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("old", 99, "published",
             json.dumps({"published_at": now - 20 * 86400}),
             now - 20 * 86400, now - 20 * 86400))
        c.commit()
        self.assertEqual(sm.activity_published_7d(c, [99], now=now), 1)

    def test_sales_sync_updated_at_does_not_inflate(self):
        c = _conn()
        now = time.time()
        # Vor 20 Tagen veröffentlicht, Sync hat updated_at gerade angefasst
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("old", 99, "published",
             json.dumps({"published_at": now - 20 * 86400, "sku": "SKU-OLD"}),
             now - 20 * 86400, now))
        c.commit()
        self.assertEqual(sm.activity_published_7d(c, [99], now=now), 0)


class TestActivitySold(unittest.TestCase):
    def test_sold_7d_counts_verkauft_with_sold_at(self):
        c = _conn()
        now = time.time()
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("s1", 99, "ended",
             json.dumps({"ended_reason": "Verkauft", "sold_at": now - 100}),
             now - 100, now - 100))
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("ended-other", 99, "ended",
             json.dumps({"ended_reason": "Zurückgezogen", "sold_at": now - 50}),
             now - 50, now - 50))
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("old-sale", 99, "ended",
             json.dumps({"ended_reason": "Verkauft", "sold_at": now - 20 * 86400}),
             now - 20 * 86400, now - 20 * 86400))
        c.commit()
        self.assertEqual(sm.activity_sold_7d(c, [99], now=now), 1)

    def test_sold_7d_falls_back_to_updated_at_without_sold_at(self):
        c = _conn()
        now = time.time()
        c.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?)",
            ("legacy", 99, "ended",
             json.dumps({"ended_reason": "Verkauft"}),
             now - 100, now - 200))
        c.commit()
        self.assertEqual(sm.activity_sold_7d(c, [99], now=now), 1)


class TestFrontendStrings(unittest.TestCase):
    def test_str_en_keys(self):
        js = Path(__file__).resolve().parent.parent.joinpath("frontend/sero.js").read_text()
        keys = [
            "Dein SERO-Effekt",
            "Zeit gespart",
            "mit {0} erfassten Stücken",
            "mit 1 erfassten Stück",
            "So wird gerechnet",
            "Berechnung schließen",
            "Letzte 7 Tage",
            "gescannt",
            "neu gelistet",
            "verkauft",
            "Häufige Fragen",
            "Brauche ich einen eBay-Developer-Account?",
            "Kann SERO etwas ohne mein Okay veröffentlichen?",
            "Liest SERO wirklich PSA-Labels vom Foto?",
            "Was passiert mit meinen Daten und Fotos?",
            "Welche Stücke funktionieren am besten?",
            "Kann ich jederzeit kündigen?",
            "Nein. Kein Developer-Account, keine API-Keys. Du nimmst dein normales eBay-Verkäuferkonto: anmelden, Freigabe erteilen, den Link zurück in die App einfügen, fertig. SERO sieht dein Passwort nie.",
            "Ø technische Analysezeit",
            "läuft im Hintergrund",
            "1 Min",
            "1 Std",
            "{0} Std",
        ]
        for k in keys:
            self.assertIn(f'"{k}":', js, f"STR_EN fehlt für {k!r}")
        self.assertIn("function formatDuration", js)
        self.assertIn('key: "effekt"', js)
        self.assertIn('key: "aktivitaet"', js)
        self.assertIn('key: "faq"', js)
        self.assertIn("15 Minuten", js)
        self.assertIn("2 Minuten", js)
        self.assertNotIn("rund 8 Minuten", js)
        self.assertNotIn("itemNeedsAttention", js)
        self.assertNotIn("Im Blick", js)
        self.assertNotIn('data-st="listed"', js)
        self.assertNotIn('data-st="sold"', js)
        self.assertNotIn('data-st="attention"', js)
        self.assertIn("HERO_BRAND", js)
        self.assertIn('state.range || "Max"', js)
        self.assertIn("loadSales()", js)
        self.assertIn("thumb(r.photo, 240)", js)
        self.assertIn("publish_uncertain",
                      Path(__file__).resolve().parent.parent.joinpath("web/app_api.py").read_text())

class TestNoLlmPricingViolation(unittest.TestCase):
    def test_module_has_no_llm_price_path(self):
        src = Path(sm.__file__).read_text()
        self.assertNotIn("ClaudeAnalyzer", src)
        self.assertNotIn("from bot.claude", src)
        self.assertNotIn("anthropic", src.lower())


if __name__ == "__main__":
    unittest.main()
