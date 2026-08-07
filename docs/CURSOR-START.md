# Start-Prompt für Cursor AI

**So gehst du vor:** In Cursor alle drei Ordner öffnen (`~/ebay-bot`,
`~/sero-app`, `~/listo-website`), dann den Text unten als allererste Nachricht
einfügen. Die `AGENTS.md` in jedem Ordner liest Cursor danach bei jedem
Auftrag automatisch mit — du musst das nie wiederholen.

---

Hallo. Du übernimmst ein laufendes Projekt namens SERO. Antworte mir bitte
immer auf Deutsch und erklär mir Technisches in normaler Sprache — ich bin
gewerblicher eBay-Händler, kein Entwickler.

**Was SERO ist:** Eine App für Sammler und kleine Händler von Sammelkarten,
Retro-Videospielen, Manga und Comics. Der Kern: Foto machen, SERO erkennt das
Stück, ermittelt den Marktwert und macht daraus mit einem Tipp ein fertiges
eBay-Listing. Deutschland zuerst, eBay.de, Euro.

**Der Code liegt in drei Ordnern, alle drei sind Git-Repos mit sauberem Stand
vom 7. August 2026:**
- `~/ebay-bot` — Backend (Python/FastAPI), Telegram-Bot, eBay-Anbindung, Tests
- `~/sero-app/web` — die App selbst (JavaScript ohne Framework)
- `~/listo-website` — Website und Onboarding

**Bevor du irgendetwas änderst, lies bitte in dieser Reihenfolge:**
1. `~/ebay-bot/AGENTS.md` — meine unverhandelbaren Regeln und die Fallen,
   die man nur kennt, wenn man reingetreten ist
2. `~/ebay-bot/docs/IMPLEMENTATION_STATUS.md` — der wahre Stand: was fertig
   ist, was bewusst nicht gemacht wurde, was noch offen ist
3. `~/ebay-bot/docs/adr/` — drei Architektur-Entscheide mit Begründung

Danach sag mir in ein paar Sätzen, was du verstanden hast, und stell mir deine
offenen Fragen. Fang noch nicht an zu programmieren.

**Die fünf Dinge, bei denen ich empfindlich bin:**

1. **Preise dürfen nie erfunden werden.** Lieber „Wert unbekannt" als eine
   Zahl, die nicht belegt ist. Das ist die wichtigste Regel im Projekt und
   steht in Tests festgeschrieben.
2. **Nichts geht ohne meine Freigabe live** — und Achtung: Der Testmodus ist
   aktuell aus. Jedes Veröffentlichen geht wirklich zu eBay und kostet mich
   Gebühren. Beim Testen also nie ein echtes Listing erzeugen.
3. **Es laufen zwei Dauerdienste** (`com.listo.web` auf Port 3000 und
   `com.listo.bot` für Telegram). Mein Handy hängt übers WLAN am Web-Dienst.
   Starte dort bitte nie einen eigenen Server und stopp die Dienste nicht —
   dabei ist mir schon eine Vorführung geplatzt. Beim Neustarten immer daran
   denken, welchen der beiden es betrifft.
4. **Bei Bildern gilt: nur Hintergrund entfernen und gerade ziehen**, sonst
   nichts. Keine Kosmetik, kein Aufhellen, kein künstlicher Hintergrund. Das
   ist dreimal schiefgegangen und steht deshalb in Tests fest.
5. **Tests dürfen meine echte Datenbank nie anfassen.** Wie das geht, steht
   in AGENTS.md — bitte halte dich dran, ich habe dadurch schon einmal Daten
   verloren.

**Prüfen kannst du mit:**
`cd ~/ebay-bot && ./.venv/bin/python -m pytest tests/ -q` (aktuell 330 grün)
und `sh ~/ebay-bot/tests/smoke.sh` für das laufende System.

Einige Tests lesen den Quelltext und schlagen an, wenn jemand eine bewusste
Entscheidung zurückbaut. Wenn so ein Test rot wird, ist nicht der Test kaputt,
sondern die Änderung falsch.

**Als Erstes möchte ich von dir wissen:** Was ist aus deiner Sicht der
sinnvollste nächste Schritt, damit die App für erste echte Nutzer bereit ist?
Die offenen Punkte stehen in `IMPLEMENTATION_STATUS.md` — sag mir, ob du die
Reihenfolge dort teilst oder etwas anders priorisieren würdest.

Und noch etwas: Ich neige dazu, zu viel gleichzeitig zu wollen. Bremse mich,
wenn ein Vorschlag den Kern nicht voranbringt.
