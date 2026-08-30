"""Zentrale Portfolio-Semantik — Fixtures, keine Live-Zahlen."""
from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from web import portfolio as pf

BERLIN = ZoneInfo("Europe/Berlin")


class TestMoney(unittest.TestCase):
    def test_eur_cents_roundtrip(self):
        self.assertEqual(pf.eur_to_cents("12,34"), 1234)
        self.assertEqual(pf.eur_to_cents(12.34), 1234)
        self.assertEqual(pf.cents_to_eur(1234), 12.34)
        self.assertIsNone(pf.eur_to_cents(None))
        self.assertIsNone(pf.eur_to_cents(""))

    def test_position_12_34_x3(self):
        item = {"est_value": "12.34", "quantity": 3, "price_state": "belegt",
                "price_source": "ebay_sold"}
        self.assertEqual(pf.unit_value_cents(item), 1234)
        self.assertEqual(pf.position_value_cents(item), 3702)
        self.assertEqual(pf.cents_to_eur(3702), 37.02)


class TestOwnership(unittest.TestCase):
    def test_row_vs_piece_count(self):
        items = [
            {"id": "a", "quantity": 3, "est_value": 10, "price_state": "belegt",
             "price_source": "ebay_sold"},
        ]
        s = pf.summarize_portfolio(items)
        self.assertEqual(s.row_count, 1)
        self.assertEqual(s.piece_count, 3)
        self.assertEqual(s.portfolio_total_cents, 3000)

    def test_unknown_excluded_from_sum(self):
        items = [
            {"id": "a", "quantity": 1, "est_value": 99, "price_state": "unbekannt",
             "price_source": None},
            {"id": "b", "quantity": 1, "est_value": 10, "price_state": "belegt",
             "price_source": "ebay_sold"},
        ]
        s = pf.summarize_portfolio(items)
        self.assertEqual(s.portfolio_total_cents, 1000)

    def test_published_excluded_from_portfolio_in_physical(self):
        items = [
            {"id": "a", "quantity": 1, "est_value": 50, "price_state": "belegt",
             "price_source": "ebay_sold", "draft_id": "d1", "draft_status": "published"},
            {"id": "b", "quantity": 1, "est_value": 10, "price_state": "belegt",
             "price_source": "ebay_sold"},
        ]
        s = pf.summarize_portfolio(items)
        self.assertEqual(s.row_count, 1)
        self.assertEqual(s.portfolio_total_cents, 1000)
        self.assertEqual(s.physical_row_count, 2)
        self.assertEqual(s.physical_total_cents, 6000)

    def test_own_value_not_market(self):
        items = [
            {"id": "a", "quantity": 1, "est_value": 25, "est_value_manual": 25,
             "price_state": "eigener_wert", "price_source": "manual"},
        ]
        s = pf.summarize_portfolio(items)
        self.assertEqual(pf.value_basis(items[0]), "own_value")
        self.assertEqual(s.own_value_cents, 2500)
        self.assertEqual(s.market_value_cents, 0)
        self.assertEqual(s.portfolio_total_cents, 2500)


class TestHistoryBerlin(unittest.TestCase):
    def test_last_point_matches_total(self):
        hist = [{"day": "2026-08-08", "value": 100.0}]
        now = datetime(2026, 8, 9, 10, 0, tzinfo=BERLIN)
        out, day, tz = pf.ensure_history_ends_at_total(
            hist, portfolio_total_cents=61057, now=now)
        self.assertEqual(day, "2026-08-09")
        self.assertEqual(tz, "Europe/Berlin")
        self.assertEqual(out[-1]["day"], "2026-08-09")
        self.assertEqual(out[-1]["value"], 610.57)

    def test_midnight_berlin_not_utc(self):
        # 00:30 Berlin am 10.08. — UTC wäre noch 9.08. 22:30
        now = datetime(2026, 8, 10, 0, 30, tzinfo=BERLIN)
        out, day, _ = pf.ensure_history_ends_at_total(
            [{"day": "2026-08-09", "value": 1.0}],
            portfolio_total_cents=200, now=now)
        self.assertEqual(day, "2026-08-10")
        self.assertEqual(out[-1]["day"], "2026-08-10")

    def test_same_day_overwrite(self):
        now = datetime(2026, 8, 9, 23, 59, tzinfo=BERLIN)
        out, day, _ = pf.ensure_history_ends_at_total(
            [{"day": "2026-08-09", "value": 999.0}],
            portfolio_total_cents=100, now=now)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["value"], 1.0)


class TestRevision(unittest.TestCase):
    def test_draft_fingerprint_changes_rev(self):
        a = pf.collection_revision(item_count=11, items_updated_at=1.0,
                                   draft_fingerprint="published=2")
        b = pf.collection_revision(item_count=11, items_updated_at=1.0,
                                   draft_fingerprint="published=3")
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("11:1.0"))


if __name__ == "__main__":
    unittest.main()
