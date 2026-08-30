const fs = require("fs");
const vm = require("vm");
const path = require("path");
const code = fs.readFileSync(path.join(__dirname, "../frontend/sero-detail.js"), "utf8");
const sandbox = { console, module: { exports: {} }, globalThis: {} };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.runInNewContext(code, sandbox);
const SD = sandbox.SeroDetail;

function assert(c, m) { if (!c) { console.error("FAIL", m); process.exit(1); } }

const empty = SD.notesModel({});
assert(!empty.sections.some((s) => s.id === "why"), "no why without set+year+variant");
assert(empty.facts.length === 0, "no invented facts");
assert((empty.sources || []).length === 0, "no invented sources");
assert(!/\bLuffy\b/i.test(JSON.stringify(empty)), "no luffy lore");

const partial = SD.notesModel({
  name: "Testkarte",
  category: "Pokémon",
  card: { set_name: "Base Set" },
});
assert(!partial.sections.some((s) => s.id === "why"), "why omitted without year+variant");
assert(partial.sections.some((s) => s.id === "notes"), "collector line from set");
assert(partial.heading === "Notizen", "notes heading");
assert(partial.collector === true, "tcg is collector");
assert(!partial.facts.some((f) => /Luffy|lore|legend/i.test(f.value)), "no lore facts");

const fullWhy = SD.notesModel({
  name: "Karte",
  category: "One Piece",
  card_info: { set_name: "OP-05", year: "2023", variant: "Parallel" },
});
const why = fullWhy.sections.find((s) => s.id === "why");
assert(!!why, "why present with set+year+variant");
assert(why.body.indexOf("OP-05") >= 0 && why.body.indexOf("2023") >= 0, "why from fields");
assert(!/Straw Hat|pirate|captain/i.test(why.body), "why is not lore");

const gameNotes = SD.notesModel({
  name: "Halo 2",
  category: "Games",
  card_info: { platform: "Xbox", brand: "Microsoft" },
});
assert(gameNotes.collector === false, "games use product info");
assert(gameNotes.sections.some((s) => s.heading === "Produktinformationen"), "product heading");

const scan = SD.notesModel({
  name: "Karte",
  category: "Pokémon",
  scan_description: "Echte Scan-Beschreibung vom Foto.",
});
assert(scan.sections.some((s) => s.body === "Echte Scan-Beschreibung vom Foto."), "reuse scan text");

const rich = SD.notesModel({
  name: "Karte",
  category: "Pokémon",
  card: { set_name: "Base Set", number: "4" },
  card_info: { year: "1999", variant: "Holo" },
});
const what = rich.sections.find((s) => s.id === "what");
assert(!!what, "what section from stored fields");
assert(/Base Set/.test(what.body) && /1999/.test(what.body) && /Holo/.test(what.body), "set+year+variant sentences");
assert(/Sammelkarte/.test(what.body), "kind sentence from category");
assert(!/Luffy|lore|legend|€|EUR/.test(JSON.stringify(rich)), "no lore and no invented euro");
assert(!rich.sections.some((s) => /Marktwert \d/.test(s.body || "")), "notes do not invent a price");

const src = SD.notesModel({
  name: "Karte",
  item_url: "https://www.ebay.de/itm/1",
  sources: [{ name: "PSA", url: "https://www.psacard.com/cert/1" }],
});
assert(src.sources.length >= 1, "real urls become chips");
assert(src.sources.every((s) => /^https?:\/\//.test(s.url)), "source urls are http");

const noFakeSrc = SD.notesModel({ name: "Karte", price_source: "ebay_sold" });
assert(noFakeSrc.sources.length === 0, "price_source without url is not a chip");

const z0 = SD.priceCardModel({ price_state: "unbekannt", est_value: 999, sold_comps: { n_avg: 0, sales: [] } });
assert(z0.showValue === false, "0 comps no price");
assert(z0.confidence !== "high", "0 comps not high");
assert(z0.value == null, "0 comps no euro amount");
assert(z0.hint && z0.hint.indexOf("verlässliche") >= 0, "unknown hint");

const few = SD.priceCardModel({
  price_state: "belegt",
  est_value: 50,
  sold_comps: { n_avg: 2, sales: [{ price_eur: 40 }, { price_eur: 60 }] },
});
assert(few.showValue === false, "<3 comps no suggestion");
assert(few.confidence === "mid", "2 comps mid");

const one = SD.priceConfidence({ sold_comps: { n_avg: 1, sales: [{}] }, price_state: "belegt" });
assert(one.level === "low", "1 comp low");
assert(one.dots === 1, "1 dot");

const highOk = SD.priceCardModel({
  price_state: "belegt",
  est_value: 80,
  sold_comps: {
    n_avg: 5,
    sales: [1, 2, 3, 4, 5].map((i) => ({ price_eur: 70 + i })),
  },
});
assert(highOk.showValue === true, "5 comps belegt shows price");
assert(highOk.confidence === "high", "5 current comps high");
assert(highOk.dots === 3, "3 dots");
assert(highOk.value === 80, "stored euro value");

const unknownHighBlocked = SD.priceConfidence({
  price_state: "unbekannt",
  est_value: 500,
  sold_comps: { n_avg: 8, sales: [] },
});
assert(unknownHighBlocked.level !== "high", "unknown never high");

const stale = SD.priceConfidence({
  price_state: "belegt",
  est_value: 80,
  price_reason: "BELEGE_ALT",
  sold_comps: { n_avg: 5, stale: true, sales: [] },
});
assert(stale.level === "low", "stale is low");

const view = SD.detailView({
  id: "abc",
  name: "2023 Set Card",
  category: "One Piece",
  photos: ["/api/app/citem-photo/abc/0"],
  design_photo: "/api/app/citem-design/abc/0",
  graded: { grader: "PSA", grade: "10", cert_number: "123" },
  favorite: true,
});
assert(view.images[0].kind === "front", "own photo first");
assert(view.images.some((i) => i.kind === "design"), "design included");
assert(view.grader === "PSA" && view.cert === "123", "grade fields");
assert(view.year === "2023", "year from title");
assert(view.kind === "graded", "graded kind");
assert(!JSON.stringify(view).toLowerCase().includes("courtyard"), "no courtyard");

const ebayHero = SD.detailImages({
  photos: ["/api/app/citem-photo/abc/0", "/api/app/citem-photo/abc/1"],
  design_photo: "/api/app/citem-design/abc/0",
}, { preferDesign: true });
assert(ebayHero[0].kind === "design", "ebay hero is design");
assert(ebayHero[0].url.indexOf("citem-design") >= 0, "design url first");
assert(ebayHero.some((i) => i.kind === "front"), "scan remains after design");
assert(ebayHero.filter((i) => i.kind === "design").length === 1, "design not duplicated");

const noDesign = SD.detailImages({
  photos: ["/api/app/citem-photo/abc/0"],
}, { preferDesign: true });
assert(noDesign[0].kind === "front", "fallback to scan without design");
assert(!noDesign.some((i) => i.kind === "design"), "no fake design");

const chips = SD.detailChips(view);
assert(chips.every((c) => c.value), "no empty chips");
assert(!chips.some((c) => c.label === "Figur"), "no invented character");

const kept = SD.ebayDescPlain("Zeile eins\n\nZeile zwei");
assert(kept === "Zeile eins\n\nZeile zwei", "existing breaks kept");
const numbered = SD.ebayDescPlain("Intro 1) Warum so 2) Hinweise hier 3) Fakten x");
assert(/\n/.test(numbered) && numbered.indexOf("1)") >= 0, "numbered inline split");
assert(numbered.indexOf("2)") >= 0, "second numbered block");
const blob = SD.ebayDescPlain("Das ist Satz eins. Das ist Satz zwei. Das ist Satz drei. Das ist Satz vier.");
assert(/\n/.test(blob), "sentence blob gets breaks");
assert(!/Luffy|lore|legend/i.test(blob), "desc wrap invents no lore");
const emptyNotes = SD.ebayDescPlain("", {
  name: "Testkarte",
  category: "Pokémon",
  card: { set_name: "Base Set" },
  card_info: { year: "1999", variant: "Holo" },
});
assert(/Testkarte/.test(emptyNotes), "title line from stored name");
assert(/1\)/.test(emptyNotes) && /Fakten/.test(emptyNotes), "notes numbered when empty");
assert(!/USED_VERY_GOOD|LIKE_NEW|Zustand/i.test(emptyNotes), "condition stays out of desc");
const html = SD.ebayDescHtml("Hallo Welt.\n\n1) Eins\nHinweis\n\n2) Zwei");
assert(html.indexOf("<p>") >= 0 && html.indexOf("<ol>") >= 0, "preview uses p and ol");
assert(html.indexOf("<script") < 0, "no script tags");
const xss = SD.ebayDescHtml("<img src=x onerror=alert(1)>");
assert(xss.indexOf("<img") < 0, "html escaped");
assert(xss.indexOf("&lt;img") >= 0, "lt escaped");

assert(typeof SD.listingValidation === "function", "listingValidation export");
const iss = SD.listingIssue({ field: "price", message: "Preis festlegen" });
assert(iss.fieldId === "price" && iss.blocking === true && iss.severity === "error", "issue defaults");

const jacket = {
  name: "Boss Sakko Herren Leinen Blazer Creme Weiß Sommer",
  category: "Sonstiges",
  status: "needs_review",
  identity_eval: { recognition_state: "uncertain", listing_ready: false },
  price_source: "estimate",
  price_reason: "KI_RICHTWERT",
  est_value: 40,
};
const jacketDraft = { status: "ready", title: jacket.name, price: "40", photos: ["/x"], listing: { title: jacket.name } };
const vJacket = SD.listingValidation(jacketDraft, jacket, {
  valid: true,
  issues: [{ field: "identity", message: "Identität unsicher — von Hand zuordnen oder bestätigen", code: "REVIEW" }],
});
assert(vJacket.ready === true, "everyday identity does not block");
assert(!vJacket.issues.some((i) => i.fieldId === "identity"), "no identity listing issues");
assert(!vJacket.issues.some((i) => /Identität unsicher|Stück zuerst prüfen|Identität bestätigen|Noch nicht bereit zum Veröffentlichen/.test(i.message)), "no identity wall copy");
assert(!vJacket.issues.some((i) => i.fieldId === "price" && i.message === "Bitte prüfen"), "saved listing price clears bitte pruefen");

const kiNoPrice = SD.listingValidation({ status: "ready", title: jacket.name, photos: ["/x"] }, jacket, null);
assert(kiNoPrice.issues.some((i) => i.fieldId === "price" && i.blocking === true && i.message === "Preis festlegen"), "missing listing price is red field");
assert(!kiNoPrice.issues.some((i) => i.fieldId === "price" && i.message === "Bitte prüfen"), "no yellow on missing price");

assert(SD.parseEuro("16,90") === 16.9, "DE comma");
assert(SD.parseEuro("16.90") === 16.9, "EN dot");
assert(SD.parseEuro("1.234,50") === 1234.5, "DE thousands");

const noPrice = SD.listingValidation({ status: "ready", title: "X", photos: ["/x"] }, jacket, null);
assert(noPrice.ready === false, "missing price blocks");
assert(noPrice.issues.some((i) => i.fieldId === "price" && i.blocking === true && i.message === "Preis festlegen"), "price missing is field error");

const loading = SD.listingValidation({ status: "analyzing" }, { status: "analyzing" }, null);
assert(loading.loading === true, "analyzing is loading");
assert(loading.issues.every((i) => i.type === "loading" || i.severity !== "error" || i.blocking), "no red field errors invented during load");

console.log("SERO-DETAIL-OK");
