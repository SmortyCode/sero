#!/bin/sh
# SERO-Prüflauf — läuft nach JEDER Änderung. Ampel statt stiller Regressionen.
cd /Users/smorty/ebay-bot || exit 1
FAIL=0
ck() { if [ "$2" = "$3" ]; then echo "  ✓ $1"; else echo "  ✗ $1 (ist: $2, soll: $3)"; FAIL=1; fi; }

echo "── SERO Smoke-Test $(date '+%H:%M:%S')"
ck "App erreichbar (200)"        "$(curl -s -o /dev/null -w '%{http_code}' localhost:3000/app/)" "200"
ck "Auth-Gate collection (401)"  "$(curl -s -o /dev/null -w '%{http_code}' localhost:3000/api/app/collection)" "401"
ck "Auth-Gate dashboard (401)"   "$(curl -s -o /dev/null -w '%{http_code}' localhost:3000/api/app/dashboard)" "401"
ck "Auth-Gate delete (401)"      "$(curl -s -o /dev/null -w '%{http_code}' -X POST localhost:3000/api/app/account/delete)" "401"
ck "Security-Header nosniff"     "$(curl -sI localhost:3000/app/ | grep -ci 'x-content-type-options')" "1"

./.venv/bin/python -c "import web.server, web.catalog, web.sold, web.cardscan, web.pricecharting, web.ebay_insights" 2>/dev/null \
  && echo "  ✓ Python-Module importieren" || { echo "  ✗ Python-Import kaputt"; FAIL=1; }
node --check /Users/smorty/sero-app/web/sero.js 2>/dev/null \
  && echo "  ✓ sero.js Syntax" || { echo "  ✗ sero.js Syntax"; FAIL=1; }

CSSV=$(grep -o 'sero\.css?v=[0-9]*' /Users/smorty/sero-app/web/index.html | grep -o '[0-9]*')
JSV=$(grep -o 'sero\.js?v=[0-9]*' /Users/smorty/sero-app/web/index.html | grep -o '[0-9]*')
[ -n "$CSSV" ] && [ -n "$JSV" ] && echo "  ✓ Versions-Pins (css v$CSSV / js v$JSV)" || { echo "  ✗ Versions-Pins fehlen"; FAIL=1; }

STUCK=$(/usr/bin/sqlite3 data.db "SELECT COUNT(*) FROM collection_items WHERE json_extract(data,'\$.status')='analyzing' AND json_extract(data,'\$.created_at') < strftime('%s','now') - 1800" 2>/dev/null)
ck "Keine Scans >30min hängend"  "$STUCK" "0"
COLL=$(/usr/bin/sqlite3 data.db "SELECT COUNT(*) FROM card_prices WHERE card_key='h:f2881756ee9f84ae'" 2>/dev/null)
ck "Keine card_key-Kollision"    "$COLL" "0"
KOMMA=$(/usr/bin/sqlite3 data.db "SELECT COUNT(*) FROM drafts WHERE json_extract(data,'\$.price') LIKE '%,%' AND json_extract(data,'\$.status') NOT IN ('ended','published')" 2>/dev/null)
ck "Keine Komma-Preise in Entwuerfen" "$KOMMA" "0"
BK=$(ls backups/data-*.db 2>/dev/null | wc -l | tr -d ' ')
[ "$BK" -ge 1 ] && echo "  ✓ Backups vorhanden ($BK Slots)" || { echo "  ✗ Keine Backups!"; FAIL=1; }

# Die Unit-Tests. Bis 02.08.2026 lagen hier 85 Tests, die NIE jemand gestartet
# hat — sie können nur schützen, wenn sie bei jeder Änderung mitlaufen.
# Exitcode statt Wortsuche: „1 xfailed" (erwarteter, dokumentierter Fehlschlag)
# enthält das Wort „failed" und färbte den Smoke fälschlich rot (03.08.).
PT_ALL=$(./.venv/bin/python -m pytest tests/ -q -p no:cacheprovider 2>&1); RC=$?
PT=$(printf '%s\n' "$PT_ALL" | tail -1)
if [ $RC -eq 0 ]; then
  echo "  ✓ Unit-Tests ($PT)"
else
  echo "  ✗ Unit-Tests: $PT"; FAIL=1
fi

[ $FAIL -eq 0 ] && echo "── ALLES GRÜN ✅" || echo "── ROT — NICHT AUSLIEFERN ❌"
exit $FAIL
