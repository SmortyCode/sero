"""Contract-Tests: identify_card-Ausgabe → Identity (set_hint, Sprache aus Aspects)."""
from __future__ import annotations

import unittest

from web.identity import (
    evaluate_identity,
    identity_from_item,
    normalize_legacy_analysis,
)


class TestSetHintAndLanguage(unittest.TestCase):
    def test_set_hint_becomes_set_name(self):
        item = {
            "card_info": {
                "name": "Pikachu",
                "number": "025",
                "game": "pokemon",
                "language": "de",
                "set_hint": "Base Set",
            },
            "analysis": {},
        }
        ident = identity_from_item(item)
        self.assertEqual(ident.set_name.value, "Base Set")

    def test_language_from_aspects(self):
        item = {
            "card_info": {
                "name": "Pikachu",
                "number": "025",
                "game": "pokemon",
                "set": "Base",
            },
            "analysis": {"aspects": {"Sprache": ["Deutsch"]}},
        }
        ident = identity_from_item(item)
        self.assertEqual(ident.language.value, "Deutsch")

    def test_language_from_title_hint(self):
        item = {
            "name": "Pokémon Exeggutor 066/063 Mega Brave Japanisch CGC Pristine 10",
            "card_info": {
                "name": "Exeggutor",
                "number": "66",
                "game": "pokemon",
                "set_hint": "Mega Brave",
                "set_total": "63",
            },
            "graded": {"grader": "CGC", "grade": "10", "label_type": "pristine",
                       "cert_number": "6138932099"},
            "analysis": {"title": "Pokémon Exeggutor 066/063 Mega Brave Japanisch CGC Pristine 10"},
        }
        ident = identity_from_item(item)
        self.assertEqual(ident.language.value, "Japanisch")
        ev = evaluate_identity(ident)
        self.assertNotIn("MISSING_LANGUAGE", [r.value for r in ev.blocking_reasons])

    def test_missing_language_needs_review(self):
        item = {
            "card_info": {
                "name": "Pikachu",
                "number": "025",
                "game": "pokemon",
                "set": "Base",
            },
            "analysis": {},
        }
        ev = evaluate_identity(identity_from_item(item))
        self.assertFalse(ev.pricing_ready)
        self.assertEqual(ev.recognition_state.value, "needs_review")

    def test_identify_card_shape_legacy(self):
        """Exakte Struktur wie identify_card() liefert (ohne Netz)."""
        card_info = {
            "game": "pokemon",
            "name": "Glurak",
            "number": "199",
            "set_total": "165",
            "set_hint": "151",
            "single": True,
            "language": None,
        }
        analysis = {
            "title": "Glurak 199/165",
            "aspects": {"Sprache": ["Englisch"]},
        }
        ident = identity_from_item({"card_info": card_info, "analysis": analysis})
        self.assertEqual(ident.set_name.value, "151")
        self.assertEqual(ident.language.value, "Englisch")

    def test_uncertain_legacy_not_ready(self):
        analysis = {
            "uncertain": True,
            "question": "Welche Sprache hat die Karte?",
            "title": "Unklare Karte",
        }
        ident = normalize_legacy_analysis(analysis)
        ev = evaluate_identity(ident)
        self.assertFalse(ev.pricing_ready)


if __name__ == "__main__":
    unittest.main()

