/* SERO v4 — Sammlungs-App: Dashboard, Scanner, Portfolio, Verkaufs-Hub, Profil. */
"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  me: null, settings: null,
  items: [], stats: null, history: [], listingsMap: {},
  dash: null, sales: null,
  filter: { cat: "Alle", fav: false, wish: false, dup: false, listed: false, draft: false, sold: false, tag: null },
  sort: "new",
  colPollTimer: null, scanPollTimer: null,
  detail: null,
  addFiles: [], dryRun: false, salesBucket: "active",
};

/* ═══════════════════ Icons (SF-Symbols-Stil) ═══════════════════ */

function icon(name, size = 20) {
  const P = {
    home: '<path d="M4.5 11.5L12 4.5l7.5 7v7c0 .8-.7 1.5-1.5 1.5h-3.5v-5.5h-5V20H6c-.8 0-1.5-.7-1.5-1.5z"/>',
    camera: '<path d="M4 8.5C4 7.7 4.7 7 5.5 7h2l1.2-1.8C9 4.7 9.5 4.5 10 4.5h4c.5 0 1 .2 1.3.7L16.5 7h2c.8 0 1.5.7 1.5 1.5v8c0 .8-.7 1.5-1.5 1.5h-13C4.7 18 4 17.3 4 16.5z"/><circle cx="12" cy="12.4" r="3.1"/>',
    scanframe: '<path d="M4.5 8V6c0-.8.7-1.5 1.5-1.5h2M16 4.5h2c.8 0 1.5.7 1.5 1.5v2M19.5 16v2c0 .8-.7 1.5-1.5 1.5h-2M8 19.5H6c-.8 0-1.5-.7-1.5-1.5v-2"/><rect x="8" y="7.5" width="8" height="9" rx="1.5"/>',
    photo: '<rect x="4" y="5.5" width="16" height="13" rx="2.5"/><circle cx="9" cy="10" r="1.5" fill="currentColor" stroke="none"/><path d="M5.5 17l4-4 2.5 2.5 3.5-3.5 3 3"/>',
    stack: '<path d="M4.5 7.5L12 4l7.5 3.5L12 11z"/><path d="M4.5 12L12 15.5 19.5 12"/><path d="M4.5 16.5L12 20l7.5-3.5"/>',
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
  };
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${P[name] || ""}</svg>`;
}

function mountStaticIcons() {
  // Login: die drei Zeilen erklären das Produkt VOR der Anmeldung
  document.querySelectorAll(".lf-ic[data-ic]").forEach((s) => { s.innerHTML = icon(s.dataset.ic, 17); });
  const su = $("loginSignup");
  if (su) su.onclick = () => window.open("https://seromunich.com", "_blank");
  $("btnCamera").innerHTML = `<img src="assets/monogram-white.png" alt="Scan" class="cam-mono">`;
  $("colSearchIcon").innerHTML = icon("search", 17);
  const camBtn = document.createElement("button");
  camBtn.className = "search-cam";
  camBtn.innerHTML = icon("camera", 18);
  camBtn.onclick = (e) => { e.stopPropagation(); $("cameraInput").click(); };
  $("colSearchBox").appendChild(camBtn);
  $("btnSort").innerHTML = icon("sort", 18);
  $("btnFilter").innerHTML = icon("sliders", 18);
  $("detailClose").innerHTML = icon("chevdown", 20);
  $("detailTrash").innerHTML = icon("trash", 18);
  $("emptyAdd").innerHTML = icon("scanframe", 18) + "<span>" + L("Erstes Stück scannen") + "</span>";
  $("scanHeroIcon").innerHTML = icon("scanframe", 44);
  $("btnScanNow").innerHTML = icon("camera", 18) + "<span>" + L("Scannen") + "</span>";
  $("btnScanGallery").innerHTML = icon("photo", 19);
  const tabIcons = { tabHome: "home", tabCollection: "stack", tabSales: "bag", tabProfile: "person" };
  document.querySelectorAll(".tab").forEach((t) => {
    t.querySelector(".tic").innerHTML = icon(tabIcons[t.dataset.tab], 24);
  });
  // Echte Icons statt Emoji in den Bedienelementen (Emoji rendern je OS anders)
  document.querySelectorAll("#scanModeSeg button").forEach((b) => {
    b.innerHTML = icon(b.dataset.m === "sell" ? "bag" : "stack", 14)
      + `<span>${L(b.dataset.m === "sell" ? "Verkauf" : "Sammlung")}</span>`;
  });
}

/* ═══════════════════ Basis ═══════════════════ */

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
  t._h = setTimeout(() => t.classList.remove("show"), action ? 6000 : 3500);
}

/* ── Entfernen mit Rückgängig (statt Nachfrage-Dialog) ── */
function removeItemWithUndo(item) {
  state.items = state.items.filter((i) => i.id !== item.id);
  renderCollection();
  const timer = setTimeout(() => {
    post(`/api/app/collection/item/${item.id}/delete`).catch(() => {}).finally(loadCollection);
  }, 6000);
  toast("Aus Sammlung entfernt", "trash", {
    label: "Rückgängig",
    fn: () => { clearTimeout(timer); loadCollection(); toast("Wiederhergestellt", "check"); },
  });
}

/* ── Zeit-Bilanz: die ehrliche Rechnung aus ECHTEN Nutzungsdaten ── */
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
       <div class="pwm"><h4>${L("Von Hand")}</h4><div class="v tnum">~13 ${L("Std")}</div>
         <p>${L("Karte bestimmen, verkaufte Angebote durchsehen, Foto zuschneiden, Titel und Pflichtfelder setzen — rund acht Minuten pro Stück.")}</p></div>
       <div class="pwm win"><h4>${L("Mit SERO")}</h4><div class="v tnum">~100 ${L("Min")}</div>
         <p>${L("Fotografieren, Ergebnis prüfen, freigeben — rund eine Minute pro Stück. 100 Karten, 100 Minuten.")}</p></div>
     </div>
     <p class="pw-foot">${L("Von Hand rund 8 Minuten je Stück (Karte bestimmen, Marktwert, Foto, Titel und Pflichtfelder). Mit SERO rund 1 Minute — das ist nicht die Scan-Dauer, sondern die ehrliche Version inklusive Hinlegen, Prüfen und Freigeben.")}</p>
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
  const sub = [item.category, item.card && item.card.set_name,
    item.card && item.card.rarity].filter(Boolean).join(" · ");
  const photo = thumb(item.photos && item.photos[0], 720) || (item.card && item.card.image);
  const val = item.est_value !== null && item.est_value !== undefined ? item.est_value : null;
  const el = document.createElement("div");
  el.className = "party scanres";
  el.innerHTML = `
    <div class="party-card res-card">
      <div class="res-grip"></div>
      <div class="res-badge">${icon("check", 15)}<span>${L("Erkannt")}</span></div>
      ${photo ? `<div class="res-photo"><img src="${esc(photo)}" alt=""></div>`
              : `<div class="res-photo">${MONO_PH}</div>`}
      <h2 class="res-name">${esc(item.name || L("Neues Stück"))}</h2>
      ${sub ? `<p class="res-sub">${esc(sub)}</p>` : ""}
      <div class="res-val tnum">${val === null ? (item.status === "ready" ? L("Wert unbekannt") : L("Wert wird noch ermittelt")) : ""}</div>
      ${item.price_label ? `<div class="res-src"><span>${esc(item.price_label)}</span></div>`
        : (val === null && item.status === "ready"
           ? `<div class="res-src"><span>${L("Kein belegter Marktwert — trag deinen Preis beim Listen selbst ein")}</span></div>`
           : "<div style='height:10px'></div>")}
      <div class="party-actions">
        <button class="btn-primary" id="resOpen">${L("Zum Stück")}</button>
        <button class="btn-secondary" id="resNext">${L("Weiter scannen")}</button>
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
  el.querySelector("#resOpen").onclick = () => close(() => openItemDetail(item.id));
  el.querySelector("#resNext").onclick = () => close(() => { switchTab("tabScan"); $("cameraInput").click(); });
  el.onclick = (e) => { if (e.target === el) close(); };
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
      close(() => { loadCollection(); switchTab("tabScan"); });
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
  ind.innerHTML = `<img class="ptr-mono" src="assets/monogram-navy.png" alt="">`;
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
  estimate: ["KI-Schätzung (veraltet)", "Dieser Wert stammt aus einer früheren KI-Einschätzung. SERO vergibt solche Werte nicht mehr — beim nächsten Preis-Update wird er durch echte Marktdaten ersetzt oder ehrlich als unbekannt angezeigt."],
  scryfall: ["Cardmarket (Scryfall)", "Der aktuelle Cardmarket-Preis dieser Magic-Karte, bezogen über die freie Scryfall-Datenbank."],
  ygoprodeck: ["Cardmarket (YGOPRODeck)", "Der aktuelle Cardmarket-Preis dieser Yu-Gi-Oh-Karte, bezogen über die freie YGOPRODeck-Datenbank."],
  listing: ["Listing-Preis", "Dieses Stück wurde aus deinen eBay-Listings importiert — als Wert dient dein Angebotspreis, bis SERO eine echte Marktquelle findet (Preis aktualisieren antippen)."],
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
  const { timeout, ...rest } = opts;
  const ms = timeout ?? (rest.body instanceof FormData ? 180000 : 25000);
  const ctrl = new AbortController();
  const stop = setTimeout(() => ctrl.abort(), ms);
  let resp;
  try {
    // "include" verhält sich same-origin exakt wie "same-origin" — und trägt
    // das Session-Cookie auch dann, wenn die App-Hülle cross-origin lädt.
    resp = await fetch(url(path), { credentials: "include", signal: ctrl.signal, ...rest });
  } catch (e) {
    throw Object.assign(new Error(
      e.name === "AbortError"
        ? L("Das hat zu lange gedauert. Versuch es noch einmal.")
        : L("Keine Verbindung. Prüf dein Netz und versuch es noch einmal.")),
      { status: 0, offline: true });
  } finally {
    clearTimeout(stop);
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
  let d = localStorage.getItem("sero_device");
  if (!d) {
    d = "d" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    localStorage.setItem("sero_device", d);
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
  get: (k) => { try { return JSON.parse(localStorage.getItem("sero_" + k)); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem("sero_" + k, JSON.stringify(v)); } catch { /* voll */ } },
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
const condLabel = (c) => L(COND_LABELS[c] || c || "—");
const CATEGORIES = ["Pokémon", "One Piece", "Magic", "Yu-Gi-Oh!", "Lorcana", "Dragon Ball", "Sport", "Games", "LEGO", "TCG Sonstiges", "Sonstiges"];
const CAT_COLORS = {
  "Pokémon": "#c9a961", "One Piece": "#2dd4bf", "Magic": "#e0682f", "Yu-Gi-Oh!": "#b48ead",
  "Lorcana": "#8a5cf6", "Dragon Ball": "#f0a03c", "Sport": "#5aa85e", "Games": "#a78bfa",
  "LEGO": "#e05252", "TCG Sonstiges": "#5a9aa8", "Sonstiges": "#8e8e93",
};
const GAME_OF_CAT = {
  "Pokémon": "pokemon", "One Piece": "onepiece", "Magic": "magic", "Yu-Gi-Oh!": "yugioh",
  "Lorcana": "lorcana", "Dragon Ball": "dragonball",
};
const VARIANT_LABELS = { holo: "Holo", reverse: "Reverse Holo", normal: "Normal", firstEdition: "1. Edition", wPromo: "Promo" };

/* Thumbnails: eigene Fotos verkleinert laden — iPhone-Bilder sind mehrere MB groß */
const thumb = (u, w) => u && u.startsWith("/api/app/")
  ? url(`${u}${u.includes("?") ? "&" : "?"}w=${w}`) : u;
/* Katalog-Bilder statt eigener Fotos? (Svens Regel: eigenes Foto ist der Standard) */
const catalogView = () => localStorage.getItem("sero_catalog") === "1";

function sparkline(values, w, h, cls = "", area = false) {
  if (!values || values.length < 2) return "";
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const xy = (v, i) => [
    (i / (values.length - 1) * (w - 4) + 2), (h - 3 - (v - min) / span * (h - 8))];
  const pts = values.map((v, i) => xy(v, i).map((n) => n.toFixed(1)).join(",")).join(" ");
  let fill = "";
  if (area) {
    const [x0] = xy(values[0], 0), [x1] = xy(values[values.length - 1], values.length - 1);
    fill = `<polygon points="${x0},${h} ${pts} ${x1},${h}" fill="currentColor" opacity=".12" stroke="none"/>`;
  }
  return `<svg class="${cls}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" fill="none">
    ${fill}<polyline pathLength="1" points="${pts}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

/* TradingView-Style Kerzen-Chart — echte Tages-OHLC aus den Preis-Snapshots */
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

function applyTheme() {
  const t = localStorage.getItem("sero_theme") || "auto";
  document.documentElement.classList.toggle("force-dark", t === "dark");
  document.documentElement.classList.toggle("force-light", t === "light");
}

/* Sprache: automatisch nach Gerät (de/en) — weitere Sprachen folgen */
const LANG = (localStorage.getItem("sero_lang")
  || ((navigator.language || "de").toLowerCase().startsWith("de") ? "de" : "en"));
const STR_EN = {
  /* ── Navigation, Tabs, Grundgerüst ── */
  "Sammlung": "Collection", "Verkauf": "Selling", "Profil": "Profile", "Scanner": "Scanner",
  "Karte scannen": "Scan a card", "Aus Fotos auswählen": "Choose from photos",
  "Sammlung durchsuchen": "Search collection", "Suchen": "Search",
  "Wird analysiert": "Analyzing", "Scan-Verlauf": "Scan history",
  "Aktiv": "Active", "Entwürfe": "Drafts", "Beendet": "Ended",
  "Deine Karten. Dein Marktplatz.": "Your cards. Your marketplace.",
  "Testmodus": "Test mode", "Scannen": "Scan", "Verkaufen": "Sell", "Karte": "Card",
  "Sortieren": "Sort", "Filtern": "Filter", "Filter": "Filter", "Schließen": "Close",
  "Favorit": "Favorite", "Entfernen": "Remove", "Abbrechen": "Cancel", "Übernehmen": "Apply",
  "Anwenden": "Apply", "Speichern": "Save", "Fertig": "Done", "Weiter": "Continue",
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
  "Stücke": "items", "auf eBay": "on eBay", "Favoriten": "Favorites", "Wunschliste": "Wishlist",
  "Entwürfe ({0})": "Drafts ({0})", "Verkauft ({0})": "Sold ({0})", "Katalog-Bilder": "Catalog images",
  "Erkannt": "Recognized", "Zum Stück": "Open item", "Weiter scannen": "Scan another",
  "Deine ehrliche Rechnung": "Your honest math", "{0} gespart": "{0} saved",
  "Aus {0} erfassten Stücken": "From {0} captured items", "Gespart": "Saved",
  "statt {0}": "instead of {0}", "{0} Min je Stück": "{0} min per item",
  "Ø {0} Sek je Scan": "avg. {0} sec per scan", "rund 1 Min je Stück": "about 1 min per item",
  "Nächster Meilenstein": "Next milestone",
  "Noch <b>{0}</b> Stücke bis {1}": "<b>{0}</b> more items to {1}",
  "Noch <b>1</b> Stück bis {0}": "<b>1</b> more item to {0}",
  "Gemessen an {0} Scans — wächst mit jedem neuen Stück.":
    "Measured across {0} scans — grows with every new item.",
  "Wächst mit jedem neuen Stück.": "Grows with every new item.",
  "{0} Stunden": "{0} hours", "{0} Minuten": "{0} minutes",
  "1 Stunde": "1 hour", "1 Minute": "1 minute", "{0} h": "{0} h", "{0} Min": "{0} min",
  "Du hast {0} Stücke erfasst. Von Hand wären das rund {1} gewesen — mit SERO waren es {2}.":
    "You've captured {0} items. By hand that would have been about {1} — with SERO it was {2}.",
  "Von Hand": "By hand", "Mit SERO": "With SERO", "Weiter so": "Keep going",
  "{0} Stücke": "{0} items",
  "Von Hand wären das rund {0} gewesen. Mit SERO hast du {1} gespart.":
    "By hand that would have been about {0}. With SERO you saved {1}.",
  "Die ehrliche Rechnung": "The honest math",
  "100 Karten listen — einmal von Hand, einmal mit SERO.": "Listing 100 cards — by hand vs. with SERO.",
  "Std": "hrs", "Min": "min",
  "Karte bestimmen, verkaufte Angebote durchsehen, Foto zuschneiden, Titel und Pflichtfelder setzen — rund acht Minuten pro Stück.":
    "Identify the card, check sold listings, crop the photo, write the title and fill required fields — about eight minutes per item.",
  "Fotografieren, Ergebnis prüfen, freigeben — rund eine Minute pro Stück. 100 Karten, 100 Minuten.":
    "Shoot, check, approve — about one minute per item. 100 cards, 100 minutes.",
  "Von Hand rund 8 Minuten je Stück (Karte bestimmen, Marktwert, Foto, Titel und Pflichtfelder). Mit SERO rund 1 Minute — das ist nicht die Scan-Dauer, sondern die ehrliche Version inklusive Hinlegen, Prüfen und Freigeben.":
    "By hand about 8 minutes per item (identify, market value, photo, title and required fields). With SERO about 1 minute — not the scan time, but the honest version including placing, checking and approving.",
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
  "Bevor das Setup starten kann, verbinde zuerst dein eBay-Konto auf der Website.": "Before setup can start, connect your eBay account on the website first.",
  "Öffne die Website, melde dich mit derselben E-Mail an und tippe auf „Mit eBay verbinden“. Danach kommst du hierher zurück.": "Open the website, sign in with the same email and tap “Connect with eBay”. Then come back here.",
  "Website öffnen": "Open website",
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
  "Zuletzt gescannt": "Recently scanned", "Alle anzeigen": "Show all", "Verkaufs-Vorlage": "Selling template",
  "SERO erkennt jedes Stück und ermittelt den Marktwert.": "SERO recognizes every item and determines its market value.",
  "SERO erkennt jedes Stück und erstellt den eBay-Entwurf nach deiner Vorlage.": "SERO recognizes every item and creates the eBay draft from your template.", 
  "Wird analysiert …": "Analyzing …", "Wert unbekannt": "Value unknown",
  "Keine Treffer": "No matches", "Für diese Filter gibt es gerade nichts.": "Nothing matches these filters right now.",
  "Noch nichts live": "Nothing live yet", "Zur Sammlung": "Go to collection", "Ansicht wechseln": "Change view",
  "Liste": "List", "Große Kacheln": "Large tiles", "Kleine Kacheln": "Small tiles",
  "Liste ein Stück aus deiner Sammlung — SERO baut das Angebot fertig auf.":
    "List an item from your collection — SERO builds the whole listing.",
  "Keine offenen Entwürfe": "No open drafts",
  "Entwürfe entstehen, wenn du ein Stück zum Listen vorbereitest.":
    "Drafts appear when you prepare an item for listing.",
  "Noch nichts beendet": "Nothing ended yet",
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
  "Größte Preisbewegung": "Biggest price move",
  "Nur Favoriten": "Favorites only", "Dubletten (×2+)": "Duplicates (×2+)",
  "Auf eBay": "On eBay", "Tags": "Tags", "Filter zurücksetzen": "Reset filters",
  "{0} Listings importiert": "{0} listings imported",
  "Nichts Neues zu importieren": "Nothing new to import",

  /* ── Portfolio-Karte gestalten ── */
  "Karte gestalten": "Customize card",
  "Wähle Farbe, Verlauf oder ein eigenes Foto als Hintergrund.":
    "Pick a color, gradient or your own photo as the background.",
  "SERO Navy": "SERO Navy", "Ozean": "Ocean", "Sonnenuntergang": "Sunset", "Wald": "Forest",
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
  "insgesamt": "in total",
  "in den letzten 7 Tagen": "in the last 7 days", "in den letzten 30 Tagen": "in the last 30 days",
  "7T": "7D", "1M": "1M", "Max": "Max",
  "in Sammlung": "in collection", "im Verkauf ({0})": "listed ({0})",
  "Wertvollste Stücke": "Most valuable", "Alle ansehen": "View all", "Kategorien": "Categories",
  "{0} Stücke": "{0} items", "Deine NFTs (Solana)": "Your NFTs (Solana)",
  "Floor unbekannt": "Floor unknown",
  "Kommende Releases": "Upcoming releases", "TCG-News": "TCG news",
  "Deine Stücke": "Your items", "Wert": "Value", "Bewegung": "Movement",
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

  /* ── Scanner & Verkaufs-Vorlage ── */
  "Pokémon, One Piece, Magic, Yu-Gi-Oh, Lorcana, Dragon Ball & mehr — SERO erkennt Karte, Set und Sprache und holt tagesaktuelle Marktpreise. Auch stapelweise: Lade viele Fotos auf einmal hoch, SERO sortiert Vorder- und Rückseiten automatisch und stellt jede Karte frei.":
    "Pokémon, One Piece, Magic, Yu-Gi-Oh, Lorcana, Dragon Ball & more — SERO identifies card, set and language and pulls up-to-date market prices. Batches work too: upload many photos at once, SERO sorts fronts and backs automatically and cuts out every card.",
  "Verkaufs-Vorlage": "Selling template",
  "Gilt für jeden Scan im eBay-Verkauf-Modus — einmal einstellen, dann läuft alles automatisch durch.":
    "Applies to every scan in eBay selling mode — set it once and everything runs automatically.",
  "Format": "Format", "Sofortkauf": "Buy It Now", "Auktion": "Auction",
  "Preis": "Price", "Marktwert": "Market value", "Markt −10 %": "Market −10 %",
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
  "{0} Fotos — SERO ordnet Vorder- und Rückseiten automatisch zu. Slabs bleiben im Case.":
    "{0} photos — SERO sorts them automatically: front and back of the same card become ONE item. Slabs (PSA, CGC …) stay in the case; from sleeves and toploaders only the card is cut out.",
  "Alle Fotos zeigen dasselbe Stück": "All photos show the same item",
  "Sortiere Fotos …": "Sorting photos …", "Automatisch sortieren": "Sort automatically",
  "{0} Fotos → {1} Stück erkannt": "{0} photos → {1} item identified",
  "{0} Fotos → {1} Stücke erkannt": "{0} photos → {1} items identified",
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

  /* ── Schnellmenü ── */
  "Listing verwalten — LIVE": "Manage listing — LIVE",
  "Listing-Entwurf öffnen": "Open listing draft", "Auf eBay listen": "List on eBay",
  "Als Favorit": "Add to favorites", "Aus Wunschliste nehmen": "Remove from wishlist",
  "Auf die Wunschliste": "Add to wishlist",
  "Keine eigenen Fotos — bitte einmal neu scannen": "No photos of your own — please scan again",
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
  "Scans": "Scans", "Premium — unbegrenzt": "Premium — unlimited",
  "Konto löschen …": "Delete account …", "Mehr": "More",
  "SERO-Website öffnen": "Open SERO website", "Abmelden": "Sign out",
  "Automatisch (System)": "Automatic (system)", "Hell": "Light", "Dunkel": "Dark",
  "Einstellung nicht gespeichert. Versuch es erneut.": "Setting not saved. Try again.", "Preise werden aktualisiert …": "Refreshing prices …",

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
  "Einschätzung fertig": "Estimate ready", "Preis aktualisiert": "Price updated",

  /* ── Detail: Mein Exemplar ── */
  "Mein Exemplar": "My copy", "Kategorie": "Category", "Zustand": "Condition",
  "Stückzahl": "Quantity", "Kaufpreis": "Purchase price", "Notiz": "Note",
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
  "Die Erstellung ist fehlgeschlagen — mit „Neu erstellen“ unten kannst du es erneut versuchen.":
    "Creation failed — use “Regenerate” below to try again.",
  "Annahme:": "Assumption:", "Preis festlegen …": "Set a price …",
  "Startpreis · Auktion": "Starting price · auction",
  "{0} Tage": "{0} days", "Altersfreigabe": "Age rating", "USK ab {0}": "USK {0}+",
  "Keine Angabe": "Not specified", "Preisvorschlag": "Best offer",
  "Änderungen speichern": "Save changes", "Auf eBay listen": "List on eBay",
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
  "Alle neu rendern": "Re-render all", "Bilder werden neu gerendert …": "Re-rendering images …",
  "Bilder neu gerendert": "Images re-rendered",

  /* ── Konto löschen ── */
  "Konto löschen": "Delete account",
  "Das entfernt alles unwiderruflich: Sammlung, Fotos, Listings-Entwürfe, Preisverlauf und dein Konto.":
    "This removes EVERYTHING irreversibly: collection, photos, listing drafts, price history and your account.",
  "Tippe unten auf „Endgültig löschen“, um es wirklich zu tun.":
    "Tap “Delete permanently” below to really go through with it.",
  "Endgültig löschen": "Delete permanently",
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
      + " .empty h2, .empty p, .section-label, .login-sub, .login-hint, .login-foot,"
      + " .login-card label, .login-card button, .topbar-badge,"
      + " #btnScanGallery, #emptyImport, #sellTplBtn, #sheetCancel, #sheetSave";
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
  try {
    state.me = await api("/api/me", { timeout: 8000 });
    cache.set("me", state.me);
    showApp();
  } catch (e) {
    /* Kein Netz heißt nicht „nicht angemeldet": mit gültigem Cache startet die
       App offline mit dem letzten Stand — vorher landete man im Login, wo ohne
       Netz nicht einmal der Code ankommen kann. Nur ein echtes 401/403 (Session
       abgelaufen) führt noch zur Anmeldung. */
    if (e.offline && cache.get("col") && cache.get("me")) {
      state.me = cache.get("me");
      showApp();
      zeigeOfflineBanner();
    } else {
      $("viewLogin").hidden = false;
      renderSocialLogins();
      dismissSplash();
    }
  }
}

function zeigeOfflineBanner() {
  const c = cache.get("col");
  const min = c && c.ts ? Math.max(1, Math.round((Date.now() - c.ts) / 60000)) : null;
  toast(min ? LF("Offline — Stand von vor {0} Min.", min) : L("Offline — gespeicherter Stand"),
        "globe", { label: L("Erneut versuchen"), fn: () => { loadCollection(); loadDashboard(); } });
}
window.addEventListener("online", () => { loadCollection(); if (!$("tabHome").hidden) loadDashboard(); });
window.addEventListener("offline", zeigeOfflineBanner);

async function renderSocialLogins() {
  const r = await api("/api/auth-providers").catch(() => ({ providers: [] }));
  if (!r.providers.length) return;
  const names = { google: "Google", apple: "Apple", x: "X" };
  const div = document.createElement("div");
  div.innerHTML = `<div class="oauth-divider"><span>${L("oder weiter mit")}</span></div>` +
    r.providers.map((p) =>
      `<button class="btn-secondary oauth-btn" data-p="${p}">${esc(LF("Mit {0} anmelden", names[p] || p))}</button>`).join("");
  $("loginStep1").appendChild(div);
  div.querySelectorAll("[data-p]").forEach((b) => {
    b.onclick = () => { location.href = `/auth/${b.dataset.p}/start`; };
  });
}

$("loginNext").onclick = async () => {
  const id = $("loginId").value.trim();
  $("loginErr1").textContent = "";
  if (!id) return;
  $("loginNext").disabled = true;
  try {
    const r = await post("/api/login-code", { identifier: id });
    $("loginStep1").hidden = true;
    $("loginStep2").hidden = false;
    if (r.dev_code) {
      $("codeHint").textContent = LF("Test-Modus (kein Mailversand) — dein Code: {0}", r.dev_code);
      $("loginCode").value = r.dev_code;
    } else if (r.via === "telegram") {
      $("codeHint").textContent = L("SERO hat dir den Code per Telegram geschickt.");
    }
    $("loginCode").focus();
  } catch (e) {
    $("loginErr1").textContent = e.message;
  } finally {
    $("loginNext").disabled = false;
  }
};

$("loginId").addEventListener("keydown", (e) => { if (e.key === "Enter") $("loginNext").click(); });
$("loginCode").addEventListener("keydown", (e) => { if (e.key === "Enter") $("loginVerify").click(); });
$("loginVerify").onclick = async () => {
  $("loginErr2").textContent = "";
  $("loginVerify").disabled = true;
  try {
    await post("/api/login-verify", { identifier: $("loginId").value.trim(), code: $("loginCode").value.trim() });
    $("viewLogin").hidden = true;
    state.me = await api("/api/me").catch(() => null);
    showApp();
  } catch (e) {
    $("loginErr2").textContent = e.message;
  } finally {
    $("loginVerify").disabled = false;
  }
};

/* Drei Schritte in EINER Karte statt drei Karten hintereinander: bis zum ersten
   Scan waren es vorher 6-7 Tipps. Erlebnis schlägt Erklärung — was die Sammlung
   und der Verkauf können, erzählt die App im Moment, in dem es relevant wird. */
const TOUR_SCHRITTE = [
  ["camera", "Fotografieren", "Halt die Karte vor die Kamera — SERO erkennt Karte, Set, Sprache und Grading-Label."],
  ["chart", "Bestätigen", "Du siehst, was erkannt wurde und was das Stück laut echten eBay-Verkäufen wert ist."],
  ["arrowup", "Listen", "Ein Tipp macht daraus ein fertiges eBay-Listing — live geht es erst, wenn du es freigibst."],
];

function showTour() {
  const el = document.createElement("div");
  el.className = "party tour";
  el.innerHTML = `
    <div class="party-card">
      <span class="party-ring tour-ring"><img src="assets/monogram-white.png" style="width:34px"></span>
      <h2>${L("So funktioniert SERO")}</h2>
      <ol class="tour-steps">
        ${TOUR_SCHRITTE.map(([ic, h, p], i) => `
          <li style="animation-delay:${0.12 + i * 0.09}s">
            <span class="ts-ic">${icon(ic, 16)}</span>
            <span class="ts-tx"><b>${L(h)}</b>${L(p)}</span>
          </li>`).join("")}
      </ol>
      <div class="party-actions">
        <button class="btn-primary" id="tourNext">${L("Erste Karte scannen")}</button>
        <button class="btn-plain" id="tourSkip" style="text-align:center">${L("Später")}</button>
      </div>
    </div>`;
  const schliessen = () => {
    localStorage.setItem("sero_tour", "1");
    el.classList.add("out");
    setTimeout(() => el.remove(), 300);
  };
  // WICHTIG: Der Kamera-Aufruf muss SYNCHRON im Tipp-Handler stehen. iOS gibt
  // die Kamera nur im Gesten-Kontext frei — ein setTimeout davor verschenkt ihn,
  // und der Knopf „Erste Karte scannen" führt dann ins Leere.
  el.querySelector("#tourNext").onclick = () => {
    switchTab("tabScan");
    $("cameraInput").click();
    schliessen();
  };
  el.querySelector("#tourSkip").onclick = schliessen;
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
});
addEventListener("unhandledrejection", (e) => {
  window.__bootError = (e.reason && e.reason.message) || String(e.reason || "");
});

function showApp() {
  /* Der Sammlungs-Cache gehörte bisher dem GERÄT, nicht dem Konto: lief die
     Session ab und meldete sich jemand anderes an, sah er beim Start die
     komplette Sammlung des Vorgängers (Namen, Werte, Statistiken), bis der
     Server sie ersetzte. Jetzt trägt der Cache den Kontobesitzer — bei einem
     Wechsel werden alle Daten-Reste verworfen, bevor irgendetwas rendert. */
  const wer = (state.me && (state.me.email || state.me.id)) || "";
  if (wer && localStorage.getItem("sero_owner") !== String(wer)) {
    ["sero_col", "sero_milestone", "sero_home_items", "sero_sell_tpl",
     "sero_hero_img", "sero_hero_grad"]
      .forEach((k) => localStorage.removeItem(k));
    localStorage.setItem("sero_owner", String(wer));
  }
  $("viewApp").hidden = false;
  setTimeout(dismissSplash, 350);
  if (!localStorage.getItem("sero_tour")) setTimeout(showTour, 850);
  attachPTR($("homeScroll"), async () => { state.dash = null; await loadDashboard(); await loadCollection(); });
  attachPTR($("colScroll"), () => loadCollection());
  const cached = cache.get("col");
  if (cached) {
    state.items = cached.items || [];
    state.stats = cached.stats;
    state.history = cached.history || [];
    renderCollection();
  }
  // Aufräumen: Reste des entfernten Verschiebe-Modus
  localStorage.removeItem("sero_home_order");
  localStorage.removeItem("sero_home_hidden");
  // Einstellungen früh laden — Zeit-Bilanz, Scanner-Zahlen und das Scan-Banner
  // hängen daran; ohne sie blieben die Bausteine beim Start unsichtbar.
  api("/api/app/settings").then((s) => {
    state.settings = s;
    if (state.dash) renderDashboard();
    if (!$("tabScan").hidden) renderScan();
  }).catch(() => {});
  loadDashboard();
  loadCollection();
  loadSales();
}

/* ═══════════════════ Tabs ═══════════════════ */

const TAB_ORDER = ["tabHome", "tabCollection", "tabScan", "tabSales", "tabProfile"];
function switchTab(id) {
  // Richtung merken, BEVOR die alte Seite versteckt wird — die neue Seite
  // schiebt sich dann aus der logischen Richtung herein (räumliche Kontinuität)
  const prev = TAB_ORDER.findIndex((t) => { const p = $(t); return p && !p.hidden; });
  const next = TAB_ORDER.indexOf(id);
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === id));
  document.querySelectorAll(".tab-page").forEach((p) => (p.hidden = p.id !== id));
  const page = $(id);
  page.classList.remove("page-enter", "page-enter-l", "page-enter-r");
  void page.offsetWidth;               // Animation neu triggern
  page.classList.add(prev >= 0 && next >= 0 && next < prev ? "page-enter-l" : "page-enter-r");
  if (id === "tabHome") loadDashboard();
  if (id === "tabCollection") loadCollection();
  if (id === "tabSales") loadSales();
  if (id === "tabScan") renderScan();
  if (id === "tabProfile") renderProfile();
}
document.querySelectorAll(".tab").forEach((t) => { t.onclick = () => switchTab(t.dataset.tab); });

/* ═══════════════════ Dashboard ═══════════════════ */

const skel = (h, r = 16) => `<div class="skel" style="height:${h}px;border-radius:${r}px"></div>`;

async function loadDashboard() {
  const el = $("homeScroll");
  if (!state.dash) {
    el.innerHTML = `<h1 class="large-title">Übersicht</h1>${skel(150, 20)}<div style="height:14px"></div>${skel(90)}<div style="height:14px"></div>${skel(90)}`;
  }
  let d;
  try {
    d = await api("/api/app/dashboard");
  } catch (e) {
    if (e.status === 401) location.reload();
    return;
  }
  if (state._dashSig === JSON.stringify(d)) { state.dash = d; return; }
  state._dashSig = JSON.stringify(d);
  state.dash = d;
  renderDashboard();
}

/* iOS-Titel-Verdichtung: großer Titel schrumpft, Wert-Pille erscheint in der Topbar
   — funktioniert auf Home UND Sammlung (gemeinsame #miniVal-Pille, je Tab verdrahtet) */
const miniWiredTabs = {};
function wireMiniVal(tabId, valText) {
  let mv = $("miniVal");
  if (!mv) {
    mv = document.createElement("span");
    mv.id = "miniVal"; mv.className = "minival";
    (document.querySelector(".topbar") || document.body).appendChild(mv);
  }
  const page = $(tabId);
  const sc = page && page.querySelector(".page-scroll");
  if (!sc) return;
  sc._miniVal = valText;
  const sync = () => {
    if (page.hidden) return;
    const on = sc.scrollTop > 90;
    mv.classList.toggle("show", on);
    if (on && sc._miniVal) mv.textContent = sc._miniVal;
    sc.classList.toggle("condensed", sc.scrollTop > 40);
  };
  sync();
  if (miniWiredTabs[tabId]) return;
  miniWiredTabs[tabId] = true;
  sc.addEventListener("scroll", sync, { passive: true });
}

/* ═══════════ Übersicht: bewegliche Bausteine ═══════════
   Jede Sektion ist eine reine Funktion (HTML-String). Die Reihenfolge und
   was sichtbar ist, bestimmt der Nutzer per Gedrückthalten (Wackel-Modus). */

const HOME_SECS = [
  { key: "stats", label: "Zahlen", fn: (d, hidden) => `
    <div class="stat-row">
      <button class="stat" id="statCol"><b>${d.count}</b><span>${L("in Sammlung")}</span></button>
      <button class="stat" id="statSales"><b class="hideable ${hidden ? "veiled" : ""}">${money(d.sales.value_active)}</b><span>${LF("im Verkauf ({0})", d.sales.active)}</span></button>
      <button class="stat" id="statDrafts"><b>${d.sales.pending}</b><span>${L("Entwürfe")}</span></button>
    </div>` },

  /* Wertvollste Stücke und Preisbewegungen zeigten dieselben Stücke in zwei
     Listen — jetzt EINE Karte mit Umschalter. */
  { key: "stuecke", label: "Deine Stücke", fn: (d, hidden, movers, mover) => {
    const tab = localStorage.getItem("sero_home_items") === "move" && movers.length ? "move" : "wert";
    const top = d.top_items || [];
    if (!top.length && !movers.length) return "";
    return `<div class="ov-card">
      <div class="ov-card-head">
        <div class="ov-card-title">${L("Deine Stücke")}</div>
        ${movers.length && top.length ? `<div class="seg mini" id="itemsSeg">
          <button data-v="wert" class="${tab === "wert" ? "on" : ""}">${L("Wert")}</button>
          <button data-v="move" class="${tab === "move" ? "on" : ""}">${L("Bewegung")}</button>
        </div>` : ""}
      </div>
      ${tab === "move" ? movers.map(mover).join("") : top.map((t) => {
        const pct = t.delta7 && t.value ? (t.delta7 / (t.value - t.delta7) * 100) : null;
        return `<button class="mv-row" data-item="${t.id}">
          ${t.photo ? `<img src="${esc(thumb(t.photo, 240))}" loading="lazy" alt="">` : `<span class="mv-ph">${MONO_PH}</span>`}
          <span class="mv-name">${esc(t.name)}<br><i class="mv-sub">${esc(condLabel(t.condition))}${t.qty > 1 ? ` · ×${t.qty}` : ""}</i></span>
          <span class="mv-val"><span class="hideable ${hidden ? "veiled" : ""}">${money(t.value)}</span><br>
            ${pct !== null && isFinite(pct) && Math.abs(pct) >= 0.1 ? `<i class="${pct >= 0 ? "up" : "down"}" style="font-weight:700">${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(2).replace(".", ",")} %</i>` : ""}</span>
        </button>`; }).join("")}
      <button class="ov-viewall" id="topViewAll">${L("Alle ansehen")}</button>
    </div>`; } },


];

const HOME_DEFAULT = HOME_SECS.map((s) => s.key);

/* Feste Reihenfolge. (Das Verschieben per Gedrückthalten war zu fehleranfällig
   und wurde am 02.08. wieder entfernt — die Registry bleibt als saubere Struktur.) */
function homeOrder() {
  return { order: HOME_DEFAULT.slice(), hidden: [] };
}

function renderHomeSections(d, hidden, movers, mover) {
  const { order, hidden: hid } = homeOrder();
  return order.map((key) => {
    const sec = HOME_SECS.find((s) => s.key === key);
    if (!sec || hid.includes(key)) return "";
    const html = sec.fn(d, hidden, movers, mover);
    if (!html) return "";
    return `<section class="home-sec" data-sec="${key}">${html}</section>`;
  }).join("");
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

  const mover = (m) => `
    <button class="mv-row" data-item="${m.id}">
      ${m.photo ? `<img src="${esc(thumb(m.photo, 240))}" loading="lazy" alt="">` : `<span class="mv-ph">${MONO_PH}</span>`}
      <span class="mv-name">${esc(m.name)}</span>
      <span class="mv-val ${m.delta > 0 ? "up" : "down"}">${m.delta > 0 ? "▲" : "▼"} ${Math.abs(m.pct).toFixed(1).replace(".", ",")} %<br>
        <i>${money(m.value)}</i></span>
    </button>`;
  const movers = [...(d.movers_up || []), ...(d.movers_down || [])];

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

  const range = state.range || "1M";
  const rangeDays = { "7T": 7, "1M": 30, "Max": 9999 }[range];
  const cutoffTs = Date.now() - rangeDays * 86400000;
  const histPts = (d.history || []).filter((p) => new Date(p.day).getTime() >= cutoffTs).map((p) => p.value);
  // NUR Sammlungswert gegen Verlauf — grand_total enthält NFTs, der Verlauf nicht
  const serverDelta = { "7T": (d.deltas || {}).d7, "1M": (d.deltas || {}).d30, "Max": null };
  const rangeDelta = serverDelta[range] !== undefined && serverDelta[range] !== null
    ? serverDelta[range]
    : (histPts.length >= 2 ? d.total_value - histPts[0] : null);
  const hidden = localStorage.getItem("sero_hide") === "1";
  // Gibt es überhaupt einen Chart? Sonst wären die Zeitraum-Pillen tote Knöpfe.
  const hasChart = histPts.length >= 2;
  const grand = d.total_value;

  wireMiniVal("tabHome", hidden ? "••••" : money(grand));
  // Ohne ein einziges Stück ist die volle Übersicht sinnlos: 0,00 €, tote
  // Zeitraum-Pillen, drei Null-Kacheln. Stattdessen EIN klarer Einstieg.
  if (!d.count && !(d.sales.active || d.sales.pending)) {
    $("homeScroll").innerHTML = `<h1 class="large-title">${L("Übersicht")}</h1>` + emptyState({
      icon: "scanframe", titel: "Noch keine Stücke",
      text: "Scanne dein erstes Stück — Marktwert und Verlauf entstehen automatisch.",
      aktion: "Erste Karte scannen", onAktion: () => switchTab("tabScan"),
    });
    return;
  }
  $("homeScroll").innerHTML = `
    <h1 class="large-title">Übersicht</h1>
    <div class="ov-head ${heroStyle() ? "themed" : ""}" style="${heroStyle()}">
      <div class="ov-top">
        <span class="ov-label">Portfolio <b>SERO</b></span>
        <button class="icon-btn sm" id="eyeBtn">${icon("eye", 16)}</button>
        <button class="icon-btn sm" id="dashRefresh">${icon("refresh", 16)}</button>
      </div>
      <div class="ov-value hideable ${hidden ? "veiled" : ""}">${money(grand)}</div>
      <div class="ov-delta ${rangeDelta === null ? "" : rangeDelta >= 0 ? "up" : "down"} hideable ${hidden ? "veiled" : ""}">
        ${grand === 0 && d.sales.active > 0
          ? LF("Deine gesamte Sammlung ist gerade im Verkauf ({0})", money(d.sales.value_active))
          : rangeDelta === null ? L("Verlauf entsteht ab dem zweiten Tag")
          : `${rangeDelta >= 0 ? "+" : "−"}${money(Math.abs(rangeDelta))} ${range === "Max" ? L("insgesamt")
            : range === "7T" ? L("in den letzten 7 Tagen") : L("in den letzten 30 Tagen")}`}
      </div>
    </div>
    ${histPts.length >= 2 ? `<div class="big-chart">${sparkline(histPts, 375, 170, "bigline", true)}</div>` : ""}
    ${hasChart ? `<div class="range-row">
      ${["7T", "1M", "Max"].map((r) => `<button class="range-pill ${range === r ? "on" : ""}" data-r="${r}">${L(r)}</button>`).join("")}
    </div>` : ""}
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
    <div id="homeSecs">${renderHomeSections(d, hidden, movers, mover)}</div>
    <div style="height:20px"></div>`;

  $("dashRefresh").onclick = async () => {
    $("dashRefresh").classList.add("spin");
    try {
      const r = await post("/api/app/collection/refresh", null, { timeout: 600000 });
      toast(LF("Preise aktualisiert ({0} von {1})", r.updated, r.total), "check");
      state.dash = null;
      loadDashboard(); loadCollection();
    } catch (e) { toast(e.message); }
    finally { const b = $("dashRefresh"); if (b) b.classList.remove("spin"); }
  };
  $("homeScroll").querySelectorAll("[data-item]").forEach((b) => {
    b.onclick = () => openItemDetail(b.dataset.item);
  });
  countUp($("homeScroll").querySelector(".h-value"), "dashVal", d.total_value);
  if (!hidden) countUp($("homeScroll").querySelector(".ov-value"), "dashGrand", grand);
  fadeImgs($("homeScroll"));
  const sc = $("setupCard");
  if (sc) sc.onclick = () => window.open("/onboarding.html", "_blank");
  const sb = $("scanBanner");
  if (sb) sb.onclick = openPaywall;
  $("homeScroll").querySelectorAll("#itemsSeg button").forEach((b) => {
    b.onclick = () => { localStorage.setItem("sero_home_items", b.dataset.v); renderDashboard(); };
  });
  $("homeScroll").querySelectorAll(".range-pill").forEach((p) => {
    p.onclick = () => { state.range = p.dataset.r; renderDashboard(); };
  });
  $("eyeBtn").onclick = () => {
    localStorage.setItem("sero_hide", localStorage.getItem("sero_hide") === "1" ? "0" : "1");
    renderDashboard();
  };
  const ss = $("statSales");
  if (ss) ss.onclick = () => { state.salesBucket = "active"; switchTab("tabSales"); };
  const sc2 = $("statCol");
  if (sc2) sc2.onclick = () => switchTab("tabCollection");
  const sd = $("statDrafts");
  if (sd) sd.onclick = () => { state.salesBucket = "draft"; switchTab("tabSales"); };
  const tva = $("topViewAll");
  if (tva) tva.onclick = () => { state.sort = "valdesc"; switchTab("tabCollection"); };
  $("homeScroll").querySelectorAll("[data-cat]").forEach((b2) => {
    b2.onclick = () => {
      state.filter = { cat: b2.dataset.cat, fav: false, wish: false, dup: false, listed: false, draft: false, tag: null };
      switchTab("tabCollection");
    };
  });
}

/* ═══════════════════ Sammlung ═══════════════════ */

/* Portfolio-Karte gestalten: Farbe, Verlauf oder eigenes Foto */
const HERO_PRESETS = [
  ["SERO Navy", ""],
  ["Ozean", "linear-gradient(140deg,#0e7490,#164e63 60%,#083344)"],
  ["Sonnenuntergang", "linear-gradient(140deg,#b45309,#9d174d 60%,#4c0519)"],
  ["Wald", "linear-gradient(140deg,#15803d,#14532d 60%,#052e16)"],
  ["Violett", "linear-gradient(140deg,#7c3aed,#4c1d95 60%,#2e1065)"],
  ["Graphit", "linear-gradient(140deg,#374151,#111827 60%,#030712)"],
  ["Gold", "linear-gradient(140deg,#b8860b,#78500a 60%,#3d2a05)"],
];

function heroStyle() {
  const img = localStorage.getItem("sero_hero_img");
  if (img) return `background: linear-gradient(rgba(8,16,34,.45), rgba(8,16,34,.72)), url(${img}) center/cover;`;
  const g = localStorage.getItem("sero_hero_grad");
  return g ? `background: ${g};` : "";
}

function refreshHeroes() {
  renderCollection();
  state.dash = null;
  loadDashboard();
}

function openHeroDesigner() {
  openSheet("Karte gestalten", "Wähle Farbe, Verlauf oder ein eigenes Foto als Hintergrund.", `
    <div class="hero-presets">${HERO_PRESETS.map(([n, g], i) => `
      <button class="hp" data-hp="${i}" style="background:${g || "linear-gradient(140deg,#1a4585,#102e5a 55%,#0b1f3e)"}"><span>${L(n)}</span></button>`).join("")}
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
      localStorage.removeItem("sero_hero_img");
      if (g) localStorage.setItem("sero_hero_grad", g);
      else localStorage.removeItem("sero_hero_grad");
      closeSheet(); refreshHeroes();
    };
  });
  $("hpColor").oninput = (e) => {
    const c = e.target.value;
    localStorage.removeItem("sero_hero_img");
    localStorage.setItem("sero_hero_grad",
      `linear-gradient(140deg, ${c} 0%, color-mix(in srgb, ${c} 55%, #000) 70%, color-mix(in srgb, ${c} 30%, #000) 100%)`);
    closeSheet(); refreshHeroes();
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
      localStorage.setItem("sero_hero_img", cv.toDataURL("image/jpeg", 0.78));
      closeSheet(); refreshHeroes();
      toast("Foto gesetzt", "check");
    } catch { toast("Foto zu groß. Wähle ein kleineres Bild."); }
  };
  $("hpReset").onclick = () => {
    localStorage.removeItem("sero_hero_img"); localStorage.removeItem("sero_hero_grad");
    closeSheet(); refreshHeroes();
  };
}

/* ── Server-Push (Baustein 2): stehende Verbindung, Änderungen erscheinen
   in 1–2 s auf jedem offenen Gerät. Regel: bei (Re-)Connect einmal voll laden,
   danach reichen die Pushes. EventSource reconnectet selbst. */
let syncES = null, syncTimer = null, syncWasDown = false, syncRetry = 1;
function startSync() {
  if (syncES || !window.EventSource) return;
  syncES = new EventSource("/api/app/events");
  syncES.onmessage = (e) => {
    let ev = {};
    try { ev = JSON.parse(e.data); } catch { return; }
    clearTimeout(syncTimer);
    syncTimer = setTimeout(() => {
      loadCollection().then(() => {
        for (const id of [...state.sellWatch]) {
          const it = state.items.find((x) => x.id === id);
          if (it && it.status === "ready" && !it.draft_id) { state.sellWatch.delete(id); listNow(id); }
          // auch bei einem Listing-Fehler aufhören zu warten (Status bleibt "ready",
          // weil die Karte erkannt ist — nur das Einstellen ging schief)
          if (it && (it.status === "error" || it.error)) state.sellWatch.delete(id);
        }
      });
      if (!$("tabHome").hidden) loadDashboard();
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
    if (syncWasDown) { syncWasDown = false; loadCollection(); loadDashboard(); }
  };
}
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    /* Gerät weggelegt: Verbindung sauber schließen. iOS kappt sie sonst still —
       der Server hielt den Slot dann als Zombie, bis 5 Zombies das Konto
       blockierten. */
    if (syncES) { syncES.close(); syncES = null; }
    return;
  }
  startSync();
  loadCollection(); if (!$("tabHome").hidden) loadDashboard();
  pruefeAblage();
});
window.addEventListener("pagehide", () => { if (syncES) { syncES.close(); syncES = null; } });

/* Ablage-Check bei Rückkehr in die App: iOS feuert beim abgebrochenen
   Kamera-Dialog oft GAR KEIN Ereignis — geparkte Fotos blieben dann unsichtbar
   liegen und wanderten beim nächsten Scan kommentarlos ins falsche Stück. */
async function pruefeAblage() {
  if (state.stageOpen || stageUpload._busy) return;
  try {
    const r = await api("/api/app/collection/stage?" + devQ());
    if ((r.photos || []).length && $("sheet").hidden) openStagedSheet(r.photos);
  } catch { /* offline — nächster Versuch beim nächsten Wechsel */ }
}

async function loadCollection() {
  startSync();
  if (!state._stageChecked) {
    state._stageChecked = true;
    api("/api/app/collection/stage?" + devQ()).then((r) => {
      if ((r.photos || []).length) openStagedSheet(r.photos);
    }).catch(() => {});
  }
  let r;
  try {
    r = await api("/api/app/collection");
  } catch (e) {
    if (e.status === 401) location.reload();
    if (e.offline && state.items.length) zeigeOfflineBanner();
    return;
  }
  // Große Sammlung? Rest in Blöcken nachziehen, bevor gerendert wird —
  // die Suche und die Statistik-Kacheln sollen IMMER alles sehen.
  while (r.total > r.items.length) {
    let mehr;
    try {
      mehr = await api(`/api/app/collection?offset=${r.items.length}&limit=${r.limit}`);
    } catch { break; }
    if (!(mehr.items || []).length) break;
    r.items = r.items.concat(mehr.items);
  }
  const sig = r.rev || JSON.stringify([r.items, r.stats]);
  state.items = r.items;
  state.stats = r.stats;
  state.history = r.history || [];
  if (state._colSig === sig) return;   // unverändert → kein Neuzeichnen (Plopp-Fix)
  state._colSig = sig;
  state.dryRun = r.dry_run;
  cache.set("col", { items: r.items, stats: r.stats, history: r.history, ts: Date.now() });
  $("dryBadge").hidden = !r.dry_run;
  renderCollection();
  // Frisch gescanntes Stück fertig? Direkt öffnen (roter Faden Scan -> Prüfen -> Verkaufen)
  if (state.watchNew) {
    const fresh = state.items.find((i) => i.id === state.watchNew);
    if (fresh && fresh.status !== "analyzing") {
      state.watchNew = null;
      showScanResult(fresh);
    }
  }
  clearTimeout(state.colPollTimer);
  if (state.items.some((i) => i.status === "analyzing" || i.status === "waiting")) {
    state.colPollTimer = setTimeout(loadCollection, 2200);
    if (!$("tabScan").hidden) renderScan();
  }
}

function filteredItems() {
  const f = state.filter;
  const q = ($("colSearch").value || "").trim().toLowerCase();
  // Standardmäßig ist ALLES sichtbar — vorher verschwand ein Stück beim Listen
  // ohne Erklärung aus der Sammlung. Die Chips filtern, sie machen nicht sichtbar.
  let items = state.items.filter((i) =>
    (f.cat === "Alle" || i.category === f.cat) &&
    (!f.fav || i.favorite) && (!f.wish || i.wishlist) &&
    (!f.dup || i.quantity > 1) &&
    // Verkauftes/Wunsch nur zeigen, wenn der passende Chip aktiv ist —
    // beides gehört nicht mehr (bzw. noch nicht) zum Besitz.
    (f.sold ? (i.sold || i.draft_status === "ended") : !(i.sold || i.draft_status === "ended")) &&
    (f.wish || !i.wishlist) &&
    (!f.listed || i.draft_status === "published") &&
    (!f.draft || (i.draft_id && i.draft_status && !["published", "ended"].includes(i.draft_status))) &&
    (!f.tag || (i.tags || []).includes(f.tag)) &&
    (!q || (i.name || "").toLowerCase().includes(q)));
  const by = {
    new: (a, b) => (b.created_at || 0) - (a.created_at || 0),
    valdesc: (a, b) => (b.est_value ?? -1) - (a.est_value ?? -1),
    valasc: (a, b) => (a.est_value ?? Infinity) - (b.est_value ?? Infinity),
    name: (a, b) => (a.name || "").localeCompare(b.name || ""),
    delta: (a, b) => Math.abs(b.delta7 || 0) - Math.abs(a.delta7 || 0),
  };
  return items.sort(by[state.sort] || by.new);
}

function activeFilterCount() {
  const f = state.filter;
  return (f.cat !== "Alle") + f.fav + f.wish + f.dup + f.listed + f.draft + (f.tag ? 1 : 0);
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

function renderCollection() {
  const s = state.stats || { count: 0, total_value: 0, categories: [] };
  pruefeSystemstatus();
  const hasItems = state.items.length > 0;
  $("colEmpty").hidden = hasItems;
  $("colSearchBox").hidden = !hasItems;
  $("colChips").hidden = !hasItems;
  $("btnSort").style.display = hasItems ? "" : "none";
  $("btnFilter").style.display = hasItems ? "" : "none";
  $("btnFilter").classList.toggle("badged", activeFilterCount() > 0);

  const hist = (state.history || []).map((p) => p.value);
  // Zahlen müssen zum Raster passen: gezählt wird, was man auch SIEHT.
  // (Vorher: Held zählte ohne gelistete Stücke, das Raster zeigt sie jetzt.)
  // Klare Definition: Sammlung = was dir GEHÖRT (auch wenn gerade gelistet).
  // Verkauftes und Wunschliste zählen nicht — beides ist über Chips erreichbar.
  const verkauft = (i) => !!(i.sold || i.draft_status === "ended");
  const alle = state.items.filter((i) => !i.wishlist && !verkauft(i));
  const gesamtwert = alle.reduce((sum, i) => sum + (i.est_value || 0) * (i.quantity || 1), 0);
  const nLive = state.items.filter((i) => i.draft_status === "published").length;
  const nFav = state.items.filter((i) => i.favorite).length;
  const nSold = state.items.filter(verkauft).length;
  $("colHero").innerHTML = !hasItems ? "" : `
    <div class="hero compact" style="${heroStyle()}">
      <button class="hero-refresh" id="heroCustom" aria-label="${L("Gestalten")}">${icon("gear", 15)}</button>
      <span class="h-label">${L("Sammlungswert")}</span>
      <div class="h-value" style="font-size:28px">${money(gesamtwert)}</div>
      ${(() => {
        // Durchgehende Wertlinie (Svens „Strich"): randlose Kurve als stilles
        // Hintergrund-Element von Kante zu Kante, statt eingeklemmter Mini-Kerzen
        const pts = hist;
        return pts.length >= 2 ? `<div class="h-spark">${sparkline(pts, 410, 58, "sline", true)}</div>` : "";
      })()}
      <div class="h-meta"><button data-hf="alle"><b>${alle.length}</b>${L("Stücke")}</button>
        <button data-hf="listed"><b>${nLive}</b>${L("auf eBay")}</button>
        <button data-hf="fav"><b>${nFav}</b>${L("Favoriten")}</button>
        ${s.wishlist ? `<button data-hf="wish"><b>${s.wishlist}</b>${L("Wunschliste")}</button>` : ""}</div>
    </div>`;

  const hcBtn = $("heroCustom");
  if (hcBtn) hcBtn.onclick = openHeroDesigner;
  $("colHero").querySelectorAll("[data-hf]").forEach((b) => {
    b.onclick = () => {
      const v = b.dataset.hf;
      state.filter = { cat: "Alle", fav: v === "fav", wish: v === "wish", dup: false,
                       listed: v === "listed", draft: false, tag: null };
      renderCollection();
    };
  });

  const cats = ["Alle", ...(s.categories || []).map(([c]) => c)];
  if (!cats.includes(state.filter.cat)) state.filter.cat = "Alle";
  const nDraft = state.items.filter((i) => i.draft_id && i.draft_status
    && !["published", "ended"].includes(i.draft_status)).length;
  $("colChips").innerHTML =
    (nLive ? `<button class="fchip status ${state.filter.listed ? "on" : ""}" data-st="listed">● Live (${nLive})</button>` : "")
    + (nDraft ? `<button class="fchip status ${state.filter.draft ? "on" : ""}" data-st="draft">${LF("Entwürfe ({0})", nDraft)}</button>` : "")
    + (nSold ? `<button class="fchip status ${state.filter.sold ? "on" : ""}" data-st="sold">${LF("Verkauft ({0})", nSold)}</button>` : "")
    + cats.map((c) =>
      `<button class="fchip ${state.filter.cat === c ? "on" : ""}" data-c="${esc(c)}">${esc(c === "Alle" ? L("Alle") : c)}</button>`).join("")
    + (state.filter.tag ? `<button class="fchip on" data-tag-clear="1"># ${esc(state.filter.tag)} ✕</button>` : "")
    + `<button class="fchip ${catalogView() ? "on" : ""}" data-catimg="1">${icon("photo", 12)} ${L("Katalog-Bilder")}</button>`;
  $("colChips").querySelectorAll(".fchip").forEach((b) => {
    b.onclick = () => {
      if (b.dataset.catimg) {
        localStorage.setItem("sero_catalog", catalogView() ? "0" : "1");
        renderCollection();
        return;
      }
      if (b.dataset.tagClear) state.filter.tag = null;
      else if (b.dataset.st) state.filter[b.dataset.st] = !state.filter[b.dataset.st];
      else state.filter.cat = b.dataset.c;
      renderCollection();
    };
  });

  const items = filteredItems();
  const grid = $("colGrid");
  grid.innerHTML = "";
  let gi = 0;
  for (const i of items) {
    const b = document.createElement("button");
    b.className = "gitem";
    b.style.setProperty("--i", Math.min(gi++, 10));
    const busy = i.status === "analyzing" || i.status === "waiting";
    const badge = i.quantity > 1 ? `<span class="gbadge">×${i.quantity}</span>` : "";
    // Ein Status-Wort mit Punkt — statt Badges, die man je nach Filter sah oder nicht
    const stat = i.sold || i.draft_status === "ended" ? ["sold", L("Verkauft")]
      : i.draft_status === "published" ? ["live", L("Live")]
      : i.draft_id && i.draft_status ? ["draft", L("Entwurf")]
      : i.wishlist ? ["wish", L("Wunsch")] : null;
    const statLine = stat ? `<span class="gstat ${stat[0]}">${stat[1]}</span>` : "";
    const fav = i.favorite ? `<span class="gfav">${icon("starfill", 15)}</span>` : "";
    let delta = "";
    if (!busy && i.delta7 !== undefined && Math.abs(i.delta7) >= 0.01 && i.est_value) {
      const up = i.delta7 > 0;
      const pct = i.delta7 / (i.est_value - i.delta7) * 100;
      delta = `<span class="gdelta ${up ? "up" : "down"}">${up ? "▲" : "▼"} ${isFinite(pct) ? Math.abs(pct).toFixed(1).replace(".", ",") + " %" : ""}</span>`;
    }
    const condLine = !busy && i.condition
      ? `<span class="gcond">${esc(condLabel(i.condition))}</span>` : "";
    const value = busy
      ? `<span class="ganalyzing"><span class="spinner"></span>${esc(i.status_text || L("Wird analysiert …"))}</span>`
      : i.est_value !== null && i.est_value !== undefined
        ? `<span class="gval">${i.price_state === "unbekannt" ? "≈ " : ""}${money(i.est_value)}${delta}</span>`
        : `<span class="gval na">${L("Wert unbekannt")}</span>`;
    b.innerHTML = `
      ${(() => {
        const u = (catalogView() && !i.graded && i.card && i.card.image) ? i.card.image
          : (thumb(i.photos[0], 480) || (i.card && i.card.image));
        return u ? `<img class="gph" src="${esc(u)}" loading="lazy" alt="">`
                 : `<span class="gph-none">${MONO_PH}</span>`; })()}
      ${badge}${fav}<span class="gmore" data-more="1">${icon("sliders", 14)}</span>
      <div class="gbody">
        <span class="gcat" style="color:${CAT_COLORS[i.category] || "var(--label-3)"}">${esc(i.category)}${(() => {
          const g = i.graded; if (!g || !g.grade) return "";
          const gr = (g.grader || "").toUpperCase();
          const t = `${i.name} ${g.grade}`.toLowerCase();
          const cls = gr === "PSA" ? "red"
            : gr === "CGC" ? (t.includes("pristine") || t.includes("perfect") ? "gold" : "bw")
            : (gr === "BGS" || gr === "BECKETT") ? "silver"
            : gr === "WATA" ? "navy" : "grey";
          return `<i class="gseal-in ${cls}">${esc(gr)} ${esc(String(g.grade))}</i>`; })()}</span>
        <div class="gname">${esc(i.name)}</div>
        ${statLine}${condLine}${value}
      </div>`;
    b.onclick = (e) => {
      if (e.target.closest("[data-more]")) { openItemMenu(i); return; }
      if (b._lp) { b._lp = false; return; }
      openItemDetail(i.id);
    };
    let lpTimer = null, sx = null, dx = 0;
    b.addEventListener("pointerdown", (e) => {
      sx = e.clientX; dx = 0;
      lpTimer = setTimeout(() => { b._lp = true; haptic("light"); openItemMenu(i); }, 450);
    });
    b.addEventListener("pointermove", (e) => {
      if (sx === null) return;
      dx = e.clientX - sx;
      if (Math.abs(dx) > 10) {
        clearTimeout(lpTimer);
        b.classList.add("dragging");
        // Aktion hinter der Kachel aufdecken, damit man SIEHT was passiert
        b.classList.toggle("rev-fav", dx > 0);
        b.classList.toggle("rev-more", dx < 0);
        const reached = Math.abs(dx) > 80;
        if (reached !== b._reached) {
          b._reached = reached;
          b.classList.toggle("armed", reached);
          if (reached) haptic("soft");
        }
        b.style.transform = `translateX(${Math.max(-120, Math.min(120, dx))}px)`;
      }
    });
    for (const ev of ["pointerup", "pointerleave", "pointercancel"])
      b.addEventListener(ev, async () => {
        clearTimeout(lpTimer);
        if (sx === null) return;
        const d = dx; sx = null;
        b.classList.remove("dragging", "rev-fav", "rev-more", "armed");
        b._reached = false; b.style.transform = "";
        if (Math.abs(d) > 80) {
          b._lp = true;
          if (d < 0) openItemMenu(i);
          else {
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
        }
      });
    b.addEventListener("contextmenu", (e) => { e.preventDefault(); b._lp = true; openItemMenu(i); });
    grid.appendChild(b);
  }
  if (!items.length && hasItems) {
    grid.innerHTML = `<div style="grid-column:1/-1">${emptyState({
      icon: "search", titel: "Keine Treffer",
      text: "Für diese Filter gibt es gerade nichts.",
      aktion: "Filter zurücksetzen",
      onAktion: () => {
        state.filter = { cat: "Alle", fav: false, wish: false, dup: false,
                         listed: false, draft: false, sold: false, tag: null };
        $("colSearch").value = "";
        renderCollection();
      },
    })}</div>`;
  }
  // Der Serverwert lässt gelistete Stücke weg — hier zählt der volle Besitz
  countUp($("colHero").querySelector(".h-value"), "colVal", gesamtwert);
  wireMiniVal("tabCollection", money(s.total_value));
  fadeImgs($("colGrid"));
}

let _searchTimer = null;
$("colSearch").addEventListener("input", () => {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(renderCollection, 180);   // sonst ploppt bei jedem Zeichen alles neu
});
$("emptyAdd").onclick = () => switchTab("tabScan");
$("emptyImport").onclick = () => importListings($("emptyImport"));

$("btnSort").onclick = () => {
  const opts = [
    { label: "Neueste zuerst", value: "new" }, { label: "Wert (hoch → niedrig)", value: "valdesc" },
    { label: "Wert (niedrig → hoch)", value: "valasc" }, { label: "Name (A–Z)", value: "name" },
    { label: "Größte Preisbewegung", value: "delta" },
  ].map((o) => ({ ...o, sel: state.sort === o.value }));
  openOptions("Sortieren", opts, (v) => { state.sort = v; renderCollection(); });
};

$("btnFilter").onclick = () => {
  const f = state.filter;
  const tagChips = (state.stats?.tags || []).map(([t]) =>
    `<button class="fchip ${f.tag === t ? "on" : ""}" data-t="${esc(t)}"># ${esc(t)}</button>`).join("");
  openSheet("Filter", "", `
    <div class="opt-list" style="margin-bottom:12px">
      ${[["fav", "star", "Nur Favoriten"], ["wish", "heart", "Wunschliste"],
         ["dup", "copies", "Dubletten (×2+)"], ["listed", "bag", "Auf eBay"]].map(([k, ic, lb]) => `
        <div class="opt"><span style="display:flex;align-items:center;gap:10px">${icon(ic, 17)} ${L(lb)}</span>
          <span class="sw"><input type="checkbox" data-f="${k}" ${f[k] ? "checked" : ""}><i></i></span></div>`).join("")}
    </div>
    ${tagChips ? `<p class="sheet-hint" style="margin-bottom:8px">${L("Tags")}</p><div class="chips">${tagChips}</div>` : ""}
    <button class="btn-secondary" id="filterReset" style="margin-top:8px">${L("Filter zurücksetzen")}</button>`,
    () => { closeSheet(); renderCollection(); }, "Anwenden");
  $("sheetBody").querySelectorAll("[data-f]").forEach((sw) => {
    sw.onchange = () => { state.filter[sw.dataset.f] = sw.checked; };
  });
  $("sheetBody").querySelectorAll("[data-t]").forEach((b) => {
    b.onclick = () => { state.filter.tag = state.filter.tag === b.dataset.t ? null : b.dataset.t; closeSheet(); renderCollection(); };
  });
  $("filterReset").onclick = () => {
    state.filter = { cat: "Alle", fav: false, wish: false, dup: false, listed: false, draft: false, tag: null };
    closeSheet(); renderCollection();
  };
};

async function importListings(btn) {
  // Sichtbare Rückmeldung + Doppeltipp-Schutz: der Import dauert bei vielen
  // Listings spürbar, und zwei Tipps starteten ihn bisher doppelt.
  if (importListings._busy) return;
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

/* ── Scanner-Cockpit: zwei Wege (Sammlung | eBay-Verkauf) + Verkaufs-Vorlage */
const scanMode = () => localStorage.getItem("sero_scan_mode") || "collect";
const SELL_TPL_DEFAULT = { format: "FIXED_PRICE", auction_days: 7, price_mode: "market", price_value: null, bg: "white" };
const sellTpl = () => ({ ...SELL_TPL_DEFAULT, ...(JSON.parse(localStorage.getItem("sero_sell_tpl") || "{}")) });
state.sellWatch = new Set();

function renderScanMode() {
  const m = scanMode();
  document.querySelectorAll("#scanModeSeg button").forEach((b) =>
    b.classList.toggle("on", b.dataset.m === m));
  // Der Hero-Satz erklärt den GEWÄHLTEN Modus (Svens Punkt: nicht zweimal dasselbe)
  const ht = $("scanHeroText");
  if (ht) ht.textContent = m === "sell"
    ? L("SERO erkennt jedes Stück und erstellt den eBay-Entwurf nach deiner Vorlage.")
    : L("SERO erkennt jedes Stück und ermittelt den Marktwert.");
  // Verkaufs-Vorlage als Einstellungs-Zeile mit den ECHTEN Ist-Werten (iOS-Muster)
  const box = $("sellTplRow");
  if (!box) return;
  if (m !== "sell") { box.innerHTML = ""; return; }
  const t = sellTpl();
  const fmt = t.format === "AUCTION" ? L("Auktion") : L("Sofortkauf");
  const price = { market: L("Marktwert"), market_minus10: "Markt −10 %",
    auction1: "1 € Start", fixed: L("Festpreis") }[t.price_mode] || L("Marktwert");
  const bg = { white: L("Weiß"), warm: L("Warmweiß"), black: L("Schwarz"),
    logo: L("Mein Logo") }[t.bg] || L("Weiß");
  box.innerHTML = `<button class="irow tap" id="sellTplBtn" style="width:100%">
    <span class="ric" style="background:#3478f6">${icon("gear", 15)}</span>
    <span class="rlabel">${L("Verkaufs-Vorlage")}</span>
    <span class="rvalue">${esc(fmt)} · ${esc(price)} · ${esc(bg)}</span>
    <span class="chev">${icon("chevron", 15)}</span></button>`;
}
document.addEventListener("click", (e) => {
  const mb = e.target.closest("#scanModeSeg button");
  if (mb) { localStorage.setItem("sero_scan_mode", mb.dataset.m); renderScanMode();
    if (mb.dataset.m === "sell" && !localStorage.getItem("sero_sell_tpl")) openSellTemplate(); }
  if (e.target.closest("#sellTplBtn")) openSellTemplate();
});

function openSellTemplate() {
  const t = sellTpl();
  const opt = (name, val, label, cur) => `<button class="fchip ${cur === val ? "on" : ""}" data-tpl="${name}:${val}">${L(label)}</button>`;
  openSheet("Verkaufs-Vorlage", "Gilt für jeden Scan im eBay-Verkauf-Modus — einmal einstellen, dann läuft alles automatisch durch.",
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
      localStorage.setItem("sero_sell_tpl", JSON.stringify(nt));
      try {
        const f = $("tplLogo").files[0];
        if (f) { const fd = new FormData(); fd.append("files", f);
          await api("/api/app/settings/render-logo", { method: "POST", body: fd }); nt.bg = "logo"; }
        await post("/api/app/settings/render", { mode: nt.bg });
      } catch (err) { toast(err.message); }
      localStorage.setItem("sero_sell_tpl", JSON.stringify(nt));
      closeSheet(); toast("Verkaufs-Vorlage gespeichert", "check");
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

async function listNow(id) {
  const t = sellTpl();
  try {
    await post(`/api/app/collection/item/${id}/list`, {
      format: t.format, auction_days: t.auction_days,
      price_mode: t.price_mode, price_value: t.price_value });
    toast("Entwurf erstellt — liegt im Verkauf-Tab", "arrowup");
  } catch (e) { toast(L("Listen fehlgeschlagen") + " — " + e.message); }
}

$("btnCamera").onclick = () => switchTab("tabScan");
document.addEventListener("click", (e) => {
  if (e.target.closest("#btnScanNow")) $("cameraInput").click();
  if (e.target.closest("#btnScanGallery")) $("fileInput").click();
});
for (const inputId of ["fileInput", "cameraInput"]) {
  /* Abbruch des Kamera-Dialogs: Safari feuert (wenn überhaupt) 'cancel'.
     Wer gerade „Weiteres Foto" wollte, hat noch Fotos in der Ablage —
     die müssen wieder aufs Sheet, sonst liegen sie verwaist herum. */
  $(inputId).addEventListener("cancel", () => {
    if (state.stageResume) { state.stageResume = false; pruefeAblage(); }
  });
  $(inputId).onchange = () => {
    const picked = [...$(inputId).files];
    $(inputId).value = "";
    if (!picked.length) {
      if (state.stageResume) { state.stageResume = false; pruefeAblage(); }
      return;
    }
    state.stageResume = false;
    if (picked.length > 1 && inputId === "fileInput") {
      state.addFiles = picked.slice(0, 24);
      openBatchSheet();
      return;
    }
    // Einzelfoto (Kamera ODER Galerie): sofort serverseitig parken —
    // iOS-PWAs verlieren beim Kamera-Wechsel den JS-Speicher!
    stageUpload(picked);
  };
}

async function stageUpload(files) {
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
      toast(L("Kein Netz — dein Foto ist gesichert und wird nachgereicht"), "camera",
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
    stageUpload(p);
  }
});

function openStagedSheet(photos) {
  /* Foto-Sammler: alle Aufnahmen liegen als Streifen vor dir. Jede Kachel hat
     ein × zum Entfernen und Pfeile zum Umsortieren — die erste ist das
     Hauptbild. BEWUSST Pfeile statt Ziehen: Drag-Sortierung auf dem Handy war
     schon einmal „komplett buggy" (Wackel-Modus, 02.08.), Knöpfe treffen
     immer. Der Kamera-Knopf bleibt oben, damit Nachschießen ein Tipp ist. */
  state.stageOrder = photos.map((p) => p.name);
  const n = photos.length;
  const kacheln = photos.map((p, i) => `
    <figure class="ph-kachel" data-name="${esc(p.name)}" data-i="${i}">
      <img src="${esc(url(p.url))}${p.url.includes("?") ? "&" : "?"}w=240" alt="" loading="lazy">
      <button class="ph-weg" data-weg="${esc(p.name)}" aria-label="${esc(L("Foto entfernen"))}">${icon("xmark", 13)}</button>
      ${i === 0 ? `<span class="ph-haupt">${L("Hauptbild")}</span>` : ""}
      <nav class="ph-sort">
        <button data-mv="-1" ${i === 0 ? "disabled" : ""} aria-label="${esc(L("nach vorn"))}">‹</button>
        <button data-mv="1" ${i === n - 1 ? "disabled" : ""} aria-label="${esc(L("nach hinten"))}">›</button>
      </nav>
    </figure>`).join("");

  openSheet(L("Scan prüfen"),
    LF("{0} von 8 Fotos — die erste Aufnahme wird das Hauptbild.", n),
    `<div class="ph-strip">${kacheln}</div>
     <p class="ph-tipp">${L("Tipp: heller Untergrund und Folie ab — durch das Case-Plastik bleibt sichtbar, worauf das Stück liegt.")}</p>
     <div class="ph-add">
       <button class="btn-secondary" id="stageMoreBtn">${icon("camera", 16)} ${L("Foto aufnehmen")}</button>
       <button class="btn-secondary" id="stageGalBtn">${icon("photo", 16)} ${L("Aus Galerie")}</button>
     </div>
     <input id="addNotes" type="text" placeholder="${esc(L("Notiz (optional)"))}">`,
    async () => {
      $("sheetSave").disabled = true;
      try {
        const fd = new FormData();
        fd.append("notes", $("addNotes").value.trim());
        // Reihenfolge mitschicken — sonst sortiert der Server nach Aufnahmezeit
        fd.append("order", (state.stageOrder || []).join(","));
        let r;
        try {
          r = await api("/api/app/collection/items-from-stage?" + devQ(), { method: "POST", body: fd });
        } catch (e) {
          if (e.offline) state.stageKeep = true;
          throw e;
        }
        state.stageKeep = true;
        state.watchNew = r.item_id;
        if (scanMode() === "sell") state.sellWatch.add(r.item_id);
        closeSheet();
        switchTab("tabScan");
        loadCollection();
        toast(`${r.photo_count} ${r.photo_count === 1 ? L("Foto") : L("Fotos")} — ${L("Wird analysiert")}`, "sparkle");
      } catch (e) {
        if (!handleScanError(e)) $("sheetErr").textContent = e.message;
      } finally {
        $("sheetSave").disabled = false;
      }
    }, L("Analysieren"));

  state.stageOpen = true;

  const weiter = (welcher) => {
    state.stageKeep = true;
    state.stageResume = true; state.stageResumeTs = Date.now();
    closeSheet();
    setTimeout(() => $(welcher).click(), 250);
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
}


function openBatchSheet() {
  const n = state.addFiles.length;
  const thumbs = blobThumbs(state.addFiles);
  openSheet("Stapel-Scan", LF("{0} Fotos — SERO ordnet Vorder- und Rückseiten automatisch zu. Slabs bleiben im Case.", n),
    `<div class="add-strip">${thumbs}</div>
     <button class="btn-secondary" id="batchSingle" style="margin-top:10px">${L("Alle Fotos zeigen dasselbe Stück")}</button>`,
    async () => {
      $("sheetSave").disabled = true;
      $("sheetSave").textContent = L("Sortiere Fotos …");
      try {
        const fd = new FormData();
        state.addFiles.forEach((f) => fd.append("files", f));
        fd.append("notes", "");
        const r = await api("/api/app/collection/scan-batch", { method: "POST", body: fd });
        state.addFiles = [];
        closeSheet();
        switchTab("tabScan");
        if (scanMode() === "sell") (r.item_ids || []).forEach((id) => state.sellWatch.add(id));
        toast(LF(r.group_count === 1 ? "{0} Fotos → {1} Stück erkannt" : "{0} Fotos → {1} Stücke erkannt",
          r.photo_count, r.group_count) + (scanMode() === "sell" ? L(" — werden automatisch gelistet") : ""), "sparkle");
        loadCollection();
      } catch (e) {
        $("sheetErr").textContent = e.message;
      } finally {
        $("sheetSave").disabled = false;
        $("sheetSave").textContent = L("Automatisch sortieren");
      }
    }, "Automatisch sortieren");
  $("batchSingle").onclick = () => { closeSheet(); setTimeout(openAddSheet, 250); };
}

function openAddSheet() {
  const thumbs = blobThumbs(state.addFiles);
  openSheet("Scan prüfen", "SERO erkennt das Stück und ermittelt den Marktwert.",
    `<div class="add-strip">${thumbs}</div>
     <input id="addNotes" type="text" placeholder="${esc(L("Notiz (optional)"))}">`,
    async () => {
      $("sheetSave").disabled = true;
      try {
        const fd = new FormData();
        state.addFiles.forEach((f) => fd.append("files", f));
        fd.append("notes", $("addNotes").value.trim());
        const r = await api("/api/app/collection/items", { method: "POST", body: fd });
        state.addFiles = [];
        state.watchNew = r.item_id;   // roter Faden: nach der Analyse direkt ins Stück springen
        if (scanMode() === "sell") state.sellWatch.add(r.item_id);
        switchTab("tabScan");
        loadCollection();
        // Stapel-Scan: direkt die nächste Karte anbieten
        openSheet("Gescannt", "Die Analyse läuft im Hintergrund — du kannst sofort weitermachen.",
          `<button class="btn-primary" id="scanNext">${icon("camera", 18)}<span>${L("Nächste Karte scannen")}</span></button>
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

/* Schnellmenü aus dem Grid (Long-Press) — der kürzeste Weg zum Verkauf */
function openItemMenu(i) {
  const hasLocal = i.photos.some((p) => p.startsWith("/api/app/citem-photo"));
  const sellLabel = L(i.draft_status === "published" ? "Listing verwalten — LIVE"
    : i.draft_id ? "Listing-Entwurf öffnen" : "Auf eBay listen");
  openSheet(i.name.length > 34 ? i.name.slice(0, 34) + "…" : i.name, "", `
    <div class="opt-list">
      <button class="opt" data-m="sell"><span style="display:flex;align-items:center;gap:10px">${icon("bag", 17)} ${sellLabel}</span></button>
      <button class="opt" data-m="fav"><span style="display:flex;align-items:center;gap:10px">${icon(i.favorite ? "starfill" : "star", 17)} ${L(i.favorite ? "Favorit entfernen" : "Als Favorit")}</span></button>
      <button class="opt" data-m="wish"><span style="display:flex;align-items:center;gap:10px">${icon("heart", 17)} ${L(i.wishlist ? "Aus Wunschliste nehmen" : "Auf die Wunschliste")}</span></button>
      <button class="opt" data-m="del" style="color:var(--red)"><span style="display:flex;align-items:center;gap:10px">${icon("trash", 17)} ${L("Entfernen")}</span></button>
    </div>`, null);
  $("sheetBody").querySelectorAll("[data-m]").forEach((btn) => {
    btn.onclick = async () => {
      closeSheet();
      const m = btn.dataset.m;
      try {
        if (m === "sell") {
          if (i.draft_id) return openItemDetail(i.id, "sell");
          if (!hasLocal) return toast("Keine eigenen Fotos — bitte einmal neu scannen");
          const _t = sellTpl();
          await post(`/api/app/collection/item/${i.id}/list`, {
            format: _t.format, auction_days: _t.auction_days,
            price_mode: _t.price_mode, price_value: _t.price_value });
          toast("Listing wird vorbereitet …", "arrowup");
          openItemDetail(i.id, "sell");
        } else if (m === "fav") {
          await post(`/api/app/collection/item/${i.id}`, { favorite: !i.favorite });
          loadCollection();
        } else if (m === "wish") {
          await post(`/api/app/collection/item/${i.id}`, { wishlist: !i.wishlist });
          loadCollection();
        } else if (m === "del") {
          removeItemWithUndo(i);
        }
      } catch (e) { toast(e.message); }
    };
  });
}

function renderScan() {
  renderScanMode();
  // EINE Liste mit Live-Status statt Warteschlange + Verlauf (Karten erschienen doppelt)
  const recent = [...state.items].sort((a, b) => (b.created_at || 0) - (a.created_at || 0)).slice(0, 5);
  $("scanHistLabel").hidden = !recent.length;
  $("scanHistory").innerHTML = recent.map((i) => {
    const busy = i.status === "analyzing" || i.status === "waiting";
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
  if (all) all.onclick = () => switchTab("tabCollection");
}

/* ═══════════════════ Verkauf ═══════════════════ */

async function loadSales() {
  let r;
  try { r = await api("/api/app/sales"); } catch { return; }
  state.sales = r;
  renderSales();
}

function renderSales() {
  const s = state.sales;
  if (!s) return;
  $("salesStats").innerHTML = `
    <div class="stat-row">
      <div class="stat"><b>${s.stats.active}</b><span>aktiv</span></div>
      <div class="stat"><b>${money(s.stats.value_active)}</b><span>Angebotswert</span></div>
      <div class="stat"><b>${s.stats.published_30d}</b><span>${L("in 30 Tagen gelistet")}</span></div>
    </div>`;
  $("salesSeg").querySelectorAll("button").forEach((b) => {
    b.classList.toggle("on", b.dataset.b === state.salesBucket);
    b.onclick = () => { state.salesBucket = b.dataset.b; renderSales(); };
  });
  // Ansicht: Liste -> 2er-Kacheln -> 4er-Kacheln
  let vbtn = $("salesView");
  if (!vbtn) {
    vbtn = document.createElement("button");
    vbtn.id = "salesView";
    vbtn.className = "icon-btn sales-view";
    vbtn.setAttribute("aria-label", L("Ansicht wechseln"));
    $("salesSeg").after(vbtn);
  }
  const mode = localStorage.getItem("sero_sales_view") || "list";
  vbtn.innerHTML = icon(mode === "list" ? "grid" : mode === "g2" ? "copies" : "stack", 17);
  vbtn.onclick = () => {
    const next = mode === "list" ? "g2" : mode === "g2" ? "g4" : "list";
    localStorage.setItem("sero_sales_view", next);
    renderSales();
    toast(next === "list" ? "Liste" : next === "g2" ? "Große Kacheln" : "Kleine Kacheln");
  };
  $("salesList").className = mode === "list" ? "" : `sale-grid ${mode}`;
  const rows = s[state.salesBucket === "active" ? "active" : state.salesBucket === "draft" ? "drafts" : "ended"] || [];
  const chip = (st) => st === "published" ? `<span class="schip live">LIVE</span>`
    : st === "ended" ? `<span class="schip">Beendet</span>`
    : st === "error" ? `<span class="schip err">Fehler</span>`
    : st === "uncertain" ? `<span class="schip warn">Rückfrage</span>`
    : `<span class="schip">Entwurf</span>`;
  const gridMode = (localStorage.getItem("sero_sales_view") || "list") !== "list";
  // Nur Entwürfe zählen, die das Backend auch wirklich veröffentlicht —
  // „Fehler" und „Rückfrage" brauchen erst eine Entscheidung.
  const listbar = rows.filter((r) => !["error", "uncertain"].includes(r.status));
  const offen = rows.length - listbar.length;
  const bulkBtn = state.salesBucket === "draft" && listbar.length >= 2
    ? `<button class="btn-primary" id="bulkPublish" style="margin:0 0 12px">${icon("arrowup", 16)}<span>${
        offen ? LF("{0} von {1} Entwürfen listen", listbar.length, rows.length)
              : LF("Alle {0} Entwürfe listen", listbar.length)}</span></button>`
      + (offen ? `<p class="bulk-note">${LF("{0} brauchen noch deine Prüfung.", offen)}</p>` : "") : "";
  const bulkBox = $("salesBulk");
  if (bulkBox) bulkBox.innerHTML = bulkBtn;
  $("salesList").innerHTML = rows.map((r) => gridMode ? `
    <button class="sale-tile" data-draft="${r.draft_id}" data-item="${r.item_id || ""}">
      ${r.photo ? `<img src="${esc(thumb(r.photo, 480))}" loading="lazy" alt="">` : `<span class="gph-none">${MONO_PH}</span>`}
      ${chip(r.status)}
      <span class="st-t">${esc(r.title)}</span>
      <span class="st-p">${r.price ? money(parseFloat(String(r.price))) : "—"}</span>
    </button>` : `
    <button class="sale-row" data-draft="${r.draft_id}" data-item="${r.item_id || ""}">
      ${r.photo ? `<img src="${r.photo}" loading="lazy" alt="">` : `<span class="mv-ph">${MONO_PH}</span>`}
      <span class="sr-body"><span class="sr-t">${esc(r.title)}</span>
        <span class="sr-m">${r.price ? money(parseFloat(String(r.price))) : "—"} · ${r.format === "AUCTION" ? "Auktion" : "Festpreis"}</span></span>
      ${chip(r.status)}
      <span class="chev">${icon("chevron", 15)}</span>
    </button>`).join("");
  $("salesEmpty").hidden = rows.length > 0;
  if (!rows.length) {
    const v = state.salesBucket;
    $("salesEmpty").innerHTML = v === "active" ? emptyState({
      icon: "bag", titel: "Noch nichts live",
      text: "Liste ein Stück aus deiner Sammlung — SERO baut das Angebot fertig auf.",
      aktion: "Zur Sammlung", onAktion: () => switchTab("tabCollection"),
    }) : v === "draft" ? emptyState({
      icon: "doc", titel: "Keine offenen Entwürfe",
      text: "Entwürfe entstehen, wenn du ein Stück zum Listen vorbereitest.",
      aktion: "Zur Sammlung", onAktion: () => switchTab("tabCollection"),
    }) : emptyState({
      icon: "clock", titel: "Noch nichts beendet",
      text: "Hier landen Angebote, die verkauft oder abgelaufen sind.",
    });
  }
  fadeImgs($("salesList"));
  $("salesList").querySelectorAll(".sale-row, .sale-tile").forEach((b) => {
    b.onclick = async () => {
      if (b.dataset.item) return openItemDetail(b.dataset.item, "sell");
      // Altes Listing ohne Sammlungsstück: automatisch übernehmen (Ein-Objekt-Prinzip)
      try {
        const r = await post(`/api/app/collection/adopt/${b.dataset.draft}`);
        loadCollection();
        openItemDetail(r.item_id, "sell");
      } catch {
        openDraftDetail(b.dataset.draft);
      }
    };
  });
}

/* ═══════════════════ Profil & Einstellungen ═══════════════════ */

/* ── Ein einziger Leer-Zustand für die ganze App ──
   Vorher: Sammlung = ganze Bühne, Verkauf = grauer Satz ins Nichts,
   Übersicht = gar keiner, Filter-Treffer = nackter Text. */
function emptyState({ icon: ic = "stack", titel, text, aktion, onAktion }) {
  const id = "es" + Math.random().toString(36).slice(2, 8);
  setTimeout(() => { const b = $(id); if (b && onAktion) b.onclick = onAktion; }, 0);
  return `<div class="empty compact">
    <span class="es-ic">${icon(ic, 26)}</span>
    <h2>${esc(L(titel))}</h2>
    ${text ? `<p>${esc(L(text))}</p>` : ""}
    ${aktion ? `<button class="btn-primary" id="${id}">${esc(L(aktion))}</button>` : ""}
  </div>`;
}

/* ── Sammler-Fortschritt: Stufe, Punkte, Set-Lücken ── */
/* ── Profil bearbeiten: Name, Avatar, Anmelde-Kennung ── */
/* ── eBay-Setup direkt in der App abschließen (vorher nur via Telegram-Bot
   oder Website möglich — der teuerste Onboarding-Blocker). Richtlinien werden
   automatisch angelegt/übernommen; die App fragt nur die Versandadresse ab. ── */
function openSetupSheet(me) {
  if (!me.ebay_connected) {
    openSheet(L("eBay verbinden"), L("Bevor das Setup starten kann, verbinde zuerst dein eBay-Konto auf der Website."),
      `<p class="sheet-hint" style="font-size:15px;line-height:1.55;margin:0">${L("Öffne die Website, melde dich mit derselben E-Mail an und tippe auf „Mit eBay verbinden“. Danach kommst du hierher zurück.")}</p>`,
      async () => { window.open(url("/onboarding.html"), "_blank"); closeSheet(); }, L("Website öffnen"));
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

function openProfileSheet(me) {
  openSheet(L("Profil"), L("Dein Name erscheint in der App und in deinen Exporten."),
    `<div class="pe-ava" id="peAva">
       ${me.avatar_url ? `<img src="${esc(me.avatar_url)}" alt="">`
                       : `<span>${esc((me.display_name || me.username || me.email || "?")[0].toUpperCase())}</span>`}
       <i>${icon("camera", 15)}</i>
     </div>
     <input id="peName" type="text" maxlength="40" placeholder="${esc(L("Dein Name"))}" value="${esc(me.display_name || "")}">
     <p class="sheet-hint" style="margin:14px 0 4px">${L("Anmelde-Kennung")}</p>
     <input id="peUser" type="text" maxlength="24" autocapitalize="none" placeholder="${esc(L("z. B. sammler_muc"))}" value="${esc(me.username || "")}">
     <p class="pe-note">${L("Mit dieser Kennung kannst du dich statt mit der E-Mail anmelden. Änderst du sie, gilt sofort die neue.")}</p>
     <input id="peFile" type="file" accept="image/*" hidden>`,
    async () => {
      $("sheetSave").disabled = true;
      try {
        const f = $("peFile").files[0];
        if (f) {
          const fd = new FormData(); fd.append("file", f);
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
  $("peFile").onchange = () => {
    const f = $("peFile").files[0];
    if (!f) return;
    $("peAva").innerHTML = `<img data-blob="1" src="${URL.createObjectURL(f)}" alt=""><i>${icon("camera", 15)}</i>`;
    freeBlobs($("peAva"));
  };
}

async function renderProfile() {
  let me = state.me;
  try { me = state.me = await api("/api/me"); } catch { /* alter Stand */ }
  state.settings = await api("/api/app/settings").catch(() => state.settings || { notifications: true });
  if (!me) return;
  const initial = (me.username || me.email || "?")[0].toUpperCase();
  const used = me.used_this_month ?? 0;
  const limit = me.plan_limit;
  const pctv = limit ? Math.min(100, Math.round(used / limit * 100)) : 0;
  const planName = { trial: "Testphase", starter: "Starter", reseller: "Reseller", shop: "Shop" }[me.plan] || me.plan;
  const row = (ic, color, label, right, id = "", tap = false) => `
    <${tap ? "button" : "div"} class="irow ${tap ? "tap" : ""}" ${id ? `id="${id}"` : ""}>
      <span class="ric" style="background:${color}">${icon(ic, 15)}</span>
      <span class="rlabel">${label}</span>${right}
      ${tap ? `<span class="chev">${icon("chevron", 15)}</span>` : ""}</${tap ? "button" : "div"}>`;
  const rv = (v) => `<span class="rvalue">${esc(v)}</span>`;

  $("profileScroll").innerHTML = `
    <h1 class="large-title">Profil</h1>
    <button class="prof-head tap" id="profEdit">
      <span class="pava">${me.avatar_url ? `<img src="${me.avatar_url}">` : initial}</span>
      <span class="ph-txt"><span class="pname">${esc(me.display_name || me.username || L("Dein Name"))}</span>
      <span class="pmail">${me.member_since
        ? LF("Sammler seit {0}", new Date(me.member_since * 1000).toLocaleDateString("de-DE", { month: "long", year: "numeric" }))
        : esc(me.email)}</span></span>
      <span class="chev">${icon("chevron", 16)}</span>
    </button>
    <div class="prof-plan">
      <div class="pp-row"><span>${esc(planName)}</span><span>${limit ? `${used} / ${limit}` : `${used} Listings`}</span></div>
      <div class="pp-sub">${me.plan === "trial" ? LF("Noch {0} Tage Testphase", me.trial_days_left) : L("Listings in diesem Monat")}</div>
      ${limit ? `<div class="bar"><i style="width:${pctv}%"></i></div>` : ""}
      <div class="pp-row" style="margin-top:10px"><span>Scans</span><span>${(state.settings || {}).premium ? "Premium — unbegrenzt" : `${(state.settings || {}).scans_used || 0} / ${(state.settings || {}).scans_limit || 50}`}</span></div>
    </div>
    <button class="premium-card" id="profPremium">
      <span class="pc-ic">${icon("crown", 20)}</span>
      <div><b>SERO Premium</b>
      <p>Unbegrenzte Scans, Preisalarme, erweiterte Statistiken, Cloud-Backup und Export — Verwaltung über die SERO-Website.</p></div>
      <span class="chev">${icon("chevron", 15)}</span>
    </button>
    <div class="section-label">Verbindungen</div>
    <div class="ilist">
      ${row("link", "#3478f6", "eBay-Konto", rv(me.ebay_connected ? "Verbunden" : "Nicht verbunden"))}
      ${row("bubble", "var(--green)", "Telegram", rv(me.telegram_linked ? "Verknüpft" : "—"))}
      ${row("gear", "var(--icon-neutral)", "Setup", rv(me.setup_ready ? "Bereit" : "Unvollständig"), "profSetup", !me.setup_ready)}
    </div>
    <div class="section-label">App</div>
    <div class="ilist">
      ${row("gear", "#3478f6", "Erscheinungsbild", "", "setTheme", true)}
      ${row("bell", "#eb4d3d", "Preisalarm-Hinweise",
        `<span class="sw"><input type="checkbox" id="setNotif" ${state.settings.notifications ? "checked" : ""}><i></i></span>`)}
      ${row("photo", "#c9a961", "Katalog-Bilder im Grid",
        `<span class="sw"><input type="checkbox" id="setCatalog" ${catalogView() ? "checked" : ""}><i></i></span>`)}
    </div>
    <div class="section-label">Daten</div>
    <div class="ilist">
      ${row("tray", "#3478f6", "eBay-Listings importieren", "", "profImport", true)}
      ${row("download", "var(--green)", "Sammlung exportieren (Backup)", "", "profExport", true)}
      ${row("refresh", "#ff9500", "Alle Preise aktualisieren", "", "profRefresh", true)}
    </div>
    <div class="section-label">Mehr</div>
    <div class="ilist">
      ${row("bubble", "var(--green)", "Hilfe & Kontakt", "", "profHelp", true)}
      ${row("shield", "#5a9aa8", "Datenschutz", "", "profPrivacy", true)}
      ${row("doc", "var(--icon-neutral)", "Nutzungsbedingungen", "", "profTerms", true)}
      ${row("link", "var(--icon-neutral)", "SERO-Website öffnen", "", "profSite", true)}
    </div>
    <div class="ilist" style="margin-top:20px">
      ${row("tray", "var(--icon-neutral)", "Abmelden", "", "profLogout", true)}
    </div>
    <div class="ilist danger" style="margin-top:12px">
      ${row("trash", "#d70015", "Konto löschen …", "", "profDelete", true)}
    </div>
    <p class="version">SERO für iOS &amp; Web · v4.0</p>`;

  $("setTheme").onclick = () => {
    const cur = localStorage.getItem("sero_theme") || "auto";
    openOptions("Erscheinungsbild", [
      { label: "Automatisch (System)", value: "auto", sel: cur === "auto" },
      { label: "Hell", value: "light", sel: cur === "light" },
      { label: "Dunkel", value: "dark", sel: cur === "dark" },
    ], (v) => { localStorage.setItem("sero_theme", v); applyTheme(); });
  };
  $("setCatalog").onchange = (e) => {
    localStorage.setItem("sero_catalog", e.target.checked ? "1" : "0");
    renderCollection();
  };
  $("setNotif").onchange = (e) =>
    post("/api/app/settings", { notifications: e.target.checked }).catch(() => toast("Einstellung nicht gespeichert. Versuch es erneut."));
  const pp = $("profPremium");
  if (pp) pp.onclick = openPaywall;
  $("profEdit").onclick = () => openProfileSheet(me);
  const ps = $("profSetup");
  if (ps && !me.setup_ready) ps.onclick = () => openSetupSheet(me);
  const links = { profHelp: "/hilfe.html", profPrivacy: "/datenschutz.html", profTerms: "/agb.html" };
  Object.entries(links).forEach(([id, url]) => {
    const b = $(id); if (b) b.onclick = () => window.open(url, "_blank");
  });
  $("profImport").onclick = () => importListings($("profImport"));
  $("profExport").onclick = () => { window.open("/api/app/export", "_blank"); };
  $("profRefresh").onclick = async () => {
    toast("Preise werden aktualisiert …", "refresh");
    try {
      const r = await post("/api/app/collection/refresh", null, { timeout: 600000 });
      toast(LF("Preise aktualisiert ({0} von {1})", r.updated, r.total), "check");
      loadCollection();
    } catch (e) { toast(e.message); }
  };
  $("profSite").onclick = () => window.open("/", "_blank");
  $("profLogout").onclick = async () => {
    await post("/api/logout").catch(() => {});
    localStorage.removeItem("sero_col");
    location.reload();
  };
}

function closeDetail() {
  const d = $("detail");
  clearTimeout(state.detail?.poll);
  state.detail = null;
  d.classList.add("closing");
  setTimeout(() => {
    // Wurde inzwischen ein neues Detail geöffnet, gehört das Overlay nicht mehr uns.
    if (!d.classList.contains("closing")) return;
    d.hidden = true; d.classList.remove("closing");
  }, 260);
  loadCollection(); loadSales();
  state.dash = null;
}
$("detailClose").onclick = closeDetail;

async function openItemDetail(itemId, seg = "overview") {
  state.detail = { mode: "item", id: itemId, data: null, poll: null, seg };
  $("detail").classList.remove("closing");
  $("detail").hidden = false;
  $("detailTitle").textContent = "";
  // Sofort aus dem Sammlungs-Cache zeichnen — kein Warten, kein Skeleton;
  // die frischen Daten (Verlauf, Verkäufe, Listing) laufen gleich hinterher
  const cached = seg === "overview" && state.items.find((x) => x.id === itemId);
  if (cached) {
    state.detail.data = cached;
    renderDetail(state.detail);
  } else {
    $("detailBody").innerHTML = skel(220, 16) + `<div style="height:14px"></div>` + skel(120);
  }
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
  const det = state.detail;
  if (!det) return;
  clearTimeout(det.poll);
  let data;
  try {
    data = det.mode === "item"
      ? await api(`/api/app/collection/item/${det.id}`)
      : { draft: await api(`/api/app/draft/${det.id}`) };
  } catch (e) {
    $("detailBody").innerHTML = `<div class="err-box">${esc(e.message)}</div>`;
    return;
  }
  if (state.detail !== det) return;
  // Erfolgs-Moment NUR beim echten Übergang Entwurf -> live (nicht bei jedem
  // Öffnen eines längst gelisteten Stücks — das feierte sich bisher selbst)
  const prevPub = det.data?.draft?.published;
  if (det.data && prevPub === false && data.draft?.published) celebrate(data.draft);
  const json = JSON.stringify(data);
  if (force || json !== det.rendered) {
    det.data = data;
    det.rendered = json;
    renderDetail(det);
  }
  const d = data.draft;
  const busy = (det.mode === "item" && data.status === "analyzing")
    || (d && (["downloading", "analyzing"].includes(d.status) || (d.stage && !d.stage.done)));
  if (busy) det.poll = setTimeout(() => refreshDetail(), 1600);
}

/* ── Ehrlicher Preiszustand (Stufe 5) ──────────────────────────────────────
   Die Zahl bleibt immer da — aber „Marktwert" heißt nur, was belegt ist.
   spanne = Richtwert (Angebote oder alte Belege), unbekannt = Schätzung. */
function wertTitel(item) {
  if (item.est_value === null || item.est_value === undefined) return L("Wert unbekannt");
  if (item.price_state === "unbekannt") return L("Richtwert");
  if (item.price_state === "spanne") return L("Marktwert (Richtwert)");
  return L("Marktwert");
}

const PREIS_GRUENDE = {
  ROHPREIS_SLAB: "Preis der ungegradeten Karte — der Slab-Aufschlag fehlt noch.",
  BELEGE_ALT: "Belege älter als 90 Tage — Karten-Märkte drehen schnell.",
  NUR_ANGEBOTE: "Aus aktiven Angeboten, noch kein belegter Verkauf.",
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

function renderDetail(det) {
  const body = $("detailBody");
  const item = det.mode === "item" ? det.data : null;
  const d = det.data.draft || null;

  $("detailTitle").textContent = item ? (item.category || "") : "Listing";
  $("detailTrash").hidden = !item;
  $("detailFav").hidden = !item;
  if (item) {
    $("detailFav").innerHTML = icon(item.favorite ? "starfill" : "star", 18);
    $("detailFav").style.color = item.favorite ? "#f5a623" : "";
    $("detailFav").onclick = () =>
      post(`/api/app/collection/item/${item.id}`, { favorite: !item.favorite })
        .then(() => refreshDetail(true)).catch((e) => toast(e.message));
    $("detailTrash").onclick = () => { closeDetail(); removeItemWithUndo(item); };
    const dup = document.querySelector(".dup-hint[data-dup]");
    if (dup) dup.onclick = () => openItemDetail(dup.dataset.dup);
  }

  const photoUrls = item ? item.photos.map((u) => thumb(u, 1100))
    : (d ? d.photos.map((p) => p.url).filter(Boolean) : []);
  // Nur EIGENE Fotos im Karussell — der Katalog-Scan war zu oft die falsche
  // Karte; er lebt jetzt allein im Korrektur-Flow („Falsche Karte? Suchen")
  const isCard = !!(item && item.card);
  const photos = photoUrls.map((u) =>
    isCard ? `<span class="holo-wrap"><img src="${esc(u)}" loading="lazy" alt=""></span>`
           : `<img src="${esc(u)}" loading="lazy" alt="">`).join("");

  const seg = det.seg || "overview";
  let html = "";
  if (item) {
    const sellTag = d ? (d.published ? " · Live" : d.status === "ended" ? "" : " · Entwurf") : "";
    html += `<div class="seg" id="detailSeg" style="margin:0 0 14px">
      <button data-s="overview" class="${seg === "overview" ? "on" : ""}">Übersicht</button>
      <button data-s="sell" class="${seg === "sell" ? "on" : ""}">Verkaufen${sellTag}</button></div>`;
  }
  if (!item || seg === "overview") html += photos ? `<div class="d-photos">${photos}</div>${photoUrls.length > 1 ? `<div class="d-dots">${photoUrls.map((_, di) => `<i class="${di === 0 ? "on" : ""}"></i>`).join("")}</div>` : ""}` : "";

  if (item && seg === "overview") {
    html += `<div class="d-name">${esc(item.name)}</div>
             <div class="d-cat" style="color:${CAT_COLORS[item.category] || "var(--label-3)"}">${esc(item.category)}${item.graded ? ` · ${esc(item.graded.grader || "")} ${esc(item.graded.grade || "")}` : ""}
             ${(item.tags || []).map((t) => `<span class="tag-chip"># ${esc(t)}</span>`).join("")}</div>`;
    if (item.status === "analyzing") {
      html += `<div class="stage-line"><span class="spinner"></span> ${esc(item.status_text || "Wird analysiert …")}</div>`;
    }
    if (item.error) html += `<div class="err-box">${esc(item.error)}</div>`;
    /* Gleiches Produkt schon in der Sammlung? Nur ein Hinweis — Sammler haben
       Dubletten absichtlich, entschieden wird per Tipp. */
    if (item.dublette) {
      html += `<div class="dup-hint" data-dup="${esc(item.dublette.id)}">
        ${icon("copies", 15)}
        <span>${LF("Dieses Stück hast du schon einmal in der Sammlung: {0}", esc(item.dublette.name))}</span>
        <b>${L("Ansehen")}</b></div>`;
    }

    const paid = item.purchase_price ? parseFloat(String(item.purchase_price).replace(",", ".")) : null;
    let delta = "";
    if (paid !== null && item.est_value !== null && item.est_value !== undefined) {
      const diff = item.est_value - paid;
      delta = `<span class="v-delta ${diff >= 0 ? "up" : "down"}">${diff >= 0 ? "+" : "−"}${money(Math.abs(diff)).replace(" €", "")} €</span>`;
    }
    const pd = item.price_detail || {};
    let trends = "";
    if (item.price_source === "cardmarket" && pd.trend) {
      trends = [trendChip("24h", pd.trend, pd.avg1), trendChip("7T", pd.trend, pd.avg7),
                trendChip("30T", pd.trend, pd.avg30)].filter(Boolean).join("");
    }
    let chartVals = (det.data.history || []).map((p) => p.value);
    if (chartVals.length < 2 && item.price_source === "cardmarket") {
      chartVals = [pd.avg30, pd.avg7, pd.avg1, pd.trend].filter((v) => v !== null && v !== undefined);
    }
    const marketLine = item.market && item.market.median
      ? LF("eBay: {0} aktive Angebote · Median {1}", item.market.count, money(item.market.median)) : "";
    const updated = item.price_updated
      ? new Date(item.price_updated * 1000).toLocaleDateString("de-DE", { day: "numeric", month: "long" }) + ", " +
        new Date(item.price_updated * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })
      : null;
    const alert = det.data.alert;
    html += `
      <div class="value-card v2">
        <div class="v-top">
          <span><span class="v-label">${wertTitel(item)}${item.price_label ? " · " + esc(item.price_label) : ""}${item.price_source ? `<button class="info-i" id="priceInfo" aria-label="Erklärung">i</button>` : ""}</span>
          <span class="v-main">${item.est_value !== null && item.est_value !== undefined ? (item.price_state === "unbekannt" ? "≈ " : "") + money(item.est_value) : "—"}</span></span>
          ${delta}
          <button class="v-refresh ${alert ? (alert.triggered ? "alert-hit" : "alert-on") : ""}" id="alertBtn" aria-label="Preisalarm">${icon("bell", 16)}</button>
          <button class="v-refresh" id="priceRefresh" aria-label="Preis aktualisieren">${icon("refresh", 16)}</button>
        </div>
        ${alert ? `<span class="v-sub" style="color:${alert.triggered ? "var(--green)" : "var(--label-2)"}">
          ${alert.triggered ? L("Alarm ausgelöst") : L("Alarm")}: ${alert.direction === "above" ? "über" : "unter"} ${money(alert.threshold)}</span>` : ""}
        ${trends ? `<div class="trend-chips">${trends}</div>` : ""}
        ${chartVals.length >= 2 ? `<div class="v-chart">${sparkline(chartVals, 300, 54, "sline", true)}</div>` : ""}
        ${pd.tcgplayer_eur ? `<span class="v-sub">TCGplayer (US): ≈ ${money(pd.tcgplayer_eur)}${pd.tcgplayer_usd ? ` ($${String(pd.tcgplayer_usd).replace(".", ",")})` : ""}</span>` : ""}
        ${marketLine ? `<span class="v-sub">${esc(marketLine)}</span>` : ""}
        ${item.price_state && item.price_state !== "belegt" && PREIS_GRUENDE[item.price_reason]
          ? `<span class="v-sub" style="color:var(--label-2)">${esc(L(PREIS_GRUENDE[item.price_reason]))}</span>` : ""}
        ${updated ? `<span class="v-sub dim">${LF("Stand {0}", updated)}</span>` : ""}
      </div>`;

    // Letzte eBay-Verkäufe — IMMER direkt unter dem Marktwert (Svens Regel)
    const soldSales = (item.sold_comps || {}).sales || [];
    html += `<div class="section-label">Letzte eBay-Verkäufe</div><div class="ilist">`
      + (soldSales.length
        ? soldSales.slice(0, 5).map((sm) => `
          <a class="irow tap sample" ${sm.url ? `href="${esc(sm.url)}" target="_blank" rel="noopener"` : ""}>
            ${sm.image ? `<img class="simg" src="${esc(sm.image)}" loading="lazy" alt="">`
                       : `<span class="ric" style="background:var(--green)">${icon("check", 15)}</span>`}
            <span class="rlabel sample-t">${esc(sm.title || "Verkauft")}<br><i style="color:var(--label-2);font-style:normal;font-size:11.5px">${esc(sm.date || "")}</i></span>
            <span class="rvalue" style="color:var(--green);font-weight:700">${money(sm.price_eur)}</span>
            <span class="chev">${icon("link", 13)}</span>
          </a>`).join("")
          + `<div class="irow"><span class="ric" style="background:var(--green)">${icon("chart", 15)}</span>
              <span class="rlabel">${LF("Ø letzte {0} Verkäufe", item.sold_comps.n_avg)}</span>
              <span class="rvalue" style="font-weight:750">${money(item.sold_comps.avg3)}</span></div>`
        : `<div class="irow"><span class="ric" style="background:var(--icon-neutral)">${icon("clock", 15)}</span>
            <span class="rlabel" style="color:var(--label-2)">${LF("Noch keine belegten Verkäufe — SERO sucht automatisch weiter (aktueller Wert: {0})", esc(item.price_label || L("Marktquelle")))}</span></div>`)
      + `</div>`;

    /* Angebotslage mit Markt-Umschalter (Svens Entscheid 03.08.): EU ist
       eBay.de, USA ist eBay.com, Japan sind die Händler mit Standort Japan
       auf eBay.com — einen eigenen eBay-Marktplatz hat Japan nicht mehr.
       Bewusst als ANGEBOTSLAGE beschriftet, nie als Marktwert: die Zahl ist
       das, was Verkäufer verlangen, nicht das, was Käufer zahlen. */
    html += `<div class="section-label offers-head">${L("Aktuelle eBay-Angebote")}
      <span class="offer-seg" id="offerSeg">
        ${["eu", "us", "jp"].map((m) =>
          `<button data-m="${m}" class="${(det.offersMarket || "eu") === m ? "on" : ""}">${{ eu: "EU", us: "USA", jp: "Japan" }[m]}</button>`).join("")}
      </span></div>
      <div id="offersBox"></div>`;

    // Korrektur-Flow: falsche/fehlende Erkennung von Hand richtigstellen
    const fixBtn = `<button class="btn-secondary" id="fixCard" style="margin-top:10px;min-height:42px;font-size:14px">
      ${icon("search", 15)}<span>${item.card ? "Falsche Karte? Richtige suchen" : "Karte in Datenbank suchen"}</span></button>`;

    // Karten-Katalog (wenn identifiziert)
    if (item.card) {
      const c = item.card;
      const crow = (lb, v) => v ? `<div class="irow plain"><span class="rlabel" style="color:var(--label-2)">${lb}</span><span class="rvalue" style="color:var(--label)">${esc(v)}</span></div>` : "";
      html += `<div class="section-label">Karte</div><div class="ilist">
        ${crow("Set", c.set_name)}
        ${crow("Nummer", c.number ? `${c.number}${c.total ? " / " + c.total : ""}` : null)}
        ${crow("Seltenheit", c.rarity)}
        ${crow("Illustrator", c.illustrator)}
        ${crow("Sprache", c.language)}
        ${crow("Druck", (c.variants || []).map((v) => VARIANT_LABELS[v] || v).join(", ") || null)}
      </div>${fixBtn}`;
    } else if (item.status === "ready") {
      html += `<div class="section-label">Karte</div>
        <p class="v-sub" style="display:block;font-size:13.5px;color:var(--label-2);margin:0 4px">Keine Karten-Datenbank-Zuordnung — für Sealed-Produkte normal. Einzelkarte? Dann von Hand zuordnen:</p>${fixBtn}`;
    }


    // Grading-Bereich (nur für identifizierte Einzelkarten)
    if (item.card) {
      const gm = item.graded_market;
      const raw = item.est_value;
      let rows = "";
      if (gm) {
        const g10 = gm.psa10, g9 = gm.psa9;
        if (g10) rows += `<div class="irow"><span class="ric" style="background:#c9a961">${icon("shield", 15)}</span>
          <span class="rlabel">PSA 10</span><span class="rvalue" style="color:var(--label);font-weight:700">${money(g10.median)} <i class="gm-n">· ${g10.count} Angebote</i></span></div>`;
        if (g9) rows += `<div class="irow"><span class="ric" style="background:var(--icon-neutral)">${icon("shield", 15)}</span>
          <span class="rlabel">PSA 9</span><span class="rvalue" style="color:var(--label);font-weight:700">${money(g9.median)} <i class="gm-n">· ${g9.count} Angebote</i></span></div>`;
        if (raw !== null && raw !== undefined) rows += `<div class="irow"><span class="ric" style="background:#5a9aa8">${icon("tag", 15)}</span>
          <span class="rlabel">Roh (deine Karte)</span><span class="rvalue">${money(raw)}</span></div>`;
        if (g10 && raw) {
          const gain = g10.median - raw - 25;
          rows += `<div class="irow"><span class="ric" style="background:${gain > 0 ? "#248a3d" : "var(--icon-neutral)"}">${icon("chart", 15)}</span>
            <span class="rlabel" style="color:${gain > 0 ? "var(--green)" : "var(--label-2)"}">${
              gain > 0 ? LF("Grading könnte sich lohnen: ~+{0} bei PSA 10*", money(gain)) : L("Grading lohnt bei dieser Karte eher nicht*")}</span></div>`;
        }
      }
      html += `<div class="section-label">Grading</div>
        ${rows ? `<div class="ilist">${rows}</div>` : ""}
        ${gm && gm.psa10 ? `<p class="v-sub dim" style="display:block;margin:6px 4px 0">*aktive PSA-Angebote auf eBay, abzüglich ~25 € Grading-Gebühr — keine Garantie</p>` : ""}
        <div class="gr-btns">
          <button class="btn-secondary" id="gmBtn">${icon("refresh", 15)}<span>${gm ? "PSA-Preise aktualisieren" : "PSA-Preise laden"}</span></button>
        </div>`;
    }

    html += `<div class="section-label">Mein Exemplar</div>
      <div class="ilist" id="itemList">
        ${irow("i-cat", "folder", "#3478f6", "Kategorie", item.category)}
        ${irow("i-cond", "tag", "#ff9500", "Zustand", condLabel(item.condition))}
        ${irow("i-qty", "box", "#a355d6", "Stückzahl", String(item.quantity))}
        ${irow("i-paid", "euro", "#5a9aa8", "Kaufpreis", item.purchase_price ? money(parseFloat(String(item.purchase_price).replace(",", "."))) : "—")}
        ${irow("i-tags", "tag", "var(--green)", "Tags", (item.tags || []).length ? item.tags.join(", ") : "—")}
        ${irow("i-notes", "note", "var(--icon-neutral)", "Notiz", item.notes || "—")}
        <div class="irow"><span class="ric" style="background:#e0518e">${icon("heart", 15)}</span>
          <span class="rlabel">Wunschliste</span>
          <span class="sw"><input type="checkbox" id="wishSw" ${item.wishlist ? "checked" : ""}><i></i></span></div>
      </div>`;

  }

  const hasLocalPhotos = item && item.photos.some((p) => p.startsWith("/api/app/citem-photo"));
  const listCta = `<button class="btn-primary" id="btnList">${icon("arrowup", 18)}<span>Auf eBay listen</span></button>
    <p class="v-sub" style="display:block;margin-top:10px;color:var(--label-2);font-size:13px">
      SERO erstellt Titel, Beschreibung, Kategorie und Preisvorschlag — live geht es erst nach deiner Freigabe.</p>`;
  const noPhotosHint = `<div class="err-box" style="color:var(--label-2);background:var(--fill)">
      Für dieses Stück liegen keine eigenen Fotos mehr vor — zum Listen bitte einmal neu
      fotografieren (Scanner) und das alte Stück entfernen.</div>`;

  if (item && seg === "overview") {
    // Verkaufs-Einstieg am Ende der Übersicht — der rote Faden
    html += `<div class="section-label">Verkaufen</div>`;
    if (d) {
      const label = d.published ? "Listing verwalten — LIVE auf eBay"
        : d.status === "ended" ? "Erneut listen" : "Listing-Entwurf fortsetzen";
      html += `<button class="btn-secondary" id="gotoSell">${icon("bag", 17)}<span>${label}</span></button>`;
    } else if (!hasLocalPhotos) {
      html += noPhotosHint;
    } else {
      html += listCta;
    }
  } else if (item && seg === "sell") {
    html += `<div class="sell-head">
      ${item.photos.length ? `<img src="${item.photos[0]}" alt="">` : ""}
      <span>${esc(item.name)}</span></div>`;
    if (d) html += renderDraftSection(d);
    else if (!hasLocalPhotos) html += noPhotosHint;
    else html += listCta;
  } else if (!item) {
    html += `<div class="section-label">eBay</div>`;
    html += d ? renderDraftSection(d) : "";
  }

  body.innerHTML = html;
  const segEl = $("detailSeg");
  if (segEl) segEl.querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      if (det.seg === b.dataset.s) return;
      det.seg = b.dataset.s;
      renderDetail(det);
      $("detailBody").scrollTop = 0;
    };
  });
  const gs = $("gotoSell");
  if (gs) gs.onclick = () => { det.seg = "sell"; renderDetail(det); $("detailBody").scrollTop = 0; };

  const oSeg = $("offerSeg");
  if (oSeg && item) {
    oSeg.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        if ((det.offersMarket || "eu") === b.dataset.m) return;
        det.offersMarket = b.dataset.m;
        haptic("light");
        oSeg.querySelectorAll("button").forEach((x) =>
          x.classList.toggle("on", x.dataset.m === b.dataset.m));
        fuelleOffers(det, item);
      };
    });
    fuelleOffers(det, item);
  }

  if (item) {
    wireRow("i-cat", () => openOptions("Kategorie", CATEGORIES.map((c) => ({
      label: c, value: c, sel: item.category === c,
    })), (v) => patchItem(item.id, { category: v })));
    wireRow("i-cond", () => openInput({
      title: "Zustand", hint: "z. B. Neu · Neuwertig · Gebraucht — sehr gut · Near Mint",
      value: condLabel(item.condition) === "—" ? "" : condLabel(item.condition),
    }, (v) => patchItem(item.id, { condition: v })));
    wireRow("i-qty", () => openStepper(item.quantity, (v) => patchItem(item.id, { quantity: v })));
    wireRow("i-paid", () => openInput({
      title: "Kaufpreis", hint: "Was hast du bezahlt? (leer lassen zum Entfernen)",
      value: eur(item.purchase_price) || "", mode: "decimal", ph: "12,50",
    }, (v) => patchItem(item.id, { purchase_price: v })));
    wireRow("i-tags", () => openInput({
      title: "Tags", hint: "Mit Komma trennen — z. B. Ordner Vitrine, Deck, Verkaufen",
      value: (item.tags || []).join(", "), ph: "Vitrine, Grading-Kandidat",
    }, (v) => patchItem(item.id, { tags: v.split(",").map((t) => t.trim()).filter(Boolean) })));
    wireRow("i-notes", () => openInput({
      title: "Notiz", textarea: true, value: item.notes || "", ph: "Besonderheiten, Herkunft …",
    }, (v) => patchItem(item.id, { notes: v })));
    const wsw = $("wishSw");
    if (wsw) wsw.onchange = () =>
      post(`/api/app/collection/item/${item.id}`, { wishlist: wsw.checked })
        .then(() => refreshDetail(true)).catch((e) => { toast(e.message); wsw.checked = !wsw.checked; });
    const ab = $("alertBtn");
    if (ab) ab.onclick = () => openAlertSheet(item, det.data.alert);
    const fc = $("fixCard");
    if (fc) fc.onclick = () => openCardSearch(item);
    const gmB = $("gmBtn");
    if (gmB) gmB.onclick = async () => {
      gmB.disabled = true;
      toast("PSA-Angebote werden gesucht …", "shield");
      try { await post(`/api/app/collection/item/${item.id}/graded-market`); refreshDetail(true); }
      catch (e) { toast(e.message); gmB.disabled = false; }
    };
    const pi = $("priceInfo");
    if (pi) pi.onclick = () => {
      const [t, txt] = SOURCE_INFO[item.price_source] || ["Marktwert", "Automatisch ermittelter Schätzwert."];
      openSheet(`Woher kommt dieser Preis?`, "", `<p class="sheet-hint" style="font-size:15px;line-height:1.55;margin:0"><b>${esc(t)}:</b> ${esc(txt)}</p>`, null);
    };
    const pr = $("priceRefresh");
    if (pr) pr.onclick = async () => {
      pr.classList.add("spin");
      try {
        await post(`/api/app/collection/item/${item.id}/refresh-price`);
        toast("Preis aktualisiert", "check");
        refreshDetail(true);
      } catch (e) { toast(e.message); }
      finally { pr.classList.remove("spin"); }
    };
  }
  if (item) {
    const btnList = $("btnList");
    if (btnList) btnList.onclick = async () => {
      btnList.disabled = true;
      try {
        const _t = sellTpl();
        await post(`/api/app/collection/item/${item.id}/list`, {
          format: _t.format, auction_days: _t.auction_days,
          price_mode: _t.price_mode, price_value: _t.price_value });
        toast("Listing wird vorbereitet …", "arrowup");
        det.seg = "sell";
        refreshDetail(true);
      } catch (e) {
        toast(e.message);
        btnList.disabled = false;
      }
    };
  }
  if (d) wireDraftSection(d);
  fadeImgs(body);
  // Foto-Punkte: aktive Seite folgt dem Karussell (iOS-Muster)
  const _strip = body.querySelector(".d-photos");
  const _dots = body.querySelectorAll(".d-dots i");
  if (_strip && _dots.length) {
    _strip.addEventListener("scroll", () => {
      const max = Math.max(1, _strip.scrollWidth - _strip.clientWidth);
      const di = Math.round(_strip.scrollLeft / max * (_dots.length - 1));
      _dots.forEach((d2, n) => d2.classList.toggle("on", n === di));
    }, { passive: true });
  }
  // Holo-Tilt: Karte neigt sich zum Zeiger, Glanz wandert mit
  const holoWraps = body.querySelectorAll(".holo-wrap");
  holoWraps.forEach((w) => {
    const move = (e) => {
      const r = w.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      w.style.setProperty("--rx", `${(0.5 - y) * 10}deg`);
      w.style.setProperty("--ry", `${(x - 0.5) * 12}deg`);
      w.style.setProperty("--gx", `${x * 100}%`);
      w.style.setProperty("--gy", `${y * 100}%`);
      w.classList.add("tilting");
    };
    w.addEventListener("pointermove", move);
    w.addEventListener("pointerleave", () => {
      w.classList.remove("tilting");
      w.style.setProperty("--rx", "0deg"); w.style.setProperty("--ry", "0deg");
    });
  });
  // Gyro-Holo: das NEIGEN des iPhones steuert den Glanz wie bei einer echten
  // Holo-Karte im Licht (iOS verlangt eine Nutzer-Geste für die Erlaubnis)
  if (holoWraps.length && window.DeviceOrientationEvent
      && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const arm = () => {
      if (state._gyro) return;
      state._gyro = true;
      window.addEventListener("deviceorientation", (e) => {
        const g = Math.max(-30, Math.min(30, e.gamma || 0));
        const b = Math.max(-30, Math.min(30, (e.beta || 0) - 40));
        document.querySelectorAll(".holo-wrap").forEach((w) => {
          w.classList.add("tilting");
          w.style.setProperty("--rx", `${(-b / 30) * 5}deg`);
          w.style.setProperty("--ry", `${(g / 30) * 6}deg`);
          w.style.setProperty("--gx", `${50 + (g / 30) * 45}%`);
          w.style.setProperty("--gy", `${50 + (b / 30) * 45}%`);
        });
      });
    };
    if (typeof DeviceOrientationEvent.requestPermission === "function") {
      if (state._gyroOk) arm();
      else holoWraps.forEach((w) => w.addEventListener("click", () => {
        // NUR beim Tippen aufs Foto fragen — vorher kam der iOS-Dialog
        // mitten beim Listen-Knopf, ohne jeden Zusammenhang.
        DeviceOrientationEvent.requestPermission()
          .then((r) => { if (r === "granted") { state._gyroOk = true; arm(); } })
          .catch(() => {});
      }, { once: true }));
    } else arm();
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
function wireRow(id, fn) { const el = $(id); if (el) el.onclick = fn; }

async function patchItem(itemId, fields) {
  await post(`/api/app/collection/item/${itemId}`, fields);
  refreshDetail(true);
}

/* ─── eBay-Draft-Sektion ─── */

function renderDraftSection(d) {
  let html = "";
  const isAuc = d.format === "AUCTION";
  const price = eur(d.price);

  if (d.published) html += `<span class="live-pill">LIVE auf eBay</span>`;
  if (d.stage && !d.stage.done) {
    html += `<div class="stage-line"><span class="spinner"></span> ${esc(d.stage.text)}</div>`;
  }
  if (d.question) {
    html += `<div class="qbox"><p>${esc(d.question)}</p>
      <div class="qrow"><input id="qInput" type="text" placeholder="Antwort …">
      <button class="qsend" id="qSend">${icon("arrowup", 17)}</button></div></div>`;
  } else if (d.pending) {
    html += `<div class="qbox"><p>Für dieses Stück fehlen Grading-Angaben. Beispiel: PSA 9.5 12345678</p>
      <div class="qrow"><input id="qInput" type="text" placeholder="Bewerter Note Zertifikat …">
      <button class="qsend" id="qSend">${icon("arrowup", 17)}</button></div></div>`;
  }
  if (d.error_text) {
    html += `<div class="err-box">${esc(d.error_text)}</div>`;
  } else if (d.status === "error") {
    html += `<div class="err-box">Die Erstellung ist fehlgeschlagen — mit „Neu erstellen“ unten kannst du es erneut versuchen.</div>`;
  }
  if (d.assumptions && !d.published) html += `<div class="assume">Annahme: ${esc(d.assumptions)}</div>`;

  if (d.title && !["downloading", "analyzing"].includes(d.status)) {
    html += `
      <button class="price-tap" data-dact="price">
        <span class="pt-price ${price ? "" : "missing"}">${price ? price + " €" : "Preis festlegen …"}</span>
        <span class="pt-sub">${d.price_basis ? esc(L(d.price_basis)) + " · " : ""}${isAuc ? L("Startpreis · Auktion") : L("Sofortkauf")}${d.quantity > 1 ? ` · ${d.quantity} Stück` : ""}${d.fee ? ` · Gebühr${d.quantity > 1 ? " gesamt" : ""} ~${eur(d.fee.fee.toFixed(2))} € · Netto ~${eur(d.fee.net.toFixed(2))} €` : ""}</span>
        <span class="chev">${icon("chevron", 16)}</span>
      </button>
      <div class="seg" data-dseg="fmt">
        <button data-v="FIXED_PRICE" class="${isAuc ? "" : "on"}">Festpreis</button>
        <button data-v="AUCTION" class="${isAuc ? "on" : ""}">Auktion</button>
      </div>
      ${isAuc ? `<div class="seg small" data-dseg="dur">
        ${[1, 3, 5, 7, 10].map((n) => `<button data-v="${n}" class="${d.auction_days === n ? "on" : ""}">${n} Tg</button>`).join("")}
      </div>` : ""}
      <div class="ilist" style="margin-bottom:12px">
        ${drow("cond", "tag", "#ff9500", "Zustand", condLabel(d.condition))}
        ${d.show_usk ? drow("usk", "shield", "#eb4d3d", "Altersfreigabe",
                            d.usk !== null && d.usk !== undefined ? LF("USK ab {0}", d.usk) : L("Keine Angabe")) : ""}
        ${!isAuc ? drow("qty", "box", "#a355d6", "Stückzahl", String(d.quantity)) : ""}
        ${!isAuc ? `<div class="irow"><span class="ric" style="background:#5a9aa8">${icon("percent", 15)}</span>
            <span class="rlabel">Preisvorschlag</span>
            <span class="sw"><input type="checkbox" ${d.best_offer ? "checked" : ""} data-dsw="offer"><i></i></span></div>` : ""}
      </div>
      ${d.description_plain ? `<p class="v-sub" style="display:block;font-size:13.5px;color:var(--label-2);line-height:1.45;margin-bottom:14px">${esc(d.description_plain).slice(0, 200)}${d.description_plain.length > 200 ? "…" : ""}</p>` : ""}
      ${d.published
        ? `<button class="btn-primary success" data-dact="save">Änderungen speichern</button>`
        : `<button class="btn-primary" data-dact="upload">${icon("arrowup", 18)}<span>Auf eBay listen</span></button>`}
      <div class="quick-row" style="margin-top:12px">
        <button class="quick" data-dact="title"><span class="qic">${icon("pencil", 19)}</span><span>Titel</span></button>
        <button class="quick" data-dact="desc"><span class="qic">${icon("doc", 19)}</span><span>Text</span></button>
        <button class="quick" data-dact="img"><span class="qic">${icon("photo", 19)}</span><span>Bilder</span></button>
        <button class="quick" data-dact="regen"><span class="qic">${icon("refresh", 19)}</span><span>Neu</span></button>
        ${d.published
          ? `<button class="quick danger" data-dact="end"><span class="qic">${icon("trash", 19)}</span><span>Beenden</span></button>`
          : `<button class="quick danger" data-dact="discard"><span class="qic">${icon("trash", 19)}</span><span>Verwerfen</span></button>`}
      </div>
      ${d.published && d.item_url ? `<a class="btn-secondary" style="margin-top:12px;text-decoration:none" href="${esc(d.item_url)}" target="_blank">Auf eBay ansehen&nbsp;${icon("link", 14)}</a>` : ""}`;
  }
  return html;
}

function drow(act, ic, color, label, value) {
  return `<button class="irow tap" data-dact="${act}">
    <span class="ric" style="background:${color}">${icon(ic, 15)}</span>
    <span class="rlabel">${esc(L(label))}</span>
    <span class="rvalue">${esc(L(value))}</span>
    <span class="chev">${icon("chevron", 15)}</span></button>`;
}

function wireDraftSection(d) {
  const body = $("detailBody");
  body.querySelectorAll("[data-dact]").forEach((b) => {
    b.onclick = () => handleDraftAction(d, b.dataset.dact, b);
  });
  body.querySelectorAll("[data-dsw]").forEach((sw) => {
    sw.onchange = () => doAction(d.id, sw.dataset.dsw)
      .catch((e) => { toast(e.message); sw.checked = !sw.checked; });
  });
  body.querySelectorAll("[data-dseg]").forEach((seg) => {
    const kind = seg.dataset.dseg;
    seg.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        if (b.classList.contains("on")) return;
        seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
        doAction(d.id, kind, kind === "dur" ? b.dataset.v : null).catch((e) => toast(e.message));
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
}

async function doAction(draftId, action, value = null, opts = {}) {
  const r = await post(`/api/app/draft/${draftId}/action`, { action, value });
  refreshDetail(true);
  return r;
}

function handleDraftAction(d, act, btn) {
  if (act === "price") {
    openInput({ title: d.price ? "Preis ändern" : "Preis festlegen",
                hint: d.format === "AUCTION" ? "Startpreis der Auktion in Euro" : "Sofortkauf-Preis in Euro",
                value: eur(d.price) || "", mode: "decimal", ph: "16,90" },
      (v) => doAction(d.id, "price", v));
  } else if (act === "title") {
    openInput({ title: "Titel", hint: "Max. 80 Zeichen — Marke, Modell, Variante",
                value: d.title || "" }, (v) => doAction(d.id, "title", v));
  } else if (act === "desc") {
    openInput({ title: "Beschreibung", hint: "Dein Text ersetzt die automatische Beschreibung.",
                textarea: true, value: d.description_plain || "" }, (v) => doAction(d.id, "desc", v));
  } else if (act === "cond") {
    openInput({ title: "Zustand", hint: "z. B. Neu · Neuwertig · Gebraucht — sehr gut",
                value: condLabel(d.condition) === "—" ? "" : condLabel(d.condition) },
      (v) => doAction(d.id, "cond", v));
  } else if (act === "qty") {
    openStepper(d.quantity, (v) => doAction(d.id, "qty", String(v)));
  } else if (act === "usk") {
    const opts = [0, 6, 12, 16, 18].map((n) => ({ label: LF("USK ab {0} freigegeben", n), value: String(n), sel: d.usk === n }));
    opts.push({ label: "Keine Angabe", value: "none", sel: d.usk === null || d.usk === undefined });
    openOptions("Altersfreigabe", opts, (v) => doAction(d.id, "uskset", v));
  } else if (act === "img") {
    openImageSheet(d);
  } else if (act === "regen") {
    confirmSheet("Neu erstellen?", "Titel, Beschreibung und Preis werden neu generiert — manuelle Änderungen gehen verloren.", "Neu erstellen")
      .then((ok) => ok && doAction(d.id, "regen").catch((e) => toast(e.message)));
  } else if (act === "upload") {
    btn.disabled = true;
    doAction(d.id, "upload").catch((e) => toast(e.message)).finally(() => (btn.disabled = false));
  } else if (act === "save") {
    btn.disabled = true;
    doAction(d.id, "save").catch((e) => toast(e.message)).finally(() => (btn.disabled = false));
  } else if (act === "discard") {
    confirmSheet("Listing-Entwurf verwerfen?", "Das Stück bleibt in deiner Sammlung.", "Verwerfen", true)
      .then((ok) => ok && post(`/api/app/draft/${d.id}/action`, { action: "discard", value: null })
        .then(() => refreshDetail(true)).catch((e) => toast(e.message)));
  } else if (act === "end") {
    confirmSheet("Listing beenden?", "Es wird sofort von eBay genommen. Das Stück bleibt in deiner Sammlung.", "Beenden", true)
      .then((ok) => ok && post(`/api/app/draft/${d.id}/action`, { action: "end", value: null })
        .then(() => { toast("Listing beendet"); refreshDetail(true); }).catch((e) => toast(e.message)));
  }
}

function openImageSheet(d) {
  const rows = d.photos.map((p, i) => {
    let label;
    if (!p.has_render) label = LF("Bild {0} — Original (kein Freisteller)", i + 1);
    else if (p.is_original) label = `Bild ${i + 1} — Original → freistellen`;
    else label = `Bild ${i + 1} — Freigestellt → Original`;
    return `<div class="img-row">${p.url ? `<img src="${p.url}">` : ""}
            <button class="btn-secondary" data-i="${i}" ${p.has_render ? "" : "disabled style='opacity:.45'"}>${label}</button></div>`;
  }).join("");
  openSheet(L("Bilder"), L("Pro Foto zwischen Freisteller und Original wechseln."),
    rows + `<button class="btn-secondary" id="rerenderAll" style="margin-top:10px">${icon("refresh", 16)}<span>Alle neu rendern</span></button>`, null);
  $("sheetBody").querySelectorAll("[data-i]").forEach((b) => {
    b.onclick = async () => {
      try { await doAction(d.id, "imgtog", b.dataset.i); closeSheet(); }
      catch (e) { $("sheetErr").textContent = e.message; }
    };
  });
  $("rerenderAll").onclick = async () => {
    closeSheet();
    toast("Bilder werden neu gerendert …", "refresh");
    try { await doAction(d.id, "imgren"); toast("Bilder neu gerendert", "check"); }
    catch (e) { toast(e.message); }
  };
}

/* ═══════════════════ Sheets (Infrastruktur) ═══════════════════ */

function openSheet(title, hint, bodyHTML, onSave, saveLabel = "Übernehmen", destructive = false) {
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
  _bd.hidden = false;
  _sh.hidden = false;
  $("viewApp").classList.add("recede");
  const save = $("sheetSave");
  save.textContent = L(saveLabel);
  save.classList.toggle("destructive", destructive);
  save.hidden = !onSave;
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
  $("sheetBackdrop").onclick = closeSheet;
}
function closeSheet() {
  // Scan-Sheet ohne „Analysieren"/„Weiteres Foto" verlassen = Vorgang abgebrochen:
  // geparkte Fotos verwerfen, damit sie nicht in den nächsten Scan rutschen.
  if (state.stageOpen) {
    state.stageOpen = false;
    if (state.stageKeep) state.stageKeep = false;
    else post("/api/app/collection/stage/clear?" + devQ()).catch(() => {});
  }
  const sh = $("sheet"), bd = $("sheetBackdrop");
  $("viewApp").classList.remove("recede");
  if (sh.hidden) return;
  // Abfahrt mit Animation statt Schlagartig-Verschwinden
  sh.style.transform = "";
  sh.classList.add("closing"); bd.classList.add("closing");
  setTimeout(() => {
    // Wurde inzwischen ein neues Sheet geöffnet, hat openSheet „closing"
    // entfernt — dann gehört dieses Sheet nicht mehr uns.
    if (!sh.classList.contains("closing")) return;
    sh.hidden = true; bd.hidden = true;
    sh.classList.remove("closing"); bd.classList.remove("closing");
  }, 260);
}

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
  const sh = $("sheet"), grip = document.querySelector(".sheet-grip");
  if (!grip) return;
  let sy = null;
  grip.style.touchAction = "none";
  grip.addEventListener("pointerdown", (e) => { sy = e.clientY; grip.setPointerCapture(e.pointerId); });
  grip.addEventListener("pointermove", (e) => {
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
  grip.addEventListener("pointerup", end);
  grip.addEventListener("pointercancel", end);
})();

function openInput(cfg, onSubmit) {
  const body = cfg.textarea
    ? `<textarea id="sheetField" placeholder="${esc(L(cfg.ph || ""))}">${esc(cfg.value || "")}</textarea>`
    : `<input id="sheetField" type="text" ${cfg.mode ? `inputmode="${cfg.mode}"` : ""}
        value="${esc(cfg.value || "")}" placeholder="${esc(L(cfg.ph || ""))}">`;
  openSheet(cfg.title, cfg.hint, body, async () => {
    try {
      await onSubmit($("sheetField").value.trim());
      closeSheet();
    } catch (e) {
      $("sheetErr").textContent = e.message;
    }
  });
  setTimeout(() => $("sheetField").focus(), 300);
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
      <button class="stbtn" id="stMinus">${icon("minus", 22)}</button>
      <span class="stval" id="stVal">${val}</span>
      <button class="stbtn" id="stPlus">${icon("plus", 22)}</button>
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
    openSheet(title, text, "", () => { closeSheet(); resolve(true); }, okLabel, destructive);
    const done = (v) => () => { closeSheet(); resolve(v); };
    $("sheetCancel").onclick = done(false);
    $("sheetBackdrop").onclick = done(false);
  });
}

boot();

/* Seiten-Wischen zwischen den Haupt-Tabs (freigegebenes Motion-Paket, Punkt 4) */
(() => {
  const ORDER = ["tabHome", "tabCollection", "tabSales", "tabProfile"];
  let tx = null, ty = null;
  document.addEventListener("touchstart", (e) => {
    tx = e.touches[0].clientX; ty = e.touches[0].clientY;
  }, { passive: true });
  document.addEventListener("touchend", (e) => {
    if (tx === null || !$("detail").hidden || !$("sheet").hidden) { tx = null; return; }
    if (e.target.closest(".gitem, .feed, input, .add-strip")) { tx = null; return; }
    const dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty;
    tx = null;
    if (Math.abs(dx) < 70 || Math.abs(dy) > 50) return;
    const cur = ORDER.findIndex((id) => !$(id).hidden);
    if (cur === -1) return;
    const next = ORDER[cur + (dx < 0 ? 1 : -1)];
    if (next) switchTab(next);
  }, { passive: true });
})();

/* Konto löschen — DSGVO, doppelt bestätigt */
document.addEventListener("click", (e) => {
  if (!e.target.closest("#profDelete")) return;
  openSheet("Konto löschen", "Das entfernt alles unwiderruflich: Sammlung, Fotos, Listings-Entwürfe, Preisverlauf und dein Konto.",
    `<p class="sheet-hint" style="color:var(--red);font-weight:700">Tippe unten auf „Endgültig löschen“, um es wirklich zu tun.</p>`,
    async () => {
      try {
        await post("/api/app/account/delete");
        localStorage.clear();
        location.reload();
      } catch (err) { $("sheetErr").textContent = err.message; }
    }, "Endgültig löschen");
});

document.addEventListener("click", (e) => {
  if (!e.target.closest("#bulkPublish")) return;
  openSheet("Alle Entwürfe listen", "Jeder Entwurf geht nacheinander live auf eBay — mit deinen Vorlage-Einstellungen.",
    `<p class="sheet-hint">Das lässt sich nicht rückgängig machen (Listings kannst du danach auf eBay beenden).</p>`,
    async () => {
      try { const r = await post("/api/app/sales/publish-drafts");
        closeSheet(); toast(LF("{0} Entwürfe werden gelistet …", r.count), "arrowup");
      } catch (err) { $("sheetErr").textContent = err.message; }
    }, "Jetzt listen");
});
renderScanMode();
