# SERO — Anmeldung einrichten (Google / Telegram / Telefon)

**Stand:** 15.08.2026  
Bestehender E-Mail-/Code-Login bleibt. Zusätzlich parallele Optionen auf dem Login-Screen.

Öffentliche App-URL: `https://app.seromunich.com`  
Redirect-Basis: `PUBLIC_BASE_URL=https://app.seromunich.com`

Keine Production-Secrets in Docs oder Repo ablegen.

---

## 1. Google (OAuth)

Code ist fertig (`/auth/google/start` + `/callback`). Braucht Keys in `.env` auf Contabo (und lokal zum Testen):

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### In der Google Cloud Console

1. Projekt anlegen oder wählen → **APIs & Services → Credentials**
2. **OAuth-Client-ID** vom Typ **Webanwendung**
3. Autorisierte JavaScript-Ursprünge:
   - `https://app.seromunich.com`
   - lokal optional: `http://127.0.0.1:3000` (nur Dev, Port nicht den launchd-Dienst spoilen)
4. Autorisierte Weiterleitungs-URIs:
   - `https://app.seromunich.com/auth/google/callback`
   - lokal optional: `http://127.0.0.1:<dein-dev-port>/auth/google/callback`
5. Client-ID und Secret in Contabo-`.env` eintragen, `systemctl restart sero-web`

OAuth-Zustimmungsbildschirm: Extern, Testnutzer oder Produktion freigeben — für „jedermann“ Produktion + verifizierte App nötig, sonst nur Testnutzer.

---

## 2. Telegram Login Widget

Code: `POST /api/auth/telegram` (Hash-Prüfung laut Bot-API).  
Voraussetzung: `TELEGRAM_BOT_TOKEN` (schon vorhanden) + `LISTO_BOT_USERNAME` (Bot-Name ohne @).

### Bei @BotFather

1. Bot wählen (derselbe wie für den SERO-Bot)
2. `/setdomain` → Domain: **`app.seromunich.com`**  
   (Widget läuft in der App unter `/app/`, Host ist die App-Domain)
3. Optional `/setprivacy` nach Bedarf

Flag: `SERO_TELEGRAM_LOGIN=0` schaltet das Widget aus (Default an, wenn Token+Username da).

---

## 3. Telefon / SMS

UI und API sind vorbereitet:

- `POST /api/auth/phone/start` — Code erzeugen, SMS senden
- `POST /api/auth/phone/verify` — Code prüfen, Session setzen

### Echter Versand (kostet Geld)

Twilio (oder kompatibel):

```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM=+49…   # freigeschaltete Absendernummer
```

### Lokal / Stub ohne SMS

```
SERO_PHONE_AUTH=stub
```

Dann erscheint der Code nur in der API-Antwort (`dev_code`) bei lokaler Anfrage bzw. Stub — **nicht** als Ersatz für Produktion ohne SMS-Keys.

`SERO_PHONE_AUTH=0` schaltet Telefon komplett aus.

---

## 4. Session / Cookie

Unverändert: Cookie `listo_session`, HttpOnly, SameSite=Lax, in Produktion `Secure`, Signatur über `web_secret` in der DB. Max-Age 30 Tage.

---

## 5. Admin-Anmeldung ohne Code

Eine Mail-Adresse (Env `SERO_ADMIN_EMAIL`, Default im Code) darf OTP und PIN
überspringen: einmal ins Login-Feld, „Weiter“, normale Session. Das Frontend
kennt die Adresse nicht — nur das Backend. Konto wird angelegt, falls fehlend
(wie Signup). Andere Adressen laufen weiter über Code. Kein offenes `/app/`
ohne Anmeldung, kein zweites Nutzer-System.

```
# SERO_ADMIN_EMAIL=          # nur setzen, wenn der Default im Code nicht passt
```

---

## 6. Status-Check

```bash
curl -s https://app.seromunich.com/api/auth-providers
```

Erwartung nach Key-Eintrag z. B.:

```json
{
  "providers": ["google"],
  "google": true,
  "telegram": {"enabled": true, "bot": "EBAYSERO_bot"},
  "phone": {"enabled": true, "mode": "twilio", "sms_ready": true}
}
```
