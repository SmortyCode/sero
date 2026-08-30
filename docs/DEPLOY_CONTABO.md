# SERO auf Contabo (öffentlich)

**Stand:** 15.08.2026  
**Host:** `169.58.182.35`

| URL | Inhalt |
|---|---|
| https://seromunich.com | **Landingpage** (statisch, `/opt/sero-landing`) — kein Shopify-Shop mehr |
| https://www.seromunich.com | gleich (www → Contabo) |
| https://app.seromunich.com | **App** (`/opt/sero`, systemd `sero-web`, nginx+Let’s Encrypt) |

**Code Mac:** `/Users/smorty/ebay-bot` · **Website-Alt (Listo):** `/opt/listo-website` (`LISTO_SITE_DIR`) weiter für Onboarding/Legal unter der App-Domain, bis umgezogen.

## Rollen

| Ort | Zweck |
|---|---|
| Mac (`com.listo.web` / `com.listo.bot`) | Lokal / Entwicklung — **Port 3000 nicht anfassen** |
| Contabo | **Testseite** (nicht „Produktion die man nie anfasst“): App `app.seromunich.com` + Landing. Nach App-Änderungen `sh scripts/deploy_contabo.sh` |

## Dienste

```bash
systemctl restart sero-web
systemctl status sero-web
journalctl -u sero-web -f

# Bot (standardmäßig AUS — gleicher Telegram-Token wie Mac → Konflikt)
systemctl start sero-bot    # nur wenn Mac-Bot gestoppt ist

systemctl reload nginx
journalctl -u nginx -f
```

Uvicorn lauscht nur auf `127.0.0.1:3000`; nginx terminiert HTTPS für die App.  
Landing: nginx liefert `/opt/sero-landing` direkt (kein uvicorn).

## Wichtig: eBay / dry_run

Maßgeblich ist `kv['dry_run']` in der jeweiligen `data.db`, nicht nur
`DRY_RUN` in `.env`.

**Stand 18.08.2026 (Abend):** Mac und Contabo stehen auf **`false`**
(JSON-Boolean). Publish geht live zu eBay — **echte Gebühren**. In der App
gibt es keinen Testmodus (kein Banner, kein Toggle). Telegram `/dryrun`
bleibt als Notfall. `scripts/deploy_contabo.sh` rsync’t `data.db` nicht und
darf dry_run **nicht auf true setzen**. Default für neue Installs: false.

Prüfen:

```
sqlite3 -readonly ~/ebay-bot/data.db "SELECT value FROM kv WHERE key='dry_run'"
ssh root@169.58.182.35 "sqlite3 -readonly /opt/sero/data.db \"SELECT value FROM kv WHERE key='dry_run'\""
```

`PUBLIC_BASE_URL=https://app.seromunich.com`, `APP_ENV=production`, `SERO_TRUST_PROXY=1`.

## Deploy vom Mac

```bash
# SSH-Key in den Agent laden (Passphrase), falls BatchMode scheitert:
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

sh scripts/deploy_contabo.sh              # App + Landing
sh scripts/deploy_contabo.sh --landing-only
```

**Wichtig:** Der Code-Deploy rsync’t **keine** `collection_photos/` und keine
`data.db`. Fehlen Bilder auf Contabo:

```bash
sh scripts/restore_photos_contabo.sh
```

Das kopiert die Mac-Fotos nach `/opt/sero/collection_photos/` und legt einen
Symlink `/Users/smorty/ebay-bot` → `/opt/sero` an (DB speichert Mac-Absolutpfade).
Mac-DB und Mac-Fotos bleiben unberührt.

Manuell (App):

```bash
rsync -az --delete   --exclude '.venv/' --exclude '__pycache__/' --exclude '.git/'   --exclude 'data.db*' --exclude 'backups/' --exclude '.env'   --exclude 'collection_photos/' --exclude 'logs/' --exclude 'tmp/'   /Users/smorty/ebay-bot/ root@169.58.182.35:/opt/sero/
ssh root@169.58.182.35 'systemctl restart sero-web'
```

Landing:

```bash
rsync -az --delete /Users/smorty/ebay-bot/landing/ root@169.58.182.35:/opt/sero-landing/
# nginx-Site: deploy/nginx-seromunich-landing.conf → sites-available + certbot
```

Firewall: 22 / 80 / 443. Certbot erneuert automatisch (App schon; Apex nach DNS).

Auth-Keys (Google/Telegram/Telefon): `docs/AUTH_SETUP.md`.

---

## DNS — Shopify → Contabo (seromunich.com)

**Stand 15.08.2026 (Nachmittag):** Apex `seromunich.com` zeigt noch auf
**Shopify** (`23.227.38.32` / `shops.myshopify.com`). Die neue Landing liegt
bereits im Repo unter `landing/` und auf Contabo unter `/opt/sero-landing`
(nach `sh scripts/deploy_contabo.sh --landing-only`) — sichtbar unter
seromunich.com erst **nach** der DNS-Umstellung unten. Bis dahin: Vorschau
über IP/Server oder nach Deploy die Dateien auf dem Host prüfen.

**Ziel:** Apex und www zeigen auf Contabo `169.58.182.35`.  
**Nicht anfassen:** MX und TXT für Google (Workspace / Mail).

### Vorher klar

Nach der A-Record-Änderung ist der **Shopify-Shop unter dieser Domain weg**.  
In Shopify die Domain ggf. **abkoppeln** (Settings → Domains), sonst verwirrende Warnungen im Shopify-Admin. Der Shop-Inhalt bei Shopify bleibt im Account, ist aber unter seromunich.com nicht mehr erreichbar.

### Schritte (Shopify DNS oder Registrar, wo die Zone liegt)

1. **A-Record `@` (seromunich.com)**  
   - Alte Shopify-IP **ändern** auf **`169.58.182.35`**
2. **AAAA `@`** (IPv6 auf Shopify)  
   - Falls vorhanden: **löschen** — sonst kann IPv6 weiter zu Shopify zeigen und die Seite „flackert“
3. **`www`**  
   - Entweder **A** `www` → `169.58.182.35`  
   - Oder **CNAME** `www` → `seromunich.com` (wenn der DNS-Anbieter Apex-CNAME erlaubt bzw. Flattening)
4. **MX / TXT (Google)** — **unverändert lassen**
5. Propagation abwarten (oft Minuten bis wenige Stunden), dann auf Contabo:

```bash
# Landing-Site + Zertifikat (einmalig, wenn DNS schon zeigt)
certbot --nginx -d seromunich.com -d www.seromunich.com
nginx -t && systemctl reload nginx
```

### Prüfen

```bash
dig +short seromunich.com A
dig +short www.seromunich.com A
# erwartet: 169.58.182.35
curl -sI https://seromunich.com/ | head
curl -sI https://app.seromunich.com/app/ | head
```

### SSH vom Mac

```bash
ssh -o BatchMode=yes root@169.58.182.35 'hostname'
```

Wenn `Permission denied (publickey)`: Key mit Passphrase in den Agent laden (`ssh-add`), nicht den Contabo-Dienst anfassen.
