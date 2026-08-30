"""Profil-Kennzahlen und Billing-/Alert-Verhalten."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


class TestProfileStatsUnit(unittest.TestCase):
    def test_empty(self):
        from web.profile_stats import summarize_profile
        s = summarize_profile(items=[], drafts=[])
        self.assertEqual(s["active_on_ebay"], 0)
        self.assertEqual(s["in_collection"], 0)
        self.assertEqual(s["sold"], 0)
        self.assertEqual(s["portfolio_pieces"], 0)

    def test_quantity_sum_and_wishlist_excluded(self):
        from web.profile_stats import summarize_profile
        items = [
            {"id": "a", "quantity": 3},
            {"id": "b", "quantity": 2, "wishlist": True},
            {"id": "c", "quantity": "bad"},
        ]
        s = summarize_profile(items=items, drafts=[])
        self.assertEqual(s["in_collection"], 4)  # 3 + 1(default for bad)

    def test_published_and_active_listing_still_in_collection(self):
        from web.profile_stats import summarize_profile
        items = [{"id": "a", "quantity": 1, "draft_id": "d1"}]
        drafts = [{"id": "d1", "status": "published"}]
        s = summarize_profile(items=items, drafts=drafts)
        self.assertEqual(s["active_on_ebay"], 1)
        self.assertEqual(s["in_collection"], 1)
        self.assertEqual(s["sold"], 0)

    def test_ended_without_sold_not_counted(self):
        from web.profile_stats import summarize_profile
        drafts = [{"id": "d1", "status": "ended", "ended_reason": "Beendet (ENDED)"}]
        items = [{"id": "a", "quantity": 1}]
        s = summarize_profile(items=items, drafts=drafts)
        self.assertEqual(s["sold"], 0)
        self.assertEqual(s["in_collection"], 1)

    def test_sold_ts_counts_once(self):
        from web.profile_stats import summarize_profile
        items = [{"id": "a", "quantity": 2, "sold_ts": 1, "draft_id": "d1"}]
        drafts = [{"id": "d1", "status": "ended", "ended_reason": "Verkauft"}]
        s = summarize_profile(items=items, drafts=drafts)
        self.assertEqual(s["sold"], 1)
        self.assertEqual(s["in_collection"], 0)

    def test_sold_draft_without_item(self):
        from web.profile_stats import summarize_profile
        drafts = [{"id": "d9", "status": "ended", "ended_reason": "Verkauft"}]
        s = summarize_profile(items=[], drafts=drafts)
        self.assertEqual(s["sold"], 1)

    def test_bad_quantity_no_crash(self):
        from web.profile_stats import summarize_profile
        items = [{"id": "a", "quantity": None}, {"id": "b", "quantity": -5}]
        s = summarize_profile(items=items, drafts=[])
        self.assertEqual(s["in_collection"], 1)  # None→1, -5→0


class TestBillingReturnGuard(unittest.TestCase):
    def test_return_url_is_app_slash(self):
        src = Path("web/server.py").read_text(encoding="utf-8")
        self.assertIn('return_url=public_base_url(request) + "/app/"', src)
        self.assertNotIn('+"/app.html"', src.replace(" ", ""))


class TestPriceAlertPreference(unittest.TestCase):
    def test_check_alert_respects_preference_source(self):
        src = Path("web/app_api.py").read_text(encoding="utf-8")
        self.assertIn("def price_alerts_on", src)
        self.assertIn("if not price_alerts_on(account_id)", src)
        self.assertIn("price_alerts_enabled", src)
        # SSE notify bleibt unabhängig
        self.assertIn("def notify(account_id", src)


if __name__ == "__main__":
    unittest.main()
