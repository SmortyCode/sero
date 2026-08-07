import json
import re

from bot.ebay.inventory import translate_ebay_error


def _err_25002(msg):
    return json.dumps({"errors": [{"errorId": 25002, "message": msg}]})


def test_25002_single_value_gets_matching_hint():
    out = translate_ebay_error(_err_25002(
        "A user error has occurred. Verlag darf nur einen Wert enthalten."), 400)
    assert "erlaubt nur einen Wert" in out
    assert "merchantLocationKey" not in out   # der falsche Location-Hint ist weg


def test_25002_location_keeps_location_hint():
    out = translate_ebay_error(_err_25002(
        "Invalid merchantLocationKey or location not found."), 400)
    assert "merchantLocationKey" in out


def test_25002_generic_has_no_misleading_hint():
    out = translate_ebay_error(_err_25002("Ein anderer Nutzerfehler."), 400)
    assert "merchantLocationKey" not in out
    assert "nur einen Wert" not in out


def test_error_message_aspect_name_regex():
    """Das Sicherheitsnetz in run_upload muss den Aspektnamen extrahieren können."""
    text = ("eBay-Fehler 25002: A user error has occurred. "
            "Verlag darf nur einen Wert enthalten. Entfernen Sie die zusätzlichen Werte.")
    m = re.search(r"([A-ZÄÖÜ][\w\säöüß/-]*?) darf nur einen Wert", text)
    assert m and m.group(1).strip() == "Verlag"
    m2 = re.search(r"([A-ZÄÖÜ][\w\säöüß/-]*?) darf nur einen Wert",
                   "Spielname/Untertitel darf nur einen Wert enthalten")
    assert m2 and m2.group(1).strip() == "Spielname/Untertitel"
