/* SERO v4 — Scanner-first: Scan → Entwurf prüfen → bei eBay freigeben. */
"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  me: null, settings: null,
  items: [], stats: null, history: [], listingsMap: {},
  dash: null, sales: null,
  filter: { cat: "Alle", cats: [], cond: null, graders: [], notes: [],
    noteFrom: "", noteTo: "", langs: [], regions: [],
    valueFrom: "", valueTo: "", yearFrom: "", yearTo: "",
    fav: false, wish: false, dup: false, listed: false, draft: false, sold: false, tag: null },
  sort: "new",
  colQuery: "",
  colSearchOpen: false,
  salesQuery: "",
  salesSearchOpen: false,
  salesFilter: { cats: [], cond: null, graders: [], notes: [],
    noteFrom: "", noteTo: "", valueFrom: "", valueTo: "" },
  colPollTimer: null, scanPollTimer: null,
  detail: null,
  addFiles: [], dryRun: false, salesBucket: "draft",
  colRange: "30T",
  salesPollTimer: null,
  salesSelectMode: false,
  _bulkReviewIds: null,
  _salesError: null,
  draftBusy: {},
  scanIntent: null,          // SELL_SINGLE | SELL_BATCH | COLLECT_ONLY
  selectedDrafts: {},        // { draftId: true } — selektiver Bulk
  scanSession: null,         // persistente Queue aus /scan-session
  camShots: [],              // lokale Multi-Foto-Session vor Upload
  camUndo: null,
  camLoop: false,
  camLive: false,
  camFacing: "environment",
  camTorch: false,
  ebayPolicies: null,
  batchGroups: null,         // editierbare Gruppen vor Analyse
  batchPhotos: null,
  batchId: null,
};

/* Mobile-Stabilität (sero-mobile.js) — Fallbacks falls Skript fehlt */
const SM = (typeof window !== "undefined" && window.SeroMobile) ? window.SeroMobile : {
  store: {
    getString: (k, f = null) => { try { const v = localStorage.getItem(k); return v == null ? f : v; } catch { return f; } },
    setString: (k, v) => { try { localStorage.setItem(k, v); return true; } catch { return false; } },
    remove: (k) => { try { localStorage.removeItem(k); } catch { /* */ } },
    getJSON: (k, f = null) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : f; } catch { return f; } },
    setJSON: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; } },
  },
  makeLatestWins: () => { let g = 0; return { begin() { g += 1; const id = g; return { id, signal: undefined, isCurrent() { return id === g; } }; }, current() { return g; } }; },
  gestures: { shouldAllowTabSwipe: () => false, HORIZONTAL_SEL: ".chips", INTERACTIVE_SEL: "button,input", axisLock: () => null },
  installViewportController: () => ({ sync() {}, stop() {} }),
  errors: { push() {}, list: () => [], safeAsync: (fn) => fn },
  makeHoloController: () => ({ setWraps() {}, queue() {}, activate() {}, deactivate() {}, active: false, writeCount: 0 }),
  COL_CHUNK: 60,
};
const storeSafe = SM.store;
const dashWins = SM.makeLatestWins();
const colWins = SM.makeLatestWins();
const salesWins = SM.makeLatestWins();
const detailWins = SM.makeLatestWins();
const preflightWins = SM.makeLatestWins();
const preflightDedup = SM.makeInflightDedup ? SM.makeInflightDedup() : { run: (_k, fn) => fn() };
const holoCtl = SM.makeHoloController();
const TITLE_V = "10"; // Cache-Bust für Script-Titelbilder
const MAX_LISTING_PHOTOS = 12;
const GUEST_DRAFTS_KEY = "sero_guest_drafts_v1";

function isGuest() {
  return !state.me;
}

function isGuestItemId(id) {
  return String(id || "").startsWith("guest-");
}
/** Sichtbare DE-Bezeichnungen für Topbar/ARIA. */
const TAB_SECTION = {
  tabHome: ["portfolio", "Portfolio"],
  tabCollection: ["sammlung", "Collection"],
  tabSales: ["verkauf", "Sell"],
  tabProfile: ["profil", "Profil"],
};
function isDarkTheme() {
  const root = document.documentElement;
  if (root.classList.contains("force-dark")) return true;
  if (root.classList.contains("force-light")) return false;
  try { return matchMedia("(prefers-color-scheme: dark)").matches; } catch (_) { return false; }
}
/** Hell-Mode: kräftige (*-dark). Dark-Mode: weiche (*.png). Ein Bild je Theme. */
function titleSrc(name) {
  return isDarkTheme()
    ? `assets/titles/${name}.png?v=${TITLE_V}`
    : `assets/titles/${name}-dark.png?v=${TITLE_V}`;
}
function titlePair(name, alt, extraClass = "", w = null, h = null) {
  const cls = extraClass ? ` ${extraClass}` : "";
  // Keine pauschalen 900×340 — falsches Intrinsic-Ratio schneidet Schrift ab
  const wh = (w && h) ? ` width="${w}" height="${h}"` : "";
  return `<img class="tab-title${cls}" src="${titleSrc(name)}" alt="${esc(alt)}" data-title-name="${esc(name)}"${wh}>`;
}
function refreshThemeTitles() {
  document.querySelectorAll("img[data-title-name]").forEach((img) => {
    const name = img.getAttribute("data-title-name");
    if (!name) return;
    const next = titleSrc(name);
    if (img.getAttribute("src") !== next) img.setAttribute("src", next);
  });
}
function paintTopbarSection(tabId) {
  const el = $("topbarSection");
  if (!el) return;
  const pair = TAB_SECTION[tabId] || TAB_SECTION.tabHome;
  el.innerHTML = titlePair(pair[0], pair[1], "topbar-title");
  el.setAttribute("aria-label", pair[1]);
}

/* ═══════════════════ Icons (SF-Symbols-Stil) ═══════════════════ */

/* Icon-Wörterbuch: jeder icon("…")-Aufruf muss hier stehen.
   Fehlende Namen → stiller Fallback (question); max. einmal warnen. */
const ICON_PATHS = {
  home: '<path d="M4.5 11.5L12 4.5l7.5 7v7c0 .8-.7 1.5-1.5 1.5h-3.5v-5.5h-5V20H6c-.8 0-1.5-.7-1.5-1.5z"/>',
  camera: '<path d="M4 8.5C4 7.7 4.7 7 5.5 7h2l1.2-1.8C9 4.7 9.5 4.5 10 4.5h4c.5 0 1 .2 1.3.7L16.5 7h2c.8 0 1.5.7 1.5 1.5v8c0 .8-.7 1.5-1.5 1.5h-13C4.7 18 4 17.3 4 16.5z"/><circle cx="12" cy="12.4" r="3.1"/>',
  scanframe: '<path d="M4.5 8V6c0-.8.7-1.5 1.5-1.5h2M16 4.5h2c.8 0 1.5.7 1.5 1.5v2M19.5 16v2c0 .8-.7 1.5-1.5 1.5h-2M8 19.5H6c-.8 0-1.5-.7-1.5-1.5v-2"/><rect x="8" y="7.5" width="8" height="9" rx="1.5"/>',
  photo: '<rect x="4" y="5.5" width="16" height="13" rx="2.5"/><circle cx="9" cy="10" r="1.5" fill="currentColor" stroke="none"/><path d="M5.5 17l4-4 2.5 2.5 3.5-3.5 3 3"/>',
  stack: '<path d="M4.5 7.5L12 4l7.5 3.5L12 11z"/><path d="M4.5 12L12 15.5 19.5 12"/><path d="M4.5 16.5L12 20l7.5-3.5"/>',
  grid: '<rect x="4.5" y="4.5" width="6" height="6" rx="1"/><rect x="13.5" y="4.5" width="6" height="6" rx="1"/><rect x="4.5" y="13.5" width="6" height="6" rx="1"/><rect x="13.5" y="13.5" width="6" height="6" rx="1"/>',
  swatch: '<rect x="4.5" y="4.5" width="7" height="7" rx="1.5"/><rect x="12.5" y="7.5" width="7" height="7" rx="1.5"/><rect x="7.5" y="12.5" width="7" height="7" rx="1.5"/>',
  pencil: '<path d="M14.5 5.5l4 4L8 20H4v-4z"/><path d="M12.7 7.3l4 4"/>',
  doc: '<rect x="5.5" y="4" width="13" height="16" rx="2.5"/><path d="M9 9h6M9 12.5h6M9 16h3.5"/>',
  tag: '<path d="M4.5 10V6c0-.8.7-1.5 1.5-1.5h4l9 9c.6.6.6 1.5 0 2.1l-3.9 3.9c-.6.6-1.5.6-2.1 0z"/><circle cx="9" cy="9" r="1.3" fill="currentColor" stroke="none"/>',
  clock: '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
  trash: '<path d="M5.5 7.5h13M10 5h4M8 7.5l.6 11c0 .8.7 1.5 1.5 1.5h3.8c.8 0 1.5-.7 1.5-1.5l.6-11"/><path d="M10.3 11v5M13.7 11v5"/>',
  refresh: '<path d="M18.5 12a6.5 6.5 0 1 1-2-4.7"/><path d="M17 3.8v3.7h-3.7"/>',
  xmark: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  chevron: '<path d="M9.5 6l6 6-6 6"/>',
  chevdown: '<path d="M6 9.5l6 6 6-6"/>',
  plus: '<path d="M12 5.5v13M5.5 12h13"/>',
  minus: '<path d="M5.5 12h13"/>',
  person: '<circle cx="12" cy="8.7" r="3.4"/><path d="M5.3 19.2c1-3 3.6-4.6 6.7-4.6s5.7 1.6 6.7 4.6"/>',
  search: '<circle cx="11" cy="11" r="6.2"/><path d="M15.6 15.6L20 20"/>',
  eye: '<path d="M3.5 12S6.5 6.5 12 6.5 20.5 12 20.5 12 17.5 17.5 12 17.5 3.5 12 3.5 12z"/><circle cx="12" cy="12" r="2.6"/>',
  arrowup: '<path d="M12 19V5.5M6.5 11L12 5.5 17.5 11"/>',
  folder: '<path d="M4 7.5C4 6.7 4.7 6 5.5 6h4l1.8 2h7.2c.8 0 1.5.7 1.5 1.5v7c0 .8-.7 1.5-1.5 1.5h-13C4.7 18 4 17.3 4 16.5z"/>',
  chart: '<path d="M5 19V10M10.5 19V5.5M16 19v-7M20 19H4"/>',
  shield: '<path d="M12 4l7 2.5v5c0 4.2-3 7.4-7 8.5-4-1.1-7-4.3-7-8.5v-5z"/>',
  box: '<path d="M4.5 8L12 4.5 19.5 8v8L12 19.5 4.5 16z"/><path d="M4.5 8L12 11.5 19.5 8M12 11.5v8"/>',
  percent: '<path d="M6 18L18 6"/><circle cx="7.8" cy="7.8" r="2.2"/><circle cx="16.2" cy="16.2" r="2.2"/>',
  link: '<path d="M8 8h8.5v8.5"/><path d="M16.5 8L7 17.5"/>',
  euro: '<path d="M17 6.5a6.5 6.5 0 1 0 0 11"/><path d="M5.5 10.3h8M5.5 13.7h8"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 4.5v2M12 17.5v2M19.5 12h-2M6.5 12h-2M17.3 6.7l-1.4 1.4M8.1 15.9l-1.4 1.4M17.3 17.3l-1.4-1.4M8.1 8.1L6.7 6.7"/>',
  note: '<rect x="4.5" y="4.5" width="15" height="15" rx="3"/><path d="M8.5 9.5h7M8.5 13h7M8.5 16.5h4"/>',
  bubble: '<path d="M12 4.5c-4.7 0-8.5 3.1-8.5 7 0 2.2 1.2 4.1 3 5.4-.1 1-.5 2-1.3 2.9 1.6-.1 3.1-.6 4.3-1.5.8.2 1.6.3 2.5.3 4.7 0 8.5-3.1 8.5-7s-3.8-7.1-8.5-7.1z"/>',
  tray: '<path d="M4.5 13.5V17c0 .8.7 1.5 1.5 1.5h12c.8 0 1.5-.7 1.5-1.5v-3.5"/><path d="M12 4.5V14M8 10.5l4 4 4-4"/>',
  star: '<path d="M12 4.5l2.3 4.8 5.2.7-3.8 3.6.9 5.2L12 16.3l-4.6 2.5.9-5.2L4.5 10l5.2-.7z"/>',
  starfill: '<path fill="currentColor" stroke="none" d="M12 4.5l2.3 4.8 5.2.7-3.8 3.6.9 5.2L12 16.3l-4.6 2.5.9-5.2L4.5 10l5.2-.7z"/>',
  heart: '<path d="M12 19.5S4.5 15 4.5 9.8C4.5 7.4 6.4 5.5 8.7 5.5c1.4 0 2.6.7 3.3 1.8.7-1.1 1.9-1.8 3.3-1.8 2.3 0 4.2 1.9 4.2 4.3C19.5 15 12 19.5 12 19.5z"/>',
  sliders: '<path d="M5 8h9M17.5 8H19M5 16h2.5M11 16h8"/><circle cx="15.5" cy="8" r="2"/><circle cx="8.5" cy="16" r="2"/>',
  sort: '<path d="M8 5.5v13M8 18.5L5 15.5M8 18.5l3-3M16 18.5v-13M16 5.5l-3 3M16 5.5l3 3"/>',
  bell: '<path d="M12 4.5c-3 0-5 2.2-5 5v3l-1.5 3h13L17 12.5v-3c0-2.8-2-5-5-5z"/><path d="M10.3 18.5a1.8 1.8 0 0 0 3.4 0"/>',
  bag: '<path d="M6 8.5h12l-.9 10c-.07.85-.75 1.5-1.6 1.5H8.5c-.85 0-1.53-.65-1.6-1.5z"/><path d="M9 8.5V7a3 3 0 0 1 6 0v1.5"/>',
  globe: '<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2.2 2.2 3.2 5 3.2 8S14.2 21.8 12 20M12 4c-2.2 2.2-3.2 5-3.2 8s1 5.8 3.2 8" transform="translate(0 0)"/>',
  download: '<path d="M12 4.5V15M7.5 11L12 15.5 16.5 11"/><path d="M5 19.5h14"/>',
  crown: '<path d="M5 17h14l1-8-4.3 2.6L12 6.5 8.3 11.6 4 9z"/>',
  copies: '<rect x="7.5" y="7.5" width="12" height="12" rx="2.5"/><path d="M16.5 5H7A2.5 2.5 0 0 0 4.5 7.5V17"/>',
  ellipsis: '<circle cx="5" cy="12" r="1.7" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.7" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.7" fill="currentColor" stroke="none"/>',
  crop: '<path d="M7 3v14h14"/><path d="M3 7h14v14"/>',
  camflip: '<path d="M4.5 12a7.5 7.5 0 0 1 12.4-5.7"/><path d="M16.5 4.5v3.5h-3.5"/><path d="M19.5 12a7.5 7.5 0 0 1-12.4 5.7"/><path d="M7.5 19.5V16h3.5"/><circle cx="12" cy="12" r="2.2"/>',
  bolt: '<path d="M13 3.5L6.5 13h5l-1 7.5L17.5 11h-5z"/>',
  ticket: '<path d="M5 8.5c0-.8.7-1.5 1.5-1.5h11c.8 0 1.5.7 1.5 1.5v2a1.5 1.5 0 0 0 0 3v2c0 .8-.7 1.5-1.5 1.5h-11C5.7 17 5 16.3 5 15.5v-2a1.5 1.5 0 0 0 0-3z"/><path d="M14.5 7.5v9"/>',
  share: '<circle cx="7.5" cy="12" r="2.2"/><circle cx="16.5" cy="7.5" r="2.2"/><circle cx="16.5" cy="16.5" r="2.2"/><path d="M9.4 11l4.7-2.6M9.4 13l4.7 2.6"/>',
  expand: '<path d="M9 4.5H4.5V9M15 4.5h4.5V9M4.5 15v4.5H9M19.5 15v4.5H15"/>',
  logout: '<path d="M10 5.5H7A2.5 2.5 0 0 0 4.5 8v8A2.5 2.5 0 0 0 7 18.5h3"/><path d="M13 12h6.5M16.5 8.5L20 12l-3.5 3.5"/>',
  info: '<circle cx="12" cy="12" r="8"/><path d="M12 11v5.5M12 8.2v.2"/>',
  question: '<circle cx="12" cy="12" r="8"/><path d="M9.8 9.4a2.4 2.4 0 1 1 3.5 2.1c-.7.4-1.3 1-1.3 1.9V14"/><circle cx="12" cy="17" r=".9" fill="currentColor" stroke="none"/>',
};
const _iconMissing = new Set();
function icon(name, size = 20) {
  let body = ICON_PATHS[name];
  if (!body) {
    if (!_iconMissing.has(name)) {
      _iconMissing.add(name);
      try {
        if (typeof location !== "undefined" && /[?&]debug=1\b/.test(location.search))
          console.warn("[sero] unknown icon:", name);
      } catch (_) { /* ignore */ }
    }
    body = ICON_PATHS.question;
  }
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
}

function mountStaticIcons() {
  // Login: die drei Zeilen erklären das Produkt VOR der Anmeldung
  document.querySelectorAll(".lf-ic[data-ic]").forEach((s) => { s.innerHTML = icon(s.dataset.ic, 17); });
  const showSignup = () => {
    $("loginStep1").hidden = true;
    $("loginStep2").hidden = true;
    $("loginSignupCard").hidden = false;
    $("loginFootSignup").hidden = true;
    $("loginFootLogin").hidden = false;
    $("signupErr").textContent = "";
    $("signupEmail").focus();
  };
  const showLogin = () => {
    clearLoginPending();
    $("loginSignupCard").hidden = true;
    $("loginStep2").hidden = true;
    $("loginStep1").hidden = false;
    $("loginFootSignup").hidden = false;
    $("loginFootLogin").hidden = true;
    $("loginErr1").textContent = "";
    $("loginId").focus();
  };
  const su = $("loginSignup");
  if (su) su.onclick = showSignup;
  const back = $("loginBack");
  if (back) back.onclick = showLogin;
  /* FAB + icon set in HTML — no dynamic innerHTML needed */
  $("detailClose").innerHTML = icon("chevron", 20);
  $("detailClose").style.transform = "rotate(180deg)";
  $("detailTrash").innerHTML = icon("trash", 18);
  if ($("detailShare")) $("detailShare").innerHTML = icon("share", 18);
  if ($("detailMore")) $("detailMore").innerHTML = icon("ellipsis", 18);
  $("emptyAdd").innerHTML = icon("camera", 18) + "<span>" + L("Artikel fotografieren") + "</span>";
  if ($("scanHeroIcon")) $("scanHeroIcon").innerHTML = icon("scanframe", 44);
  if ($("btnScanNow")) $("btnScanNow").innerHTML = icon("camera", 18) + "<span>" + L("Artikel fotografieren") + "</span>";
  if ($("btnScanGallery")) $("btnScanGallery").innerHTML = icon("photo", 16) + "<span>" + L("Aus Fotos") + "</span>";
  const tabIcons = { tabHome: "home", tabCollection: "stack", tabSales: "tag", tabProfile: "person" };
  document.querySelectorAll(".tab").forEach((t) => {
    const tic = t.querySelector(".tic");
    if (tic) tic.innerHTML = icon(tabIcons[t.dataset.tab], 24);
  });
  if ($("settingsBack")) $("settingsBack").innerHTML = icon("chevron", 20);
  // Bewegung & Glas aus gespeicherter Wahl
  try {
    if (storeSafe.getString("sero_motion") === "reduced")
      document.documentElement.classList.add("reduced-effects");
  } catch (_) { /* */ }
}

/* ═══════════════════ Basis ═══════════════════ */

/** Datensparsame Funnel-Events — keine Produktinhalte, keine Fotos. */
function trackFunnel(name, dims) {
  try {
    const payload = { e: String(name || ""), t: Date.now() };
    if (dims && typeof dims === "object") {
      for (const k of ["mode", "status", "ms", "code"]) {
        if (dims[k] != null && dims[k] !== "") payload[k] = dims[k];
      }
    }
    const q = state._funnel = state._funnel || [];
    q.push(payload);
    if (q.length > 40) q.splice(0, q.length - 40);
  } catch (_) { /* */ }
}

function toast(msg, ic = null, action = null) {
  msg = L(msg);
  let t = $("toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); }
  t.innerHTML = (ic ? `<span style="color:var(--tint);display:grid">${icon(ic, 17)}</span>` : "")
    + "<span></span>" + (action ? `<button class="toast-act">${esc(L(action.label))}</button>` : "");
  t.querySelector("span:last-of-type").textContent = msg;
  if (action) t.querySelector(".toast-act").onclick = () => { t.classList.remove("show"); action.fn(); };
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), action ? 6000 : 3000);
}

/* Externe Seite öffnen. Bewusst ein echter Link statt window.open(…, features):
   In der installierten PWA schluckt der Popup-Schutz das Fenster, der Tipp
   wirkt tot oder landet auf einer leeren Startseite. Kommt kein Fenster
   zustande, sagt SERO das, statt still nichts zu tun. */
function openExternalUrl(href, hinweis) {
  if (!href) return false;
  try {
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    return true;
  } catch (_) {
    toast(hinweis || L("Seite konnte nicht geöffnet werden."));
    return false;
  }
}

function askRemoveItem(item) {
  if (!item || !item.id) return;
  confirmSheet(L("Stück entfernen?"), L("Das Stück verlässt die Sammlung. Du kannst das gleich rückgängig machen."), L("Entfernen"), true)
    .then((ok) => { if (ok) removeItemWithUndo(item); });
}

/* ── Entfernen mit Rückgängig (nach Confirm-Sheet) ──
   Sofort auf dem Server löschen (Papierkorb). Früher: 6 s warten — in der
   Zeit hat SSE/loadCollection das Stück wieder eingeblendet, der Toast
   log „entfernt“ war Lüge. Undo stellt aus _trash wieder her. */
function removeItemWithUndo(item) {
  if (!item || !item.id) return;
  if (isGuestItemId(item.id) || item.guest) {
    const prev = guestDraftRows();
    setGuestDraftRows(prev.filter((r) => r.id !== item.id));
    applyGuestItems();
    dismissSheetNow();
    if (state.detail && state.detail.mode === "item" && state.detail.id === item.id) {
      closeDetail({ instant: true, skipReload: true });
    }
    renderCollection();
    toast("Aus Sammlung entfernt", "trash", {
      label: "Rückgängig",
      fn: () => {
        setGuestDraftRows([prev.find((r) => r.id === item.id), ...guestDraftRows()].filter(Boolean));
        applyGuestItems();
        renderCollection();
        toast("Wiederhergestellt", "check");
      },
    });
    return;
  }
  state.pendingDeletes = state.pendingDeletes || {};
  if (state.pendingDeletes[item.id]) return;
  state.pendingDeletes[item.id] = { started: Date.now(), status: "inflight" };
  dismissSheetNow();
  if (state.detail && state.detail.mode === "item" && state.detail.id === item.id) {
    closeDetail({ instant: true, skipReload: true });
  }
  state.items = (state.items || []).filter((i) => i.id !== item.id);
  if (state.stats && state.stats.count != null) {
    state.stats.count = Math.max(0, Number(state.stats.count) - 1);
  }
  try {
    const cached = cache.get("col");
    if (cached && cached.items) {
      cached.items = cached.items.filter((i) => i.id !== item.id);
      if (cached.stats && cached.stats.count != null) {
        cached.stats.count = Math.max(0, Number(cached.stats.count) - 1);
      }
      cache.set("col", cached);
    }
  } catch (_) { /* */ }
  state._colSig = null;
  renderCollection();
  const _ts = $("tabScan"); if (_ts && !_ts.hidden) renderScan();

  const undoGone = { done: false };
  const clearPending = () => {
    if (state.pendingDeletes) delete state.pendingDeletes[item.id];
  };
  let inflight = true;

  post(`/api/app/collection/item/${item.id}/delete`)
    .then(() => {
      inflight = false;
      const slot = state.pendingDeletes && state.pendingDeletes[item.id];
      if (slot) slot.status = "done";
      if (undoGone.done) clearPending();
    })
    .catch((e) => {
      inflight = false;
      if (undoGone.done) { clearPending(); return; }
      clearPending();
      loadCollection();
      toast(e.message || L("Entfernen fehlgeschlagen"));
    });

  const timer = setTimeout(() => {
    undoGone.done = true;
    if (!inflight) clearPending();
  }, 8000);

  toast("Aus Sammlung entfernt", "trash", {
    label: "Rückgängig",
    fn: () => {
      if (undoGone.done) return;
      undoGone.done = true;
      clearTimeout(timer);
      post(`/api/app/collection/item/${item.id}/restore`)
        .then(() => {
          clearPending();
          loadCollection();
          toast("Wiederhergestellt", "check");
        })
        .catch((e) => {
          clearPending();
          loadCollection();
          toast(e.message || L("Wiederherstellen fehlgeschlagen"));
        });
    },
  });
}

/* ── Zeit-Bilanz (Paywall): Zehntel-Stunden-Form ── */
const dur = (s) => {
  if (s >= 3600) {
    // Zehntel-Stunden: sonst stünde „1 Stunde gespart statt 1 Stunde" da
    const h = Math.round(s / 360) / 10;
    return h === 1 ? L("1 Stunde") : LF("{0} Stunden", String(h).replace(".", ","));
  }
  const m = Math.max(1, Math.round(s / 60));
  return m === 1 ? L("1 Minute") : LF("{0} Minuten", m);
};
/* Kurzform für die Balken — „1,5 h" statt „1,5 Stunden" (bricht sonst um) */
const durShort = (s) => s >= 3600
  ? LF("{0} h", String(Math.round(s / 360) / 10).replace(".", ","))
  : LF("{0} Min", Math.max(1, Math.round(s / 60)));

/* SERO-Effekt: klare Std/Min ohne Dezimalangaben */
function formatDuration(sec) {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h === 0) return m === 1 ? L("1 Min") : LF("{0} Min", m);
  if (m === 0) return h === 1 ? L("1 Std") : LF("{0} Std", h);
  const hs = h === 1 ? L("1 Std") : LF("{0} Std", h);
  const ms = m === 1 ? L("1 Min") : LF("{0} Min", m);
  return `${hs} ${ms}`;
}

function openImpactSheet(impact) {
  const n = impact.successful_scans || 0;
  const avg = impact.avg_analysis_seconds;
  const avgLine = (avg != null && n >= 3)
    ? `<p class="impact-sheet-avg">${esc(L("Ø technische Analysezeit"))}: ${esc(formatDuration(avg))} — ${esc(L("läuft im Hintergrund"))}</p>`
    : "";
  openSheet("Dein SERO-Effekt", "", `
    <p class="impact-sheet-lead">${esc(L("SERO rechnet mit 15 Minuten von Hand und 2 Minuten mit SERO — je erfolgreichem Scan. Von Hand: bestimmen, echte Verkaufsbelege prüfen, Foto vorbereiten, Titel schreiben und eBay-Pflichtfelder setzen. Mit SERO: fotografieren, Ergebnis prüfen und freigeben. Die technische Analyse im Hintergrund zählt nicht als deine Arbeitszeit."))}</p>
    <div class="impact-sheet-rows">
      <div><span>${esc(L("Von Hand"))}</span><b class="tnum">${esc(formatDuration(impact.manual_seconds))}</b></div>
      <div><span>${esc(L("Mit SERO"))}</span><b class="tnum">${esc(formatDuration(impact.sero_seconds))}</b></div>
      <div><span>${esc(L("Gespart"))}</span><b class="tnum">${esc(formatDuration(impact.saved_seconds))}</b></div>
    </div>
    ${avgLine}`,
    () => closeSheet(), "Berechnung schließen");
}

const PREMIUM_URL = "https://seromunich.com/premium";
const pctOf = (now, before) => {
  if (now == null || before == null || !isFinite(now) || !isFinite(before) || before === 0) return null;
  return ((now - before) / Math.abs(before)) * 100;
};

function openPaywall() {
  const s = state.settings || {};
  const used = s.scans_used || 0, lim = s.scans_limit || 50;
  const feat = (ic, txt) => `<div class="pw-row">${icon(ic, 16)}<span>${L(txt)}</span></div>`;
  const left = Math.max(0, lim - used);
  openSheet(left > 0 ? LF("Noch {0} Gratis-Scans", left) : L("Deine Gratis-Scans sind aufgebraucht"),
    L("Mit SERO Premium scannst du ohne Limit weiter."),
    `<div class="pw-bar"><i style="width:${Math.min(100, Math.round(used / Math.max(1, lim) * 100))}%"></i></div>
     <p class="pw-count tnum">${used} / ${lim} ${L("Scans genutzt")}</p>
     <p class="pw-math-t">${L("Die ehrliche Rechnung")}</p>
     <p class="pw-math-s">${L("100 Karten listen — einmal von Hand, einmal mit SERO.")}</p>
     <div class="pw-math">
       <div class="pwm"><h4>${L("Von Hand")}</h4><div class="v tnum">~25 ${L("Std")}</div>
         <p>${L("Karte bestimmen, verkaufte Angebote durchsehen, Foto zuschneiden, Titel und Pflichtfelder setzen — 15 Minuten pro Stück.")}</p></div>
       <div class="pwm win"><h4>${L("Mit SERO")}</h4><div class="v tnum">~200 ${L("Min")}</div>
         <p>${L("Fotografieren, Ergebnis prüfen, freigeben — 2 Minuten pro Stück. 100 Karten, 200 Minuten.")}</p></div>
     </div>
     <p class="pw-foot">${L("Von Hand 15 Minuten je Stück (bestimmen, Marktwert, Foto, Titel und Pflichtfelder). Mit SERO 2 Minuten — nicht die Scan-Dauer im Hintergrund, sondern deine aktive Zeit inklusive Hinlegen, Prüfen und Freigeben.")}</p>
     <div class="pw-feats">
       ${feat("scanframe", "Unbegrenzte Scans")}
       ${feat("bell", "Preisalarme für deine Stücke")}
       ${feat("chart", "Portfolio-Verlauf & Statistiken")}
       ${feat("shield", "Cloud-Backup deiner Sammlung")}
     </div>`,
    () => { window.open(PREMIUM_URL, "_blank"); closeSheet(); },
    L("SERO Premium holen"));
}
/* Fehler vom Server (402) automatisch in die Paywall umleiten */
function handleScanError(e, fallback) {
  if (e && e.status === 402) {
    // Die Fotos MÜSSEN liegen bleiben: closeSheet räumt die Ablage sonst leer,
    // und der Nutzer steht vor der Paywall — seine Aufnahmen wären weg.
    state.stageKeep = true;
    closeSheet(); openPaywall(); return true;
  }
  if (fallback) fallback(e);
  return false;
}

/* ── Wow-Moment: das frisch gescannte Stück mit seinem Marktwert ── */
/* Läuft gerade ein Foto-Vorgang? Dann ist JEDES Overlay eine Störung:
   Sven tippt „Rückseite fotografieren", ist im Kamera-Dialog — und in dem
   Moment wird die vorherige Analyse fertig. Das Ergebnis legte sich über
   alles und riss den Vorgang mit. */
function fotoVorgangLaeuft() {
  // „Weiteres Foto" verfällt nach zwei Minuten: kehrt jemand nie aus der
  // Kamera zurück (App weggelegt), darf das gemerkte Ergebnis nicht ewig
  // liegen bleiben.
  if (state.stageResume && Date.now() - (state.stageResumeTs || 0) > 120000) {
    state.stageResume = false;
  }
  return !!(state.stageOpen || state.stageResume || stageUpload._busy
            || (!$("sheet").hidden && !$("sheet").classList.contains("closing")));
}

/* Ergebnis parken statt verwerfen — es kommt, sobald der Weg frei ist. */
function zeigeErgebnisWennFrei() {
  if (!state.wartendesErgebnis || fotoVorgangLaeuft()) return;
  const item = state.wartendesErgebnis;
  state.wartendesErgebnis = null;
  showScanResult(item);
}

function showScanResult(item) {
  if (fotoVorgangLaeuft()) {
    // Nur das zuletzt fertige Stück merken — wer zehn Karten scannt, will
    // nicht zehn Pop-ups nacheinander wegtippen.
    state.wartendesErgebnis = item;
    return;
  }
  // Ein gescheiterter Scan hat sich bisher mit grünem Haken und „Erkannt"
  // gefeiert — die Karte war leer, der Wert fehlte, und der Nutzer musste
  // selbst darauf kommen, dass nichts geklappt hat.
  if (item.status === "error") return showScanFailed(item);
  const needsReview = item.status === "needs_review" || item.status === "uncertain";
  const sub = [item.category, item.card && item.card.set_name,
    item.card && item.card.rarity].filter(Boolean).join(" · ");
  const photo = thumb(item.photos && item.photos[0], 720) || (item.card && item.card.image);
  const val = item.est_value !== null && item.est_value !== undefined ? item.est_value : null;
  const reviewQ = item.review_question
    || ((item.identity_eval && item.identity_eval.blocking_texts) || [])[0]
    || L("Bitte Angaben prüfen");
  const el = document.createElement("div");
  el.className = "party scanres";
  el.innerHTML = `
    <div class="party-card res-card">
      <div class="res-grip"></div>
      <div class="res-badge ${needsReview ? "fail" : ""}">${icon(needsReview ? "question" : "check", 15)}<span>${L(needsReview ? "Bitte prüfen" : "Erkannt")}</span></div>
      ${photo ? `<div class="res-photo"><img src="${esc(photo)}" alt=""></div>`
              : `<div class="res-photo">${MONO_PH}</div>`}
      <h2 class="res-name">${esc(item.name || L("Neues Stück"))}</h2>
      ${sub ? `<p class="res-sub">${esc(sub)}</p>` : ""}
      ${needsReview ? `<p class="res-sub">${esc(reviewQ)}</p>` : ""}
      <div class="res-val tnum">${val === null ? (item.status === "ready" || needsReview ? L("Wert unbekannt") : L("Wert wird noch ermittelt")) : ""}</div>
      ${val === null
        ? (item.status === "ready" || needsReview
           ? `<div class="res-src"><span>${L("Kein belegter Marktwert — trag deinen Preis beim Listen selbst ein")}</span></div>`
           : "<div style='height:10px'></div>")
        : (item.price_source === "estimate" || item.price_reason === "KI_RICHTWERT"
           ? `<div class="res-src"><span>${L("KI-Richtwert — bitte prüfen, Preis ist änderbar")}</span></div>`
           : (item.price_label
              ? `<div class="res-src"><span>${esc(item.price_label)}</span></div>`
              : "<div style='height:10px'></div>"))}
      <div class="party-actions">
        ${state.scanIntent === "COLLECT_ONLY"
          ? `<button class="btn-primary" id="resOpen">${L("In Sammlung öffnen")}</button>
             <button class="btn-secondary" id="resNext">${L("Weiter scannen")}</button>`
          : `<button class="btn-primary" id="resList">${L("Entwurf prüfen")}</button>
             <button class="btn-secondary" id="resNext">${L("Weiter scannen")}</button>
             <button class="btn-secondary" id="resOpen">${L("Nur in Sammlung behalten")}</button>`}
      </div>
    </div>`;
  document.body.appendChild(el);
  // Der Wert kommt bei 550 ms — zusammen mit Lichtstoß und Haptik. Vorher stand
  // er von der ersten Millisekunde an da und die Karte hatte keine Dramaturgie.
  const ruhig = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (val !== null) {
    const zeigeWert = () => countUp(el.querySelector(".res-val"), "scanres_" + item.id, val, true);
    if (ruhig) zeigeWert();
    else {
      el._t1 = setTimeout(() => { zeigeWert(); haptic("medium"); }, 550);
      el._t0 = setTimeout(() => haptic("light"), 120);   // Foto ist da
    }
  }
  const close = (then) => {
    clearTimeout(el._t0); clearTimeout(el._t1);   // sonst vibriert es ins Leere
    el.classList.add("out");
    setTimeout(() => { el.remove(); if (then) then(); }, 300);
  };
  const resList = el.querySelector("#resList");
  if (resList) resList.onclick = (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    // Sofort schließen — sonst liegt party (z=70) über dem Sheet und der Tipp wirkt tot
    clearTimeout(el._t0); clearTimeout(el._t1);
    el.remove();
    state.scanIntent = null;
    try {
      openQuickListSheet(item);
    } catch (e) {
      toast(L("Listen fehlgeschlagen") + " — " + (e && e.message ? e.message : e), "xmark");
    }
  };
  const resOpen = el.querySelector("#resOpen");
  if (resOpen) resOpen.onclick = (ev) => {
    ev.stopPropagation();
    clearTimeout(el._t0); clearTimeout(el._t1);
    el.remove();
    state.scanIntent = null;
    openItemDetail(item.id);
  };
  el.querySelector("#resNext").onclick = (ev) => {
    ev.stopPropagation();
    clearTimeout(el._t0); clearTimeout(el._t1);
    el.remove();
    startScanMode("SELL_SINGLE");
  };
  el.onclick = (e) => { if (e.target === el) { clearTimeout(el._t0); clearTimeout(el._t1); el.remove(); } };
}

/* Ehrliche Variante, wenn die Erkennung nicht geklappt hat: sagen was war,
   und den einen Knopf anbieten, der weiterhilft. */
function showScanFailed(item) {
  const photo = thumb(item.photos && item.photos[0], 720);
  const el = document.createElement("div");
  el.className = "party scanres";
  el.innerHTML = `
    <div class="party-card res-card">
      <div class="res-grip"></div>
      <div class="res-badge fail">${icon("xmark", 15)}<span>${L("Nicht erkannt")}</span></div>
      ${photo ? `<div class="res-photo"><img src="${esc(photo)}" alt=""></div>`
              : `<div class="res-photo">${MONO_PH}</div>`}
      <h2 class="res-name">${esc(item.name || L("Stück nicht erkannt"))}</h2>
      <p class="res-sub">${esc(item.error || L("Die Analyse ist fehlgeschlagen. Meist hilft ein Foto mit mehr Licht und ohne Spiegelung."))}</p>
      <div class="party-actions">
        <button class="btn-primary" id="resRetry">${L("Nochmal versuchen")}</button>
        <button class="btn-secondary" id="resOpen">${L("Zum Stück")}</button>
      </div>
    </div>`;
  document.body.appendChild(el);
  const close = (then) => {
    el.classList.add("out");
    setTimeout(() => { el.remove(); if (then) then(); }, 300);
  };
  el.querySelector("#resRetry").onclick = async () => {
    const b = el.querySelector("#resRetry");
    b.disabled = true; b.textContent = L("Starte neu …");
    try {
      await post(`/api/app/collection/item/${item.id}/rescan`);
      state.watchNew = item.id;
      close(() => { loadCollection(); startScanMode("SELL_SINGLE"); });
    } catch (e) {
      b.disabled = false; b.textContent = L("Nochmal versuchen");
      toast(e.message);
    }
  };
  el.querySelector("#resOpen").onclick = () => close(() => openItemDetail(item.id));
  el.onclick = (e) => { if (e.target === el) close(); };
}

/* ── Erfolgs-Moment: Listing ist live ── */
function celebrate(d) {
  const el = document.createElement("div");
  el.className = "party";
  el.innerHTML = `
    <div class="party-card">
      <span class="party-ring">${icon("check", 34)}</span>
      <h2>${L("Live auf eBay")}</h2>
      <p>${esc(d.title || "")}</p>
      <div class="party-price">${esc(eur(d.price) || "")} €</div>
      <div class="party-actions">
        ${d.item_url ? `<a class="btn-primary" href="${esc(d.item_url)}" target="_blank">${L("Auf eBay ansehen")}</a>` : ""}
        <button class="btn-secondary" id="partyDone">${L("Fertig")}</button>
      </div>
    </div>`;
  document.body.appendChild(el);
  haptic("success");
  el.querySelector("#partyDone").onclick = () => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 300);
  };
}

/* ── Pull-to-Refresh (Geste auf Handy; ↻-Knopf bleibt) ── */
function attachPTR(scrollEl, onRefresh) {
  const ind = document.createElement("div");
  ind.className = "ptr";
  ind.innerHTML = `<span class="ptr-spin" aria-hidden="true"></span>`;
  scrollEl.parentElement.prepend(ind);
  let startY = 0, pulling = false, dist = 0, busy = false;
  scrollEl.addEventListener("touchstart", (e) => {
    if (scrollEl.scrollTop <= 0 && !busy) { startY = e.touches[0].clientY; pulling = true; dist = 0; }
  }, { passive: true });
  scrollEl.addEventListener("touchmove", (e) => {
    if (!pulling) return;
    dist = e.touches[0].clientY - startY;
    if (dist > 8 && scrollEl.scrollTop <= 0) {
      ind.style.opacity = Math.min(1, dist / 85);
      ind.style.transform = `translate(-50%, ${Math.min(dist / 2.2, 54)}px)`;
      // Spürbare Schwelle: ab hier löst Loslassen wirklich aus
      const scharf = dist > 85;
      if (scharf !== ind._scharf) {
        ind._scharf = scharf;
        ind.classList.toggle("armed", scharf);
        if (scharf) haptic("soft");
      }
    }
  }, { passive: true });
  scrollEl.addEventListener("touchend", async () => {
    if (pulling && dist > 85) {
      busy = true;
      ind.classList.add("go");
      try { await onRefresh(); } finally {
        busy = false;
        ind.classList.remove("go");
        ind.style.opacity = 0; ind.style.transform = "";
      }
    } else { ind.style.opacity = 0; ind.style.transform = ""; }
    ind._scharf = false; ind.classList.remove("armed");
    pulling = false;
  });
}

/* ── Preisquellen in einfachen Worten ── */
const SOURCE_INFO = {
  cardmarket: ["Cardmarket-Trend", "Cardmarket ist Europas größter Marktplatz für Sammelkarten. Der Trend-Preis ist der geglättete Durchschnitt der tatsächlichen Verkaufspreise der letzten Tage — die verlässlichste Zahl für den aktuellen Wert deiner Karte. SERO aktualisiert ihn automatisch."],
  ebay: ["eBay-Median", "SERO sucht aktuelle eBay-Sofortkauf-Angebote für vergleichbare Stücke, entfernt Ausreißer und nimmt den mittleren Preis (Median). Das zeigt, wofür vergleichbare Stücke gerade angeboten werden — Verkaufspreise können leicht darunter liegen."],
  estimate: ["KI-Richtwert", "Grobe Einschätzung für Alltagsprodukte ohne belastbare Verkaufsbelege. Bitte den Preis prüfen und bei Bedarf manuell ändern. Bei Sammelkarten vergibt SERO solche Werte nicht."],
  scryfall: ["Cardmarket (Scryfall)", "Der aktuelle Cardmarket-Preis dieser Magic-Karte, bezogen über die freie Scryfall-Datenbank."],
  ygoprodeck: ["Cardmarket (YGOPRODeck)", "Der aktuelle Cardmarket-Preis dieser Yu-Gi-Oh-Karte, bezogen über die freie YGOPRODeck-Datenbank."],
  listing: ["Listing-Preis", "Dieses Stück wurde aus deinen eBay-Listings importiert — als Wert dient dein Angebotspreis, bis SERO eine echte Marktquelle findet (Preis aktualisieren antippen)."],
  manual: ["Dein Preis", "Von dir manuell gesetzter Portfolio-Wert. Tippe auf den Aktualisieren-Knopf, wenn du wieder den Marktwert von SERO nutzen willst."],
  ebay_sold: ["Ø letzte eBay-Verkäufe", "SERO nimmt die zuletzt tatsächlich verkauften eBay-Angebote genau dieses Stücks (Grader streng getrennt, max. 90 Tage alt) und mittelt die letzten drei. Nicht was verlangt wird — was wirklich bezahlt wurde. Die Belege stehen mit Link darunter."],
  ebay_eu: ["eBay-DE-Markt", "Der mittlere Preis der aktuellen deutschen eBay-Angebote für genau dieses Stück (Grader getrennt), konservativ 12 % unter Angebotsniveau. Greift, wenn es noch keine belegten Verkäufe gibt."],
  tcgplayer: ["TCGplayer-Markt (US)", "Der aktuelle Marktwert auf TCGplayer, dem größten US-Kartenmarktplatz, umgerechnet zum EZB-Kurs."],
  pricecharting: ["PriceCharting-Verkäufe", "Verkaufsbasierter Marktwert von PriceCharting (US) — kennt Grading-Stufen (PSA/CGC/BGS/WATA) separat. SERO nutzt ihn, wenn keine frischen eBay-Verkäufe vorliegen."],
  pricecharting_weak: ["Zuordnung unsicher", "Für dieses Stück konnte SERO keinen eindeutig passenden Markt-Eintrag finden — der Wert ist nur eine grobe Orientierung. Tippe auf „Falsche Karte? Richtige suchen“, um die Zuordnung zu korrigieren."],
};

/* Ohne Zeitgrenze wartet fetch im Mobilfunk-Funkloch endlos: der Spinner dreht
   sich weiter, der Knopf bleibt gesperrt, und die App wirkt eingefroren, obwohl
   nichts kaputt ist. Uploads dürfen länger dauern als normale Abfragen. */
async function api(path, opts = {}) {
  const { timeout, signal: outerSignal, ...rest } = opts;
  const ms = timeout ?? (rest.body instanceof FormData ? 180000 : 25000);
  const ctrl = new AbortController();
  const stop = setTimeout(() => ctrl.abort(), ms);
  let onOuterAbort = null;
  if (outerSignal) {
    if (outerSignal.aborted) ctrl.abort();
    else {
      onOuterAbort = () => ctrl.abort();
      outerSignal.addEventListener("abort", onOuterAbort, { once: true });
    }
  }
  let resp;
  try {
    // "include" verhält sich same-origin exakt wie "same-origin" — und trägt
    // das Session-Cookie auch dann, wenn die App-Hülle cross-origin lädt.
    resp = await fetch(url(path), { credentials: "include", ...rest, signal: ctrl.signal });
  } catch (e) {
    const superseded = !!(outerSignal && outerSignal.aborted && e.name === "AbortError");
    if (superseded) {
      throw Object.assign(new Error("superseded"), { status: 0, superseded: true, offline: false });
    }
    throw Object.assign(new Error(
      e.name === "AbortError"
        ? L("Das hat zu lange gedauert. Versuch es noch einmal.")
        : L("Keine Verbindung. Prüf dein Netz und versuch es noch einmal.")),
      { status: 0, offline: true });
  } finally {
    clearTimeout(stop);
    if (outerSignal && onOuterAbort) outerSignal.removeEventListener("abort", onOuterAbort);
  }
  let data = {};
  try { data = await resp.json(); } catch { /* leer */ }
  if (!resp.ok) throw Object.assign(new Error(data.error || `${L("Fehler")} ${resp.status}`), { status: resp.status });
  return data;
}
/* Jedes URL.createObjectURL hält das komplette Foto im Speicher, bis es
   ausdrücklich freigegeben wird. Bei 20 Fotos à 3–4 MB pro Stapel läuft das
   Handy nach ein paar Runden voll und iOS wirft die App raus. Nach dem Laden
   braucht das <img> die URL nicht mehr — also sofort zurückgeben. */
function blobThumbs(files) {
  return files.map((f) => `<img data-blob="1" src="${URL.createObjectURL(f)}" alt="">`).join("");
}
function freeBlobs(root) {
  (root || document).querySelectorAll('img[data-blob="1"]').forEach((im) => {
    const frei = () => { URL.revokeObjectURL(im.src); im.removeAttribute("data-blob"); };
    if (im.complete) frei();
    else im.addEventListener("load", frei, { once: true });
    im.addEventListener("error", frei, { once: true });
  });
}

/** Quadratisches Avatar-Preview (max. size px) — verhindert Riesenfotos im Sheet */
async function squareImageBlob(file, size = 512) {
  const img = new Image();
  const url = URL.createObjectURL(file);
  try {
    await new Promise((ok, err) => { img.onload = ok; img.onerror = err; img.src = url; });
  } finally {
    URL.revokeObjectURL(url);
  }
  const side = Math.min(img.width, img.height) || 1;
  const sx = (img.width - side) / 2, sy = (img.height - side) / 2;
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  cv.getContext("2d").drawImage(img, sx, sy, side, side, 0, 0, size, size);
  const blob = await new Promise((res) => cv.toBlob(res, "image/jpeg", 0.88));
  if (!blob) throw new Error(L("Foto konnte nicht geladen werden"));
  return blob;
}

const post = (path, body, opts = {}) => api(path, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}),
  ...opts,
});

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const eur = (v) => (v === null || v === undefined || v === "" ? null : String(v).replace(".", ","));
const money = (v) => v === null || v === undefined ? "—"
  : Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
/* Odometer (Apple-Wallet-Look): jede Ziffernspalte rollt von der alten zur
   neuen Ziffer. Fällt auf direktes Setzen zurück, wenn sich die Zahlen-Form
   ändert (andere Stellenzahl) oder Bewegung reduziert werden soll. */
const ODO_ROW = 1.08;   // Zeilenhöhe der Ziffernspalte in em (muss zum CSS passen)
const ODO_DIGITS = Array.from({ length: 10 }, (_, d) => `<span>${d}</span>`).join("");
function countUp(el, key, to, vonNull = false) {
  if (!el || to === null || to === undefined) return;
  const bekannt = state.anim?.[key];
  (state.anim = state.anim || {})[key] = to;
  const txt = money(to);
  // vonNull: Erstanzeige soll rollen (Scan-Ergebnis!). Startbild hat dieselbe
  // Form wie das Ziel, nur mit Nullen — sonst greift die Längen-Prüfung unten
  // nicht und die wichtigste Zahl der App erscheint einfach schlagartig.
  const old = bekannt !== undefined ? money(bekannt)
            : vonNull ? txt.replace(/\d/g, "0") : txt;
  const rollable = txt !== old && old.length === txt.length
    && [...txt].every((c, i) => /\d/.test(c) === /\d/.test(old[i]))
    && !matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!rollable) { el.textContent = txt; return; }
  el.innerHTML = [...txt].map((ch, i) => /\d/.test(ch)
    ? `<span class="odc"><span class="odr" style="transform:translateY(-${(Number(old[i]) * ODO_ROW).toFixed(2)}em)">${ODO_DIGITS}</span></span>`
    : `<span class="ods">${esc(ch)}</span>`).join("");
  const targets = [...txt].filter((c) => /\d/.test(c));
  requestAnimationFrame(() => requestAnimationFrame(() => {
    el.querySelectorAll(".odr").forEach((r, n) => {
      r.style.transform = `translateY(-${(Number(targets[n]) * ODO_ROW).toFixed(2)}em)`;
    });
  }));
}

/* Bilder sanft einblenden, sobald sie geladen sind */
function fadeImgs(root) {
  (root || document).querySelectorAll("img:not(.ld)").forEach((img) => {
    if (img.complete && img.naturalWidth) img.classList.add("ld");
    else {
      img.addEventListener("load", () => img.classList.add("ld"), { once: true });
      // Toter Link (z. B. abgelaufene eBay-Bild-URL): Platzhalter statt leerer Kachel
      img.addEventListener("error", () => {
        const ph = document.createElement("span");
        ph.className = img.classList.contains("gph") ? "gph-none" : "mv-ph";
        ph.innerHTML = MONO_PH;
        img.replaceWith(ph);
      }, { once: true });
    }
  });
}

/* Platzhalter für fehlende Kartenfotos: die Slab-Silhouette sagt, was hier
   hingehört — und als Strich-SVG braucht sie im Dunkelmodus keinen
   Invert-Filter, anders als das bisherige PNG. */
const MONO_PH = `<svg class="mono-ph" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="SERO"> <rect x="22" y="8" width="56" height="84" rx="8" ry="8"/> <line x1="22" y1="25" x2="78" y2="25"/> <circle cx="67" cy="16.5" r="3.6"/> <path d="M64 48 C64 42.5 58 39.5 50 39.5 C42 39.5 36 42.5 36 48.2 C36 52.4 40 54.4 45 56.2 L55 61.8 C60 63.6 64 65.6 64 70.5 C64 76.2 58 79.2 50 79.2 C42 79.2 36 76.2 36 70.7"/> </svg>`;

/* Capacitor-Vorbereitung: im Browser ist SERO_API_BASE nicht gesetzt und
   url() reicht Pfade unverändert durch. Die spätere App-Hülle setzt vor dem
   sero.js-Include `window.SERO_API_BASE = "https://…"` — mehr braucht der
   Umzug in den App Store an dieser Stelle nicht. */
const API_BASE = (window.SERO_API_BASE || "").replace(/\/$/, "");
const url = (p) => (API_BASE && typeof p === "string" && p.startsWith("/") ? API_BASE + p : p);

/* Stabile Geräte-Kennung: die Foto-Ablage auf dem Server ist pro Gerät
   getrennt — sonst löscht ein „Abbrechen" auf dem iPad die Aufnahmen des
   iPhones, und gleichzeitiges Fotografieren mischt zwei Stücke ineinander. */
function deviceId() {
  let d = storeSafe.getString("sero_device");
  if (!d) {
    d = "d" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    storeSafe.setString("sero_device", d);
  }
  return d;
}
const devQ = () => "device=" + encodeURIComponent(deviceId());

const HAPTIK = { light: 10, medium: [12, 50, 20], success: [10, 60, 18], soft: 8 };
function haptic(art = "light") {
  const H = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Haptics;
  if (H) {
    try {
      if (art === "success") H.notification({ type: "SUCCESS" });
      else H.impact({ style: art === "medium" ? "MEDIUM" : "LIGHT" });
      return;
    } catch { /* Plugin da, aber unwillig — unten weiter */ }
  }
  if (navigator.vibrate) navigator.vibrate(HAPTIK[art] || HAPTIK.light);
}

const cache = {
  get: (k) => storeSafe.getJSON("sero_" + k, null),
  set: (k, v) => { storeSafe.setJSON("sero_" + k, v); },
};

const COND_LABELS = {
  NEW: "Neu", LIKE_NEW: "Neuwertig", NEW_OTHER: "Neu (sonstige)",
  NEW_WITH_DEFECTS: "Neu mit Fehlern", CERTIFIED_REFURBISHED: "Zertifiziert refurbished",
  EXCELLENT_REFURBISHED: "Refurbished (exzellent)", VERY_GOOD_REFURBISHED: "Refurbished (sehr gut)",
  GOOD_REFURBISHED: "Refurbished (gut)", SELLER_REFURBISHED: "Vom Verkäufer aufbereitet",
  USED_EXCELLENT: "Gebraucht — exzellent", USED_VERY_GOOD: "Gebraucht — sehr gut",
  USED_GOOD: "Gebraucht — gut", USED_ACCEPTABLE: "Gebraucht — akzeptabel",
  PRE_OWNED_EXCELLENT: "Gebraucht — exzellent", PRE_OWNED_FAIR: "Gebraucht — okay",
  FOR_PARTS_OR_NOT_WORKING: "Defekt / für Bastler",
  GRADED: "Professionell bewertet (Graded)", UNGRADED: "Nicht bewertet (Ungraded)",
};
/** Bei Sammelkarten: LIKE_NEW = Graded, USED_VERY_GOOD = Ungraded (eBay-IDs). */
function isCardCategory(name) {
  const n = String(name || "").toLowerCase();
  return /karte|card|trading|pokémon|pokemon|one piece|yu-?gi|magic|lorcana|dragon ball|tcg/.test(n);
}
const condLabel = (c, catName) => {
  if (isCardCategory(catName)) {
    if (c === "LIKE_NEW") return L("Professionell bewertet (Graded)");
    if (c === "USED_VERY_GOOD") return L("Nicht bewertet (Ungraded)");
  }
  return L(COND_LABELS[c] || c || "—");
};
const CATEGORIES = ["Pokémon", "One Piece", "Magic", "Yu-Gi-Oh!", "Lorcana", "Dragon Ball", "Sport", "Games", "Manga", "Comics", "LEGO", "TCG Sonstiges", "Sonstiges"];
const CAT_COLORS = {
  "Pokémon": "#c9a961", "One Piece": "#2dd4bf", "Magic": "#e0682f", "Yu-Gi-Oh!": "#b48ead",
  "Lorcana": "#8a5cf6", "Dragon Ball": "#f0a03c", "Sport": "#5aa85e", "Games": "#a78bfa",
  "Manga": "#e8d5a3", "Comics": "#7aa2f7",
  "LEGO": "#e05252", "TCG Sonstiges": "#5a9aa8", "Sonstiges": "#8e8e93",
};
/** Anzeige ohne Sammelbegriff TCG — intern bleibt domain/category unverändert. */
const CAT_UI_LABEL = { "TCG Sonstiges": "Weitere Karten", "Sonstiges": "Weiteres" };
function catUiLabel(c) { return CAT_UI_LABEL[c] || c || ""; }
const CAT_CHIP_LOGO = {
  "Pokémon": "assets/logo-pokemon.svg",
  "One Piece": "assets/logo-onepiece.svg",
};
const CAT_CHIP_ORDER = ["One Piece", "Pokémon", "Games", "Magic", "Yu-Gi-Oh!", "Lorcana", "Dragon Ball", "Sport", "Manga", "Comics", "LEGO", "TCG Sonstiges", "Sonstiges"];
function itemMatchesFilterCat(item, cat) {
  if (!cat || cat === "Alle") return true;
  const name = String((item && item.name) || "");
  const category = String((item && item.category) || "");
  const game = String((item && item.card && item.card.game) || "").toLowerCase();
  const blob = `${name} ${category}`.toLowerCase();
  if (cat === "Pokémon") {
    return category === "Pokémon" || game === "pokemon" || /pok[eé]mon/i.test(blob);
  }
  if (cat === "One Piece") {
    return category === "One Piece" || game === "onepiece" || /one\s*piece/i.test(blob);
  }
  if (cat === "Games") {
    const kind = item && item.canonical_identity && item.canonical_identity.kind;
    return category === "Games" || kind === "game";
  }
  if (cat === "Manga") return /manga/.test(blob);
  if (cat === "Comics") return /comic/.test(blob);
  return category === cat;
}
function collectionChipCats(items) {
  const list = items || [];
  const counts = {};
  for (const cat of CAT_CHIP_ORDER) {
    const n = list.filter((i) => itemMatchesFilterCat(i, cat)).length;
    if (n) counts[cat] = n;
  }
  for (const i of list) {
    const c = i && i.category;
    if (c && !counts[c] && c !== "Alle") {
      const n = list.filter((x) => x.category === c).length;
      if (n) counts[c] = n;
    }
  }
  const extra = Object.keys(counts).filter((c) => !CAT_CHIP_ORDER.includes(c));
  return CAT_CHIP_ORDER.filter((c) => counts[c]).concat(extra);
}
function catChipHtml(cat, on) {
  const label = catUiLabel(cat);
  const logo = CAT_CHIP_LOGO[cat];
  const inner = logo
    ? `<img class="fchip-logo" src="${esc(logo)}" alt="">`
    : esc(L(label));
  return `<button type="button" class="fchip${logo ? " fchip-logoed" : ""} ${on ? "on" : ""}" data-c="${esc(cat)}" aria-label="${esc(L(label))}">${inner}</button>`;
}

/** Sichtbare Inventar-Kategorien — Multi-Select, leer = alle. */
const INV_CATS = ["One Piece", "Games", "Pokémon", "Sonstiges", "TCG Sonstiges"];
const INV_TCG_SET = new Set(["One Piece", "Pokémon", "TCG Sonstiges"]);
const INV_GRADERS = ["PSA", "BGS", "SGC", "CGC", "WATA"];
const INV_NOTES = ["10", "9.8", "9.5", "9", "8.5", "8", "7"];
const INV_LANGS = [
  { id: "de", label: "Deutsch" },
  { id: "en", label: "Englisch" },
  { id: "ja", label: "Japanisch" },
  { id: "andere", label: "Andere" },
];
const INV_REGIONS = ["PAL", "NTSC", "Japan", "Andere"];

function identFieldVal(item, key) {
  const f = item && item.canonical_identity && item.canonical_identity.fields;
  const v = f && f[key] && f[key].value;
  return v == null ? "" : String(v);
}
function identKindOf(item) {
  return (item && item.canonical_identity && item.canonical_identity.kind) || "";
}
function itemInvCat(item) {
  if (!item) return "Sonstiges";
  if (itemMatchesFilterCat(item, "One Piece")) return "One Piece";
  if (itemMatchesFilterCat(item, "Pokémon")) return "Pokémon";
  if (itemMatchesFilterCat(item, "Games") || identKindOf(item) === "game") return "Games";
  const cat = String((item && item.category) || "");
  if (cat === "Magic" || cat === "Yu-Gi-Oh!" || cat === "Lorcana" || cat === "Dragon Ball"
      || cat === "TCG Sonstiges" || cat === "Sport" || isCardCategory(cat)
      || itemMatchesFilterCat(item, "Magic") || itemMatchesFilterCat(item, "Yu-Gi-Oh!")
      || itemMatchesFilterCat(item, "Lorcana") || itemMatchesFilterCat(item, "Dragon Ball")
      || itemMatchesFilterCat(item, "TCG Sonstiges"))
    return "TCG Sonstiges";
  return "Sonstiges";
}
function invCatsChipOrder() {
  const head = CAT_CHIP_ORDER.filter((c) => INV_CATS.includes(c));
  return head.concat(INV_CATS.filter((c) => !head.includes(c)));
}
function invCatChipHtml(cat, on) {
  const label = catUiLabel(cat);
  const logo = CAT_CHIP_LOGO[cat];
  const inner = logo
    ? `<img class="fchip-logo" src="${esc(logo)}" alt="">`
    : `<span class="fchip-lab">${esc(L(label))}</span>`;
  return `<button type="button" class="fchip inv-chip${logo ? " fchip-logoed" : ""} ${on ? "on" : ""}" data-c="${esc(cat)}" aria-pressed="${on ? "true" : "false"}" aria-label="${esc(L(label))}">${inner}</button>`;
}
function invCatsSelected(f) {
  const cats = (f && f.cats) || [];
  return cats.filter((c) => INV_CATS.includes(c));
}
function itemMatchesInvCats(item, cats) {
  if (!cats || !cats.length) return true;
  return cats.includes(itemInvCat(item));
}
function invToggleCat(list, cat) {
  const cur = (list || []).slice();
  const i = cur.indexOf(cat);
  if (i >= 0) cur.splice(i, 1);
  else cur.push(cat);
  return cur.filter((c) => INV_CATS.includes(c));
}
function invNormGrader(raw) {
  const g = String(raw || "").toUpperCase().replace(/[^A-Z]/g, "");
  if (g === "BECKETT" || g === "BGS") return "BGS";
  if (INV_GRADERS.includes(g)) return g;
  return g ? "Andere" : "";
}
function invGradeNote(item) {
  const g = (item && item.graded) || {};
  const n = g.grade != null ? String(g.grade).replace(",", ".") : "";
  const num = parseFloat(n);
  return { raw: n, num: isFinite(num) ? num : NaN };
}
function itemIsGraded(item) {
  const g = (item && item.graded) || {};
  return !!(g.grade || g.grader);
}
function invNormLang(raw) {
  const s = String(raw || "").toLowerCase();
  if (!s) return "";
  if (/deutsch|german|\bde\b|ger\b/.test(s)) return "de";
  if (/englisch|english|\ben\b|\beng\b/.test(s)) return "en";
  if (/japanisch|japanese|\bjp\b|\bja\b|日本語/.test(s)) return "ja";
  return "andere";
}
function itemLangId(item) {
  const fromIdent = identFieldVal(item, "language");
  const fromCard = (item && item.card && item.card.language)
    || (item && item.card_info && item.card_info.language) || "";
  const hint = detectLanguageHint(item && item.name, fromIdent, fromCard);
  return invNormLang(fromIdent || fromCard || hint || "");
}
function invNormRegion(raw) {
  const s = String(raw || "").toUpperCase();
  if (!s) return "";
  if (/\bPAL\b/.test(s)) return "PAL";
  if (/\bNTSC\b/.test(s)) return "NTSC";
  if (/JAPAN|\bJPN\b|\bJP\b/.test(s)) return "Japan";
  return "Andere";
}
function itemRegionId(item) {
  const fromIdent = identFieldVal(item, "region");
  const blob = `${fromIdent} ${item && item.name || ""} ${identFieldVal(item, "platform")}`;
  if (!fromIdent && !/\bPAL\b|\bNTSC\b|JAPAN|\bJPN\b/i.test(blob)) return "";
  return invNormRegion(fromIdent || blob);
}
function itemYear(item) {
  const fromIdent = identFieldVal(item, "year") || identFieldVal(item, "edition");
  const y1 = parseInt(fromIdent, 10);
  if (y1 >= 1970 && y1 <= 2035) return y1;
  const m = String((item && item.name) || "").match(/\b(19[8-9]\d|20[0-3]\d)\b/);
  return m ? parseInt(m[1], 10) : NaN;
}
function itemSearchHay(item) {
  const g = (item && item.graded) || {};
  const c = (item && item.card) || {};
  const ci = (item && item.card_info) || {};
  return [
    item && item.name, item && item.category, item && item.notes,
    c.set_name, c.set, c.number, ci.set_name, ci.number, ci.set_hint,
    identFieldVal(item, "set_name"), identFieldVal(item, "number"),
    identFieldVal(item, "edition"), identFieldVal(item, "cert_number"),
    g.cert_number, g.cert, g.psa_cert,
  ].filter(Boolean).join(" ").toLowerCase();
}
function itemValueNum(item) {
  const v = item && item.est_value;
  if (v == null || v === "") return NaN;
  const n = Number(v);
  return isFinite(n) ? n : NaN;
}
function parseRangeNum(s) {
  if (s == null || String(s).trim() === "") return NaN;
  const n = parseFloat(String(s).replace(",", "."));
  return isFinite(n) ? n : NaN;
}
function invSheetFacetCount(f) {
  if (!f) return 0;
  let n = 0;
  if (f.cond) n += 1;
  n += (f.graders || []).length;
  n += (f.notes || []).length;
  if (String(f.noteFrom || "").trim() || String(f.noteTo || "").trim()) n += 1;
  n += (f.langs || []).length;
  n += (f.regions || []).length;
  if (String(f.valueFrom || "").trim() || String(f.valueTo || "").trim()) n += 1;
  if (String(f.yearFrom || "").trim() || String(f.yearTo || "").trim()) n += 1;
  return n;
}
function invFilterBadgeCount(f) {
  return invCatsSelected(f).length + invSheetFacetCount(f);
}
function invSheetActive(f) {
  return invSheetFacetCount(f) > 0;
}
function invResetSheetFacets(f) {
  f.cats = [];
  f.cond = null;
  f.graders = [];
  f.notes = [];
  f.noteFrom = "";
  f.noteTo = "";
  f.langs = [];
  f.regions = [];
  f.valueFrom = "";
  f.valueTo = "";
  f.yearFrom = "";
  f.yearTo = "";
  return f;
}
function cloneInvFacets(f) {
  return {
    cond: f.cond || null,
    graders: (f.graders || []).slice(),
    notes: (f.notes || []).slice(),
    noteFrom: f.noteFrom || "",
    noteTo: f.noteTo || "",
    langs: (f.langs || []).slice(),
    regions: (f.regions || []).slice(),
    valueFrom: f.valueFrom || "",
    valueTo: f.valueTo || "",
    yearFrom: f.yearFrom || "",
    yearTo: f.yearTo || "",
  };
}
function applyInvFacets(target, src) {
  target.cond = src.cond || null;
  target.graders = (src.graders || []).slice();
  target.notes = (src.notes || []).slice();
  target.noteFrom = src.noteFrom || "";
  target.noteTo = src.noteTo || "";
  target.langs = (src.langs || []).slice();
  target.regions = (src.regions || []).slice();
  target.valueFrom = src.valueFrom || "";
  target.valueTo = src.valueTo || "";
  target.yearFrom = src.yearFrom || "";
  target.yearTo = src.yearTo || "";
}
function itemMatchesSheetFacets(item, f) {
  if (!f) return true;
  const graded = itemIsGraded(item);
  if (f.cond === "raw" && graded) return false;
  if (f.cond === "graded" && !graded) return false;
  if ((f.graders || []).length) {
    const g = invNormGrader(item.graded && item.graded.grader);
    if (!f.graders.includes(g || "Andere")) return false;
  }
  const note = invGradeNote(item);
  if ((f.notes || []).length) {
    const token = INV_NOTES.includes(note.raw) ? note.raw
      : (isFinite(note.num) && INV_NOTES.includes(String(note.num)) ? String(note.num) : "Andere");
    if (!f.notes.includes(token)) return false;
  }
  const nFrom = parseRangeNum(f.noteFrom);
  const nTo = parseRangeNum(f.noteTo);
  if (isFinite(nFrom) || isFinite(nTo)) {
    if (!isFinite(note.num)) return false;
    if (isFinite(nFrom) && note.num < nFrom) return false;
    if (isFinite(nTo) && note.num > nTo) return false;
  }
  if ((f.langs || []).length) {
    const id = itemLangId(item) || "andere";
    if (!f.langs.includes(id)) return false;
  }
  if ((f.regions || []).length) {
    const id = itemRegionId(item) || "Andere";
    if (!f.regions.includes(id)) return false;
  }
  const val = itemValueNum(item);
  const vFrom = parseRangeNum(f.valueFrom);
  const vTo = parseRangeNum(f.valueTo);
  if (isFinite(vFrom) || isFinite(vTo)) {
    if (!isFinite(val)) return false;
    if (isFinite(vFrom) && val < vFrom) return false;
    if (isFinite(vTo) && val > vTo) return false;
  }
  const yr = itemYear(item);
  const yFrom = parseRangeNum(f.yearFrom);
  const yTo = parseRangeNum(f.yearTo);
  if (isFinite(yFrom) || isFinite(yTo)) {
    if (!isFinite(yr)) return false;
    if (isFinite(yFrom) && yr < yFrom) return false;
    if (isFinite(yTo) && yr > yTo) return false;
  }
  return true;
}
function invAppliedChip(key, label) {
  return `<button type="button" class="inv-applied-chip" data-ak="${esc(key)}" aria-label="${esc(L("Entfernen"))}: ${esc(label)}"><span>${esc(label)}</span><span class="inv-x" aria-hidden="true">${icon("xmark", 12)}</span></button>`;
}
function invAppliedHtml(f, query, id) {
  const chips = [];
  const q = (query || "").trim();
  if (q) chips.push(invAppliedChip("q", `„${q}“`));
  if (f.cond === "raw") chips.push(invAppliedChip("cond", L("Roh")));
  if (f.cond === "graded") chips.push(invAppliedChip("cond", L("Graded")));
  (f.graders || []).forEach((g) => chips.push(invAppliedChip("grader:" + g, g === "Andere" ? L("Andere") : g)));
  (f.notes || []).forEach((n) => chips.push(invAppliedChip("note:" + n, n === "Andere" ? L("Andere") : n)));
  const nFrom = String(f.noteFrom || "").trim();
  const nTo = String(f.noteTo || "").trim();
  if (nFrom || nTo) chips.push(invAppliedChip("noteRange", (nFrom || "…") + "–" + (nTo || "…")));
  (f.langs || []).forEach((idL) => {
    const lab = (INV_LANGS.find((x) => x.id === idL) || {}).label || idL;
    chips.push(invAppliedChip("lang:" + idL, L(lab)));
  });
  (f.regions || []).forEach((r) => chips.push(invAppliedChip("region:" + r, r === "Andere" ? L("Andere") : r)));
  const vFrom = String(f.valueFrom || "").trim();
  const vTo = String(f.valueTo || "").trim();
  if (vFrom && vTo) chips.push(invAppliedChip("value", LF("{0}–{1} €", vFrom, vTo)));
  else if (vFrom) chips.push(invAppliedChip("value", LF("ab {0} €", vFrom)));
  else if (vTo) chips.push(invAppliedChip("value", LF("bis {0} €", vTo)));
  const yFrom = String(f.yearFrom || "").trim();
  const yTo = String(f.yearTo || "").trim();
  if (yFrom || yTo) chips.push(invAppliedChip("year", (yFrom || "…") + "–" + (yTo || "…")));
  if (!chips.length) return "";
  return chips.join("") + `<button type="button" class="inv-clear-all" data-ak="all">${esc(L("Alles zurücksetzen"))}</button>`;
}
function invRemoveApplied(f, key, querySetter) {
  if (key === "all") {
    invResetSheetFacets(f);
    if (querySetter) querySetter("");
    return;
  }
  if (key === "q") { if (querySetter) querySetter(""); return; }
  if (key === "cond") { f.cond = null; return; }
  if (key === "value") { f.valueFrom = ""; f.valueTo = ""; return; }
  if (key === "year") { f.yearFrom = ""; f.yearTo = ""; return; }
  if (key === "noteRange") { f.noteFrom = ""; f.noteTo = ""; return; }
  const [kind, val] = key.split(":");
  const drop = (arr) => (arr || []).filter((x) => x !== val);
  if (kind === "grader") f.graders = drop(f.graders);
  else if (kind === "note") f.notes = drop(f.notes);
  else if (kind === "lang") f.langs = drop(f.langs);
  else if (kind === "region") f.regions = drop(f.regions);
}
function invFacetChip(name, val, label, on) {
  return `<button type="button" class="fchip inv-chip ${on ? "on" : ""}" data-inv="${esc(name)}" data-v="${esc(val)}" aria-pressed="${on ? "true" : "false"}">${esc(L(label))}</button>`;
}
function invRangeRow(idFrom, idTo, fromVal, toVal, unit, phFrom, phTo) {
  return `<div class="inv-range">
    <input id="${esc(idFrom)}" type="text" inputmode="decimal" placeholder="${esc(L(phFrom))}" value="${esc(fromVal || "")}" autocomplete="off">
    <span class="inv-range-sep">–</span>
    <input id="${esc(idTo)}" type="text" inputmode="decimal" placeholder="${esc(L(phTo))}" value="${esc(toVal || "")}" autocomplete="off">
    ${unit ? `<span class="inv-range-unit">${esc(unit)}</span>` : ""}
  </div>`;
}
function invFilterGroups(cats) {
  const sel = cats || [];
  const games = sel.includes("Games");
  const tcg = sel.some((c) => INV_TCG_SET.has(c));
  return { games, tcg };
}
function invFilterBodyHtml(draft, opts) {
  const o = opts || {};
  const cats = o.cats || [];
  const groups = invFilterGroups(cats);
  const cond = draft.cond || "";
  const showGrade = cond === "graded";
  const showNote = cond === "graded";
  const catBlock = o.withCats
    ? `<p class="sheet-hint">${L("Kategorie")}</p>
       <div class="chips" id="fltCats">${invCatsChipOrder().map((c) => invCatChipHtml(c, cats.includes(c))).join("")}</div>`
    : "";
  const gradeBlock = showGrade
    ? `<p class="sheet-hint">${L("Grading")}</p>
       <div class="chips" id="invFltGrader">${INV_GRADERS.concat(["Andere"]).map((g) =>
         invFacetChip("grader", g, g, (draft.graders || []).includes(g))).join("")}</div>`
    : "";
  const noteBlock = showNote
    ? `<p class="sheet-hint">${L("Note")}</p>
       <div class="chips" id="invFltNote">${INV_NOTES.concat(["Andere"]).map((n) =>
         invFacetChip("note", n, n, (draft.notes || []).includes(n))).join("")}</div>
       ${invRangeRow("invNoteFrom", "invNoteTo", draft.noteFrom, draft.noteTo, "", "Von", "Bis")}`
    : "";
  const langBlock = o.withLang && groups.tcg
    ? `<p class="sheet-hint">${L("Sprache")}</p>
       <div class="chips" id="invFltLang">${INV_LANGS.map((x) =>
         invFacetChip("lang", x.id, x.label, (draft.langs || []).includes(x.id))).join("")}</div>`
    : "";
  const regionBlock = o.withRegion && groups.games
    ? `<p class="sheet-hint">${L("Region")}</p>
       <div class="chips" id="invFltRegion">${INV_REGIONS.map((r) =>
         invFacetChip("region", r, r, (draft.regions || []).includes(r))).join("")}</div>`
    : "";
  const yearBlock = o.withYear
    ? `<p class="sheet-hint">${L("Jahr")}</p>
       ${invRangeRow("invYearFrom", "invYearTo", draft.yearFrom, draft.yearTo, "", "Von", "Bis")}`
    : "";
  return `
    ${catBlock}
    <p class="sheet-hint">${L("Zustand")}</p>
    <div class="chips" id="invFltCond">
      ${invFacetChip("cond", "raw", "Roh", cond === "raw")}
      ${invFacetChip("cond", "graded", "Graded", cond === "graded")}
    </div>
    ${gradeBlock}
    ${noteBlock}
    ${langBlock}
    ${regionBlock}
    <p class="sheet-hint">${L("Wert")}</p>
    ${invRangeRow("invValFrom", "invValTo", draft.valueFrom, draft.valueTo, "€", "Von", "Bis")}
    ${yearBlock}`;
}
/* „Bis“ kleiner als „Von“ ergibt eine leere Menge. Vorher wurde das still
   angewendet und sah aus, als gäbe es keine Treffer. Jetzt: sichtbare
   Meldung, kein Anwenden. Die Filterschlüssel bleiben unverändert. */
const INV_RANGE_PAIRS = [
  ["valueFrom", "valueTo", "Wert"],
  ["noteFrom", "noteTo", "Note"],
  ["yearFrom", "yearTo", "Jahr"],
];
function invRangeError(f) {
  if (!f) return null;
  for (const [a, b, label] of INV_RANGE_PAIRS) {
    const from = parseRangeNum(f[a]);
    const to = parseRangeNum(f[b]);
    if (isFinite(from) && isFinite(to) && to < from) return label;
  }
  return null;
}
function invPaintRangeError(f) {
  const bad = invRangeError(f);
  const err = $("sheetErr");
  if (err) {
    err.textContent = bad
      ? LF("{0}: „Bis“ ist kleiner als „Von“. Bitte Werte tauschen.", L(bad))
      : "";
  }
  return bad;
}
function toggleInvList(arr, val) {
  const cur = (arr || []).slice();
  const i = cur.indexOf(val);
  if (i >= 0) cur.splice(i, 1);
  else cur.push(val);
  return cur;
}
function bindInvFilterSheet(draft, opts, onLiveValue) {
  const body = $("sheetBody");
  if (!body) return;
  const paint = () => {
    body.innerHTML = invFilterBodyHtml(draft, opts);
    bindInvFilterSheet(draft, opts, onLiveValue);
    invPaintRangeError(draft);
  };
  body.querySelectorAll("[data-inv]").forEach((b) => {
    b.onclick = () => {
      const kind = b.dataset.inv;
      const val = b.dataset.v;
      if (kind === "cond") draft.cond = draft.cond === val ? null : val;
      else if (kind === "grader") draft.graders = toggleInvList(draft.graders, val);
      else if (kind === "note") draft.notes = toggleInvList(draft.notes, val);
      else if (kind === "lang") draft.langs = toggleInvList(draft.langs, val);
      else if (kind === "region") draft.regions = toggleInvList(draft.regions, val);
      paint();
    };
  });
  const catBtns = body.querySelectorAll("#fltCats [data-c]");
  catBtns.forEach((b) => {
    b.onclick = () => {
      opts.cats = invToggleCat(opts.cats, b.dataset.c);
      paint();
    };
  });
  const bindRange = (idFrom, idTo, keyFrom, keyTo, live) => {
    const a = $(idFrom), c = $(idTo);
    const sync = () => {
      draft[keyFrom] = a ? a.value : "";
      draft[keyTo] = c ? c.value : "";
      const bad = invPaintRangeError(draft);
      [a, c].forEach((el) => { if (el) el.classList.toggle("is-bad", !!bad); });
      if (live && onLiveValue && !bad) onLiveValue();
    };
    if (a) a.oninput = sync;
    if (c) c.oninput = sync;
  };
  bindRange("invValFrom", "invValTo", "valueFrom", "valueTo", true);
  bindRange("invNoteFrom", "invNoteTo", "noteFrom", "noteTo", false);
  bindRange("invYearFrom", "invYearTo", "yearFrom", "yearTo", false);
}
function openInvFilter(title, draft, opts, onApply, onReset) {
  openSheet(title, "", invFilterBodyHtml(draft, opts), () => {
    if (invPaintRangeError(draft)) {
      haptic("light");
      return;   // verdrehte Spanne wird nicht still übernommen
    }
    onApply();
    closeSheet();
  }, "Anwenden");
  const sh = $("sheet");
  if (sh) sh.classList.add("sheet-inv");
  $("sheetCancel").textContent = L("Zurücksetzen");
  $("sheetCancel").onclick = () => {
    onReset();
    const body = $("sheetBody");
    if (body) {
      body.innerHTML = invFilterBodyHtml(draft, opts);
      bindInvFilterSheet(draft, opts, opts.onLiveValue);
      invPaintRangeError(draft);
    }
  };
  bindInvFilterSheet(draft, opts, opts.onLiveValue);
  invPaintRangeError(draft);
}
function invSearchHtml(id, ph, value) {
  return `<div class="inv-search" id="${esc(id)}Wrap">
    <span class="inv-search-ic">${icon("search", 16)}</span>
    <input id="${esc(id)}" type="search" inputmode="search" enterkeyhint="search"
      placeholder="${esc(L(ph))}" autocomplete="off" value="${esc(value || "")}">
    <button type="button" class="inv-search-clear" id="${esc(id)}Clear" aria-label="${esc(L("Zurücksetzen"))}" ${value ? "" : "hidden"}>${icon("xmark", 14)}</button>
  </div>`;
}
function saleLinkedItem(r) {
  if (!r || !r.item_id) return null;
  return (state.items || []).find((x) => x.id === r.item_id) || null;
}
function saleAsInvItem(r) {
  const col = saleLinkedItem(r);
  if (col) return col;
  return {
    name: (r && r.title) || "",
    category: "",
    category_name: (r && r.category_name) || "",
    condition: r && r.condition,
    graded: null,
    notes: "",
    est_value: salePriceNum(r),
    card: null,
  };
}
function salePriceNum(r) {
  const raw = r && (r.sold_price || r.current_price || r.price);
  if (raw == null || raw === "") return NaN;
  const n = parseFloat(String(raw).replace(",", "."));
  return isFinite(n) ? n : NaN;
}
function saleInvCat(r) {
  return itemInvCat(saleAsInvItem(r));
}
function saleSearchHay(r) {
  const item = saleAsInvItem(r);
  return [
    r && r.title, r && r.listing_id, r && r.draft_id,
    itemSearchHay(item),
  ].filter(Boolean).join(" ").toLowerCase();
}
function saleMatchesInv(r, f, q) {
  const item = saleAsInvItem(r);
  if (q && !saleSearchHay(r).includes(q)) return false;
  if (!itemMatchesInvCats(item, (f && f.cats) || [])) return false;
  if (!itemMatchesSheetFacets(item, f)) return false;
  return true;
}
function ebayMarkHtml(cls = "") {
  return `<span class="tab-ebay-mark${cls ? " " + cls : ""}" aria-hidden="true"><svg viewBox="0 0 1000 401" width="48" height="19" fill="currentColor" focusable="false"><path d="M199.636 185.866c-1.944-46.877-35.78-64.42-71.941-64.42-38.994 0-70.127 19.733-75.58 64.42zm-148.602 33.325c2.704 45.484 34.07 72.384 77.198 72.384 29.88 0 56.46-12.175 65.359-38.66h51.684c-10.052 53.74-67.154 71.98-116.303 71.98C39.606 324.895 0 275.679 0 209.307 0 136.242 40.966 88.122 129.788 88.122c70.699 0 122.5 37 122.5 117.756v13.313z"/><path d="M380.832 290.624c46.572 0 78.441-33.522 78.441-84.109 0-50.582-31.869-84.108-78.441-84.108-46.31 0-78.444 33.526-78.444 84.108 0 50.587 32.133 84.109 78.444 84.109zM252.285 0h50.103v125.877c24.557-29.26 58.389-37.755 91.69-37.755 55.835 0 117.851 37.677 117.851 119.029 0 68.122-49.322 117.745-118.781 117.745-36.357 0-70.581-13.043-91.687-38.883 0 10.321-.576 20.724-1.705 30.564h-49.172c.855-15.91 1.706-35.718 1.706-51.747z"/><path d="M633.078 212.533c-45.439 1.49-73.671 9.689-73.671 39.619 0 19.376 15.447 40.382 54.663 40.382 52.577 0 80.643-28.659 80.643-75.663v-5.17c-18.433 0-41.164.161-61.637.833zm111.751 62.103c0 14.583.422 28.978 1.694 41.941h-46.614c-1.243-10.674-1.697-21.28-1.697-31.567-25.202 30.98-55.177 39.886-96.762 39.886-61.676 0-94.7-32.6-94.7-70.307 0-54.612 44.916-73.867 122.89-75.654 21.323-.487 45.274-.559 65.075-.559v-5.336c0-36.561-23.444-51.593-64.068-51.593-30.158 0-52.385 12.48-54.676 34.047h-52.652c5.572-53.772 62.067-67.371 111.74-67.371 59.509 0 109.773 21.173 109.773 84.115z"/><path d="M1000 96.457 845.055 400.751h-56.106l44.547-84.495L716.89 96.457h58.627l85.805 171.731 85.563-171.731z"/></svg></span>`;
}
/** Live auf eBay: Draft published, oder echte Listing-URL / Item-Id. */
function itemLiveOnEbay(i) {
  if (!i || i.sold || i.draft_status === "ended") return false;
  if (i.draft_status === "published") return true;
  const url = String(i.item_url || "");
  if (/ebay\.(de|com|at|ch)\//i.test(url) || /\/itm\//i.test(url)) return true;
  const st = String(i.listing_status || i.ebay_status || "").toLowerCase();
  if (st === "active" || st === "listed" || st === "published") return true;
  if (i.ebay_item_id || i.listing_id) return true;
  return false;
}
/** Grade-Siegel: Text + Farbe. CGC Pristine/Perfect → Gold, nicht schwarz/weiß.
 *  compact: kurze Form für kleine Kacheln (CGC P10 statt CGC Pristine 10). */
function gradeSeal(g, nameHint, compact) {
  if (!g || !g.grade) return { text: "", cls: "" };
  const gr = (g.grader || "").toUpperCase();
  const note = String(g.grade);
  const lab = String(g.label_type || "").toLowerCase().replace(/[\s-]+/g, "_");
  const blob = `${nameHint || ""} ${g.label_type || ""} ${note}`.toLowerCase();
  const isPristine = lab === "pristine" || lab === "gold_label" || blob.includes("pristine");
  const isPerfect = lab === "perfect" || blob.includes("perfect");
  const isBlack = lab === "black_label" || blob.includes("black label");
  let extra = "";
  if (isPristine) extra = compact ? "P" : "Pristine";
  else if (isPerfect) extra = compact ? "Pf" : "Perfect";
  else if (isBlack) extra = compact ? "BL" : "Black Label";
  const text = compact
    ? (extra ? `${gr} ${extra}${note}` : `${gr} ${note}`)
    : (extra ? `${gr} ${extra} ${note}` : `${gr} ${note}`);
  const cls = gr === "PSA" ? "red"
    : gr === "CGC" ? (isPristine || isPerfect ? "gold" : "bw")
    : (gr === "BGS" || gr === "BECKETT") ? (isBlack ? "gold" : "silver")
    : gr === "WATA" ? "navy" : "grey";
  return { text, cls };
}
const GAME_OF_CAT = {
  "Pokémon": "pokemon", "One Piece": "onepiece", "Magic": "magic", "Yu-Gi-Oh!": "yugioh",
  "Lorcana": "lorcana", "Dragon Ball": "dragonball",
};
const VARIANT_LABELS = { holo: "Holo", reverse: "Reverse Holo", normal: "Normal", firstEdition: "1. Edition", wPromo: "Promo" };

/* Thumbnails: eigene Fotos verkleinert laden — iPhone-Bilder sind mehrere MB groß */
const thumb = (u, w) => u && u.startsWith("/api/app/")
  ? url(`${u}${u.includes("?") ? "&" : "?"}w=${w}`) : u;
/* Katalog-Bilder statt eigener Fotos? (Svens Regel: eigenes Foto ist der Standard) */
const catalogView = () => storeSafe.getString("sero_catalog") === "1";

function sparklineLayout(values, w, h) {
  if (!values || values.length < 2) return [];
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  return values.map((v, i) => ({
    x: i / (values.length - 1) * (w - 4) + 2,
    y: h - 3 - (v - min) / span * (h - 8),
    v,
  }));
}
function sparkline(values, w, h, cls = "", area = false) {
  if (!values || values.length < 2) return "";
  const layout = sparklineLayout(values, w, h);
  const pts = layout.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const hub = cls.includes("ebay-hub-spark");
  const hair = cls.includes("col-hair");
  let fill = "";
  if (area && !hair) {
    const x0 = layout[0].x, x1 = layout[layout.length - 1].x;
    fill = `<polygon points="${x0},${h} ${pts} ${x1},${h}" fill="currentColor" opacity="${hub ? ".22" : ".12"}" stroke="none"/>`;
  }
  const sw = hair ? 1 : (hub ? 2.75 : 2);
  let extra = "";
  if (hub && !hair) {
    const last = layout[layout.length - 1];
    extra = `<circle cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="5" fill="currentColor"/>`;
  }
  return `<svg class="${cls}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" fill="none">
    ${fill}<polyline pathLength="1" points="${pts}" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"/>${extra}</svg>`;
}

const COL_HUB_CHART_W = 375;
const COL_HUB_CHART_H = 160;

function bindChartScrub(el, points, opts) {
  if (!el || !points || points.length < 2) return;
  const values = points.map((p) => p.v);
  const layout = sparklineLayout(values, COL_HUB_CHART_W, COL_HUB_CHART_H);
  const sumEl = opts && opts.sumEl;
  const dateEl = opts && opts.dateEl;
  const restText = (opts && opts.restText) || (sumEl ? sumEl.textContent : "—");
  const hidden = !!(opts && opts.hidden);
  const overlay = el.querySelector(".ebay-hub-scrub");
  const hair = el.querySelector(".ebay-hub-hair");
  const dot = el.querySelector(".ebay-hub-dot");
  const apply = (i, scrubbing) => {
    const p = points[i] || points[points.length - 1];
    if (sumEl && !hidden) {
      sumEl.textContent = (p && p.v != null && isFinite(p.v)) ? money(p.v) : "—";
    }
    /* 30-Tage-Delta bleibt auf dem Endwert, Scrub ändert nur die große Summe. */
    if (dateEl) {
      const lab = (scrubbing && p && p.t) ? fmtChartDay(p.t) : "";
      dateEl.hidden = !lab;
      if (lab) dateEl.textContent = lab;
    }
    if (overlay) overlay.hidden = !scrubbing;
    if (scrubbing && hair && dot && layout[i]) {
      hair.style.left = (layout[i].x / COL_HUB_CHART_W * 100) + "%";
      dot.style.left = (layout[i].x / COL_HUB_CHART_W * 100) + "%";
      dot.style.top = (layout[i].y / COL_HUB_CHART_H * 100) + "%";
    }
  };
  const rest = () => {
    if (sumEl && !hidden) sumEl.textContent = restText;
    if (dateEl) dateEl.hidden = true;
    if (overlay) overlay.hidden = true;
  };
  const idxFromEvent = (e) => {
    const src = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]) || e;
    const rect = el.getBoundingClientRect();
    const x = (src.clientX || 0) - rect.left;
    const t = rect.width ? x / rect.width : 1;
    return Math.max(0, Math.min(values.length - 1, Math.round(t * (values.length - 1))));
  };
  let pid = null;
  const start = (e) => {
    if (hidden) return;
    if (pid != null) return;
    if (e.pointerType === "mouse" && e.button != null && e.button !== 0) return;
    pid = e.pointerId != null ? e.pointerId : "touch";
    try { if (e.pointerId != null) el.setPointerCapture(e.pointerId); } catch (_) { /* */ }
    apply(idxFromEvent(e), true);
    if (e.cancelable && String(e.type || "").startsWith("touch")) e.preventDefault();
  };
  const move = (e) => {
    if (pid == null) return;
    if (e.pointerId != null && e.pointerId !== pid) return;
    apply(idxFromEvent(e), true);
    if (e.cancelable && String(e.type || "").startsWith("touch")) e.preventDefault();
  };
  const end = (e) => {
    if (pid == null) return;
    if (e && e.pointerId != null && e.pointerId !== pid) return;
    pid = null;
    rest();
  };
  el.addEventListener("pointerdown", start);
  el.addEventListener("pointermove", move);
  el.addEventListener("pointerup", end);
  el.addEventListener("pointercancel", end);
  el.addEventListener("pointerleave", (e) => {
    if (pid == null) return;
    if (el.hasPointerCapture && e.pointerId != null && el.hasPointerCapture(e.pointerId)) return;
    end(e);
  });
  el.addEventListener("touchstart", start, { passive: false });
  el.addEventListener("touchmove", move, { passive: false });
  el.addEventListener("touchend", end);
  el.addEventListener("touchcancel", end);
}

/* Achsen: europäisch, TradingView-Stil („2,86 K" / Euro) */
const fmtChartY = (v) => {
  const n = Number(v) || 0;
  if (Math.abs(n) >= 1000) {
    return (n / 1000).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " K";
  }
  return n.toLocaleString("de-DE", { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + " €";
};
const fmtChartDay = (dayOrTs) => {
  const d = typeof dayOrTs === "number"
    ? new Date(dayOrTs < 1e12 ? dayOrTs * 1000 : dayOrTs)
    : new Date(String(dayOrTs).length <= 10 ? dayOrTs + "T12:00:00" : dayOrTs);
  if (isNaN(d.getTime())) return "";
  let mon = d.toLocaleDateString("de-DE", { month: "short" }).replace(/\.$/, "");
  mon = mon.charAt(0).toUpperCase() + mon.slice(1);
  return `${d.getDate()}. ${mon}.`;
};

/* Historie: Backend liefert bereits heutigen Punkt (Europe/Berlin).
   Frontend erfindet keinen abweichenden Tag per UTC-toISOString. */
function histWithLive(hist, liveValue, asOfDay) {
  const pts = (hist || []).filter((p) => p && p.value != null).map((p) => ({
    day: p.day || null,
    value: Number(p.value),
  })).filter((p) => p.day && isFinite(p.value));
  if (liveValue == null || !isFinite(liveValue)) return pts;
  const today = asOfDay || (pts.length ? pts[pts.length - 1].day : null);
  if (!today) return [{ day: "today", value: liveValue }];
  if (!pts.length) return [{ day: today, value: liveValue }];
  if (pts[pts.length - 1].day === today) {
    return pts.slice(0, -1).concat([{ day: today, value: liveValue }]);
  }
  return pts.concat([{ day: today, value: liveValue }]);
}

/** Verlauf an gefilterten Sammlungswert anpassen (Form bleibt, Ende = Live). */
function scaleHistToLive(hist, fullLive, liveValue, asOfDay) {
  const base = Number(fullLive);
  if (!isFinite(base) || base <= 0) return histWithLive([], liveValue, asOfDay);
  const ratio = Number(liveValue) / base;
  const scaled = (hist || [])
    .filter((p) => p && p.day && p.value != null && isFinite(Number(p.value)))
    .map((p) => ({ day: p.day, value: Number(p.value) * ratio }));
  return histWithLive(scaled, liveValue, asOfDay);
}

/** Kurzverlauf aus 7-Tage-Deltas der sichtbaren Stücke (mind. 2 Punkte). */
function histFromItemDeltas(items, liveValue, asOfDay) {
  let weekAgo = 0;
  let n = 0;
  for (const i of items || []) {
    if (i.est_value === null || i.est_value === undefined) continue;
    const qty = Math.max(1, Number(i.quantity) || 1);
    const unit = Number(i.est_value);
    if (!isFinite(unit)) continue;
    const d = Number(i.delta7);
    weekAgo += (isFinite(d) ? unit - d : unit) * qty;
    n += 1;
  }
  if (!n || liveValue == null || !isFinite(liveValue)) return [];
  const today = asOfDay || "today";
  let weekDay = "week";
  if (asOfDay && /^\d{4}-\d{2}-\d{2}$/.test(asOfDay)) {
    const d = new Date(asOfDay + "T12:00:00");
    d.setDate(d.getDate() - 7);
    weekDay = d.toISOString().slice(0, 10);
  }
  return histWithLive([{ day: weekDay, value: weekAgo }], liveValue, asOfDay);
}

/** Statistik-Verlauf: immer sichtbar, angepasst an Filter (Kategorie echt). */
function collectionHistSeries(wertItems, liveValue, asOfDay, filterAn) {
  if (!filterAn) return histWithLive(state.history || [], liveValue, asOfDay);
  const f = state.filter;
  const cats = invCatsSelected(f);
  const onlyCat = cats.length === 1 && !invSheetActive(f) && !f.listed && !f.sold && !f.fav && !f.draft
    && !f.wish && !f.dup && !f.tag
    && !(state.colQuery && state.colQuery.trim());
  if (onlyCat && state.historyByCat && state.historyByCat[cats[0]]) {
    return histWithLive(state.historyByCat[cats[0]], liveValue, asOfDay);
  }
  const fromDelta = histFromItemDeltas(wertItems, liveValue, asOfDay);
  if (fromDelta.length >= 2) return fromDelta;
  const fullLive = Number((state.stats || {}).total_value);
  return scaleHistToLive(state.history || [], fullLive, liveValue, asOfDay);
}

/** TradingView-Linienchart — Y rechts, Daten unten, dünnes Grid, neon-grüne Linie */
function tvLineChart(series, opts = {}) {
  const w = opts.w || 375, h = opts.h || 200;
  const padL = 8, padR = 52, padT = 10, padB = 22;
  const pts = (series || []).filter((p) => p && isFinite(p.value));
  if (pts.length < 2) {
    return `<div class="tv-chart empty"><p>${esc(L(opts.empty || "Noch kein Verlauf"))}</p></div>`;
  }
  const vals = pts.map((p) => p.value);
  let min = Math.min(...vals), max = Math.max(...vals);
  if (max === min) { min -= Math.max(1, min * 0.01); max += Math.max(1, max * 0.01); }
  const span = max - min;
  const plotW = w - padL - padR, plotH = h - padT - padB;
  const xy = (v, i) => [
    padL + (i / (pts.length - 1)) * plotW,
    padT + plotH - ((v - min) / span) * plotH,
  ];
  const line = pts.map((p, i) => xy(p.value, i).map((n) => n.toFixed(1)).join(",")).join(" ");
  const ticks = 4;
  let grid = "", ylab = "";
  for (let i = 0; i <= ticks; i++) {
    const t = i / ticks;
    const y = padT + t * plotH;
    const val = max - t * span;
    grid += `<line class="tv-grid" x1="${padL}" y1="${y.toFixed(1)}" x2="${(w - padR).toFixed(1)}" y2="${y.toFixed(1)}"/>`;
    ylab += `<text class="tv-ylab" x="${w - 6}" y="${(y + 3).toFixed(1)}" text-anchor="end">${esc(fmtChartY(val))}</text>`;
  }
  const x0 = fmtChartDay(pts[0].day);
  const x1 = fmtChartDay(pts[pts.length - 1].day);
  return `<div class="tv-chart"><svg viewBox="0 0 ${w} ${h}" class="tv-svg" aria-hidden="true">
    ${grid}
    <polyline class="tv-line" points="${line}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    ${ylab}
    <text class="tv-xlab" x="${padL}" y="${h - 4}" text-anchor="start">${esc(x0)}</text>
    <text class="tv-xlab" x="${w - padR}" y="${h - 4}" text-anchor="end">${esc(x1)}</text>
  </svg></div>`;
}

const fmtAxis = (v) => v >= 1000
  ? Math.round(v).toLocaleString("de-DE")
  : v.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function trendChip(label, now, before) {
  const p = pctOf(now, before);
  if (p === null || !isFinite(p)) return "";
  const dir = p >= 0.5 ? "up" : p <= -0.5 ? "down" : "flat";
  const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "•";
  return `<span class="tchip ${dir}">${label} ${arrow} ${Math.abs(p).toFixed(1).replace(".", ",")} %</span>`;
}

/* ═══════════════════ Boot & Login ═══════════════════ */

function themePrefersDark() {
  try { return window.matchMedia("(prefers-color-scheme: dark)").matches; }
  catch (_) { return true; }
}

function themeIsDark() {
  const t = storeSafe.getString("sero_theme", "auto") || "auto";
  if (t === "light") return false;
  if (t === "dark") return true;
  return themePrefersDark();
}

function applyTheme() {
  const t = storeSafe.getString("sero_theme", "auto") || "auto";
  const dark = themeIsDark();
  document.documentElement.classList.add("skin-clean");
  document.documentElement.classList.toggle("force-dark", dark);
  document.documentElement.classList.toggle("force-light", !dark);
  try { refreshThemeTitles(); } catch (_) { /* */ }
  try {
    document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
      m.setAttribute("content", dark ? "#000000" : "#ffffff");
    });
  } catch (_) { /* */ }
  if (!applyTheme._mediaWired) {
    applyTheme._mediaWired = true;
    try {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onCh = () => {
        const cur = storeSafe.getString("sero_theme", "auto") || "auto";
        if (cur === "auto") applyTheme();
      };
      if (mq.addEventListener) mq.addEventListener("change", onCh);
      else if (mq.addListener) mq.addListener(onCh);
    } catch (_) { /* */ }
  }
}

/* Sprache: auto = Gerätesprache; explizit de/en speichern */
const _langPref = storeSafe.getString("sero_lang") || "auto";
const LANG = (_langPref === "de" || _langPref === "en")
  ? _langPref
  : ((navigator.language || "de").toLowerCase().startsWith("de") ? "de" : "en");
try { document.documentElement.lang = LANG; } catch (_) { /* */ }
const STR_EN = {
  /* ── Navigation, Tabs, Grundgerüst ── */
  "Sammlung": "Collection", "Verkauf": "Selling", "Profil": "Profile", "Scanner": "Scanner",
  "Start": "Home", "eBay": "eBay", "Info": "Info",
  "Karte scannen": "Scan item", "Scannen": "Scan", "Aus Fotos auswählen": "Choose from photos",
  "Verbindungen": "Connections", "Darstellung": "Appearance", "Daten & Sync": "Data & sync",
  "Hilfe & Rechtliches": "Help & legal", "Einrichten": "Set up",
  "Preis selbst setzen": "Set price yourself",
  "Dein Portfolio-Wert für dieses Stück. Leer lassen löscht den manuellen Wert.":
    "Your portfolio value for this item. Leave empty to clear the manual value.",
  "Preis gesetzt": "Price set", "Manueller Preis entfernt": "Manual price removed",
  "Foto bearbeiten": "Edit photo",
  "Erste Karte scannen": "Scan first item",
  "Erstes Stück scannen": "Scan first item",
  "Nächste Karte scannen": "Scan next item",
  "Nächstes Stück scannen": "Scan next item",
  "Preise werden aktualisiert …": "Updating prices…",
  "Sammlung neu erkennen": "Re-identify collection",
  "Neu erkennen": "Re-identify",
  "Sammlung wird neu erkannt …": "Re-identifying collection…",
  "{0} Stücke in der Warteschlange": "{0} items queued",
  "SERO analysiert alle Stücke mit Foto erneut — Set, Nummer und Sprache werden nachgezogen. Dauert bei vielen Stücken eine Weile.":
    "SERO re-analyzes all items with a photo — set, number and language are updated. This can take a while with many items.",
  "Sammlung durchsuchen": "Search collection", "Suchen": "Search",
  "Wird analysiert": "Analyzing", "Scan-Verlauf": "Scan history",
  "Aktiv": "Active", "Entwürfe": "Drafts", "Beendet": "Ended", "Verkauft": "Sold",
  "Deine Karten. Dein Marktplatz.": "Your cards. Your marketplace.",
  "Testmodus": "Test mode", "Scannen": "Scan", "Verkaufen": "Sell", "Karte": "Card",
  "Sortieren": "Sort", "Filtern": "Filter", "Filter": "Filter", "Schließen": "Close",
  "Favorit": "Favorite", "Entfernen": "Remove", "Abbrechen": "Cancel", "Übernehmen": "Apply",
  "Wird geladen …": "Loading…",
  "Aus Mediathek": "From library",
  "Aus Mediathek auswählen": "Choose from library",
  "Foto aufnehmen": "Take photo",
  "Aus Fotos": "From photos",
  "Wert wird ab dem 3. Stück sichtbar": "Value appears from the 3rd item",
  "Erlöse erscheinen hier": "Proceeds appear here",
  "Business Policies deines eBay-Kontos. Keine US-Dienste.":
    "Business policies of your eBay account. No US services.",
  "Weiteres Foto": "Another photo",
  "{0} von {1}": "{0} of {1}",
  "Hauptfoto": "Main photo",
  "Foto entfernen rückgängig": "Undo remove photo",
  "Foto öffnen": "Open photo",
  "nächstes Foto": "next photo",
  "Kamera bleibt offen": "Camera stays open",
  "über Inventory API verwaltet": "managed via Inventory API",
  "Bei eBay öffnen": "Open on eBay",
  "Versandprofil": "Shipping profile",
  "Richtlinie wählen": "Choose policy",
  "Kamera wechseln": "Switch camera",
  "Blitz": "Flash",
  "Blitz an": "Flash on",
  "Blitz aus": "Flash off",
  "Kamera nicht freigegeben. Mediathek geht trotzdem.":
    "Camera permission denied. The library still works.",
  "Keine Kamera an diesem Gerät.": "No camera on this device.",
  "Kamera ist gerade von einer anderen App belegt.":
    "The camera is in use by another app.",
  "Foto ist schon dabei.": "That photo is already added.",
  "Kostenlos": "Free",
  "Bearbeitungszeit": "Handling time",
  "Versandart": "Shipping type",
  "Versandkosten": "Shipping cost",
  "Internationaler Versand": "International shipping",
  "Abholung": "Pickup",
  "Zielmarktplatz": "Marketplace",
  "Rücknahme": "Returns",
  "Artikelmerkmale": "Item specifics",
  "Werktage": "business days",
  "{0} von {1} Fotos — Tipp wählt das Hauptbild.": "{0} of {1} photos — tap to set the main image.",
  "Zurück": "Back",
  "Alles klar": "Got it",
  "Kamera öffnen": "Open camera",
  "Später": "Later",
  "Schritt {0} von {1}": "Step {0} of {1}",
  "Willkommen": "Welcome",
  "SERO erkennt Sammelkarten, Spiele, Manga und Comics, zeigt den Marktwert und macht daraus auf Wunsch ein eBay-Angebot — immer erst nach deiner Freigabe.":
    "SERO identifies collectible cards, games, manga and comics, shows market value, and can turn them into an eBay listing — only after you approve.",
  "1 · Scannen": "1 · Scan",
  "Tippe unten in der Mitte auf die Kamera und fotografiere die Vorderseite. SERO liest Name, Set, Sprache und Grading-Label.":
    "Tap the camera at the bottom center and photograph the front. SERO reads name, set, language and grading label.",
  "2 · Marktwert": "2 · Market value",
  "Du siehst, was erkannt wurde. Den Wert holt SERO aus echten eBay-Verkäufen — nie als KI-Schätzung. Fehlen Belege, steht ehrlich „Wert unbekannt“.":
    "You see what was recognized. SERO takes the value from real eBay sales — never as an AI guess. If evidence is missing, it honestly says “Value unknown”.",
  "3 · Sammlung": "3 · Collection",
  "Jedes Stück landet in deiner Sammlung. Im Portfolio siehst du den Gesamtwert und die Entwicklung über die Zeit.":
    "Every item lands in your collection. In the portfolio you see total value and how it changes over time.",
  "4 · Listen": "4 · List",
  "Aus der Sammlung wird mit wenigen Tipps ein fertiges eBay-Listing. Online geht es erst, wenn du es freigibst — kein Autopilot.":
    "From the collection, a few taps build a ready eBay listing. It goes live only when you approve — no autopilot.",
  "Listing-Wert": "Listing value",
  "Entwurfswert": "Draft value",
  "Verkaufserlös": "Sales proceeds",
  "Designs": "Designs",
  "Noch keine Designs": "No designs yet",
  "{0} Designs": "{0} designs",
  "{0} verkauft": "{0} sold",
  "Verkauft für {0}": "Sold for {0}",
  "Endet bald": "Ending soon",
  "Endet zuletzt": "Ending last",
  "Preis · hoch → niedrig": "Price · high → low",
  "Preis · niedrig → hoch": "Price · low → high",
  "Endet gleich": "Ending now",
  "Endet in {0} Min": "Ends in {0} min",
  "Endet in {0} Std": "Ends in {0} h",
  "Endet {0}": "Ends {0}",
  "Endete {0}": "Ended {0}",
  "Verkauft {0}": "Sold {0}",
  "Entwurf verworfen": "Draft discarded",
  "Wiederherstellen fehlgeschlagen": "Restore failed",
  "Entfernen fehlgeschlagen": "Remove failed",
  "Ende": "Ends",
  "Termin": "Schedule",
  "Gebot": "Bid", "Gebote": "Bids",
  "Merkliste": "Watchlist",
  "Aufrufe": "Views",
  "Listing-Zahlen": "Listing stats",
  "Verkauf aktualisiert": "Sales updated",

  "{0} aktiv auf eBay": "{0} active on eBay",
  "{0} Entwürfe": "{0} drafts",
  "Gebot {0} · 1 Gebot": "Bid {0} · 1 bid",
  "Gebot {0} · {1} Gebote": "Bid {0} · {1} bids",
  "Auktion ab {0}": "Auction from {0}",
  "Auktion": "Auction",
  "Festpreis": "Fixed price",
  "Ja": "Yes", "Zurücksetzen": "Reset", "Gestalten": "Customize", "Alle": "All",
  "Fehler": "Error", "Erklärung": "Explanation",
  "⚙️ Verkaufs-Vorlage (Format · Preis · Hintergrund)":
    "⚙️ Selling template (format · price · background)",

  /* ── Login ── */
  "E-Mail-Adresse oder Benutzername": "Email or username", "du@mail.de": "you@mail.com",
  "Dein Anmeldecode": "Your sign-in code",
  "SERO hat dir einen Code geschickt.": "SERO sent you a code.",
  "SERO hat dir den Code per Telegram geschickt.": "SERO sent the code to your Telegram.",
  "Anmelden": "Sign in",
  "Noch kein Konto? Registrierung und Abo verwaltest du auf der SERO-Website.":
    "No account yet? Sign-up and subscription are handled on the SERO website.",
  "Den Anmeldecode bekommst du von Sven (Telegram).":
    "You’ll get the login code from Sven (Telegram).",
  "Den Anmeldecode schickt SERO an deine E-Mail.":
    "SERO sends the sign-in code to your email.",
  "Telefonnummer": "Phone number",
  "Code senden": "Send code",
  "Dein SMS-Code": "Your SMS code",
  "SMS kostet — nur wenn der Versand eingerichtet ist.":
    "SMS costs money — only when delivery is set up.",
  "Zurück": "Back",
  "Mit Google anmelden": "Sign in with Google",
  "Mit Telegram anmelden": "Sign in with Telegram",
  "Mit Telefon anmelden": "Sign in with phone",
  "Telefon-Login ist noch nicht eingerichtet.":
    "Phone sign-in is not set up yet.",
  "Telegram-Login ist noch nicht eingerichtet.":
    "Telegram sign-in is not set up yet.",
  "Google-Login ist noch nicht eingerichtet.":
    "Google sign-in is not set up yet.",
  "SMS-Code geschickt.": "SMS code sent.",
  "Konto angelegt. Prüfe deine E-Mail für den Code.":
    "Account created. Check your email for the code.",
  "Schon ein Konto?": "Already have an account?",
  // Der Textknoten vor dem Knopf ist ein eigener Schlüssel. Ohne ihn stand auf
  // dem englischen Login „Noch kein Konto? Create account“ — zwei Sprachen.
  "Noch kein Konto?": "No account yet?",
  "Konto erstellen": "Create account",
  "Benutzername": "Username",
  "E-Mail": "Email",
  "Dein Code geht an Sven per Telegram — er gibt ihn dir.":
    "Your code goes to Sven on Telegram — he’ll give it to you.",
  "Konto angelegt. Code kommt von Sven.": "Account created. Code comes from Sven.",
  "Bitte E-Mail und Benutzername angeben.": "Please enter email and username.",
  "Benutzername: 3–24 Zeichen, nur Buchstaben, Zahlen, Punkt oder Unterstrich.":
    "Username: 3–24 characters, letters, numbers, dot or underscore only.",
  "oder weiter mit": "or continue with",
  "Mit {0} anmelden": "Sign in with {0}",
  "Test-Modus (kein Mailversand) — dein Code: {0}": "Test mode (no email sent) — your code: {0}",

  /* ── Tour ── */
  "Fotografiere eine Karte oder ein Sammlerstück — SERO erkennt es automatisch und ermittelt den echten Marktwert.":
    "Photograph a card or collectible — SERO identifies it automatically and pulls the real market price.",
  "Deine Sammlung bekommt einen Gesamtwert mit täglichem Verlauf, Preisalarmen und Cardmarket-Daten.":
    "Your collection gets a total value with a daily history, price alerts and Cardmarket data.",
  "Ein Tipp erstellt ein fertiges eBay-Listing — Titel, Beschreibung, Preis. Live geht es erst nach deinem Okay.":
    "One tap creates a finished eBay listing — title, description, price. It only goes live once you approve.",

  /* ── Sammlung: leerer Zustand & Hero ── */
  "Deine Sammlung startet hier": "Your collection starts here",
  "Scanne deine erste Karte — SERO erkennt sie, ermittelt den Marktwert und macht sie mit einem Tipp eBay-fertig.":
    "Scan your first card — SERO identifies it, fetches the market price and makes it eBay-ready in one tap.",
  "Aus eBay-Listings importieren": "Import from eBay listings",
  "Erstes Stück scannen": "Scan your first item", "Jetzt scannen": "Scan now",
  "Sammlungswert": "Collection value",
  "Weitere Karten": "Other cards",
  "Manga": "Manga",
  "Comics": "Comics",
  "Listing-Design": "Listing design",
  "eBay-Wert": "eBay value",
  "Verkaufswert": "Sold value",
  "Wert · {0}": "Value · {0}",
  "Weiter zum Listen": "Continue to list",
  "Preis festlegen — danach öffnet sich der Entwurf zum Listen auf eBay.":
    "Set the price — then the draft opens so you can list on eBay.",
  "Ansicht wechseln": "Change view",
  "Stücke": "items", "auf eBay": "on eBay", "Favoriten": "Favorites", "Wunschliste": "Wishlist",
  "Entwürfe ({0})": "Drafts ({0})", "Verkauft ({0})": "Sold ({0})", "Katalog-Bilder": "Catalog images",
  "Katalog-Bilder im Grid": "Catalog images in grid",
  "Erkannt": "Recognized", "Zum Stück": "Open item", "Weiter scannen": "Scan another",
  "Stück in der Sammlung": "Item is in the collection",
  "Die Erkennung läuft im Hintergrund.": "Recognition runs in the background.",
  "Mit dem Entwurf fortsetzen": "Continue with the draft",
  "In der Sammlung anschauen": "View in the collection",
  "Scan": "Scan",
  "Foto wird übernommen …": "Saving the photo …",
  "Foto konnte nicht gespeichert werden.": "The photo could not be saved.",
  "Deine ehrliche Rechnung": "Your honest math", "{0} gespart": "{0} saved",
  "Aus {0} erfassten Stücken": "From {0} captured items", "Gespart": "Saved",
  "statt {0}": "instead of {0}", "{0} Min je Stück": "{0} min per item",
  "Ø {0} Sek je Scan": "avg. {0} sec per scan", "rund 2 Min je Stück": "about 2 min per item",
  "Nächster Meilenstein": "Next milestone",
  "Noch <b>{0}</b> Stücke bis {1}": "<b>{0}</b> more items to {1}",
  "Noch <b>1</b> Stück bis {0}": "<b>1</b> more item to {0}",
  "Gemessen an {0} Scans — wächst mit jedem neuen Stück.":
    "Measured across {0} scans — grows with every new item.",
  "Wächst mit jedem neuen Stück.": "Grows with every new item.",
  "{0} Stunden": "{0} hours", "{0} Minuten": "{0} minutes",
  "1 Stunde": "1 hour", "1 Minute": "1 minute", "{0} h": "{0} h", "{0} Min": "{0} min",
  "1 Min": "1 min", "1 Std": "1 hr", "{0} Std": "{0} hr",
  "Du hast {0} Stücke erfasst. Von Hand wären das rund {1} gewesen — mit SERO waren es {2}.":
    "You've captured {0} items. By hand that would have been about {1} — with SERO it was {2}.",
  "Von Hand": "By hand", "Mit SERO": "With SERO", "Weiter so": "Keep going",
  "{0} Stücke": "{0} items",
  "Von Hand wären das rund {0} gewesen. Mit SERO hast du {1} gespart.":
    "By hand that would have been about {0}. With SERO you saved {1}.",
  "Die ehrliche Rechnung": "The honest math",
  "100 Karten listen — einmal von Hand, einmal mit SERO.": "Listing 100 cards — by hand vs. with SERO.",
  "Std": "hrs", "Min": "min",
  /* ── Startseite: SERO-Effekt, Aktivität, FAQ ── */
  "Dein SERO-Effekt": "Your SERO effect",
  "Zeit gespart": "Time saved",
  "mit 1 erfassten Stück": "with 1 captured item",
  "mit {0} erfassten Stücken": "with {0} captured items",
  "So wird gerechnet": "How this is calculated",
  "Berechnung schließen": "Close calculation",
  "Letzte 7 Tage": "Last 7 days",
  "gescannt": "scanned",
  "neu gelistet": "newly listed",
  "verkauft": "sold",
  "live": "live",
  "Ø technische Analysezeit": "Avg. technical analysis time",
  "läuft im Hintergrund": "runs in the background",
  "SERO rechnet mit 15 Minuten von Hand und 2 Minuten mit SERO — je erfolgreichem Scan. Von Hand: bestimmen, echte Verkaufsbelege prüfen, Foto vorbereiten, Titel schreiben und eBay-Pflichtfelder setzen. Mit SERO: fotografieren, Ergebnis prüfen und freigeben. Die technische Analyse im Hintergrund zählt nicht als deine Arbeitszeit.":
    "SERO counts 15 minutes by hand and 2 minutes with SERO — per successful scan. By hand: identify, check real sold comps, prepare the photo, write the title and fill eBay required fields. With SERO: photograph, check the result and approve. Background analysis time is not counted as your work time.",
  "Karte bestimmen, verkaufte Angebote durchsehen, Foto zuschneiden, Titel und Pflichtfelder setzen — 15 Minuten pro Stück.":
    "Identify the card, check sold listings, crop the photo, write the title and fill required fields — 15 minutes per item.",
  "Fotografieren, Ergebnis prüfen, freigeben — 2 Minuten pro Stück. 100 Karten, 200 Minuten.":
    "Shoot, check, approve — 2 minutes per item. 100 cards, 200 minutes.",
  "Von Hand 15 Minuten je Stück (bestimmen, Marktwert, Foto, Titel und Pflichtfelder). Mit SERO 2 Minuten — nicht die Scan-Dauer im Hintergrund, sondern deine aktive Zeit inklusive Hinlegen, Prüfen und Freigeben.":
    "By hand 15 minutes per item (identify, market value, photo, title and required fields). With SERO 2 minutes — not background scan time, but your active time including placing, checking and approving.",
  "Häufige Fragen": "Frequently asked questions",
  "Brauche ich einen eBay-Developer-Account?": "Do I need an eBay developer account?",
  "Nein. Kein Developer-Account, keine API-Keys. Du nimmst dein normales eBay-Verkäuferkonto: anmelden, Freigabe erteilen, den Link zurück in die App einfügen, fertig. SERO sieht dein Passwort nie.":
    "No. No developer account, no API keys. Use your regular eBay seller account: sign in, approve access, paste the link back into the app, done. SERO never sees your password.",
  "Kann SERO etwas ohne mein Okay veröffentlichen?": "Can SERO publish anything without my okay?",
  "Nein. Ohne deinen Tipp geht nichts live — auch nicht versehentlich. Jedes Listing wartest du dir an und gibst es erst dann frei.":
    "No. Nothing goes live without your tap — not even by accident. You review every listing and only then approve it.",
  "Liest SERO wirklich PSA-Labels vom Foto?": "Does SERO really read PSA labels from the photo?",
  "Ja. Vom Slab-Foto kommen Bewerter, Note und Zertifikatsnummer in die eBay-Felder. Ist das Label unscharf, fragt SERO nach — geraten wird nicht.":
    "Yes. From the slab photo, grader, grade and cert number go into the eBay fields. If the label is blurry, SERO asks — it does not guess.",
  "Was passiert mit meinen Daten und Fotos?": "What happens to my data and photos?",
  "Deine Fotos und Stückdaten bleiben bei dir im Konto, solange das Stück in der Sammlung ist. Die eBay-Freigabe liegt verschlüsselt in der EU. Verkauft werden deine Daten nicht — bezahlt wird das Abo.":
    "Your photos and item data stay in your account as long as the item is in your collection. The eBay access token is stored encrypted in the EU. Your data is not sold — you pay for the subscription.",
  "Welche Stücke funktionieren am besten?": "Which items work best?",
  "Am besten, wofür SERO gebaut ist: Sammelkarten roh und graded, Retro- und Videospiele, Manga und Comics. Andere Sammlerware oft auch — Alltagsprodukte eher nebenbei.":
    "Best for what SERO is built for: trading cards raw and graded, retro and video games, manga and comics. Other collectibles often work — everyday products are secondary.",
  "Kann ich jederzeit kündigen?": "Can I cancel any time?",
  "Ja. Monatlich im Konto kündbar, ohne Mindestlaufzeit und ohne Anruf.":
    "Yes. Cancel monthly in your account, with no minimum term and no phone call.",
  "{0} Sek": "{0} sec", "Sekunden": "Seconds", "pro Stück": "per item",
  "Felder": "fields", "von Hand": "by hand", "Grader": "graders", "Stücke erfasst": "items captured",
  "Neues Stück": "New item", "Wert wird noch ermittelt": "Determining value …",
  "Kein belegter Marktwert — trag deinen Preis beim Listen selbst ein": "No verified market value — enter your own price when listing",
  "eBay-Setup abschließen": "Finish eBay setup",
  "eBay braucht einen Versandstandort. Die Adresse wird nicht öffentlich angezeigt.": "eBay needs a shipping location. The address is never shown publicly.",
  "Straße und Hausnummer": "Street and number", "PLZ": "ZIP", "Stadt": "City",
  "Vorhandene Verkaufsrichtlinien aus deinem eBay-Konto werden übernommen — es wird nichts doppelt angelegt.": "Existing selling policies from your eBay account are reused — nothing is created twice.",
  "Setup abschließen": "Finish setup",
  "eBay verbinden": "Connect eBay",
  "Neu verbinden": "Reconnect",
  "eBay neu verbinden": "Reconnect eBay",
  "Angemeldet": "Signed in",
  "eBay verbunden": "eBay connected",
  "eBay verbunden — Bestellungen noch einmal prüfen": "eBay connected — check orders once more",
  "eBay-Verbindung fehlgeschlagen": "eBay connection failed",
  "Verbindung prüfen": "Check connection",
  "eBay öffnet sich in einem neuen Tab. Diese App bleibt offen — nach der Freigabe tippe „Verbindung prüfen“, oder warte kurz.":
    "eBay opens in a new tab. This app stays open — after approving, tap “Check connection”, or wait a moment.",
  "Noch nicht verbunden. Nach der Freigabe bei eBay hier erneut tippen — oder die Adresse einfügen.":
    "Not connected yet. After approving on eBay, tap here again — or paste the address.",
  "Damit Verkäufe und Preisvorschläge korrekt erkannt werden, verbinde eBay einmal neu.":
    "So sales and offers are detected correctly, reconnect eBay once.",
  "Damit Verkäufe korrekt erkannt werden, brauchst du den Scope für Bestellungen. Tippe unten — danach prüft SERO die Verbindung.":
    "So sales are detected correctly, you need the orders scope. Tap below — then SERO checks the connection.",
  "Bevor das Setup starten kann, verbinde zuerst dein eBay-Konto.":
    "Before setup can start, connect your eBay account first.",
  "Du wirst zu eBay weitergeleitet und landest danach wieder in der App.":
    "You'll be taken to eBay and then return to the app.",
  "Du wirst zu eBay weitergeleitet. Danach kannst du das Setup hier fortsetzen.":
    "You'll be taken to eBay. Afterwards you can continue setup here.",
  "Damit Verkäufe korrekt erkannt werden, verbinde eBay einmal neu.":
    "So sales are detected correctly, reconnect eBay once.",
  "Bevor das Setup starten kann, verbinde zuerst dein eBay-Konto.":
    "Before setup can start, connect your eBay account first.",
  "Tippe auf „eBay verbinden“ — du wirst zu eBay weitergeleitet und landest danach wieder in der App.":
    "Tap “Connect eBay” — you'll be taken to eBay and then return to the app.",
  "Website öffnen": "Open website",
  "eBay-Adresse einfügen": "Paste eBay address",
  "Wenn du nach der Freigabe nicht automatisch zurückkommst: kopiere die komplette Adresse aus der Browser-Zeile und füge sie hier ein.":
    "If you are not returned automatically after approving: copy the full address from the browser bar and paste it here.",
  "https://auth.ebay.com/…?code=…": "https://auth.ebay.com/…?code=…",
  "Verbindung speichern": "Save connection",
  "eBay-Setup fortsetzen": "Continue eBay setup",
  "Kein code= in der URL gefunden.": "No code= found in the URL.",
  "Setup abgeschlossen — du kannst jetzt listen": "Setup complete — you can list now",
  "Deine Gratis-Scans sind aufgebraucht": "You've used all your free scans",
  "Mit SERO Premium scannst du ohne Limit weiter.": "SERO Premium removes the scan limit.",
  "Scans genutzt": "scans used", "Unbegrenzte Scans": "Unlimited scans",
  "Preisalarme für deine Stücke": "Price alerts for your items",
  "Portfolio-Verlauf & Statistiken": "Portfolio history & statistics",
  "Cloud-Backup deiner Sammlung": "Cloud backup of your collection",
  "SERO Premium holen": "Get SERO Premium", "Noch {0} Scans frei": "{0} scans left",
  "Keine Gratis-Scans mehr": "No free scans left", "Premium": "Premium",
  "Noch {0} Gratis-Scans": "{0} free scans left",
  "Rückseite fotografieren": "Photograph the back", "Weiteres Foto": "Another photo",
  "Weiteres Foto hinzufügen": "Add another photo",
  "Tipp auf ein Foto macht es zum Hauptbild.": "Tap a photo to make it the main image.",
  "{0} von 8 Fotos — Tipp wählt das Hauptbild.": "{0} of 8 photos — tap to set the main image.",
  "Zuletzt gescannt": "Recently scanned", "Alle anzeigen": "Show all", "Verkaufs-Vorlage": "Selling template",
  "SERO erkennt jedes Stück, ermittelt den Marktwert und legt einen eBay-Entwurf an.":
    "SERO identifies each item, finds the market value and creates an eBay draft.",
  "SERO erkennt jedes Stück und ermittelt den Marktwert.": "SERO recognizes every item and determines its market value.",
  "SERO erkennt jedes Stück und erstellt den eBay-Entwurf nach deiner Vorlage.": "SERO recognizes every item and creates the eBay draft from your template.",
  "SERO erkennt jedes Stück deiner Sammlung.": "SERO recognizes every piece of your collection.",
  "KI-Richtwert": "AI estimate",
  "KI-Richtwert — bitte prüfen, Preis ist änderbar": "AI estimate — please check, you can change the price",
  "Unsicherer Richtwert — bitte prüfen und bei Bedarf manuell ändern.":
    "Uncertain estimate — please check and change manually if needed.",
  "Wird analysiert …": "Analyzing …", "Wert unbekannt": "Value unknown",
  "Produktart ist unklar": "Product type is unclear",
  "Spiel oder Marke fehlt": "Game or brand is missing",
  "Name fehlt": "Name is missing",
  "Kartennummer fehlt": "Card number is missing",
  "Set oder Nenner fehlt": "Set or set total is missing",
  "Sprache fehlt": "Language is missing",
  "Auflage oder Edition fehlt": "Edition is missing",
  "Grader fehlt": "Grader is missing",
  "Note fehlt": "Grade is missing",
  "Label-Typ fehlt (z. B. Pristine oder Gem Mint)": "Label type is missing (e.g. Pristine or Gem Mint)",
  "Plattform fehlt": "Platform is missing",
  "Region fehlt": "Region is missing",
  "Vollständigkeit fehlt (lose, CIB, sealed)": "Completeness is missing (loose, CIB, sealed)",
  "Serie fehlt": "Series is missing",
  "Band oder Ausgabe fehlt": "Volume is missing",
  "Marke fehlt": "Brand is missing",
  "Modell fehlt": "Model is missing",
  "preisrelevante Variante fehlt": "Price-relevant variant is missing",
  "Ein Merkmal ist nur geraten oder ungeprüft": "A detail is only guessed or unchecked",
  "Mehrere Modelle passen — bitte tippen": "Several models fit — please tap to confirm",
  "Alte Erkennung — bitte prüfen": "Old recognition — please check",
  "Identität prüfen": "Check identity",
  "Wert unbekannt — Identität unklar": "Value unknown — identity unclear",
  "Keine Treffer": "No matches", "Für diese Filter gibt es gerade nichts.": "Nothing matches these filters right now.",
  "Noch nichts live": "Nothing live yet", "Zur Sammlung": "Go to collection", "Ansicht wechseln": "Change view",
  "Werte verbergen": "Hide values", "Werte anzeigen": "Show values",
  "Preise aktualisieren": "Refresh prices",
  "Foto entfernen": "Remove photo", "nach vorn": "move forward", "nach hinten": "move back",
  "Senden": "Send", "Weniger": "Less",
  "Liste": "List", "Kacheln": "Tiles", "Große Kacheln": "Large tiles", "Kleine Kacheln": "Small tiles",
  "Liste ein Stück aus deiner Sammlung — SERO baut das Angebot fertig auf.":
    "List an item from your collection — SERO builds the whole listing.",
  "Keine offenen Entwürfe": "No open drafts",
  "Entwürfe entstehen, wenn du ein Stück zum Listen vorbereitest.":
    "Drafts appear when you prepare an item for listing.",
  "Noch nichts beendet": "Nothing ended yet",
  "Noch nichts verkauft": "Nothing sold yet",
  "Hier erscheinen Stücke, die über SERO auf eBay verkauft wurden.":
    "Items sold through SERO on eBay appear here.",
  "Festpreis · live auf eBay": "Fixed price · live on eBay",
  "Auktion · noch ohne Gebot": "Auction · no bids yet",
  "Verkaufspreis · beendet": "Sale price · ended",
  "Live auf eBay — Format steht fest. Preis, Titel und Beschreibung kannst du ändern und speichern.":
    "Live on eBay — format is fixed. You can change and save price, title and description.",
  "Live auf eBay — Format steht fest. Titel und Beschreibung kannst du speichern.":
    "Live on eBay — format is fixed. You can save title and description.",
  "tippen zum Ändern": "tap to change",
  " · Verkauft": " · Sold",
  "Hier landen Angebote, die verkauft oder abgelaufen sind.":
    "Listings that sold or expired end up here.",
  "Noch keine Stücke": "No items yet",
  "Scanne dein erstes Stück — Marktwert und Verlauf entstehen automatisch.":
    "Scan your first item — market value and history build automatically.",
  "Aus Sammlung entfernt": "Removed from collection", "Rückgängig": "Undo",
  "Wiederhergestellt": "Restored",
  "Favorit entfernt": "Removed from favorites", "Als Favorit markiert": "Marked as favorite",

  /* ── Sortieren & Filtern ── */
  "Neueste zuerst": "Newest first", "Wert (hoch → niedrig)": "Value (high → low)",
  "Wert (niedrig → hoch)": "Value (low → high)", "Name (A–Z)": "Name (A–Z)",
  "Name (Z–A)": "Name (Z–A)",
  "Zuletzt hinzugefügt": "Date added",
  "Wert (höchster zuerst)": "Value (highest first)",
  "Wert (niedrigster zuerst)": "Value (lowest first)",
  "Zuletzt bearbeitet": "Last edited",
  "Bald endend": "Ending soonest",
  "Neu eingestellt": "Newly listed",
  "Zuletzt verkauft": "Recently sold",
  "Preis (höchster zuerst)": "Price (highest first)",
  "Preis (niedrigster zuerst)": "Price (lowest first)",
  "Titel, Set, Cert-Nr.": "Title, set, cert no.",
  "Titel, Artikelnummer": "Title, item number",
  "Roh": "Raw", "Graded": "Graded",
  "Grading": "Grading", "Note": "Grade",
  "Sprache": "Language", "Region": "Region",
  "Deutsch": "German", "Englisch": "English", "Japanisch": "Japanese",
  "Andere": "Other",
  "Von": "From", "Bis": "To",
  "Jahr": "Year",
  "{0}: „Bis“ ist kleiner als „Von“. Bitte Werte tauschen.":
    "{0}: “To” is lower than “From”. Please swap the values.",
  "ab {0} €": "from {0} €",
  "bis {0} €": "up to {0} €",
  "{0}–{1} €": "{0}–{1} €",
  "Alles zurücksetzen": "Clear all",
  "Anwenden": "Apply",
  "TCG Sonstiges": "Other TCG",
  "Games": "Games",
  "Sonstiges": "Other",
  "LIVE": "LIVE", "ENTWURF": "DRAFT", "VERKAUFT": "SOLD",
  "Fotografieren, prüfen, in die Sammlung legen.": "Photograph, review, add to the collection.",
  "Keine Treffer für „{0}“": "No results for “{0}”",
  "Suchbegriff kürzen oder Filter zurücksetzen.": "Shorten the search or reset filters.",
  "Größte Preisbewegung": "Biggest price move",
  "Nur Favoriten": "Favorites only", "Dubletten (×2+)": "Duplicates (×2+)",
  "Auf eBay": "On eBay", "Tags": "Tags", "Filter zurücksetzen": "Reset filters",
  "{0} Listings importiert": "{0} listings imported",
  "Nichts Neues zu importieren": "Nothing new to import",

  /* ── Portfolio-Karte gestalten ── */
  "Karte gestalten": "Customize card",
  "Portfolio-Hintergrund": "Portfolio background",
  "Wähle Farbe, Verlauf oder ein eigenes Foto als Hintergrund.":
    "Pick a color, gradient or your own photo as the background.",
  "Hintergrund gesetzt": "Background set",
  "Hintergrund zurückgesetzt": "Background reset",
  "SERO Navy": "SERO Navy", "Ozean": "Ocean", "Wald": "Forest",
  "Violett": "Violet", "Graphit": "Graphite", "Gold": "Gold",
  "Eigene Farbe": "Custom color", "Eigenes Foto": "Own photo",
  "Foto gesetzt": "Photo set", "Foto zu groß. Wähle ein kleineres Bild.": "Photo too large. Choose a smaller image.",

  /* ── Dashboard ── */
  "hat {0} erreicht (Alarm {1} {2})": "reached {0} (alert {1} {2})",
  "über": "above", "unter": "below",
  "eBay-Konto verbinden": "Connect eBay account",
  "Verkaufs-Setup abschließen": "Complete selling setup",
  "Fast startklar": "Almost ready", "{0} von {1} Schritten": "{0} of {1} steps",
  " · Karten + NFTs": " · cards + NFTs",
  "Deine gesamte Sammlung ist gerade im Verkauf ({0})":
    "Your entire collection is currently listed for sale ({0})",
  "Verlauf entsteht ab dem zweiten Tag": "History starts on day two",
  "Noch kein Verlauf": "No history yet",
  "insgesamt": "in total",
  "in den letzten 7 Tagen": "in the last 7 days", "in den letzten 30 Tagen": "in the last 30 days",
  "30 Tage": "30 days",
  "seit Start": "since start",
  "7T": "7D", "30T": "30D", "1J": "1Y", "1M": "1M", "Max": "Max",
  "Verlauf ab dem ersten Scan": "History from the first scan",
  "Erlös": "Proceeds",
  "Besitz": "Owned",
  "Daten / Export": "Data / export",
  "Aus": "Off",
  "An": "On",
  "eBay verbinden": "Connect eBay",
  "Darstellung": "Appearance",
  "in Sammlung": "in collection", "im Verkauf ({0})": "listed ({0})",
  "Wertvollste Stücke": "Most valuable", "Alle ansehen": "View all", "Kategorien": "Categories",
  "{0} Stücke": "{0} items", "Deine NFTs (Solana)": "Your NFTs (Solana)",
  "Floor unbekannt": "Floor unknown",
  "Kommende Releases": "Upcoming releases", "TCG-News": "TCG news",
  "Deine Sammlung": "Your collection", "Wert": "Value", "Bewegung": "Movement",
  "Zahlen": "Numbers", "Deine NFTs": "Your NFTs",
  "Dein Name": "Your name", "Sammler seit {0}": "Collector since {0}",
  "Dein Name erscheint in der App und in deinen Exporten.": "Your name appears in the app and in your exports.",
  "Anmelde-Kennung": "Sign-in handle", "z. B. sammler_muc": "e.g. collector_muc",
  "Mit dieser Kennung kannst du dich statt mit der E-Mail anmelden. Änderst du sie, gilt sofort die neue.":
    "You can sign in with this handle instead of your email. If you change it, the new one applies immediately.",
  "Sichern": "Save", "Profil gespeichert": "Profile saved",
  "{0} Punkte": "{0} points", "noch {0} bis {1}": "{0} more to {1}",
  "Neu": "New", "Sammler": "Collector", "Kenner": "Connoisseur", "Kurator": "Curator", "Archivar": "Archivist",
  "Stücke erfasst": "items captured", "vollständig bestimmt": "fully identified",
  "Grading erkannt": "grading detected", "gelistet": "listed", "verkauft": "sold",
  "Deine Sets": "Your sets", "Live": "Live", "Entwurf": "Draft", "Wunsch": "Wish", "Verkauft": "Sold",
  "Rückgängig": "Undo", "Filter zurücksetzen": "Reset filters",
  "Hilfe": "Help",
  "Hilfe & Kontakt": "Help & contact", "Datenschutz": "Privacy", "Nutzungsbedingungen": "Terms",
  "Solana-Wallet": "Solana wallet", "Verbunden": "Connected",
  "NEU": "NEW", "HEUTE": "TODAY", "in {0} Tagen": "in {0} days",
  "Preise aktualisiert ({0} von {1})": "Prices updated ({0}/{1})",
  "erschienen am {0}": "released on {0}", "erscheint HEUTE": "releases TODAY",
  "erscheint in 1 Tag — {1}": "releases in 1 day — {1}",
  "erscheint in {0} Tagen — {1}": "releases in {0} days — {1}",

  /* ── Preisquellen ── */
  "Cardmarket-Trend": "Cardmarket trend",
  "Cardmarket ist Europas größter Marktplatz für Sammelkarten. Der Trend-Preis ist der geglättete Durchschnitt der tatsächlichen Verkaufspreise der letzten Tage — die verlässlichste Zahl für den aktuellen Wert deiner Karte. SERO aktualisiert ihn automatisch.":
    "Cardmarket is Europe's largest marketplace for trading cards. The trend price is the smoothed average of actual sale prices over the last few days — the most reliable figure for what your card is worth right now. SERO keeps it up to date automatically.",
  "eBay-Median": "eBay median",
  "SERO sucht aktuelle eBay-Sofortkauf-Angebote für vergleichbare Stücke, entfernt Ausreißer und nimmt den mittleren Preis (Median). Das zeigt, wofür vergleichbare Stücke gerade angeboten werden — Verkaufspreise können leicht darunter liegen.":
    "SERO looks up current eBay Buy It Now offers for comparable items, drops the outliers and takes the middle price (median). That shows what comparable items are being asked for right now — actual sale prices can be slightly lower.",
  "KI-Schätzung": "AI estimate",
  "KI-Schätzung (veraltet)": "AI estimate (outdated)",
  "Dieser Wert stammt aus einer früheren KI-Einschätzung. SERO vergibt solche Werte nicht mehr — beim nächsten Preis-Update wird er durch echte Marktdaten ersetzt oder ehrlich als unbekannt angezeigt.":
    "This value comes from an earlier AI estimate. SERO no longer assigns such values — the next price update replaces it with real market data or honestly shows it as unknown.",
  "Cardmarket (Scryfall)": "Cardmarket (Scryfall)",
  "Der aktuelle Cardmarket-Preis dieser Magic-Karte, bezogen über die freie Scryfall-Datenbank.":
    "The current Cardmarket price of this Magic card, sourced from the free Scryfall database.",
  "Cardmarket (YGOPRODeck)": "Cardmarket (YGOPRODeck)",
  "Der aktuelle Cardmarket-Preis dieser Yu-Gi-Oh-Karte, bezogen über die freie YGOPRODeck-Datenbank.":
    "The current Cardmarket price of this Yu-Gi-Oh card, sourced from the free YGOPRODeck database.",
  "Listing-Preis": "Listing price",
  "Dieses Stück wurde aus deinen eBay-Listings importiert — als Wert dient dein Angebotspreis, bis SERO eine echte Marktquelle findet (Preis aktualisieren antippen).":
    "This item was imported from your eBay listings — your asking price is used as its value until SERO finds a real market source (tap Refresh price).",
  "Woher kommt dieser Preis?": "Where does this price come from?",
  "Automatisch ermittelter Schätzwert.": "Automatically determined estimate.",

  /* ── Zustände (eBay) ── */
  "Neu": "New", "Neuwertig": "Like new", "Neu (sonstige)": "New (other)",
  "Neu mit Fehlern": "New with defects", "Zertifiziert refurbished": "Certified refurbished",
  "Refurbished (exzellent)": "Refurbished (excellent)",
  "Refurbished (sehr gut)": "Refurbished (very good)", "Refurbished (gut)": "Refurbished (good)",
  "Vom Verkäufer aufbereitet": "Seller refurbished",
  "Gebraucht — exzellent": "Used — excellent", "Gebraucht — sehr gut": "Used — very good",
  "Gebraucht — gut": "Used — good", "Gebraucht — akzeptabel": "Used — acceptable",
  "Gebraucht — okay": "Used — fair", "Defekt / für Bastler": "For parts / not working",
  "Professionell bewertet (Graded)": "Professionally graded",
  "Nicht bewertet (Ungraded)": "Ungraded",
  "1. Edition": "1st Edition",

  /* ── Scanner-first Copy ── */
  "Scannen. Prüfen. Bei eBay verkaufen.": "Scan. Review. Sell on eBay.",
  "Bald im App Store und für Android": "Available soon in the App Store and on Android",
  "Fertiger eBay-Entwurf direkt nach dem Scan": "Ready eBay draft right after the scan",
  "Alles prüfen und ändern, bevor etwas live geht": "Review and edit everything before anything goes live",
  "Bei eBay erst nach deiner Freigabe": "Live on eBay only after you approve",
  "SERO erkennt dein Produkt und bereitet dein eBay-Angebot vor.": "SERO recognizes your product and prepares your eBay listing.",
  "Artikel fotografieren": "Photograph item",
  "Mehrere Produkte scannen": "Scan multiple products",
  "Nur zur Sammlung hinzufügen": "Add to collection only",
  "Analysieren & Entwurf erstellen": "Analyze & create draft",
  "Entwurf prüfen": "Review draft",
  "A · Bilder": "A · Photos",
  "B · Produkt": "B · Product",
  "C · Angebot": "C · Offer",
  "D · Versand & Regeln": "D · Shipping & rules",
  "Bilder bearbeiten": "Edit photos",
  "Dein Freisteller ist das Hauptbild. Tippe auf Bilder für Zuschnitt, Drehen und Hintergrund.": "Your cutout is the main photo. Tap Photos for crop, rotate and background.",
  "Dein Freisteller ist das Hauptbild. Tippe auf ein Bild für Zuschnitt, Drehen, Hintergrund und Freistellen.":
    "Your cutout is the main photo. Tap a photo for crop, rotate, background and cut-out.",
  "Reihenfolge, Hauptbild, Freisteller und Neu-Rendern an einem Ort.":
    "Order, main photo, cutout toggle and re-render in one place.",
  "Pro Foto zwischen Freisteller und Original wechseln.": "Toggle cutout vs original per photo.",
  "Identität": "Identity",
  "Pflichtmerkmale": "Required specifics",
  "Fehlt — tippen": "Missing — tap",
  "Prüfung vor dem Publish": "Checks before publish",
  "Noch nicht bereit zum Veröffentlichen": "Not ready to publish yet",
  "Noch {0} Angaben": "{0} details left",
  "Angaben prüfen oder Rückfrage beantworten — Publish bleibt gesperrt, bis alles klar ist.": "Review details or answer the question — publish stays locked until everything is clear.",
  "Erst Angaben prüfen": "Review details first",
  "Kategorie wählen": "Choose category",
  "Suche die passende eBay-Kategorie — Pflichtmerkmale werden danach neu geladen.": "Search for the right eBay category — required specifics reload afterwards.",
  "z. B. One Piece Einzelkarte": "e.g. One Piece single card",
  "Nichts gefunden — anderen Suchbegriff tippen.": "Nothing found — try another search term.",
  "Kategorie gesetzt": "Category set",
  "Setup im Profil öffnen": "Open profile setup",
  "Versand und Richtlinien im Profil prüfen": "Check shipping and policies in profile",
  "Bereit": "Ready",
  "Fehlt — Setup im Profil": "Missing — finish profile setup",
  "Versandrichtlinie": "Shipping policy",
  "Zahlungsrichtlinie": "Payment policy",
  "Rücknahmerichtlinie": "Return policy",
  "Versandstandort": "Ship-from location",
  "eBay-Konto": "eBay account",
  "Kein Sammlungsstück verknüpft": "No collection item linked",
  "Falsche Karte? Von Hand neu zuordnen.": "Wrong card? Match it by hand.",
  "Tippen zum Wählen": "Tap to choose",
  "Pflichtmerkmal für diese eBay-Kategorie": "Required specific for this eBay category",
  "Suche …": "Searching…",
  "eBay-Entwurf vorbereiten": "Prepare eBay draft",
  "Jetzt bei eBay veröffentlichen": "Publish on eBay now",
  "Live bei eBay": "Live on eBay",
  "Standard für eBay-Entwürfe": "Default for eBay drafts",
  "Standard für eBay-Entwürfe gespeichert": "Default for eBay drafts saved",
  "Fotografieren. Prüfen. Bei eBay verkaufen.": "Photograph. Review. Sell on eBay.",
  "SERO bereitet aus deinem Foto einen editierbaren eBay-Entwurf vor. Live geht es erst nach deiner Freigabe.": "SERO turns your photo into an editable eBay draft. Nothing goes live until you approve.",
  "Automatische Vorbereitung von Titel, Kategorie und Preisvorschlag": "Automatic prep of title, category and price suggestion",
  "Alles änderbar, bevor etwas live geht": "Everything editable before anything goes live",
  "Veröffentlichen nur mit bewusstem Tipp": "Publish only with a deliberate tap",
  "eBay verbunden — Entwürfe kannst du freigeben": "eBay connected — you can approve drafts",
  "eBay verbunden — Verkaufs-Setup noch abschließen": "eBay connected — finish selling setup",
  "Noch nicht mit eBay verbunden — Entwurf geht trotzdem": "Not connected to eBay yet — draft still works",
  "{0} Entwürfe warten auf Prüfung": "{0} drafts waiting for review",
  "Erstes Listing vorbereiten": "Prepare first listing",
  "Fotografieren": "Take a photo",
  "Aus der Mediathek": "From the photo library",
  "Keine Kamera an diesem Gerät — wähle ein Foto aus der Mediathek.":
    "No camera on this device — pick a photo from the library.",
  "Noch kein Listing vorbereitet": "No listing prepared yet",
  "Fotografiere dein erstes Stück — SERO baut den eBay-Entwurf, die Sammlung wächst nebenbei.": "Photograph your first item — SERO builds the eBay draft; collection grows alongside.",
  "Nur in Sammlung behalten": "Keep in collection only",
  "eBay-Entwurf": "eBay draft",
  "Verkaufen": "Sell",
  "Listings": "Listings",
  "Portfolio": "Portfolio",
  "Entwürfe, Live, Verkauft": "Drafts, live, sold",
  "Live ({0})": "Live ({0})",
  "Aktiv ({0})": "Active ({0})",
  "Auf eBay hochladen": "Upload to eBay",
  "{0} Stück auf eBay hochladen": "Upload {0} items to eBay",
  "Alle auswählen": "Select all",
  "{0} ausgewählt": "{0} selected",
  "Auswahl aufheben": "Clear selection",
  "Versand eingerichtet": "Shipping set up",
  "Versand fehlt": "Shipping missing",
  "Verkauf nicht geladen": "Sales not loaded",
  "Erneut laden": "Reload",
  "Übersprungen — unvollständig": "Skipped — incomplete",
  "Stück {0} von {1}": "Item {0} of {1}",
  "{0} veröffentlicht, {1} unvollständig, {2} fehlgeschlagen":
    "{0} published, {1} incomplete, {2} failed",
  "Listing {0}": "Listing {0}",
  "Preis fehlt": "Price missing",
  "Titel fehlt": "Title missing",
  "Zustand fehlt": "Condition missing",
  "Noch nicht bereit": "Not ready yet",
  "Bitte diese Punkte prüfen — erst dann kannst du veröffentlichen.": "Fix these points first — then you can publish.",
  "Angaben unvollständig": "Details incomplete",
  "Bei eBay veröffentlichen?": "Publish on eBay?",
  "Kurz prüfen — danach geht der Entwurf live.": "Quick check — then the draft goes live.",
  "Zielmarktplatz eBay.de. Live erst nach diesem Tipp — kein zweiter automatischer Versuch bei unklarer Antwort.": "Marketplace eBay.de. Live only after this tap — no blind retry if the status is unclear.",
  "Ausgewählte Entwürfe veröffentlichen": "Publish selected drafts",
  "Nur geprüfte Entwürfe gehen nacheinander live — jeweils mit Preflight.": "Only reviewed drafts go live one by one — each with preflight.",
  "{0} Entwürfe werden veröffentlicht …": "Publishing {0} drafts …",
  "Willkommen": "Welcome",
  "Foto machen, prüfen, listen. Aus dem Scan wird ein eBay-Entwurf. Live geht nichts ohne deinen Tipp.": "Take a photo, review, list. The scan becomes an eBay draft. Nothing goes live without your tap.",
  "1 · Fotografieren": "1 · Photograph",
  "Tippe unten in der Mitte auf Scannen. SERO erkennt das Stück und baut Titel, Kategorie, Beschreibung und Preisvorschlag.": "Tap Scan in the center. SERO recognizes the item and builds title, category, description and price suggestion.",
  "2 · Entwurf prüfen": "2 · Review draft",
  "Alles bleibt änderbar: Bilder, Identität, Preis, Format, Zustand. Fehlende Angaben siehst du klar — nichts wird geraten und still übernommen.": "Everything stays editable: photos, identity, price, format, condition. Missing fields stay visible — nothing is silently guessed.",
  "3 · Bei eBay freigeben": "3 · Approve on eBay",
  "Erst der Tipp auf „Jetzt bei eBay veröffentlichen“ startet den Upload. Deine Sammlung wächst parallel automatisch mit.": "Only the tap on “Publish on eBay now” starts the upload. Your collection grows automatically alongside.",
  "Bereite ein Listing vor — prüfen, dann bewusst bei eBay veröffentlichen.": "Prepare a listing — review, then deliberately publish on eBay.",
  "Fotografiere ein Stück — SERO baut den eBay-Entwurf zur Prüfung.": "Photograph an item — SERO builds the eBay draft for review.",

  /* ── Scanner & Verkaufs-Vorlage ── */
  "Pokémon, One Piece, Magic, Yu-Gi-Oh, Lorcana, Dragon Ball & mehr — SERO erkennt Karte, Set und Sprache und holt tagesaktuelle Marktpreise. Auch stapelweise: Lade viele Fotos auf einmal hoch, SERO sortiert Vorder- und Rückseiten automatisch und stellt jede Karte frei.":
    "Pokémon, One Piece, Magic, Yu-Gi-Oh, Lorcana, Dragon Ball & more — SERO identifies card, set and language and pulls up-to-date market prices. Batches work too: upload many photos at once, SERO sorts fronts and backs automatically and cuts out every card.",
  "Verkaufs-Vorlage": "Selling template",
  "Gilt für jeden Scan — Format, Preisregel und Hintergrund für den eBay-Entwurf.":
    "Applies to every scan — format, price rule and background for the eBay draft.",
  "Gilt für jeden Scan im eBay-Verkauf-Modus — einmal einstellen, dann läuft alles automatisch durch.":
    "Applies to every scan in eBay selling mode — set it once and everything runs automatically.",
  "Format": "Format", "Sofortkauf": "Buy It Now", "Auktion": "Auction",
  "Preis": "Price", "Marktwert": "Market value", "Eigener Wert": "Your value", "Markt −10 %": "Market −10 %",
  "1 € Start": "€1 start", "Fest:": "Fixed:", "Festpreis in €": "Fixed price in €",
  "Listing-Hintergrund (gerendertes Produktbild)": "Listing background (rendered product image)",
  "Weiß": "White", "Warmweiß": "Warm white", "Schwarz": "Black", "Mein Logo": "My logo",
  "Verkaufs-Vorlage gespeichert": "Selling template saved",
  "Entwurf erstellt — liegt im Verkauf-Tab": "Draft created — find it in the Selling tab",
  "eBay-Verkauf": "eBay selling",
  "Verkaufs-Vorlage (Format · Preis · Hintergrund)": "Selling template (format · price · background)",
  "Alle {0} Entwürfe listen": "List all {0} drafts",
  "{0} Entwürfe werden gelistet …": "Listing {0} drafts …",
  "Alarm ausgelöst": "Alert triggered",

  /* ── Stapel-Scan & Scan prüfen ── */
  "Stapel-Scan": "Batch scan",
  "{0} Fotos — SERO ordnet Vorder- und Rückseiten automatisch zu. Slabs und Hüllen bleiben im Plastik.":
    "{0} photos — SERO sorts them automatically: front and back of the same card become ONE item. Slabs stay in the case; sleeves and toploaders stay in their plastic.",
  "Alle Fotos zeigen dasselbe Stück": "All photos show the same item",
  "Sortiere Fotos …": "Sorting photos …", "Automatisch sortieren": "Sort automatically",
  "{0} Fotos → {1} Stück erkannt": "{0} photos → {1} item identified",
  "{0} Fotos → {1} Stücke erkannt": "{0} photos → {1} items identified",
  " — Entwurf wird vorbereitet": " — draft is being prepared",
  " — werden automatisch gelistet": " — will be listed automatically",
  "Scan prüfen": "Check scan",
  "SERO erkennt das Stück und ermittelt den Marktwert.":
    "SERO identifies the item and fetches the market price automatically.",
  "Notiz (optional)":
    "Note (optional)",
  "Gescannt": "Scanned",
  "Die Analyse läuft im Hintergrund — du kannst sofort weitermachen.":
    "Analysis runs in the background — you can carry on right away.",
  "Nächste Karte scannen": "Scan next card", "Analysieren": "Analyze",
  "Gruppen prüfen": "Review groups",
  "Teilen": "Split", "Zusammenführen": "Merge",
  "Hauptbild": "Main photo",
  "Als Hauptbild": "Set as main photo",
  "Gruppe teilen": "Split group", "Mit nächster Gruppe zusammenführen": "Merge with next group",
  "Analyse starten": "Start analysis",
  "In die Warteschlange": "Added to queue",
  "{0} Stücke in der Warteschlange — Analyse läuft.": "{0} items in the queue — analysis running.",
  "Scan-Warteschlange": "Scan queue",
  "Bereit": "Ready", "Prüfung nötig": "Needs review", "Kein Preis": "No price",
  "Warteschlange leeren": "Clear queue",
  "Ein Artikel": "Single item", "Mehrere Artikel": "Multiple items", "Nur erfassen": "Collect only",
  "Scan-Modus": "Scan mode",
  "Ausgewählte Entwürfe": "Selected drafts",
  "{0} ausgewählt listen": "List {0} selected",
  "Zusammenfassung vor dem Publish": "Summary before publish",
  "Format": "Format", "Versand": "Shipping",
  "Preflight ok": "Preflight ok", "Preflight blockiert": "Preflight blocked",
  "Nur die Häkchen gehen live — jeweils mit Preflight.": "Only checked drafts go live — each with preflight.",
  "Entwürfe auswählen": "Select drafts",
  "Ein Artikel, Mehrere Artikel oder nur erfassen.": "Single item, multiple items, or collect only.",
  "{0} von {1} bereit": "{0} of {1} ready",
  "Kein Entwurf ist bereit.": "No draft is ready.",
  "{0} Entwürfe werden veröffentlicht …": "{0} drafts are being published …",
  "Das lässt sich nicht rückgängig machen (Listings kannst du danach auf eBay beenden).":
    "This cannot be undone (you can end listings on eBay afterwards).",
  "Prüfung fehlgeschlagen": "Check failed",
  "Sofortkauf": "Buy It Now",
  "Auktion": "Auction",
  "Versand": "Shipping",
  "Wird analysiert …": "Analyzing …",
  "Fehler": "Error",
  "Bildreihenfolge speichern": "Save photo order",
  "Foto entfernen aus Entwurf": "Remove photo from draft",
  "Fotos im Entwurf": "Draft photos",
  "Nach vorn": "Move forward", "Nach hinten": "Move back",
  "Nächstes Stück scannen": "Scan next item",
  "Fertig": "Done",
  "Stück {0}": "Item {0}",
  "{0} Fotos": "{0} photos",
  "Wird analysiert": "Analyzing",
  "Keine Gruppen": "No groups",
  "Vorder-/Rückseite prüfen. Erstes Foto je Gruppe ist das Hauptbild.":
    "Check front/back. The first photo in each group is the main image.",

  /* ── Schnellmenü ── */
  "Listing verwalten — LIVE": "Manage listing — LIVE",
  "Bitte prüfen": "Please review",
  "Bitte Angaben prüfen": "Please check the details",
  "Auf eBay listen": "List on eBay",
  "Zum Verkauf": "Go to selling",
  "Bulk-Upload": "Bulk upload",
  "{0} ausgewählt": "{0} selected",
  "Auswahl aufheben": "Clear selection",
  "Listing wird vorbereitet …": "Preparing listing …",
  "Im nächsten Schritt prüfst du Preis, Titel und Zustand — live geht es erst nach deiner Freigabe.":
    "Next you check price, title and condition — it goes live only after you approve.",
  "Titel, Beschreibung, Kategorie und Preis werden vorausgefüllt — danach kannst du alles prüfen und listen.":
    "Title, description, category and price are prefilled — then you can check everything and list.",
  "Tippen zum Bearbeiten": "Tap to edit",
  "Wird ermittelt …": "Looking up …",
  "Jetzt live listen": "List live now",
  "Testlauf fertig — Inventar und Angebot liegen bei eBay, noch nicht veröffentlicht. Tippe, um live zu listen.": "Test run done — inventory and offer are on eBay, not published yet. Tap to list live.",
  "Wird zu eBay geladen …": "Uploading to eBay …",
  "Upload läuft gerade — einen Moment.": "Upload in progress — one moment.",
  "App verlassen?": "Leave the app?",
  "SERO schließen und zurück zum Startbildschirm.": "Close SERO and return to the home screen.",
  "App verlassen": "Leave app",
  "Format und Preis festlegen — live geht es erst nach deiner Freigabe im Entwurf.": "Set format and price — it only goes live after you approve the draft.",
  "Verkaufsart": "Sale type",
  "Preis in €": "Price in €",
  "Entwurf anlegen": "Create draft",
  "Bitte einen gültigen Preis eintragen.": "Please enter a valid price.",
  "Entwurf ist unter Verkauf": "Draft is under Selling",
  "Listing wird vorbereitet …": "Preparing listing…",
  "Für dieses Stück fehlen Grading-Angaben. Beispiel: PSA 9.5 12345678": "Grading details are missing for this item. Example: PSA 9.5 12345678",
  "Bewerter Note Zertifikat …": "Grader grade certificate…",
  "Listing-Entwurf öffnen": "Open listing draft",
  "Als Favorit": "Add to favorites", "Favorit entfernen": "Remove favorite",
  "Aus Wunschliste nehmen": "Remove from wishlist",
  "Auf die Wunschliste": "Add to wishlist",
  "Keine eigenen Fotos — bitte einmal neu scannen": "No photos of your own — please scan again",
  "Entwurf ist unter Verkauf": "Draft is under Selling",
  "Listing wird vorbereitet …": "Preparing listing …",

  /* ── Verkauf-Tab ── */
  "aktiv": "active", "Angebotswert": "Listed value", "30 Tage live": "live in 30 days",
  "Rückfrage": "Question", "Entwurf": "Draft",
  "Festpreis": "Fixed price",
  "Keine aktiven Listings — liste ein Stück aus deiner Sammlung.":
    "No active listings — list an item from your collection.",
  "Alle Entwürfe listen": "List all drafts",
  "Jeder Entwurf geht nacheinander live auf eBay — mit deinen Vorlage-Einstellungen.":
    "Each draft goes live on eBay one after another — using your template settings.",
  "Das lässt sich nicht rückgängig machen (Listings kannst du danach auf eBay beenden).":
    "This cannot be undone (you can end the listings on eBay afterwards).",
  "Jetzt listen": "List now",

  /* ── Profil ── */
  "Testphase": "Trial", "SERO-Konto": "SERO account", "{0} Listings": "{0} listings",
  "Noch {0} Tage Testphase": "{0} days left in trial",
  "Listings in diesem Monat": "Listings this month",
  "Unbegrenzte Scans, Preisalarme, erweiterte Statistiken, Cloud-Backup und Export — Verwaltung über die SERO-Website.":
    "Unlimited scans, price alerts, advanced stats, cloud backup and export — managed on the SERO website.",
  "Konto": "Account", "eBay-Konto": "eBay account",
  "Verbunden": "Connected", "Nicht verbunden": "Not connected", "Verknüpft": "Linked",
  "Setup": "Setup", "Bereit": "Ready", "Unvollständig": "Incomplete",
  "Sprache": "Language", "Erscheinungsbild": "Appearance", "Währung": "Currency",
  "Preisalarm-Hinweise": "Price alert notifications",
  "Katalog-Bilder im Grid": "Catalog images in grid",
  "Nur die öffentliche Adresse wird verbunden (lesend) — SERO fragt niemals nach Keys oder Signaturen. NFT-Werte = Floor-Preis der Collection (Magic Eden).":
    "Only the public address is connected (read-only) — SERO never asks for keys or signatures. NFT values = the collection's floor price (Magic Eden).",
  "Daten": "Data", "eBay-Listings importieren": "Import eBay listings",
  "Sammlung exportieren (Backup)": "Export collection (backup)",
  "Alle Preise aktualisieren": "Refresh all prices",
  "Sammlung neu erkennen": "Re-identify collection",
  "SERO analysiert alle Stücke mit Foto erneut — Set, Nummer und Sprache werden nachgezogen. Dauert bei vielen Stücken eine Weile.":
    "SERO analyzes every item with a photo again — set, number and language are filled in. With many items this takes a while.",
  "Neu erkennen": "Re-identify",
  "Sammlung wird neu erkannt …": "Re-identifying collection …",
  "{0} Stücke in der Warteschlange": "{0} items queued",
  "Scans": "Scans", "Premium — unbegrenzt": "Premium — unlimited",
  "Konto löschen …": "Delete account …", "Mehr": "More",
  "SERO-Website öffnen": "Open SERO website", "Abmelden": "Sign out",
  "Automatisch (System)": "Automatic (system)", "Hell": "Light", "Dunkel": "Dark",
  "Einstellung nicht gespeichert. Versuch es erneut.": "Setting not saved. Try again.", "Preise werden aktualisiert …": "Refreshing prices …",
  "Veröffentlicht": "Published", "Stück": "Items", "Verkäufe": "Sales",
  "Aktiv auf eBay": "Active on eBay",
  "Besitz inklusive eBay-Angebote": "Owned incl. eBay listings",
  "In Sammlung": "In collection", "Verkauft": "Sold",
  "Im Portfolio": "In portfolio",
  "Tarif & Abrechnung": "Plan & billing", "Tarif wählen": "Choose a plan",
  "Abo verwalten": "Manage subscription",
  "Listings ohne Monatslimit": "Listings without a monthly limit",
  "Scans ohne Limit": "Scans without limit",
  "{0} von {1} Listings in diesem Monat": "{0} of {1} listings this month",
  "{0} von {1} Gratis-Scans": "{0} of {1} free scans",
  "Testphase beendet": "Trial ended",
  "Konto & Profil": "Account & profile",
  "eBay & Verkaufssetup": "eBay & selling setup",
  "Darstellung & Sprache": "Display & language",
  "Daten & Backup": "Data & backup",
  "Hilfe": "Help",
  "Hilfe & Kontakt": "Help & contact",
  "Rechtliches": "Legal", "Über SERO": "About SERO",
  "Einstellungen": "Settings", "Zurück": "Back",
  "eBay ist nicht verbunden": "eBay is not connected",
  "Verbinde eBay unter eBay und Verkaufssetup, bevor du einstellst.":
    "Connect eBay under eBay and selling setup before you list.",
  "eBay verbinden": "Connect eBay",
  "Wird vorbereitet…": "Preparing…",
  "Listing-Vorbereitung fehlgeschlagen — erneut versuchen":
    "Listing prep failed — try again",
  "Stück entfernen?": "Remove item?",
  "Das Stück verlässt die Sammlung. Du kannst das gleich rückgängig machen.":
    "The item leaves the collection. You can undo this right away.",
  "Entfernen": "Remove",
  "Freistellen…": "Cutting out…",
  "Keine Entwürfe.": "No drafts.",
  "Fotografiere ein Stück. SERO baut den Entwurf.": "Photograph an item. SERO builds the draft.",
  "Noch nichts live.": "Nothing live yet.",
  "Noch nichts verkauft.": "Nothing sold yet.",
  "Fotografieren.": "Photograph.",
  "Ein Foto reicht.": "One photo is enough.",
  "Prüfen.": "Review.",
  "SERO legt einen Entwurf. Nichts geht live.": "SERO creates a draft. Nothing goes live.",
  "In der Sammlung.": "In the collection.",
  "Live auf eBay nur, wenn du es willst.": "Live on eBay only if you want it.",
  "Überspringen": "Skip",
  "Rechtstext": "Legal text",
  "Das Foto wird der Entwurf.": "This photo becomes the draft.",
  "Nochmal fotografieren": "Photograph again",
  "Noch keine Stücke.": "No items yet.",
  "Profil bearbeiten": "Edit profile", "Profilbild ändern": "Change profile photo",
  "Anzeigename": "Display name", "E-Mail": "Email",
  "Anmeldung per E-Mail-Code, kein Passwort": "Sign-in with email code, no password",
  "Mitglied seit": "Member since",
  "Profil von {0} bearbeiten": "Edit profile for {0}",
  "Gefahrenzone": "Danger zone",
  "Löscht Sammlung, Fotos, Entwürfe, Preisverlauf und dein SERO-Konto.":
    "Deletes collection, photos, drafts, price history and your SERO account.",
  "Bereits auf eBay veröffentlichte Angebote bleiben bei eBay bestehen und müssen dort beendet werden.":
    "Listings already published on eBay stay on eBay and must be ended there.",
  "Zuerst Sammlung exportieren": "Export collection first",
  "Tippe LÖSCHEN zur Bestätigung": "Type LÖSCHEN to confirm",
  "Konto endgültig löschen": "Permanently delete account",
  "Versand & eBay-Richtlinien": "Shipping & eBay policies",
  "Dafür braucht SERO zuerst dein eBay-Konto. Versandstandort und Verkaufsrichtlinien liegen dort.":
    "SERO needs your eBay account first. Shipping location and selling policies live there.",
  "Standort und Verkaufsrichtlinien": "Location and selling policies",
  "Verkaufsvorlage": "Selling template",
  "Format, Preisregel, Bildhintergrund": "Format, price rule, image background",
  "Einrichtung abschließen": "Finish setup", "Neu verbinden": "Reconnect",
  "Code kopieren": "Copy code", "SERO-Bot öffnen": "Open SERO bot",
  "Verbindung prüfen": "Check connection",
  "Öffne den SERO-Bot und sende diesen Code:": "Open the SERO bot and send this code:",
  "Code wird geladen …": "Loading code …", "Code nicht verfügbar": "Code not available",
  "Telegram ist verknüpft": "Telegram is linked", "Noch nicht verknüpft": "Not linked yet",
  "Automatisch": "Automatic",
  "Bilder in der Sammlung": "Images in the collection",
  "Eigene Fotos": "Your photos",
  "Katalogbilder, wenn verfügbar": "Catalog images when available",
  "Bewegung & Glaseffekte": "Motion & glass effects", "Reduziert": "Reduced",
  "Preisalarme": "Price alerts",
  "Preisalarme aktiv": "Price alerts on", "Preisalarme pausiert": "Price alerts paused",
  "Als Entwurf behalten": "Keep as draft",
  "Anmelden zum Speichern": "Sign in to save",
  "Der Entwurf bleibt auf diesem Gerät.": "The draft stays on this device.",
  "Entwürfe werden gespeichert …": "Saving drafts …",
  "Entwurf gespeichert. Analyse läuft.": "Draft saved. Analysis is running.",
  "{0} Entwürfe gespeichert. Analyse läuft.": "{0} drafts saved. Analysis is running.",
  "Entwurf konnte nicht gespeichert werden": "The draft could not be saved",
  "Teilweise gespeichert — restliche Entwürfe bleiben auf dem Gerät.":
    "Partly saved — remaining drafts stay on this device.",
  "Anmeldung fehlgeschlagen": "Sign-in failed",
  "Code": "Code",
  "Einstellen": "List item",
  "über eBay": "via eBay",
  "Notizen": "Notes",
  "Aktiv": "Active",
  "Bestehende Schwellen bleiben beim Pausieren gespeichert":
    "Existing thresholds stay saved while paused",
  "{0} aktiv": "{0} active",
  "Sprache gespeichert — App wird neu geladen": "Language saved — app will reload",
  "Sammlung exportieren": "Export collection",
  "Backup wird erstellt …": "Creating backup …",
  "Backup geladen — {0} Stücke": "Backup downloaded — {0} items",
  "Backup fehlgeschlagen": "Backup failed",
  "JSON-Backup mit Sammlung und Stammdaten laden":
    "Download a JSON backup with collection and account data",
  "Neue und noch nicht vorhandene Listings übernehmen":
    "Import new listings that are not in SERO yet",
  "Marktwerte neu abrufen": "Refresh market values",
  "Verwendet echte Belege und kann einige Minuten dauern":
    "Uses real comps and can take a few minutes",
  "Erkennung für alle Stücke neu starten": "Re-run identification for all items",
  "Nur verwenden, wenn Set, Nummer oder Sprache bei vielen Stücken falsch sind":
    "Only use this if set, number or language are wrong for many items",
  "Jetzt abrufen": "Fetch now", "Neu starten": "Restart",
  "Marktwerte werden abgerufen …": "Fetching market values …",
  "Erkennung läuft …": "Identification running …",
  "Erkennung neu starten": "Restart identification",
  "SERO holt für bis zu {0} Stücke frische Belege. Das kann einige Minuten dauern.":
    "SERO fetches fresh comps for up to {0} items. This can take a few minutes.",
  "SERO analysiert bis zu {0} Stücke mit Foto erneut. Nur nötig, wenn Zuordnung oft falsch ist.":
    "SERO re-analyzes up to {0} items with a photo. Only needed when matches are often wrong.",
  "Anleitung öffnen": "Open guide", "Guide auf der SERO-Website": "Guide on the SERO website",
  "Problem melden": "Report a problem", "E-Mail an den Support": "Email support",
  "Diagnose kopieren": "Copy diagnostics",
  "Version und Browserfamilie, ohne persönliche Daten":
    "Version and browser family, no personal data",
  "SERO weiterempfehlen": "Recommend SERO",
  "Diagnose kopiert": "Diagnostics copied",
  "Impressum": "Imprint", "Website öffnen": "Open website",
  "eBay ist nicht verbunden.": "eBay is not connected.",
  "Der Text konnte gerade nicht geladen werden.": "The text could not be loaded right now.",
  "Im Browser öffnen": "Open in browser",
  "Seite konnte nicht geöffnet werden.": "The page could not be opened.",
  "Billing-Portal im Testmodus nicht verfügbar.": "Billing portal not available in test mode.",
  "Portal-Adresse fehlt. Versuch es erneut.": "Portal URL missing. Try again.",
  "Aktion fehlgeschlagen": "Action failed",
  "Testmodus": "Test mode",
  "Profil gespeichert": "Profile saved",
  "Abonnement": "Subscription",
  "Scans und Listen ohne Limit": "Scans and listings without limit",
  "Einem Freund empfehlen": "Invite a friend",
  "Teile SERO mit anderen Sammlern": "Share SERO with other collectors",
  "SERO erkennt deine Sammelstücke und listet sie mit einem Tipp auf eBay.":
    "SERO identifies your collectibles and lists them on eBay in one tap.",
  "Link kopiert": "Link copied", "Teilen nicht möglich": "Sharing not available",
  "Über": "About", "Dein Name": "Your name",
  "Kategorien": "Categories", "Foto ändern": "Change photo",
  "Tippe auf das Bild, um ein neues Foto zu wählen. Mit „Sichern“ übernimmst du es.":
    "Tap the image to choose a new photo. Tap Save to apply it.",
  "Vorschau bereit — tippe auf Sichern": "Preview ready — tap Save",
  "Foto konnte nicht geladen werden": "Could not load photo",
  "Foto tippen zum Ändern": "Tap photo to change",
  "Kein Netz — Foto bleibt vorgemerkt, solange die App geöffnet ist":
    "No network — photo stays queued while the app stays open",
  "Suchen": "Search",
  "Name, Set oder Kategorie tippen": "Type a name, set or category",
  "Tippe, um Stücke zu finden.": "Type to find items.",

  /* ── Wallet ── */
  "Adresse": "Address", "Wallet trennen": "Disconnect wallet",
  "Wallet getrennt": "Wallet disconnected",
  "Phantom verbinden": "Connect Phantom", "Solflare verbinden": "Connect Solflare",
  "Adresse manuell eingeben": "Enter address manually",
  "Wallet verbunden — {0} NFTs gefunden": "Wallet connected — {0} NFTs found",
  "Phantom nicht gefunden — Browser-Erweiterung installieren oder Adresse manuell eingeben":
    "Phantom not found — install the browser extension or enter the address manually",
  "Solflare nicht gefunden — Erweiterung installieren oder Adresse manuell eingeben":
    "Solflare not found — install the extension or enter the address manually",
  "Verbindung abgebrochen": "Connection cancelled", "Solana-Adresse": "Solana address",
  "Deine öffentliche Wallet-Adresse (beginnt nicht mit 0x — das wäre Ethereum).":
    "Your public wallet address (it does not start with 0x — that would be Ethereum).",
  "z. B. 9WzD…AWWM": "e.g. 9WzD…AWWM",

  /* ── Detail: Übersicht & Wert ── */
  "Übersicht": "Overview", " · Live": " · Live", " · Entwurf": " · Draft",
  "eBay: {0} aktive Angebote · Median {1}": "eBay: {0} active offers · median {1}",
  "Preisalarm": "Price alert", "Preis aktualisieren": "Refresh price",
  "Stand {0}": "As of {0}",
  "Letzte eBay-Verkäufe": "Recent eBay sales", "Verkauft": "Sold",
  "Ø letzte {0} Verkäufe": "Avg. last {0} sales",
  "Noch keine belegten Verkäufe — SERO sucht automatisch weiter (aktueller Wert: {0})":
    "No confirmed sales yet — SERO keeps looking automatically (current value: {0})",
  "Marktquelle": "market source",
  "Falsche Karte? Richtige suchen": "Wrong card? Find the right one",
  "Karte in Datenbank suchen": "Search the card database",
  "Set": "Set", "Nummer": "Number", "Seltenheit": "Rarity", "Illustrator": "Illustrator",
  "Druck": "Print",
  "Keine Karten-Datenbank-Zuordnung — für Sealed-Produkte normal. Einzelkarte? Dann von Hand zuordnen:":
    "No card database match — normal for sealed products. A single card? Then match it by hand:",

  /* ── Detail: Grading ── */
  "Grading könnte sich lohnen: ~+{0} bei PSA 10*": "Grading could pay off: ~+{0} at PSA 10*",
  "Grading lohnt bei dieser Karte eher nicht*":
    "Grading probably isn't worth it for this card*",
  "KI-Einschätzung:": "AI estimate:", "Sicherheit": "Confidence",
  "*aktive PSA-Angebote auf eBay, abzüglich ~25 € Grading-Gebühr — keine Garantie":
    "*active PSA offers on eBay, minus a ~€25 grading fee — no guarantee",
  "PSA-Preise aktualisieren": "Refresh PSA prices", "PSA-Preise laden": "Load PSA prices",
  "Note neu schätzen": "Re-estimate grade", "Note per KI schätzen": "Estimate grade with AI",
  "PSA-Angebote werden gesucht …": "Searching PSA offers …",
  "Einschätzung läuft — dauert etwa 30 Sekunden":
    "AI is checking condition & grade — takes about 30 seconds …",
  "Wert unbekannt": "Value unknown",
  "Marktwert (Schätzung)": "Market value (estimate)",
  "Katalogwert": "Guide value",
  "Rohkarten-Marktwert": "Raw card market",
  "Angebotspreis": "Asking price",
  "Einschätzung fertig": "Estimate ready", "Preis aktualisiert": "Price updated",
  "Preisermittlung läuft": "Price lookup running",
  "Preisermittlung läuft noch — gleich nochmal prüfen": "Price lookup still running — check again shortly",
  "Kein Marktwert gefunden": "No market value found",
  "Preisermittlung fehlgeschlagen": "Price lookup failed",

  /* ── Detail: Mein Exemplar ── */
  "Mein Exemplar": "My copy", "Kategorie": "Category", "Zustand": "Condition",
  "Stückzahl": "Quantity", "Kaufpreis": "Purchase price", "Notiz": "Note",
  "Herkunft": "Origin", "Karte": "Card", "Dein Bestand": "Your stock",
  "Set": "Set", "Serie": "Series", "Jahr": "Year", "Name": "Name",
  "Kartennummer": "Card number", "Sprache": "Language", "Auflage": "Edition",
  "Variante": "Variant", "Seltenheit": "Rarity", "Grade": "Grade",
  "Zertifikat": "Certificate",
  "So erscheint das Stück in deiner Sammlung und später im Listing.":
    "This is how the item appears in your collection and later in the listing.",
  "Aktuelle eBay-Angebote": "Current eBay offers",
  "1 Stück wartet und läuft automatisch weiter.": "1 item is waiting and will continue automatically.",
  "{0} Stücke warten und laufen automatisch weiter.": "{0} items are waiting and will continue automatically.",
  "Das KI-Guthaben ist aufgebraucht. Lade auf console.anthropic.com unter Plans & Billing auf — die Analyse läuft dann automatisch weiter.":
    "The AI credit balance is empty. Top up at console.anthropic.com under Plans & Billing — the analysis then continues automatically.",
  "Die KI-Analyse ist gerade ausgelastet. SERO versucht es automatisch weiter.":
    "The AI analysis is busy right now. SERO keeps retrying automatically.",
  "Keine Verbindung zur KI-Analyse. SERO versucht es automatisch weiter.":
    "No connection to the AI analysis. SERO keeps retrying automatically.",
  "Tipp: heller Untergrund und Folie ab — durch das Case-Plastik bleibt sichtbar, worauf das Stück liegt.":
    "Tip: bright surface and sleeve off — whatever the slab sits on stays visible through the clear case.",
  "Richtwert": "Estimated value", "Marktwert (Richtwert)": "Market value (guide)",
  "Preis der ungegradeten Karte — der Slab-Aufschlag fehlt noch.":
    "Price of the raw card — the slab premium is not included yet.",
  "Belege älter als 90 Tage — Karten-Märkte drehen schnell.":
    "Sales older than 90 days — card markets move fast.",
  "Aus aktiven Angeboten, noch kein belegter Verkauf.":
    "Based on active offers, no confirmed sale yet.",
  "Preisquelle passt nicht sicher zum Stück.":
    "Price source does not clearly match this item.",
  "Die Quellen widersprechen sich zu stark.":
    "The sources disagree too strongly.",
  "Keine belastbaren Vergleichsdaten. Beim Listen trägst du deinen Preis selbst ein — findet SERO später Belege, übernimmt es sie.":
    "No reliable comparison data. Enter your own price when listing — if SERO finds evidence later, it takes over.",
  "Median {0}": "Median {0}", "{0} Angebote": "{0} offers",
  "Nur {0} Angebote — zu wenige für einen belastbaren Median":
    "Only {0} offers — too few for a reliable median",
  "Auf diesem Markt ist gerade nichts im Angebot.":
    "Nothing on offer in this market right now.",
  "Gerade nicht abrufbar — tipp den Umschalter gleich noch einmal.":
    "Not available right now — tap the switch again in a moment.",
  "SERO erstellt Titel, Beschreibung, Kategorie und Preisvorschlag — live geht es erst nach deiner Freigabe.":
    "SERO writes the title, description, category and a suggested price — it only goes live once you approve.",
  "Für dieses Stück liegen keine eigenen Fotos mehr vor — zum Listen bitte einmal neu fotografieren (Scanner) und das alte Stück entfernen.":
    "There are no photos of your own left for this item — to list it, please photograph it again (Scanner) and remove the old item.",
  "Listing verwalten — LIVE auf eBay": "Manage listing — LIVE on eBay",
  "Erneut listen": "List again", "Listing-Entwurf fortsetzen": "Continue listing draft",
  "z. B. Neu · Neuwertig · Gebraucht — sehr gut · Near Mint":
    "e.g. New · Like new · Used — very good · Near Mint",
  "Was hast du bezahlt? (leer lassen zum Entfernen)":
    "What did you pay? (leave empty to clear)",
  "Mit Komma trennen — z. B. Ordner Vitrine, Deck, Verkaufen":
    "Separate with commas — e.g. binder, display case, deck, to sell",
  "Vitrine, Grading-Kandidat": "Display case, grading candidate",
  "Besonderheiten, Herkunft …": "Special features, provenance …",

  /* ── Karten-Suche ── */
  "Karte zuordnen": "Match card",
  "Suche die richtige Karte — deine Auswahl überschreibt die automatische Erkennung.":
    "Find the right card — your choice overrides the automatic detection.",
  "Kartenname, z. B. Monkey D. Luffy OP01": "Card name, e.g. Monkey D. Luffy OP01",
  "Suche … (erster Lauf pro Spiel kann eine Minute dauern)":
    "Searching … (the first run per game can take a minute)",
  "Nichts gefunden — anderen Namen oder Kartencode probieren.":
    "Nothing found — try a different name or card code.",
  "Karte wird zugeordnet …": "Matching card …",
  "Karte zugeordnet — Preis aktualisiert": "Card matched — price updated",

  /* ── Preisalarm ── */
  "Du bekommst einen Hinweis im Dashboard, sobald der Marktwert die Schwelle erreicht.":
    "You'll get a notice on the dashboard as soon as the market value hits the threshold.",
  "Steigt über": "Rises above", "Fällt unter": "Falls below", "z. B. 25": "e.g. 25",
  "Alarm löschen": "Delete alert", "Preisalarm gesetzt": "Price alert set",
  "Alarm setzen": "Set alert", "Alarm gelöscht": "Alert deleted",

  /* ── eBay-Entwurf ── */
  "LIVE auf eBay": "LIVE on eBay", "Live auf eBay": "Live on eBay",
  "Auf eBay ansehen": "View on eBay", "Antwort …": "Answer …",
  "Für dieses Stück fehlen Grading-Angaben. Beispiel: PSA 9.5 12345678":
    "Grading details are missing for this item. Example: PSA 9.5 12345678",
  "Bewerter Note Zertifikat …": "Grader grade certificate …",
  "Die Erstellung ist fehlgeschlagen.": "Creation failed.",
  "Erneut versuchen": "Try again",
  "Kein Stück zu diesem Entwurf": "No item for this draft",
  "Annahme:": "Assumption:", "Preis festlegen …": "Set a price …",
  "Startpreis · Auktion": "Starting price · auction",
  "{0} Tage": "{0} days", "Altersfreigabe": "Age rating", "USK ab {0}": "USK {0}+",
  "Keine Angabe": "Not specified", "Preisvorschlag": "Best offer",
  "Mindestpreis": "Minimum price",
  "Mindestpreis optional": "Minimum price optional",
  "Erst Preisvorschlag einschalten.": "Turn on best offer first.",
  "Tippe auf ein Bild für die volle Werkzeugleiste — Reihenfolge und Hauptbild hier.":
    "Tap a photo for the full toolbar — order and main photo here.",
  "Werkzeuge": "Tools",
  "Reihenfolge & Hauptbild": "Order & main photo",
  "Original aktiv": "Original active",
  "Freisteller aktiv": "Cut-out active",
  "Bild {0} — Original → Freisteller": "Image {0} — original → cut-out",
  "Bild {0} — Freisteller → Original": "Image {0} — cut-out → original",
  "Foto bearbeiten": "Edit photo",
  "1 Preisvorschlag": "1 offer",
  "{0} Preisvorschläge": "{0} offers",
  "Preisvorschlag {0}": "Offer {0}",
  "{0} Preisvorschläge · bis {1}": "{0} offers · up to {1}",
  "Offene Preisvorschläge": "Pending offers",
  "offen bis": "open until",
  "Käufer": "Buyer",
  "Damit Verkäufe und Preisvorschläge korrekt erkannt werden, verbinde eBay einmal neu auf der Website (Mit eBay verbinden).":
    "So sales and offers are detected correctly, reconnect eBay once on the website (Connect with eBay).",
  "Damit Verkäufe korrekt erkannt werden, verbinde eBay einmal neu auf der Website (Mit eBay verbinden).":
    "So sales are detected correctly, reconnect eBay once on the website (Connect with eBay).",
  "Fotos": "Photos",
  "Zuschneiden": "Crop",
  "Drehen": "Rotate",
  "Neues Foto": "New photo",
  "Hintergrund": "Background",
  "Hintergrund für eBay": "Background for eBay",
  "Hintergrund gespeichert": "Background saved",
  "Reinweiß": "Pure white",
  "Kaltweiß": "Cool white",
  "Off-White": "Off-white",
  "Anthrazit": "Anthracite",
  "Graphit": "Graphite",
  "Eisblau": "Ice blue",
  "Hellblau": "Light blue",
  "Navy-Hell": "Soft navy",
  "Konto-Standard": "Account default",
  "Standard": "Default",
  "Standard ist Schwarz — tipp eine andere Farbe, wenn du willst.": "Default is black — tap another color if you want.",
  "Tipp eine Farbe — so erscheint das Stück später auf eBay.":
    "Pick a color — that is how the item will look on eBay later.",
  "Vollbild": "Full screen",
  "Zuschneiden stellt die Karte frei. Drehen dreht um 90 Grad.":
    "Crop cuts out the card. Rotate turns it by 90 degrees.",
  "Zuschneiden und Drehen bearbeiten das aktuelle Foto. Freistellen entfernt den Hintergrund.":
    "Crop and rotate edit the current photo. Cut-out removes the background.",
  "Zieh die Ecken oder den Rahmen. Mit Übernehmen speicherst du den Ausschnitt.":
    "Drag the corners or the frame. Tap Apply to save the crop.",
  "Dreh frei mit dem Regler. Zurücksetzen holt das Originalbild.":
    "Rotate freely with the slider. Reset restores the original image.",
  "Dreh frei mit dem Regler. Null liegt in der Mitte. Speichern erst mit Übernehmen.":
    "Rotate freely with the slider. Zero is in the middle. Saving only happens when you tap Apply.",
  "Stelle Karte frei …": "Cutting out card …",
  "Freisteller läuft im Hintergrund": "Cut-out runs in the background",
  "Freisteller für die Sammlung läuft im Hintergrund": "Cut-outs for the collection run in the background",
  "Zuschneiden fertig": "Crop finished",
  "Zuschneiden wird gespeichert …": "Saving crop …",
  "Zuschneiden fehlgeschlagen": "Crop failed",
  "Freistellen": "Cut out",
  "Freistellen fertig": "Cut-out finished",
  "Freistellen fehlgeschlagen": "Cut-out failed",
  "Freistellen fehlgeschlagen — Original bleibt. Tipp aufs Bild, dann Freistellen.":
    "Cut-out failed — original stays. Tap the photo, then Cut out.",
  "Nochmal freistellen": "Cut out again",
  "Original wiederherstellen": "Restore original",
  "Original wird wiederhergestellt …": "Restoring original …",
  "Original wiederhergestellt": "Original restored",
  "Foto wird gedreht …": "Rotating photo …",
  "Foto gedreht": "Photo rotated",
  "Drehen fehlgeschlagen": "Rotate failed",
  "Foto gespeichert": "Photo saved",
  "Fotos sind im Listing-Entwurf aktualisiert": "Photos updated in the listing draft",
  "Filtern": "Filter",
  "Schließen": "Close",
  "Zurück": "Back",
  "Weiter": "Next",
  "Änderungen speichern": "Save changes",
  "Titel": "Title", "Text": "Text", "Bilder": "Images", "Neu erstellen": "Regenerate",
  "Beenden": "End", "Verwerfen": "Discard",
  "Preis ändern": "Change price", "Preis festlegen": "Set price",
  "Marktwert": "Market value", "KI-Schätzung": "AI estimate", "Auktionsstart 1 €": "Auction start €1",
  "Startpreis der Auktion in Euro": "Auction starting price in euros",
  "Sofortkauf-Preis in Euro": "Buy It Now price in euros",
  "Max. 80 Zeichen — Marke, Modell, Variante": "Max. 80 characters — brand, model, variant",
  "Beschreibung": "Description",
  "Dein Text ersetzt die automatische Beschreibung.":
    "Your text replaces the automatic description.",
  "z. B. Neu · Neuwertig · Gebraucht — sehr gut": "e.g. New · Like new · Used — very good",
  "USK ab {0} freigegeben": "Rated USK {0}+",
  "Neu erstellen?": "Regenerate?",
  "Titel, Beschreibung und Preis werden neu generiert — manuelle Änderungen gehen verloren.":
    "Title, description and price are generated again — manual changes will be lost.",
  "Listing-Entwurf verwerfen?": "Discard listing draft?",
  "Das Stück bleibt in deiner Sammlung.": "The item stays in your collection.",
  "Listing beenden?": "End listing?",
  "Es wird sofort von eBay genommen. Das Stück bleibt in deiner Sammlung.":
    "It will be taken off eBay immediately. The item stays in your collection.",
  "Listing beendet": "Listing ended",

  /* ── Bilder ── */
  "Bild {0} — Original (kein Freisteller)": "Image {0} — original (no cutout)",
  "Pro Foto zwischen Freisteller und Original wechseln.":
    "Switch each photo between the cutout and the original.",
  "Alle neu rendern": "Re-render all",
  "Bilder werden neu gerendert …": "Re-rendering images …",
  "Bilder werden im Hintergrund gerendert": "Images are rendering in the background",
  "Bilder neu gerendert": "Images re-rendered",

  /* ── Konto löschen ── */
  "Konto löschen": "Delete account",
  "Das entfernt alles unwiderruflich: Sammlung, Fotos, Listings-Entwürfe, Preisverlauf und dein Konto.":
    "This removes EVERYTHING irreversibly: collection, photos, listing drafts, price history and your account.",
  "Tippe unten auf „Endgültig löschen“, um es wirklich zu tun.":
    "Tap “Delete permanently” below to really go through with it.",
  "Endgültig löschen": "Delete permanently",
  "Stück teilen": "Share item",
  "Vergrößern": "Zoom",
  "Du": "You",
  "SERO Preis": "SERO Price",
  "Konfidenz": "Confidence",
  "Hoch": "High",
  "Mittel": "Medium",
  "Niedrig": "Low",
  "Noch keine verlässliche Preisschätzung": "No reliable price estimate yet",
  "{0} Vergleiche": "{0} comps",
  "SERO Notes": "SERO Notes",
  "Sammlerhinweise": "Collector notes",
  "Produktinformationen": "Product information",
  "Warum es interessant ist": "Why it is interesting",
  "Kerndaten": "Key facts",
  "Hinweise": "Notes",
  "Fakten": "Facts",
  "Quellen": "Sources",
  "Automatisch erzeugte Angaben — bitte prüfen.": "Automatically generated details — please check.",
  "Details": "Details",
  "einstellen": "list",
  "Auf eBay einstellen": "Prepare eBay listing",
  "Bearbeiten": "Edit",
  "{0} Stück": "{0} items",
  "Das ist eine Sammelkarte.": "This is a trading card.",
  "Das ist eine bewertete Karte im Slab.": "This is a graded card in a slab.",
  "Das ist ein Videospiel.": "This is a video game.",
  "Das ist ein Sammlerstück.": "This is a collectible.",
  "Das ist Kleidung.": "This is clothing.",
  "Das ist ein elektronisches Gerät.": "This is an electronic device.",
  "Kaufart": "Listing format",
  "Tipp aufs Bild zum Bearbeiten": "Tap the photo to edit",
  "Seltenheit": "Rarity",
  "Stück entfernen": "Remove item",
  "Figur": "Character",
  "Grader": "Grader",
  "Plattform": "Platform",
  "Marke": "Brand",
  "Modell": "Model",
  "Band": "Volume",
};
const L = (s) => (LANG === "de" ? s : (STR_EN[s] ?? s));

/* Vollautomatische Übersetzung (EN): Ein Beobachter tauscht JEDEN gerenderten
   Text gegen das 435-Einträge-Wörterbuch — statisch wie dynamisch, ohne
   hunderte Code-Stellen anzufassen. Läuft nur bei Nicht-DE-Geräten. */
function _translateNode(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const t = n.nodeValue.trim();
    if (t && STR_EN[t]) n.nodeValue = n.nodeValue.replace(t, STR_EN[t]);
  }
  for (const el of (root.querySelectorAll ? root.querySelectorAll("[placeholder]") : [])) {
    const p = el.getAttribute("placeholder");
    if (p && STR_EN[p]) el.setAttribute("placeholder", STR_EN[p]);
  }
}
if (LANG !== "de") {
  new MutationObserver((muts) => {
    for (const m of muts) {
      for (const node of m.addedNodes) {
        if (node.nodeType === 1) _translateNode(node);
        else if (node.nodeType === 3 && STR_EN[node.nodeValue?.trim()])
          node.nodeValue = STR_EN[node.nodeValue.trim()];
      }
    }
  }).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", () => _translateNode(document.body));
}
/* Wie L(), aber mit Platzhaltern {0}, {1} … — Zahlen und Namen bleiben unangetastet. */
const LF = (s, ...a) => L(s).replace(/\{(\d+)\}/g, (m, i) => (a[i] === undefined ? m : a[i]));

async function boot() {
  applyTheme();
  mountStaticIcons();
  document.documentElement.lang = LANG;
  if (LANG !== "de") {
    /* Statisches Markup übersetzen — konservativ: nur Knoten mit reinem Text
       und nur, wenn STR_EN den Wortlaut wirklich kennt. */
    const SEL = ".large-title, .tab span:last-child, .seg button, .scan-hero h2, .scan-hero p,"
      + " .empty h2, .empty p, .section-label, .login-sub, .login-soon-copy, .login-hint, .login-foot,"
      + " .login-card label, .login-card button,"
      + " #btnScanGallery, #sellTplBtn, #sheetCancel, #sheetSave";
    document.querySelectorAll(SEL).forEach((el) => {
      if (el.children.length) return;
      const t = el.textContent.trim();
      if (STR_EN[t]) el.textContent = STR_EN[t];
    });
    document.querySelectorAll("[aria-label]").forEach((el) => {
      const t = el.getAttribute("aria-label");
      if (STR_EN[t]) el.setAttribute("aria-label", STR_EN[t]);
    });
    document.querySelectorAll("input[placeholder]").forEach((el) => {
      if (STR_EN[el.placeholder]) el.placeholder = STR_EN[el.placeholder];
    });
  }
  /* Magic-Link / eBay-Callback: Query auswerten, dann URL säubern */
  let ebayFlag = null;
  try {
    const q = new URLSearchParams(location.search);
    if (q.get("logged_in") === "1") toast(L("Angemeldet"), "check");
    ebayFlag = q.get("ebay");
    if (ebayFlag === "ok") {
      try { sessionStorage.removeItem("sero_ebay_pending"); } catch (_) {}
      toast(L("eBay verbunden"), "check");
    } else if (ebayFlag === "failed" || ebayFlag === "invalid") {
      try { sessionStorage.removeItem("sero_ebay_pending"); } catch (_) {}
      toast(L("eBay-Verbindung fehlgeschlagen"), "xmark");
    }
    if (q.has("logged_in") || q.has("ebay")) {
      const clean = new URL(location.href);
      clean.searchParams.delete("logged_in");
      clean.searchParams.delete("ebay");
      history.replaceState({}, "", clean.pathname + clean.search + clean.hash);
    }
  } catch (_) { /* ignore */ }
  try {
    state.me = await api("/api/me", { timeout: 8000 });
    cache.set("me", state.me);
    showApp();
    if (guestDraftRows().length) await flushGuestDrafts();
    if (ebayFlag === "ok") afterEbayConnectOk(state.me, { silentToast: true });
    else if (ebayFlag === "failed" || ebayFlag === "invalid") {
      setTimeout(() => openEbayConnectSheet(state.me), 400);
    }
  } catch (e) {
    /* Kein Netz heißt nicht „nicht angemeldet": mit gültigem Cache startet die
       App offline mit dem letzten Stand. Ohne Session (401/403) oder ohne
       Cache: Gastmodus — Scan und lokaler Entwurf, Login erst beim Speichern. */
    if (e.offline && cache.get("col") && cache.get("me")) {
      state.me = cache.get("me");
      showApp();
      zeigeOfflineBanner();
    } else if (e.status === 401 || e.status === 403 || e.offline) {
      /* C6: ohne Session in die App — Scan und lokaler Entwurf zuerst.
         Login nur, wenn Speichern ein Konto braucht. */
      enterGuestApp();
    } else {
      $("viewLogin").hidden = false;
      if (!restoreLoginPending()) renderSocialLogins();
      dismissSplash();
    }
  }
}

function paintTopAva() {
  const btn = $("topAva");
  if (!btn) return;
  const me = state.me;
  btn.hidden = false;
  const personSvg = `<svg class="topbar-ava-fallback" viewBox="0 0 36 36" fill="none"><circle cx="18" cy="14" r="6" fill="currentColor"/><path d="M6 32c0-6.6 5.4-12 12-12s12 5.4 12 12" fill="currentColor"/></svg>`;
  if (!me) {
    btn.innerHTML = personSvg;
    btn.onclick = () => openSaveLoginSheet();
    btn.setAttribute("aria-label", L("Anmelden zum Speichern"));
    return;
  }
  btn.innerHTML = me.avatar_url
    ? `<img src="${esc(me.avatar_url)}" alt="">${personSvg}`
    : personSvg;
  btn.onclick = () => openSeroProfile();
  btn.setAttribute("aria-label", L("Profil"));
}

/** SERO-Konto und Einstellungen — nur über den Avatar oben rechts, nicht den eBay-Tab. */
function openSeroProfile() {
  if (needAccountForSave()) return;
  const nav = (typeof settingsNav !== "undefined" && settingsNav)
    || (typeof window !== "undefined" && window.settingsNav);
  if (nav && typeof nav.openRoot === "function") {
    nav.openRoot("profile", "Profil", (body) => {
      if (typeof renderProfile === "function") renderProfile(body);
    }, $("topAva") || document.activeElement);
    return;
  }
  if (typeof renderProfile === "function") renderProfile();
}

/** Auge + Neu laden in der Topbar (neben Profilbild). */
function paintTopTools() {
  const hidden = storeSafe.getString("sero_hide") === "1";
  const eye = $("eyeBtn");
  const ref = $("dashRefresh");
  if (eye) {
    eye.innerHTML = icon("eye", 16);
    eye.setAttribute("aria-label", L(hidden ? "Werte anzeigen" : "Werte verbergen"));
    eye.onclick = () => {
      storeSafe.setString("sero_hide", storeSafe.getString("sero_hide") === "1" ? "0" : "1");
      paintTopTools();
      if (!$("tabHome").hidden && state.dash) renderDashboard();
      if (!$("tabCollection").hidden) renderCollection();
    };
  }
  if (ref) {
    ref.innerHTML = icon("refresh", 16);
    ref.setAttribute("aria-label", L("Preise aktualisieren"));
    ref.onclick = async () => {
      ref.classList.add("spin");
      try {
        const r = await post("/api/app/collection/refresh", null, { timeout: 600000 });
        toast(LF("Preise aktualisiert ({0} von {1})", r.updated, r.total), "check");
        loadDashboard({ background: true });
        loadCollection();
      } catch (e) { toast(e.message); }
      finally { ref.classList.remove("spin"); }
    };
  }
}

/** Nach eBay-OAuth oder Paste: Profil/Verkauf frisch, Setup anbieten. */
function afterEbayConnectOk(me, opts = {}) {
  stopEbayConnectPoll();
  try {
    sessionStorage.removeItem("sero_ebay_pending");
    sessionStorage.removeItem("sero_ebay_token_at0");
    sessionStorage.removeItem("sero_ebay_was_connected");
  } catch (_) {}
  if (!me) return;
  state.me = me;
  cache.set("me", me);
  paintTopAva();
  closeSheet();
  if ($("colEbayHub")) paintEbayHub();
  else if (!$("tabSales").hidden) loadSales().catch(() => {});
  if (!opts.silentToast) {
    if (me.ebay_needs_reconnect) {
      toast(L("eBay verbunden — Bestellungen noch einmal prüfen"), "check");
    } else {
      toast(L("eBay verbunden"), "check");
    }
  } else if (me.ebay_needs_reconnect) {
    toast(L("eBay verbunden — Bestellungen noch einmal prüfen"), "check");
  }
  if (!me.setup_ready && me.ebay_connected) {
    setTimeout(() => openSetupSheet(me), 600);
  }
}

let _ebayConnectPollTimer = null;
function stopEbayConnectPoll() {
  if (_ebayConnectPollTimer) {
    clearInterval(_ebayConnectPollTimer);
    _ebayConnectPollTimer = null;
  }
}

function markEbayConnectPending() {
  try {
    sessionStorage.setItem("sero_ebay_pending", "1");
    const at = (state.me && state.me.ebay_token_at) || 0;
    sessionStorage.setItem("sero_ebay_token_at0", String(at));
    sessionStorage.setItem("sero_ebay_was_connected",
      (state.me && state.me.ebay_connected) ? "1" : "0");
  } catch (_) {}
}

/** True, wenn seit Connect-Start ein neuer Token gespeichert wurde. */
function ebayTokenLooksNew(me) {
  if (!me || !me.ebay_connected) return false;
  let pending = false, base = 0, was = "0";
  try {
    pending = sessionStorage.getItem("sero_ebay_pending") === "1";
    base = parseFloat(sessionStorage.getItem("sero_ebay_token_at0") || "0") || 0;
    was = sessionStorage.getItem("sero_ebay_was_connected") || "0";
  } catch (_) {}
  if (!pending) return false;
  const at = Number(me.ebay_token_at) || 0;
  if (at > base + 0.5) return true;
  /* Erstverbindung: vorher kein Token — verbunden reicht (auch ohne token_at). */
  if (was !== "1") return true;
  return false;
}

async function refreshMeAfterEbayReturn() {
  let pending = false;
  try { pending = sessionStorage.getItem("sero_ebay_pending") === "1"; } catch (_) {}
  if (!pending && state.me && state.me.ebay_connected && !state.me.ebay_needs_reconnect) return;
  try {
    const me = await api("/api/me", { timeout: 8000 });
    state.me = me;
    cache.set("me", me);
    if (pending && ebayTokenLooksNew(me)) {
      afterEbayConnectOk(me);
    } else if ($("colEbayHub")) paintEbayHub();
    else if (!$("tabSales").hidden) loadSales().catch(() => {});
  } catch (_) { /* still offline / session */ }
}

/** Startet Consent. Bevorzugt neuer Tab — die App bleibt offen und pollen kann. */
function goEbayConnect(opts = {}) {
  markEbayConnectPending();
  const href = "/connect/ebay?next=" + encodeURIComponent("/app/");
  if (opts.sameWindow) {
    location.href = href;
    return;
  }
  const w = window.open(href, "_blank");
  if (!w) {
    location.href = href;
    return;
  }
  startEbayConnectPoll();
}

function startEbayConnectPoll() {
  stopEbayConnectPoll();
  let n = 0;
  _ebayConnectPollTimer = setInterval(async () => {
    n += 1;
    if (n > 90) { stopEbayConnectPoll(); return; } // ~3 Min
    let pending = false;
    try { pending = sessionStorage.getItem("sero_ebay_pending") === "1"; } catch (_) {}
    if (!pending) { stopEbayConnectPoll(); return; }
    try {
      const me = await api("/api/me", { timeout: 5000 });
      if (ebayTokenLooksNew(me)) afterEbayConnectOk(me);
    } catch (_) { /* keep polling */ }
  }, 2000);
}

window.addEventListener("pageshow", () => { refreshMeAfterEbayReturn(); });
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") refreshMeAfterEbayReturn();
});

function zeigeOfflineBanner() {
  const c = cache.get("col");
  const min = c && c.ts ? Math.max(1, Math.round((Date.now() - c.ts) / 60000)) : null;
  toast(min ? LF("Offline — Stand von vor {0} Min.", min) : L("Offline — gespeicherter Stand"),
        "globe", { label: L("Erneut versuchen"), fn: () => { loadCollection(); loadDashboard(); } });
}
window.addEventListener("online", () => { loadCollection(); if (!$("tabHome").hidden) loadDashboard(); });
window.addEventListener("offline", zeigeOfflineBanner);

async function renderSocialLogins() {
  const host = $("loginSocial");
  if (!host) return;
  const r = await api("/api/auth-providers").catch(() => ({}));
  const providers = r.providers || [];
  const googleOn = !!(r.google || providers.includes("google"));
  const tg = r.telegram || {};
  const phone = r.phone || {};
  // Parallele Optionen immer zeigen — fehlende Keys → klarer Hinweis beim Tipp
  host.hidden = false;
  host.innerHTML = `
    <div class="oauth-divider"><span>${L("oder weiter mit")}</span></div>
    <button type="button" class="btn-secondary oauth-btn" id="loginGoogleBtn">${L("Mit Google anmelden")}</button>
    <button type="button" class="btn-secondary oauth-btn" id="loginTelegramBtn">${L("Mit Telegram anmelden")}</button>
    <div id="telegramLoginSlot" class="tg-login-slot" hidden></div>
    <button type="button" class="btn-secondary oauth-btn" id="loginPhoneBtn">${L("Mit Telefon anmelden")}</button>
  `;
  $("loginGoogleBtn").onclick = () => {
    if (!googleOn) {
      toast(L("Google-Login ist noch nicht eingerichtet."), "info");
      return;
    }
    location.href = "/auth/google/start";
  };
  $("loginTelegramBtn").onclick = () => {
    if (!tg.enabled || !tg.bot) {
      toast(L("Telegram-Login ist noch nicht eingerichtet."), "info");
      return;
    }
    showTelegramWidget(tg.bot);
  };
  $("loginPhoneBtn").onclick = () => {
    if (!phone.enabled) {
      toast(L("Telefon-Login ist noch nicht eingerichtet."), "info");
      return;
    }
    $("loginStep1").hidden = true;
    $("loginPhoneCard").hidden = false;
    $("loginFootSignup").hidden = true;
    $("loginFootLogin").hidden = true;
    $("loginPhone").focus();
  };
  // Weitere OAuth (Apple/X), falls Keys gesetzt
  providers.filter((p) => p !== "google").forEach((p) => {
    const names = { apple: "Apple", x: "X" };
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn-secondary oauth-btn";
    b.textContent = LF("Mit {0} anmelden", names[p] || p);
    b.onclick = () => { location.href = `/auth/${p}/start`; };
    host.appendChild(b);
  });
}

function showTelegramWidget(bot) {
  const slot = $("telegramLoginSlot");
  if (!slot) return;
  slot.hidden = false;
  slot.innerHTML = "";
  window.onTelegramAuth = async (user) => {
    try {
      await post("/api/auth/telegram", user);
      clearLoginPending();
      $("viewLogin").hidden = true;
      state.me = await api("/api/me").catch(() => null);
      showApp();
    } catch (e) {
      toast(e.message || L("Fehler"), "info");
    }
  };
  const s = document.createElement("script");
  s.src = "https://telegram.org/js/telegram-widget.js?22";
  s.async = true;
  s.setAttribute("data-telegram-login", bot);
  s.setAttribute("data-size", "large");
  s.setAttribute("data-radius", "12");
  s.setAttribute("data-request-access", "write");
  s.setAttribute("data-onauth", "onTelegramAuth(user)");
  slot.appendChild(s);
}

function onLoginScreen() {
  const v = $("viewLogin");
  return !!(v && !v.hidden);
}

function enterGuestApp() {
  state.me = null;
  if ($("viewLogin")) $("viewLogin").hidden = true;
  applyGuestItems();
  showApp();
}

function guestDraftRows() {
  const rows = storeSafe.getJSON(GUEST_DRAFTS_KEY, []) || [];
  return Array.isArray(rows) ? rows : [];
}

function setGuestDraftRows(rows) {
  storeSafe.setJSON(GUEST_DRAFTS_KEY, Array.isArray(rows) ? rows : []);
}

function guestItemFromRow(row) {
  const photos = Array.isArray(row && row.photos) ? row.photos.filter(Boolean) : [];
  return {
    id: row.id,
    guest: true,
    name: (row && row.name) || "Stück",
    photos,
    status: "ready",
    quantity: 1,
    est_value: null,
    price_state: "unbekannt",
    price_reason: "UNBEKANNT_KEINE_BELEGE",
    category: null,
    favorite: false,
    wishlist: false,
    notes: (row && row.notes) || "",
    created_at: (row && row.created_at) || Date.now() / 1000,
    has_photos_raw: photos.length > 0,
  };
}

function applyGuestItems() {
  const guests = guestDraftRows().map(guestItemFromRow);
  if (isGuest()) {
    state.items = guests;
    state.stats = { count: guests.length, total_value: 0, categories: [] };
    state.history = [];
    state.historyByCat = {};
    return guests;
  }
  const have = new Set((state.items || []).map((i) => i.id));
  const extra = guests.filter((g) => !have.has(g.id));
  if (extra.length) state.items = extra.concat(state.items || []);
  return guests;
}

let _guestFlushErr = "";

function ensureGuestSaveBar() {
  let bar = $("guestSaveBar");
  if (bar) return bar;
  const hero = $("colHero");
  const host = (hero && hero.parentNode) || $("colScroll");
  if (!host) return null;
  bar = document.createElement("div");
  bar.id = "guestSaveBar";
  bar.className = "guest-save-bar";
  if (hero) host.insertBefore(bar, hero);
  else host.insertBefore(bar, host.firstChild);
  return bar;
}

function paintGuestSaveBar() {
  if (flushGuestDrafts._busy) return;
  const bar = ensureGuestSaveBar();
  if (!bar) return;
  const leftover = guestDraftRows().length;
  if (isGuest()) {
    bar.hidden = false;
    bar.innerHTML = `<button type="button" class="guest-save-btn" id="guestSaveBtn">${esc(L("Anmelden zum Speichern"))}</button>`;
    const btn = $("guestSaveBtn");
    if (btn) btn.onclick = () => openSaveLoginSheet();
    return;
  }
  if (leftover) {
    bar.hidden = false;
    const msg = _guestFlushErr || L("Entwurf konnte nicht gespeichert werden");
    bar.innerHTML = `<p class="guest-save-err" role="status">${esc(msg)}</p>
      <button type="button" class="guest-save-btn" id="guestSaveRetry">${esc(L("Erneut versuchen"))}</button>`;
    const retry = $("guestSaveRetry");
    if (retry) retry.onclick = () => { flushGuestDrafts(); };
    return;
  }
  bar.hidden = true;
  bar.innerHTML = "";
}

function paintGuestFlushStatus(msg) {
  const bar = ensureGuestSaveBar();
  if (!bar) return;
  bar.hidden = false;
  bar.innerHTML = `<p class="guest-save-status" role="status">${esc(msg)}</p>`;
}

function needAccountForSave() {
  if (!isGuest()) return false;
  openSaveLoginSheet();
  return true;
}

function saveLoginHint(r) {
  r = r || {};
  if (r.dev_code) return LF("Test-Modus (kein Mailversand) — dein Code: {0}", r.dev_code);
  if (r.via === "admin_telegram" || r.via === "telegram_admin") {
    return L("Dein Code geht an Sven per Telegram — er gibt ihn dir.");
  }
  if (r.via === "telegram") return L("SERO hat dir den Code per Telegram geschickt.");
  return L("SERO hat dir einen Code geschickt.");
}

function openSaveLoginSheet() {
  if (!isGuest()) return;
  const paint = (step, extra) => {
    extra = extra || {};
    const email = extra.email || "";
    const hint = extra.hint || "";
    const codeVal = extra.code || "";
    if (step === "code") {
      openSheet(
        L("Anmelden zum Speichern"),
        L("Der Entwurf bleibt auf diesem Gerät."),
        `<label class="sheet-field-lab" for="saveLoginCode">${esc(L("Code"))}</label>
         <input id="saveLoginCode" inputmode="text" autocomplete="one-time-code" placeholder="L-123456" value="${esc(codeVal)}">
         <p class="sheet-hint" id="saveLoginHint">${esc(hint)}</p>
         <p class="sheet-err" id="saveLoginErr"></p>`,
        async () => {
          const code = (($("saveLoginCode") && $("saveLoginCode").value) || "").trim();
          if (!code) return;
          try {
            await post("/api/login-verify", { identifier: email, code });
            await enterAppAfterSession();
          } catch (e) {
            if ($("saveLoginErr")) $("saveLoginErr").textContent = e.message || L("Fehler");
          }
        },
        L("Anmelden")
      );
      $("sheetCancel").textContent = L("Später");
      $("sheetCancel").onclick = () => closeSheet();
      if ($("saveLoginCode")) $("saveLoginCode").focus();
      return;
    }
    openSheet(
      L("Anmelden zum Speichern"),
      L("Der Entwurf bleibt auf diesem Gerät."),
      `<label class="sheet-field-lab" for="saveLoginId">${esc(L("E-Mail"))}</label>
       <input id="saveLoginId" type="email" autocomplete="username" inputmode="email" placeholder="du@mail.de" value="${esc(email)}">
       <p class="sheet-err" id="saveLoginErr"></p>`,
      async () => {
        const id = (($("saveLoginId") && $("saveLoginId").value) || "").trim();
        if (!id) return;
        try {
          const r = await post("/api/login-code", { identifier: id });
          if (r && r.ok) {
            await enterAppAfterSession();
            return;
          }
          paint("code", { email: id, hint: saveLoginHint(r), code: r.dev_code || "" });
        } catch (e) {
          if (e.status === 404) {
            try {
              const s = await post("/api/signup", { email: id });
              if (s && s.ok) {
                await enterAppAfterSession();
                return;
              }
              paint("code", { email: id, hint: saveLoginHint(s), code: s.dev_code || "" });
              return;
            } catch (e2) {
              if ($("saveLoginErr")) $("saveLoginErr").textContent = e2.message || L("Fehler");
              return;
            }
          }
          if ($("saveLoginErr")) $("saveLoginErr").textContent = e.message || L("Fehler");
        }
      },
      L("Weiter")
    );
    $("sheetCancel").textContent = L("Später");
    $("sheetCancel").onclick = () => closeSheet();
    if ($("saveLoginId")) $("saveLoginId").focus();
  };
  paint("email");
}

async function fileToGuestDataUrl(file) {
  if (!file) return "";
  const img = new Image();
  const src = URL.createObjectURL(file);
  try {
    await new Promise((ok, err) => { img.onload = ok; img.onerror = err; img.src = src; });
  } finally {
    URL.revokeObjectURL(src);
  }
  const max = 1280;
  let w = img.width || max, h = img.height || max;
  if (w > max || h > max) {
    const s = max / Math.max(w, h);
    w = Math.round(w * s);
    h = Math.round(h * s);
  }
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = h;
  cv.getContext("2d").drawImage(img, 0, 0, w, h);
  return cv.toDataURL("image/jpeg", 0.82);
}

async function keepGuestDraftFromFiles(files, notes) {
  const list = (files || []).filter(Boolean).slice(0, MAX_LISTING_PHOTOS);
  if (!list.length) return null;
  const photos = [];
  for (const f of list) {
    try { photos.push(await fileToGuestDataUrl(f)); } catch (_) { /* skip */ }
  }
  if (!photos.length) {
    toast(L("Foto konnte nicht geladen werden"));
    return null;
  }
  const row = {
    id: "guest-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8),
    name: "Stück",
    photos,
    notes: notes || "",
    created_at: Date.now() / 1000,
  };
  const rows = guestDraftRows();
  rows.unshift(row);
  setGuestDraftRows(rows.slice(0, 24));
  applyGuestItems();
  state.watchNew = row.id;
  state.scanChoiceShown = row.id;
  return row;
}

async function dataUrlToBlob(dataUrl) {
  if (!dataUrl) return null;
  const r = await fetch(dataUrl);
  return r.blob();
}

async function flushGuestDrafts() {
  if (isGuest()) return { uploaded: 0, failed: 0 };
  if (flushGuestDrafts._busy) return flushGuestDrafts._busy;
  let finish;
  flushGuestDrafts._busy = new Promise((res) => { finish = res; });
  const run = (async () => {
    let uploaded = 0;
    let failed = 0;
    let lastItemId = "";
    paintGuestFlushStatus(L("Entwürfe werden gespeichert …"));
    while (!isGuest()) {
      const rows = guestDraftRows();
      if (!rows.length) break;
      const row = rows[0];
      try {
        const fd = new FormData();
        const photos = Array.isArray(row.photos) ? row.photos : [];
        for (let i = 0; i < photos.length; i++) {
          try {
            const blob = await dataUrlToBlob(photos[i]);
            if (blob) fd.append("files", blob, "guest-" + i + ".jpg");
          } catch (_) { /* einzelnes Foto überspringen */ }
        }
        const still = guestDraftRows();
        if (!still.some((r) => r.id === row.id)) continue;
        if (row.notes) fd.append("notes", row.notes);
        if (![...fd.keys()].includes("files")) {
          _guestFlushErr = L("Foto konnte nicht geladen werden");
          failed += 1;
          break;
        }
        const r = await api("/api/app/collection/items", { method: "POST", body: fd });
        const latest = guestDraftRows();
        setGuestDraftRows(latest.filter((r0) => r0.id !== row.id));
        if (r && r.item_id) {
          uploaded += 1;
          lastItemId = r.item_id;
          if (state.watchNew === row.id || !state.watchNew) state.watchNew = r.item_id;
        }
      } catch (e) {
        _guestFlushErr = e.message || L("Entwurf konnte nicht gespeichert werden");
        failed += 1;
        break;
      }
    }
    applyGuestItems();
    if (failed) {
      paintGuestSaveBar();
      toast(_guestFlushErr || L("Entwurf konnte nicht gespeichert werden"));
      if (uploaded) toast(L("Teilweise gespeichert — restliche Entwürfe bleiben auf dem Gerät."));
    } else {
      _guestFlushErr = "";
      paintGuestSaveBar();
      if (uploaded === 1) toast(L("Entwurf gespeichert. Analyse läuft."), "check");
      else if (uploaded > 1) toast(LF("{0} Entwürfe gespeichert. Analyse läuft.", uploaded), "check");
    }
    if (uploaded && !isGuest()) loadCollection();
    return { uploaded, failed, itemId: lastItemId };
  })();
  try {
    const result = await run;
    finish(result);
    return result;
  } catch (e) {
    finish({ uploaded: 0, failed: 1 });
    throw e;
  } finally {
    flushGuestDrafts._busy = null;
  }
}

function saveLoginPending(extra = {}) {
  try {
    sessionStorage.setItem("sero_login_pending", JSON.stringify({
      identifier: ($("loginId") && $("loginId").value || "").trim(),
      hint: ($("codeHint") && $("codeHint").textContent) || "",
      ts: Date.now(),
      ...extra,
    }));
  } catch (_) { /* privat / voll */ }
}

function clearLoginPending() {
  try { sessionStorage.removeItem("sero_login_pending"); } catch (_) { /* */ }
}

function restoreLoginPending() {
  let raw;
  try { raw = sessionStorage.getItem("sero_login_pending"); } catch (_) { return false; }
  if (!raw) return false;
  let data;
  try { data = JSON.parse(raw); } catch (_) { clearLoginPending(); return false; }
  if (!data || !data.identifier || !data.ts || Date.now() - data.ts > 15 * 60 * 1000) {
    clearLoginPending();
    return false;
  }
  if ($("loginId")) $("loginId").value = data.identifier;
  if ($("loginSignupCard")) $("loginSignupCard").hidden = true;
  if ($("loginStep1")) $("loginStep1").hidden = true;
  if ($("loginStep2")) $("loginStep2").hidden = false;
  if ($("loginFootSignup")) $("loginFootSignup").hidden = true;
  if ($("loginFootLogin")) $("loginFootLogin").hidden = true;
  if ($("codeHint") && data.hint) $("codeHint").textContent = data.hint;
  return true;
}

/** 401 während Anmeldung darf die Seite NICHT neu laden (Code-Schritt weg). */
function reloadIfSessionLost() {
  if (onLoginScreen() || !state.me) return;
  location.reload();
}

async function enterAppAfterSession() {
  clearLoginPending();
  $("viewLogin").hidden = true;
  closeSheet();
  state.me = await api("/api/me").catch(() => null);
  if (!state.me) {
    toast(L("Anmeldung fehlgeschlagen"));
    enterGuestApp();
    return;
  }
  showApp();
  await flushGuestDrafts();
}

$("loginNext").onclick = async () => {
  const id = $("loginId").value.trim();
  $("loginErr1").textContent = "";
  if (!id) return;
  $("loginNext").disabled = true;
  try {
    const r = await post("/api/login-code", { identifier: id });
    if (r.ok) {
      await enterAppAfterSession();
      return;
    }
    $("loginStep1").hidden = true;
    $("loginSignupCard").hidden = true;
    $("loginStep2").hidden = false;
    $("loginFootSignup").hidden = true;
    $("loginFootLogin").hidden = true;
    if (r.dev_code) {
      $("codeHint").textContent = LF("Test-Modus (kein Mailversand) — dein Code: {0}", r.dev_code);
      $("loginCode").value = r.dev_code;
    } else if (r.via === "admin_telegram" || r.via === "telegram_admin") {
      $("codeHint").textContent = L("Dein Code geht an Sven per Telegram — er gibt ihn dir.");
    } else if (r.via === "telegram") {
      $("codeHint").textContent = L("SERO hat dir den Code per Telegram geschickt.");
    } else {
      $("codeHint").textContent = L("SERO hat dir einen Code geschickt.");
    }
    saveLoginPending({ via: r.via || null });
    $("loginCode").focus();
  } catch (e) {
    $("loginErr1").textContent = e.message;
  } finally {
    $("loginNext").disabled = false;
  }
};

$("loginId").addEventListener("keydown", (e) => { if (e.key === "Enter") $("loginNext").click(); });
$("loginCode").addEventListener("keydown", (e) => { if (e.key === "Enter") $("loginVerify").click(); });

async function doSignup() {
  const email = ($("signupEmail").value || "").trim();
  const username = ($("signupUser").value || "").trim();
  $("signupErr").textContent = "";
  if (!email || !username) {
    $("signupErr").textContent = L("Bitte E-Mail und Benutzername angeben.");
    return;
  }
  $("signupBtn").disabled = true;
  try {
    const r = await post("/api/signup", { email, username });
    if (r.ok) {
      await enterAppAfterSession();
      return;
    }
    $("loginId").value = email;
    $("loginSignupCard").hidden = true;
    $("loginStep1").hidden = true;
    $("loginStep2").hidden = false;
    $("loginFootSignup").hidden = true;
    $("loginFootLogin").hidden = true;
    if (r.dev_code) {
      $("codeHint").textContent = LF("Test-Modus (kein Mailversand) — dein Code: {0}", r.dev_code);
      $("loginCode").value = r.dev_code;
    } else {
      $("codeHint").textContent = L("Konto angelegt. Prüfe deine E-Mail für den Code.");
    }
    saveLoginPending({ via: "signup" });
    $("loginCode").focus();
  } catch (e) {
    $("signupErr").textContent = e.message;
  } finally {
    $("signupBtn").disabled = false;
  }
}
$("signupBtn").onclick = doSignup;
$("signupUser").addEventListener("keydown", (e) => { if (e.key === "Enter") doSignup(); });
$("signupEmail").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); $("signupUser").focus(); }
});


$("loginPhoneBack") && ($("loginPhoneBack").onclick = () => {
  $("loginPhoneCard").hidden = true;
  $("loginPhoneStep2").hidden = true;
  $("loginStep1").hidden = false;
  $("loginFootSignup").hidden = false;
  if ($("loginPhoneErr")) $("loginPhoneErr").textContent = "";
});

$("loginPhoneNext") && ($("loginPhoneNext").onclick = async () => {
  const phone = ($("loginPhone").value || "").trim();
  $("loginPhoneErr").textContent = "";
  if (!phone) return;
  $("loginPhoneNext").disabled = true;
  try {
    const r = await post("/api/auth/phone/start", { phone });
    $("loginPhoneCard").hidden = true;
    $("loginPhoneStep2").hidden = false;
    if (r.dev_code) {
      $("loginPhoneCode").value = r.dev_code;
      toast(LF("Test-Modus (kein Mailversand) — dein Code: {0}", r.dev_code), "check");
    } else {
      toast(L("SMS-Code geschickt."), "check");
    }
    $("loginPhoneCode").focus();
  } catch (e) {
    $("loginPhoneErr").textContent = e.message;
  } finally {
    $("loginPhoneNext").disabled = false;
  }
});

$("loginPhoneVerify") && ($("loginPhoneVerify").onclick = async () => {
  $("loginPhoneErr2").textContent = "";
  $("loginPhoneVerify").disabled = true;
  try {
    await post("/api/auth/phone/verify", {
      phone: ($("loginPhone").value || "").trim(),
      code: ($("loginPhoneCode").value || "").trim(),
    });
    await enterAppAfterSession();
  } catch (e) {
    $("loginPhoneErr2").textContent = e.message;
  } finally {
    $("loginPhoneVerify").disabled = false;
  }
});

$("loginVerify").onclick = async () => {
  $("loginErr2").textContent = "";
  $("loginVerify").disabled = true;
  try {
    await post("/api/login-verify", { identifier: $("loginId").value.trim(), code: $("loginCode").value.trim() });
    await enterAppAfterSession();
  } catch (e) {
    $("loginErr2").textContent = e.message;
  } finally {
    $("loginVerify").disabled = false;
  }
};

/* First-Run: Splash + 3 Screens. Skip und Abschluss setzen dasselbe Flag. */
const TOUR_PAGES = [
  ["camera", "Fotografieren.", "Ein Foto reicht."],
  ["pencil", "Prüfen.", "SERO legt einen Entwurf. Nichts geht live."],
  ["stack", "In der Sammlung.", "Live auf eBay nur, wenn du es willst."],
];

function tourStorageKey() {
  const wer = (state.me && (state.me.email || state.me.id)) || "anon";
  return "sero_tour_v3_" + String(wer);
}

function shouldShowOnboard() {
  if (storeSafe.getString(tourStorageKey()) || storeSafe.getString("sero_onboard_v1") || storeSafe.getString("sero_tour")) return false;
  if ((state.items || []).length > 0) return false;
  try {
    const cached = cache.get("col");
    if (cached && (cached.items || []).length) return false;
  } catch (_) { /* */ }
  return true;
}

function showTour() {
  if (!shouldShowOnboard()) return;
  const el = document.createElement("div");
  el.className = "party tour";
  let page = 0;
  const paint = () => {
    const [, h, p] = TOUR_PAGES[page];
    const last = page === TOUR_PAGES.length - 1;
    el.innerHTML = `
      <div class="party-card tour-card">
        <img class="tour-wordmark logo-light" src="assets/wordmark-navy.png?v=2" alt="SERO">
        <img class="tour-wordmark logo-dark" src="assets/wordmark-white.png?v=2" alt="SERO">
        <button type="button" class="tour-skip" id="tourSkip">${L("Überspringen")}</button>
        <h2>${L(h)}</h2>
        <p class="tour-lead voll">${L(p)}</p>
        <div class="tour-dots" aria-hidden="true">${
          TOUR_PAGES.map((_, i) => `<span class="${i === page ? "on" : ""}"></span>`).join("")
        }</div>
        <div class="party-actions">
          ${last
            ? `<button class="btn-primary" id="tourScan">${L("Artikel fotografieren")}</button>`
            : `<button class="btn-primary" id="tourNext">${L("Weiter")}</button>`}
        </div>
      </div>`;
    const schliessen = () => {
      storeSafe.setString(tourStorageKey(), "1");
      storeSafe.setString("sero_tour", "1");
      storeSafe.setString("sero_onboard_v1", "1");
      el.classList.add("out");
      setTimeout(() => el.remove(), 300);
    };
    const next = el.querySelector("#tourNext");
    if (next) next.onclick = () => { page += 1; paint(); };
    const skip = el.querySelector("#tourSkip");
    if (skip) skip.onclick = schliessen;
    const scan = el.querySelector("#tourScan");
    if (scan) scan.onclick = () => {
      // Kamera synchron im Gesten-Kontext öffnen (iOS)
      startScanMode("SELL_SINGLE");
      schliessen();
    };
  };
  paint();
  document.body.appendChild(el);
}

function dismissSplash() {
  const sp = $("splash");
  if (sp) { sp.classList.add("done"); setTimeout(() => sp.remove(), 500); }
}

/* ── Sicherheitsnetz: die App darf NIE stumm im Startbildschirm hängen ──
   Bricht das Skript ab (z. B. altes HTML aus dem Cache + neues JS), lief
   boot() nie zu Ende und der Splash blieb für immer stehen. */
setTimeout(() => {
  const sp = $("splash");
  if (!sp || sp.classList.contains("done")) return;
  dismissSplash();
  const app = $("viewApp"), login = $("viewLogin");
  if (app && app.hidden && login && login.hidden) {
    document.body.insertAdjacentHTML("beforeend", `
      <div class="boot-err">
        <b>Die App konnte nicht starten.</b>
        <p>Meist hilft ein vollständiges Neuladen: Seite schließen und erneut öffnen.
           Bleibt es dabei, hilft der Knopf unten.</p>
        <button class="btn-primary" onclick="location.reload(true)">Neu laden</button>
        <button class="btn-secondary" id="bootReset">Zwischenspeicher leeren</button>
        <small id="bootErrMsg"></small>
      </div>`);
    const msg = window.__bootError ? String(window.__bootError) : "";
    if (msg) $("bootErrMsg").textContent = msg.slice(0, 300);
    $("bootReset").onclick = async () => {
      try { localStorage.clear(); sessionStorage.clear(); } catch { /* egal */ }
      try {
        if (window.caches) for (const k of await caches.keys()) await caches.delete(k);
      } catch { /* egal */ }
      location.replace(location.pathname + "?frisch=" + Date.now());
    };
  }
}, 6000);

/* Fehler sichtbar machen statt still scheitern */
addEventListener("error", (e) => {
  window.__bootError = (e.error && e.error.message) || e.message || "Unbekannter Fehler";
  SM.errors.push({ area: "window.error", type: (e.error && e.error.name) || "Error" });
});
addEventListener("unhandledrejection", (e) => {
  window.__bootError = (e.reason && e.reason.message) || String(e.reason || "");
  SM.errors.push({ area: "unhandledrejection", type: (e.reason && e.reason.name) || "Rejection" });
});
/* Viewport-Höhe für Sheets / Tastatur */
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => SM.installViewportController());
} else {
  SM.installViewportController();
}

function showApp() {
  /* Der Sammlungs-Cache gehörte bisher dem GERÄT, nicht dem Konto: lief die
     Session ab und meldete sich jemand anderes an, sah er beim Start die
     komplette Sammlung des Vorgängers (Namen, Werte, Statistiken), bis der
     Server sie ersetzte. Jetzt trägt der Cache den Kontobesitzer — bei einem
     Wechsel werden alle Daten-Reste verworfen, bevor irgendetwas rendert. */
  const wer = (state.me && (state.me.email || state.me.id)) || "";
  if (wer && storeSafe.getString("sero_owner") !== String(wer)) {
    ["sero_col", "sero_milestone", "sero_home_items", "sero_sell_tpl",
     "sero_hero_img", "sero_hero_grad"]
      .forEach((k) => storeSafe.remove(k));
    storeSafe.setString("sero_owner", String(wer));
  }
  $("viewApp").hidden = false;
  paintTopAva();
  paintTopTools();
  paintTopbarSection("tabCollection");
  // Altes Rot-Preset (Sonnenuntergang) → Brand-Navy
  const hg = storeSafe.getString("sero_hero_grad") || "";
  if (/#b45309|#9d174d|#4c0519/i.test(hg)) {
    storeSafe.setString("sero_hero_grad", HERO_BRAND);
  }
  if (!state.range) state.range = "Max";
  setTimeout(dismissSplash, 350);
  if (shouldShowOnboard()) setTimeout(showTour, 850);
  attachPTR($("homeScroll"), async () => { await loadDashboard(); await loadCollection(); });
  attachPTR($("colScroll"), () => loadCollection());
  if ($("salesScroll")) {
    attachPTR($("salesScroll"), async () => {
      await loadSales(true);
      toast(L("Verkauf aktualisiert"), "check");
    });
  }
  if (isGuest()) {
    applyGuestItems();
    paintGuestSaveBar();
    renderCollection();
    switchTab("tabCollection");
    return;
  }
  const cached = cache.get("col");
  if (cached) {
    state.items = cached.items || [];
    state.stats = cached.stats;
    state.history = cached.history || [];
    state.historyByCat = cached.history_by_cat || {};
    applyGuestItems();
    renderCollection();
  }
  // Aufräumen: Reste des entfernten Verschiebe-Modus
  storeSafe.remove("sero_home_order");
  storeSafe.remove("sero_home_hidden");
  // Einstellungen früh laden — Zeit-Bilanz, Scanner-Zahlen und das Scan-Banner
  // hängen daran; ohne sie blieben die Bausteine beim Start unsichtbar.
  api("/api/app/settings").then((s) => {
    state.settings = s;
    if (state.dash) renderDashboard();
    { const _ts = $("tabScan"); if (_ts && !_ts.hidden) renderScan(); }
  }).catch(() => {});
  loadDashboard();
  loadCollection();
  loadSales();
  switchTab("tabCollection");
}

/* ═══════════════════ eBay-Hub (Revolut-Look, nur API-Daten) ═══════════════════ */

function ebayHubChartPoints(sales) {
  const ended = (sales && sales.ended) || [];
  const pts = [];
  for (const r of ended) {
    const ts = Number(r.sold_at || r.ends_at || 0);
    const raw = r.sold_price != null && r.sold_price !== "" ? r.sold_price : r.price;
    const price = parseFloat(String(raw || "").replace(",", "."));
    if (!ts || !isFinite(price) || price < 0) continue;
    pts.push({ t: ts > 1e12 ? ts : ts * 1000, v: price });
  }
  pts.sort((a, b) => a.t - b.t);
  if (pts.length >= 2) {
    let acc = 0;
    return pts.map((p) => { acc += p.v; return { v: acc, t: p.t }; });
  }
  const stats = (sales && sales.stats) || {};
  const live = Number(stats.value_active || 0);
  const sold = Number(stats.value_sold || 0);
  if (pts.length === 1) {
    const one = pts[0].v;
    const t1 = pts[0].t;
    if (live > 0) return [{ v: 0, t: null }, { v: one, t: t1 }, { v: one + live, t: null }];
    return [{ v: 0, t: null }, { v: one, t: t1 }];
  }
  if (sold > 0 && live > 0) return [{ v: 0, t: null }, { v: sold, t: null }, { v: sold + live, t: null }];
  if (sold > 0) return [{ v: 0, t: null }, { v: sold, t: null }];
  if (live > 0) return [{ v: 0, t: null }, { v: live, t: null }];
  return [];
}
function ebayHubChartValues(sales) {
  const pts = ebayHubChartPoints(sales);
  if (!pts.length) return [0, 0];
  return pts.map((p) => p.v);
}
function colHubRestValue(sales) {
  const stats = (sales && sales.stats) || {};
  const live = Number(stats.value_active);
  if (isFinite(live) && live > 0) return live;
  const pts = ebayHubChartPoints(sales);
  if (pts.length) {
    const last = pts[pts.length - 1].v;
    if (isFinite(last) && last > 0) return last;
  }
  const sold = Number(stats.value_sold);
  if (isFinite(sold) && sold > 0) return sold;
  return null;
}

/** 30-Tage-Delta nur aus datierten Punkten. Nie raten, nie LLM, kein Fake-Prozent. */
function colHubDeltaFromPoints(pts, nowMs) {
  const windowMs = 30 * 86400000;
  const dated = [];
  for (const p of pts || []) {
    if (!p) continue;
    const t = Number(p.t);
    const v = Number(p.v);
    if (!t || !isFinite(t) || !isFinite(v)) continue;
    dated.push({ t, v });
  }
  dated.sort((a, b) => a.t - b.t);
  if (!dated.length) return { kind: "none" };
  const nowV = dated[dated.length - 1].v;
  const tNow = nowMs != null && isFinite(Number(nowMs)) ? Number(nowMs) : Date.now();
  const cutoff = tNow - windowMs;
  let thenPt = null;
  for (let i = dated.length - 1; i >= 0; i--) {
    if (dated[i].t <= cutoff) { thenPt = dated[i]; break; }
  }
  if (thenPt) {
    const thenV = thenPt.v;
    const euro = nowV - thenV;
    const pct = thenV === 0 ? null : (nowV - thenV) / thenV;
    return { kind: "d30", now: nowV, then: thenV, euro, pct };
  }
  if (dated.length < 2) return { kind: "none" };
  const thenV = dated[0].v;
  const euro = nowV - thenV;
  if (!isFinite(euro) || Math.abs(euro) < 0.005) return { kind: "none" };
  const pct = thenV === 0 ? null : (nowV - thenV) / thenV;
  return { kind: "since_start", now: nowV, then: thenV, euro, pct, since: dated[0].t };
}

function colHubHistoryPoints(history, asOfDay, liveCollection) {
  const series = histWithLive(history || [], liveCollection, asOfDay);
  const out = [];
  for (const p of series) {
    if (!p || !p.day || !/^\d{4}-\d{2}-\d{2}$/.test(p.day)) continue;
    const t = new Date(p.day + "T12:00:00").getTime();
    const v = Number(p.value);
    if (!isFinite(t) || !isFinite(v)) continue;
    out.push({ t, v });
  }
  return out;
}

function colHubSalesDatedPoints(sales) {
  const out = [];
  for (const p of ebayHubChartPoints(sales) || []) {
    if (!p) continue;
    const t = Number(p.t);
    const v = Number(p.v);
    if (!t || !isFinite(t) || !isFinite(v)) continue;
    out.push({ t, v });
  }
  return out;
}

/** Zuerst Collection-Verlauf (schon geladen), sonst kumulierte Sales mit Datum. */
function colHubDeltaSeries(sales, history, asOfDay, liveCollection, nowMs) {
  const histDelta = colHubDeltaFromPoints(colHubHistoryPoints(history, asOfDay, liveCollection), nowMs);
  if (histDelta.kind === "d30") return histDelta;
  const salesDelta = colHubDeltaFromPoints(colHubSalesDatedPoints(sales), nowMs);
  if (salesDelta.kind === "d30") return salesDelta;
  if (histDelta.kind === "since_start") return histDelta;
  if (salesDelta.kind === "since_start") return salesDelta;
  return { kind: "none" };
}

function fmtColHubPct(pct) {
  if (pct == null || !isFinite(pct)) return "";
  const n = pct * 100;
  const abs = Math.abs(n).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const sign = n > 0.05 ? "+" : n < -0.05 ? "−" : "";
  return `${sign}${abs} %`;
}

function fmtColHubEuro(euro) {
  const n = Number(euro);
  if (!isFinite(n)) return "";
  const sign = n > 0.005 ? "+" : n < -0.005 ? "−" : "";
  return sign + money(Math.abs(n));
}

function colHubDeltaHtml(delta, hidden) {
  const d = delta || { kind: "none" };
  let nums = "—";
  let lab = L("30 Tage");
  let dir = "";
  if (hidden) {
    nums = "••••";
  } else if (d.kind === "d30" || d.kind === "since_start") {
    const parts = [];
    if (d.kind === "d30" && d.pct != null && isFinite(d.pct) && d.then !== 0) {
      parts.push(fmtColHubPct(d.pct));
    }
    if (isFinite(d.euro)) parts.push(fmtColHubEuro(d.euro));
    if (parts.length) nums = parts.join(" · ");
    if (d.kind === "since_start") lab = L("seit Start");
    if (isFinite(d.euro)) {
      if (d.euro > 0.005) dir = "up";
      else if (d.euro < -0.005) dir = "down";
    }
  }
  const aria = `${nums} ${lab}`.trim();
  return `<div class="col-hub-delta${dir ? ` ${dir}` : ""}" id="colHubDelta" aria-label="${esc(aria)}">
    <span class="col-hub-delta-nums">${esc(nums)}</span>
    <span class="col-hub-delta-lab">${esc(lab)}</span>
  </div>`;
}

function colHubDeltaFromState() {
  const hiddenVals = storeSafe.getString("sero_hide") === "1";
  const histLive = Number((state.stats || {}).total_value);
  const live = isFinite(histLive) ? histLive : null;
  return colHubDeltaHtml(
    colHubDeltaSeries(state.sales, state.history, state.asOfDay, live),
    hiddenVals);
}

function refreshColHubDelta() {
  const html = colHubDeltaFromState();
  const el = $("colHubDelta");
  if (el) el.outerHTML = html;
  else {
    const sumEl = $("colHubSum");
    if (sumEl) sumEl.insertAdjacentHTML("afterend", html);
  }
}

function colHubChartMarkup(pts) {
  const values = pts.map((p) => p.v);
  return `<div class="ebay-hub-chart" id="colHubChart" role="img" aria-hidden="true">
    ${sparkline(values, COL_HUB_CHART_W, COL_HUB_CHART_H, "ebay-hub-spark col-hair sline", false)}
    <div class="ebay-hub-scrub" hidden>
      <i class="ebay-hub-hair"></i>
      <i class="ebay-hub-dot"></i>
    </div>
  </div>`;
}

function _resamplePts(attr, n) {
  const raw = String(attr || "").trim().split(/\s+/).map((p) => {
    const [x, y] = p.split(",");
    return { x: Number(x), y: Number(y) };
  }).filter((p) => isFinite(p.x) && isFinite(p.y));
  if (raw.length < 2) return [];
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1) * (raw.length - 1);
    const a = raw[Math.floor(t)];
    const b = raw[Math.min(raw.length - 1, Math.ceil(t))];
    const f = t - Math.floor(t);
    out.push({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f });
  }
  return out;
}

function morphColHubChart(prevAttr, chartEl) {
  const poly = chartEl && chartEl.querySelector("polyline");
  if (!poly || !prevAttr) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const toAttr = poly.getAttribute("points") || "";
  const from = _resamplePts(prevAttr, 24);
  const dest = _resamplePts(toAttr, 24);
  if (from.length < 2 || dest.length < 2) return;
  const t0 = performance.now();
  const dur = 280;
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  const fmt = (pts) => pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const step = (now) => {
    const p = Math.min(1, (now - t0) / dur);
    const e = ease(p);
    const mid = from.map((a, i) => ({
      x: a.x + (dest[i].x - a.x) * e,
      y: a.y + (dest[i].y - a.y) * e,
    }));
    poly.setAttribute("points", p < 1 ? fmt(mid) : toAttr);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function colRangeDays() {
  return { "7T": 7, "30T": 30, "1J": 365 }[state.colRange || "30T"] || 30;
}

function colChartPoints(wertItems, liveValue, filterAn) {
  const series = collectionHistSeries(wertItems, liveValue, state.asOfDay, filterAn);
  const cutoff = Date.now() - colRangeDays() * 86400000;
  const pts = [];
  for (const p of series || []) {
    if (!p || !p.day) continue;
    const t = new Date(p.day + "T12:00:00").getTime();
    const v = Number(p.value);
    if (!isFinite(t) || !isFinite(v)) continue;
    if (t >= cutoff) pts.push({ t, v });
  }
  return pts;
}
function bindColHubScrub(pts, restVal, hiddenVals) {
  const el = $("colHubChart");
  if (!el || hiddenVals) return;
  const sumEl = $("colHubSum");
  const restText = restVal != null && isFinite(restVal)
    ? money(restVal)
    : (sumEl ? sumEl.textContent : "—");
  bindChartScrub(el, pts, {
    sumEl,
    dateEl: $("colHubDate"),
    restText,
    hidden: hiddenVals,
  });
}
function refreshColHubFromSales() {
  /* Sammlung-Hero bleibt Sammlungs-Wert und History.
     Verkaufszahlen, +% und Grün gehören nicht auf diesen Screen. */
}

function ebayHubDesignItems() {
  return (state.items || []).filter((i) =>
    i && !i.wishlist && (i.design_photo || i.design_status === "ready" || i.design_status === "running"));
}

function ebayHubRow(kind, id, photo, title, meta, extra = {}) {
  const item = extra.item || "";
  const draft = extra.draft || "";
  return `<button type="button" class="sale-row ebay-hub-row" data-hub="${esc(kind)}" data-id="${esc(id || "")}" data-item="${esc(item)}" data-draft="${esc(draft)}">
    ${photo ? `<img src="${esc(thumb(photo, 240))}" loading="lazy" alt="">` : `<span class="mv-ph">${typeof MONO_PH !== "undefined" ? MONO_PH : ""}</span>`}
    <span class="sr-body"><span class="sr-t">${esc(title || "—")}</span>
      ${meta ? `<span class="sr-m">${esc(meta)}</span>` : ""}</span>
    <span class="chev">${icon("chevron", 15)}</span>
  </button>`;
}

async function ebayHubOpenRow(kind, itemId, draftId, fallbackId) {
  if (kind === "design") {
    const id = itemId || fallbackId;
    if (id) return openItemDetail(id);
    return;
  }
  if (itemId) return openItemDetail(itemId, "sell");
  if (draftId) {
    try {
      const r = await post(`/api/app/collection/adopt/${draftId}`);
      loadCollection();
      if (r && r.item_id) return openItemDetail(r.item_id, "sell");
    } catch (_) { /* */ }
    if (typeof openDraftDetail === "function") return openDraftDetail(draftId);
  }
}

function ebayHubCap(key, n) {
  const all = state.ebayHubShowAll && state.ebayHubShowAll[key];
  return all ? n : Math.min(n, 12);
}

function paintEbayHub() {
  /* Sammlung zeigt eigene Stücke, keine Live-/Verkauft-Listen. */
  const sc = $("colEbayHub");
  if (!sc) return;
  sc.innerHTML = "";
}

async function renderEbayHub() {
  paintEbayHub();
  try { await loadSales(true); } catch (_) { /* */ }
  paintEbayHub();
}
window.renderEbayHub = renderEbayHub;
window.openSeroProfile = openSeroProfile;

const TAB_ORDER = ["tabHome", "tabCollection", "tabSales", "tabProfile"];
function switchTab(id) {
  // Richtung merken, BEVOR die alte Seite versteckt wird — die neue Seite
  // schiebt sich dann aus der logischen Richtung herein (räumliche Kontinuität)
  const prev = TAB_ORDER.findIndex((t) => { const p = $(t); return p && !p.hidden; });
  const next = TAB_ORDER.indexOf(id);
  document.querySelectorAll(".tab").forEach((x) => {
    const on = x.dataset.tab === id;
    x.classList.toggle("active", on);
    if (on) x.setAttribute("aria-current", "page");
    else x.removeAttribute("aria-current");
    if (on) {
      const tic = x.querySelector(".tic");
      if (tic && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        tic.classList.remove("lens-go");
        void tic.offsetWidth;
        tic.classList.add("lens-go");
      }
    }
  });
  document.querySelectorAll(".tab-page").forEach((p) => {
    const on = p.id === id;
    p.hidden = !on;
    if (on) p.removeAttribute("aria-hidden");
    else p.setAttribute("aria-hidden", "true");
  });
  paintTopbarSection(id);
  const review = $("scanReview");
  if (review) review.hidden = true;
  const cam = $("btnCamera");
  if (cam) {
    cam.classList.remove("active");
    cam.removeAttribute("aria-current");
  }
  const page = $(id);
  page.classList.remove("page-enter", "page-enter-l", "page-enter-r");
  void page.offsetWidth;               // Animation neu triggern
  page.classList.add(prev >= 0 && next >= 0 && next < prev ? "page-enter-l" : "page-enter-r");
  if (id === "tabHome") loadDashboard({ background: !!state.dash || !!state._dashStale });
  if (id === "tabCollection") loadCollection();
  if (id === "tabSales") {
    state.salesBucket = "draft";
    state.salesSelectMode = false;
    loadSales(true); startSalesPoll(); loadScanSession();
  }
  else stopSalesPoll();
  if (false && id === "tabScan") {
    renderScan();
    try { trackFunnel("scan_opened"); } catch (_) { /* */ }
  }
}
document.querySelectorAll(".tab").forEach((t) => { t.onclick = () => switchTab(t.dataset.tab); });

/* ═══════════════════ Dashboard ═══════════════════ */

const skel = (h, r = 16) => `<div class="skel" style="height:${h}px;border-radius:${r}px"></div>`;

async function loadDashboard(opts = {}) {
  if (isGuest()) return;
  const el = $("homeScroll");
  const background = !!(opts && opts.background);
  // Cache sofort zeigen — Skeleton nur beim allerersten Besuch ohne Daten.
  // Früher: closeDetail setzte dash=null → jedes Zurück zur Startseite = Skeleton + Wartezeit.
  if (state.dash) {
    if (!el.querySelector(".ov-hero, .h-value, .ov-value, .ov-card")) {
      try { renderDashboard(); } catch (_) { /* */ }
    }
  } else if (!background) {
    el.innerHTML = `${skel(150, 20)}<div style="height:14px"></div>${skel(90)}<div style="height:14px"></div>${skel(90)}`;
  }
  const ticket = dashWins.begin();
  let d;
  try {
    d = await api("/api/app/dashboard", { signal: ticket.signal, timeout: 20000 });
  } catch (e) {
    if (e.superseded) return;
    if (e.status === 401) reloadIfSessionLost();
    // Bei Timeout/Netz: alten Stand lassen, nicht leer stehen
    if (state.dash && !el.querySelector(".ov-hero, .h-value, .ov-value, .ov-card")) {
      try { renderDashboard(); } catch (_) { /* */ }
    }
    return;
  }
  if (!ticket.isCurrent()) return;
  state._dashStale = false;
  const sig = JSON.stringify(d);
  if (state._dashSig === sig) {
    state.dash = d;
    if (!el.querySelector(".ov-hero, .h-value, .ov-value, .ov-card")) renderDashboard();
    return;
  }
  state._dashSig = sig;
  state.dash = d;
  renderDashboard();
}

/* Scroll-Verdichtung ohne Mini-Wert-Pille in der Topbar */
const miniWiredTabs = {};
function wireMiniVal(tabId, _valText) {
  const page = $(tabId);
  const sc = page && page.querySelector(".page-scroll");
  if (!sc) return;
  const mv = $("miniVal");
  if (mv) mv.classList.remove("show");
  if (miniWiredTabs[tabId]) return;
  miniWiredTabs[tabId] = true;
  sc.addEventListener("scroll", () => {
    if (page.hidden) return;
    sc.classList.toggle("condensed", sc.scrollTop > 40);
  }, { passive: true });
}
/* ═══════════ Übersicht: feste Bausteine ═══════════
   Jede Sektion ist eine reine Funktion (HTML-String). */

const HOME_SECS = [
  /* Zahlen-Kacheln entfallen — der TradingView-Verlauf ersetzt den Statistik-Block. */

  /* Wertvollste Stücke — eigene Karte unter dem Verlauf. */
  { key: "stuecke", label: "Deine Sammlung", fn: (d, hidden) => {
    const top = d.top_items || [];
    if (!top.length) return "";
    return `<div class="ov-card">
      <div class="ov-card-head">
        <div class="ov-card-title">${L("Deine Sammlung")}</div>
      </div>
      ${top.map((t) => {
        const pct = t.delta7 && t.value ? (t.delta7 / (t.value - t.delta7) * 100) : null;
        const seal = gradeSeal(t.graded, t.name);
        const sub = seal.text || "";
        return `<button class="mv-row" data-item="${t.id}">
          ${t.photo ? `<img src="${esc(thumb(t.photo, 240))}" loading="lazy" alt="">` : `<span class="mv-ph">${MONO_PH}</span>`}
          <span class="mv-name">${esc(t.name)}<br><i class="mv-sub">${esc(sub)}${t.qty > 1 ? ` · ×${t.qty}` : ""}</i></span>
          <span class="mv-val"><span class="hideable ${hidden ? "veiled" : ""}">${money(t.value)}</span><br>
            ${pct !== null && isFinite(pct) && Math.abs(pct) >= 0.1 ? `<i class="${pct >= 0 ? "up" : "down"}" style="font-weight:700">${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(2).replace(".", ",")} %</i>` : ""}</span>
        </button>`; }).join("")}
      <button class="ov-viewall" id="topViewAll">${L("Alle ansehen")}</button>
    </div>`; } },

  { key: "effekt", label: "Dein SERO-Effekt", fn: (d) => {
    const imp = d.impact || {};
    const n = imp.successful_scans || 0;
    if (n < 1) return "";
    const manual = Math.max(0, Number(imp.manual_seconds) || 0);
    const sero = Math.max(0, Number(imp.sero_seconds) || 0);
    const saved = Math.max(0, Number(imp.saved_seconds) || 0);
    const seroPct = Math.min(100, Math.max(4, Math.round(100 * sero / Math.max(1, manual))));
    const sub = n === 1
      ? L("mit 1 erfassten Stück")
      : LF("mit {0} erfassten Stücken", n);
    return `<div class="impact-card">
      <div class="impact-card-head">
        <div class="impact-card-title">${L("Dein SERO-Effekt")}</div>
        <span class="impact-badge">${L("Zeit gespart")}</span>
      </div>
      <div class="impact-value tnum">${esc(formatDuration(saved))}</div>
      <div class="impact-sub">${esc(sub)}</div>
      <div class="impact-bars" aria-hidden="true">
        <div class="impact-bar-row">
          <span class="impact-bar-lab">${L("Von Hand")}</span>
          <span class="impact-bar-track"><i style="width:100%"></i></span>
          <span class="impact-bar-val tnum">${esc(formatDuration(manual))}</span>
        </div>
        <div class="impact-bar-row">
          <span class="impact-bar-lab">${L("Mit SERO")}</span>
          <span class="impact-bar-track"><i style="width:${seroPct}%"></i></span>
          <span class="impact-bar-val tnum">${esc(formatDuration(sero))}</span>
        </div>
      </div>
      <button type="button" class="impact-how" id="btnImpactHow">${L("So wird gerechnet")}</button>
    </div>`; } },

  { key: "aktivitaet", label: "Letzte 7 Tage", fn: (d) => {
    const a = d.activity_7d || {};
    const scanned = a.scanned || 0;
    const published = a.published || 0;
    const sold = a.sold || 0;
    const live = a.active_listings || 0;
    if (!scanned && !published && !sold && !live) return "";
    const tile = (n, label) => `<div class="act-tile">
      <b class="tnum">${n}</b><span>${esc(L(label))}</span></div>`;
    return `<div class="ov-card act-card">
      <div class="ov-card-title">${L("Letzte 7 Tage")}</div>
      <div class="act-row">
        ${tile(scanned, "gescannt")}
        ${tile(published, "neu gelistet")}
        ${tile(sold, "verkauft")}
        ${tile(live, "live")}
      </div>
    </div>`; } },

];

const FAQ_ITEMS = [
  ["Brauche ich einen eBay-Developer-Account?",
   "Nein. Kein Developer-Account, keine API-Keys. Du nimmst dein normales eBay-Verkäuferkonto: anmelden, Freigabe erteilen, den Link zurück in die App einfügen, fertig. SERO sieht dein Passwort nie."],
  ["Kann SERO etwas ohne mein Okay veröffentlichen?",
   "Nein. Ohne deinen Tipp geht nichts live — auch nicht versehentlich. Jedes Listing wartest du dir an und gibst es erst dann frei."],
  ["Liest SERO wirklich PSA-Labels vom Foto?",
   "Ja. Vom Slab-Foto kommen Bewerter, Note und Zertifikatsnummer in die eBay-Felder. Ist das Label unscharf, fragt SERO nach — geraten wird nicht."],
  ["Was passiert mit meinen Daten und Fotos?",
   "Deine Fotos und Stückdaten bleiben bei dir im Konto, solange das Stück in der Sammlung ist. Die eBay-Freigabe liegt verschlüsselt in der EU. Verkauft werden deine Daten nicht — bezahlt wird das Abo."],
  ["Welche Stücke funktionieren am besten?",
   "Am besten, wofür SERO gebaut ist: Sammelkarten roh und graded, Retro- und Videospiele, Manga und Comics. Andere Sammlerware oft auch — Alltagsprodukte eher nebenbei."],
  ["Kann ich jederzeit kündigen?",
   "Ja. Monatlich im Konto kündbar, ohne Mindestlaufzeit und ohne Anruf."],
];

function faqAccordionHtml(cls) {
  return `<div class="${esc(cls || "help-faq")}">
    ${FAQ_ITEMS.map(([q, a]) => `<details>
      <summary>${esc(L(q))}</summary>
      <p>${esc(L(a))}</p>
    </details>`).join("")}
  </div>`;
}
window.faqAccordionHtml = faqAccordionHtml;

function homeBuiltByFooter() {
  const alt = "Built by a seller who was sick of typing.";
  return `<div class="home-builtby">
    <img class="logo-light" src="assets/built-by-seller-light.png?v=6" alt="${esc(alt)}" width="4096" height="561" loading="lazy" decoding="async">
    <img class="logo-dark" src="assets/built-by-seller-dark.png?v=6" alt="" width="4096" height="548" loading="lazy" decoding="async">
  </div>`;
}

const HOME_DEFAULT = HOME_SECS.map((s) => s.key);

/* Feste Reihenfolge der Startseiten-Bausteine. */
function homeOrder() {
  return { order: HOME_DEFAULT.slice(), hidden: [] };
}

function renderHomeSections(d, hidden) {
  const { order, hidden: hid } = homeOrder();
  return order.map((key) => {
    const sec = HOME_SECS.find((s) => s.key === key);
    if (!sec || hid.includes(key)) return "";
    const html = sec.fn(d, hidden);
    if (!html) return "";
    return `<section class="home-sec" data-sec="${key}">${html}</section>`;
  }).join("");
}


function homeSellHero(d) {
  const me = state.me || {};
  const stats = (d && d.sales) || {};
  const draftN = Number(stats.pending || stats.drafts || 0) || 0;
  const ebayLine = me.setup_ready
    ? L("eBay verbunden — Entwürfe kannst du freigeben")
    : (me.ebay_connected
       ? L("eBay verbunden — Verkaufs-Setup noch abschließen")
       : L("Noch nicht mit eBay verbunden — Entwurf geht trotzdem"));
  const draftCard = draftN > 0
    ? `<button type="button" class="home-draft-card" id="homeDrafts">${LF("{0} Entwürfe warten auf Prüfung", draftN)}</button>`
    : "";
  return `<div class="home-sell-hero">
    <h1 class="home-sell-title">${L("Fotografieren. Prüfen. Bei eBay verkaufen.")}</h1>
    <p class="home-sell-lead">${L("SERO bereitet aus deinem Foto einen editierbaren eBay-Entwurf vor. Live geht es erst nach deiner Freigabe.")}</p>
    <div class="home-sell-actions">
      <button type="button" class="btn-primary" id="homeScanOne">${icon("camera", 18)}<span>${L("Artikel fotografieren")}</span></button>
      <div class="home-sell-chips">
        <button type="button" class="scan-chip" id="homeScanBatch">${icon("stack", 16)}<span>${L("Mehrere Produkte scannen")}</span></button>
        <button type="button" class="scan-chip" id="homeCollectOnly">${L("Nur zur Sammlung hinzufügen")}</button>
      </div>
    </div>
    <ul class="home-trust">
      <li>${L("Automatische Vorbereitung von Titel, Kategorie und Preisvorschlag")}</li>
      <li>${L("Alles änderbar, bevor etwas live geht")}</li>
      <li>${L("Veröffentlichen nur mit bewusstem Tipp")}</li>
    </ul>
    <p class="home-ebay-status">${esc(ebayLine)}</p>
    ${draftCard}
  </div>`;
}

function renderDashboard() {
  const d = state.dash;
  if (!d) return;
  const hist = (d.history || []).map((p) => p.value);
  const alertBox = (d.alerts_triggered || []).length ? `
    <div class="alert-box">
      <span class="ab-ic">${icon("bell", 18)}</span>
      <div>${d.alerts_triggered.map((a) => `
        <button class="ab-row" data-item="${a.item_id}"><b>${esc(a.name)}</b> ${LF("hat {0} erreicht (Alarm {1} {2})",
          money(a.value), a.direction === "above" ? L("über") : L("unter"), money(a.threshold))}</button>`).join("")}
      </div>
    </div>` : "";

  const me = state.me || {};
  const setupSteps = [
    ["eBay-Konto verbinden", me.ebay_connected],
    ["Verkaufs-Setup abschließen", me.setup_ready],
  ];
  const openSteps = setupSteps.filter(([, ok]) => !ok).length;
  const setupCard = openSteps ? `
    <button class="setup-card" id="setupCard">
      <div class="sc-head"><b>${L("Fast startklar")}</b><span>${LF("{0} von {1} Schritten", setupSteps.length - openSteps, setupSteps.length)}</span></div>
      ${setupSteps.map(([label, ok]) => `
        <div class="sc-step ${ok ? "done" : ""}"><span class="sc-tick">${icon(ok ? "check" : "chevron", 13)}</span>${L(label)}</div>`).join("")}
    </button>` : "";

  const range = state.range || "Max";
  const rangeDays = { "7T": 7, "1M": 30, "Max": 9999 }[range];
  const cutoffTs = Date.now() - rangeDays * 86400000;
  const histSeries = histWithLive(d.history || [], d.total_value, d.as_of_day)
    .filter((p) => new Date(p.day + "T12:00:00").getTime() >= cutoffTs);
  const histPts = histSeries.map((p) => p.value);
  // NUR Sammlungswert gegen Verlauf — grand_total enthält NFTs, der Verlauf nicht
  const serverDelta = { "7T": (d.deltas || {}).d7, "1M": (d.deltas || {}).d30, "Max": null };
  const rangeDelta = serverDelta[range] !== undefined && serverDelta[range] !== null
    ? serverDelta[range]
    : (histPts.length >= 2 ? d.total_value - histPts[0] : null);
  const hidden = storeSafe.getString("sero_hide") === "1";
  // Gibt es überhaupt einen Chart? Sonst wären die Zeitraum-Pillen tote Knöpfe.
  const hasChart = histPts.length >= 2;
  const grand = d.total_value;

  wireMiniVal("tabHome", hidden ? "••••" : money(grand));
  // Ohne ein einziges Stück ist die volle Übersicht sinnlos: 0,00 €, tote
  // Zeitraum-Pillen, drei Null-Kacheln. Stattdessen EIN klarer Einstieg.
  if (!d.count && !(d.sales.active || d.sales.pending)) {
    $("homeScroll").innerHTML = `
      ${homeSellHero(d)}
      <div class="tab-title-glass tab-title-flush page-tab-title">${titlePair("portfolio", "Portfolio")}</div>
      ${emptyState({
      icon: "scanframe", titel: "Noch kein Listing vorbereitet",
      text: "Fotografiere dein erstes Stück — SERO baut den eBay-Entwurf, die Sammlung wächst nebenbei.",
      aktion: "Artikel fotografieren", onAktion: () => { startScanMode("SELL_SINGLE"); },
    })}
      <div id="homeSecs">${renderHomeSections(d, false)}</div>
      ${homeBuiltByFooter()}`;
    wireHomeSellHero();
    return;
  }
  $("homeScroll").innerHTML = `
    ${homeSellHero(d)}
    <div class="tab-title-glass tab-title-flush page-tab-title">${titlePair("portfolio", "Portfolio")}</div>
    <div class="ov-hero">
      <div class="ov-value-row">
        ${hasChart ? `<div class="range-row ov-range">
          ${["7T", "1M", "Max"].map((r) => `<button class="range-pill ${range === r ? "on" : ""}" data-r="${r}">${L(r)}</button>`).join("")}
        </div>` : `<div class="ov-range"></div>`}
        <div class="ov-value-stack">
          <div class="ov-value hideable ${hidden ? "veiled" : ""}">${money(grand)}</div>
          <div class="ov-delta ${rangeDelta === null ? "" : rangeDelta >= 0 ? "up" : "down"} hideable ${hidden ? "veiled" : ""}">
            ${grand === 0 && d.sales.active > 0
              ? LF("Deine gesamte Sammlung ist gerade im Verkauf ({0})", money(d.sales.value_active))
              : rangeDelta === null ? ""
              : `${rangeDelta >= 0 ? "+" : "−"}${money(Math.abs(rangeDelta))} ${range === "Max" ? L("insgesamt")
                : range === "7T" ? L("in den letzten 7 Tagen") : L("in den letzten 30 Tagen")}`}
          </div>
        </div>
      </div>
      <div class="ov-chart-block">
        <div class="ov-chart-wrap">
          ${tvLineChart(histSeries, { h: 130 })}
        </div>
      </div>
    </div>
    ${alertBox}
    ${(() => {
      const s = state.settings || {};
      if (s.premium || !s.scans_limit) return "";
      const left = s.scans_limit - (s.scans_used || 0);
      if (left > s.scans_limit * 0.2) return "";
      return `<button class="scan-banner" id="scanBanner">
        <span>${left > 0 ? LF("Noch {0} Scans frei", left) : L("Keine Gratis-Scans mehr")}</span>
        <b>${L("Premium")} ›</b></button>`;
    })()}
    ${setupCard}
    <div id="homeSecs">${renderHomeSections(d, hidden)}</div>
    ${homeBuiltByFooter()}`;

  paintTopTools();
  $("homeScroll").querySelectorAll("[data-item]").forEach((b) => {
    b.onclick = () => openItemDetail(b.dataset.item);
  });
  if (!hidden) countUp($("homeScroll").querySelector(".ov-value"), "dashGrand", grand);
  fadeImgs($("homeScroll"));
  const sc = $("setupCard");
  if (sc) sc.onclick = () => window.open("/onboarding.html", "_blank");
  const sb = $("scanBanner");
  if (sb) sb.onclick = openPaywall;
  $("homeScroll").querySelectorAll(".range-pill").forEach((p) => {
    p.onclick = () => { state.range = p.dataset.r; renderDashboard(); };
  });
  const tva = $("topViewAll");
  if (tva) tva.onclick = () => { state.sort = "valdesc"; switchTab("tabCollection"); };
  const how = $("btnImpactHow");
  if (how) how.onclick = () => openImpactSheet(d.impact || {});
  wireHomeSellHero();
}

function wireHomeSellHero() {
  const one = $("homeScanOne");
  if (one) one.onclick = () => {
    const inp = $("cameraInput");
    try { if (inp) inp.click(); } catch (_) { /* */ }
    try { trackFunnel("scan_mode_selected", { mode: "SELL_SINGLE" }); } catch (_) { /* */ }
  };
  const batch = $("homeScanBatch");
  if (batch) batch.onclick = () => {
    const inp = $("fileInput");
    try { if (inp) { inp.multiple = true; inp.click(); } } catch (_) { /* */ }
    try { trackFunnel("scan_mode_selected", { mode: "SELL_BATCH" }); } catch (_) { /* */ }
  };
  const only = $("homeCollectOnly");
  if (only) only.onclick = () => {
    state.scanIntent = "COLLECT_ONLY";
    const inp = $("cameraInput");
    try { if (inp) inp.click(); } catch (_) { /* */ }
    try { trackFunnel("scan_mode_selected", { mode: "COLLECT_ONLY" }); } catch (_) { /* */ }
  };
  const drafts = $("homeDrafts");
    if (drafts) drafts.onclick = () => {
    state.salesBucket = "draft";
    state.ebayHubFocus = "active";
    switchTab("tabSales");
  };
}

/* ═══════════════════ Sammlung ═══════════════════ */

/* Portfolio-Karte gestalten: Default = Brand-Blau (wie Schriftzüge) */
const HERO_BRAND =
  "linear-gradient(150deg, #1b4483 0%, #102e5a 55%, #0a1d3c 100%)";
const HERO_PRESETS = [
  ["SERO Navy", HERO_BRAND],
  ["Ozean", "linear-gradient(140deg,#0e7490,#164e63 60%,#083344)"],
  ["Wald", "linear-gradient(140deg,#15803d,#14532d 60%,#052e16)"],
  ["Graphit", "linear-gradient(140deg,#374151,#111827 60%,#030712)"],
  ["Gold", "linear-gradient(140deg,#b8860b,#78500a 60%,#3d2a05)"],
];

function heroStyle() {
  const img = storeSafe.getString("sero_hero_img");
  if (img) return `background: linear-gradient(rgba(8,16,34,.45), rgba(8,16,34,.72)), url(${img}) center/cover;`;
  const g = storeSafe.getString("sero_hero_grad");
  // Kein gespeicherter Verlauf → Brand-Default (nicht Rot/Leer)
  return `background: ${g || HERO_BRAND};`;
}

function refreshHeroes() {
  // Sofort neu zeichnen — loadDashboard allein überspringt oft den Render,
  // wenn sich die Portfolio-Zahlen nicht geändert haben.
  if (state.dash) {
    try { renderDashboard(); } catch (_) { /* */ }
  } else {
    loadDashboard({ background: true });
  }
  renderCollection();
}

function openHeroDesigner() {
  openSheet("Karte gestalten", "Wähle Farbe, Verlauf oder ein eigenes Foto als Hintergrund.", `
    <div class="hero-presets">${HERO_PRESETS.map(([n, g], i) => `
      <button class="hp" data-hp="${i}" style="background:${g}"><span>${L(n)}</span></button>`).join("")}
    </div>
    <div class="hp-row">
      <label class="btn-secondary" style="flex:1;margin:0;position:relative">
        ${icon("pencil", 15)}<span>${L("Eigene Farbe")}</span>
        <input id="hpColor" type="color" value="#102e5a" style="opacity:0;width:100%;height:100%;position:absolute;inset:0;cursor:pointer">
      </label>
      <button class="btn-secondary" id="hpPhoto" style="flex:1">${icon("photo", 15)}<span>${L("Eigenes Foto")}</span></button>
    </div>
    <input id="hpFile" type="file" accept="image/*" hidden>
    <button class="btn-plain" id="hpReset" style="width:100%;text-align:center;margin-top:6px">${L("Zurücksetzen")}</button>`, null);
  $("sheetBody").querySelectorAll("[data-hp]").forEach((b2) => {
    b2.onclick = () => {
      const g = HERO_PRESETS[Number(b2.dataset.hp)][1];
      storeSafe.remove("sero_hero_img");
      storeSafe.setString("sero_hero_grad", g);
      closeSheet(); refreshHeroes();
      toast(L("Hintergrund gesetzt"), "check");
    };
  });
  $("hpColor").oninput = (e) => {
    const c = e.target.value;
    storeSafe.remove("sero_hero_img");
    storeSafe.setString("sero_hero_grad",
      `linear-gradient(140deg, ${c} 0%, color-mix(in srgb, ${c} 55%, #000) 70%, color-mix(in srgb, ${c} 30%, #000) 100%)`);
    closeSheet(); refreshHeroes();
    toast(L("Hintergrund gesetzt"), "check");
  };
  $("hpPhoto").onclick = () => $("hpFile").click();
  $("hpFile").onchange = async () => {
    const f = $("hpFile").files[0];
    if (!f) return;
    const img = new Image();
    const blob = URL.createObjectURL(f);
    img.src = blob;
    try {
      await new Promise((ok, err) => { img.onload = ok; img.onerror = err; });
    } finally {
      URL.revokeObjectURL(blob);
    }
    const cv = document.createElement("canvas");
    const scale = Math.min(1, 900 / img.width);
    cv.width = img.width * scale; cv.height = img.height * scale;
    cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
    try {
      storeSafe.setString("sero_hero_img", cv.toDataURL("image/jpeg", 0.78));
      closeSheet(); refreshHeroes();
      toast("Foto gesetzt", "check");
    } catch { toast("Foto zu groß. Wähle ein kleineres Bild."); }
  };
  $("hpReset").onclick = () => {
    storeSafe.remove("sero_hero_img");
    storeSafe.setString("sero_hero_grad", HERO_BRAND);
    closeSheet(); refreshHeroes();
    toast(L("Hintergrund zurückgesetzt"), "check");
  };
}

/* ── Server-Push (Baustein 2): stehende Verbindung, Änderungen erscheinen
   in 1–2 s auf jedem offenen Gerät. Regel: bei (Re-)Connect einmal voll laden,
   danach reichen die Pushes. EventSource reconnectet selbst. */
let syncES = null, syncTimer = null, syncWasDown = false, syncRetry = 1;
function startSync() {
  if (onLoginScreen() || !state.me) return;
  if (syncES || !window.EventSource) return;
  syncES = new EventSource("/api/app/events");
  syncES.onmessage = (e) => {
    let ev = {};
    try { ev = JSON.parse(e.data); } catch { return; }
    clearTimeout(syncTimer);
    syncTimer = setTimeout(() => {
      loadCollection().then(() => {
        /* Sync neu geladener Stücke — Auto-Listen nach Scan entfällt. */
      });
      if (!$("tabHome").hidden) loadDashboard();
      if (!$("tabSales").hidden) loadSales();
      if (state.detail && state.detail.mode === "item" && ev.id === state.detail.id) refreshDetail(true);
    }, 300);
  };
  syncES.onerror = () => {
    syncWasDown = true;
    /* EventSource verbindet nur bei NETZ-Fehlern selbst neu. Antwortet der
       Server mit einem Status (429, 500), geht die Verbindung in CLOSED —
       und blieb dann für die ganze Sitzung tot: kein Live-Sync mehr, ohne
       jedes sichtbare Zeichen. Jetzt: schließen und mit wachsendem Abstand
       neu aufbauen. */
    if (syncES && syncES.readyState === EventSource.CLOSED) {
      syncES.close(); syncES = null;
      syncRetry = Math.min((syncRetry || 1) * 2, 30);
      setTimeout(startSync, syncRetry * 1000);
    }
  };
  syncES.onopen = () => {
    syncRetry = 1;
    if (syncWasDown) {
      syncWasDown = false;
      loadCollection();
      loadDashboard();
      if (!$("tabSales").hidden) loadSales();
    }
  };
}
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    /* Gerät weggelegt: Verbindung sauber schließen. iOS kappt sie sonst still —
       der Server hielt den Slot dann als Zombie, bis 5 Zombies das Konto
       blockierten. */
    if (syncES) { syncES.close(); syncES = null; }
    stopSalesPoll();
    return;
  }
  // Login/Code-Schritt: kein Collection-Reload — sonst 401 → Seiten-Neuladen
  // und der gerade angeforderte Code ist weg.
  if (onLoginScreen() || !state.me) return;
  startSync();
  loadCollection(); if (!$("tabHome").hidden) loadDashboard();
  if (!$("tabSales").hidden) { loadSales(true); startSalesPoll(); }
  pruefeAblage();
});
window.addEventListener("pagehide", () => { if (syncES) { syncES.close(); syncES = null; } });

/* Ablage-Check bei Rückkehr in die App: iOS feuert beim abgebrochenen
   Kamera-Dialog oft GAR KEIN Ereignis — geparkte Fotos blieben dann unsichtbar
   liegen und wanderten beim nächsten Scan kommentarlos ins falsche Stück. */
async function pruefeAblage() {
  if (isGuest()) return;
  if (state.stageOpen || stageUpload._busy) return;
  try {
    const r = await api("/api/app/collection/stage?" + devQ());
    if ((r.photos || []).length && $("sheet").hidden) openStagedSheet(r.photos);
  } catch { /* offline — nächster Versuch beim nächsten Wechsel */ }
}

async function loadCollection() {
  if (isGuest()) {
    applyGuestItems();
    paintGuestSaveBar();
    renderCollection();
    return;
  }
  startSync();
  if (!state._stageChecked) {
    state._stageChecked = true;
    api("/api/app/collection/stage?" + devQ()).then((r) => {
      if ((r.photos || []).length) openStagedSheet(r.photos);
    }).catch(() => {});
  }
  const ticket = colWins.begin();
  let r;
  try {
    r = await api("/api/app/collection", { signal: ticket.signal });
  } catch (e) {
    if (e.superseded) return;
    if (e.status === 401) reloadIfSessionLost();
    if (e.offline && state.items.length) zeigeOfflineBanner();
    return;
  }
  if (!ticket.isCurrent()) return;
  // Große Sammlung? Rest in Blöcken nachziehen, bevor gerendert wird —
  // die Suche und die Statistik-Kacheln sollen IMMER alles sehen.
  while (r.total > r.items.length) {
    if (!ticket.isCurrent()) return;
    let mehr;
    try {
      mehr = await api(`/api/app/collection?offset=${r.items.length}&limit=${r.limit}`, { signal: ticket.signal });
    } catch (e) {
      if (e && e.superseded) return;
      break;
    }
    if (!(mehr.items || []).length) break;
    r.items = r.items.concat(mehr.items);
  }
  if (!ticket.isCurrent()) return;
  const pending = state.pendingDeletes || {};
  const kept = (r.items || []).filter((i) => !pending[i.id]);
  state.items = kept;
  state.stats = r.stats;
  if (state.stats && Object.keys(pending).length) {
    state.stats = Object.assign({}, r.stats, { count: kept.length });
  }
  state.history = r.history || [];
  state.historyByCat = r.history_by_cat || {};
  state.asOfDay = r.as_of_day || null;
  // Signature: Stats+Rev — Draft-Status kann Rev ändern ohne Item-Timestamps
  const sig = [r.rev, state.stats && state.stats.total_value_cents, state.stats && state.stats.total_value,
               kept.length, r.as_of_day].join("|");
  if (state._colSig === sig) return;   // unverändert → kein Neuzeichnen (Plopp-Fix)
  state._colSig = sig;
  state.dryRun = r.dry_run;
  cache.set("col", { items: kept, stats: state.stats, history: r.history,
    history_by_cat: r.history_by_cat, as_of_day: r.as_of_day, ts: Date.now() });
  applyGuestItems();
  paintGuestSaveBar();
  renderCollection();
  paintEbayHub();
  // Frisch gescanntes Stück fertig? Direkt öffnen (roter Faden Scan -> Prüfen -> Verkaufen)
  if (state.watchNew) {
    const fresh = state.items.find((i) => i.id === state.watchNew);
    if (fresh && fresh.status !== "analyzing" && fresh.cutout_status !== "running") {
      const id = state.watchNew;
      state.watchNew = null;
      if (state.scanChoiceShown !== id) showScanResult(fresh);
    }
  }
  clearTimeout(state.colPollTimer);
  if (state.items.some((i) => i.status === "analyzing" || i.status === "waiting"
      || i.cutout_status === "running" || i.design_status === "running")) {
    state.colPollTimer = setTimeout(loadCollection, 2200);
    { const _ts = $("tabScan"); if (_ts && !_ts.hidden) renderScan(); }
  }
  if (!state._designAutoQueued && (r.items || []).length) {
    state._designAutoQueued = true;
    post("/api/app/collection/designs-missing").then((x) => {
      if (x && x.enqueued > 0) loadCollection();
    }).catch(() => { state._designAutoQueued = false; });
  }
}

function filteredItems() {
  const f = state.filter;
  const q = (state.colQuery || "").trim().toLowerCase();
  const cats = invCatsSelected(f);
  // Standardmäßig ist ALLES sichtbar — vorher verschwand ein Stück beim Listen
  // ohne Erklärung aus der Sammlung. Die Chips filtern, sie machen nicht sichtbar.
  let items = state.items.filter((i) =>
    itemMatchesInvCats(i, cats) &&
    itemMatchesSheetFacets(i, f) &&
    (!f.fav || i.favorite) && (!f.wish || i.wishlist) &&
    (!f.dup || i.quantity > 1) &&
    // Verkauftes/Wunsch nur zeigen, wenn der passende Chip aktiv ist —
    // beides gehört nicht mehr (bzw. noch nicht) zum Besitz.
    (f.sold ? (i.sold || i.draft_status === "ended") : !(i.sold || i.draft_status === "ended")) &&
    (f.wish || !i.wishlist) &&
    (!f.listed || i.draft_status === "published") &&
    (!f.draft || (i.draft_id && i.draft_status && !["published", "ended"].includes(i.draft_status))) &&
    (!f.tag || (i.tags || []).includes(f.tag)) &&
    (!q || itemSearchHay(i).includes(q)));
  const by = {
    new: (a, b) => (b.created_at || 0) - (a.created_at || 0),
    valdesc: (a, b) => (b.est_value ?? -1) - (a.est_value ?? -1),
    valasc: (a, b) => (a.est_value ?? Infinity) - (b.est_value ?? Infinity),
    name: (a, b) => (a.name || "").localeCompare(b.name || "", "de"),
    nameza: (a, b) => (b.name || "").localeCompare(a.name || "", "de"),
  };
  const sort = storeSafe.getString("sero_col_sort") || state.sort || "new";
  return items.sort(by[sort] || by.new);
}

/** Stückwert für die große Zahl: Live-eBay → Listingpreis, sonst Marktwert. */
function itemValueForSum(i) {
  const qty = Math.max(1, Number(i.quantity) || 1);
  if (i.draft_status === "published") {
    const lp = i.listing_price != null && i.listing_price !== ""
      ? parseFloat(String(i.listing_price).replace(",", "."))
      : NaN;
    if (isFinite(lp)) return lp * qty;
  }
  if (i.est_value === null || i.est_value === undefined) return 0;
  return Number(i.est_value) * qty;
}

/** Welche Stücke zählen in den Sammlungswert — immer passend zum Filter. */
function itemsForCollectionValue(visible) {
  const f = state.filter;
  // eBay- / Verkauft-Chip: genau das, was die Liste zeigt
  if (f.listed || f.sold) return visible;
  // Sonst Besitz ohne Live-Listings (Portfolio-Regel), ggf. Kategorie/Favorit/Suche
  return visible.filter((i) => i.draft_status !== "published");
}

function sumCollectionValue(items) {
  return items.reduce((sum, i) => sum + itemValueForSum(i), 0);
}

function collectionFiltersActive() {
  const f = state.filter;
  return invCatsSelected(f).length > 0 || invSheetActive(f) || f.listed || f.sold || f.fav || f.draft
    || !!(state.colQuery && state.colQuery.trim());
}

function activeFilterCount() {
  return invFilterBadgeCount(state.filter);
}

function colViewMode() {
  const v = storeSafe.getString("sero_col_view") || "g2";
  if (v === "list") return "list";
  return "g2";
}

function salesViewMode() {
  const v = storeSafe.getString("sero_sales_view") || "list";
  if (v === "g2" || v === "g4") return "g2";
  return "list";
}

/* ── Systemstatus (04.08.) ─────────────────────────────────────────────────
   Klemmt eine Außenquelle, sagt es die App EINMAL oben — statt an jedem
   Stück einzeln einen roten Fehler zu zeigen, dessen gemeinsame Ursache
   niemand sieht. Wartende Stücke laufen von selbst weiter, das steht dabei. */
async function pruefeSystemstatus() {
  try {
    const st = await api("/api/app/systemstatus");
    const el = $("sysBanner");
    if (!el) return;
    if (st.ok && !st.wartende) { el.hidden = true; return; }
    const teile = [];
    if (st.meldung) teile.push(esc(L(st.meldung)));
    if (st.wartende) {
      teile.push(esc(st.wartende === 1
        ? L("1 Stück wartet und läuft automatisch weiter.")
        : LF("{0} Stücke warten und laufen automatisch weiter.", st.wartende)));
    }
    el.innerHTML = `${icon("clock", 15)}<span>${teile.join(" ")}</span>`;
    el.hidden = false;
  } catch { /* Status ist Beiwerk — Fehler hier dürfen nichts blockieren */ }
}

function ensureInvSearchWired() {
  const colInp = $("colSearchLive");
  if (colInp && !colInp._seroInv) {
    colInp._seroInv = true;
    colInp.addEventListener("input", () => {
      state.colQuery = colInp.value || "";
      const clr = $("colSearchClear");
      if (clr) clr.hidden = !String(state.colQuery).trim();
      renderCollection();
    });
  }
  const colClr = $("colSearchClear");
  if (colClr && !colClr._seroInv) {
    colClr._seroInv = true;
    colClr.addEventListener("click", () => {
      state.colQuery = "";
      if (colInp) colInp.value = "";
      colClr.hidden = true;
      renderCollection();
    });
  }
  const salesInp = $("salesSearchLive");
  if (salesInp && !salesInp._seroInv) {
    salesInp._seroInv = true;
    salesInp.addEventListener("input", () => {
      state.salesQuery = salesInp.value || "";
      const clr = $("salesSearchClear");
      if (clr) clr.hidden = !String(state.salesQuery).trim();
      renderSales();
    });
  }
  const salesClr = $("salesSearchClear");
  if (salesClr && !salesClr._seroInv) {
    salesClr._seroInv = true;
    salesClr.addEventListener("click", () => {
      state.salesQuery = "";
      if (salesInp) salesInp.value = "";
      salesClr.hidden = true;
      renderSales();
    });
  }
}

function paintColInvBar(items, hasItems) {
  const bar = $("colInvBar");
  if (!bar) return;
  bar.hidden = !hasItems;
  if (!hasItems) return;
  const wrap = $("colSearchWrap");
  const q = state.colQuery || "";
  if (wrap) wrap.hidden = false;
  const inp = $("colSearchLive");
  if (inp && document.activeElement !== inp && inp.value !== q) inp.value = q;
  const clr = $("colSearchClear");
  if (clr) {
    clr.hidden = !String(q).trim();
    if (!clr.innerHTML) clr.innerHTML = icon("xmark", 14);
  }
  const ic = wrap && wrap.querySelector(".inv-search-ic");
  if (ic && !ic.innerHTML) ic.innerHTML = icon("search", 16);
  const applied = $("colInvApplied");
  if (applied) {
    const html = invAppliedHtml(state.filter, state.colQuery, "colInvApplied");
    applied.hidden = !html;
    applied.innerHTML = html || "";
    applied.querySelectorAll("[data-ak]").forEach((b) => {
      b.onclick = () => {
        invRemoveApplied(state.filter, b.dataset.ak, (v) => {
          state.colQuery = v;
          const i2 = $("colSearchLive");
          if (i2) i2.value = v;
        });
        if (b.dataset.ak === "all" || b.dataset.ak === "q") state.colSearchOpen = !!(state.colQuery && state.colQuery.trim());
        renderCollection();
      };
    });
  }
  const count = $("colInvCount");
  if (count) count.textContent = LF("{0} Stück", items.length);
  let tools = $("colInvTools");
  if (!tools && bar) {
    tools = document.createElement("div");
    tools.id = "colInvTools";
    tools.className = "inv-tools";
    bar.appendChild(tools);
  }
  if (tools) {
    const f = state.filter || {};
    const filterOn = invCatsSelected(f).length > 0 || invSheetActive(f)
      || f.listed || f.sold || f.fav || f.draft;
    const sortCur = storeSafe.getString("sero_col_sort") || state.sort || "new";
    const viewList = colViewMode() === "list";
    tools.innerHTML = `
      <button type="button" class="inv-chip${filterOn ? " on" : ""}" id="btnColFilter">${esc(L("Filtern"))}</button>
      <button type="button" class="inv-chip${sortCur !== "new" ? " on" : ""}" id="btnColSort">${esc(L("Sortieren"))}</button>
      <button type="button" class="inv-chip${viewList ? " on" : ""}" id="btnColView">${esc(L(viewList ? "Liste" : "Kacheln"))}</button>`;
  }
  ensureInvSearchWired();
}

function renderCollection() {
  paintGuestSaveBar();
  const s = state.stats || { count: 0, total_value: 0, categories: [] };
  pruefeSystemstatus();
  const hasItems = state.items.length > 0;
  $("colEmpty").hidden = hasItems;

  // Verkaufs-Chips aus der Sammlung entfernt — alte Filterzustände leeren
  if (state.filter.listed || state.filter.sold) {
    state.filter.listed = false;
    state.filter.sold = false;
  }

  const items = filteredItems();
  const wertItems = itemsForCollectionValue(items);
  const filterAn = collectionFiltersActive();
  let gesamtwert;
  if (filterAn) {
    gesamtwert = sumCollectionValue(wertItems);
  } else if (s.total_value != null && isFinite(Number(s.total_value))) {
    gesamtwert = Number(s.total_value);
  } else {
    gesamtwert = sumCollectionValue(wertItems);
  }
  const view = colViewMode();
  const hiddenVals = storeSafe.getString("sero_hide") === "1";
  const liveVal = (sumVal => sumVal)(gesamtwert);
  const histPts = colChartPoints(wertItems, liveVal, filterAn);
  const littleHist = histPts.length < 3;
  const chartPts = littleHist ? [] : histPts;
  const sumVal = liveVal;
  const sumTxt = hiddenVals ? "••••" : (sumVal != null && isFinite(sumVal) ? money(sumVal) : "—");
  const prevPoly = $("colHubChart") && $("colHubChart").querySelector("polyline");
  const prevPts = prevPoly ? prevPoly.getAttribute("points") : "";
  const sparkHtml = littleHist
    ? `<p class="col-hist-hint">${esc(L("Wert wird ab dem 3. Stück sichtbar"))}</p>`
    : colHubChartMarkup(chartPts);
  const range = state.colRange || "30T";
  const deltaHtml = colHubDeltaFromState();

  $("colHero").innerHTML = !hasItems ? "" : `
    <div id="colEbayHub"></div>
    <div class="col-port compact">
      <div class="col-top">
        <div class="col-top-main">
          <div class="ov-value col-port-val" id="colHubSum">${sumTxt}</div>
          <div class="col-hub-date" id="colHubDate" hidden></div>
          ${deltaHtml}
          <span class="col-count-pill">${esc(LF("{0} Stück", state.items.length))}</span>
        </div>
      </div>
      ${sparkHtml}
      <div class="range-row col-range">
        ${["7T", "30T", "1J"].map((r) =>
          `<button type="button" class="range-pill ${range === r ? "on" : ""}" data-col-r="${r}">${L(r)}</button>`
        ).join("")}
      </div>
    </div>`;
  paintEbayHub();
  if (!littleHist) {
    morphColHubChart(prevPts, $("colHubChart"));
    bindColHubScrub(chartPts, sumVal, hiddenVals);
  }
  paintColInvBar(items, hasItems);

  $("colHero").querySelectorAll("[data-col-r]").forEach((p) => {
    p.onclick = () => { state.colRange = p.dataset.colR; renderCollection(); };
  });
  const viewBtn = $("btnColView");
  if (viewBtn) viewBtn.onclick = () => {
    const next = colViewMode() === "list" ? "g2" : "list";
    storeSafe.setString("sero_col_view", next);
    renderCollection();
  };
  const searchBtn = $("btnColSearch");
  if (searchBtn) searchBtn.onclick = openColSearch;
  const filterBtn = $("btnColFilter");
  if (filterBtn) filterBtn.onclick = openColFilter;
  const sortBtn = $("btnColSort");
  if (sortBtn) sortBtn.onclick = openColSort;

  const grid = $("colGrid");
  grid.className = view === "list" ? "grid col-list"
    : view === "g4" ? "grid col-g4" : "grid";
  const scrollEl = $("colScroll");
  const savedScroll = scrollEl ? scrollEl.scrollTop : 0;
  state._colRenderGen = (state._colRenderGen || 0) + 1;
  const renderGen = state._colRenderGen;
  if (state._colIO) { try { state._colIO.disconnect(); } catch (_) {} state._colIO = null; }
  grid.innerHTML = "";
  if (!grid._seroDelegated) {
    grid._seroDelegated = true;
    grid.addEventListener("click", (e) => {
      const add = e.target.closest(".gitem-add");
      if (add && grid.contains(add)) {
        startScanMode("SELL_SINGLE");
        return;
      }
      const b = e.target.closest(".gitem");
      if (!b || !grid.contains(b) || b.classList.contains("gitem-add")) return;
      const id = b.dataset.id;
      const i = state.items.find((x) => x.id === id);
      if (!i) return;
      if (e.target.closest("[data-more]")) {
        e.preventDefault();
        e.stopPropagation();
        openItemMenu(i);
        return;
      }
      if (b._lp) { b._lp = false; return; }
      openItemDetail(i.id);
    });
    grid.addEventListener("contextmenu", (e) => {
      const b = e.target.closest(".gitem");
      if (!b || !grid.contains(b)) return;
      e.preventDefault();
      b._lp = true;
      const i = state.items.find((x) => x.id === b.dataset.id);
      if (i) openItemMenu(i);
    });
    let lpTimer = null, sx = null, dx = 0, active = null;
    grid.addEventListener("pointerdown", (e) => {
      const b = e.target.closest(".gitem");
      if (!b || !grid.contains(b)) return;
      active = b; sx = e.clientX; dx = 0;
      lpTimer = setTimeout(() => {
        b._lp = true; haptic("light");
        const i = state.items.find((x) => x.id === b.dataset.id);
        if (i) openItemMenu(i);
      }, 450);
    });
    grid.addEventListener("pointermove", (e) => {
      if (!active || sx === null) return;
      dx = e.clientX - sx;
      if (Math.abs(dx) > 10) {
        clearTimeout(lpTimer);
        active.classList.add("dragging");
        active.classList.toggle("rev-fav", dx > 0);
        active.classList.toggle("rev-more", dx < 0);
        const reached = Math.abs(dx) > 80;
        if (reached !== active._reached) {
          active._reached = reached;
          active.classList.toggle("armed", reached);
          if (reached) haptic("soft");
        }
        active.style.transform = `translateX(${Math.max(-120, Math.min(120, dx))}px)`;
      }
    });
    const endPtr = async () => {
      clearTimeout(lpTimer);
      if (!active || sx === null) { active = null; sx = null; return; }
      const b = active, d = dx, id = b.dataset.id;
      active = null; sx = null;
      b.classList.remove("dragging", "rev-fav", "rev-more", "armed");
      b._reached = false; b.style.transform = "";
      if (Math.abs(d) <= 80) return;
      b._lp = true;
      const i = state.items.find((x) => x.id === id);
      if (!i) return;
      if (d < 0) openItemMenu(i);
      else {
        if (needAccountForSave() || isGuestItemId(i.id)) return;
        const war = i.favorite;
        try {
          await post(`/api/app/collection/item/${i.id}`, { favorite: !war });
          loadCollection();
          toast(war ? "Favorit entfernt" : "Als Favorit markiert", "starfill", {
            label: "Rückgängig",
            fn: async () => {
              try { await post(`/api/app/collection/item/${i.id}`, { favorite: war }); loadCollection(); }
              catch (e2) { toast(e2.message); }
            },
          });
        } catch (e) { toast(e.message); }
      }
    };
    for (const ev of ["pointerup", "pointerleave", "pointercancel"]) grid.addEventListener(ev, endPtr);
  }

  const makeCard = (i, gi) => {
    const b = document.createElement("button");
    const isG4 = view === "g4";
    const isList = view === "list";
    b.className = "gitem" + ((i.id === state.watchNew || i.id === state.scanChoiceShown) ? " gitem-fresh" : "");
    b.dataset.id = i.id;
    b.style.setProperty("--i", Math.min(gi, 10));
    b.style.contentVisibility = "auto";
    b.style.containIntrinsicSize = isList ? "56px 72px" : isG4 ? "90px 160px" : "180px 240px";
    const busy = i.status === "analyzing" || i.status === "waiting" || i.cutout_status === "running";
    const badge = i.quantity > 1 ? `<span class="gbadge">×${i.quantity}</span>` : "";
    const liveOn = itemLiveOnEbay(i);
    const stat = i.sold || i.draft_status === "ended" ? ["sold", L("Verkauft")]
      : liveOn ? ["live", L("Aktiv")]
      : i.wishlist ? ["wish", L("Wunsch")]
      : ["draft", L("Entwurf")];
    const statLine = `<span class="gstat ${stat[0]}">${stat[1]}</span>`;
    const fav = i.favorite ? `<span class="gfav">${icon("starfill", 15)}</span>` : "";
    const value = busy
      ? `<span class="ganalyzing"><span class="spinner"></span>${esc(i.status_text || L("Wird analysiert …"))}</span>`
      : i.est_value !== null && i.est_value !== undefined
        ? (() => {
            const unit = Number(i.est_value);
            const qty = Math.max(1, Number(i.quantity) || 1);
            const pos = unit * qty;
            const approx = (i.price_state === "unbekannt") ? "≈ " : "";
            const own = (i.price_state === "eigener_wert" || i.price_source === "manual");
            if (qty > 1) {
              return `<span class="gval">${approx}${money(pos)}`
                + `<span class="gqty">${esc(money(unit))} × ${qty}</span></span>`;
            }
            return `<span class="gval">${own ? "" : approx}${money(unit)}</span>`;
          })()
        : `<span class="gval na">${L("Wert unbekannt")}</span>`;
    const u = (catalogView() && !i.graded && i.card && i.card.image) ? i.card.image
      : (thumb(i.photos[0], 480) || (i.card && i.card.image));
    const seal = gradeSeal(i.graded, i.name, isG4);
    const gradeTxt = seal.text || "";
    const catLab = catUiLabel(i.category);
    const sealInCat = (!isG4 && !isList && gradeTxt)
      ? `<i class="gseal-in ${seal.cls}">${esc(gradeTxt)}</i>` : "";
    const sealUnderName = (isG4 && gradeTxt)
      ? `<span class="gseal-line"><i class="gseal-in ${seal.cls}">${esc(gradeTxt)}</i></span>` : "";
    const tileBg = listingBgCss(i);
    const photoInner = u
      ? `<img class="gph" src="${esc(u)}" loading="lazy" alt="" style="background:${esc(tileBg)}">`
      : `<span class="gph-none">${MONO_PH}</span>`;
    const catChip = catLab
      ? `<span class="gchip-cat">${esc(catLab)}</span>` : "";
    if (isList) {
      const meta = gradeTxt || "";
      b.innerHTML = `
        <span class="gph-box">${photoInner}</span>
        ${badge}${fav}
        <div class="gbody">
          <div class="gname">${esc(i.name)}</div>
          ${catChip}${meta ? `<span class="gcat">${esc(meta)}</span>` : ""}
        </div>
        <div class="gfoot">${value}</div>`;
      return b;
    }
    b.innerHTML = `
      <span class="gph-box">${photoInner}</span>
      ${badge}${fav}${isG4 ? "" : `<span class="gmore" data-more="1">${icon("sliders", 14)}</span>`}
      <div class="gbody">
        <div class="ghead">
          <div class="gname">${esc(i.name)}</div>
          <div class="gfoot">${value}</div>
        </div>
        ${catChip}${sealInCat}
        ${sealUnderName}
        ${statLine}
      </div>`;
    return b;
  };

  const CHUNK = SM.COL_CHUNK || 60;
  let shown = 0;
  const appendChunk = () => {
    if (renderGen !== state._colRenderGen) return;
    const frag = document.createDocumentFragment();
    const end = Math.min(shown + CHUNK, items.length);
    for (; shown < end; shown++) frag.appendChild(makeCard(items[shown], shown));
    grid.appendChild(frag);
    const oldSent = grid.querySelector(".col-sentinel");
    if (oldSent) oldSent.remove();
    if (shown < items.length) {
      const sent = document.createElement("div");
      sent.className = "col-sentinel";
      sent.style.cssText = "grid-column:1/-1;height:1px;";
      sent.setAttribute("aria-hidden", "true");
      grid.appendChild(sent);
      if (typeof IntersectionObserver === "function") {
        const io = new IntersectionObserver((ents) => {
          if (renderGen !== state._colRenderGen) return;
          if (ents.some((en) => en.isIntersecting)) {
            io.disconnect();
            appendChunk();
          }
        }, { root: scrollEl || null, rootMargin: "200px" });
        state._colIO = io;
        io.observe(sent);
      } else {
        const more = document.createElement("button");
        more.className = "btn-secondary";
        more.style.cssText = "grid-column:1/-1;margin:8px 0";
        more.textContent = L("Mehr laden");
        more.onclick = () => { more.remove(); appendChunk(); };
        grid.appendChild(more);
      }
    }
    fadeImgs(grid);
    if (shown >= items.length && view !== "list" && hasItems) {
      const add = document.createElement("button");
      add.type = "button";
      add.className = "gitem gitem-add";
      add.setAttribute("aria-label", L("Fotografieren"));
      add.innerHTML = `<span class="gadd-ic">${icon("camera", 22)}</span><span class="gadd-lab">${esc(L("Fotografieren"))}</span>`;
      add.onclick = () => startScanMode("SELL_SINGLE");
      grid.appendChild(add);
    }
  };
  appendChunk();
  if (scrollEl && savedScroll) {
    requestAnimationFrame(() => { if (scrollEl) scrollEl.scrollTop = savedScroll; });
  }
  if (!items.length && hasItems) {
    const q = (state.colQuery || "").trim();
    const titel = q ? LF("Keine Treffer für „{0}“", q) : "Keine Treffer";
    grid.innerHTML = `<div style="grid-column:1/-1">${emptyState({
      icon: "search", titel,
      text: "Suchbegriff kürzen oder Filter zurücksetzen.",
      sekundar: "Filter zurücksetzen",
      onSekundar: () => {
        invResetSheetFacets(state.filter);
        state.colQuery = "";
        state.colSearchOpen = false;
        const inp = $("colSearchLive");
        if (inp) inp.value = "";
        renderCollection();
      },
    })}</div>`;
  }
  // Angezeigter Wert folgt Filter (Kategorie)
  const valEl = $("colHero") && $("colHero").querySelector(".col-port-val");
  if (valEl) {
    if (storeSafe.getString("sero_hide") === "1") valEl.textContent = "••••";
    else countUp(valEl, "colVal", gesamtwert);
  }
  wireMiniVal("tabCollection", money(gesamtwert));
  fadeImgs($("colGrid"));
}

function openColSort() {
  const cur = storeSafe.getString("sero_col_sort") || state.sort || "new";
  const opts = [
    { label: "Zuletzt hinzugefügt", value: "new" },
    { label: "Wert (höchster zuerst)", value: "valdesc" },
    { label: "Wert (niedrigster zuerst)", value: "valasc" },
    { label: "Name (A–Z)", value: "name" },
    { label: "Name (Z–A)", value: "nameza" },
  ].map((o) => ({ ...o, sel: cur === o.value }));
  openOptions("Sortieren", opts, (v) => {
    state.sort = v;
    storeSafe.setString("sero_col_sort", v);
    renderCollection();
  });
}

function openColFilter() {
  const draft = cloneInvFacets(state.filter);
  const opts = {
    cats: invCatsSelected(state.filter),
    withCats: true,
    withLang: true,
    withRegion: true,
    withYear: true,
    onLiveValue: () => {
      state.filter.valueFrom = draft.valueFrom;
      state.filter.valueTo = draft.valueTo;
      renderCollection();
    },
  };
  openInvFilter("Filter", draft, opts, () => {
    applyInvFacets(state.filter, draft);
    state.filter.cats = (opts.cats || []).slice();
    state.filter.cat = (state.filter.cats && state.filter.cats.length === 1) ? state.filter.cats[0] : "Alle";
    renderCollection();
  }, () => {
    invResetSheetFacets(draft);
    invResetSheetFacets(state.filter);
    opts.cats = [];
    state.filter.cat = "Alle";
    renderCollection();
  });
}

function openColSearch() {
  state.colSearchOpen = !state.colSearchOpen;
  if (!state.colSearchOpen && !(state.colQuery || "").trim()) {
    paintColInvBar(filteredItems(), state.items.length > 0);
    return;
  }
  state.colSearchOpen = true;
  paintColInvBar(filteredItems(), state.items.length > 0);
  const inp = $("colSearchLive");
  setTimeout(() => { try { if (inp) inp.focus(); } catch (_) { /* */ } }, 40);
}

$("emptyAdd").onclick = () => startScanMode("SELL_SINGLE");
{ const eh = document.querySelector("#colEmpty h2"); if (eh) eh.textContent = L("Noch keine Stücke."); }

async function importListings(btn) {
  if (needAccountForSave()) return;
  // Sichtbare Rückmeldung + Doppeltipp-Schutz: der Import dauert bei vielen
  // Listings spürbar, und zwei Tipps starteten ihn bisher doppelt.
  if (importListings._busy) return;
  // Ohne eBay-Konto gibt es nichts zu holen. Vorher meldete der Import dann
  // „Nichts Neues zu importieren“ — richtig gerechnet, aber die falsche
  // Auskunft. Jetzt führt der Tipp zum Verbinden.
  const me = state.me || {};
  if (!me.ebay_connected || me.ebay_needs_reconnect) {
    if (typeof openEbayConnectSheet === "function") {
      openEbayConnectSheet(me);
    } else {
      toast(L("eBay ist nicht verbunden."), "link");
    }
    return;
  }
  importListings._busy = true;
  if (btn) btn.disabled = true;
  toast("Listings werden importiert …", "tray");
  try {
    const r = await post("/api/app/collection/import");
    toast(r.imported ? LF("{0} Listings importiert", r.imported) : "Nichts Neues zu importieren", "tray");
    loadCollection();
  } catch (e) { toast(e.message); }
  finally { importListings._busy = false; if (btn) btn.disabled = false; }
}

/* ═══════════════════ Scanner ═══════════════════ */

const SELL_TPL_DEFAULT = { format: "FIXED_PRICE", auction_days: 7, price_mode: "market", price_value: null, bg: "black" };
const sellTpl = () => ({ ...SELL_TPL_DEFAULT, ...(storeSafe.getJSON("sero_sell_tpl", {}) || {}) });

function renderScanMode() {
  const ht = $("scanHeroText");
  if (ht) {
    ht.textContent = canLiveCam()
      ? L("SERO erkennt dein Produkt und bereitet dein eBay-Angebot vor.")
      : L("Keine Kamera an diesem Gerät.");
  }
  /* Ohne Kamera bleibt der Weg auf dieser Oberfläche: der Hauptknopf heißt dann
     „Aus der Mediathek“ und öffnet die Dateiauswahl. Vorher tippte man auf
     „Artikel fotografieren“ und bekam nur einen Hinweis-Toast. */
  const sn = $("btnScanNow");
  if (sn) {
    const kam = canLiveCam();
    sn.dataset.pick = kam ? "cam" : "lib";
    sn.innerHTML = icon(kam ? "camera" : "photo", 18)
      + "<span>" + esc(L(kam ? "Artikel fotografieren" : "Aus der Mediathek")) + "</span>";
  }
  const gal = $("btnScanGallery");
  if (gal) gal.hidden = !canLiveCam();
  let extra = $("scanExtraActions");
  if (!extra) {
    const hero = document.querySelector(".scan-actions");
    if (hero && !$("scanExtraActions")) {
      extra = document.createElement("div");
      extra.id = "scanExtraActions";
      extra.className = "scan-extra";
      extra.innerHTML = `
        <button type="button" class="scan-chip" id="btnScanBatch">${L("Mehrere Produkte scannen")}</button>
        <button type="button" class="scan-chip" id="btnScanCollectOnly">${L("Nur zur Sammlung hinzufügen")}</button>`;
      hero.parentNode.insertBefore(extra, hero.nextSibling);
      const bb = $("btnScanBatch");
      if (bb) bb.onclick = () => startScanMode("SELL_BATCH");
      const co = $("btnScanCollectOnly");
      if (co) co.onclick = () => startScanMode("COLLECT_ONLY");
    }
  }
  const box = $("sellTplRow");
  if (!box) return;
  const t = sellTpl();
  const fmt = t.format === "AUCTION" ? L("Auktion") : L("Sofortkauf");
  const price = { market: L("Marktwert"), market_minus10: "Markt −10 %",
    auction1: "1 € Start", fixed: L("Festpreis") }[t.price_mode] || L("Marktwert");
  const bg = { white: L("Weiß"), warm: L("Warmweiß"), black: L("Schwarz"),
    logo: L("Mein Logo") }[t.bg] || L("Schwarz");
  box.innerHTML = `<button class="irow tap sell-tpl-stack" id="sellTplBtn">
    <span class="ric" style="background:#3478f6">${icon("gear", 15)}</span>
    <span class="sell-tpl-text">
      <span class="rlabel">${L("Standard für eBay-Entwürfe")}</span>
      <span class="rvalue">${esc(fmt)} · ${esc(price)} · ${esc(bg)}</span>
    </span>
    <span class="chev">${icon("chevron", 15)}</span></button>`;
}
document.addEventListener("click", (e) => {
  if (e.target.closest("#sellTplBtn")) openSellTemplate();
});

function openSellTemplate() {
  const t = sellTpl();
  const opt = (name, val, label, cur) => `<button class="fchip ${cur === val ? "on" : ""}" data-tpl="${name}:${val}">${L(label)}</button>`;
  openSheet("Standard für eBay-Entwürfe", "Gilt für jeden Scan — Format, Preisregel und Hintergrund für den eBay-Entwurf.",
    `<p class="sheet-hint">${L("Format")}</p><div class="chips" id="tplF">${opt("format", "FIXED_PRICE", "Sofortkauf", t.format)}${opt("format", "AUCTION", "Auktion", t.format)}</div>
     <div id="tplDaysRow" ${t.format === "AUCTION" ? "" : "hidden"}><p class="sheet-hint">${L("Laufzeit")}</p><div class="chips">${[3,5,7,10].map((d) => opt("auction_days", d, LF("{0} Tage", d), t.auction_days)).join("")}</div></div>
     <p class="sheet-hint">${L("Preis")}</p><div class="chips">${opt("price_mode", "market", "Marktwert", t.price_mode)}${opt("price_mode", "market_minus10", "Markt −10 %", t.price_mode)}${opt("price_mode", "auction1", "1 € Start", t.price_mode)}${opt("price_mode", "fixed", "Fest:", t.price_mode)}</div>
     <input id="tplPrice" type="text" inputmode="decimal" placeholder="${esc(L("Festpreis in €"))}" value="${t.price_value || ""}" style="margin-top:8px" ${t.price_mode === "fixed" ? "" : "hidden"}>
     <p class="sheet-hint">${L("Listing-Hintergrund (gerendertes Produktbild)")}</p>
     <div class="chips">${opt("bg", "white", "Weiß", t.bg)}${opt("bg", "warm", "Warmweiß", t.bg)}${opt("bg", "black", "Schwarz", t.bg)}${opt("bg", "logo", "Mein Logo", t.bg)}</div>
     <input id="tplLogo" type="file" accept="image/*" style="margin-top:8px" ${t.bg === "logo" ? "" : "hidden"}>`,
    async () => {
      const nt = sellTpl();
      document.querySelectorAll("[data-tpl].on").forEach((b) => {
        const [k, v] = b.dataset.tpl.split(":");
        nt[k] = k === "auction_days" ? parseInt(v) : v;
      });
      nt.price_value = parseFloat(($("tplPrice").value || "").replace(",", ".")) || null;
      storeSafe.setJSON("sero_sell_tpl", nt);
      try {
        if (!isGuest()) {
          const f = $("tplLogo").files[0];
          if (f) { const fd = new FormData(); fd.append("files", f);
            await api("/api/app/settings/render-logo", { method: "POST", body: fd }); nt.bg = "logo"; }
          await post("/api/app/settings/render", { mode: nt.bg });
        }
      } catch (err) { toast(err.message); }
      storeSafe.setJSON("sero_sell_tpl", nt);
      closeSheet(); toast("Standard für eBay-Entwürfe gespeichert", "check");
      renderScanMode();
    }, "Speichern");
  $("sheetBody").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tpl]");
    if (!b) return;
    const k = b.dataset.tpl.split(":")[0];
    $("sheetBody").querySelectorAll(`[data-tpl^='${k}:']`).forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    // Nur Relevantes zeigen: Laufzeit bei Auktion, Festpreis bei Fest, Logo bei Mein Logo
    const v = b.dataset.tpl.split(":")[1];
    if (k === "format") $("tplDaysRow").hidden = v !== "AUCTION";
    if (k === "price_mode") $("tplPrice").hidden = v !== "fixed";
    if (k === "bg") $("tplLogo").hidden = v !== "logo";
  });
}

function ebayConnectedNow() {
  const me = state.me || {};
  return !!(me.ebay_connected && !me.ebay_needs_reconnect);
}

function showEbayNotConnectedHint() {
  openSheet(
    L("eBay ist nicht verbunden"),
    L("Verbinde eBay unter eBay und Verkaufssetup, bevor du einstellst."),
    "",
    () => {
      closeSheet();
      openSeroProfile();
    },
    L("eBay verbinden")
  );
}

async function listNow(id, opts = null) {
  if (needAccountForSave()) return;
  if (isGuestItemId(id)) { openSaveLoginSheet(); return; }
  if (!ebayConnectedNow()) { showEbayNotConnectedHint(); return; }
  const t = { ...sellTpl(), ...(opts || {}) };
  delete t._auto;
  try {
    const r = await post(`/api/app/collection/item/${id}/list`, {
      format: t.format, auction_days: t.auction_days,
      price_mode: t.price_mode, price_value: t.price_value }, { timeout: 20000 });
    const did = r && r.draft_id;
    if (did) {
      toast(r.existing ? L("Zum Verkauf") : L("Listing wird vorbereitet …"), "arrowup");
      await openItemDetail(id, "sell");
    } else {
      toast(L("Listing wird vorbereitet …"), "arrowup");
      await openItemDetail(id, "sell");
    }
  } catch (e) { toast(L("Listen fehlgeschlagen") + " — " + e.message, "xmark"); }
}

/** Verkauf-Tab: Entwurf automatisch anlegen und Felder vorausfüllen. */
/** Nur belegter Marktwert darf ungefragt Listenpreis werden — nie Portfolio/KI/Asking. */
function listingTippFromItem(item) {
  if (!item || item.est_value == null) return null;
  const n = Number(item.est_value);
  if (!(n > 0)) return null;
  if (item.price_source === "estimate" || item.price_source === "manual") return null;
  if (item.price_reason === "KI_RICHTWERT" || item.price_reason === "ROHPREIS_SLAB") return null;
  if (item.price_state === "unbekannt" || item.price_state === "eigener_wert" || item.price_state === "spanne") return null;
  const pc = item.price_class;
  if (pc === "ASKING_ONLY" || pc === "NO_MARKET_DATA" || pc === "GUIDE_VALUE") return null;
  if (item.price_state === "belegt") return n;
  return null;
}

async function ensureItemDraft(item, opts) {
  opts = opts || {};
  if (!item || !item.id) return;
  if (item.draft_id && item.draft_status && item.draft_status !== "error") return;
  if (state.scanIntent === "COLLECT_ONLY") return;
  if (needAccountForSave() || isGuestItemId(item.id)) {
    throw Object.assign(new Error(L("Anmelden zum Speichern")), { status: 401 });
  }
  if (!ebayConnectedNow()) {
    showEbayNotConnectedHint();
    throw Object.assign(new Error(L("eBay ist nicht verbunden")), { status: 409 });
  }
  if (state._ensuringDraft === item.id) return;
  state._ensuringDraft = item.id;
  try {
    const t = sellTpl();
    const tipp = listingTippFromItem(item);
    const body = {
      format: t.format || "FIXED_PRICE",
      auction_days: t.auction_days || 7,
    };
    if (tipp > 0 && (t.price_mode === "market" || t.price_mode === "market_minus10" || !t.price_mode)) {
      body.price_mode = t.price_mode === "market_minus10" ? "market_minus10" : "market";
    } else if (t.price_mode === "fixed" && t.price_value != null) {
      body.price_mode = "fixed";
      body.price_value = t.price_value;
    } else if (t.price_mode === "auction1") {
      body.price_mode = "auction1";
    } else if (tipp > 0) {
      body.price_mode = "market";
    } else if (t.price_mode) {
      body.price_mode = t.price_mode;
      if (t.price_value != null) body.price_value = t.price_value;
    }
    const r = await post(`/api/app/collection/item/${item.id}/list`, body, {
      timeout: opts.timeout || 20000,
    });
    if (r && r.draft_id) item.draft_id = r.draft_id;
    state._listingPrepError = null;
    if (state.detail && state.detail.id === item.id) {
      await refreshDetail(true);
    }
    try { if (typeof loadSales === "function") loadSales(); } catch (_) { /* */ }
    return r;
  } catch (e) {
    try { console.warn("Listing-Vorbereitung", e && e.status, e && e.message); } catch (_) { /* */ }
    throw e;
  } finally {
    if (state._ensuringDraft === item.id) state._ensuringDraft = null;
  }
}

async function startListingPrep(item, btn) {
  if (!item || !item.id) return;
  if (needAccountForSave() || isGuestItemId(item.id)) {
    openSaveLoginSheet();
    return;
  }
  if (state._listingPrepBusy) return;
  if (!ebayConnectedNow()) {
    showEbayNotConnectedHint();
    return;
  }
  state._listingPrepBusy = true;
  state._listingPrepId = item.id;
  state._listingPrepError = null;
  const prev = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span><span>${esc(L("Wird vorbereitet…"))}</span>`;
    try { btn.scrollIntoView({ block: "nearest", inline: "nearest" }); } catch (_) { /* */ }
  }
  try {
    await ensureItemDraft(item, { timeout: 20000 });
  } catch (e) {
    const msg = (e && e.message) || L("Listing-Vorbereitung fehlgeschlagen — erneut versuchen");
    state._listingPrepError = { itemId: item.id, message: msg };
    toast(L("Listing-Vorbereitung fehlgeschlagen — erneut versuchen"), "xmark");
    if (state.detail && state.detail.id === item.id) {
      try { renderDetail(state.detail, { preserve: true, ebayOnly: true }); } catch (_) { /* */ }
    }
  } finally {
    state._listingPrepBusy = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = prev;
    }
  }
}

/** Nach Scan oder aus der Sammlung: Format + Preis, dann direkt zum Listen. */
function openQuickListSheet(item) {
  // Direkt in den Verkauf-Tab — Felder werden dort vorausgefüllt und prüfbar.
  openItemDetail(item.id, "sell");
}

$("btnCamera").onclick = () => {
  openPlusSheet();
};

function openPlusSheet() {
  openSheet("", "", `<div class="plus-sheet-list">
    <button type="button" class="btn-secondary" id="plusPhoto">${icon("camera", 17)}<span>${L("Foto aufnehmen")}</span></button>
    <button type="button" class="btn-secondary" id="plusLibrary">${icon("photo", 17)}<span>${L("Aus Mediathek auswählen")}</span></button>
  </div>`, null);
  $("plusPhoto").onclick = () => { closeSheet(); startScanMode("SELL_SINGLE"); };
  $("plusLibrary").onclick = () => {
    closeSheet();
    const inp = $("libraryInput") || $("fileInput");
    try { if (inp) { inp.multiple = true; inp.click(); } } catch (_) { /* */ }
  };
  const sh = $("sheet");
  if (sh) sh.classList.add("sheet-no-actions");
}

/** Scan-Modus starten — Kamera/Galerie im gleichen Gesture (iOS). */
function startScanMode(mode) {
  state.scanIntent = mode === "COLLECT_ONLY" ? "COLLECT_ONLY" : (mode === "SELL_BATCH" ? null : null);
  if (mode === "COLLECT_ONLY") state.scanIntent = "COLLECT_ONLY";
  try { trackFunnel("scan_mode_selected", { mode }); } catch (_) { /* */ }
  if (mode === "SELL_BATCH") {
    const inp = $("fileInput") || $("libraryInput");
    try { if (inp) { inp.multiple = true; inp.click(); } } catch (_) { /* */ }
    return;
  }
  if (canLiveCam()) {
    openCamCapture($("cameraInput"));
    return;
  }
  const inp = $("libraryInput") || $("fileInput");
  try { if (inp) inp.click(); } catch (_) { /* */ }
}

function canLiveCam() {
  try {
    return !!(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  } catch (_) { return false; }
}

function camShotBlob(shot) {
  return (shot && (shot.edited || shot.original)) || null;
}

function revokeCamShot(shot) {
  if (shot && shot.thumbUrl) {
    try { URL.revokeObjectURL(shot.thumbUrl); } catch (_) { /* */ }
    shot.thumbUrl = null;
  }
}

function clearCamShots() {
  (state.camShots || []).forEach(revokeCamShot);
  if (state.camUndo) revokeCamShot(state.camUndo);
  state.camShots = [];
  state.camUndo = null;
}

function stopLiveCam() {
  state.camLive = false;
  const ov = $("camOverlay");
  if (ov) ov.hidden = true;
  const v = $("camVideo");
  const stream = v && v.srcObject;
  if (stream && stream.getTracks) stream.getTracks().forEach((t) => { try { t.stop(); } catch (_) { /* */ } });
  if (v) v.srcObject = null;
}

function markCamPrimary() {
  (state.camShots || []).forEach((s, i) => {
    s.pos = i;
    s.isPrimary = i === 0;
  });
}

async function prepareScanFile(file) {
  if (!file) return file;
  const name = (file.name || "scan").toLowerCase();
  const type = (file.type || "").toLowerCase();
  const heic = type.includes("heic") || type.includes("heif") || /\.hei[cf]$/.test(name);
  const toJpeg = async (src) => {
    const bmp = await createImageBitmap(src);
    const cv = document.createElement("canvas");
    cv.width = bmp.width;
    cv.height = bmp.height;
    cv.getContext("2d").drawImage(bmp, 0, 0);
    if (bmp.close) bmp.close();
    const blob = await new Promise((r) => cv.toBlob(r, "image/jpeg", 0.92));
    const outName = (file.name || "scan").replace(/\.hei[cf]$/i, ".jpg").replace(/\.[^.]+$/, ".jpg");
    return blob ? new File([blob], outName, { type: "image/jpeg" }) : file;
  };
  try {
    if (heic) return await toJpeg(file);
    if (type.startsWith("image/")) {
      try { return await toJpeg(file); } catch (_) { return file; }
    }
  } catch (_) { /* Server kann HEIC (pillow-heif) */ }
  return file;
}

function camFileSig(file) {
  if (!file) return "";
  return [file.name || "", file.size || 0, file.lastModified || 0].join("|");
}

function camAlreadyHas(file) {
  const sig = camFileSig(file);
  if (!sig || sig === "||0") return false;
  return (state.camShots || []).some((s) => camFileSig(s.original || s.edited) === sig);
}

function liveCamTrack() {
  const v = $("camVideo");
  const stream = v && v.srcObject;
  const tracks = stream && stream.getVideoTracks && stream.getVideoTracks();
  return (tracks && tracks[0]) || null;
}

function paintCamTools() {
  const flip = $("camFlip");
  if (flip) {
    flip.innerHTML = icon("camflip", 20);
    flip.setAttribute("aria-label", L("Kamera wechseln"));
    flip.hidden = false;
  }
  const flash = $("camFlash");
  if (flash) {
    flash.innerHTML = icon("bolt", 18);
    flash.classList.toggle("is-on", !!state.camTorch);
    flash.setAttribute("aria-label", state.camTorch ? L("Blitz an") : L("Blitz aus"));
  }
}

async function applyCamTorch(on) {
  const track = liveCamTrack();
  if (!track || !track.applyConstraints) return false;
  try {
    await track.applyConstraints({ advanced: [{ torch: !!on }] });
    state.camTorch = !!on;
    paintCamTools();
    return true;
  } catch (_) {
    state.camTorch = false;
    paintCamTools();
    return false;
  }
}

function camPermissionMessage(err) {
  const name = (err && err.name) || "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return L("Kamera nicht freigegeben. Mediathek geht trotzdem.");
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return L("Keine Kamera an diesem Gerät.");
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return L("Kamera ist gerade von einer anderen App belegt.");
  }
  return "";
}

async function addCamFiles(files, source) {
  const list = [...(files || [])];
  if (!list.length) return;
  const room = MAX_LISTING_PHOTOS - (state.camShots || []).length;
  if (room <= 0) {
    toast(LF("{0} von {1}", MAX_LISTING_PHOTOS, MAX_LISTING_PHOTOS));
    return;
  }
  let skipped = 0;
  let added = 0;
  for (const raw of list) {
    if (added >= room) break;
    if (source === "library" && camAlreadyHas(raw)) { skipped += 1; continue; }
    const file = await prepareScanFile(raw);
    if (source === "library" && camAlreadyHas(file)) { skipped += 1; continue; }
    const shot = {
      id: "p" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      source: source || "camera",
      original: file,
      edited: null,
      thumbUrl: URL.createObjectURL(file),
      pos: (state.camShots || []).length,
      isPrimary: false,
      upload: { status: "local" },
    };
    state.camShots = (state.camShots || []).concat([shot]);
    added += 1;
  }
  if (skipped && !added) toast(L("Foto ist schon dabei."));
  markCamPrimary();
  if (state.camLive) paintCamOverlay();
  else openCamReview();
}

function paintCamOverlay() {
  const n = (state.camShots || []).length;
  const count = $("camCount");
  if (count) count.textContent = LF("{0} von {1}", n, MAX_LISTING_PHOTOS);
  const strip = $("camStrip");
  if (strip) {
    strip.innerHTML = (state.camShots || []).map((s, i) => `
      <figure class="${i === 0 ? "is-hero" : ""}" data-i="${i}">
        <img src="${esc(s.thumbUrl)}" alt="">
      </figure>`).join("");
    strip.querySelectorAll("figure").forEach((fig) => {
      fig.onclick = () => openCamLightbox(Number(fig.dataset.i));
    });
  }
  const next = $("camNext");
  if (next) next.disabled = n < 1;
}

function wireCamOverlay() {
  const ov = $("camOverlay");
  if (!ov || ov.dataset.wired) return;
  ov.dataset.wired = "1";
  const close = $("camClose");
  if (close) close.onclick = () => { stopLiveCam(); if (!(state.camShots || []).length) clearCamShots(); else openCamSheet(); };
  const lib = $("camLibrary");
  if (lib) {
    lib.textContent = L("Aus Mediathek");
    lib.onclick = () => { const i = $("libraryInput"); if (i) i.click(); };
  }
  const next = $("camNext");
  if (next) {
    next.textContent = L("Weiter");
    next.onclick = () => { stopLiveCam(); openCamReview(); };
  }
  const shut = $("camShutter");
  if (shut) shut.onclick = () => captureLiveFrame();
  const flip = $("camFlip");
  if (flip) flip.onclick = () => flipLiveCam();
  const flash = $("camFlash");
  if (flash) flash.onclick = () => applyCamTorch(!state.camTorch);
}

async function captureLiveFrame() {
  const v = $("camVideo");
  if (!v || !v.videoWidth) return;
  if ((state.camShots || []).length >= MAX_LISTING_PHOTOS) return;
  const cv = $("camCanvas") || document.createElement("canvas");
  cv.width = v.videoWidth;
  cv.height = v.videoHeight;
  cv.getContext("2d").drawImage(v, 0, 0);
  const blob = await new Promise((r) => cv.toBlob(r, "image/jpeg", 0.92));
  if (!blob) return;
  const file = new File([blob], "cam-" + Date.now() + ".jpg", { type: "image/jpeg" });
  await addCamFiles([file], "camera");
}

async function attachLiveStream() {
  const v = $("camVideo");
  if (!v) return false;
  const old = v.srcObject;
  if (old && old.getTracks) old.getTracks().forEach((t) => { try { t.stop(); } catch (_) { /* */ } });
  const facing = state.camFacing === "user" ? "user" : "environment";
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: facing } }, audio: false,
  });
  v.srcObject = stream;
  await v.play().catch(() => {});
  const track = stream.getVideoTracks && stream.getVideoTracks()[0];
  let torchOk = false;
  try {
    const caps = track && track.getCapabilities && track.getCapabilities();
    torchOk = !!(caps && caps.torch);
  } catch (_) { torchOk = false; }
  const flash = $("camFlash");
  if (flash) flash.hidden = !torchOk;
  if (torchOk && state.camTorch) await applyCamTorch(true);
  else state.camTorch = false;
  paintCamTools();
  return true;
}

async function flipLiveCam() {
  if (!state.camLive) return;
  state.camFacing = state.camFacing === "user" ? "environment" : "user";
  state.camTorch = false;
  try {
    await attachLiveStream();
  } catch (err) {
    state.camFacing = state.camFacing === "user" ? "environment" : "user";
    const msg = camPermissionMessage(err);
    if (msg) toast(msg);
  }
}

async function startLiveCam() {
  wireCamOverlay();
  const ov = $("camOverlay");
  const v = $("camVideo");
  if (!ov || !v) return false;
  try {
    await attachLiveStream();
    state.camLive = true;
    ov.hidden = false;
    paintCamOverlay();
    paintCamTools();
    return true;
  } catch (err) {
    const msg = camPermissionMessage(err);
    if (msg) toast(msg);
    return false;
  }
}

/* Rückfallweg, wenn die Live-Kamera nicht geht: Dateiauswahl öffnen.
   Klappt auch die nicht, sagt SERO das — ein Tipp ohne jede Reaktion ist
   schlimmer als eine ehrliche Meldung. */
function camFileFallback(inp) {
  try {
    if (inp) { inp.click(); return true; }
  } catch (_) { /* */ }
  toast(L("Keine Kamera an diesem Gerät."));
  return false;
}

function openCamCapture(inp) {
  state.camLoop = true;
  if (!(state.camShots && state.camShots.length)) state.camShots = state.camShots || [];
  if (canLiveCam()) {
    startLiveCam().then((ok) => {
      if (!ok) camFileFallback(inp);
    });
    return;
  }
  camFileFallback(inp);
}

function openCamSheet() {
  const photos = state.camShots || [];
  const n = photos.length;
  if (!n) return;
  const kacheln = photos.map((s, i) => `
    <figure class="ph-kachel${i === 0 ? " is-hero" : ""}" data-i="${i}" role="button" tabindex="0">
      <img src="${esc(s.thumbUrl)}" alt="" loading="lazy">
      <button type="button" class="ph-weg" data-weg="${i}" aria-label="${esc(L("Foto entfernen"))}">${icon("xmark", 13)}</button>
      ${i === 0 ? `<span class="ph-haupt">${L("Hauptfoto")}</span>` : ""}
      <nav class="ph-sort">
        <button type="button" data-mv="-1" ${i === 0 ? "disabled" : ""} aria-label="${esc(L("nach vorn"))}">‹</button>
        <button type="button" data-mv="1" ${i === n - 1 ? "disabled" : ""} aria-label="${esc(L("nach hinten"))}">›</button>
      </nav>
    </figure>`).join("");
  openSheet(L("Scan prüfen"),
    LF("{0} von {1} Fotos — Tipp wählt das Hauptbild.", n, MAX_LISTING_PHOTOS),
    `<div class="ph-strip">${kacheln}</div>
     <p class="ph-tipp">${esc(L("Tipp auf ein Foto macht es zum Hauptbild."))}</p>
     <div class="ph-add">
       <button type="button" class="btn-secondary" id="stageMoreBtn">${icon("camera", 16)} ${L("Weiteres Foto")}</button>
       <button type="button" class="btn-secondary" id="stageGalBtn">${icon("photo", 16)} ${L("Aus Mediathek")}</button>
       ${state.camUndo ? `<button type="button" class="btn-plain" id="camUndoBtn">${L("Foto entfernen rückgängig")}</button>` : ""}
     </div>`,
    () => { openCamReview(); }, L("Weiter"));
  const weiterCam = () => {
    state.camLoop = true;
    const inp = $("cameraInput");
    if (inp) inp.click();
  };
  const smb = $("stageMoreBtn");
  if (smb) smb.onclick = weiterCam;
  const gal = $("stageGalBtn");
  if (gal) gal.onclick = () => { const i = $("libraryInput"); if (i) i.click(); };
  const undo = $("camUndoBtn");
  if (undo) undo.onclick = () => {
    if (!state.camUndo) return;
    state.camShots.push(state.camUndo);
    state.camUndo = null;
    markCamPrimary();
    openCamSheet();
  };
  $("sheetBody").querySelectorAll("[data-weg]").forEach((b) => {
    b.onclick = (ev) => {
      ev.stopPropagation();
      const i = Number(b.dataset.weg);
      const gone = state.camShots.splice(i, 1)[0];
      if (state.camUndo) revokeCamShot(state.camUndo);
      state.camUndo = gone;
      markCamPrimary();
      if (!state.camShots.length) { closeSheet(); return; }
      openCamSheet();
    };
  });
  $("sheetBody").querySelectorAll("[data-mv]").forEach((b) => {
    b.onclick = (ev) => {
      ev.stopPropagation();
      const kachel = b.closest(".ph-kachel");
      const von = Number(kachel.dataset.i);
      const nach = von + Number(b.dataset.mv);
      if (nach < 0 || nach >= state.camShots.length) return;
      const sortiert = [...state.camShots];
      [sortiert[von], sortiert[nach]] = [sortiert[nach], sortiert[von]];
      state.camShots = sortiert;
      markCamPrimary();
      openCamSheet();
    };
  });
  $("sheetBody").querySelectorAll(".ph-kachel").forEach((fig) => {
    fig.onclick = (ev) => {
      if (ev.target.closest(".ph-weg, .ph-sort")) return;
      openCamLightbox(Number(fig.dataset.i));
    };
  });
}

function openCamLightbox(index) {
  const shots = state.camShots || [];
  const i = Math.max(0, Math.min(index || 0, shots.length - 1));
  const s = shots[i];
  if (!s) return;
  openSheet(i === 0 ? L("Hauptfoto") : L("Foto öffnen"), LF("{0} von {1}", i + 1, shots.length),
    `<div class="cam-lightbox-in"><img src="${esc(s.thumbUrl)}" alt="" style="width:100%;border-radius:12px"></div>
     <div class="quick-row" style="margin-top:12px">
       <button type="button" class="btn-secondary" id="lbCrop">${L("Zuschneiden")}</button>
       <button type="button" class="btn-secondary" id="lbRot">${L("Drehen")}</button>
       <button type="button" class="btn-plain" id="lbDel">${L("Foto entfernen")}</button>
     </div>`,
    () => { closeSheet(); if (state.camLive) paintCamOverlay(); else openCamSheet(); }, L("Zurück"));
  const crop = $("lbCrop");
  if (crop) crop.onclick = () => openCamShotCrop(i);
  const rot = $("lbRot");
  if (rot) rot.onclick = () => openCamShotRotate(i);
  const del = $("lbDel");
  if (del) del.onclick = () => {
    const gone = state.camShots.splice(i, 1)[0];
    if (state.camUndo) revokeCamShot(state.camUndo);
    state.camUndo = gone;
    markCamPrimary();
    closeSheet();
    if (state.camShots.length) openCamSheet();
  };
}

function openCamShotCrop(index) {
  const s = (state.camShots || [])[index];
  if (!s) return;
  const fake = { id: "cam", photos: [s.thumbUrl], _camIndex: index, has_photos_raw: !!s.original };
  openManualCrop(fake, 0);
}

async function applyCamShotBlob(shot, blob) {
  if (!shot || !blob) return;
  revokeCamShot(shot);
  shot.edited = new File([blob], (shot.original && shot.original.name) || "edit.jpg", { type: blob.type || "image/jpeg" });
  shot.thumbUrl = URL.createObjectURL(shot.edited);
}

function openCamShotRotate(index) {
  const s = (state.camShots || [])[index];
  if (!s) return;
  const fake = { id: "cam", photos: [s.thumbUrl], _camIndex: index, has_photos_raw: !!s.original };
  openManualRotate(fake, 0);
}

function openCamReview() {
  const photos = state.camShots || [];
  if (!photos.length) { toast(L("Keine Fotos")); return; }
  const ov = $("scanReview");
  const img = $("scanReviewImg");
  const keep = $("scanReviewKeep");
  const again = $("scanReviewAgain");
  const title = $("scanReviewTitle");
  const lead = $("scanReviewLead");
  if (!ov || !img || !keep || !again) {
    openCamSheet();
    const save = $("sheetSave");
    if (save) {
      save.textContent = L("Als Entwurf behalten");
      save.onclick = () => commitCamShots();
    }
    return;
  }
  stopLiveCam();
  if (title) title.textContent = L("Prüfen.");
  if (lead) lead.textContent = L("Das Foto wird der Entwurf.");
  img.src = photos[0].thumbUrl || "";
  keep.textContent = L("Als Entwurf behalten");
  again.textContent = L("Nochmal fotografieren");
  keep.onclick = () => {
    ov.hidden = true;
    commitCamShots();
  };
  again.onclick = () => {
    ov.hidden = true;
    clearCamShots();
    startScanMode(state.scanIntent === "COLLECT_ONLY" ? "COLLECT_ONLY" : "SELL_SINGLE");
  };
  ov.hidden = false;
}

async function commitCamShots() {
  const shots = state.camShots || [];
  if (!shots.length) return;
  const files = shots.map((s) => camShotBlob(s)).filter(Boolean);
  stopLiveCam();
  state.camLoop = false;
  closeSheet();
  try {
    if (isGuest()) {
      const row = await keepGuestDraftFromFiles(files);
      clearCamShots();
      if (row) {
        switchTab("tabCollection");
        renderCollection();
        if (row.id) openItemDetail(row.id);
      }
      return;
    }
    await stageUpload(files);
    clearCamShots();
  } catch (_) {
    state.camLoop = true;
  }
}

function normalizeItemPhotos(item) {
  if (!item) return [];
  if (Array.isArray(item.photo_model) && item.photo_model.length) {
    return item.photo_model.slice().sort((a, b) => (a.pos || 0) - (b.pos || 0));
  }
  const photos = item.photos || [];
  if (item.image && !photos.length) {
    return [{ id: "legacy", original: item.image, edited: item.image, pos: 0, isPrimary: true }];
  }
  return photos.map((p, i) => ({ id: "p" + i, original: p, edited: p, pos: i, isPrimary: i === 0 }));
}

function openScanModePicker() {
  openSheet(L("Scan-Modus"), L("Ein Artikel, Mehrere Artikel oder nur erfassen."),
    `<div class="scan-mode-list">
      <button type="button" class="btn-secondary" id="smSingle">${icon("camera", 17)}<span>${L("Ein Artikel")}</span></button>
      <button type="button" class="btn-secondary" id="smBatch">${icon("stack", 17)}<span>${L("Mehrere Artikel")}</span></button>
      <button type="button" class="btn-plain" id="smCollect">${icon("tray", 17)}<span>${L("Nur erfassen")}</span></button>
    </div>`, null);
  $("smSingle").onclick = () => { closeSheet(); startScanMode("SELL_SINGLE"); };
  $("smBatch").onclick = () => { closeSheet(); startScanMode("SELL_BATCH"); };
  $("smCollect").onclick = () => { closeSheet(); startScanMode("COLLECT_ONLY"); };
}

/* Long-Press / Context-Menü am Scan-Button — iOS: contextmenu + Touch-Timer */
(function wireCamLongPress() {
  const cam = $("btnCamera");
  if (!cam || cam.dataset.lpWired) return;
  cam.dataset.lpWired = "1";
  let timer = null;
  let longDone = false;
  const clear = () => { if (timer) { clearTimeout(timer); timer = null; } };
  const arm = () => {
    longDone = false;
    clear();
    timer = setTimeout(() => {
      longDone = true;
      try { haptic("medium"); } catch (_) { /* */ }
      openScanModePicker();
    }, 480);
  };
  cam.addEventListener("touchstart", arm, { passive: true });
  cam.addEventListener("touchend", (e) => {
    clear();
    if (longDone) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, { passive: false });
  cam.addEventListener("touchcancel", clear, { passive: true });
  cam.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    openScanModePicker();
  });
  // Pointer: Desktop + moderne Browser
  cam.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "touch") return; // touchstart deckt ab
    if (e.button !== 0) return;
    arm();
  });
  cam.addEventListener("pointerup", clear);
  cam.addEventListener("pointercancel", clear);
  // Kurz-Tipp: onclick bleibt (SELL_SINGLE) — aber nach Long-Press nicht nochmal
  cam.addEventListener("click", (e) => {
    if (longDone) {
      e.preventDefault();
      e.stopImmediatePropagation();
      longDone = false;
    }
  }, true);
})();

document.addEventListener("click", (e) => {
  const now = e.target.closest("#btnScanNow");
  if (now) {
    startScanMode(state.scanIntent === "COLLECT_ONLY" ? "COLLECT_ONLY" : "SELL_SINGLE");
    return;
  }
  if (e.target.closest("#btnScanGallery")) {
    const inp = $("libraryInput") || $("fileInput");
    try { if (inp) inp.click(); } catch (_) { /* */ }
  }
});
for (const inputId of ["fileInput", "cameraInput", "libraryInput"]) {
  /* Abbruch des Kamera-Dialogs: Safari feuert (wenn überhaupt) 'cancel'.
     Wer gerade „Weiteres Foto" wollte, hat noch Fotos in der Ablage —
     die müssen wieder aufs Sheet, sonst liegen sie verwaist herum. */
  const el = $(inputId);
  if (!el) continue;
  el.addEventListener("cancel", () => {
    if (state.camLoop && (state.camShots || []).length) openCamSheet();
    if (state.stageResume) { state.stageResume = false; pruefeAblage(); }
  });
  el.onchange = () => {
    const picked = [...el.files];
    el.value = "";
    if (!picked.length) {
      if (state.camLoop && (state.camShots || []).length) openCamSheet();
      if (state.stageResume) { state.stageResume = false; pruefeAblage(); }
      return;
    }
    if (state.camLoop || inputId === "libraryInput") {
      const src = inputId === "cameraInput" ? "camera" : "library";
      addCamFiles(picked, src);
      return;
    }
    const addingToItem = !!(state.stageOpen || state.stageResume);
    state.stageResume = false;
    if (addingToItem) {
      stageUpload(picked);
      return;
    }
    // Galerie-Mehrfach nur für Stapel (andere Stücke). Kamera bleibt einzeln;
    // weitere Fotos desselben Stücks kommen über das Sammler-Sheet.
    if (picked.length > 1 && inputId === "fileInput") {
      state.addFiles = picked.slice(0, 24);
      openBatchSheet();
      return;
    }
    // Alle Files stagen — Nutzer wählt das Hauptbild, kein stilles Auto-Item.
    stageUpload(picked);
  };
}

async function commitScanFast(files) {
  /* Alle Files in die lokale Session, Nutzer wählt das Hauptbild. Kein Auto-Item,
     kein eBay-Listing. Kamera liefert auf iOS immer ein File — weitere Fotos
     über Capture-Loop / Overlay (Weiteres Foto / Aus Mediathek / Weiter). */
  return addCamFiles(files || [], "camera");
}

function openScanDoneSheet({ itemId, photoUrl }) {
  const ph = photoUrl
    ? `<img class="scan-done-ph" src="${esc(photoUrl)}" alt="">`
    : "";
  openSheet(
    L("Stück in der Sammlung"),
    L("Die Erkennung läuft im Hintergrund."),
    `${ph}<div class="scan-done-acts">
      <button type="button" class="btn-primary" id="scanDoneNext">${L("Weiter scannen")}</button>
      <button type="button" class="btn-secondary" id="scanDoneDraft">${L("Mit dem Entwurf fortsetzen")}</button>
      <button type="button" class="btn-plain" id="scanDoneCol">${L("In der Sammlung anschauen")}</button>
    </div>`,
    { recede: false, fit: true, hideActions: true, scanDone: true });
  const next = $("scanDoneNext");
  if (next) next.onclick = () => {
    closeSheet();
    startScanMode("SELL_SINGLE");
  };
  const draft = $("scanDoneDraft");
  if (draft) draft.onclick = () => {
    closeSheet();
    openItemDetail(itemId);
  };
  const col = $("scanDoneCol");
  if (col) col.onclick = () => {
    closeSheet();
    switchTab("tabCollection");
  };
}

async function stageUpload(files) {
  if (isGuest()) {
    const row = await keepGuestDraftFromFiles(files);
    closeSheet();
    if (row) {
      switchTab("tabCollection");
      renderCollection();
      if (row.id) openItemDetail(row.id);
    }
    return;
  }
  // In-Flight-Sperre: iOS feuert das Kamera-Event gern doppelt — der zweite
  // Schuss darf nicht parallel hochladen (Server-Dedupe ist die zweite Sicherung)
  if (stageUpload._busy) { toast(L("Foto wird schon hochgeladen …")); return; }
  stageUpload._busy = true;
  // Ein ankommendes Foto beendet das Warten auf die Kamera — egal über welchen
  // Weg es hereinkam. Sonst bliebe ein gemerktes Scan-Ergebnis liegen.
  state.stageResume = false;
  // Sofort etwas zeigen: zwischen Tipp und Server-Antwort war bisher NICHTS
  // zu sehen — bei langsamem Netz wirkte die Kamera schlicht kaputt.
  openSheet("Scan prüfen", "", `<div class="stage-line"><span class="spinner"></span> ${L("Foto wird hochgeladen …")}</div>`, null);
  try {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const r = await api("/api/app/collection/stage?" + devQ(), { method: "POST", body: fd });
    state.pendingPhotos = null;
    openStagedSheet(r.photos || []);
  } catch (e) {
    closeSheet();
    if (e.offline) {
      // Das Foto ist NICHT verloren — es liegt im File-Objekt und wird beim
      // nächsten Netz automatisch (oder per Tipp) nachgereicht.
      state.pendingPhotos = files;
      toast(L("Kein Netz — Foto bleibt vorgemerkt, solange die App geöffnet ist"), "camera",
            { label: L("Jetzt senden"), fn: () => {
                const p = state.pendingPhotos; state.pendingPhotos = null;
                stageUpload(p || []);
              } });
    } else toast(e.message);
  }
  finally { stageUpload._busy = false; }
}
window.addEventListener("online", () => {
  if (state.pendingPhotos && !stageUpload._busy) {
    const p = state.pendingPhotos; state.pendingPhotos = null;
    if (p.length) stageUpload(p);
  }
});

function openStagedSheet(photos) {
  /* Foto-Sammler: alle Aufnahmen als Streifen. Tipp auf eine Kachel = Hauptbild.
     Kamera einzeln (iOS), Galerie kann mehrere nachliefern. Kein Auto-Listing. */
  state.stageOrder = photos.map((p) => p.name);
  const n = photos.length;
  const kacheln = photos.map((p, i) => `
    <figure class="ph-kachel${i === 0 ? " is-hero" : ""}" data-name="${esc(p.name)}" data-i="${i}" role="button" tabindex="0" aria-label="${esc(i === 0 ? L("Hauptbild") : L("Als Hauptbild"))}">
      <img src="${esc(url(p.url))}${p.url.includes("?") ? "&" : "?"}w=240" alt="" loading="lazy">
      <button type="button" class="ph-weg" data-weg="${esc(p.name)}" aria-label="${esc(L("Foto entfernen"))}">${icon("xmark", 13)}</button>
      ${i === 0 ? `<span class="ph-haupt">${L("Hauptbild")}</span>` : ""}
      <nav class="ph-sort">
        <button type="button" data-mv="-1" ${i === 0 ? "disabled" : ""} aria-label="${esc(L("nach vorn"))}">‹</button>
        <button type="button" data-mv="1" ${i === n - 1 ? "disabled" : ""} aria-label="${esc(L("nach hinten"))}">›</button>
      </nav>
    </figure>`).join("");

  openSheet(L("Scan prüfen"),
    LF("{0} von {1} Fotos — Tipp wählt das Hauptbild.", n, MAX_LISTING_PHOTOS),
    `<div class="ph-strip">${kacheln}</div>
     <p class="ph-tipp">${esc(L("Tipp auf ein Foto macht es zum Hauptbild."))}</p>
     <div class="ph-add">
       <button type="button" class="btn-secondary" id="stageMoreBtn">${icon("camera", 16)} ${L("Weiteres Foto hinzufügen")}</button>
       <button type="button" class="btn-secondary" id="stageGalBtn">${icon("photo", 16)} ${L("Aus Mediathek")}</button>
     </div>
     <input id="addNotes" type="text" placeholder="${esc(L("Notiz (optional)"))}">`,
    async () => {
      $("sheetSave").disabled = true;
      try {
        const fd = new FormData();
        fd.append("notes", $("addNotes").value.trim());
        fd.append("order", (state.stageOrder || []).join(","));
        let r;
        try {
          r = await api("/api/app/collection/items-from-stage?" + devQ(), { method: "POST", body: fd });
        } catch (e) {
          if (e.offline) state.stageKeep = true;
          throw e;
        }
        state.stageKeep = true;
        state.stageOpen = false;
        state.watchNew = r.item_id;
        state.scanChoiceShown = r.item_id;
        const hero = photos[0];
        const photoUrl = hero && hero.url ? url(hero.url) : "";
        closeSheet();
        switchTab("tabCollection");
        openScanDoneSheet({ itemId: r.item_id, photoUrl: photoUrl });
        loadCollection();
      } catch (e) {
        if (!handleScanError(e)) $("sheetErr").textContent = e.message;
      } finally {
        if ($("sheetSave")) $("sheetSave").disabled = false;
      }
    }, L("Fertig"));

  state.stageOpen = true;

  const weiter = (welcher) => {
    state.stageKeep = true;
    state.stageResume = true; state.stageResumeTs = Date.now();
    // Input synchron im Nutzer-Click öffnen (iOS Transient Activation), Sheet danach
    const inp = $(welcher);
    if (inp) inp.click();
    closeSheet();
  };
  const smb = $("stageMoreBtn");
  if (smb) smb.onclick = () => weiter("cameraInput");
  const gal = $("stageGalBtn");
  if (gal) gal.onclick = () => weiter("fileInput");

  // × entfernt das Foto
  $("sheetBody").querySelectorAll("[data-weg]").forEach((b) => {
    b.onclick = async (ev) => {
      ev.stopPropagation();
      b.disabled = true;
      try {
        const fd = new FormData();
        fd.append("name", b.dataset.weg);
        const r = await api("/api/app/collection/stage/remove?" + devQ(), { method: "POST", body: fd });
        state.stageKeep = true;
        haptic("light");
        if (!(r.photos || []).length) { closeSheet(); return; }
        openStagedSheet(r.photos);
      } catch (e) { b.disabled = false; toast(e.message); }
    };
  });

  // Pfeile sortieren um — nur in der Anzeige, gespeichert wird beim Analysieren
  $("sheetBody").querySelectorAll("[data-mv]").forEach((b) => {
    b.onclick = (ev) => {
      ev.stopPropagation();
      const kachel = b.closest(".ph-kachel");
      const von = Number(kachel.dataset.i);
      const nach = von + Number(b.dataset.mv);
      if (nach < 0 || nach >= photos.length) return;
      const sortiert = [...photos];
      [sortiert[von], sortiert[nach]] = [sortiert[nach], sortiert[von]];
      haptic("soft");
      state.stageKeep = true;
      openStagedSheet(sortiert);
    };
  });

  $("sheetBody").querySelectorAll(".ph-kachel").forEach((fig) => {
    fig.onclick = (ev) => {
      if (ev.target.closest(".ph-weg, .ph-sort")) return;
      const von = Number(fig.dataset.i);
      if (!von) return;
      const sortiert = [...photos];
      const [picked] = sortiert.splice(von, 1);
      sortiert.unshift(picked);
      haptic("soft");
      state.stageKeep = true;
      openStagedSheet(sortiert);
    };
  });
}


function openBatchSheet() {
  const n = state.addFiles.length;
  const thumbs = blobThumbs(state.addFiles);
  openSheet("Stapel-Scan", LF("{0} Fotos — SERO ordnet Vorder- und Rückseiten automatisch zu. Slabs und Hüllen bleiben im Plastik.", n),
    `<div class="add-strip">${thumbs}</div>
     <button class="btn-secondary" id="batchSingle" style="margin-top:10px">${L("Alle Fotos zeigen dasselbe Stück")}</button>`,
    async () => {
      $("sheetSave").disabled = true;
      $("sheetSave").textContent = L("Sortiere Fotos …");
      try {
        if (isGuest()) {
          const row = await keepGuestDraftFromFiles(state.addFiles);
          state.addFiles = [];
          closeSheet();
          if (row) {
            switchTab("tabCollection");
            renderCollection();
            if (row.id) openItemDetail(row.id);
          }
          return;
        }
        const fd = new FormData();
        state.addFiles.forEach((f) => fd.append("files", f));
        const r = await api("/api/app/collection/scan-batch-preview", { method: "POST", body: fd });
        state.addFiles = [];
        state.batchId = r.batch_id;
        state.batchPhotos = r.photos || [];
        state.batchGroups = (r.groups || []).map((g) => g.slice());
        closeSheet();
        openBatchGroupEditor();
      } catch (e) {
        $("sheetErr").textContent = e.message;
      } finally {
        $("sheetSave").disabled = false;
        $("sheetSave").textContent = L("Automatisch sortieren");
      }
    }, "Automatisch sortieren");
  $("batchSingle").onclick = () => { closeSheet(); setTimeout(openAddSheet, 250); };
}

/** Editierbare Batch-Gruppierung: teilen, zusammenführen, Hauptbild (= erstes). */
function openBatchGroupEditor() {
  const photos = state.batchPhotos || [];
  const groups = state.batchGroups || [];
  if (!photos.length || !groups.length) {
    toast(L("Keine Gruppen"));
    return;
  }
  const urlOf = (i) => {
    const p = photos.find((x) => x.i === i) || photos[i];
    return p ? url(p.url) : "";
  };
  const body = groups.map((g, gi) => {
    const kacheln = g.map((pi, j) => `
      <figure class="ph-kachel bg-kachel" data-g="${gi}" data-pi="${pi}">
        <img src="${esc(urlOf(pi))}?w=240" alt="" loading="lazy">
        ${j === 0 ? `<span class="ph-haupt">${L("Hauptbild")}</span>` : ""}
        <nav class="ph-sort">
          <button type="button" data-bg-main="${gi}:${pi}" ${j === 0 ? "disabled" : ""}>${L("Als Hauptbild")}</button>
        </nav>
      </figure>`).join("");
    return `<div class="bg-group" data-gi="${gi}">
      <div class="bg-group-h"><b>${LF("Stück {0}", gi + 1)}</b>
        <span>${LF("{0} Fotos", g.length)}</span></div>
      <div class="ph-strip">${kacheln}</div>
      <div class="bg-group-acts">
        <button type="button" class="btn-plain" data-bg-split="${gi}" ${g.length < 2 ? "disabled" : ""}>${L("Gruppe teilen")}</button>
        <button type="button" class="btn-plain" data-bg-merge="${gi}" ${gi >= groups.length - 1 ? "disabled" : ""}>${L("Mit nächster Gruppe zusammenführen")}</button>
      </div>
    </div>`;
  }).join("");
  openSheet(L("Gruppen prüfen"),
    L("Vorder-/Rückseite prüfen. Erstes Foto je Gruppe ist das Hauptbild."),
    body, async () => {
      $("sheetSave").disabled = true;
      try {
        const r = await post("/api/app/collection/scan-batch-confirm", {
          batch_id: state.batchId,
          groups: state.batchGroups,
          notes: "",
        });
        state.batchId = null;
        state.batchPhotos = null;
        state.batchGroups = null;
        state.scanSession = r.scan_session || null;
        closeSheet();
        switchTab("tabCollection");
        toast(LF("{0} Stücke in der Warteschlange — Analyse läuft.", r.group_count), "sparkle");
        loadScanSession();
        loadSales();
        // Sammlung im Hintergrund aktualisieren — Abschluss ist die Queue, nicht still loadCollection
        loadCollection();
      } catch (e) {
        $("sheetErr").textContent = e.message;
      } finally {
        $("sheetSave").disabled = false;
      }
    }, "Analyse starten");
  $("sheetBody").querySelectorAll("[data-bg-split]").forEach((b) => {
    b.onclick = () => {
      const gi = Number(b.dataset.bgSplit);
      const g = state.batchGroups[gi];
      if (!g || g.length < 2) return;
      const mid = Math.ceil(g.length / 2);
      state.batchGroups.splice(gi, 1, g.slice(0, mid), g.slice(mid));
      openBatchGroupEditor();
    };
  });
  $("sheetBody").querySelectorAll("[data-bg-merge]").forEach((b) => {
    b.onclick = () => {
      const gi = Number(b.dataset.bgMerge);
      if (gi >= state.batchGroups.length - 1) return;
      const a = state.batchGroups[gi];
      const c = state.batchGroups[gi + 1];
      state.batchGroups.splice(gi, 2, a.concat(c));
      openBatchGroupEditor();
    };
  });
  $("sheetBody").querySelectorAll("[data-bg-main]").forEach((b) => {
    b.onclick = () => {
      const [gs, pis] = b.dataset.bgMain.split(":");
      const gi = Number(gs), pi = Number(pis);
      const g = state.batchGroups[gi];
      if (!g) return;
      state.batchGroups[gi] = [pi].concat(g.filter((x) => x !== pi));
      openBatchGroupEditor();
    };
  });
}

async function loadScanSession() {
  try {
    const s = await api("/api/app/scan-session");
    state.scanSession = s;
    renderScanQueue();
    if ((s.items || []).some((x) => x.status === "analyzing")) {
      clearTimeout(loadScanSession._t);
      loadScanSession._t = setTimeout(loadScanSession, 2800);
    }
  } catch (_) { /* offline / unauth */ }
}

function queueStatusLabel(st) {
  return ({
    ready: L("Bereit"),
    needs_review: L("Prüfung nötig"),
    no_price: L("Kein Preis"),
    error: L("Fehler"),
    analyzing: L("Wird analysiert"),
  })[st] || st;
}

function renderScanQueue() {
  let box = $("salesQueue");
  if (!box) {
    const host = $("salesBulk");
    if (!host || !host.parentNode) return;
    box = document.createElement("div");
    box.id = "salesQueue";
    box.className = "sales-queue";
    host.parentNode.insertBefore(box, host);
  }
  const items = (state.scanSession && state.scanSession.items) || [];
  if (!items.length || state.salesBucket !== "draft") {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = `
    <div class="sq-head">
      <b>${L("Scan-Warteschlange")}</b>
      <button type="button" class="btn-plain" id="sqClear">${L("Warteschlange leeren")}</button>
    </div>
    <div class="sq-list">${items.map((it) => `
      <button type="button" class="sq-row" data-item="${esc(it.item_id)}" data-draft="${esc(it.draft_id || "")}">
        ${it.photo ? `<img src="${esc(thumb(it.photo, 120))}" alt="">` : `<span class="mv-ph">${MONO_PH}</span>`}
        <span class="sq-body"><b>${esc(it.title || L("Stück"))}</b>
          <i class="sq-st sq-${esc(it.status)}">${esc(queueStatusLabel(it.status))}</i></span>
        <span class="chev">${icon("chevron", 15)}</span>
      </button>`).join("")}</div>`;
  box.querySelectorAll(".sq-row").forEach((b) => {
    b.onclick = () => {
      if (b.dataset.draft) openDraftDetail(b.dataset.draft);
      else openItemDetail(b.dataset.item);
    };
  });
  const clr = $("sqClear");
  if (clr) clr.onclick = async () => {
    try {
      await post("/api/app/scan-session", { clear: true });
      state.scanSession = { state: "idle", items: [], batch_queue: [] };
      renderScanQueue();
    } catch (e) { toast(e.message); }
  };
}

function openAddSheet() {
  const thumbs = blobThumbs(state.addFiles);
  openSheet("Scan prüfen", "SERO erkennt das Stück und ermittelt den Marktwert.",
    `<div class="add-strip">${thumbs}</div>
     <input id="addNotes" type="text" placeholder="${esc(L("Notiz (optional)"))}">`,
    async () => {
      $("sheetSave").disabled = true;
      try {
        if (isGuest()) {
          const row = await keepGuestDraftFromFiles(state.addFiles, $("addNotes").value.trim());
          state.addFiles = [];
          closeSheet();
          if (row) {
            switchTab("tabCollection");
            renderCollection();
            if (row.id) openItemDetail(row.id);
          }
          return;
        }
        const fd = new FormData();
        state.addFiles.forEach((f) => fd.append("files", f));
        fd.append("notes", $("addNotes").value.trim());
        const r = await api("/api/app/collection/items", { method: "POST", body: fd });
        state.addFiles = [];
        state.watchNew = r.item_id;   // roter Faden: nach der Analyse direkt ins Stück springen
        switchTab("tabCollection");
        loadCollection();
        // Stapel-Scan: direkt die nächste Karte anbieten
        openSheet("Gescannt", "Die Analyse läuft im Hintergrund — du kannst sofort weitermachen.",
          `<button class="btn-primary" id="scanNext">${icon("camera", 18)}<span>${L("Nächstes Stück scannen")}</span></button>
           <button class="btn-secondary" id="scanDone" style="margin-top:10px">${L("Fertig")}</button>`, null);
        $("scanNext").onclick = () => { closeSheet(); $("cameraInput").click(); };
        $("scanDone").onclick = () => closeSheet();
      } catch (e) {
        $("sheetErr").textContent = e.message;
      } finally {
        $("sheetSave").disabled = false;
      }
    }, "Analysieren");

}

/* ── Foto-Vollbild + Menü (Zuschneiden / Drehen / Neues Foto) ── */
function openLightbox(urls, start) {
  if (!urls || !urls.length) return;
  let i = Math.max(0, Math.min(start || 0, urls.length - 1));
  let lb = $("lightbox");
  if (!lb) {
    lb = document.createElement("div");
    lb.id = "lightbox";
    lb.hidden = true;
    lb.innerHTML = `<button type="button" class="lb-close" id="lbClose" aria-label="${esc(L("Schließen"))}">${icon("xmark", 18)}</button>
      <button type="button" class="lb-nav lb-prev" id="lbPrev" aria-label="${esc(L("Zurück"))}">‹</button>
      <img id="lbImg" alt="">
      <button type="button" class="lb-nav lb-next" id="lbNext" aria-label="${esc(L("Weiter"))}">›</button>
      <div class="lb-meta" id="lbMeta"></div>`;
    document.body.appendChild(lb);
  }
  const show = () => {
    $("lbImg").src = urls[i];
    $("lbMeta").textContent = urls.length > 1 ? `${i + 1} / ${urls.length}` : "";
    $("lbPrev").hidden = urls.length < 2;
    $("lbNext").hidden = urls.length < 2;
  };
  show();
  lb.hidden = false;
  document.body.classList.add("lb-open");
  const close = () => {
    lb.hidden = true;
    document.body.classList.remove("lb-open");
    lb.onclick = null;
  };
  $("lbClose").onclick = (e) => { e.stopPropagation(); close(); };
  $("lbPrev").onclick = (e) => { e.stopPropagation(); i = (i - 1 + urls.length) % urls.length; show(); };
  $("lbNext").onclick = (e) => { e.stopPropagation(); i = (i + 1) % urls.length; show(); };
  lb.onclick = (e) => { if (e.target === lb) close(); };
  const img = $("lbImg");
  if (img && !img.dataset.pinch) {
    img.dataset.pinch = "1";
    let scale = 1, base = 1, dist0 = 0;
    img.addEventListener("touchstart", (e) => {
      if (e.touches.length === 2) {
        dist0 = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY,
        );
        base = scale;
      }
    }, { passive: true });
    img.addEventListener("touchmove", (e) => {
      if (e.touches.length === 2 && dist0) {
        const d = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY,
        );
        scale = Math.min(4, Math.max(1, base * d / dist0));
        img.style.transform = `scale(${scale})`;
      }
    }, { passive: true });
    img.addEventListener("touchend", () => {
      if (scale < 1.05) { scale = 1; img.style.transform = ""; }
    });
  } else if (img) {
    img.style.transform = "";
  }
}

function photoIdxNow() {
  const det = state.detail;
  if (det && det.heroImages && det.heroImages.length) return heroSourcePhotoIdx(det);
  if (det && typeof det.photoIdx === "number" && det.photoIdx >= 0) return det.photoIdx;
  const track = document.querySelector(".d-gallery-track") || document.querySelector(".d-photos");
  if (!track) return 0;
  const n = track.querySelectorAll("img").length;
  if (n < 2) return 0;
  const max = Math.max(1, track.scrollWidth - track.clientWidth);
  return Math.round(track.scrollLeft / max * (n - 1));
}

function bestOfferOn(d) {
  const bo = d && d.best_offer;
  return !!(bo && (bo === true || bo.enabled));
}

function bestOfferMin(d) {
  const bo = d && d.best_offer;
  if (!bo || bo.min_price == null || bo.min_price === "") return "";
  return String(bo.min_price).replace(".", ",");
}

function resolveDraftPhotoItem(d) {
  const itemId = d.collection_item_id
    || (state.detail && state.detail.mode === "item" && state.detail.id);
  if (!itemId) return null;
  if (state.detail && state.detail.mode === "item" && state.detail.data
      && state.detail.data.id === itemId) {
    return state.detail.data;
  }
  const fromList = (state.items || []).find((x) => x.id === itemId);
  if (fromList) return fromList;
  /* Entwurfs-URLs (/api/app/photo/…) reichen für Zuschnitt nicht — Bearbeitung
     läuft immer über das verknüpfte Sammlungsstück (/api/app/citem-photo/…). */
  const n = Math.max((d.photos || []).length, 1);
  return {
    id: itemId,
    photos: Array.from({ length: n }, (_, i) => `/api/app/citem-photo/${itemId}/${i}`),
    has_photos_raw: !!d.has_photos_raw,
    listing_bg: d.listing_bg || DEFAULT_LISTING_BG,
  };
}

function draftPhotoItemHasLocal(item, d) {
  if (!item) return false;
  if ((item.photos || []).some((u) => String(u).startsWith("/api/app/citem-photo"))) return true;
  return !!(d && d.collection_item_id);
}

function draftPhotoStatus(p) {
  if (!p || !p.has_render) return L("Original (kein Freisteller)");
  return p.is_original ? L("Original aktiv") : L("Freisteller aktiv");
}

async function openDraftPhotoMenu(d, index) {
  if (!d) return;
  let item = resolveDraftPhotoItem(d);
  const idx = Math.max(0, Math.min(index || 0, (d.photos || []).length - 1));
  const p = (d.photos || [])[idx] || {};
  if (!item) {
    toast(L("Kein Sammlungsstück verknüpft"));
    openImageSheet(d, idx);
    return;
  }
  if (d.collection_item_id && !draftPhotoItemHasLocal(item, d)) {
    try {
      const full = await api(`/api/app/collection/item/${d.collection_item_id}`);
      if (full && full.id) {
        item = full;
        const ix = (state.items || []).findIndex((x) => x.id === full.id);
        if (ix >= 0) state.items[ix] = full;
        else if (Array.isArray(state.items)) state.items.push(full);
      }
    } catch (_) { /* synthetischer Stub reicht für citem-photo-Pfade */ }
  }
  if (state.detail) state.detail.photoIdx = idx;
  const hasLocal = draftPhotoItemHasLocal(item, d);
  const hasRaw = !!(item.has_photos_raw || d.has_photos_raw);
  const canTog = !!p.has_render;
  const togLabel = !canTog
    ? LF("Bild {0} — Original (kein Freisteller)", idx + 1)
    : p.is_original
      ? LF("Bild {0} — Original → Freisteller", idx + 1)
      : LF("Bild {0} — Freisteller → Original", idx + 1);
  openSheet(L("Fotos"), draftPhotoStatus(p), `
    <div class="opt-list">
      <button class="opt" id="optDraftImgTog" ${canTog ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("scanframe", 17)} ${esc(togLabel)}</span></button>
      <button class="opt" id="optPhotoCrop" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("crop", 17)} ${L("Zuschneiden")}</span></button>
      <button class="opt" id="optPhotoRotate" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("refresh", 17)} ${L("Drehen")}</span></button>
      <button class="opt" id="optPhotoBg" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("swatch", 17)} ${L("Hintergrund")}</span></button>
      <button class="opt" id="optPhotoRestore" ${hasLocal && hasRaw ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("tray", 17)} ${L("Original wiederherstellen")}</span></button>
      <button class="opt" id="optPhotoFreistellen" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("scanframe", 17)} ${L("Freistellen")}</span></button>
      <button class="opt" id="optPhotoNew"><span style="display:flex;align-items:center;gap:10px">${icon("camera", 17)} ${L("Neues Foto")}</span></button>
      <button class="opt" id="optDraftImgOrder"><span style="display:flex;align-items:center;gap:10px">${icon("photo", 17)} ${L("Reihenfolge & Hauptbild")}</span></button>
    </div>`, null);
  const tog = $("optDraftImgTog");
  if (tog) tog.onclick = async () => {
    try {
      await doAction(d.id, "imgtog", String(idx));
      closeSheet();
      refreshDetail(true);
    } catch (e) { toast(e.message); }
  };
  const crop = $("optPhotoCrop");
  if (crop) crop.onclick = () => openManualCrop(item, idx);
  const rot = $("optPhotoRotate");
  if (rot) rot.onclick = () => openManualRotate(item, idx);
  const bg = $("optPhotoBg");
  if (bg) bg.onclick = () => openListingBgPicker(item);
  const rest = $("optPhotoRestore");
  if (rest) rest.onclick = () => { closeSheet(); restoreItemPhoto(item.id, idx); };
  const frei = $("optPhotoFreistellen");
  if (frei) frei.onclick = () => { freistellenItemPhoto(item.id); };
  const neu = $("optPhotoNew");
  if (neu) neu.onclick = () => { closeSheet(); pickItemPhoto(item.id); };
  const ord = $("optDraftImgOrder");
  if (ord) ord.onclick = () => { closeSheet(); openImageSheet(d, idx); };
}

function openItemPhotoMenu(item) {
  if (!item) return;
  const hasLocal = (item.photos || []).some((p) => String(p).startsWith("/api/app/citem-photo"))
    || !!(item.id && (item.photos || []).length);
  const hasRaw = !!item.has_photos_raw;
  openSheet(L("Fotos"), "", `
    <div class="opt-list">
      <button class="opt" id="optPhotoCrop" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("crop", 17)} ${L("Zuschneiden")}</span></button>
      <button class="opt" id="optPhotoRotate" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("refresh", 17)} ${L("Drehen")}</span></button>
      <button class="opt" id="optPhotoBg" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("swatch", 17)} ${L("Hintergrund")}</span></button>
      <button class="opt" id="optPhotoRestore" ${hasLocal && hasRaw ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("tray", 17)} ${L("Original wiederherstellen")}</span></button>
      <button class="opt" id="optPhotoFreistellen" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("scanframe", 17)} ${L("Freistellen")}</span></button>
      <button class="opt" id="optPhotoNew"><span style="display:flex;align-items:center;gap:10px">${icon("camera", 17)} ${L("Neues Foto")}</span></button>
    </div>`, null);
  const idx = () => photoIdxNow();
  // Direkt openSheet im Editor — closeSheet davor ließ das zweite Öffnen oft hängen
  // (Schließ-Timer vs. neues Sheet).
  const crop = $("optPhotoCrop");
  if (crop) crop.onclick = () => openManualCrop(item, idx());
  const rot = $("optPhotoRotate");
  if (rot) rot.onclick = () => openManualRotate(item, idx());
  const bg = $("optPhotoBg");
  if (bg) bg.onclick = () => openListingBgPicker(item);
  const rest = $("optPhotoRestore");
  if (rest) rest.onclick = () => { closeSheet(); restoreItemPhoto(item.id, idx()); };
  const frei = $("optPhotoFreistellen");
  if (frei) frei.onclick = () => { freistellenItemPhoto(item.id); };
  const neu = $("optPhotoNew");
  if (neu) neu.onclick = () => { closeSheet(); pickItemPhoto(item.id); };
}

/** Whitelist — muss zu web/listing_bg.py passen. */
const DEFAULT_LISTING_BG = "#0B0B0D"; // Hintergrund 3 (Schwarz)
const LISTING_BG_SWATCHES = [
  { hex: "#FFFFFF", label: "Reinweiß" },
  { hex: "#F5F9FF", label: "Kaltweiß" },
  { hex: "#F7F4EF", label: "Off-White" },
  { hex: "#F5EFE3", label: "Warmweiß" },
  { hex: "#0B0B0D", label: "Schwarz" },
  { hex: "#2A2E35", label: "Anthrazit" },
  { hex: "#3D4450", label: "Graphit" },
  { hex: "#E4ECF6", label: "Eisblau" },
  { hex: "#D6E6F8", label: "Hellblau" },
  { hex: "#C5D4EA", label: "Navy-Hell" },
];

function listingBgCss(item) {
  const h = item && item.listing_bg;
  if (h && /^#[0-9A-Fa-f]{6}$/.test(h)) return h;
  return DEFAULT_LISTING_BG;
}

function openListingBgPicker(item) {
  if (!item) return;
  const cur = ((item.listing_bg || DEFAULT_LISTING_BG) + "").toUpperCase();
  const photo = (item.photos || []).find((p) => String(p).startsWith("/api/app/citem-photo"));
  const preview = photo
    ? `<div class="bg-pick-preview" style="background:${esc(cur)}"><img src="${esc(thumb(photo, 720))}" alt=""></div>`
    : "";
  const swatches = LISTING_BG_SWATCHES.map((s) => {
    const on = cur === s.hex ? " on" : "";
    const dark = ["#0B0B0D", "#2A2E35", "#3D4450"].includes(s.hex) ? " dark" : "";
    return `<button type="button" class="bg-swatch${on}${dark}" data-bg="${s.hex}" aria-label="${esc(L(s.label))}" title="${esc(L(s.label))}" style="background:${s.hex}"></button>`;
  }).join("");
  openSheet(L("Hintergrund für eBay"), L("Standard ist Schwarz — tipp eine andere Farbe, wenn du willst."), `
    ${preview}
    <div class="bg-swatch-grid">${swatches}
      <button type="button" class="bg-swatch bg-swatch-default" data-bg="" aria-label="${esc(L("Standard"))}" title="${esc(L("Standard"))}">↺</button>
    </div>`, null);
  const prev = document.querySelector(".bg-pick-preview");
  document.querySelectorAll(".bg-swatch").forEach((btn) => {
    btn.onclick = async () => {
      const hex = btn.dataset.bg || "";
      try {
        const updated = await post(`/api/app/collection/item/${item.id}`, { listing_bg: hex });
        const it = (state.items || []).find((x) => x.id === item.id);
        const next = updated.listing_bg || DEFAULT_LISTING_BG;
        if (it) it.listing_bg = next;
        item.listing_bg = next;
        if (state.detail && state.detail.id === item.id) state.detail.listing_bg = next;
        const active = (hex || DEFAULT_LISTING_BG).toUpperCase();
        document.querySelectorAll(".bg-swatch").forEach((b) => {
          if (!b.dataset.bg) b.classList.toggle("on", !hex);
          else b.classList.toggle("on", b.dataset.bg.toUpperCase() === active);
        });
        if (prev) prev.style.background = next;
        applyListingBgPreview(item);
        toast(L("Hintergrund gespeichert"), "check");
      } catch (e) { toast(e.message); }
    };
  });
}

function applyListingBgPreview(item) {
  if (!item) return;
  const bg = listingBgCss(item);
  document.querySelectorAll("#detailBody .d-photos img, #detailBody .d-photos .holo-wrap").forEach((el) => {
    el.style.background = bg;
  });
  const gal = $("detailGallery");
  if (gal) gal.style.setProperty("--listing-bg", bg);
  document.querySelectorAll("#detailBody .d-gal-slide").forEach((el) => {
    el.style.background = bg;
  });
  const g = document.querySelector(`.gitem[data-id="${item.id}"] .gph, .gitem[data-id="${item.id}"] img`);
  if (g) g.style.background = bg;
}

function pickItemPhoto(itemId) {
  let inp = $("itemPhotoInput");
  if (!inp) {
    inp = document.createElement("input");
    inp.id = "itemPhotoInput";
    inp.type = "file";
    inp.accept = "image/*";
    inp.multiple = true;
    inp.hidden = true;
    document.body.appendChild(inp);
  }
  inp.onchange = async () => {
    const picked = [...inp.files];
    inp.value = "";
    if (!picked.length) return;
    toast(L("Foto wird hochgeladen …"), "camera");
    try {
      const fd = new FormData();
      picked.slice(0, 8).forEach((f) => fd.append("files", f));
      // Anhängen, nicht alles ersetzen (Claude-Review B4)
      fd.append("replace", "0");
      await api(`/api/app/collection/item/${itemId}/photos`, { method: "POST", body: fd });
      toast(L("Foto gespeichert"), "check");
      const it = (state.items || []).find((x) => x.id === itemId);
      if (it && it.draft_id) {
        toast(L("Fotos sind im Listing-Entwurf aktualisiert"), "check");
      }
      refreshDetail(true);
      loadCollection();
    } catch (e) { toast(e.message); }
  };
  inp.click();
}

async function freistellenItemPhoto(itemId) {
  const line = $("cutoutChrome");
  if (line) line.textContent = L("Freistellen…");
  try {
    await post(`/api/app/collection/item/${itemId}/recrop`, {}, { timeout: 45000 });
    toast(L("Freistellen fertig"), "check");
    refreshDetail(true);
    loadCollection();
  } catch (e) {
    const msg = (e && e.message) || L("Freistellen fehlgeschlagen — Original bleibt.");
    try { console.warn("Freistellen", e && e.status, msg); } catch (_) { /* */ }
    if (line) {
      line.innerHTML = `${esc(msg)} <button type="button" class="btn-plain" id="btnCutoutRetry">${esc(L("Nochmal freistellen"))}</button>`;
      const b = $("btnCutoutRetry");
      if (b) b.onclick = () => freistellenItemPhoto(itemId);
    } else {
      toast(msg);
    }
  }
}

async function restoreItemPhoto(itemId, index) {
  toast(L("Original wird wiederhergestellt …"), "tray");
  try {
    await post(`/api/app/collection/item/${itemId}/photo-restore`, { index: index || 0 });
    toast(L("Original wiederhergestellt"), "check");
    refreshDetail(true);
    loadCollection();
  } catch (e) { toast(e.message); }
}

function loadPhotoImage(url) {
  return new Promise((ok, err) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => ok(img);
    img.onerror = err;
    img.src = url;
  });
}

/** Canvas → Blob ohne schwarze Polster: JPEG bei deckend, sonst PNG (Alpha bleibt). */
function canvasToPhotoBlob(cv) {
  return new Promise((res) => {
    try {
      const ctx = cv.getContext("2d");
      const { data } = ctx.getImageData(0, 0, Math.min(cv.width, 8), Math.min(cv.height, 8));
      let alpha = false;
      for (let i = 3; i < data.length; i += 4) if (data[i] < 250) { alpha = true; break; }
      if (alpha) cv.toBlob(res, "image/png");
      else cv.toBlob(res, "image/jpeg", 0.92);
    } catch {
      cv.toBlob(res, "image/jpeg", 0.92);
    }
  });
}

/**
 * Rotation „cover“ im Originalrahmen: keine leeren/schwarzen Ecken —
 * Bild dreht und skaliert so, dass der Rahmen voll mit Bildinhalt gefüllt bleibt.
 */
function rotateImageCover(img, deg) {
  const w = img.naturalWidth, h = img.naturalHeight;
  const rad = (deg * Math.PI) / 180;
  const cos = Math.abs(Math.cos(rad)), sin = Math.abs(Math.sin(rad));
  const bw = w * cos + h * sin;
  const bh = w * sin + h * cos;
  const scale = Math.max(w / bw, h / bh);
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = h;
  const ctx = cv.getContext("2d");
  // Kein clear/fill → kein Schwarz; Cover füllt den Rahmen vollständig
  ctx.translate(w / 2, h / 2);
  ctx.rotate(rad);
  ctx.scale(scale, scale);
  ctx.drawImage(img, -w / 2, -h / 2);
  return cv;
}

async function uploadEditedPhoto(itemId, index, blob, item) {
  if (itemId === "cam") {
    const i = (item && Number.isFinite(item._camIndex)) ? item._camIndex : index;
    const s = (state.camShots || [])[i];
    await applyCamShotBlob(s, blob);
    return { cam: true };
  }
  const fd = new FormData();
  const name = (blob.type || "").includes("png") ? "edit.png" : "edit.jpg";
  fd.append("file", blob, name);
  fd.append("index", String(index || 0));
  fd.append("keep_raw", "1");
  await api(`/api/app/collection/item/${itemId}/photo-replace`, { method: "POST", body: fd });
}

/** Manuelles Zuschneiden: Rechteck ziehen, bestätigen — kein AI-Recrop. */
function openManualCrop(item, index) {
  const urls = item.photos || [];
  const idx = Math.max(0, Math.min(index || 0, urls.length - 1));
  const src = thumb(urls[idx], 1600);
  openSheet(L("Zuschneiden"), L("Zieh die Ecken oder den Rahmen. Mit Übernehmen speicherst du den Ausschnitt."), `
    <div class="edit-stage" id="cropStage">
      <img id="cropImg" alt="" draggable="false">
      <div class="crop-box" id="cropBox">
        <i class="ch nw" data-h="nw"></i><i class="ch ne" data-h="ne"></i>
        <i class="ch sw" data-h="sw"></i><i class="ch se" data-h="se"></i>
      </div>
    </div>`, async () => {
    try {
      $("sheetSave").disabled = true;
      const img = $("cropImg");
      const box = $("cropBox");
      const stage = $("cropStage");
      const natW = img.naturalWidth, natH = img.naturalHeight;
      const dispW = img.clientWidth, dispH = img.clientHeight;
      const sx = (box.offsetLeft - img.offsetLeft) / dispW * natW;
      const sy = (box.offsetTop - img.offsetTop) / dispH * natH;
      const sw = box.offsetWidth / dispW * natW;
      const sh = box.offsetHeight / dispH * natH;
      const cv = document.createElement("canvas");
      cv.width = Math.max(1, Math.round(sw));
      cv.height = Math.max(1, Math.round(sh));
      cv.getContext("2d").drawImage(img, sx, sy, sw, sh, 0, 0, cv.width, cv.height);
      const blob = await canvasToPhotoBlob(cv);
      if (!blob) throw new Error(L("Zuschneiden fehlgeschlagen"));
      toast(L("Zuschneiden wird gespeichert …"), "crop");
      const camEdit = await uploadEditedPhoto(item.id, idx, blob, item);
      closeSheet();
      toast(L("Zuschneiden fertig"), "check");
      if (camEdit && camEdit.cam) { if (state.camLive) paintCamOverlay(); else openCamSheet(); return; }
      refreshDetail(true);
      loadCollection();
    } catch (e) {
      $("sheetErr").textContent = e.message;
    } finally {
      $("sheetSave").disabled = false;
    }
  }, L("Übernehmen"));

  const img = $("cropImg");
  const box = $("cropBox");
  const stage = $("cropStage");
  img.src = src;
  img.onload = () => {
    const pad = 0.08;
    const w = img.clientWidth, h = img.clientHeight;
    box.style.left = `${img.offsetLeft + w * pad}px`;
    box.style.top = `${img.offsetTop + h * pad}px`;
    box.style.width = `${w * (1 - 2 * pad)}px`;
    box.style.height = `${h * (1 - 2 * pad)}px`;
  };

  let mode = null, startX = 0, startY = 0, startRect = null;
  const clampBox = () => {
    const min = 40;
    let l = box.offsetLeft, t = box.offsetTop, w = box.offsetWidth, h = box.offsetHeight;
    const il = img.offsetLeft, it = img.offsetTop, iw = img.clientWidth, ih = img.clientHeight;
    w = Math.max(min, Math.min(w, iw));
    h = Math.max(min, Math.min(h, ih));
    l = Math.max(il, Math.min(l, il + iw - w));
    t = Math.max(it, Math.min(t, it + ih - h));
    box.style.left = `${l}px`; box.style.top = `${t}px`;
    box.style.width = `${w}px`; box.style.height = `${h}px`;
  };
  const onMove = (e) => {
    if (!mode) return;
    const pt = e.touches ? e.touches[0] : e;
    const dx = pt.clientX - startX, dy = pt.clientY - startY;
    let { l, t, w, h } = startRect;
    if (mode === "move") { l += dx; t += dy; }
    else {
      if (mode.includes("e")) w = startRect.w + dx;
      if (mode.includes("s")) h = startRect.h + dy;
      if (mode.includes("w")) { l = startRect.l + dx; w = startRect.w - dx; }
      if (mode.includes("n")) { t = startRect.t + dy; h = startRect.h - dy; }
    }
    box.style.left = `${l}px`; box.style.top = `${t}px`;
    box.style.width = `${w}px`; box.style.height = `${h}px`;
    clampBox();
    e.preventDefault();
  };
  const onUp = () => { mode = null; };
  const begin = (e, m) => {
    const pt = e.touches ? e.touches[0] : e;
    mode = m; startX = pt.clientX; startY = pt.clientY;
    startRect = { l: box.offsetLeft, t: box.offsetTop, w: box.offsetWidth, h: box.offsetHeight };
    e.preventDefault(); e.stopPropagation();
  };
  box.addEventListener("pointerdown", (e) => {
    if (e.target.dataset.h) begin(e, e.target.dataset.h);
    else begin(e, "move");
  });
  stage.addEventListener("pointermove", onMove);
  stage.addEventListener("pointerup", onUp);
  stage.addEventListener("pointercancel", onUp);
  stage.addEventListener("pointerleave", onUp);
}

/** Freie Rotation −180…+180° (0 in der Mitte), Vorschau lokal, Speichern erst bei Übernehmen. */
function openManualRotate(item, index) {
  const urls = item.photos || [];
  const idx = Math.max(0, Math.min(index || 0, urls.length - 1));
  const src = thumb(urls[idx], 1600);
  const hasRaw = !!item.has_photos_raw;
  openSheet(L("Drehen"), L("Dreh frei mit dem Regler. Null liegt in der Mitte. Speichern erst mit Übernehmen."), `
    <div class="edit-stage rot-stage">
      <img id="rotImg" alt="" draggable="false">
    </div>
    <div class="rot-controls">
      <label class="rot-lab"><span id="rotDegLabel">0°</span>
        <input id="rotRange" type="range" min="-180" max="180" step="1" value="0">
      </label>
      ${hasRaw ? `<button type="button" class="btn-secondary" id="rotRestore" style="width:100%;margin-top:10px">${L("Original wiederherstellen")}</button>` : ""}
    </div>`, async () => {
    try {
      $("sheetSave").disabled = true;
      const deg = Number($("rotRange").value) || 0;
      if (Math.abs(deg) < 0.5) { closeSheet(); return; }
      toast(L("Foto wird gedreht …"), "refresh");
      // Cover im Originalrahmen — keine schwarzen Ecken (kein expand + JPEG-Fill)
      const img = await loadPhotoImage(src);
      const cv = rotateImageCover(img, deg);
      const blob = await canvasToPhotoBlob(cv);
      if (!blob) throw new Error(L("Drehen fehlgeschlagen"));
      const camEdit = await uploadEditedPhoto(item.id, idx, blob, item);
      closeSheet();
      toast(L("Foto gedreht"), "check");
      if (camEdit && camEdit.cam) { if (state.camLive) paintCamOverlay(); else openCamSheet(); return; }
      refreshDetail(true);
      loadCollection();
    } catch (e) {
      $("sheetErr").textContent = e.message;
    } finally {
      $("sheetSave").disabled = false;
    }
  }, L("Übernehmen"));

  const img = $("rotImg");
  const range = $("rotRange");
  const lab = $("rotDegLabel");
  img.src = src;
  const coverScale = (d) => {
    const w = img.naturalWidth || 1, h = img.naturalHeight || 1;
    const rad = (d * Math.PI) / 180;
    const cos = Math.abs(Math.cos(rad)), sin = Math.abs(Math.sin(rad));
    const bw = w * cos + h * sin, bh = w * sin + h * cos;
    return Math.max(w / bw, h / bh);
  };
  const paint = () => {
    const d = Number(range.value) || 0;
    lab.textContent = `${d > 0 ? "+" : ""}${d}°`;
    img.style.transform = `rotate(${d}deg) scale(${coverScale(d)})`;
  };
  range.oninput = paint;
  img.onload = paint;
  paint();
  const rr = $("rotRestore");
  if (rr) rr.onclick = async () => {
    if (item.id === "cam") {
      const i = Number.isFinite(item._camIndex) ? item._camIndex : idx;
      const s = (state.camShots || [])[i];
      if (s && s.edited) {
        s.edited = null;
        revokeCamShot(s);
        s.thumbUrl = URL.createObjectURL(s.original);
      }
      closeSheet();
      openCamSheet();
      return;
    }
    closeSheet();
    await restoreItemPhoto(item.id, idx);
  };
}

/* Schnellmenü aus dem Grid (Long-Press) — der kürzeste Weg zum Verkauf */
function openItemMenu(i) {
  const hasLocal = i.photos.some((p) => p.startsWith("/api/app/citem-photo"));
  const sellLabel = L(i.draft_status === "published" ? "Live bei eBay"
    : i.draft_id ? "Entwurf prüfen" : "eBay-Entwurf vorbereiten");
  openSheet(i.name.length > 34 ? i.name.slice(0, 34) + "…" : i.name, "", `
    <div class="opt-list">
      <button type="button" class="opt" data-m="sell"><span style="display:flex;align-items:center;gap:10px">${icon("bag", 17)} ${sellLabel}</span></button>
      <button type="button" class="opt" data-m="photo" ${hasLocal ? "" : "disabled"}><span style="display:flex;align-items:center;gap:10px">${icon("photo", 17)} ${L("Foto bearbeiten")}</span></button>
      <button type="button" class="opt" data-m="fav"><span style="display:flex;align-items:center;gap:10px">${icon(i.favorite ? "starfill" : "star", 17)} ${L(i.favorite ? "Favorit entfernen" : "Als Favorit")}</span></button>
      <button type="button" class="opt" data-m="wish"><span style="display:flex;align-items:center;gap:10px">${icon("heart", 17)} ${L(i.wishlist ? "Aus Wunschliste nehmen" : "Auf die Wunschliste")}</span></button>
      <button type="button" class="opt" data-m="del" style="color:var(--red)"><span style="display:flex;align-items:center;gap:10px">${icon("trash", 17)} ${L("Entfernen")}</span></button>
    </div>`, { hideActions: true, recede: false, fit: true });
  $("sheetBody").querySelectorAll("[data-m]").forEach((btn) => {
    btn.onclick = async (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const m = btn.dataset.m;
      try {
        if (m === "sell") {
          closeSheet();
          if (needAccountForSave() || isGuestItemId(i.id)) return;
          if (!hasLocal && !i.draft_id) return toast("Keine eigenen Fotos — bitte einmal neu scannen");
          openItemDetail(i.id, "sell");
        } else if (m === "photo") {
          // Kein Umweg über openItemDetail — der ließ das zweite Sheet oft hängen.
          closeSheet();
          openItemPhotoMenu(i);
        } else if (m === "fav") {
          closeSheet();
          if (needAccountForSave() || isGuestItemId(i.id)) return;
          await post(`/api/app/collection/item/${i.id}`, { favorite: !i.favorite });
          loadCollection();
        } else if (m === "wish") {
          closeSheet();
          if (needAccountForSave() || isGuestItemId(i.id)) return;
          await post(`/api/app/collection/item/${i.id}`, { wishlist: !i.wishlist });
          loadCollection();
        } else if (m === "del") {
          askRemoveItem(i);
        }
      } catch (e) { toast(e.message); }
    };
  });
}

function renderScan() {
  renderScanMode();
  const finder = $("scanFinder");
  if (finder && !finder._seroTap) {
    finder._seroTap = true;
    finder.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      startScanMode(state.scanIntent === "COLLECT_ONLY" ? "COLLECT_ONLY" : "SELL_SINGLE");
    });
  }
  // EINE Liste mit Live-Status statt Warteschlange + Verlauf (Karten erschienen doppelt)
  const sorted = [...state.items].sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  const recent = state._scanShowAll ? sorted : sorted.slice(0, 5);
  $("scanHistLabel").hidden = !recent.length;
  $("scanHistory").innerHTML = recent.map((i) => {
    const busy = i.status === "analyzing" || i.status === "waiting" || i.cutout_status === "running";
    return `
    <button class="irow tap" data-item="${i.id}">
      ${(i.card && i.card.image) || i.photos.length
        ? `<img class="simg" src="${esc(thumb(i.photos[0], 240) || (i.card && i.card.image))}" loading="lazy" alt="">`
        : `<span class="ric" style="background:var(--icon-neutral)">${icon("photo", 15)}</span>`}
      <span class="rlabel" style="font-size:14px">${esc(i.name)}</span>
      ${busy
        ? `<span class="rvalue ganalyzing"><span class="spinner"></span>${esc(i.status_text || L("Wird analysiert …"))}</span>`
        : `<span class="rvalue">${i.est_value !== null && i.est_value !== undefined ? money(i.est_value) : "—"}</span>`}
      <span class="chev">${icon("chevron", 15)}</span>
    </button>`; }).join("");
  fadeImgs($("scanHistory"));
  $("scanHistory").querySelectorAll("[data-item]").forEach((b) => {
    b.onclick = () => openItemDetail(b.dataset.item);
  });
  const all = $("scanAll");
  if (all) {
    all.hidden = state._scanShowAll || sorted.length <= 5;
    all.onclick = () => {
      state._scanShowAll = true;
      renderScan();
    };
  }
}

/* ═══════════════════ Verkauf ═══════════════════ */

function stopSalesPoll() {
  if (state.salesPollTimer) { clearInterval(state.salesPollTimer); state.salesPollTimer = null; }
}
function startSalesPoll() {
  stopSalesPoll();
  state.salesPollTimer = setInterval(() => {
    if ($("tabSales") && !$("tabSales").hidden && !document.hidden) loadSales(true);
  }, 60000);
}

async function loadSales(forceRefresh = false) {
  if (isGuest()) {
    state.sales = state.sales || { drafts: [], active: [], ended: [], stats: {} };
    renderSales();
    return;
  }
  const ticket = salesWins.begin();
  const list = $("salesList");
  if (!state.sales && list && !list.innerHTML) {
    list.innerHTML = skel(72) + skel(72) + skel(72);
    const empty = $("salesEmpty");
    if (empty) empty.hidden = true;
  }
  let r;
  try {
    r = await api("/api/app/sales" + (forceRefresh ? "?refresh=1" : ""), { signal: ticket.signal });
  } catch (e) {
    if (e && e.superseded) return;
    if (!state.sales) {
      state._salesError = (e && e.message) || L("Verkauf nicht geladen");
      renderSales();
    }
    return;
  }
  if (!ticket.isCurrent()) return;
  state.sales = r;
  state._salesError = null;
  if (r.ebay_needs_reconnect && state.me) state.me.ebay_needs_reconnect = true;
  renderSales();
  paintEbayHub();
  refreshColHubFromSales();
}

function salePriceLabel(r) {
  const st = String((r && r.status) || "");
  const liveRaw = r && (r.current_price != null && r.current_price !== "") ? r.current_price : r.price;
  const raw = liveRaw != null && liveRaw !== "" ? parseFloat(String(liveRaw).replace(",", ".")) : NaN;
  if (st === "ended" || r.sold_price) {
    const sold = r.sold_price != null && r.sold_price !== ""
      ? parseFloat(String(r.sold_price).replace(",", ".")) : raw;
    if (!isFinite(sold)) return "—";
    return LF("Verkauft für {0}", money(sold));
  }
  if (!isFinite(raw)) return "—";
  return money(raw);
}

/** Endzeit aus Unix-Sekunden — für Liste und Listing-Detail. */
function formatListingEnd(ts, { sold = false } = {}) {
  const n = Number(ts);
  if (!n || !isFinite(n)) return "";
  const ms = n > 1e12 ? n : n * 1000;
  const d = new Date(ms);
  if (isNaN(d.getTime())) return "";
  const opts = { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" };
  let abs;
  try {
    abs = d.toLocaleString("de-DE", opts).replace(",", "");
  } catch (_) {
    abs = d.toISOString().slice(0, 16).replace("T", " ");
  }
  if (sold) return LF("Verkauft {0}", abs);
  const diff = d.getTime() - Date.now();
  if (diff <= -60 * 60 * 1000) return LF("Endete {0}", abs);
  if (diff <= 0) return L("Endet gleich");
  const mins = Math.round(diff / 60000);
  if (mins < 60) return LF("Endet in {0} Min", Math.max(1, mins));
  const hours = Math.round(diff / 3600000);
  if (hours < 48) return LF("Endet in {0} Std", hours);
  return LF("Endet {0}", abs);
}

function saleEndLabel(r) {
  if (!r) return "";
  if (r.status === "ended") return formatListingEnd(r.sold_at || r.ends_at, { sold: true });
  return formatListingEnd(r.ends_at);
}

/** Detail: Ende, Gebote, Merkliste, Aufrufe — nur echte eBay-Zahlen. */
function listingStatsHtml(d) {
  if (!d || !(d.published || d.status === "ended")) return "";
  const isAuc = String(d.format || "").toUpperCase() === "AUCTION";
  const cells = [];
  const endL = saleEndLabel(d);
  if (endL) cells.push([endL, L("Termin")]);
  if (isAuc) {
    const n = Number(d.bid_count) || 0;
    cells.push([String(n), n === 1 ? L("Gebot") : L("Gebote")]);
  }
  if (d.watch_count != null && d.watch_count !== "") {
    cells.push([String(Number(d.watch_count) || 0), L("Merkliste")]);
  }
  if (d.hit_count != null && d.hit_count !== "") {
    cells.push([String(Number(d.hit_count) || 0), L("Aufrufe")]);
  }
  if (!cells.length) return "";
  return `<div class="listing-stats" role="group" aria-label="${esc(L("Listing-Zahlen"))}">`
    + cells.map(([v, k]) =>
      `<div class="ls-cell"><span class="ls-v">${esc(v)}</span><span class="ls-k">${esc(k)}</span></div>`)
      .join("")
    + `</div>`;
}

function saleSortKey(r, mode) {
  const price = salePriceNum(r) || 0;
  const end = Number(r && (r.ends_at || r.sold_at)) || 0;
  const edited = Number(r && r.updated_at) || 0;
  const created = Number(r && r.created_at) || 0;
  const sold = Number(r && r.sold_at) || 0;
  if (mode === "price_desc") return -price;
  if (mode === "price_asc") return price;
  if (mode === "edited") return edited ? -edited : 1e15;
  if (mode === "listed") return created ? -created : 1e15;
  if (mode === "sold") return sold ? -sold : (end ? -end : 1e15);
  if (mode === "end_desc") return end ? -end : 1e15;
  return end || 1e15;
}

function salesSortDefault(bucket) {
  if (bucket === "draft") return "edited";
  if (bucket === "ended") return "sold";
  return "end_asc";
}

function salesSortMode(bucket) {
  return storeSafe.getString("sero_sales_sort_" + bucket) || salesSortDefault(bucket);
}

function sortSalesRows(rows, bucket) {
  const mode = salesSortMode(bucket);
  return [...rows].sort((a, b) => {
    if (mode === "name") return String(a.title || "").localeCompare(String(b.title || ""), "de");
    if (mode === "nameza") return String(b.title || "").localeCompare(String(a.title || ""), "de");
    const d = saleSortKey(a, mode) - saleSortKey(b, mode);
    if (d) return d;
    return String(a.title || "").localeCompare(String(b.title || ""), "de");
  });
}

function openSalesSort() {
  const bucket = state.salesBucket || "draft";
  const cur = salesSortMode(bucket);
  const common = [
    { label: "Preis (höchster zuerst)", value: "price_desc" },
    { label: "Preis (niedrigster zuerst)", value: "price_asc" },
    { label: "Name (A–Z)", value: "name" },
  ];
  const head = bucket === "draft"
    ? [{ label: "Zuletzt bearbeitet", value: "edited" }]
    : bucket === "ended"
      ? [{ label: "Zuletzt verkauft", value: "sold" }]
      : [{ label: "Bald endend", value: "end_asc" }, { label: "Neu eingestellt", value: "listed" }];
  const opts = head.concat(common).map((o) => ({ ...o, sel: cur === o.value }));
  openOptions(L("Sortieren"), opts, (v) => {
    storeSafe.setString("sero_sales_sort_" + bucket, v);
    renderSales();
  });
}

function openSalesSearch() {
  const q = (state.salesQuery || "").trim();
  if (state.salesSearchOpen && !q) state.salesSearchOpen = false;
  else state.salesSearchOpen = true;
  renderSales();
  if (state.salesSearchOpen) {
    const inp = $("salesSearchLive");
    setTimeout(() => { try { if (inp) inp.focus(); } catch (_) { /* */ } }, 40);
  }
}

function openSalesFilter() {
  const draft = cloneInvFacets(state.salesFilter);
  const opts = {
    cats: invCatsSelected(state.salesFilter),
    withCats: true,
    withLang: false,
    withRegion: false,
    withYear: false,
    strictGrade: true,
    onLiveValue: () => {
      state.salesFilter.valueFrom = draft.valueFrom;
      state.salesFilter.valueTo = draft.valueTo;
      renderSales();
    },
  };
  openInvFilter("Filter", draft, opts, () => {
    applyInvFacets(state.salesFilter, draft);
    state.salesFilter.cats = (opts.cats || []).slice();
    renderSales();
  }, () => {
    invResetSheetFacets(draft);
    invResetSheetFacets(state.salesFilter);
    opts.cats = [];
    renderSales();
  });
}

function paintSalesInvBar(rows, hasItems = true) {
  const bar = $("salesInvBar");
  if (!bar) return;
  bar.hidden = !hasItems;
  if (!hasItems) return;
  const wrap = $("salesSearchWrap");
  const q = state.salesQuery || "";
  if (wrap) wrap.hidden = !(state.salesSearchOpen || q.trim());
  const inp = $("salesSearchLive");
  if (inp && document.activeElement !== inp && inp.value !== q) inp.value = q;
  const clr = $("salesSearchClear");
  if (clr) {
    clr.hidden = !String(q).trim();
    if (!clr.innerHTML) clr.innerHTML = icon("xmark", 14);
  }
  const ic = wrap && wrap.querySelector(".inv-search-ic");
  if (ic && !ic.innerHTML) ic.innerHTML = icon("search", 16);
  const applied = $("salesInvApplied");
  if (applied) {
    const html = invAppliedHtml(state.salesFilter, state.salesQuery, "salesInvApplied");
    applied.hidden = !html;
    applied.innerHTML = html || "";
    applied.querySelectorAll("[data-ak]").forEach((b) => {
      b.onclick = () => {
        invRemoveApplied(state.salesFilter, b.dataset.ak, (v) => {
          state.salesQuery = v;
          const i2 = $("salesSearchLive");
          if (i2) i2.value = v;
        });
        renderSales();
      };
    });
  }
  const count = $("salesInvCount");
  if (count) count.textContent = LF("{0} Stück", rows.length);
  let tools = $("salesInvTools");
  if (!tools && bar) {
    tools = document.createElement("div");
    tools.id = "salesInvTools";
    tools.className = "inv-tools";
    bar.appendChild(tools);
  }
  if (tools) {
    tools.innerHTML = `
      <button type="button" class="inv-tool" id="salesSearch">${esc(L("Suchen"))}</button>
      <button type="button" class="inv-tool" id="salesFilter">${esc(L("Filtern"))}</button>
      <button type="button" class="inv-tool" id="salesSort">${esc(L("Sortieren"))}</button>`;
    const sbtn = $("salesSort");
    if (sbtn) sbtn.onclick = openSalesSort;
    const fbtn = $("salesFilter");
    if (fbtn) fbtn.onclick = openSalesFilter;
    const qbtn = $("salesSearch");
    if (qbtn) qbtn.onclick = openSalesSearch;
  }
  ensureInvSearchWired();
}

function saleLayoutBadge(r, bucket) {
  const st = String((r && r.status) || "");
  if (bucket === "active" || st === "published")
    return `<span class="schip live">${esc(L("Live"))}</span>`;
  if (bucket === "ended" || st === "ended")
    return `<span class="schip">${esc(L("Verkauft"))}</span>`;
  return `<span class="schip warn">${esc(L("Entwurf"))}</span>`;
}

function saleFormatLabel(r) {
  return String((r && r.format) || "").toUpperCase() === "AUCTION" ? L("Auktion") : L("Sofortkauf");
}

function saleShippingLabel(r) {
  if (!r) return L("Versand");
  if (r.shipping_ok === false) return L("Versand fehlt");
  if (r.shipping_ok === true) return L("Versand eingerichtet");
  return r.shipping_label || r.ship_to || L("Versand");
}

function saleDraftHints(r) {
  const hints = [];
  if (!r) return hints;
  if (!(r.title || "").trim()) hints.push(L("Titel fehlt"));
  const p = r.price != null && r.price !== "" ? parseFloat(String(r.price).replace(",", ".")) : NaN;
  if (!isFinite(p) || p <= 0) hints.push(L("Preis fehlt"));
  if (!(r.condition || "").trim()) hints.push(L("Zustand fehlt"));
  const miss = r.missing_aspects || [];
  miss.slice(0, 3).forEach((n) => hints.push(String(n)));
  if (r.shipping_ok === false) hints.push(L("Versand fehlt"));
  if (r.error_text) hints.push(String(r.error_text));
  return hints;
}

function saleStatusChip(r, bucket) {
  const st = String((r && r.status) || "");
  if (bucket === "active" || st === "published")
    return `<span class="schip live">${esc(L("Aktiv"))}</span>`;
  if (bucket === "ended" || st === "ended")
    return `<span class="schip">${esc(L("Verkauft"))}</span>`;
  if (st === "error") return `<span class="schip err">${esc(L("Fehler"))}</span>`;
  if (st === "uncertain" || st === "publish_uncertain")
    return `<span class="schip warn">${esc(L("Unvollständig"))}</span>`;
  if (st === "ready" || st === "dry_run_done") {
    const hints = saleDraftHints(r);
    if (hints.length) return `<span class="schip warn">${esc(L("Unvollständig"))}</span>`;
    return `<span class="schip live">${esc(L("Bereit"))}</span>`;
  }
  return `<span class="schip warn">${esc(L("Unvollständig"))}</span>`;
}

function paintSalesSegInk() {
  const seg = $("salesSeg");
  const ink = $("salesSegInk");
  const on = seg && seg.querySelector("button.on");
  if (!seg || !ink || !on) return;
  ink.style.width = on.offsetWidth + "px";
  ink.style.transform = "translateX(" + on.offsetLeft + "px)";
}
if (typeof window !== "undefined" && !window._seroSalesInk) {
  window._seroSalesInk = true;
  window.addEventListener("resize", () => { try { paintSalesSegInk(); } catch (_) { /* */ } });
}

function renderSales() {
  const emptyEl = $("salesEmpty");
  const listEl = $("salesList");
  if (state._salesError && !state.sales) {
    if (listEl) listEl.innerHTML = "";
    if (emptyEl) {
      emptyEl.hidden = false;
      emptyEl.innerHTML = emptyState({
        icon: "refresh", titel: "Verkauf nicht geladen",
        text: state._salesError,
        aktion: "Erneut laden", onAktion: () => loadSales(true),
      });
    }
    return;
  }
  const s = state.sales;
  if (!s) return;
  const bucket = state.salesBucket || "draft";
  const stats = s.stats || {};
  const activeN = Number(stats.active || 0) || 0;
  const draftN = Number(stats.drafts || 0) || 0;
  const soldN = Number(stats.ended || 0) || (s.ended || []).length || 0;
  const listingVal = stats.value_active || 0;
  const draftVal = stats.value_drafts || 0;
  const soldVal = stats.value_sold || 0;
  let headLabel = L("Live");
  let headVal = money(activeN ? listingVal : 0);
  let headSub = activeN
    ? esc(LF("{0} aktiv auf eBay", activeN)) + (draftN ? ` · ${esc(LF("{0} Entwürfe", draftN))}` : "")
    : "";
  if (bucket === "draft") {
    headLabel = L("Entwurfswert");
    headVal = money(draftN ? draftVal : 0);
    headSub = draftN
      ? esc(LF("{0} Entwürfe", draftN))
      : "";
  } else if (bucket === "ended") {
    headLabel = L("Erlös");
    headVal = money(soldN ? soldVal : 0);
    headSub = soldN
      ? esc(LF("{0} verkauft", soldN))
      : "";
  }
  const mode = salesViewMode();
  /* Bei null Stücken in diesem Reiter ist die weiße Leiste Verkäufer-Möbel um
     nichts herum: kein Geld, keine vier Icon-Knöpfe, kein „0 Stück“ und keine
     zweite Zeile „Keine offenen Entwürfe“. Suche/Filter/Sort bleiben Text
     in der Inv-Leiste, nie vier Kreise. */
  const bucketKey = bucket === "active" ? "active" : bucket === "draft" ? "drafts" : "ended";
  const bucketRows = s[bucketKey] || [];
  const bucketLeer = bucketRows.length === 0;
  $("salesStats").innerHTML = `
    <div class="col-port compact sales-port">
      <div class="col-top">
        <div class="col-top-main">
          <span class="ov-label">${esc(headLabel)}</span>
          <div class="ov-value col-port-val">${headVal}</div>
          <span class="ov-sub">${headSub}</span>
        </div>
      </div>
    </div>`;
  const prevBucket = state._salesPaintBucket;
  $("salesSeg").querySelectorAll("button").forEach((b) => {
    b.classList.toggle("on", b.dataset.b === state.salesBucket);
    b.onclick = () => {
      state._salesBucketTouched = true;
      state.salesSelectMode = false;
      state.salesBucket = b.dataset.b;
      renderSales();
    };
  });
  paintSalesSegInk();
  state._salesPaintBucket = state.salesBucket;
  $("salesList").className = mode === "list" ? "" : `sale-grid ${mode}`;
  const rawRows = bucketRows;
  const q = (state.salesQuery || "").trim().toLowerCase();
  const filtered = rawRows.filter((r) => saleMatchesInv(r, state.salesFilter, q));
  const rows = sortSalesRows(filtered, bucket);
  paintSalesInvBar(rows, !bucketLeer);
  const offerChip = (r) => {
    const n = r.offer_count || (r.buyer_offers || []).length || 0;
    if (!n) return "";
    const top = r.top_offer ? money(parseFloat(String(r.top_offer))) : "";
    return `<span class="schip offer">${n === 1
      ? (top ? LF("Preisvorschlag {0}", top) : L("1 Preisvorschlag"))
      : (top ? LF("{0} Preisvorschläge · bis {1}", n, top) : LF("{0} Preisvorschläge", n))}</span>`;
  };
  const gridMode = salesViewMode() !== "list";
  const selecting = bucket === "draft" && !!state.salesSelectMode;
  const selectedIds = Object.keys(state.selectedDrafts || {}).filter((id) =>
    rows.some((r) => String(r.draft_id) === id));
  const selN = selectedIds.length;
  let bulkHtml = "";
  if (bucket === "draft" && rows.length >= 1) {
    if (!selecting) {
      bulkHtml = `<div class="sales-bulk-bar">
        <button type="button" class="btn-secondary" id="salesSelectStart">${esc(L("Bulk-Upload"))}</button>
      </div>`;
    } else {
      bulkHtml = `<div class="sales-bulk-bar">
        <button type="button" class="btn-plain" id="salesSelectAll">${esc(L("Alle auswählen"))}</button>
        <span class="sales-bulk-n">${esc(LF("{0} ausgewählt", selN))}</span>
        <button type="button" class="btn-plain" id="salesSelectCancel">${esc(L("Abbrechen"))}</button>
        <button type="button" class="btn-primary" id="bulkPublish" ${selN < 1 ? "disabled" : ""}>${icon("arrowup", 16)}<span>${esc(L("Auf eBay hochladen"))}</span></button>
      </div>`;
    }
  }
  const bulkBox = $("salesBulk");
  if (bulkBox) bulkBox.innerHTML = bulkHtml;
  const startSel = $("salesSelectStart");
  if (startSel) startSel.onclick = () => { state.salesSelectMode = true; renderSales(); };
  const allSel = $("salesSelectAll");
  if (allSel) allSel.onclick = () => {
    state.selectedDrafts = {};
    rows.forEach((r) => { state.selectedDrafts[r.draft_id] = true; });
    renderSales();
  };
  const cancelSel = $("salesSelectCancel");
  if (cancelSel) cancelSel.onclick = () => {
    state.salesSelectMode = false;
    state.selectedDrafts = {};
    renderSales();
  };
  renderScanQueue();
  let reconnectEl = $("salesReconnect");
  if (!reconnectEl) {
    reconnectEl = document.createElement("p");
    reconnectEl.id = "salesReconnect";
    reconnectEl.className = "assume";
    reconnectEl.hidden = true;
    const host = $("salesBulk") || $("salesList");
    if (host && host.parentNode) host.parentNode.insertBefore(reconnectEl, host);
  }
  const needsReconnect = (state.me && state.me.ebay_needs_reconnect) || s.ebay_needs_reconnect;
  if (needsReconnect) {
    reconnectEl.hidden = false;
    reconnectEl.innerHTML = `<span>${esc(L("Damit Verkäufe und Preisvorschläge korrekt erkannt werden, verbinde eBay einmal neu."))}</span>
      <button type="button" class="btn-secondary" id="salesReconnectBtn" style="margin-top:10px;width:100%">${esc(L("eBay neu verbinden"))}</button>`;
    const rb = $("salesReconnectBtn");
    if (rb) rb.onclick = () => { openEbayConnectSheet(state.me || {}); };
  } else {
    reconnectEl.hidden = true;
    reconnectEl.textContent = "";
  }
  $("salesList").innerHTML = rows.map((r) => {
    const oc = offerChip(r);
    const pl = salePriceLabel(r);
    const fmt = saleFormatLabel(r);
    const cond = condLabel(r.condition, r.category_name);
    const endL = saleEndLabel(r);
    const bids = Number(r.bid_count) || 0;
    const hints = bucket === "draft" ? saleDraftHints(r) : [];
    const hintHtml = hints.length
      ? `<span class="sr-hint">${esc(hints.slice(0, 2).join(" · "))}</span>` : "";
    const lid = r.listing_id ? LF("Listing {0}", r.listing_id) : "";
    const metaParts = [];
    if (bucket === "draft") {
      if (cond && cond !== "—") metaParts.push(cond);
      metaParts.push(fmt);
      metaParts.push(pl);
    } else if (bucket === "active") {
      metaParts.push(pl);
      metaParts.push(fmt);
      if (endL) metaParts.push(endL);
      if (bids) metaParts.push(`${bids} ${bids === 1 ? L("Gebot") : L("Gebote")}`);
      if (lid) metaParts.push(lid);
    } else {
      metaParts.push(pl);
      if (endL) metaParts.push(endL);
      if (r.platform) metaParts.push(r.platform);
    }
    const meta = metaParts.filter(Boolean).join(" · ");
    const tilePrice = endL ? `${pl}<br><span class="st-end">${esc(endL)}</span>` : pl;
    const checked = !!(state.selectedDrafts && state.selectedDrafts[r.draft_id]);
    const sel = selecting
      ? `<span class="sale-sel"><input type="checkbox" data-sel-draft="${esc(r.draft_id)}" ${checked ? "checked" : ""}></span>`
      : "";
    const rowCls = `sale-row${selecting && checked ? " is-select" : ""}${hints.length ? " is-blocked" : ""}`;
    const tileCls = `sale-tile${selecting && checked ? " is-select" : ""}`;
    const stChip = saleStatusChip(r, bucket);
    const layChip = saleLayoutBadge(r, bucket);
    return gridMode ? `
    <button class="${tileCls}" data-draft="${r.draft_id}" data-item="${r.item_id || ""}">
      ${sel}
      ${r.photo ? `<img src="${esc(thumb(r.photo, 480))}" loading="lazy" alt="">` : `<span class="gph-none">${MONO_PH}</span>`}
      ${layChip}${oc}
      <span class="st-t">${esc(r.title || L("Stück"))}</span>
      <span class="st-p">${tilePrice}</span>
    </button>` : `
    <button class="${rowCls}" data-draft="${r.draft_id}" data-item="${r.item_id || ""}">
      ${sel}
      ${r.photo ? `<img src="${esc(thumb(r.photo, 240))}" loading="lazy" alt="">` : `<span class="mv-ph">${MONO_PH}</span>`}
      <span class="sr-body"><span class="sr-t">${esc(r.title || L("Stück"))}</span>
        <span class="sr-m">${esc(meta)}</span>
        ${hintHtml}
        <span class="sr-chips">${stChip}${oc}</span></span>
      <span class="chev">${icon("chevron", 15)}</span>
    </button>`;
  }).join("");
  const listEl2 = $("salesList");
  if (listEl2 && prevBucket && prevBucket !== bucket
      && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    listEl2.classList.remove("sales-xfade");
    void listEl2.offsetWidth;
    listEl2.classList.add("sales-xfade");
  }
  $("salesList").querySelectorAll("[data-sel-draft]").forEach((inp) => {
    inp.onclick = (ev) => { ev.stopPropagation(); };
    inp.onchange = () => {
      state.selectedDrafts = state.selectedDrafts || {};
      if (inp.checked) state.selectedDrafts[inp.dataset.selDraft] = true;
      else delete state.selectedDrafts[inp.dataset.selDraft];
      renderSales();
    };
  });
  $("salesEmpty").hidden = rows.length > 0;
  let fotoHost = $("salesFotoPill");
  if (!fotoHost) {
    fotoHost = document.createElement("div");
    fotoHost.id = "salesFotoPill";
    const list = $("salesList");
    if (list && list.parentNode) list.parentNode.insertBefore(fotoHost, list.nextSibling);
  }
  if (fotoHost) {
    fotoHost.hidden = true;
    fotoHost.innerHTML = "";
  }
  if (!rows.length) {
    const v = state.salesBucket;
    const listAction = () => {
      if (!ebayConnectedNow()) { showEbayNotConnectedHint(); return; }
      openPlusSheet();
    };
    const q = (state.salesQuery || "").trim();
    const filteredOut = rawRows.length > 0;
    $("salesEmpty").innerHTML = filteredOut ? emptyState({
      icon: "search",
      titel: q ? LF("Keine Treffer für „{0}“", q) : "Keine Treffer",
      text: "Suchbegriff kürzen oder Filter zurücksetzen.",
      sekundar: "Filter zurücksetzen",
      onSekundar: () => {
        invResetSheetFacets(state.salesFilter);
        state.salesQuery = "";
        state.salesSearchOpen = false;
        const inp = $("salesSearchLive");
        if (inp) inp.value = "";
        renderSales();
      },
    }) : v === "active" ? emptyState({
      icon: "bag", titel: "Noch nichts live.",
      text: "",
    }) : v === "draft" ? emptyState({
      icon: "doc", titel: "Keine Entwürfe.",
      text: "",
      aktion: "Einstellen", onAktion: listAction, well: true,
    }) : `<p class="sales-empty-muted">${esc(L("Erlöse erscheinen hier"))}</p>`;
  }
  fadeImgs($("salesList"));
  $("salesList").querySelectorAll(".sale-row, .sale-tile").forEach((b) => {
    b.onclick = async () => {
      const did = b.dataset.draft;
      if (selecting && did) {
        state.selectedDrafts = state.selectedDrafts || {};
        if (state.selectedDrafts[did]) delete state.selectedDrafts[did];
        else state.selectedDrafts[did] = true;
        renderSales();
        return;
      }
      if (b.dataset.item) return openItemDetail(b.dataset.item, "ebay");
      try {
        const r = await post(`/api/app/collection/adopt/${did}`);
        loadCollection();
        openItemDetail(r.item_id, "ebay");
      } catch {
        openDraftDetail(did);
      }
    };
  });
}

/* ═══════════════════ Profil & Einstellungen ═══════════════════ */

/* ── Ein einziger Leer-Zustand für die ganze App ──
   Vorher: Sammlung = ganze Bühne, Verkauf = grauer Satz ins Nichts,
   Übersicht = gar keiner, Filter-Treffer = nackter Text. */
/* `well: true` stellt den Leerzustand in ein anthrazitfarbenes Foto-Feld —
   die Fläche, auf der später das Bild liegt. Ohne das las sich der leere
   Verkaufen-Reiter wie ein Dashboard ohne Zahlen. */
function emptyState({ icon: ic = "stack", titel, text, aktion, onAktion, sekundar, onSekundar, well }) {
  const id = "es" + Math.random().toString(36).slice(2, 8);
  setTimeout(() => {
    const b = $(id); if (b && onAktion) b.onclick = onAktion;
    const s = $(id + "s"); if (s && onSekundar) s.onclick = onSekundar;
  }, 0);
  return `<div class="empty compact${well ? " empty-well" : ""}">
    <span class="es-ic">${icon(ic, 26)}</span>
    <h2>${esc(L(titel))}</h2>
    ${text ? `<p>${esc(L(text))}</p>` : ""}
    ${aktion ? `<button class="btn-primary" id="${id}">${esc(L(aktion))}</button>` : ""}
    ${sekundar ? `<button class="btn-secondary" id="${id}s">${esc(L(sekundar))}</button>` : ""}
  </div>`;
}

/* ── Sammler-Fortschritt: Stufe, Punkte, Set-Lücken ── */
/* ── Profil bearbeiten: Name, Avatar, Anmelde-Kennung ── */
/* ── eBay-Setup direkt in der App abschließen (vorher nur via Telegram-Bot
   oder Website möglich — der teuerste Onboarding-Blocker). Richtlinien werden
   automatisch angelegt/übernommen; die App fragt nur die Versandadresse ab. ── */
function openSetupSheet(me) {
  /* Ohne eBay-Konto gibt es keinen Versandstandort zu setzen. Vorher öffnete
     sich hier stillschweigend das Verbinden-Sheet — die falsche Tür: man tippt
     auf „Versand & eBay-Richtlinien“ und steht bei „eBay verbinden“, ohne zu
     wissen warum. Jetzt sagt SERO den Grund und bietet den Weg an. */
  if (!me.ebay_connected) {
    openSheet(L("Versand & eBay-Richtlinien"),
      L("Dafür braucht SERO zuerst dein eBay-Konto. Versandstandort und Verkaufsrichtlinien liegen dort."),
      "", () => { closeSheet(); openEbayConnectSheet(me); }, "eBay verbinden");
    return;
  }
  openSheet(L("eBay-Setup abschließen"), L("eBay braucht einen Versandstandort. Die Adresse wird nicht öffentlich angezeigt."),
    `<input id="suStreet" type="text" placeholder="${esc(L("Straße und Hausnummer"))}">
     <div style="display:flex;gap:10px;margin-top:10px">
       <input id="suPlz" type="text" inputmode="numeric" maxlength="5" placeholder="${esc(L("PLZ"))}" style="flex:0 0 100px">
       <input id="suCity" type="text" placeholder="${esc(L("Stadt"))}" style="flex:1">
     </div>
     <p class="pe-note">${L("Vorhandene Verkaufsrichtlinien aus deinem eBay-Konto werden übernommen — es wird nichts doppelt angelegt.")}</p>`,
    async () => {
      $("sheetSave").disabled = true;
      try {
        await post("/api/ebay-setup", {
          street: $("suStreet").value.trim(),
          postal_code: $("suPlz").value.trim(),
          city: $("suCity").value.trim(),
        });
        state.me = await api("/api/me").catch(() => state.me);
        closeSheet(); renderProfile(); toast("Setup abgeschlossen — du kannst jetzt listen", "check");
      } catch (e) {
        $("sheetErr").textContent = e.message;
      } finally { $("sheetSave").disabled = false; }
    }, L("Setup abschließen"));
}

/** eBay verbinden / neu verbinden — gleicher Ablauf für Verkauf und Profil.
 *  Neuer Tab + Poll; Paste-Fallback wenn RuName lokal nicht zurückkommt. */
function openEbayConnectSheet(me) {
  const reconnect = !!(me && me.ebay_needs_reconnect);
  openSheet(
    L(reconnect ? "eBay neu verbinden" : "eBay verbinden"),
    reconnect
      ? L("Damit Verkäufe korrekt erkannt werden, brauchst du den Scope für Bestellungen. Tippe unten — danach prüft SERO die Verbindung.")
      : L("Bevor das Setup starten kann, verbinde zuerst dein eBay-Konto."),
    `<p class="sheet-hint" style="font-size:15px;line-height:1.55;margin:0 0 12px">${L(
      "eBay öffnet sich in einem neuen Tab. Diese App bleibt offen — nach der Freigabe tippe „Verbindung prüfen“, oder warte kurz.")}</p>
     <button type="button" class="btn-primary" id="ebayConnectGo" style="width:100%">${esc(L(
       reconnect ? "eBay neu verbinden" : "eBay verbinden"))}</button>
     <button type="button" class="btn-secondary" id="ebayConnectCheck" style="width:100%;margin-top:10px">${esc(L("Verbindung prüfen"))}</button>
     <p class="sheet-hint" style="font-size:13px;line-height:1.45;margin:16px 0 8px">${L(
       "Wenn du nach der Freigabe nicht automatisch zurückkommst: kopiere die komplette Adresse aus der Browser-Zeile und füge sie hier ein.")}</p>
     <input id="ebayPasteUrl" type="url" autocapitalize="off" autocomplete="off"
       placeholder="${esc(L("https://auth.ebay.com/…?code=…"))}" style="width:100%">
     <button type="button" class="btn-secondary" id="ebayPasteGo" style="width:100%;margin-top:10px">${esc(L("Verbindung speichern"))}</button>`,
    null);
  setTimeout(() => {
    const b = $("ebayConnectGo");
    if (b) b.onclick = () => { goEbayConnect(); };
    const c = $("ebayConnectCheck");
    if (c) c.onclick = async () => {
      c.disabled = true;
      if ($("sheetErr")) $("sheetErr").textContent = "";
      try {
        const me2 = await api("/api/me", { timeout: 8000 });
        state.me = me2;
        cache.set("me", me2);
        if (ebayTokenLooksNew(me2)) afterEbayConnectOk(me2);
        else if (me2.ebay_connected && !me2.ebay_needs_reconnect) afterEbayConnectOk(me2);
        else if ($("sheetErr")) {
          $("sheetErr").textContent = L("Noch nicht verbunden. Nach der Freigabe bei eBay hier erneut tippen — oder die Adresse einfügen.");
        }
      } catch (e) {
        if ($("sheetErr")) $("sheetErr").textContent = e.message || L("eBay-Verbindung fehlgeschlagen");
      } finally { c.disabled = false; }
    };
    const p = $("ebayPasteGo");
    if (p) p.onclick = submitEbayPasteUrl;
  }, 0);
}

async function submitEbayPasteUrl() {
  const inp = $("ebayPasteUrl");
  const url = (inp && inp.value || "").trim();
  const err = $("sheetErr");
  if (err) err.textContent = "";
  if (!url || !url.includes("code=")) {
    if (err) err.textContent = L("Kein code= in der URL gefunden.");
    return;
  }
  if ($("ebayPasteGo")) $("ebayPasteGo").disabled = true;
  try {
    markEbayConnectPending();
    await post("/api/ebay-redirect", { url });
    state.me = await api("/api/me");
    cache.set("me", state.me);
    afterEbayConnectOk(state.me);
  } catch (e) {
    if (err) err.textContent = e.message || L("eBay-Verbindung fehlgeschlagen");
  } finally {
    const btn = $("ebayPasteGo");
    if (btn) btn.disabled = false;
  }
}

function openProfileSheet(me) {
  let pendingAvatar = null; // zugeschnittenes JPEG, bereit zum Upload
  openSheet(L("Profil"), L("Dein Name erscheint in der App und in deinen Exporten."),
    `<button type="button" class="pe-ava" id="peAva" aria-label="${esc(L("Foto ändern"))}">
       ${me.avatar_url ? `<img src="${esc(me.avatar_url)}" alt="">`
                       : `<span class="pe-letter">${esc((me.display_name || me.username || me.email || "?")[0].toUpperCase())}</span>`}
       <span class="pe-ava-overlay"><i>${icon("camera", 20)}</i><em>${L("Foto ändern")}</em></span>
     </button>
     <p class="pe-ava-hint">${L("Tippe auf das Bild, um ein neues Foto zu wählen. Mit „Sichern“ übernimmst du es.")}</p>
     <input id="peName" type="text" maxlength="40" placeholder="${esc(L("Dein Name"))}" value="${esc(me.display_name || "")}">
     <p class="sheet-hint" style="margin:14px 0 4px">${L("Anmelde-Kennung")}</p>
     <input id="peUser" type="text" maxlength="24" autocapitalize="none" placeholder="${esc(L("z. B. sammler_muc"))}" value="${esc(me.username || "")}">
     <p class="pe-note">${L("Mit dieser Kennung kannst du dich statt mit der E-Mail anmelden. Änderst du sie, gilt sofort die neue.")}</p>
     <input id="peFile" type="file" accept="image/*" hidden>`,
    async () => {
      $("sheetSave").disabled = true;
      try {
        if (pendingAvatar) {
          const fd = new FormData();
          fd.append("file", pendingAvatar, "avatar.jpg");
          await api("/api/avatar", { method: "POST", body: fd });
        }
        await post("/api/profile", {
          display_name: $("peName").value.trim(),
          username: $("peUser").value.trim() || null,
        });
        state.me = await api("/api/me").catch(() => state.me);
        closeSheet(); renderProfile(); toast("Profil gespeichert", "check");
      } catch (e) {
        $("sheetErr").textContent = e.message;
      } finally { $("sheetSave").disabled = false; }
    }, L("Sichern"));
  $("peAva").onclick = () => $("peFile").click();
  $("peFile").onchange = async () => {
    const f = $("peFile").files[0];
    if (!f) return;
    try {
      pendingAvatar = await squareImageBlob(f, 512);
      const prev = $("peAva").querySelector("img[data-blob]");
      if (prev) URL.revokeObjectURL(prev.src);
      const url = URL.createObjectURL(pendingAvatar);
      $("peAva").innerHTML =
        `<img data-blob="1" src="${url}" alt=""><span class="pe-ava-overlay"><i>${icon("camera", 20)}</i><em>${L("Foto ändern")}</em></span>`;
      toast(L("Vorschau bereit — tippe auf Sichern"), "check");
    } catch (e) {
      pendingAvatar = null;
      toast(e.message || L("Foto konnte nicht geladen werden"));
    }
  };
}

async function shareSero() {
  const data = {
    title: "SERO",
    text: L("SERO erkennt deine Sammelstücke und listet sie mit einem Tipp auf eBay."),
    url: "https://seromunich.com",
  };
  try {
    if (navigator.share) await navigator.share(data);
    else {
      await navigator.clipboard.writeText(data.url);
      toast("Link kopiert", "check");
    }
  } catch (e) {
    if (e && e.name === "AbortError") return;
    try {
      await navigator.clipboard.writeText(data.url);
      toast("Link kopiert", "check");
    } catch { toast("Teilen nicht möglich"); }
  }
}

async function renderProfile() {
  let me = state.me;
  try { me = state.me = await api("/api/me"); } catch { /* alter Stand */ }
  state.settings = await api("/api/app/settings").catch(() => state.settings || { notifications: true });
  if (!me) return;
  const initial = (me.username || me.email || "?")[0].toUpperCase();
  const used = me.used_this_month ?? 0;
  const limit = me.plan_limit;
  const planKey = (me.plan || "trial").toLowerCase();
  const planName = { trial: "Testphase", starter: "Starter", reseller: "Reseller", shop: "Shop" }[planKey] || me.plan;
  // Sticker und Tarifname sind derselbe Text — Versalien lasen sich wie eine Warnung.
  const planBadge = planName || "—";
  const nPub = (state.items || []).filter((i) => i.draft_status === "published").length
    || (state.dash && state.dash.sales && state.dash.sales.active) || 0;
  const nStueck = (state.stats && state.stats.count) || (state.dash && state.dash.count)
    || (state.items || []).filter((i) => !i.wishlist && !(i.sold || i.draft_status === "ended")).length;
  const nSold = (state.items || []).filter((i) => i.sold || i.draft_status === "ended").length;

  const menuRow = (ic, label, id, right = "", danger = false) => `
    <button class="tv-menu-row ${danger ? "danger" : ""}" id="${id}">
      <span class="tv-mic">${icon(ic, 18)}</span>
      <span class="tv-mlabel">${L(label)}</span>
      ${right}
      ${danger ? "" : `<span class="chev">${icon("chevron", 14)}</span>`}
    </button>`;

  $("profileScroll").innerHTML = `
    <div class="tab-title-glass page-tab-title">${titlePair("profil", "Profil", "profil")}</div>
    <div class="tv-prof-card" id="profCard">
      <div class="tv-prof-top">
        <button type="button" class="tv-ava" id="profAva" aria-label="${esc(L("Foto ändern"))}">
          ${me.avatar_url ? `<img src="${me.avatar_url}" alt="">` : `<span>${esc(initial)}</span>`}
          <span class="tv-ava-cam">${icon("camera", 14)}</span>
        </button>
        <button type="button" class="tv-prof-info" id="profEdit">
          <span class="tv-pname">${esc(me.display_name || me.username || L("Dein Name"))}</span>
          <span class="tv-badge">${esc(planBadge)}</span>
          <span class="tv-ava-hint">${L("Foto tippen zum Ändern")}</span>
        </button>
        <button type="button" class="tv-prof-chev" id="profEdit2" aria-label="${esc(L("Profil"))}">
          <span class="chev">${icon("chevron", 16)}</span>
        </button>
      </div>
      <div class="tv-prof-stats">
        <div><b>${nPub}</b><span>${L("Veröffentlicht")}</span></div>
        <div><b>${nStueck}</b><span>${L("Stück")}</span></div>
        <div><b>${nSold}</b><span>${L("Verkäufe")}</span></div>
      </div>
    </div>

    <div class="tv-tiles">
      <button class="tv-tile" id="profPremium">
        <span class="tv-tile-ic">${icon("ticket", 20)}</span>
        <span class="chev">${icon("chevron", 14)}</span>
        <b>${L("Abonnement")}</b>
        <p>${esc(planName)}${limit ? ` · ${used} / ${limit}` : ""} — ${L("Scans und Listen ohne Limit")}</p>
      </button>
      <button class="tv-tile" id="profShare">
        <span class="tv-tile-ic">${icon("share", 20)}</span>
        <b>${L("Einem Freund empfehlen")}</b>
        <p>${L("Teile SERO mit anderen Sammlern")}</p>
      </button>
    </div>

    <div class="tab-title-glass"><img class="tab-title sm title-invert" src="assets/titles/einstellungen.png?v=${TITLE_V}" alt="Einstellungen" width="867" height="247"></div>

    <div class="tv-menu">
      ${menuRow("link", "Verbindungen", "profConn",
        `<span class="tv-mval">${esc(me.ebay_connected ? L("eBay") : L("Einrichten"))}</span>`)}
      ${menuRow("gear", "Darstellung", "profAppear")}
      ${menuRow("tray", "Daten & Sync", "profData")}
      ${menuRow("question", "Hilfe & Rechtliches", "profLegal")}
    </div>

    <div class="tv-menu logout">
      ${menuRow("logout", "Abmelden", "profLogout", "", true)}
    </div>
    <div class="tv-menu danger">
      ${menuRow("trash", "Konto löschen …", "profDelete", "", true)}
    </div>
    <p class="version">SERO für iOS &amp; Web · v4.0</p>
    ${me.ebay_needs_reconnect ? `<p class="sheet-hint tv-reconnect">${L("Damit Verkäufe korrekt erkannt werden, verbinde eBay einmal neu.")}</p>` : ""}`;

  const openProfPanel = (title, bodyHtml, wire) => {
    openSheet(title, "", bodyHtml, null);
    if (wire) wire();
  };

  $("profConn").onclick = () => openProfPanel(L("Verbindungen"), `
    <div class="opt-list">
      <button class="opt" id="pEbay"><span style="display:flex;align-items:center;gap:10px">${icon("link", 17)} ${L("eBay-Konto")}</span>
        <span class="tv-mval${me.ebay_needs_reconnect ? " warn" : ""}" style="margin-left:auto;font-size:13px;color:var(--label-2)">${esc(
          me.ebay_needs_reconnect ? L("Neu verbinden")
            : (me.ebay_connected ? L("Verbunden") : L("Nicht verbunden")))}</span></button>
      <div class="opt"><span style="display:flex;align-items:center;gap:10px">${icon("bubble", 17)} ${L("Telegram")}</span>
        <span style="margin-left:auto;font-size:13px;color:var(--label-2)">${me.telegram_linked ? L("Verknüpft") : "—"}</span></div>
      ${!me.setup_ready ? `<button class="opt" id="pSetup"><span style="display:flex;align-items:center;gap:10px">${icon("gear", 17)} ${L("Setup")}</span>
        <span style="margin-left:auto;font-size:13px;color:var(--orange)">${L("Unvollständig")}</span></button>` : ""}
    </div>`, () => {
    const e = $("pEbay");
    if (e) e.onclick = () => { closeSheet(); openEbayConnectSheet(me); };
    const s = $("pSetup");
    if (s) s.onclick = () => { closeSheet(); openSetupSheet(me); };
  });

  $("profAppear").onclick = () => openProfPanel(L("Darstellung"), `
    <div class="opt-list">
      <button class="opt" id="pTheme"><span style="display:flex;align-items:center;gap:10px">${icon("gear", 17)} ${L("Erscheinungsbild")}</span></button>
      <button class="opt" id="pHero"><span style="display:flex;align-items:center;gap:10px">${icon("photo", 17)} ${L("Portfolio-Hintergrund")}</span>
        <span class="chev">${icon("chevron", 14)}</span></button>
      <div class="opt"><span style="display:flex;align-items:center;gap:10px">${icon("bell", 17)} ${L("Preisalarm-Hinweise")}</span>
        <span class="sw"><input type="checkbox" id="pNotif" ${state.settings.notifications ? "checked" : ""}><i></i></span></div>
      <div class="opt"><span style="display:flex;align-items:center;gap:10px">${icon("photo", 17)} ${L("Katalog-Bilder im Grid")}</span>
        <span class="sw"><input type="checkbox" id="pCatalog" ${catalogView() ? "checked" : ""}><i></i></span></div>
    </div>`, () => {
    $("pTheme").onclick = () => {
      const cur = storeSafe.getString("sero_theme", "auto") || "auto";
      openOptions("Erscheinungsbild", [
        { label: "Automatisch (System)", value: "auto", sel: cur === "auto" },
        { label: "Hell", value: "light", sel: cur === "light" },
        { label: "Dunkel", value: "dark", sel: cur === "dark" },
      ], (v) => { storeSafe.setString("sero_theme", v); applyTheme(); });
    };
    $("pHero").onclick = () => openHeroDesigner();
    $("pNotif").onchange = (e) =>
      post("/api/app/settings", { notifications: e.target.checked }).catch(() => toast("Einstellung nicht gespeichert. Versuch es erneut."));
    $("pCatalog").onchange = (e) => {
      storeSafe.setString("sero_catalog", e.target.checked ? "1" : "0");
      renderCollection();
    };
  });

  $("profData").onclick = () => openProfPanel(L("Daten & Sync"), `
    <div class="opt-list">
      <button class="opt" id="pImport"><span style="display:flex;align-items:center;gap:10px">${icon("tray", 17)} ${L("eBay-Listings importieren")}</span></button>
      <button class="opt" id="pExport"><span style="display:flex;align-items:center;gap:10px">${icon("download", 17)} ${L("Sammlung exportieren (Backup)")}</span></button>
      <button class="opt" id="pRefresh"><span style="display:flex;align-items:center;gap:10px">${icon("refresh", 17)} ${L("Alle Preise aktualisieren")}</span></button>
      <button class="opt" id="pRescan"><span style="display:flex;align-items:center;gap:10px">${icon("scanframe", 17)} ${L("Sammlung neu erkennen")}</span></button>
    </div>`, () => {
    $("pImport").onclick = () => { closeSheet(); importListings(); };
    $("pExport").onclick = () => { closeSheet(); window.location = "/api/app/export"; };
    $("pRefresh").onclick = async () => {
      closeSheet();
      toast(L("Preise werden aktualisiert …"), "refresh");
      try {
        const r = await post("/api/app/collection/refresh", null, { timeout: 600000 });
        toast(LF("Preise aktualisiert ({0} von {1})", r.updated, r.total), "check");
        loadCollection(); loadDashboard();
      } catch (e) { toast(e.message); }
    };
    $("pRescan").onclick = async () => {
      closeSheet();
      const ok = await confirmSheet(
        L("Sammlung neu erkennen"),
        L("SERO analysiert alle Stücke mit Foto erneut — Set, Nummer und Sprache werden nachgezogen. Dauert bei vielen Stücken eine Weile."),
        L("Neu erkennen"));
      if (!ok) return;
      toast(L("Sammlung wird neu erkannt …"), "scanframe");
      try {
        const r = await post("/api/app/collection/rescan-all");
        toast(LF("{0} Stücke in der Warteschlange", r.enqueued), "check");
        loadCollection();
      } catch (e) { toast(e.message); }
    };
  });

  $("profLegal").onclick = () => openProfPanel(L("Hilfe & Rechtliches"), `
    <div class="opt-list">
      <button class="opt" id="pHelp"><span style="display:flex;align-items:center;gap:10px">${icon("question", 17)} ${L("Hilfe & Kontakt")}</span></button>
      <button class="opt" id="pPrivacy"><span style="display:flex;align-items:center;gap:10px">${icon("shield", 17)} ${L("Datenschutz")}</span></button>
      <button class="opt" id="pAbout"><span style="display:flex;align-items:center;gap:10px">${icon("info", 17)} ${L("Über")}</span></button>
      <button class="opt" id="pTerms"><span style="display:flex;align-items:center;gap:10px">${icon("doc", 17)} ${L("Nutzungsbedingungen")}</span></button>
      <button class="opt" id="pSite"><span style="display:flex;align-items:center;gap:10px">${icon("link", 17)} ${L("SERO-Website öffnen")}</span></button>
    </div>`, () => {
    const go = (id, fn) => { const el = $(id); if (el) el.onclick = () => { closeSheet(); fn(); }; };
    // Bestehende Handler unten spiegeln — nach closeSheet die Original-IDs nutzen
    go("pHelp", () => window.open("/hilfe.html", "_blank"));
    go("pPrivacy", () => window.open("/datenschutz.html", "_blank"));
    go("pAbout", () => window.open("/", "_blank"));
    go("pTerms", () => window.open("/agb.html", "_blank"));
    go("pSite", () => window.open("/", "_blank"));
  });

  // Alte Direkt-Handler entfallen — Kategorien oben.
  $("profPremium").onclick = openPaywall;
  $("profShare").onclick = shareSero;
  const openProf = () => openProfileSheet(me);
  $("profEdit").onclick = openProf;
  const pe2 = $("profEdit2");
  if (pe2) pe2.onclick = openProf;
  $("profAva").onclick = () => {
    openProfileSheet(me);
    const f = $("peFile");
    if (f) f.click();
  };
  $("profLogout").onclick = async () => {
    await post("/api/logout").catch(() => {});
    storeSafe.remove("sero_col");
    try {
      storeSafe.remove(tourStorageKey());
      storeSafe.remove("sero_tour");
    } catch (_) { /* */ }
    location.reload();
  };
  paintTopAva();
}


function seroDetailApi() {
  return (typeof SeroDetail !== "undefined" && SeroDetail) || (typeof window !== "undefined" && window.SeroDetail) || null;
}

function shareItem(item) {
  const name = (item && (item.name || item.title)) || "SERO";
  const data = { title: name, text: name };
  return Promise.resolve().then(async () => {
    try {
      if (navigator.share) await navigator.share(data);
      else {
        await navigator.clipboard.writeText(name);
        toast(L("Link kopiert"), "check");
      }
    } catch (e) {
      if (e && e.name === "AbortError") return;
      try {
        await navigator.clipboard.writeText(name);
        toast(L("Link kopiert"), "check");
      } catch { toast(L("Teilen nicht möglich")); }
    }
  });
}

function bindDetailScrollTitle(name) {
  const body = $("detailBody");
  const hero = $("detailHeroTitle");
  const bar = $("detailTitle");
  if (!body || !bar) return;
  const paint = () => {
    if (!hero) { bar.textContent = ""; return; }
    const barEl = document.querySelector("#detail .detail-bar");
    const cut = barEl ? barEl.getBoundingClientRect().bottom + 4 : 80;
    bar.textContent = hero.getBoundingClientRect().bottom <= cut ? (name || "") : "";
  };
  if (bindDetailScrollTitle._on) body.removeEventListener("scroll", bindDetailScrollTitle._on);
  let raf = 0;
  bindDetailScrollTitle._on = () => {
    if (raf) return;
    raf = requestAnimationFrame(() => { raf = 0; paint(); });
  };
  body.addEventListener("scroll", bindDetailScrollTitle._on, { passive: true });
  paint();
}

function detailGalleryImages(item, preferDesign) {
  const SD = seroDetailApi();
  if (SD) return SD.detailImages(item, { preferDesign: !!preferDesign });
  const photos = (item && Array.isArray(item.photos)) ? item.photos.filter(Boolean) : [];
  const out = [];
  const seen = {};
  const add = (url, kind) => {
    if (!url) return;
    const key = String(url).split("?")[0];
    if (seen[key]) return;
    seen[key] = true;
    out.push({ url: url, kind: kind });
  };
  const designUrl = item && item.design_photo;
  if (preferDesign && designUrl) add(designUrl, "design");
  photos.forEach((u, i) => add(u, i === 0 ? "front" : (i === 1 ? "back" : "extra")));
  if (designUrl) add(designUrl, "design");
  return out;
}

function galleryTrackHtml(images) {
  if (!images.length) return `<div class="d-gal-slide d-gal-empty">${icon("photo", 36)}</div>`;
  return images.map((im, i) => `<div class="d-gal-slide" data-i="${i}" data-kind="${esc(im.kind || "")}">
       <img src="${esc(thumb(im.url, 1600))}" loading="${i === 0 ? "eager" : "lazy"}" alt="">
     </div>`).join("");
}

function galleryThumbsHtml(images) {
  const thumbsSrc = images.length ? images : [{ url: "" }];
  return thumbsSrc.map((im, i) =>
    `<button type="button" class="d-gal-th${i === 0 ? " on" : ""}" data-i="${i}">
       ${im.url ? `<img src="${esc(thumb(im.url, 240))}" loading="lazy" alt="">` : icon("photo", 16)}
     </button>`).join("");
}

function paintDetailHeroGallery(item, det, opts) {
  opts = opts || {};
  const preferDesign = (det && det.seg) === "sell";
  const images = detailGalleryImages(item, preferDesign);
  const track = $("detailGalleryTrack");
  const thumbsEl = $("detailGalleryThumbs");
  const sig = images.map((im) => im.url || "").join("\n");
  const same = det && det._heroSig === sig && track && track.children.length;
  if (same && !opts.force) {
    bindDetailGallery(images, det);
    return images;
  }
  const keepIdx = (det && typeof det.photoIdx === "number") ? det.photoIdx : 0;
  if (track) {
    track.innerHTML = galleryTrackHtml(images);
    const w = track.clientWidth || 1;
    track.scrollLeft = Math.max(0, Math.min(images.length - 1, keepIdx)) * w;
  }
  if (thumbsEl) thumbsEl.innerHTML = galleryThumbsHtml(images);
  if (det) {
    det.photoIdx = Math.max(0, Math.min(Math.max(images.length, 1) - 1, keepIdx));
    det._heroSig = sig;
  }
  bindDetailGallery(images, det);
  return images;
}

function bindDetailGallery(images, det) {
  const track = $("detailGalleryTrack") || document.querySelector(".d-gallery-track");
  const thumbs = document.querySelectorAll("#detailGalleryThumbs .d-gal-th");
  if (!track) return;
  if (bindDetailGallery._onScroll && bindDetailGallery._track) {
    bindDetailGallery._track.removeEventListener("scroll", bindDetailGallery._onScroll);
  }
  const n = Math.max(1, images.length);
  const setIdx = (idx) => {
    idx = Math.max(0, Math.min(n - 1, idx));
    det.photoIdx = idx;
    const w = track.clientWidth || 1;
    track.scrollTo({ left: idx * w, behavior: "smooth" });
    thumbs.forEach((t, i) => t.classList.toggle("on", i === idx));
  };
  bindDetailGallery._onScroll = () => {
    const w = track.clientWidth || 1;
    const idx = Math.round(track.scrollLeft / w);
    thumbs.forEach((t, i) => t.classList.toggle("on", i === idx));
    det.photoIdx = idx;
  };
  bindDetailGallery._track = track;
  track.addEventListener("scroll", bindDetailGallery._onScroll, { passive: true });
  thumbs.forEach((t) => {
    t.onclick = () => setIdx(Number(t.dataset.i) || 0);
  });
  const zoom = $("detailZoom");
  const urls = images.map((im) => thumb(im.url, 1600)).filter(Boolean);
  const openLb = (idx) => {
    if (!urls.length) return;
    det.photoIdx = idx || 0;
    openLightbox(urls, idx || 0);
  };
  if (zoom) zoom.onclick = (ev) => {
    ev.stopPropagation();
    if (isDetailEbaySeg(det)) openHeroPhotoEdit(det);
    else openLb(det.photoIdx || 0);
  };
  if (det) det.heroImages = images;
  bindHeroPhotoClicks(det, images);
}

function isDetailEbaySeg(det) {
  return (det && det.seg) === "sell";
}

function heroSourcePhotoIdx(det) {
  const images = (det && det.heroImages) || [];
  const idx = (det && typeof det.photoIdx === "number") ? det.photoIdx : 0;
  const im = images[idx];
  if (!im || im.kind === "design") return 0;
  let n = 0;
  for (let i = 0; i < idx; i++) {
    if (!images[i] || images[i].kind !== "design") n++;
  }
  return n;
}

function openHeroPhotoEdit(det) {
  const item = det && det.mode === "item" ? det.data : null;
  const d = det && det.data && det.data.draft;
  const idx = heroSourcePhotoIdx(det);
  if (d) openDraftPhotoMenu(d, idx);
  else if (item) openItemPhotoMenu(item);
}

function bindHeroPhotoClicks(det, images) {
  const track = $("detailGalleryTrack") || document.querySelector(".d-gallery-track");
  const gal = $("detailGallery");
  if (!track) return;
  const ebay = isDetailEbaySeg(det);
  if (gal) gal.classList.toggle("is-ebay", ebay);
  const item = det && det.mode === "item" ? det.data : null;
  if (item && gal) gal.style.setProperty("--listing-bg", listingBgCss(item));
  const urls = (images || []).map((im) => thumb(im.url, 1600)).filter(Boolean);
  track.querySelectorAll("img").forEach((img, idx) => {
    img.style.cursor = ebay ? "pointer" : "zoom-in";
    img.onclick = (ev) => {
      ev.stopPropagation();
      if (det) det.photoIdx = idx;
      if (ebay) openHeroPhotoEdit(det);
      else if (urls.length) openLightbox(urls, idx);
    };
  });
}

function showDetailSeg(det, seg) {
  if (!det) return;
  const wantListing = seg === "sell" || seg === "ebay";
  det.seg = wantListing ? "sell" : "overview";
  det.showListing = wantListing;
  renderDetail(det);
}

function hideDetailCtaDock() {
  const dock = $("detailCtaDock");
  const root = $("detail");
  if (dock) {
    dock.hidden = true;
    dock.innerHTML = "";
  }
  if (root) root.classList.remove("has-cta-dock");
}

function syncDetailCtaDock(det) {
  const dock = $("detailCtaDock");
  const root = $("detail");
  if (!dock || !root) return;
  const item = det && det.mode === "item" ? det.data : null;
  if (!item || root.hidden || det.showListing) {
    hideDetailCtaDock();
    return;
  }
  dock.innerHTML = `<button type="button" class="btn-primary d-ebay-cta" id="btnList" aria-label="${esc(L("Einstellen"))}">
      <span class="d-cta-lab">${esc(L("Einstellen"))}</span>
    </button>
  <p class="d-cta-sub">${esc(L("über eBay"))}</p>`;
  dock.hidden = false;
  root.classList.add("has-cta-dock");
  const btn = dock.querySelector("#btnList");
  if (btn) {
    btn.onclick = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (state._skipEnsureDraft) delete state._skipEnsureDraft[item.id];
      /* aaaa.md: Einstellen wechselt auf eBay-Tab. Nicht-verbunden lebt im Pane,
         nicht als Extra unter den Notizen. */
      showDetailSeg(det, "sell");
      if (!ebayConnectedNow()) return;
      startListingPrep(item, btn);
    };
  }
}

function paintDetailSeg(det) {
  const onSell = !!(det && (det.showListing || det.seg === "sell"));
  const ov = document.querySelector('#detailPanes [data-pane="overview"]');
  const sl = document.querySelector('#detailPanes [data-pane="sell"]');
  if (ov) ov.hidden = onSell;
  if (sl) sl.hidden = !onSell;
  document.querySelectorAll("#detailSeg [data-dseg]").forEach((b) => {
    const on = (b.dataset.dseg === "sell") === onSell;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
  });
}
function bindDetailSegTabs(det) {
  document.querySelectorAll("#detailSeg [data-dseg]").forEach((b) => {
    b.onclick = () => showDetailSeg(det, b.dataset.dseg);
  });
}

function bindDetailPaneSwipe(det) {
  const el = $("detailPanes") || $("detailBody");
  if (!el) return;
  if (bindDetailPaneSwipe._el) {
    bindDetailPaneSwipe._el.removeEventListener("touchstart", bindDetailPaneSwipe._start);
    bindDetailPaneSwipe._el.removeEventListener("touchend", bindDetailPaneSwipe._end);
  }
  let x0 = 0, y0 = 0, ok = false;
  bindDetailPaneSwipe._start = (e) => {
    if (!e.touches || e.touches.length !== 1) return;
    const t = e.touches[0];
    if (t.clientX < 20) { ok = false; return; }
    const gal = e.target.closest && e.target.closest(".d-gallery-main, .d-gallery-thumbs, .d-hero");
    if (gal) { ok = false; return; }
    x0 = t.clientX; y0 = t.clientY; ok = true;
  };
  bindDetailPaneSwipe._end = (e) => {
    if (!ok) return;
    ok = false;
    const t = (e.changedTouches && e.changedTouches[0]) || null;
    if (!t) return;
    const dx = t.clientX - x0, dy = t.clientY - y0;
    if (Math.abs(dx) < 56 || Math.abs(dx) < Math.abs(dy) * 1.3) return;
    if (dx < 0 && (det.seg || "overview") === "overview") showDetailSeg(det, "sell");
    else if (dx > 0 && det.seg === "sell") showDetailSeg(det, "overview");
  };
  bindDetailPaneSwipe._el = el;
  el.addEventListener("touchstart", bindDetailPaneSwipe._start, { passive: true });
  el.addEventListener("touchend", bindDetailPaneSwipe._end, { passive: true });
}

function seroPriceCardHtml(item) {
  const SD = seroDetailApi();
  const m = SD ? SD.priceCardModel(item) : { label: "Wert unbekannt", showValue: false, hint: "Noch keine verlässliche Preisschätzung" };
  const valTxt = m.showValue ? money(m.value) : L("Wert unbekannt");
  const range = (m.range && m.showValue)
    ? `<span class="d-pc-range">${money(m.range.low)} – ${money(m.range.high)}</span>` : "";
  const conf = m.confidenceLabel
    ? `<div class="d-pc-row"><span>${esc(L("Konfidenz"))}</span>
        <span class="d-pc-conf d-pc-${esc(m.confidence || "")}">${esc(L(m.confidenceLabel))}
          <i class="d-pc-dots" data-n="${m.dots || 0}"><i></i><i></i><i></i></i></span></div>`
    : "";
  const meta = [];
  if (m.compsCount) meta.push(LF("{0} Vergleiche", m.compsCount));
  if (m.updated) {
    const d = new Date(m.updated * 1000);
    if (!isNaN(d)) meta.push(d.toLocaleDateString("de-DE", { day: "numeric", month: "short" }));
  }
  const reason = (item.price_state && item.price_state !== "belegt" && PREIS_GRUENDE[item.price_reason])
    ? `<p class="d-pc-hint">${esc(L(PREIS_GRUENDE[item.price_reason]))}</p>` : "";
  const hint = (!m.showValue && m.hint) ? `<p class="d-pc-hint">${esc(L(m.hint))}</p>` : "";
  return `<section class="d-card" id="seroPriceCard">
    <div class="d-card-h">${esc(L("Marktwert"))}</div>
    <div class="d-pc-row"><span>${esc(L(m.label))}</span><span class="d-pc-val">${valTxt}${range}</span></div>
    ${conf}${hint}${reason}
    ${meta.length ? `<p class="d-pc-meta">${esc(meta.join(" · "))}</p>` : ""}
  </section>`;
}

function seroNotesHtml(item) {
  const SD = seroDetailApi();
  const n = SD ? SD.notesModel(item) : { sections: [], facts: [], sources: [], disclaimer: null };
  const secs = (n.sections || []).map((s) => `
    ${s.heading ? `<div class="d-notes-k">${esc(L(s.heading))}</div>` : ""}
    <p class="d-notes-p${s.id === "title" ? " d-notes-title" : ""}">${esc(L(s.body))}</p>`).join("");
  const facts = (n.facts || []).length
    ? `<div class="d-notes-k">${esc(L("Kerndaten"))}</div>
       <div class="d-facts">${n.facts.map((f) =>
         `<span class="d-fact"><i></i>${esc(L(f.label))}: ${esc(f.value)}</span>`).join("")}</div>`
    : "";
  const src = (n.sources || []).length
    ? `<div class="d-notes-k">${esc(L("Quellen"))}</div>
       <div class="d-sources">${n.sources.map((s) =>
         `<a class="d-src" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}${icon("link", 12)}</a>`
       ).join("")}</div>`
    : "";
  const disc = n.disclaimer ? `<p class="d-notes-disc">${esc(L(n.disclaimer))}</p>` : "";
  return `<section class="d-card d-notes open" id="detailNotes">
    <button type="button" class="d-notes-h" id="notesToggle">
      <span>${icon("note", 16)} ${esc(L("Notizen"))}</span>
      <span class="d-notes-chev">${icon("chevdown", 16)}</span>
    </button>
    <div class="d-notes-b">${secs}${facts}${src}${disc}</div>
  </section>`;
}

function seroDetailsHtml(item) {
  const SD = seroDetailApi();
  const chips = SD ? SD.detailChips(item) : [];
  if (!chips.length) return "";
  return `<section class="d-card" id="detailFacts">
    <div class="d-card-h">${esc(L("Details"))}</div>
    <div class="d-attr">${chips.map((c) =>
      `<span class="d-chip">${esc(L(c.label))}: ${esc(c.value)}</span>`).join("")}</div>
  </section>`;
}

function overviewHeroHtml(item, images) {
  const SD = seroDetailApi();
  const view = SD ? SD.detailView(item) : { title: item.name || "", images: [], owner: "Du" };
  images = images || view.images || [];
  const pills = [];
  pills.push(`<span class="d-pill">${icon("person", 13)} ${esc(L(view.owner || "Du"))}</span>`);
  if (view.grader && view.grade) {
    const g = item.graded || {};
    const seal = gradeSeal(g, item.name);
    pills.push(`<span class="d-pill">${esc(seal.text || (view.grader + " " + view.grade))}</span>`);
  }
  if (view.cert) pills.push(`<span class="d-pill">${esc((view.grader || "PSA") + ": " + view.cert)}</span>`);
  const qty = Number(item.quantity);
  if (Number.isFinite(qty) && qty > 0) {
    pills.push(`<span class="d-pill">${esc(LF("{0} Stück", qty))}</span>`);
  }
  return `<div class="d-hero" id="detailHero">
    <h1 class="d-hero-title" id="detailHeroTitle">${esc(view.title || L("Stück"))}</h1>
    <div class="d-pills">${pills.join("")}</div>
    <div class="d-gallery" id="detailGallery" style="--listing-bg:${esc(listingBgCss(item))}">
      <div class="d-gallery-main" id="detailGalleryMain">
        <div class="d-gallery-track" id="detailGalleryTrack">${galleryTrackHtml(images)}</div>
        <button type="button" class="d-gallery-zoom" id="detailZoom" aria-label="${esc(L("Vergrößern"))}">${icon("expand", 18)}</button>
      </div>
      <div class="d-gallery-thumbs" id="detailGalleryThumbs">${galleryThumbsHtml(images)}</div>
    </div>
  </div>`;
}

function openItemMoreMenu(item, det) {
  openSheet(L("Mehr"), "", `
    <div class="opt-list">
      <button type="button" class="opt" id="optMorePhotos"><span style="display:flex;align-items:center;gap:10px">${icon("photo", 17)} ${L("Fotos")}</span></button>
      <button type="button" class="opt" id="priceRefresh"><span style="display:flex;align-items:center;gap:10px">${icon("refresh", 17)} ${L("Preis aktualisieren")}</span></button>
      <button type="button" class="opt" id="alertBtn"><span style="display:flex;align-items:center;gap:10px">${icon("bell", 17)} ${L("Preisalarm")}</span></button>
      <button type="button" class="opt" id="optMoreDel" style="color:var(--red)"><span style="display:flex;align-items:center;gap:10px">${icon("trash", 17)} ${L("Stück entfernen")}</span></button>
    </div>`, { hideActions: true, recede: false, fit: true });
  const ph = $("optMorePhotos");
  if (ph) ph.onclick = (ev) => { ev.preventDefault(); ev.stopPropagation(); closeSheet(); openItemPhotoMenu(item); };
  const del = $("optMoreDel");
  if (del) del.onclick = (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    askRemoveItem(item);
  };
  const pr = $("priceRefresh");
  if (pr) pr.onclick = async () => {
    closeSheet();
    try {
      const res = await post(`/api/app/collection/item/${item.id}/refresh-price`, {}, { timeout: 180000 });
      if (res && res.job_id) toast(L("Preisermittlung läuft"), "check");
      else toast(L("Preis aktualisiert"), "check");
      refreshDetail(true);
    } catch (e) { toast(e.message); }
  };
  const ab = $("alertBtn");
  if (ab) ab.onclick = () => { closeSheet(); openAlertSheet(item, det && det.data && det.data.alert); };
}

function closeDetail(opts) {
  opts = opts || {};
  const d = $("detail");
  clearTimeout(state.detail?.poll);
  state.detail = null;
  try { holoCtl.deactivate(); } catch (_) { /* */ }
  hideDetailCtaDock();
  d.classList.add("closing");
  const reopenBulk = (state._bulkReviewIds || []).slice();
  const finish = () => {
    if (state.detail) return;
    d.hidden = true;
    d.classList.remove("closing");
    $("detailBody").innerHTML = "";
    hideDetailCtaDock();
    if (!opts.skipReload) {
      loadCollection(); loadSales();
    }
    if (!$("tabHome").hidden) loadDashboard({ background: true });
    else state._dashStale = true;
    if (reopenBulk.length && typeof openBulkReviewSheet === "function") {
      setTimeout(() => openBulkReviewSheet(reopenBulk), 80);
    }
  };
  if (opts.instant) {
    finish();
    return;
  }
  setTimeout(finish, 280);
}
$("detailClose").onclick = closeDetail;

async function openItemDetail(itemId, seg = "overview") {
  const pane = (seg === "sell" || seg === "ebay") ? "sell" : "overview";
  const showListing = seg === "sell" || seg === "ebay";
  state.detail = { mode: "item", id: itemId, data: null, poll: null, seg: "overview", showListing };
  $("detail").classList.remove("closing");
  $("detail").hidden = false;
  $("detailTitle").textContent = "";
  // Sofort aus dem Sammlungs-Cache zeichnen — kein Warten, kein Skeleton;
  // die frischen Daten (Verlauf, Verkäufe, Listing) laufen gleich hinterher
  const cached = state.items.find((x) => x.id === itemId);
  if (cached) {
    state.detail.data = cached;
    renderDetail(state.detail);
  } else {
    $("detailBody").innerHTML = skel(220, 16) + `<div style="height:14px"></div>` + skel(120);
  }
  if (isGuestItemId(itemId) || (isGuest() && cached)) return;
  await refreshDetail(true);
}

async function openDraftDetail(draftId) {
  state.detail = { mode: "draft", id: draftId, data: null, poll: null };
  $("detail").classList.remove("closing");
  $("detail").hidden = false;
  $("detailTitle").textContent = "Listing";
  $("detailBody").innerHTML = skel(220, 16);
  await refreshDetail(true);
}

async function refreshDetail(force = false) {
  const opts = (force && typeof force === "object") ? force : { force: !!force };
  const det = state.detail;
  if (!det) return;
  clearTimeout(det.poll);
  const ticket = detailWins.begin();
  let data;
  try {
    data = det.mode === "item"
      ? await api(`/api/app/collection/item/${det.id}`, { signal: ticket.signal })
      : { draft: await api(`/api/app/draft/${det.id}`, { signal: ticket.signal }) };
  } catch (e) {
    if (e.superseded || !ticket.isCurrent()) return;
    if (sheetIsOpen()) { toast(e.message); return; }
    $("detailBody").innerHTML = `<div class="err-box">${esc(e.message)}</div>`;
    return;
  }
  if (!ticket.isCurrent() || state.detail !== det) return;
  // Erfolgs-Moment NUR beim echten Übergang Entwurf -> live (nicht bei jedem
  // Öffnen eines längst gelisteten Stücks — das feierte sich bisher selbst)
  const prevPub = det.data?.draft?.published;
  if (det.data && prevPub === false && data.draft?.published) celebrate(data.draft);
  const dFresh = data.draft;
  if (dFresh && state.draftBusy && state.draftBusy[dFresh.id || det.id]) {
    const id = dFresh.id || det.id;
    const started = state.draftBusy[id];
    const age = Date.now() - (typeof started === "number" ? started : 0);
    const uploading = dFresh.status === "publishing"
      || (dFresh.stage && !dFresh.stage.done);
    const fertig = ["published", "ended", "dry_run_done", "error", "publish_uncertain"]
      .includes(dFresh.status);
    // Kurz nach Tipp noch „ready": Server hat publishing noch nicht geschrieben —
    // Busy nicht sofort löschen (sonst springen Festpreis/Auktion wieder frei).
    if (fertig || (!uploading && age > 2500)) delete state.draftBusy[id];
  }
  const json = JSON.stringify(data);
  const listKey = listingPaintKey(data);
  if (opts.force || json !== det.rendered) {
    const st = captureDetailViewState(det);
    const prevList = det._listingPaint;
    det.data = data;
    det.rendered = json;
    det._listingPaint = listKey;
    if (listingInputBusy()) {
      state._detailPaintQueued = true;
    } else {
      const keep = !opts.full && ($("detailPanes") || $("detailHero"));
      const listingChanged = !!opts.force || listKey !== prevList;
      if (keep && !listingChanged && det.showListing) {
        /* Cutout/Analyse-Ticks: Listing-DOM stehen lassen, sonst stirbt der Tipp. */
      } else if (keep) {
        renderDetail(det, {
          preserve: true,
          ebayOnly: !!opts.ebayOnly || !!(det.showListing && listingChanged),
        });
      } else {
        renderDetail(det);
      }
      restoreDetailViewState(det, st);
    }
  }
  const d = data.draft;
  const busy = (det.mode === "item" && (data.status === "analyzing" || data.cutout_status === "running"))
    || (d && (["downloading", "analyzing", "publishing"].includes(d.status)
              || d.render_busy
              || (d.stage && !d.stage.done)
              || (state.draftBusy && state.draftBusy[d.id || det.id])));
  if (busy) det.poll = setTimeout(() => refreshDetail(), 1600);
}

/* ── Ehrlicher Preiszustand (Stufe 5) ──────────────────────────────────────
   Die Zahl bleibt immer da — aber „Marktwert" heißt nur, was belegt ist.
   spanne = Richtwert (Angebote oder alte Belege), unbekannt = Schätzung. */
function wertTitel(item) {
  if (item.est_value === null || item.est_value === undefined) return L("Wert unbekannt");
  if (item.price_state === "eigener_wert" || item.price_source === "manual") return L("Eigener Wert");
  if (item.price_source === "estimate" || item.price_reason === "KI_RICHTWERT") return L("Richtwert");
  const pc = item.price_class;
  if (pc === "EXACT_SOLD") return L("Marktwert");
  if (pc === "ESTIMATED_SOLD") return L("Marktwert (Schätzung)");
  if (pc === "GUIDE_VALUE") return L("Katalogwert");
  if (pc === "RAW_MARKET") return L("Rohkarten-Marktwert");
  if (pc === "ASKING_ONLY") return L("Angebotspreis");
  if (pc === "NO_MARKET_DATA") return L("Wert unbekannt");
  if (item.price_state === "unbekannt") return L("Richtwert");
  if (item.price_state === "spanne") return L("Marktwert (Richtwert)");
  return L("Marktwert");
}

const PREIS_GRUENDE = {
  ROHPREIS_SLAB: "Preis der ungegradeten Karte — der Slab-Aufschlag fehlt noch.",
  BELEGE_ALT: "Belege älter als 90 Tage — Karten-Märkte drehen schnell.",
  NUR_ANGEBOTE: "Aus aktiven Angeboten, noch kein belegter Verkauf.",
  KI_RICHTWERT: "Unsicherer Richtwert — bitte prüfen und bei Bedarf manuell ändern.",
  UNBEKANNT_ZUORDNUNG: "Preisquelle passt nicht sicher zum Stück.",
  UNBEKANNT_WIDERSPRUCH: "Die Quellen widersprechen sich zu stark.",
  UNBEKANNT_KEINE_BELEGE: "Keine belastbaren Vergleichsdaten. Beim Listen trägst du deinen Preis selbst ein — findet SERO später Belege, übernimmt es sie.",
};

/* ── Angebotslage: drei Märkte, ein Umschalter ─────────────────────────────
   Die Daten kommen je Markt einzeln vom Server (6-h-Cache dort, eBay-Auflage)
   und werden am det-Objekt zwischengehalten, damit der Poll-Refresh des
   Detailfensters keinen erneuten Abruf auslöst. */
const usdFmt = (v) => v === null || v === undefined ? "—"
  : Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " $";

function offersHtml(o) {
  if (o === undefined) return skel(72, 12);
  if (!o || o.fehler) {
    return `<div class="irow"><span class="ric" style="background:var(--icon-neutral)">${icon("photo", 15)}</span>
      <span class="rlabel" style="color:var(--label-2)">${esc(o && o.fehler || L("Gerade nicht abrufbar — tipp den Umschalter gleich noch einmal."))}</span></div>`;
  }
  const inUsd = o.currency === "USD";
  const fmt = inUsd ? usdFmt : money;
  let kopf;
  if (!o.count) {
    kopf = `<span class="rlabel" style="color:var(--label-2)">${L("Auf diesem Markt ist gerade nichts im Angebot.")}</span>`;
  } else if (o.solid) {
    kopf = `<span class="rlabel">${LF("Median {0}", fmt(o.median))}${inUsd && o.median_eur ? ` <i class="offer-eur">≈ ${money(o.median_eur)}</i>` : ""}</span>
      <span class="rvalue" style="color:var(--label-2)">${LF("{0} Angebote", o.count)}</span>`;
  } else {
    kopf = `<span class="rlabel" style="color:var(--label-2)">${LF("Nur {0} Angebote — zu wenige für einen belastbaren Median", o.count)}</span>`;
  }
  const zeilen = (o.samples || []).map((sm) => `
    <a class="irow tap sample" ${sm.url ? `href="${esc(sm.url)}" target="_blank" rel="noopener"` : ""}>
      ${sm.image ? `<img class="simg" src="${esc(sm.image)}" loading="lazy" alt="">`
                 : `<span class="ric" style="background:var(--icon-neutral)">${icon("photo", 15)}</span>`}
      <span class="rlabel sample-t">${esc(sm.title)}</span>
      <span class="rvalue" style="color:var(--label);font-weight:650">${fmt(sm.price)}</span>
      <span class="chev">${icon("link", 13)}</span>
    </a>`).join("");
  return `<div class="ilist"><div class="irow">${kopf}</div>${zeilen}</div>`;
}

function fuelleOffers(det, item) {
  const box = $("offersBox");
  if (!box) return;
  const m = det.offersMarket || "eu";
  det.offers = det.offers || {};
  // EU startet mit dem, was das Stück schon mitbringt — kein Extra-Abruf
  if (m === "eu" && det.offers.eu === undefined && item.market && !item.market.estimated) {
    det.offers.eu = { ...item.market, currency: "EUR",
                      solid: (item.market.count || 0) >= 5 };
  }
  box.innerHTML = offersHtml(det.offers[m]);
  if (det.offers[m] !== undefined) return;
  api(`/api/app/collection/item/${item.id}/offers?market=${m}`)
    .then((o) => {
      det.offers[m] = o;
      if (state.detail === det && (det.offersMarket || "eu") === m) fuelleOffers(det, item);
    })
    .catch((e) => {
      det.offers[m] = { fehler: e.message };
      if (state.detail === det && (det.offersMarket || "eu") === m) fuelleOffers(det, item);
      delete det.offers[m];   // Fehler nicht einfrieren — nächster Tipp probiert neu
    });
}

function renderDetail(det, opts) {
  opts = opts || {};
  const body = $("detailBody");
  if (!det || !det.data) {
    const retryId = "detRetry" + Math.random().toString(36).slice(2, 8);
    body.innerHTML = `<div class="stage-line"><span class="spinner"></span> ${esc(L("Wird geladen …"))}</div>
      <button class="btn-secondary" id="${retryId}" style="margin:16px auto;display:block">${esc(L("Erneut laden"))}</button>`;
    const rb = $(retryId);
    if (rb) rb.onclick = () => refreshDetail(true);
    hideDetailCtaDock();
    return;
  }
  try { return _renderDetail(det, opts, body); }
  catch (e) {
    console.error("renderDetail error", e);
    const retryId = "detRetry" + Math.random().toString(36).slice(2, 8);
    body.innerHTML = `<div class="err-box">${esc(String(e && e.message || e))}</div>
      <button class="btn-secondary" id="${retryId}" style="margin:16px auto;display:block">${esc(L("Erneut laden"))}</button>`;
    const rb = $(retryId);
    if (rb) rb.onclick = () => refreshDetail(true);
    hideDetailCtaDock();
  }
}
function _renderDetail(det, opts, body) {
  const item = det.mode === "item" ? det.data : null;
  const d = (det.data && det.data.draft) || null;

  $("detailTitle").textContent = item ? "" : "Listing";
  $("detailTrash").hidden = true;
  $("detailFav").hidden = !item;
  const shareBtn = $("detailShare");
  if (shareBtn) {
    shareBtn.hidden = !item;
    shareBtn.onclick = item ? () => shareItem(item) : null;
  }
  const moreBtn = $("detailMore");
  if (moreBtn) {
    moreBtn.hidden = !item;
    moreBtn.onclick = () => openItemMoreMenu(item, det);
  }
  if (item) {
    $("detailFav").innerHTML = icon(item.favorite ? "starfill" : "star", 18);
    $("detailFav").style.color = item.favorite ? "#f5a623" : "";
    $("detailFav").onclick = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const next = !item.favorite;
      item.favorite = next;
      $("detailFav").innerHTML = icon(next ? "starfill" : "star", 18);
      $("detailFav").style.color = next ? "#f5a623" : "";
      const cached = (state.items || []).find((x) => x.id === item.id);
      if (cached) cached.favorite = next;
      post(`/api/app/collection/item/${item.id}`, { favorite: next })
        .catch((e) => {
          item.favorite = !next;
          $("detailFav").innerHTML = icon(item.favorite ? "starfill" : "star", 18);
          $("detailFav").style.color = item.favorite ? "#f5a623" : "";
          if (cached) cached.favorite = !next;
          toast(e.message);
        });
    };
    $("detailTrash").onclick = () => askRemoveItem(item);
    const dup = document.querySelector(".dup-hint[data-dup]");
    if (dup) dup.onclick = () => openItemDetail(dup.dataset.dup);
  }

  const seg = det.seg || "overview";
  const showListing = !!det.showListing || seg === "sell";
  const heroImgs = item ? detailGalleryImages(item, showListing) : [];
  const photoUrls = item ? (heroImgs.map((im) => thumb(im.url, 1600)))
    : (d ? d.photos.map((p) => p.url).filter(Boolean) : []);
  const isCard = !!(item && item.card);
  const photos = photoUrls.map((u) =>
    isCard ? `<span class="holo-wrap"><img src="${esc(u)}" loading="lazy" alt=""></span>`
           : `<img src="${esc(u)}" loading="lazy" alt="">`).join("");

  let html = "";
  if (item) {
    html += overviewHeroHtml(item, heroImgs);
    if (item.cutout_status === "error") {
      html += `<p class="d-cutout-chrome d-cutout-err" id="cutoutChrome">${esc(item.cutout_error || L("Freistellen fehlgeschlagen — Original bleibt."))}
        <button type="button" class="btn-plain" id="btnCutoutRetry">${esc(L("Nochmal freistellen"))}</button></p>`;
    }
  }
  if (!item && photos) {
    html += `<div class="d-photos large">${photos}</div>`;
  }

  let overviewPane = "";
  if (item) {
    if (item.status === "analyzing" || item.cutout_status === "running") {
      overviewPane += `<div class="stage-line"><span class="spinner"></span> ${esc(item.status_text || (item.cutout_status === "running" ? L("Stelle Karte frei …") : L("Wird analysiert …")))}</div>`;
    }
    /* Freistell-Fehler sitzt als graue Chrome-Zeile unter den Thumbs, nicht hier. */
    if (item.error) overviewPane += `<div class="err-box">${esc(item.error)}</div>`;
    if (item.dublette) {
      overviewPane += `<div class="dup-hint" data-dup="${esc(item.dublette.id)}">
        ${icon("copies", 15)}
        <span>${LF("Dieses Stück hast du schon einmal in der Sammlung: {0}", esc(item.dublette.name))}</span>
        <b>${L("Ansehen")}</b></div>`;
    }
    overviewPane += seroPriceCardHtml(item);
    overviewPane += seroNotesHtml(item);
    overviewPane += seroDetailsHtml(item);
  }

  const hasLocalPhotos = item && (item.photos || []).some((p) => String(p).startsWith("/api/app/citem-photo"));
  const listCta = `<button class="btn-primary" id="btnListPrep">${icon("arrowup", 18)}<span>${L("eBay-Entwurf vorbereiten")}</span></button>
    <p class="v-sub" style="display:block;margin-top:10px;color:var(--label-2);font-size:13px">
      ${L("Im nächsten Schritt prüfst du Preis, Titel und Zustand — live geht es erst nach deiner Freigabe.")}</p>`;
  const noPhotosHint = `<div class="err-box" style="color:var(--label-2);background:var(--fill)">
      Für dieses Stück liegen keine eigenen Fotos mehr vor — zum Listen bitte einmal neu
      fotografieren (Scanner) und das alte Stück entfernen.</div>`;
  const sellPreparing = `<div class="stage-line"><span class="spinner"></span> ${esc(L("Listing wird vorbereitet …"))}</div>
    <p class="v-sub" style="display:block;margin-top:10px;color:var(--label-2);font-size:13px">
      ${L("Titel, Beschreibung, Kategorie und Preis werden vorausgefüllt — danach kannst du alles prüfen und listen.")}</p>`;

  let ebayPane = "";
  if (item) {
    ebayPane += `<div class="ebay-design-kicker d-ebay-kicker"><span>${esc(L("Listing-Design"))}</span>
      <button type="button" class="d-ebay-photos" id="ebayPhotoEdit">${esc(L("Bilder bearbeiten"))}</button>
      <span class="d-ebay-hint">${esc(L("Tipp aufs Bild zum Bearbeiten"))}</span></div>`;
    if (d) ebayPane += renderDraftSection(d, { hidePhotos: true, cards: true, item });
    else if (!hasLocalPhotos) ebayPane += noPhotosHint;
    else if (!ebayConnectedNow()) {
      ebayPane += `<div class="lr-prep-fail">
        <p>${esc(L("eBay ist nicht verbunden"))}</p>
        <button type="button" class="btn-primary" id="btnEbayConnectHint">${esc(L("eBay verbinden"))}</button>
      </div>`;
    } else if (state._listingPrepError && state._listingPrepError.itemId === item.id) {
      ebayPane += `<div class="lr-prep-fail">
        <p>${esc(L("Listing-Vorbereitung fehlgeschlagen — erneut versuchen"))}</p>
        ${state._listingPrepError.message ? `<p class="v-sub">${esc(state._listingPrepError.message)}</p>` : ""}
        <button type="button" class="btn-primary" id="btnListPrep">${esc(L("Erneut versuchen"))}</button>
      </div>`;
    } else if (state._listingPrepBusy && state._listingPrepId === item.id) ebayPane += sellPreparing;
    else ebayPane += listCta;
  } else {
    html += `<div class="section-label">eBay</div>`;
    html += d ? renderDraftSection(d) : "";
  }
  if (item) {
    const onSell = showListing;
    html += `<div class="d-seg" id="detailSeg" role="tablist">
      <button type="button" role="tab" data-dseg="overview" class="${onSell ? "" : "on"}" aria-selected="${onSell ? "false" : "true"}">${esc(L("Info"))}</button>
      <button type="button" role="tab" data-dseg="sell" class="${onSell ? "on" : ""}" aria-selected="${onSell ? "true" : "false"}">${esc(L("eBay"))}</button>
    </div>
    <div class="d-panes" id="detailPanes">
      <div class="d-pane" data-pane="overview"${onSell ? " hidden" : ""}>${overviewPane}</div>
      <div class="d-pane" data-pane="sell"${onSell ? "" : " hidden"}>
        <div class="d-listing-block" id="detailListingBlock">${ebayPane}</div>
      </div>
    </div>`;
  }

  const keepShell = !!(opts && opts.preserve && item && $("detailPanes") && $("detailHero")
    && det._shellItemId === item.id);
  const skipListingPaint = listingInputBusy();
  if (skipListingPaint) state._detailPaintQueued = true;
  if (keepShell) {
    if (skipListingPaint) {
      /* Aktives Eingabefeld nicht remounten (iOS-Tastatur). */
    } else if (opts && opts.ebayOnly) {
      const block = $("detailListingBlock");
      if (block) {
        block.innerHTML = ebayPane;
      } else {
        const sl = document.querySelector('#detailPanes [data-pane="sell"]');
        if (sl) sl.innerHTML = `<div class="d-listing-block" id="detailListingBlock">${ebayPane}</div>`;
      }
    } else {
      const ov = document.querySelector('#detailPanes [data-pane="overview"]');
      const sl = document.querySelector('#detailPanes [data-pane="sell"]');
      if (ov) ov.innerHTML = overviewPane;
      if (sl) sl.innerHTML = `<div class="d-listing-block" id="detailListingBlock">${ebayPane}</div>`;
    }
    const ht = $("detailHeroTitle");
    if (ht) {
      const SD = seroDetailApi();
      const view = SD ? SD.detailView(item) : { title: item.name || "" };
      ht.textContent = view.title || L("Stück");
    }
  } else if (skipListingPaint && item && $("detailPanes") && body.innerHTML.trim()) {
    /* Input focused — defer repaint, but only when body already has content. */
  } else {
    body.innerHTML = html;
    det._shellItemId = item ? item.id : null;
    det._heroSig = item ? detailHeroSignature(item, seg) : "";
  }

  const skipHeroBind = (keepShell && opts && opts.ebayOnly) || skipListingPaint;
  if (!skipHeroBind) {
    if (item) {
      bindDetailScrollTitle(item.name || "");
      bindDetailGallery(heroImgs, det);
    } else {
      bindDetailScrollTitle("");
    }
    bindDetailPaneSwipe(det);
  }
  bindDetailSegTabs(det);
  paintDetailSeg(det);
  const nt = $("notesToggle");
  if (nt) nt.onclick = () => {
    const box = $("detailNotes");
    if (box) box.classList.toggle("open");
  };

  if (item) {
    wireRow("i-name", () => openInput({
      title: "Name", hint: "So erscheint das Stück in deiner Sammlung und später im Listing.",
      value: item.name || "",
    }, (v) => patchItem(item.id, { name: v })));
    const bcs = $("btnCardSearch");
    if (bcs) bcs.onclick = () => openCardSearch(item);
    wireRow("i-cat", () => openOptions("Kategorie", CATEGORIES.map((c) => ({
      label: catUiLabel(c), value: c, sel: item.category === c,
    })), (v) => patchItem(item.id, { category: v })));
    wireRow("i-cond", () => {
      if (isCardCategory(item.category)) {
        openOptions("Zustand", [
          { label: "Nicht bewertet (Ungraded)", value: "USED_VERY_GOOD",
            sel: item.condition !== "LIKE_NEW" && item.condition !== "Professionell bewertet (Graded)"
              && item.condition !== "GRADED" },
          { label: "Professionell bewertet (Graded)", value: "LIKE_NEW",
            sel: item.condition === "LIKE_NEW" || item.condition === "Professionell bewertet (Graded)"
              || item.condition === "GRADED" },
        ], (v) => patchItem(item.id, { condition: v }));
      } else {
        openInput({
          title: "Zustand", hint: "z. B. Neu · Neuwertig · Gebraucht — sehr gut · Near Mint",
          value: condLabel(item.condition, item.category) === "—" ? ""
            : condLabel(item.condition, item.category),
        }, (v) => patchItem(item.id, { condition: v }));
      }
    });
    wireRow("i-qty", () => openStepper(item.quantity, (v) => patchItem(item.id, { quantity: v })));
    wireRow("i-paid", () => openInput({
      title: "Kaufpreis", hint: "Was hast du bezahlt? (leer lassen zum Entfernen)",
      value: eur(item.purchase_price) || "", mode: "decimal", ph: "12,50",
    }, (v) => patchItem(item.id, { purchase_price: v })));
    wireRow("i-notes", () => openInput({
      title: L("Notiz"), hint: L("Notiz (optional)"),
      value: item.notes || "",
    }, (v) => patchItem(item.id, { notes: v })));
    const favSw = $("favSw");
    if (favSw) favSw.onchange = () =>
      post(`/api/app/collection/item/${item.id}`, { favorite: favSw.checked })
        .then(() => refreshDetail(true)).catch((e) => { toast(e.message); favSw.checked = !favSw.checked; });
    const wsw = $("wishSw");
    if (wsw) wsw.onchange = () =>
      post(`/api/app/collection/item/${item.id}`, { wishlist: wsw.checked })
        .then(() => refreshDetail(true)).catch((e) => { toast(e.message); wsw.checked = !wsw.checked; });
    const ab = $("alertBtn");
    if (ab) ab.onclick = () => openAlertSheet(item, det.data.alert);
    const pc = $("seroPriceCard");
    if (pc) {
      pc.classList.add("price-tap");
      pc.onclick = () => openInput({
        title: L("Preis selbst setzen"),
        hint: L("Dein Portfolio-Wert für dieses Stück. Leer lassen löscht den manuellen Wert."),
        value: item.price_source === "manual" && item.est_value != null
          ? eur(item.est_value) : (eur(item.est_value) || ""),
        mode: "decimal", ph: "25,00",
      }, async (v) => {
        await patchItem(item.id, { est_value: v });
        toast(v.trim() ? L("Preis gesetzt") : L("Manueller Preis entfernt"), "check");
      });
    }
    const pi = $("priceInfo");
    if (pi) pi.onclick = () => {
      const [t, txt] = SOURCE_INFO[item.price_source] || ["Marktwert", "Automatisch ermittelter Schätzwert."];
      openSheet(`Woher kommt dieser Preis?`, "", `<p class="sheet-hint" style="font-size:15px;line-height:1.55;margin:0"><b>${esc(t)}:</b> ${esc(txt)}</p>`, null);
    };
    const cutRetry = $("btnCutoutRetry");
    if (cutRetry) cutRetry.onclick = () => freistellenItemPhoto(item.id);
    const pr = $("priceRefresh");
    if (pr) pr.onclick = async () => {
      pr.classList.add("spin");
      try {
        // Bis zu 3 Min. warten; bei Job-Antwort pollen — Timeout ≠ Erfolg
        const res = await post(`/api/app/collection/item/${item.id}/refresh-price`,
                               {}, { timeout: 180000 });
        if (res && res.job_id) {
          toast(L("Preisermittlung läuft"), "check");
          const jid = res.job_id;
          let done = false;
          for (let i = 0; i < 60 && !done; i++) {
            await new Promise(r => setTimeout(r, 2000));
            try {
              const st = await api(`/api/app/collection/item/${item.id}/price-job/${jid}`,
                                   { timeout: 15000 });
              const status = (st && st.job && st.job.status) || "";
              if (status === "COMPLETE") {
                toast(L("Preis aktualisiert"), "check");
                done = true;
              } else if (status === "NO_MARKET_DATA") {
                toast(L("Kein Marktwert gefunden"), "warn");
                done = true;
              } else if (status === "RETRYABLE_ERROR" || status === "PERMANENT_ERROR") {
                toast(L("Preisermittlung fehlgeschlagen"), "warn");
                done = true;
              }
            } catch (_) { /* weiter pollen */ }
          }
          if (!done) toast(L("Preisermittlung läuft noch — gleich nochmal prüfen"), "warn");
        } else {
          // Legacy: nur bei konkretem Wert Erfolg melden
          const val = res && (res.est_value != null ? res.est_value
                        : (res.item && res.item.est_value));
          if (val != null && val !== "") toast(L("Preis aktualisiert"), "check");
          else toast(L("Kein Marktwert gefunden"), "warn");
        }
        refreshDetail(true);
      } catch (e) {
        const msg = String(e && e.message || e || "");
        if (/zu lange|timeout|abort/i.test(msg)) {
          toast(L("Preisermittlung läuft noch — gleich nochmal prüfen"), "warn");
        } else {
          toast(msg);
        }
      }
      finally { pr.classList.remove("spin"); }
    };
  }
  if (item) {
    syncDetailCtaDock(det);
    const btnPrep = $("btnListPrep");
    if (btnPrep) btnPrep.onclick = () => {
      if (state._skipEnsureDraft) delete state._skipEnsureDraft[item.id];
      startListingPrep(item, btnPrep);
    };
    const ebayHint = $("btnEbayConnectHint");
    if (ebayHint) ebayHint.onclick = () => showEbayNotConnectedHint();
    const photoEdit = $("ebayPhotoEdit");
    if (photoEdit) photoEdit.onclick = () => openHeroPhotoEdit(det);
  }
  /* Kein stiller Auto-Start: Vorbereitung nur nach Tipp, mit eBay-Gate und Timeout. */
  if (!skipListingPaint) {
    if (d) wireDraftSection(d);
    bindEbayDescCollapse();
    if (d) applyListingValidation(d, item);
  }
  if (!item) hideDetailCtaDock();
  if (!skipHeroBind) {
  fadeImgs(body);
  // Foto-Punkte: aktive Seite folgt dem Karussell (iOS-Muster)
  const _strip = body.querySelector(".d-photos");
  const _dots = body.querySelectorAll(".d-dots i");
  if (_strip && _dots.length) {
    _strip.addEventListener("scroll", () => {
      const max = Math.max(1, _strip.scrollWidth - _strip.clientWidth);
      const di = Math.round(_strip.scrollLeft / max * (_dots.length - 1));
      _dots.forEach((d2, n) => d2.classList.toggle("on", n === di));
      det.photoIdx = di;
    }, { passive: true });
  }
  if (item && seg === "overview") {
    const fullUrls = (item.photos || []).map((u) => thumb(u, 1600));
    const openLb = (idx) => {
      det.photoIdx = idx || 0;
      openLightbox(fullUrls, idx || 0);
    };
    body.querySelectorAll(".d-photos img").forEach((img, idx) => {
      img.style.cursor = "zoom-in";
      img.onclick = (ev) => { ev.stopPropagation(); openLb(idx); };
    });
    body.querySelectorAll(".holo-wrap").forEach((w, idx) => {
      w.style.cursor = "zoom-in";
      w.addEventListener("click", (ev) => { ev.stopPropagation(); openLb(idx); });
    });
  }
  // Holo-Tilt: Pointer + Gyro gebündelt (max. 1 Frame), Listener nur bei sichtbarem Detail
  const holoWraps = body.querySelectorAll(".holo-wrap");
  holoCtl.deactivate();
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches
    || document.documentElement.classList.contains("reduced-effects");
  if (!holoWraps.length || reduced) {
    /* kein Holo */
  } else {
    holoCtl.setWraps(holoWraps);
    holoWraps.forEach((w) => {
      let moveRaf = 0, last = null;
      const flush = () => {
        moveRaf = 0;
        if (!last) return;
        const e = last; last = null;
        const r = w.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        holoCtl.queue({
          rx: `${(0.5 - y) * 10}deg`,
          ry: `${(x - 0.5) * 12}deg`,
          gx: `${x * 100}%`,
          gy: `${y * 100}%`,
        });
      };
      w.addEventListener("pointermove", (e) => {
        last = e;
        if (!moveRaf) moveRaf = requestAnimationFrame(flush);
      });
      w.addEventListener("pointerleave", () => {
        w.classList.remove("tilting");
        w.style.setProperty("--rx", "0deg"); w.style.setProperty("--ry", "0deg");
      });
    });
    if (window.DeviceOrientationEvent) {
      const arm = () => {
        holoCtl.activate((e) => {
          if ($("detail").hidden || document.hidden) return null;
          const g = Math.max(-30, Math.min(30, e.gamma || 0));
          const b = Math.max(-30, Math.min(30, (e.beta || 0) - 40));
          return {
            rx: `${(-b / 30) * 5}deg`,
            ry: `${(g / 30) * 6}deg`,
            gx: `${50 + (g / 30) * 45}%`,
            gy: `${50 + (b / 30) * 45}%`,
          };
        });
        state._gyro = true;
      };
      if (typeof DeviceOrientationEvent.requestPermission === "function") {
        if (state._gyroOk) arm();
        else holoWraps.forEach((w) => w.addEventListener("click", () => {
          DeviceOrientationEvent.requestPermission()
            .then((s) => { if (s === "granted") { state._gyroOk = true; arm(); } })
            .catch(() => {});
        }, { once: true }));
      } else arm();
    }
  }
  }
}

function openCardSearch(item) {
  let game = (item.card && item.card.game) || GAME_OF_CAT[item.category] || "pokemon";
  const games = [["pokemon", "Pokémon"], ["onepiece", "One Piece"], ["magic", "Magic"],
    ["yugioh", "Yu-Gi-Oh"], ["lorcana", "Lorcana"], ["dragonball", "Dragon Ball"]];
  openSheet("Karte zuordnen", "Suche die richtige Karte — deine Auswahl überschreibt die automatische Erkennung.", `
    <div class="chips" style="padding-bottom:10px">${games.map(([g, l]) =>
      `<button class="fchip ${game === g ? "on" : ""}" data-g="${g}">${l}</button>`).join("")}</div>
    <input id="csQ" type="text" placeholder="Kartenname, z. B. Monkey D. Luffy OP01" enterkeyhint="search">
    <div id="csResults" class="ilist" style="margin-top:12px"></div>`, null);
  const doSearch = async () => {
    const q = $("csQ").value.trim();
    if (q.length < 2) return;
    $("csResults").innerHTML = `<div class="stage-line" style="padding:12px"><span class="spinner"></span> Suche … (erster Lauf pro Spiel kann eine Minute dauern)</div>`;
    try {
      const r = await api(`/api/app/cardsearch?game=${game}&q=${encodeURIComponent(q)}`);
      if (!r.results.length) {
        $("csResults").innerHTML = `<p class="v-sub" style="display:block;padding:12px">Nichts gefunden — anderen Namen oder Kartencode probieren.</p>`;
        return;
      }
      $("csResults").innerHTML = r.results.map((res, i) => `
        <button class="irow tap" data-cs="${i}">
          ${res.image ? `<img class="simg" src="${esc(res.image)}" loading="lazy" style="object-fit:contain">` : `<span class="ric" style="background:var(--icon-neutral)">${icon("photo", 15)}</span>`}
          <span class="rlabel" style="font-size:13.5px;line-height:1.3">${esc(res.label)}<br><i class="mv-sub">${esc(res.sub || "")}</i></span>
          <span class="chev">${icon("chevron", 15)}</span>
        </button>`).join("");
      fadeImgs($("csResults"));
      $("csResults").querySelectorAll("[data-cs]").forEach((b) => {
        b.onclick = async () => {
          closeSheet();
          toast("Karte wird zugeordnet …", "check");
          try {
            await post(`/api/app/collection/item/${item.id}/match`, r.results[Number(b.dataset.cs)].match);
            toast("Karte zugeordnet — Preis aktualisiert", "check");
            refreshDetail(true);
          } catch (e) { toast(e.message); }
        };
      });
    } catch (e) {
      $("csResults").innerHTML = `<p class="v-sub" style="display:block;padding:12px;color:var(--red)">${esc(e.message)}</p>`;
    }
  };
  $("sheetBody").querySelectorAll("[data-g]").forEach((b) => {
    b.onclick = () => {
      game = b.dataset.g;
      $("sheetBody").querySelectorAll("[data-g]").forEach((x) => x.classList.toggle("on", x === b));
      doSearch();
    };
  });
  let t = null;
  $("csQ").addEventListener("input", () => { clearTimeout(t); t = setTimeout(doSearch, 500); });
  $("csQ").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
  setTimeout(() => $("csQ").focus(), 300);
}


function openCategorySearch(d) {
  openSheet(L("Kategorie wählen"), L("Suche die passende eBay-Kategorie — Pflichtmerkmale werden danach neu geladen."), `
    <input id="catQ" type="text" placeholder="${esc(L("z. B. One Piece Einzelkarte"))}" enterkeyhint="search" value="${esc((d.category_name || d.title || "").slice(0, 60))}">
    <div id="catResults" class="ilist" style="margin-top:12px"></div>`, null);
  const run = async () => {
    const q = $("catQ").value.trim();
    if (q.length < 2) return;
    $("catResults").innerHTML = `<div class="stage-line" style="padding:12px"><span class="spinner"></span> ${esc(L("Suche …"))}</div>`;
    try {
      const r = await api(`/api/app/category-suggest?q=${encodeURIComponent(q)}`);
      if (!(r.results || []).length) {
        $("catResults").innerHTML = `<p class="v-sub" style="display:block;padding:12px">${esc(L("Nichts gefunden — anderen Suchbegriff tippen."))}</p>`;
        return;
      }
      $("catResults").innerHTML = r.results.map((res, i) => `
        <button class="irow tap" data-cat="${i}">
          <span class="ric" style="background:#5a9aa8">${icon("stack", 15)}</span>
          <span class="rlabel">${esc(res.name)}</span>
          <span class="chev">${icon("chevron", 15)}</span>
        </button>`).join("");
      $("catResults").querySelectorAll("[data-cat]").forEach((b) => {
        b.onclick = async () => {
          const hit = r.results[Number(b.dataset.cat)];
          closeSheet();
          try {
            await doAction(d.id, "cat", hit.id + String.fromCharCode(9) + hit.name);
            toast(L("Kategorie gesetzt"), "check");
          } catch (e) { toast(e.message); }
        };
      });
    } catch (e) {
      $("catResults").innerHTML = `<p class="v-sub" style="display:block;padding:12px;color:var(--red)">${esc(e.message)}</p>`;
    }
  };
  $("catQ").addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  setTimeout(() => { try { $("catQ").focus(); run(); } catch (_) {} }, 200);
}

function openAlertSheet(item, alert) {
  let dir = alert?.direction || "above";
  openSheet("Preisalarm", "Du bekommst einen Hinweis im Dashboard, sobald der Marktwert die Schwelle erreicht.",
    `<div class="seg" id="alertDir" style="margin:0 0 12px">
       <button data-v="above" class="${dir === "above" ? "on" : ""}">Steigt über</button>
       <button data-v="below" class="${dir === "below" ? "on" : ""}">Fällt unter</button>
     </div>
     <input id="alertVal" type="text" inputmode="decimal" placeholder="z. B. 25"
       value="${alert ? String(alert.threshold).replace(".", ",") : ""}">
     ${alert ? `<button class="btn-secondary" id="alertDel" style="margin-top:12px;color:var(--red)">Alarm löschen</button>` : ""}`,
    async () => {
      try {
        await post(`/api/app/collection/item/${item.id}/alert`, { threshold: $("alertVal").value, direction: dir });
        closeSheet();
        toast("Preisalarm gesetzt", "bell");
        refreshDetail(true);
      } catch (e) { $("sheetErr").textContent = e.message; }
    }, "Alarm setzen");
  $("alertDir").querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      dir = b.dataset.v;
      $("alertDir").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    };
  });
  const del = $("alertDel");
  if (del) del.onclick = async () => {
    await post(`/api/app/collection/item/${item.id}/alert`, { threshold: null }).catch(() => {});
    closeSheet(); toast("Alarm gelöscht"); refreshDetail(true);
  };
}

function irow(id, ic, color, label, value, { tap = true } = {}) {
  return `<button class="irow ${tap ? "tap" : ""}" id="${id}">
    <span class="ric" style="background:${color}">${icon(ic, 15)}</span>
    <span class="rlabel">${esc(L(label))}</span>
    <span class="rvalue">${esc(value ?? "—")}</span>
    ${tap ? `<span class="chev">${icon("chevron", 15)}</span>` : ""}</button>`;
}

/** Readonly-Zeile in „Mein Exemplar“ — zeigt Analyse-Daten, ohne Patch. */
function exShow(ic, color, label, value) {
  const v = (value === null || value === undefined || value === "") ? "—" : String(value);
  return `<div class="irow">
    <span class="ric" style="background:${color}">${icon(ic, 15)}</span>
    <span class="rlabel">${esc(L(label))}</span>
    <span class="rvalue">${esc(v)}</span></div>`;
}

/** Sprache aus Name/Titel ziehen — oft schon im Listing-Titel. */
function detectLanguageHint(...parts) {
  const blob = parts.filter(Boolean).join(" ");
  if (!blob) return null;
  const rules = [
    [/Japanisch|Japanese|\bJP\b|日本語/i, "Japanisch"],
    [/Englisch|English|\bEN\b|\bENG\b/i, "Englisch"],
    [/Deutsch|German|\bDE\b/i, "Deutsch"],
    [/Koreanisch|Korean|\bKR\b/i, "Koreanisch"],
    [/Chinesisch|Chinese|\bCN\b|简体|繁體/i, "Chinesisch"],
    [/Französisch|French|\bFR\b/i, "Französisch"],
    [/Italienisch|Italian|\bIT\b/i, "Italienisch"],
    [/Spanisch|Spanish|\bES\b/i, "Spanisch"],
  ];
  for (const [re, lab] of rules) if (re.test(blob)) return lab;
  return null;
}

/** Kartennummer aus Text (z. B. 199/165, OP13-007, P-099). */
function detectCardNumber(...parts) {
  const blob = parts.filter(Boolean).join(" ");
  if (!blob) return null;
  const slash = blob.match(/\b(\d{1,4})\s*\/\s*(\d{1,4})\b/);
  if (slash) return { number: slash[1], total: slash[2] };
  const code = blob.match(/\b([A-Z]{1,4}\d{0,2}-\d{2,3}[A-Z]?)\b/i);
  if (code) return { number: code[1].toUpperCase(), total: null };
  const promo = blob.match(/\b(P-\d{2,4})\b/i);
  if (promo) return { number: promo[1].toUpperCase(), total: null };
  return null;
}

/**
 * Stammdaten für „Mein Exemplar“: Katalog-card gewinnt, sonst card_info,
 * sonst Heuristik aus Name/Titel. Ohne Katalog-Match war card oft null —
 * die Erkennung steckt dann in card_info.
 */
function mergeCardStammdaten(item) {
  const c = item.card || {};
  const ci = item.card_info || {};
  const pick = (a, b) => (a !== null && a !== undefined && a !== "" ? a : b);
  const setName = pick(c.set_name, pick(ci.set_name, ci.set_hint || null));
  let number = pick(c.number, ci.number || null);
  let total = pick(c.total, pick(c.set_total, ci.set_total || null));
  if (!number) {
    const hit = detectCardNumber(item.name, item.analysis_title, ci.set_hint);
    if (hit) { number = hit.number; total = total || hit.total; }
  }
  const language = pick(c.language, pick(ci.language,
    detectLanguageHint(item.name, item.analysis_title, ci.set_hint)));
  const nummer = number
    ? `${number}${total ? " / " + total : ""}`
    : null;
  return { setName, nummer, language };
}

/** Stammdaten in der Übersicht — Besitz, keine Listing-Felder. */
function exemplarBlock(item) {
  const st = mergeCardStammdaten(item);
  const g = item.graded || {};
  const seal = gradeSeal(g, item.name);
  const gradeTxt = seal.text
    || ((g.grader || g.grade)
      ? [g.grader, g.label_type, g.grade].filter(Boolean).join(" ")
      : null);
  const cert = g.cert_number || null;
  const notes = String(item.notes || "").trim();

  const isCardCat = isCardCategory(item.category);
  const hasCard = !!(item.card && (item.card.name || item.card.number));
  const matchHint = isCardCat && !hasCard
    ? L("Keine Karten-Datenbank-Zuordnung — für Sealed-Produkte normal. Einzelkarte? Dann von Hand zuordnen:")
    : (isCardCat ? L("Falsche Karte? Von Hand neu zuordnen.") : "");
  const showIf = (ic, color, label, value) => {
    if (value === null || value === undefined || String(value).trim() === "") return "";
    return exShow(ic, color, label, value);
  };
  return `
    <div class="section-label">${L("Mein Exemplar")}</div>
    <div class="ilist">
      ${irow("i-name", "note", "var(--tint)", "Name", item.name || "—")}
      ${showIf("tag", "#ff9500", "Kartennummer", st.nummer)}
      ${showIf("folder", "#3478f6", "Set", st.setName)}
      ${showIf("note", "#5a9aa8", "Sprache", st.language)}
      ${irow("i-cat", "folder", "#3478f6", "Kategorie", catUiLabel(item.category))}
      ${isCardCat ? `<button class="irow tap" id="btnCardSearch">
        <span class="ric" style="background:#3478f6">${icon("search", 15)}</span>
        <span class="rlabel">${L("Karte zuordnen")}${matchHint ? `<br><i class="mv-sub">${esc(matchHint)}</i>` : ""}</span>
        <span class="chev">${icon("chevron", 15)}</span></button>` : ""}
    </div>

    <div class="ex-sub">${L("Zustand")}</div>
    <div class="ilist">
      ${irow("i-cond", "tag", "#ff9500", "Zustand", condLabel(item.condition, item.category))}
      ${showIf("shield", "#c9a961", "Grade", gradeTxt)}
      ${cert ? exShow("shield", "var(--icon-neutral)", "Zertifikat", cert) : ""}
    </div>

    <div class="ex-sub">${L("Dein Bestand")}</div>
    <div class="ilist" id="itemList">
      ${irow("i-qty", "box", "#a355d6", "Stückzahl", String(item.quantity))}
      ${irow("i-paid", "euro", "#5a9aa8", "Kaufpreis",
        item.purchase_price ? money(parseFloat(String(item.purchase_price).replace(",", "."))) : "—")}
      ${notes ? irow("i-notes", "note", "#8e8e93", "Notiz", notes) : ""}
    </div>`;
}

function wireRow(id, fn) { const el = $(id); if (el) el.onclick = fn; }

async function patchItem(itemId, fields) {
  await post(`/api/app/collection/item/${itemId}`, fields);
  refreshDetail({ force: true, preserve: true });
}

/* ─── eBay-Draft-Sektion ─── */

function isDraftUploadBusy(d) {
  if (!d) return false;
  if (d.status === "publishing") return true;
  if (d.stage && !d.stage.done) return true;
  if (state.draftBusy && state.draftBusy[d.id]) return true;
  return false;
}

function markDraftBusy(draftId, on) {
  if (!draftId) return;
  state.draftBusy = state.draftBusy || {};
  if (on) state.draftBusy[draftId] = Date.now();
  else delete state.draftBusy[draftId];
}

function reviewGateBlocked(d) {
  const st = (d && d.status) || "";
  if (["analyzing", "downloading", "waiting", "publishing"].includes(st)) return true;
  if (isDraftUploadBusy(d)) return true;
  return false;
}

const DRAFT_LIGHT_ACTIONS = new Set([
  "price", "title", "desc", "qty", "fmt", "dur", "offer", "offermin", "usk", "uskset",
]);

async function ensureEbayPolicies() {
  if (state.ebayPolicies && !state.ebayPolicies._loading) return state.ebayPolicies;
  if (state.ebayPolicies && state.ebayPolicies._loading) return state.ebayPolicies;
  state.ebayPolicies = { _loading: true };
  try {
    state.ebayPolicies = await api("/api/app/ebay/policies");
  } catch (_) {
    state.ebayPolicies = { fulfillment: [], payment: [], return: [], current: {} };
  }
  return state.ebayPolicies;
}

function fulfillmentForDraft(d, policies) {
  const pack = policies || state.ebayPolicies || {};
  const id = (d && d.policies && d.policies.fulfillment_policy_id)
    || (pack.current && pack.current.fulfillment_policy_id);
  return (pack.fulfillment || []).find((p) => p && p.id === id) || null;
}

function returnPolicyForDraft(d, policies) {
  const pack = policies || state.ebayPolicies || {};
  const id = (d && d.policies && d.policies.return_policy_id)
    || (pack.current && pack.current.return_policy_id);
  return (pack.return || []).find((p) => p && p.id === id) || null;
}

function shippingFactRows(d) {
  const f = fulfillmentForDraft(d);
  const ret = returnPolicyForDraft(d);
  const pol = (d && d.policies) || {};
  const row = (label, value) => {
    if (!value) return "";
    return `<div class="irow"><span class="ric" style="background:#5a9aa8">${icon("box", 15)}</span>
        <span class="rlabel">${esc(L(label))}</span>
        <span class="rvalue">${esc(value)}</span></div>`;
  };
  let html = "";
  if (f && f.name) html += row("Versandprofil", f.name);
  if (f && f.service) html += row("Versandart", f.service);
  if (f && f.cost) html += row("Versandkosten", f.cost === "Kostenlos" ? L("Kostenlos") : f.cost);
  if (f && f.handling) html += row("Bearbeitungszeit", f.handling);
  html += row("Zielmarktplatz", "eBay.de");
  if (pol.location_key) html += row("Versandstandort", pol.location_key);
  if (f && f.international) html += row("Internationaler Versand", L("aktiv"));
  if (f && f.pickup) html += row("Abholung", L("aktiv"));
  if (ret) html += row("Rücknahme", ret.returnsAccepted ? L("aktiv") : L("nein"));
  return html;
}

function listingValidationFor(d, item) {
  const SD = seroDetailApi();
  if (SD && SD.listingValidation) return SD.listingValidation(d, item, d && d._preflight);
  return { issues: [], blockingCount: 0, ready: true, loading: false };
}

function captureDetailViewState(det) {
  const body = $("detailBody");
  const track = $("detailGalleryTrack");
  return {
    scrollTop: body ? body.scrollTop : 0,
    photoIdx: (det && typeof det.photoIdx === "number") ? det.photoIdx : 0,
    galLeft: track ? track.scrollLeft : 0,
  };
}

function restoreDetailViewState(det, st) {
  if (!st) return;
  const body = $("detailBody");
  const track = $("detailGalleryTrack");
  if (body) body.scrollTop = st.scrollTop;
  if (track && st.galLeft != null) track.scrollLeft = st.galLeft;
  if (det && st.photoIdx != null) det.photoIdx = st.photoIdx;
}

function detailHeroSignature(item, seg) {
  if (!item) return "";
  const imgs = detailGalleryImages(item, seg === "sell");
  return String(item.id || "") + "|" + imgs.map((im) => im.url || "").join("\n");
}

function sheetIsOpen() {
  const sh = $("sheet");
  return !!(sh && !sh.hidden && !sh.classList.contains("closing"));
}

function listingInputBusy() {
  const ae = document.activeElement;
  if (!ae || !/^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName)) return false;
  if (ae.readOnly || ae.disabled) return false;
  const sh = $("sheet");
  if (sh && sheetIsOpen() && sh.contains(ae)) return true;
  const det = $("detail");
  if (det && !det.hidden && det.contains(ae)) return true;
  return false;
}

function listingPaintKey(data) {
  if (!data) return "";
  const d = data.draft || null;
  return JSON.stringify({
    itemStatus: data.status || "",
    design: data.design_photo || "",
    photos: data.photos || [],
    draft: d && {
      id: d.id,
      status: d.status,
      price: d.price,
      title: d.title,
      format: d.format,
      quantity: d.quantity,
      auction_days: d.auction_days,
      description_plain: d.description_plain,
      condition: d.condition,
      category_name: d.category_name,
      aspects: d.aspects,
      missing_aspects: d.missing_aspects,
      question: d.question,
      pending: d.pending,
      error: d.error || d.error_text || "",
      published: d.published,
      revision: d.revision,
      stageBusy: !!(d.stage && !d.stage.done),
      render_busy: d.render_busy,
      best_offer: d.best_offer,
      best_offer_min: d.best_offer_min,
      policies: d.policies,
      photoUrls: (d.photos || []).map((p) => p.url || p),
      identity_label: d.identity_label,
      usk: d.usk,
    },
  });
}

function flushQueuedDetailPaint() {
  if (!state._detailPaintQueued) return;
  if (listingInputBusy()) return;
  state._detailPaintQueued = false;
  const det = state.detail;
  if (!det || !det.data) return;
  const st = captureDetailViewState(det);
  const keep = $("detailPanes") || $("detailHero");
  if (keep) renderDetail(det, { preserve: true, ebayOnly: !!det.showListing });
  else renderDetail(det);
  restoreDetailViewState(det, st);
}

function mergeDraftPayload(draftId, payload) {
  const det = state.detail;
  if (!det || !det.data || !payload) return;
  if (payload.discarded || payload.ended) return;
  if (payload.ok && payload.processing && !payload.id) return;
  const cur = det.data.draft;
  if (!cur) return;
  if (cur.id && payload.id && cur.id !== payload.id) return;
  if (draftId && cur.id && cur.id !== draftId && det.id !== draftId) return;
  det.data.draft = Object.assign({}, cur, payload);
}

function fieldElForIssue(field) {
  if (!field) return null;
  if (field === "identity" || field === "item_status") return $("lr-identity") || $("lr-cardsearch") || $("lr-product");
  if (field === "price") return $("lr-price");
  if (field === "title") return $("lr-title") || $("lr-offer");
  if (field === "description") return $("lr-desc") || $("lr-desc-card") || $("lr-offer");
  if (field === "category_id") return $("lr-product");
  if (field === "condition") return $("lr-product");
  if (String(field).startsWith("aspect:")) {
    const name = String(field).slice(7);
    return document.getElementById("lr-aspect-" + name) || $("lr-product");
  }
  if (field === "photos") return $("lr-photos") || $("detailGallery");
  if (field === "shipping" || field === "payment" || field === "return" || field === "ebay")
    return document.getElementById("lr-" + field) || $("lr-shipping");
  if (field === "question") return $("lr-question");
  return $(field) || $("lr-offer");
}

function applyListingFieldHints(issues, opts) {
  opts = opts || {};
  const root = $("detailBody");
  if (!root) return;
  root.querySelectorAll(".lr-field-msg").forEach((el) => el.remove());
  root.querySelectorAll(".lr-miss, .lr-warn").forEach((el) => {
    el.classList.remove("lr-miss", "lr-warn");
  });
  if (opts.loading) return;
  (issues || []).forEach((iss) => {
    const el = fieldElForIssue(iss.fieldId || iss.field);
    if (!el) return;
    if (iss.blocking && iss.severity === "error") el.classList.add("lr-miss");
    else if (iss.severity === "warn") el.classList.add("lr-warn");
    const host = el.querySelector(".rlabel") || el.querySelector(".pt-sub") || el;
    if (host.querySelector && host.querySelector(".lr-field-msg")) return;
    const msg = document.createElement("i");
    msg.className = "lr-field-msg " + (iss.severity === "warn" ? "is-warn" : "is-err");
    msg.textContent = L(iss.message || "");
    host.appendChild(msg);
  });
}

function syncPublishCta(d, item) {
  const btn = $("lr-publish");
  if (!btn || !d) return;
  if (isDraftUploadBusy(d) || d.published || d.status === "ended") return;
  const v = listingValidationFor(d, item);
  if (v.loading) {
    btn.disabled = true;
    btn.removeAttribute("data-dact");
    btn.innerHTML = `<span class="spinner"></span><span>${esc(L("Listing wird vorbereitet …"))}</span>`;
    return;
  }
  btn.disabled = false;
  btn.setAttribute("data-dact", "upload");
  const n = v.blockingCount;
  btn.classList.toggle("is-incomplete", n > 0);
  btn.textContent = n > 0 ? LF("Noch {0} Angaben", n) : L("Bereit");
}

function applyListingValidation(d, item) {
  if (!d) return;
  const v = listingValidationFor(d, item);
  applyListingFieldHints(v.issues, { loading: v.loading });
  syncPublishCta(d, item);
  return v;
}

function aspectVal(aspects, name) {
  const v = (aspects || {})[name];
  if (Array.isArray(v)) return (v[0] != null ? String(v[0]) : "");
  return v != null ? String(v) : "";
}

function sellFieldCard(title, act, id, value, { locked, frozen, placeholder } = {}) {
  const txt = (value && String(value).trim()) ? String(value) : (placeholder || L("Tippen zum Bearbeiten"));
  const inner = frozen
    ? `<div class="d-sell-input" id="${id}">${esc(txt)}</div>`
    : `<button type="button" class="d-sell-input" data-dact="${act}" id="${id}"${locked ? " disabled aria-disabled=\"true\"" : ""}>${esc(txt)}</button>`;
  return `<section class="d-card d-sell-card lr-sec">
    <div class="d-card-h">${esc(L(title))}</div>${inner}</section>`;
}

function sellDescCard(descFull, { locked, frozen, item } = {}) {
  const SD = seroDetailApi();
  const raw = String(descFull || "");
  const plain = (SD && SD.ebayDescPlain) ? SD.ebayDescPlain(raw, item) : raw.replace(/\r\n/g, "\n").trim();
  const empty = !String(plain).trim();
  const body = empty
    ? esc(L("Tippen zum Bearbeiten"))
    : ((SD && SD.ebayDescHtml) ? SD.ebayDescHtml(plain) : `<p>${esc(plain)}</p>`);
  const edit = (frozen || locked)
    ? ""
    : `<button type="button" class="d-desc-edit" data-dact="desc">${esc(L("Bearbeiten"))}</button>`;
  const tap = (frozen || locked) ? "" : ` data-dact="desc"`;
  const more = empty ? "" : `<button type="button" class="d-desc-more" id="lr-desc-more">${esc(L("Mehr"))}</button>`;
  return `<section class="d-card d-sell-card lr-sec d-desc-card" id="lr-desc-card">
    <div class="d-card-h"><span>${esc(L("Beschreibung"))}</span>${edit}</div>
    <div class="d-desc-preview is-collapsed" id="lr-desc"${tap}>${body}</div>
    ${more}
  </section>`;
}

function bindEbayDescCollapse() {
  const preview = $("lr-desc");
  const more = $("lr-desc-more");
  if (!preview || !more) return;
  preview.classList.add("is-collapsed");
  const overflow = preview.scrollHeight > preview.clientHeight + 4;
  if (!overflow) {
    preview.classList.remove("is-collapsed");
    more.hidden = true;
    return;
  }
  more.hidden = false;
  more.textContent = L("Mehr");
  more.onclick = (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    const collapsed = preview.classList.toggle("is-collapsed");
    more.textContent = collapsed ? L("Mehr") : L("Weniger");
  };
}

function renderDraftSection(d, opts) {
  opts = opts || {};
  if (!state.ebayPolicies) {
    ensureEbayPolicies().then(() => {
      try { renderDetail(state.detail, { preserve: true, ebayOnly: true }); } catch (_) { /* */ }
    });
  }
  let html = "";
  const isAuc = d.format === "AUCTION";
  const price = eur(d.price);
  const locked = isDraftUploadBusy(d);

  const live = !!d.published;
  const sold = d.status === "ended";
  const formatFrozen = live || sold;
  const priceFrozen = sold || (live && isAuc && (d.bid_count || 0) > 0);
  const frozen = formatFrozen;
  const lockAttr = (locked || sold) ? " disabled aria-disabled=\"true\"" : "";

  if (live) html += `<span class="live-pill">${L("Live bei eBay")}</span>`;
  if (sold) html += `<span class="live-pill sold">${L("Verkauft")}</span>`;
  html += listingStatsHtml(d);
  const bos = d.buyer_offers || [];
  if (live && bos.length) {
    html += `<div class="buyer-offers"><div class="section-label" style="margin-top:12px">${L("Offene Preisvorschläge")}</div><div class="ilist">`
      + bos.slice(0, 5).map((o) => `
        <div class="irow">
          <span class="ric" style="background:#5a9aa8">${icon("percent", 15)}</span>
          <span class="rlabel">${esc(o.buyer || L("Käufer"))}${o.expires
            ? `<br><i style="color:var(--label-2);font-style:normal;font-size:11.5px">${L("offen bis")} ${esc(String(o.expires).slice(0, 16).replace("T", " "))}</i>`
            : ""}</span>
          <span class="rvalue" style="font-weight:750;color:var(--tint)">${money(parseFloat(String(o.price)))}</span>
        </div>`).join("")
      + `</div></div>`;
  }
  if (d.stage && !d.stage.done) {
    html += `<div class="stage-line"><span class="spinner"></span> ${esc(d.stage.text)}</div>`;
  }
  if (d.question) {
    html += `<div class="qbox" id="lr-question"><p>${esc(d.question)}</p>
      <div class="qrow"><input id="qInput" type="text" placeholder="Antwort …">
      <button type="button" class="qsend" id="qSend" aria-label="${esc(L("Senden"))}">${icon("arrowup", 17)}</button></div></div>`;
  } else if (d.pending === "graded" || d.pending === "graded_update") {
    html += `<div class="qbox" id="lr-question"><p>${esc(d.pending_frage || L("Für dieses Stück fehlen Grading-Angaben. Beispiel: PSA 9.5 12345678"))}</p>
      <div class="qrow"><input id="qInput" type="text" placeholder="${esc(L("Bewerter Note Zertifikat …"))}">
      <button type="button" class="qsend" id="qSend" aria-label="${esc(L("Senden"))}">${icon("arrowup", 17)}</button></div></div>`;
  }
  const errMsg = d.error_text || d.error;
  if (errMsg) {
    html += `<div class="err-box">${esc(errMsg)}</div>`;
  } else if (d.status === "error") {
    html += `<div class="err-box">${esc(L("Die Erstellung ist fehlgeschlagen."))}</div>`;
  }
  if (d.status === "error") {
    html += `<button type="button" class="btn-primary" data-dact="retry_list" style="margin-top:12px">${esc(L("Erneut versuchen"))}</button>`;
    return html;
  }
  if (d.assumptions && !d.published) html += `<div class="assume">Annahme: ${esc(d.assumptions)}</div>`;

  if (["downloading", "analyzing"].includes(d.status) && !d.title && !(opts.item && opts.item.name)) {
    if (!(d.stage && !d.stage.done) && !d.question && !errMsg) {
      html += `<div class="stage-line"><span class="spinner"></span> ${esc(L("Listing wird vorbereitet …"))}</div>`;
    }
    return html;
  }
  if (!d.title && opts.item && opts.item.name) d.title = opts.item.name;

  const cardCls = opts.cards ? " d-card d-sell-card" : "";
  const itemScan = opts.item && (opts.item.scan_description || (opts.item.analysis && opts.item.analysis.description_plain));
  const descFull = d.description_plain || itemScan || "";

  if (opts.cards) {
    html += sellFieldCard("Titel", "title", "lr-title", d.title, { locked: false, frozen: sold });
    html += sellDescCard(descFull, { locked, frozen: locked || sold, item: opts.item });
  }

  /* ── A · Bilder ─────────────────────────────────────────── */
  const dPhotos = d.photos || [];
  const photoStrip = dPhotos.length ? `<div class="ph-strip lr-ph-strip" id="lr-ph-strip">${
    dPhotos.map((p, i) => `
      <figure class="ph-kachel" data-pi="${i}">
        <img src="${esc(thumb(p.url || p, 240))}" alt="" loading="lazy">
        ${i === 0 ? `<span class="ph-haupt">${L("Hauptbild")}</span>` : ""}
        ${(!frozen && !locked && dPhotos.length > 1) ? `<nav class="ph-sort lr-ph-sort" aria-label="${esc(L("Reihenfolge & Hauptbild"))}">
          <button type="button" class="ph-star${i === 0 ? " is-main" : ""}" data-dact="imgmain" data-i="${i}" ${i === 0 ? "disabled" : ""} aria-label="${esc(L("Als Hauptbild"))}">${icon(i === 0 ? "starfill" : "star", 18)}</button>
          <div class="ph-nudge-pair">
            <button type="button" class="ph-nudge" data-dact="imgswap" data-i="${i}" data-dir="-1" ${i === 0 ? "disabled" : ""} aria-label="${esc(L("Nach vorn"))}"><span aria-hidden="true">‹</span></button>
            <button type="button" class="ph-nudge" data-dact="imgswap" data-i="${i}" data-dir="1" ${i === dPhotos.length - 1 ? "disabled" : ""} aria-label="${esc(L("Nach hinten"))}"><span aria-hidden="true">›</span></button>
          </div>
        </nav>` : ""}
      </figure>`).join("")
  }</div>` : "";
  if (!opts.hidePhotos) {
    html += `<div class="lr-sec${cardCls}" id="lr-photos">
    <div class="section-label">${L("A · Bilder")}</div>
    <p class="lr-hint">${esc(L("Dein Freisteller ist das Hauptbild. Tippe auf ein Bild für Zuschnitt, Drehen, Hintergrund und Freistellen."))}</p>
    ${photoStrip}
    <div class="quick-row">
      <button class="quick" data-dact="img"${lockAttr}><span class="qic">${icon("photo", 19)}</span><span>${L("Bilder bearbeiten")}</span></button>
    </div>
  </div>`;
  }

  /* ── B · Produkt ────────────────────────────────────────── */
  const aspects = d.aspects || {};
  const required = d.required_aspects || [];
  const missing = d.missing_aspects || [];
  const idLabel = d.identity_label || d.title || "—";
  const SD = seroDetailApi();
  const isCardRow = SD && SD.isCardLike ? SD.isCardLike(opts.item, d) : false;
  html += `<div class="lr-sec${cardCls}" id="lr-product">
    <div class="section-label">${opts.cards ? L("Kategorie") : L("B · Produkt")}</div>
    <div class="ilist">`;
  if (!frozen && !locked && isCardRow && d.collection_item_id) {
    html += `<button type="button" class="irow tap" data-dact="cardsearch" id="lr-identity">
      <span class="ric" style="background:#3478f6">${icon("search", 15)}</span>
      <span class="rlabel">${L("Identität")}<br><i class="mv-sub">${esc(idLabel)}</i></span>
      <span class="rvalue">${L("Karte zuordnen")}</span>
      <span class="chev">${icon("chevron", 15)}</span></button>`;
  } else {
    html += `<div class="irow" id="lr-identity"><span class="ric" style="background:#3478f6">${icon("search", 15)}</span>
      <span class="rlabel">${L("Identität")}<br><i class="mv-sub">${esc(idLabel)}</i></span>
      <span class="rvalue">${esc(idLabel)}</span></div>`;
  }
  if (frozen || locked) {
    html += `<div class="irow"><span class="ric" style="background:#5a9aa8">${icon("stack", 15)}</span>
      <span class="rlabel">${L("Kategorie")}</span>
      <span class="rvalue">${esc(d.category_name || L("Wird ermittelt …"))}</span></div>`;
  } else {
    html += drow("cat", "stack", "#5a9aa8", "Kategorie", d.category_name || L("Tippen zum Wählen"));
  }
  if (frozen) {
    html += `<div class="irow"><span class="ric" style="background:#ff9500">${icon("tag", 15)}</span>
      <span class="rlabel">${L("Zustand")}</span>
      <span class="rvalue">${esc(L(condLabel(d.condition, d.category_name)))}</span></div>`;
  } else if (locked) {
    html += `<div class="irow"><span class="ric" style="background:#ff9500">${icon("tag", 15)}</span>
      <span class="rlabel">${L("Zustand")}</span>
      <span class="rvalue">${esc(L(condLabel(d.condition, d.category_name)))}</span></div>`;
  } else {
    html += drow("cond", "tag", "#ff9500", "Zustand", condLabel(d.condition, d.category_name));
  }
  if (!frozen && d.show_usk) {
    html += locked
      ? `<div class="irow"><span class="ric" style="background:#eb4d3d">${icon("shield", 15)}</span>
          <span class="rlabel">${L("Altersfreigabe")}</span>
          <span class="rvalue">${esc(d.usk !== null && d.usk !== undefined ? LF("USK ab {0}", d.usk) : L("Keine Angabe"))}</span></div>`
      : drow("usk", "shield", "#eb4d3d", "Altersfreigabe",
                        d.usk !== null && d.usk !== undefined ? LF("USK ab {0}", d.usk) : L("Keine Angabe"));
  }
  // Pflichtmerkmale
  const aspectNames = [...new Set([...(required || []), ...Object.keys(aspects || {})])];
  if (aspectNames.length) {
    html += `</div><div class="ex-sub">${L("Pflichtmerkmale")}</div><div class="ilist">`;
    aspectNames.forEach((name) => {
      const val = aspectVal(aspects, name) || (missing.includes(name) ? L("Fehlt — tippen") : "—");
      const miss = missing.includes(name) || !aspectVal(aspects, name);
      if (frozen || locked) {
        html += `<div class="irow${miss ? " lr-miss" : ""}" id="lr-aspect-${esc(name)}">
          <span class="ric" style="background:${miss ? "#eb4d3d" : "#8e8e93"}">${icon("doc", 15)}</span>
          <span class="rlabel">${esc(name)}</span>
          <span class="rvalue">${esc(val)}</span></div>`;
      } else {
        html += `<button class="irow tap${miss ? " lr-miss" : ""}" data-dact="aspect" data-aspect="${esc(name)}" id="lr-aspect-${esc(name)}">
          <span class="ric" style="background:${miss ? "#eb4d3d" : "#8e8e93"}">${icon("doc", 15)}</span>
          <span class="rlabel">${esc(name)}</span>
          <span class="rvalue">${esc(val)}</span>
          <span class="chev">${icon("chevron", 15)}</span></button>`;
      }
    });
  }
  html += `</div></div>`;

  /* ── C · Angebot ────────────────────────────────────────── */
  const priceSub = priceFrozen
    ? (sold
        ? (d.sold_price || price
            ? LF("Verkauft für {0}", money(parseFloat(String(d.sold_price || d.price).replace(",", "."))))
            : L("Verkaufspreis · beendet"))
        : (isAuc
            ? ((d.bid_count || 0) > 0
                ? LF("Aktuelles Gebot · Auktion · {0} Gebote", d.bid_count || 0)
                : L("Auktion · noch ohne Gebot"))
            : L("Festpreis · live auf eBay")))
    : live
      ? `${isAuc ? L("Auktion · noch ohne Gebot") : L("Festpreis · live auf eBay")} · ${L("tippen zum Ändern")}`
      : `${d.price_basis ? esc(L(d.price_basis)) + " · " : ""}${isAuc ? L("Startpreis · Auktion") : L("Sofortkauf")}${d.quantity > 1 ? ` · ${d.quantity} Stück` : ""}${d.fee ? ` · Gebühr${d.quantity > 1 ? " gesamt" : ""} ~${eur(d.fee.fee.toFixed(2))} € · Netto ~${eur(d.fee.net.toFixed(2))} €` : ""}`;

  html += `<div class="lr-sec${cardCls}" id="lr-offer">
    <div class="section-label">${opts.cards ? L("Preis") : L("C · Angebot")}</div>`;
  html += priceFrozen
    ? `<div class="price-tap price-live" aria-disabled="true" id="lr-price">
        <span class="pt-price ${price ? "" : "missing"}">${price ? price + " €" : "—"}</span>
        <span class="pt-sub">${priceSub}</span>
      </div>`
    : `<button type="button" class="price-tap" data-dact="price" id="lr-price"${lockAttr}>
        <span class="pt-price ${price ? "" : "missing"}">${price ? price + " €" : "Preis festlegen …"}</span>
        <span class="pt-sub">${priceSub}</span>
        <span class="chev">${icon("chevron", 16)}</span>
      </button>`;
  if (!formatFrozen) {
    html += `
    ${opts.cards ? `<div class="d-sell-k">${esc(L("Kaufart"))}</div>` : ""}
    <div class="seg${locked ? " is-locked" : ""}" data-dseg="fmt">
      <button type="button" data-v="FIXED_PRICE" class="${isAuc ? "" : "on"}"${lockAttr}>${L("Sofortkauf")}</button>
      <button type="button" data-v="AUCTION" class="${isAuc ? "on" : ""}"${lockAttr}>${L("Auktion")}</button>
    </div>
    ${isAuc ? `<div class="seg small${locked ? " is-locked" : ""}" data-dseg="dur">
      ${[1, 3, 5, 7, 10].map((n) => `<button type="button" data-v="${n}" class="${d.auction_days === n ? "on" : ""}"${lockAttr}>${n} Tg</button>`).join("")}
    </div>` : ""}`;
  } else if (live) {
    html += `<p class="assume" style="margin:8px 0 12px">${esc(L(
      priceFrozen
        ? "Live auf eBay — Format steht fest. Titel und Beschreibung kannst du speichern."
        : "Live auf eBay — Format steht fest. Preis, Titel und Beschreibung kannst du ändern und speichern."
    ))}</p>`;
  }

  const titleRow = sold
    ? `<div class="irow" id="lr-title"><span class="ric" style="background:#3478f6">${icon("pencil", 15)}</span>
        <span class="rlabel">${L("Titel")}</span>
        <span class="rvalue">${esc(d.title)}</span></div>`
    : drow("title", "pencil", "#3478f6", "Titel", d.title);
  const descRow = (locked || sold)
    ? `<div class="irow" id="lr-desc"><span class="ric" style="background:#8e8e93">${icon("doc", 15)}</span>
        <span class="rlabel">${L("Beschreibung")}</span>
        <span class="rvalue">${esc((d.description_plain || "").slice(0, 40) || "—")}${(d.description_plain || "").length > 40 ? "…" : ""}</span></div>`
    : drow("desc", "doc", "#8e8e93", "Beschreibung",
        (d.description_plain || "").slice(0, 40) || L("Tippen zum Bearbeiten"));

  const titleDescRows = opts.cards ? "" : `${live && !locked ? drow("title", "pencil", "#3478f6", "Titel", d.title) : titleRow}
      ${live && !locked ? drow("desc", "doc", "#8e8e93", "Beschreibung",
            (d.description_plain || "").slice(0, 40) || L("Tippen zum Bearbeiten")) : descRow}`;

  html += `<div class="ilist" style="margin-bottom:12px">
      ${titleDescRows}
      ${(!frozen && !isAuc) ? (locked
        ? `<div class="irow"><span class="ric" style="background:#a355d6">${icon("box", 15)}</span>
            <span class="rlabel">${L("Stückzahl")}</span>
            <span class="rvalue">${esc(String(d.quantity))}</span></div>`
        : drow("qty", "box", "#a355d6", "Stückzahl", String(d.quantity))) : ""}
      ${(!frozen && !isAuc) ? (() => {
        const boOn = bestOfferOn(d);
        const boMin = bestOfferMin(d);
        return `<div class="irow lr-offer-row" id="lr-bo-row">
          <span class="ric" style="background:#5a9aa8">${icon("percent", 15)}</span>
          <span class="rlabel">${L("Preisvorschlag")}</span>
          <span class="lr-offer-acts">
            <span class="sw"><input type="checkbox" ${boOn ? "checked" : ""} data-dsw="offer"${lockAttr}><i></i></span>
            <input type="text" inputmode="decimal" class="lr-bo-min" data-dbo-min
              placeholder="${esc(L("Mindestpreis"))}" value="${esc(boMin)}"
              ${boOn && !locked ? "" : "hidden disabled"}${lockAttr}>
          </span></div>`;
      })() : ""}
    </div></div>`;

  /* ── D · Versand & Regeln ───────────────────────────────── */
  const pol = d.policies || {};
  const ebayOk = d.ebay_connected !== false;
  const polRow = (ok, label, field) => `
    <div class="irow${ok ? "" : " lr-miss"}" id="lr-${field}">
      <span class="ric" style="background:${ok ? "var(--green)" : "#eb4d3d"}">${icon(ok ? "check" : "xmark", 15)}</span>
      <span class="rlabel">${esc(L(label))}</span>
      <span class="rvalue">${esc(ok ? L("Bereit") : L("Fehlt — Setup im Profil"))}</span>
    </div>`;
  if (d.inventory_managed) {
    html += `<p class="assume" id="lr-inv-api">${esc(L("über Inventory API verwaltet"))}</p>`;
  }
  html += `<div class="lr-sec${cardCls}" id="lr-shipping">
    <div class="section-label">${opts.cards ? L("Versand") : L("D · Versand & Regeln")}</div>
    <div class="ilist">
      ${polRow(ebayOk, "eBay-Konto", "ebay")}
      ${polRow(!!pol.shipping, "Versandrichtlinie", "shipping")}
      ${polRow(!!pol.payment, "Zahlungsrichtlinie", "payment")}
      ${polRow(!!pol.return, "Rücknahmerichtlinie", "return")}
      ${shippingFactRows(d)}
    </div>
    ${(!pol.shipping || !pol.payment || !pol.return || !ebayOk)
      ? `<button class="btn-secondary" style="margin-top:10px" data-dact="setup">${L("Setup im Profil öffnen")}</button>`
      : `<button class="btn-secondary" style="margin-top:10px" data-dact="shippolicy">${L("Versandprofil")}</button>`}
  </div>`;

  if (d.status === "dry_run_done" && !state.dryRun) {
    html += `<div class="assume">${esc(L("Testlauf fertig — Inventar und Angebot liegen bei eBay, noch nicht veröffentlicht. Tippe, um live zu listen."))}</div>`;
  }

  /* CTA */
  if (live) {
    html += `<button class="btn-primary success" data-dact="save"${lockAttr}>${L("Änderungen speichern")}</button>`;
  } else if (!sold) {
    if (locked) {
      html += `<button class="btn-primary" disabled aria-busy="true" id="lr-publish"><span class="spinner"></span><span>${esc(L("Wird zu eBay geladen …"))}</span></button>`;
    } else {
      const item = opts.item;
      const v = listingValidationFor(d, item);
      if (v.loading) {
        html += `<button class="btn-primary" disabled id="lr-publish"><span class="spinner"></span><span>${esc(L("Listing wird vorbereitet …"))}</span></button>`;
      } else {
        const n = v.blockingCount;
        html += `<button type="button" class="btn-primary${n ? " is-incomplete" : ""}" data-dact="upload" id="lr-publish">${esc(n > 0 ? LF("Noch {0} Angaben", n) : L("Bereit"))}</button>`;
      }
    }
  }
  if (!sold) {
    html += `<div class="quick-row" style="margin-top:12px">
      ${frozen ? "" : `<button class="quick" data-dact="regen"${lockAttr}><span class="qic">${icon("refresh", 19)}</span><span>${L("Neu")}</span></button>`}
      ${live
        ? `<button class="quick danger" data-dact="end"${lockAttr}><span class="qic">${icon("trash", 19)}</span><span>${L("Beenden")}</span></button>`
        : `<button class="quick danger" data-dact="discard"${lockAttr}><span class="qic">${icon("trash", 19)}</span><span>${L("Verwerfen")}</span></button>`}
    </div>`;
  }
  if ((live || sold) && d.item_url) {
    html += `<a class="btn-secondary" style="margin-top:12px;text-decoration:none" href="${esc(d.item_url)}" target="_blank">${L("Bei eBay öffnen")}&nbsp;${icon("link", 14)}</a>`;
  }
  return html;
}

function drow(act, ic, color, label, value) {
  return `<button type="button" class="irow tap" data-dact="${act}">
    <span class="ric" style="background:${color}">${icon(ic, 15)}</span>
    <span class="rlabel">${esc(L(label))}</span>
    <span class="rvalue">${esc(L(value))}</span>
    <span class="chev">${icon("chevron", 15)}</span></button>`;
}

function wireDraftSection(d) {
  const body = $("detailBody");
  if (!body) return;
  const formatFrozen = !!d.published || d.status === "ended";
  const frozen = formatFrozen;
  const locked = isDraftUploadBusy(d);
  body.querySelectorAll("[data-dact]").forEach((b) => {
    b.onclick = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      handleDraftAction(d, b.dataset.dact, b);
    };
  });
  body.querySelectorAll("[data-dsw]").forEach((sw) => {
    sw.onchange = () => {
      const minEl = body.querySelector("[data-dbo-min]");
      const minVal = (minEl && minEl.value.trim()) ? minEl.value.trim() : null;
      doAction(d.id, sw.dataset.dsw, minVal)
        .catch((e) => { toast(e.message); sw.checked = !sw.checked; });
    };
  });
  const boMin = body.querySelector("[data-dbo-min]");
  if (boMin) {
    const saveBoMin = () => {
      if (boMin.hidden || boMin.disabled) return;
      doAction(d.id, "offermin", boMin.value.trim() || null).catch((e) => toast(e.message));
    };
    boMin.onchange = saveBoMin;
    boMin.onblur = saveBoMin;
  }
  body.querySelectorAll(".ph-kachel[data-pi]").forEach((fig) => {
    if (locked || frozen) return;
    fig.onclick = (ev) => {
      if (ev.target.closest(".ph-sort")) return;
      openDraftPhotoMenu(d, Number(fig.dataset.pi) || 0);
    };
  });
  body.querySelectorAll("[data-dseg]").forEach((seg) => {
    const kind = seg.dataset.dseg;
    seg.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        if (b.classList.contains("on") || b.disabled) return;
        if (isDraftUploadBusy(d)) {
          toast(L("Upload läuft gerade — einen Moment."));
          return;
        }
        const prevOn = [...seg.querySelectorAll("button")].find((x) => x.classList.contains("on"));
        seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
        doAction(d.id, kind, b.dataset.v).catch((e) => {
          toast(e.message);
          // Optimistic UI zurückdrehen bei Fehler
          seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === prevOn));
        });
      };
    });
  });
  const qs = $("qSend");
  if (qs) qs.onclick = async () => {
    const text = $("qInput").value.trim();
    if (!text) return;
    try {
      await post(`/api/app/draft/${d.id}/answer`, { text });
      refreshDetail(true);
    } catch (e) { toast(e.message); }
  };
  fillPreflightChecklist(d);
}

async function fillPreflightChecklist(d) {
  if (!d || !d.id || d.published || d.status === "ended") return;
  const item = (state.detail && state.detail.mode === "item") ? state.detail.data : null;
  const run = async () => {
    const ticket = preflightWins.begin();
    try {
      const pf = await api(`/api/app/draft/${d.id}/preflight`, { signal: ticket.signal });
      if (!ticket.isCurrent()) return;
      const det = state.detail;
      const cur = det && det.data && det.data.draft;
      if (!cur || cur.id !== d.id) return;
      cur._preflight = pf;
      applyListingValidation(cur, item);
    } catch (e) {
      if (e && e.superseded) return;
      applyListingValidation(d, item);
    }
  };
  if (preflightDedup && preflightDedup.run) return preflightDedup.run("pf:" + d.id, run);
  return run();
}

function jumpPreflightField(section, field) {
  const map = {
    photos: "lr-photos",
    product: "lr-product",
    offer: "lr-offer",
    shipping: "lr-shipping",
  };
  let el = fieldElForIssue(field);
  if (!el) el = $(map[section] || "lr-product");
  if (!el) return;
  try { el.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (_) { el.scrollIntoView(); }
  el.classList.add("lr-flash");
  const t = setTimeout(() => el.classList.remove("lr-flash"), 1600);
  if (typeof t === "number") { /* timer id — kein Kosmetik-Hide, nur Fokus-Ring */ }
}

const _draftActionTail = new Map();

async function doAction(draftId, action, value = null, opts = {}) {
  if (action !== "upload" && state.draftBusy && state.draftBusy[draftId]) {
    const err = new Error(L("Upload läuft gerade — einen Moment."));
    toast(err.message);
    throw err;
  }
  const prev = _draftActionTail.get(draftId) || Promise.resolve();
  let release;
  const gate = new Promise((r) => { release = r; });
  _draftActionTail.set(draftId, prev.then(() => gate, () => gate));
  try {
    await prev.catch(() => {});
    if (action !== "upload" && state.draftBusy && state.draftBusy[draftId]) {
      const err = new Error(L("Upload läuft gerade — einen Moment."));
      toast(err.message);
      throw err;
    }
    const det = state.detail && state.detail.data && state.detail.data.draft;
    const rev = (det && det.id === draftId && det.revision != null) ? det.revision : undefined;
    const payload = { action, value };
    if (rev !== undefined) payload.revision = rev;
    const r = await post(`/api/app/draft/${draftId}/action`, payload);
    if (action === "upload") markDraftBusy(draftId, true);
    mergeDraftPayload(draftId, r);
    const detNow = state.detail;
    const light = DRAFT_LIGHT_ACTIONS.has(action);
    if (listingInputBusy()) {
      state._detailPaintQueued = true;
      return r;
    }
    const st = captureDetailViewState(detNow);
    if (light && detNow && $("detailPanes")) {
      renderDetail(detNow, { preserve: true, ebayOnly: true });
      restoreDetailViewState(detNow, st);
    } else {
      await refreshDetail({ force: true, preserve: true, ebayOnly: light });
    }
    return r;
  } finally {
    release();
  }
}


async function confirmPublishDraft(d, btn) {
  if (!d || !d.id) return;
  let pf = null;
  try {
    pf = await api(`/api/app/draft/${d.id}/preflight`);
  } catch (e) {
    toast(e.message || L("Prüfung fehlgeschlagen"), "xmark");
    return;
  }
  if (pf && pf.valid === false) {
    const issues = pf.issues || [];
    const first = issues.find((iss) => iss.blocking !== false) || issues[0];
    if (first) jumpPreflightField(first.section, first.field || first.field_id);
    try { trackFunnel("review_required", { status: "preflight" }); } catch (_) { /* */ }
    return;
  }
  const isAuc = d.format === "AUCTION";
  const price = eur(d.price);
  await ensureEbayPolicies();
  const photos = d.photos || [];
  const strip = photos.length
    ? `<div class="pc-strip">${photos.map((p, i) => `
        <figure class="${i === 0 ? "is-hero" : ""}">
          <img src="${esc(p.url || "")}" alt="">
          ${i === 0 ? `<span class="ph-haupt">${esc(L("Hauptfoto"))}</span>` : ""}
        </figure>`).join("")}</div>`
    : `<div class="pc-row is-miss" id="lr-photos"><span>${esc(L("Hauptfoto"))}</span><span>—</span></div>`;
  const f = fulfillmentForDraft(d);
  const ret = returnPolicyForDraft(d);
  const pol = d.policies || {};
  const aspects = d.aspects || {};
  const aspectNames = Object.keys(aspects).filter((k) => {
    const n = String(k || "").toLowerCase().replace(/\s+/g, "");
    return n && n !== "sku" && n !== "bestandeinheit" && n !== "bestandseinheit" && n !== "customlabel";
  });
  const aspectTxt = aspectNames.length
    ? aspectNames.slice(0, 8).join(" · ") + (aspectNames.length > 8 ? " …" : "")
    : "";
  const prow = (label, value, miss) =>
    `<div class="pc-row${miss ? " is-miss" : ""}"><span>${esc(L(label))}</span><span>${esc(value || "—")}</span></div>`;
  const body = `
    <div class="publish-confirm">
      ${strip}
      <p class="pc-title">${esc(d.title || L("Ohne Titel"))}</p>
      <div class="pc-rows">
        ${prow("Kategorie", d.category_name || L("Kategorie"), !d.category_name)}
        ${prow("Zustand", condLabel(d.condition, d.category_name), !d.condition)}
        ${prow("Artikelmerkmale", aspectTxt, false)}
        ${prow("Beschreibung", (d.description_plain || "").slice(0, 80) || "—", !(d.description_plain || "").trim())}
        ${prow("Preis", price ? price + " €" : "", !price)}
        ${isAuc ? "" : prow("Stückzahl", String(d.quantity || 1), false)}
        ${prow("Versandprofil", (f && f.name) || (pol.shipping ? L("Bereit") : ""), !pol.shipping)}
        ${prow("Versandkosten", f && f.cost ? (f.cost === "Kostenlos" ? L("Kostenlos") : f.cost) : "", false)}
        ${prow("Bearbeitungszeit", (f && f.handling) || "", false)}
        ${prow("Rücknahme", ret ? (ret.returnsAccepted ? L("aktiv") : L("nein")) : (pol.return ? L("Bereit") : ""), !pol.return)}
        ${prow("Zielmarktplatz", "eBay.de", false)}
      </div>
      <p class="pc-note">${esc(L("Zielmarktplatz eBay.de. Live erst nach diesem Tipp — kein zweiter automatischer Versuch bei unklarer Antwort."))}</p>
    </div>`;
  openSheet(
    L("Bei eBay veröffentlichen?"),
    L("Kurz prüfen — danach geht der Entwurf live."),
    body,
    async () => {
      closeSheet();
      markDraftBusy(d.id, true);
      if (btn) btn.disabled = true;
      try { renderDetail(state.detail, { preserve: true, ebayOnly: true }); } catch (_) { /* */ }
      try { trackFunnel("publish_started"); } catch (_) { /* */ }
      try {
        await doAction(d.id, "upload");
        try { trackFunnel("publish_succeeded"); } catch (_) { /* */ }
      } catch (e) {
        markDraftBusy(d.id, false);
        try { trackFunnel("publish_failed", { code: "upload" }); } catch (_) { /* */ }
        toast(e.message);
        refreshDetail(true);
      }
    },
    "Jetzt bei eBay veröffentlichen");
}

async function openShippingPolicySheet(d) {
  openSheet(L("Versandprofil"), L("Richtlinie wählen"),
    `<div class="stage-line"><span class="spinner"></span> ${L("Wird geladen …")}</div>`, null);
  try {
    const r = await api("/api/app/ebay/policies");
    const cur = (r.current || {}).fulfillment_policy_id;
    const opts = (r.fulfillment || []).map((p) => `
      <button type="button" class="opt${p.id === cur ? " on" : ""}" data-pid="${esc(p.id)}">
        <span>${esc(p.name || p.id)}
          <span class="opt-sub">${esc([p.service, p.cost === "Kostenlos" ? L("Kostenlos") : p.cost, p.handling].filter(Boolean).join(" · "))}</span>
        </span>
      </button>`).join("");
    openSheet(L("Versandprofil"), L("Business Policies deines eBay-Kontos. Keine US-Dienste."),
      `<div class="opt-list">${opts || `<p>${esc(L("Fehlt — Setup im Profil"))}</p>`}</div>`, null);
    $("sheetBody").querySelectorAll("[data-pid]").forEach((b) => {
      b.onclick = async () => {
        try {
          await post("/api/app/ebay/policies", { fulfillment_policy_id: b.dataset.pid });
          state.ebayPolicies = null;
          closeSheet();
          toast(L("Versandprofil"));
          refreshDetail(true);
        } catch (e) { toast(e.message); }
      };
    });
  } catch (e) {
    $("sheetErr").textContent = e.message;
  }
}

function handleDraftAction(d, act, btn) {
  if (act !== "upload" && isDraftUploadBusy(d)) {
    toast(L("Upload läuft gerade — einen Moment."));
    return;
  }
  if (btn && btn.disabled) return;
  if (act === "price") {
    openInput({ title: d.price ? "Preis ändern" : "Preis festlegen",
                hint: d.format === "AUCTION" ? "Startpreis der Auktion in Euro" : "Sofortkauf-Preis in Euro",
                value: eur(d.price) || "", mode: "decimal", ph: "16,90" },
      (v) => doAction(d.id, "price", v));
  } else if (act === "title") {
    openInput({ title: "Titel", hint: "Max. 80 Zeichen — Marke, Modell, Variante",
                value: d.title || "" }, (v) => doAction(d.id, "title", v));
  } else if (act === "desc") {
    const item = state.detail && state.detail.mode === "item" ? state.detail.data : null;
    const start = d.description_plain
      || (item && (item.scan_description || (item.analysis && item.analysis.description_plain)))
      || "";
    const SD = seroDetailApi();
    const plain = (SD && SD.ebayDescPlain) ? SD.ebayDescPlain(start, item) : String(start || "");
    openInput({ title: "Beschreibung", hint: "Dein Text ersetzt die automatische Beschreibung.",
                textarea: true, value: plain }, (v) => doAction(d.id, "desc", v));
  } else if (act === "cond") {
    if (isCardCategory(d.category_name)) {
      openOptions("Zustand", [
        { label: "Nicht bewertet (Ungraded)", value: "USED_VERY_GOOD",
          sel: d.condition !== "LIKE_NEW" },
        { label: "Professionell bewertet (Graded)", value: "LIKE_NEW",
          sel: d.condition === "LIKE_NEW" },
      ], (v) => doAction(d.id, "cond", v));
    } else {
      const opts = Object.keys(COND_LABELS).map((v) => ({
        label: L(COND_LABELS[v]), value: v, sel: d.condition === v,
      }));
      openOptions("Zustand", opts, (v) => doAction(d.id, "cond", v));
    }
  } else if (act === "qty") {
    openStepper(d.quantity, (v) => doAction(d.id, "qty", String(v)));
  } else if (act === "usk") {
    const opts = [0, 6, 12, 16, 18].map((n) => ({ label: LF("USK ab {0} freigegeben", n), value: String(n), sel: d.usk === n }));
    opts.push({ label: "Keine Angabe", value: "none", sel: d.usk === null || d.usk === undefined });
    openOptions("Altersfreigabe", opts, (v) => doAction(d.id, "uskset", v));
  } else if (act === "img") {
    if (!(d.photos || []).length) { toast(L("Keine Fotos")); return; }
    openDraftPhotoMenu(d, 0);
  } else if (act === "imgmain") {
    const i = Number(btn && btn.dataset && btn.dataset.i);
    if (!Number.isFinite(i)) return;
    doAction(d.id, "imgmain", String(i)).catch((e) => toast(e.message));
  } else if (act === "imgswap") {
    const i = Number(btn && btn.dataset && btn.dataset.i);
    const dir = Number(btn && btn.dataset && btn.dataset.dir);
    const n = (d.photos || []).length;
    if (!Number.isFinite(i) || !Number.isFinite(dir) || n < 2) return;
    const j = i + dir;
    if (j < 0 || j >= n) return;
    const order = [...Array(n).keys()];
    [order[i], order[j]] = [order[j], order[i]];
    doAction(d.id, "imgorder", order.join(",")).catch((e) => toast(e.message));
  } else if (act === "cardsearch") {
    const itemId = d.collection_item_id
      || (state.detail && state.detail.mode === "item" && state.detail.id);
    if (!itemId) { toast(L("Kein Sammlungsstück verknüpft")); return; }
    let item = (state.detail && state.detail.mode === "item" && state.detail.data)
      ? state.detail.data : null;
    if (!item || item.id !== itemId) {
      item = { id: itemId, category: d.category_name, name: d.identity_label || d.title, card: null };
    }
    openCardSearch(item);
  } else if (act === "cat") {
    openCategorySearch(d);
  } else if (act === "aspect") {
    const name = (btn && btn.dataset && btn.dataset.aspect) || "";
    if (!name) return;
    openInput({
      title: name,
      hint: L("Pflichtmerkmal für diese eBay-Kategorie"),
      value: aspectVal(d.aspects, name) || "",
    }, (v) => doAction(d.id, "aspect", name + String.fromCharCode(9) + v));
  } else if (act === "setup") {
    closeDetail();
    openSeroProfile();
    toast(L("Versand und Richtlinien im Profil prüfen"), "check");
  } else if (act === "shippolicy") {
    openShippingPolicySheet(d);
  } else if (act === "retry_list") {
    const itemId = d.collection_item_id;
    if (!itemId) { toast(L("Kein Stück zu diesem Entwurf")); return; }
    const item = (state.items || []).find((x) => x.id === itemId) || { id: itemId };
    startListingPrep(item, btn);
  } else if (act === "regen") {
    confirmSheet("Neu erstellen?", "Titel, Beschreibung und Preis werden neu generiert — manuelle Änderungen gehen verloren.", "Neu erstellen")
      .then((ok) => ok && doAction(d.id, "regen").catch((e) => toast(e.message)));
  } else if (act === "upload") {
    if (isDraftUploadBusy(d)) return;
    const item = (state.detail && state.detail.mode === "item") ? state.detail.data : null;
    const v = listingValidationFor(d, item);
    if (v.loading) return;
    const first = (v.issues || []).find((iss) => iss.blocking && iss.severity === "error");
    if (first) {
      const fid = first.field || first.fieldId;
      if (fid === "price") {
        handleDraftAction(d, "price", btn);
        return;
      }
      jumpPreflightField(first.section, fid);
      return;
    }
    confirmPublishDraft(d, btn);
  } else if (act === "save") {
    if (btn) btn.disabled = true;
    doAction(d.id, "save").catch((e) => toast(e.message)).finally(() => { if (btn) btn.disabled = false; });
  } else if (act === "discard") {
    confirmSheet("Listing-Entwurf verwerfen?", "Das Stück bleibt in deiner Sammlung.", "Verwerfen", true)
      .then(async (ok) => {
        if (!ok) return;
        const itemId = (state.detail && state.detail.mode === "item") ? state.detail.id : null;
        if (itemId) {
          state._skipEnsureDraft = state._skipEnsureDraft || {};
          state._skipEnsureDraft[itemId] = true;
        }
        try {
          await post(`/api/app/draft/${d.id}/action`, { action: "discard", value: null });
          toast(L("Entwurf verworfen"), "check");
          loadSales();
          loadCollection();
          if (itemId && state.detail) {
            state.detail.seg = "overview";
            await refreshDetail(true);
          } else {
            closeDetail();
          }
        } catch (e) {
          if (itemId && state._skipEnsureDraft) delete state._skipEnsureDraft[itemId];
          toast(e.message);
        }
      });
  } else if (act === "end") {
    confirmSheet("Listing beenden?", "Es wird sofort von eBay genommen. Das Stück bleibt in deiner Sammlung.", "Beenden", true)
      .then((ok) => ok && post(`/api/app/draft/${d.id}/action`, { action: "end", value: null })
        .then(() => { toast("Listing beendet"); refreshDetail(true); }).catch((e) => toast(e.message)));
  }
}

function openImageSheet(d, focusIdx = 0) {
  const n = (d.photos || []).length;
  const rows = d.photos.map((p, i) => {
    let label;
    if (!p.has_render) label = LF("Bild {0} — Original (kein Freisteller)", i + 1);
    else if (p.is_original) label = LF("Bild {0} — Original → Freisteller", i + 1);
    else label = LF("Bild {0} — Freisteller → Original", i + 1);
    return `<div class="img-row">
      <button type="button" class="img-row-thumb" data-edit="${i}" aria-label="${esc(L("Foto bearbeiten"))}">
        ${p.url ? `<img src="${esc(thumb(p.url, 240))}" alt="">` : ""}
      </button>
      <div class="img-row-acts">
        <button type="button" class="btn-secondary" data-edit="${i}">${icon("photo", 16)}<span>${L("Werkzeuge")}</span></button>
        <button class="btn-secondary" data-i="${i}" ${p.has_render ? "" : "disabled style='opacity:.45'"}>${label}</button>
        ${n > 1 ? `<button type="button" class="btn-plain" data-main="${i}" ${i === 0 ? "disabled" : ""}>${L("Als Hauptbild")}</button>
        <button type="button" class="btn-plain" data-mv="${i}" data-dir="-1" ${i === 0 ? "disabled" : ""}>${L("Nach vorn")}</button>
        <button type="button" class="btn-plain" data-mv="${i}" data-dir="1" ${i === n - 1 ? "disabled" : ""}>${L("Nach hinten")}</button>` : ""}
      </div>
    </div>`;
  }).join("");
  openSheet(L("Bilder"), L("Tippe auf ein Bild für die volle Werkzeugleiste — Reihenfolge und Hauptbild hier."),
    rows + `<button class="btn-secondary" id="rerenderAll" style="margin-top:10px">${icon("refresh", 16)}<span>Alle neu rendern</span></button>`, null);
  $("sheetBody").querySelectorAll("[data-edit]").forEach((b) => {
    b.onclick = () => { closeSheet(); openDraftPhotoMenu(d, Number(b.dataset.edit) || 0); };
  });
  $("sheetBody").querySelectorAll("[data-i]").forEach((b) => {
    b.onclick = async () => {
      try { await doAction(d.id, "imgtog", b.dataset.i); closeSheet(); }
      catch (e) { $("sheetErr").textContent = e.message; }
    };
  });
  $("sheetBody").querySelectorAll("[data-main]").forEach((b) => {
    b.onclick = async () => {
      try { await doAction(d.id, "imgmain", b.dataset.main); closeSheet(); openImageSheet(
        (state.detail && state.detail.data && state.detail.data.draft) || d); }
      catch (e) { $("sheetErr").textContent = e.message; }
    };
  });
  $("sheetBody").querySelectorAll("[data-mv]").forEach((b) => {
    b.onclick = async () => {
      const i = Number(b.dataset.mv);
      const dir = Number(b.dataset.dir);
      const order = [...Array(n).keys()];
      const j = i + dir;
      if (j < 0 || j >= n) return;
      [order[i], order[j]] = [order[j], order[i]];
      try {
        await doAction(d.id, "imgorder", order.join(","));
        closeSheet();
        openImageSheet((state.detail && state.detail.data && state.detail.data.draft) || d);
      } catch (e) { $("sheetErr").textContent = e.message; }
    };
  });
  $("rerenderAll").onclick = async () => {
    closeSheet();
    toast(L("Bilder werden im Hintergrund gerendert"), "refresh");
    try { await doAction(d.id, "imgren"); refreshDetail(true); }
    catch (e) { toast(e.message); }
  };
}

/* ═══════════════════ Sheets (Infrastruktur) ═══════════════════ */

function openSheet(title, hint, bodyHTML, onSave, saveLabel = "Übernehmen", destructive = false) {
  // Optionales 5./6. Argument ODER Objekt als 4. Argument: { fit, dismissible, onSave, saveLabel, destructive }
  let opts = {};
  if (onSave && typeof onSave === "object" && !Array.isArray(onSave) && typeof onSave.then !== "function"
      && typeof onSave !== "function") {
    opts = onSave;
    onSave = opts.onSave;
    if (opts.saveLabel != null) saveLabel = opts.saveLabel;
    if (opts.destructive != null) destructive = opts.destructive;
  }
  $("sheetTitle").textContent = L(title);
  $("sheetHint").textContent = hint ? L(hint) : "";
  $("sheetHint").hidden = !hint;
  $("sheetBody").innerHTML = bodyHTML;
  freeBlobs($("sheetBody"));   // Foto-Vorschauen nicht im Speicher liegen lassen
  $("sheetErr").textContent = "";
  const _sh = $("sheet"), _bd = $("sheetBackdrop");
  // Ein noch laufender Schließ-Vorgang muss abgebrochen werden: sein Timer
  // hätte sonst 260 ms später DIESES frisch geöffnete Sheet ausgeblendet —
  // zurück blieb die abgedunkelte, verkleinerte App ohne sichtbares Sheet.
  _sh.classList.remove("closing"); _bd.classList.remove("closing");
  _sh.style.pointerEvents = "";
  _bd.style.pointerEvents = "";
  _bd.hidden = false;
  _sh.hidden = false;
  const detEl = $("detail");
  const detailOpen = !!(detEl && !detEl.hidden);
  const wantRecede = opts.recede !== false && !detailOpen
    && !document.documentElement.classList.contains("vv-keyboard");
  $("viewApp").classList.toggle("recede", wantRecede);
  $("viewApp").classList.toggle("is-detail-open", detailOpen);
  const save = $("sheetSave");
  save.textContent = L(saveLabel);
  save.classList.toggle("destructive", destructive);
  save.hidden = !onSave;
  $("sheetCancel").hidden = !!opts.hideActions;
  _sh.classList.toggle("sheet-scan-done", !!opts.scanDone);
  _sh.classList.toggle("sheet-no-actions", !!opts.hideActions);
  /* Genereller Doppeltipp-Riegel: der Knopf sperrt sich beim ersten Tipp
     selbst und öffnet erst wieder, wenn der Handler durch ist. Vorher konnte
     man „Alle listen" oder „Konto löschen" mehrfach hintereinander auslösen —
     jeder Tipp ein eigener Server-Lauf. */
  save.onclick = onSave ? async (ev) => {
    if (save.disabled) return;
    save.disabled = true;
    try { await onSave(ev); }
    finally { if (!$("sheet").hidden) save.disabled = false; }
  } : null;
  save.disabled = false;
  $("sheetCancel").textContent = onSave ? L("Abbrechen") : L("Fertig");
  $("sheetCancel").onclick = closeSheet;
  if (!opts.hideActions) $("sheetCancel").hidden = false;
  const dismissible = opts.dismissible !== false;
  $("sheetBackdrop").onclick = dismissible ? closeSheet : null;
  // Optionsmenüs: Sheet auf Inhalt kürzen (kein riesiger Leerraum unter Fertig)
  // Filter mit Anwenden ebenfalls kompakt — der Inhalt ist kurz.
  // fit verkürzt nur optisch — max-height und Body-Scroll bleiben immer (CSS).
  const kompakt = opts.fit != null ? !!opts.fit : (!onSave || saveLabel === "Anwenden");
  _sh.classList.toggle("sheet-fit", kompakt);
  // Fokussiertes Feld im Sheet sichtbar halten (nicht document scrollen)
  const body = $("sheetBody");
  body.onfocusin = (ev) => {
    const t = ev.target;
    if (!t || !/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    try { t.scrollIntoView({ block: "nearest", inline: "nearest" }); } catch (_) { /* */ }
  };
}
function dismissSheetNow() {
  const sh = $("sheet"), bd = $("sheetBackdrop");
  if (state.stageOpen) {
    state.stageOpen = false;
    if (state.stageKeep) state.stageKeep = false;
    else post("/api/app/collection/stage/clear?" + devQ()).catch(() => {});
  }
  state._inputKey = null;
  $("viewApp").classList.remove("recede");
  $("viewApp").classList.remove("is-detail-open");
  if (sh) {
    sh.style.pointerEvents = "none";
    sh.style.transform = "";
    sh.classList.remove("closing");
    sh.classList.remove("sheet-inv");
    sh.hidden = true;
  }
  if (bd) {
    bd.style.pointerEvents = "none";
    bd.classList.remove("closing");
    bd.hidden = true;
  }
  setTimeout(flushQueuedDetailPaint, 0);
}

function closeSheet() {
  // Scan-Sheet ohne „Analysieren"/„Weiteres Foto" verlassen = Vorgang abgebrochen:
  // geparkte Fotos verwerfen, damit sie nicht in den nächsten Scan rutschen.
  if (state.stageOpen) {
    state.stageOpen = false;
    if (state.stageKeep) state.stageKeep = false;
    else post("/api/app/collection/stage/clear?" + devQ()).catch(() => {});
  }
  state._inputKey = null;
  const savedScroll = state._sheetScroll;
  state._sheetScroll = null;
  const sh = $("sheet"), bd = $("sheetBackdrop");
  $("viewApp").classList.remove("recede");
  $("viewApp").classList.remove("is-detail-open");
  if (sh.hidden) {
    if (savedScroll) restoreDetailViewState(state.detail, savedScroll);
    flushQueuedDetailPaint();
    return;
  }
  // Sofort keine Taps mehr — sonst landet der Finger auf Fertig/Backdrop
  // und der nächste Tipp (Löschen, Preis) geht ins Leere.
  sh.style.pointerEvents = "none";
  if (bd) bd.style.pointerEvents = "none";
  sh.style.transform = "";
  sh.classList.add("closing"); bd.classList.add("closing");
  setTimeout(() => {
    // Wurde inzwischen ein neues Sheet geöffnet, hat openSheet „closing"
    // entfernt — dann gehört dieses Sheet nicht mehr uns.
    if (!sh.classList.contains("closing")) return;
    sh.hidden = true; bd.hidden = true;
    sh.classList.remove("closing"); bd.classList.remove("closing");
    sh.classList.remove("sheet-inv");
    sh.style.pointerEvents = "";
    if (bd) bd.style.pointerEvents = "";
    if (savedScroll) restoreDetailViewState(state.detail, savedScroll);
    flushQueuedDetailPaint();
  }, 260);
}

document.addEventListener("focusin", (e) => {
  const t = e.target;
  if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) {
    document.documentElement.classList.add("input-focus");
  }
});
document.addEventListener("focusout", () => {
  setTimeout(() => {
    if (!listingInputBusy()) {
      document.documentElement.classList.remove("input-focus");
      flushQueuedDetailPaint();
    }
  }, 80);
});

/* Escape schließt genau eine Ebene: erst das Sheet, dann eine Stufe im
   Einstellungs-Stapel. Vorher tat die Taste in den Einstellungen gar nichts. */
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const sh = $("sheet");
  if (sh && !sh.hidden) {
    e.preventDefault();
    closeSheet();
    return;
  }
  const sv = $("settingsView");
  if (sv && !sv.hidden && typeof settingsNav !== "undefined") {
    e.preventDefault();
    settingsNav.pop();
  }
});

/* Sicherheitsnetz: Die App darf NIE abgedunkelt stehenbleiben, wenn nichts
   darüber liegt. Deckt auch Wege ab, die wir noch nicht kennen — etwa einen
   Handler, der mitten im Ablauf abbricht. */
function pruefeSchleier() {
  zeigeErgebnisWennFrei();
  const sichtbar = (el) => el && !el.hidden && !el.classList.contains("closing");
  const offen = sichtbar($("sheet")) || sichtbar($("detail")) || !!document.querySelector(".party:not(.out)");
  if (!offen) $("viewApp").classList.remove("recede");
}
setInterval(pruefeSchleier, 1200);
document.addEventListener("visibilitychange", () => { if (!document.hidden) pruefeSchleier(); });

/* Griff-Geste: Sheet nach unten ziehen schließt es */
(() => {
  const sh = $("sheet");
  const handle = $("sheetHead") || document.querySelector(".sheet-grip");
  if (!sh || !handle) return;
  let sy = null;
  handle.style.touchAction = "none";
  handle.addEventListener("pointerdown", (e) => {
    if (e.target.closest && e.target.closest("#sheetBody, .sheet-actions, input, textarea, button")) return;
    sy = e.clientY;
    try { handle.setPointerCapture(e.pointerId); } catch (_) { /* */ }
  });
  handle.addEventListener("pointermove", (e) => {
    if (sy === null) return;
    sh.style.transition = "none";
    sh.style.transform = `translateY(${Math.max(0, e.clientY - sy)}px)`;
  });
  const end = (e) => {
    if (sy === null) return;
    const dy = e.clientY - sy; sy = null;
    sh.style.transition = "";
    if (dy > 90) closeSheet();
    else sh.style.transform = "";
  };
  handle.addEventListener("pointerup", end);
  handle.addEventListener("pointercancel", end);
})();

function openInput(cfg, onSubmit) {
  const key = String(cfg.title || "") + ":" + (cfg.mode || "") + ":" + (cfg.textarea ? "ta" : "in");
  const sh = $("sheet");
  const existing = $("sheetField");
  if (sh && !sh.hidden && state._inputKey === key && existing) {
    try { existing.focus(); } catch (_) { /* */ }
    return;
  }
  state._inputKey = key;
  state._sheetScroll = captureDetailViewState(state.detail);
  const body = cfg.textarea
    ? `<textarea id="sheetField" autocomplete="off" enterkeyhint="enter" placeholder="${esc(L(cfg.ph || ""))}">${esc(cfg.value || "")}</textarea>`
    : `<input id="sheetField" type="text" ${cfg.mode ? `inputmode="${cfg.mode}"` : ""}
        autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false"
        enterkeyhint="done" value="${esc(cfg.value || "")}" placeholder="${esc(L(cfg.ph || ""))}">`;
  openSheet(cfg.title, cfg.hint, body, {
    recede: false,
    onSave: async () => {
      if (state._inputBusy) return;
      state._inputBusy = true;
      try {
        const v = $("sheetField") ? $("sheetField").value.trim() : "";
        await onSubmit(v);
        closeSheet();
      } catch (e) {
        $("sheetErr").textContent = e.message;
      } finally {
        state._inputBusy = false;
      }
    },
  });
  const field = $("sheetField");
  const focusField = () => {
    if (!field || !field.isConnected) return;
    try { field.focus(); } catch (_) { /* */ }
    try {
      const n = (field.value || "").length;
      if (typeof field.setSelectionRange === "function") field.setSelectionRange(n, n);
    } catch (_) { /* */ }
  };
  if (field && typeof requestAnimationFrame === "function") {
    requestAnimationFrame(focusField);
    setTimeout(focusField, 60);
  } else if (field) {
    focusField();
  }
}

function openOptions(title, options, onPick) {
  const body = `<div class="opt-list">` + options.map((o) =>
    `<button class="opt ${o.sel ? "sel" : ""}" data-v="${esc(o.value)}">
       <span>${esc(L(o.label))}</span><span class="tick">${icon("check", 17)}</span></button>`).join("") + `</div>`;
  openSheet(title, "", body, null);
  $("sheetBody").querySelectorAll(".opt").forEach((b) => {
    b.onclick = async () => {
      try { await onPick(b.dataset.v); closeSheet(); }
      catch (e) { $("sheetErr").textContent = e.message; }
    };
  });
}

function openStepper(current, onSubmit) {
  let val = Math.max(1, current || 1);
  openSheet("Stückzahl", "", `
    <div class="stepper">
      <button type="button" class="stbtn" id="stMinus" aria-label="${esc(L("Weniger"))}">${icon("minus", 22)}</button>
      <span class="stval" id="stVal">${val}</span>
      <button type="button" class="stbtn" id="stPlus" aria-label="${esc(L("Mehr"))}">${icon("plus", 22)}</button>
    </div>`,
    async () => {
      try { await onSubmit(val); closeSheet(); }
      catch (e) { $("sheetErr").textContent = e.message; }
    });
  $("stMinus").onclick = () => { val = Math.max(1, val - 1); $("stVal").textContent = val; };
  $("stPlus").onclick = () => { val = Math.min(1000, val + 1); $("stVal").textContent = val; };
}

function confirmSheet(title, text, okLabel = "Ja", destructive = false) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (v) => {
      if (settled) return;
      settled = true;
      closeSheet();
      resolve(v);
    };
    openSheet(title, text, "", () => finish(true), okLabel, destructive);
    $("sheetCancel").onclick = () => finish(false);
    $("sheetBackdrop").onclick = () => finish(false);
    // Android-Zurück / closeSheet von außen: Promise nicht hängen lassen
    const sh = $("sheet");
    const watch = () => {
      if (settled) return;
      if (sh.hidden || sh.classList.contains("closing")) finish(false);
      else requestAnimationFrame(watch);
    };
    requestAnimationFrame(watch);
  });
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    try { holoCtl.deactivate(); } catch (_) { /* */ }
  }
});
document.addEventListener("pagehide", () => {
  try { holoCtl.deactivate(); } catch (_) { /* */ }
});

boot();

/* Android-/Browser-Zurück: Overlay → Tab → Exit-Frage (nicht die App killen) */
(() => {
  if (!SM.installBackController) return;
  const sheetVisible = () => {
    const sh = $("sheet");
    return !!(sh && !sh.hidden && !sh.classList.contains("closing"));
  };
  const detailVisible = () => {
    const d = $("detail");
    return !!(d && !d.hidden && !d.classList.contains("closing"));
  };
  const dismissTopParty = () => {
    const el = document.querySelector(".party:not(.out)");
    if (!el) return false;
    el.classList.add("out");
    setTimeout(() => { try { el.remove(); } catch (_) { /* */ } }, 300);
    return true;
  };
  const currentTabId = () =>
    TAB_ORDER.find((t) => { const p = $(t); return p && !p.hidden; }) || "tabHome";
  SM.installBackController({
    snapshot() {
      const depth = (typeof settingsNav !== "undefined" && settingsNav.stack)
        ? settingsNav.stack.length : 0;
      return {
        sheetOpen: sheetVisible(),
        partyOpen: !!document.querySelector(".party:not(.out)"),
        settingsDepth: depth,
        detailOpen: detailVisible(),
        tab: currentTabId(),
        homeTab: "tabHome",
      };
    },
    run(action) {
      if (action === "closeSheet") closeSheet();
      else if (action === "closeParty") dismissTopParty();
      else if (action === "settingsPop" && typeof settingsNav !== "undefined") settingsNav.pop();
      else if (action === "settingsClose" && typeof settingsNav !== "undefined") settingsNav.close();
      else if (action === "closeDetail") closeDetail();
      else if (action === "goHome") switchTab("tabHome");
    },
    confirmExit() {
      return confirmSheet(
        L("App verlassen?"),
        L("SERO schließen und zurück zum Startbildschirm."),
        L("App verlassen"),
        true,
      );
    },
  });
})();

/* Seiten-Wischen zwischen den Haupt-Tabs — Achsensperre + Horizontalfächen ausnehmen */
(() => {
  const ORDER = ["tabCollection"];
  let pid = null, sx = null, sy = null, axis = null;
  const reset = () => { pid = null; sx = sy = null; axis = null; };
  const modalOpen = () => !!document.querySelector(".party:not(.out)");
  const onDown = (e) => {
    if (e.isPrimary === false) return;
    pid = e.pointerId; sx = e.clientX; sy = e.clientY; axis = null;
  };
  const onMove = (e) => {
    if (pid === null || e.pointerId !== pid || sx === null) return;
    if (!axis) axis = SM.gestures.axisLock(e.clientX - sx, e.clientY - sy);
  };
  const onUp = (e) => {
    if (pid === null || (e.pointerId != null && e.pointerId !== pid) || sx === null) { reset(); return; }
    const dx = e.clientX - sx, dy = e.clientY - sy;
    const target = e.target;
    const ok = SM.gestures.shouldAllowTabSwipe({
      dx, dy, target,
      sheetOpen: !$("sheet").hidden,
      detailOpen: !$("detail").hidden,
      modalOpen: modalOpen(),
    });
    reset();
    if (!ok) return;
    const cur = ORDER.findIndex((id) => !$(id).hidden);
    if (cur === -1) return;
    const next = ORDER[cur + (dx < 0 ? 1 : -1)];
    if (next) switchTab(next);
  };
  if (window.PointerEvent) {
    document.addEventListener("pointerdown", onDown, { passive: true });
    document.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerup", onUp, { passive: true });
    document.addEventListener("pointercancel", reset, { passive: true });
  } else {
    document.addEventListener("touchstart", (e) => {
      const t = e.touches[0]; if (!t) return;
      onDown({ pointerId: 1, clientX: t.clientX, clientY: t.clientY, isPrimary: true });
    }, { passive: true });
    document.addEventListener("touchmove", (e) => {
      const t = e.touches[0]; if (!t) return;
      onMove({ pointerId: 1, clientX: t.clientX, clientY: t.clientY });
    }, { passive: true });
    document.addEventListener("touchend", (e) => {
      const t = e.changedTouches[0]; if (!t) return;
      onUp({ pointerId: 1, clientX: t.clientX, clientY: t.clientY, target: e.target });
    }, { passive: true });
    document.addEventListener("touchcancel", reset, { passive: true });
  }
})();

/* Konto löschen — UI liegt in Konto & Profil (sero-profile.js) */
document.addEventListener("click", (e) => {
  if (!e.target.closest("#profDelete")) return;
  /* Legacy-ID: zur Einstellungs-Gefahrenzone weiterleiten */
  if (typeof settingsNav !== "undefined" && state.me) {
    settingsNav.openRoot("account", "Konto & Profil",
      (b) => { if (typeof renderAccountPane === "function") renderAccountPane(b, state.me); },
      e.target);
  }
});

async function openBulkReviewSheet(idList) {
  const ids = (idList || Object.keys(state.selectedDrafts || {})).map(String).filter(Boolean);
  if (!ids.length) {
    toast(L("Entwürfe auswählen"));
    return;
  }
  const rows = ((state.sales && state.sales.drafts) || []).filter((r) => ids.includes(String(r.draft_id)));
  if (!rows.length) {
    toast(L("Entwürfe auswählen"));
    return;
  }
  state._bulkReviewIds = ids;
  const summaries = [];
  for (const r of rows) {
    let pf = { valid: false, issues: [{ message: L("Prüfung fehlgeschlagen") }] };
    try {
      pf = await api(`/api/app/draft/${r.draft_id}/preflight`);
    } catch (_) { /* */ }
    summaries.push({ row: r, pf });
  }
  const okOnes = summaries.filter((s) => s.pf && s.pf.valid);
  const skipN = summaries.length - okOnes.length;
  const body = `<div class="bulk-sum">${summaries.map(({ row: r, pf }) => {
    const fmt = saleFormatLabel(r);
    const price = r.price != null ? money(parseFloat(String(r.price))) : "—";
    const ship = saleShippingLabel(r);
    const cond = condLabel(r.condition, r.category_name);
    const ready = pf.valid
      ? `<span class="schip live">${esc(L("Bereit"))}</span>`
      : `<span class="schip err">${esc(L("Unvollständig"))}</span>`;
    const issues = (!pf.valid && pf.issues)
      ? pf.issues.slice(0, 6).map((iss) =>
        `<i class="bulk-sum-err">${esc(iss.message || L("Angaben unvollständig"))}</i>`).join("")
      : "";
    const skip = pf.valid ? "" : `<i class="bulk-sum-err">${esc(L("Übersprungen — unvollständig"))}</i>`;
    return `<button type="button" class="bulk-sum-row${pf.valid ? "" : " is-blocked"}" data-review-item="${esc(r.item_id || "")}" data-review-draft="${esc(r.draft_id)}">
      ${r.photo ? `<img src="${esc(thumb(r.photo, 120))}" alt="">` : `<span class="mv-ph">${MONO_PH}</span>`}
      <div class="bulk-sum-b">
        <b>${esc(r.title || L("Stück"))}</b>
        <span>${esc(cond)} · ${esc(fmt)} · ${esc(price)} · ${esc(ship)}</span>
        ${ready}${issues || skip}
      </div>
    </button>`;
  }).join("")}</div>
  <p class="sheet-hint">${L("Nur die Häkchen gehen live — jeweils mit Preflight.")}</p>
  <p class="sheet-hint">${L("Das lässt sich nicht rückgängig machen (Listings kannst du danach auf eBay beenden).")}</p>`;
  const bindRows = () => {
    document.querySelectorAll(".bulk-sum-row[data-review-draft]").forEach((b) => {
      b.onclick = () => {
        closeSheet();
        const itemId = b.dataset.reviewItem;
        const draftId = b.dataset.reviewDraft;
        if (itemId) openItemDetail(itemId, "ebay");
        else openDraftDetail(draftId);
      };
    });
  };
  if (!okOnes.length) {
    openSheet(L("Zusammenfassung vor dem Publish"), L("Kein Entwurf ist bereit."), body, null);
    setTimeout(bindRows, 0);
    return;
  }
  const saveLab = LF("{0} Stück auf eBay hochladen", okOnes.length);
  openSheet(L("Zusammenfassung vor dem Publish"),
    LF("{0} von {1} bereit", okOnes.length, summaries.length),
    body,
    async () => {
      const save = $("sheetSave");
      const cancel = $("sheetCancel");
      if (save) save.disabled = true;
      if (cancel) cancel.disabled = true;
      $("sheetBackdrop").onclick = null;
      const wanted = okOnes.map((s) => s.row.draft_id);
      $("sheetBody").innerHTML = `<p class="bulk-prog" id="bulkProg">${esc(LF("Stück {0} von {1}", 1, wanted.length))}</p>
        <p class="bulk-prog-sub" id="bulkProgSub">${esc(okOnes[0].row.title || L("Stück"))}</p>
        <p class="sheet-hint">${esc(L("Nur geprüfte Entwürfe gehen nacheinander live — jeweils mit Preflight."))}</p>`;
      state._bulkReviewIds = null;
      try {
        const r = await post("/api/app/sales/publish-drafts", {
          draft_ids: wanted,
        });
        const sent = Number(r && r.count) || wanted.length;
        let left = wanted.map(String);
        for (let i = 0; i < 40; i++) {
          try { await loadSales(); } catch (_) { /* */ }
          const drafts = ((state.sales && state.sales.drafts) || []);
          left = wanted.filter((id) => drafts.some((d) => String(d.draft_id) === String(id)
            && d.status !== "published"));
          const done = wanted.length - left.length;
          const cur = drafts.find((d) => left.includes(String(d.draft_id)));
          const prog = $("bulkProg");
          if (prog) prog.textContent = LF("Stück {0} von {1}", Math.min(done + 1, wanted.length), wanted.length);
          const sub = $("bulkProgSub");
          if (sub) sub.textContent = (cur && cur.title) || L("Stück");
          if (!left.length) break;
          if ($("sheet").hidden) break;
          await new Promise((res) => setTimeout(res, 2500));
        }
        try { await loadSales(true); } catch (_) { /* */ }
        const drafts = ((state.sales && state.sales.drafts) || []);
        const active = ((state.sales && state.sales.active) || []);
        const published = wanted.filter((id) => active.some((d) => String(d.draft_id) === String(id))).length;
        const failed = wanted.length - published;
        const keep = {};
        drafts.forEach((d) => {
          if (wanted.map(String).includes(String(d.draft_id))) keep[d.draft_id] = true;
        });
        state.selectedDrafts = keep;
        state.salesSelectMode = Object.keys(keep).length > 0;
        closeSheet();
        toast(LF("{0} veröffentlicht, {1} unvollständig, {2} fehlgeschlagen",
          published, skipN, failed), published ? "check" : "xmark");
        renderSales();
        void sent;
      } catch (err) {
        if ($("sheetErr")) $("sheetErr").textContent = err.message;
        if (save) save.disabled = false;
        if (cancel) cancel.disabled = false;
      }
    }, saveLab);
  setTimeout(bindRows, 0);
}

document.addEventListener("click", async (e) => {
  if (!e.target.closest("#bulkPublish")) return;
  const ids = Object.keys(state.selectedDrafts || {});
  openBulkReviewSheet(ids);
});
renderScanMode();
loadScanSession();
