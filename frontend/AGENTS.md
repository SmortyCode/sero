# SERO Frontend — Regeln für KI-Assistenten

**Antworte auf Deutsch.** Frontend im Ordner `frontend/` von `~/ebay-bot`.
Vollständige Regeln: `~/ebay-bot/AGENTS.md`.

## Fallen

1. Versions-Pins in `index.html` hochzählen (`sero.css?v=`, `sero-dark.css?v=`,
   `sero.js?v=`) — der passende Pin zur geänderten Datei.
2. Keinen eigenen Server auf Port 3000. Neustart Backend:
   `launchctl kickstart -k gui/501/com.listo.web`.

Duzen, keine Ausrufezeichen/Emojis, nie „Wir". Preise nie erfinden —
„Wert unbekannt", Listing-Preis kann manuell gesetzt werden.

Prüfen: `node --check frontend/sero.js` und `sh tests/smoke.sh`.
