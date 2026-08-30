/* Wächter für „English-only" und „Hell ist wirklich hell".
   Läuft über tests/test_ui_english_only.py. Beendet mit Code 1 und einem
   Bericht, sobald eine Lücke auftaucht.

   Drei Prüfungen:
   1. Jeder deutsche Text, der durch L() geht, hat einen STR_EN-Eintrag.
   2. Jeder statische deutsche Text in index.html hat einen STR_EN-Eintrag
      (der Beobachter in sero.js tauscht ihn nur dann aus).
   3. Keine Anthrazit-Fläche in skin-clean ohne force-light-Gegenstück.
*/
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "frontend");
const read = (f) => fs.readFileSync(path.join(root, f), "utf8");
const js = read("sero.js");
const html = read("index.html");
const clean = read("sero-clean.css");

/* ── STR_EN einlesen ── */
const start = js.indexOf("const STR_EN = {");
let depth = 0, end = -1;
for (let i = js.indexOf("{", start); i < js.length; i++) {
  if (js[i] === "{") depth++;
  else if (js[i] === "}") { depth--; if (depth === 0) { end = i; break; } }
}
const block = js.slice(start, end + 1);
const un = (s) => s.replace(/\\"/g, '"').replace(/\\n/g, "\n");
const keys = new Set();
{
  const re = /(?:^|[,{\s])"((?:[^"\\]|\\.)*)"\s*:/g;
  let m;
  while ((m = re.exec(block))) keys.add(un(m[1]));
}

const DE_WORT = /\b(der|die|das|und|nicht|kein|keine|noch|mit|wird|werden|dein|deine|ein|eine|auf|für|von|zum|zur|bei|als|aus|ist|sind|dir|du|Stück|Stücke|Entwurf|Entwürfe|Preis|Wert|Foto|Fotos|Sammlung|Verkauf|Verkaufen|Scannen|Einstellungen|Abbrechen|Speichern|Übernehmen|Zurück|Weiter|Mehr|Alle|Neu|Bild|Bilder|Karte|Karten|Konto|Anmelden|senden|Auslösen|Schließen|Profil|Zurücksetzen|Favorit|Entfernen|Mediathek|Kamera|Blitz|Werte|Preise|Titel|Übersicht|Prüfen|Bald|Telefonnummer|Benutzername)\b/i;
const istDeutsch = (s) => /[äöüÄÖÜß]/.test(s) || DE_WORT.test(s);

const fehler = [];

/* ── 0. Copy-Tabelle: der WIRKSAME Wert zählt ──
   In einem Objektliteral gewinnt der letzte Eintrag. Ein Duplikat weiter unten
   kippt sonst still eine abgesprochene Formulierung. */
{
  const wirksam = new Map();
  const re = /"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"/g;
  let m;
  while ((m = re.exec(block))) wirksam.set(un(m[1]), un(m[2]));
  const soll = JSON.parse(fs.readFileSync(path.join(__dirname, "_lang_table.json"), "utf8"));
  for (const [de, en] of Object.entries(soll)) {
    const ist = wirksam.get(de);
    if (ist !== en) {
      fehler.push(`Copy-Tabelle: ${JSON.stringify(de)} ist ${JSON.stringify(ist)}, soll ${JSON.stringify(en)}`);
    }
  }
}

/* ── 1. L()-Aufrufe ── */
for (const f of ["sero.js", "sero-profile.js", "sero-detail.js", "sero-mobile.js"]) {
  const src = f === "sero.js" ? js.slice(0, start) + js.slice(end + 1) : read(f);
  const re = /\b_?L\(\s*"((?:[^"\\]|\\.)*)"/g;
  let m;
  while ((m = re.exec(src))) {
    const s = un(m[1]);
    if (!keys.has(s) && istDeutsch(s)) fehler.push(`L() ohne STR_EN in ${f}: ${JSON.stringify(s)}`);
  }
}

/* ── 2. Statisches Markup ── */
{
  const nur = html.replace(/<!--[\s\S]*?-->/g, "").replace(/<(script|style)[\s\S]*?<\/\1>/g, "");
  const texte = new Set();
  let m;
  const tRe = />([^<>]+)</g;
  while ((m = tRe.exec(nur))) {
    const t = m[1].replace(/&nbsp;/g, " ").trim();
    if (t && /[A-Za-zÄÖÜäöüß]/.test(t)) texte.add(t);
  }
  for (const a of ["placeholder", "aria-label"]) {
    const re = new RegExp(a + '="([^"]+)"', "g");
    while ((m = re.exec(nur))) texte.add(m[1].trim());
  }
  /* Deutsche Telefonvorwahl bleibt deutsch — der Markt ist Deutschland. */
  const egal = new Set(["+49 170 1234567", "L-123456", "SERO", "eBay"]);
  for (const t of texte) {
    if (egal.has(t) || keys.has(t) || !istDeutsch(t)) continue;
    fehler.push(`index.html ohne STR_EN: ${JSON.stringify(t)}`);
  }
}

/* ── 3. Anthrazit-Inseln im Hell-Modus ── */
{
  const DUNKEL = /#(?:1c1c1e|000000|000|111111|111|2c2c2e|0a0a0a|121212|1a1a1c|18181a)\b/i;
  const regeln = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(clean))) regeln.push({ sel: m[1].trim(), body: m[2] });
  for (const r of regeln) {
    const dunkel = r.body.split(";").filter((d) => /background/.test(d) && DUNKEL.test(d));
    if (!dunkel.length) continue;
    for (const s of r.sel.split(",")) {
      const t = s.trim();
      if (!t.startsWith("html.skin-clean")) continue;
      if (t.includes("force-light") || t.includes("force-dark")) continue;
      /* Splash, Kamera und Foto-Prüfung sind absichtlich immer schwarz. */
      if (/#splash|cam-|scan-review/.test(t)) continue;
      const bare = t.replace("html.skin-clean", "").trim();
      const gedeckt = clean.includes("html.skin-clean.force-light " + bare)
        || clean.includes("html.skin-clean.force-light" + bare);
      if (!gedeckt) fehler.push(`Anthrazit ohne Hell-Regel: ${t}`);
    }
  }
}

if (fehler.length) {
  console.error("FEHLER (" + fehler.length + "):");
  for (const f of [...new Set(fehler)]) console.error("  " + f);
  process.exit(1);
}
console.log("OK — STR_EN vollständig, keine Anthrazit-Inseln im Hell-Modus.");
