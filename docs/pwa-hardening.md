# PWA-Härtung (Phase-1 Follow-up, 04.09.2026)

Kein Deploy in diesem Auftrag. Sysadmin entscheidet über nginx.

## HSTS

Snippet: `deploy/nginx-hsts.snippet.conf`

In die 443-Blöcke von `sero.ltd` und `app.sero.ltd` einfügen, dann
`nginx -t && systemctl reload nginx`. `preload` erst, wenn alle Hosts
dauerhaft HTTPS können.

## CSP

`web/server.py` setzt bereits:

`script-src 'self' 'unsafe-inline'` und `style-src 'self' 'unsafe-inline'`.

Die PWA hat kein Build: Inline-Handler und dynamisches CSS brauchen
`unsafe-inline`. Verschärfen erst mit Nonce, sonst bricht die App.

## Manifest

`frontend/manifest.webmanifest`: `id` (`/app/`) und `description`.
Screenshots später.

## Service Worker

Absichtlich nicht gebaut. Ein SW würde die Handy-App cachen und Pins
könnten alte Dateien ausliefern. Installierbarkeit über Manifest +
Add to Home Screen reicht. Bauen nur nach Sven-Ja.
