/* SERO — Profil & Einstellungen (Navigator + korrekte Stats/Tarif/Links) */
"use strict";

const SERO_APP_VERSION = "4.1.0";
/* Die Anleitung liegt als echte Seite neben der App (SITE_DIR unter „/"),
   nicht als leerer Tab. */
const SERO_GUIDE_URL = "/guide.html";

const settingsNav = {
  stack: [],
  returnFocus: null,
  push(id, title, renderFn) {
    this.stack.push({ id, title, renderFn });
    this._paint();
  },
  pop() {
    if (this.stack.length <= 1) {
      this.close();
      return;
    }
    this.stack.pop();
    this._paint();
  },
  close() {
    this.stack = [];
    const v = document.getElementById("settingsView");
    if (v) {
      v.hidden = true;
      v.setAttribute("aria-hidden", "true");
    }
    const app = document.getElementById("viewApp");
    if (app) app.classList.remove("settings-open");
    if (this.returnFocus && typeof this.returnFocus.focus === "function") {
      try { this.returnFocus.focus(); } catch (_) { /* */ }
    }
    this.returnFocus = null;
  },
  openRoot(id, title, renderFn, fromEl) {
    this.returnFocus = fromEl || document.activeElement;
    this.stack = [{ id, title, renderFn }];
    this._paint();
  },
  _paint() {
    const top = this.stack[this.stack.length - 1];
    if (!top) return;
    const v = document.getElementById("settingsView");
    const title = document.getElementById("settingsTitle");
    const body = document.getElementById("settingsBody");
    const back = document.getElementById("settingsBack");
    if (!v || !title || !body) return;
    v.hidden = false;
    v.setAttribute("aria-hidden", "false");
    document.getElementById("viewApp")?.classList.add("settings-open");
    title.textContent = typeof L === "function" ? L(top.title) : top.title;
    if (back) {
      back.hidden = false;
      back.setAttribute("aria-label", typeof L === "function" ? L("Zurück") : "Zurück");
    }
    body.innerHTML = "";
    top.renderFn(body);
    body.scrollTop = 0;
    try { back?.focus(); } catch (_) { /* */ }
  },
};

function _esc(s) {
  return typeof esc === "function" ? esc(String(s ?? "")) : String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _L(s) { return typeof L === "function" ? L(s) : s; }
function _LF(tpl, ...a) {
  if (typeof LF === "function") return LF(tpl, ...a);
  let i = 0;
  return tpl.replace(/\{(\d+)\}/g, () => String(a[i++] ?? ""));
}
function _icon(n, s) { return typeof icon === "function" ? icon(n, s) : ""; }

function planLabel(planKey) {
  return ({ trial: "Testphase", starter: "Starter", reseller: "Reseller", shop: "Shop" }[planKey]
    || planKey || "—");
}

/* Der Sticker sagt dasselbe wie der Tarifname — in Satzschreibung.
   Versalien lasen sich wie ein Warnhinweis, nicht wie eine Tarifangabe. */
function planBadge(planKey) {
  return planLabel(planKey);
}

/** Widerspruchsfreie Tariftexte — nur Listings-Kontingent, Scans separat. */
function planUsageCopy(me, settings) {
  const plan = (me.plan || "trial").toLowerCase();
  const used = me.used_this_month ?? 0;
  const limit = me.plan_limit;
  const paid = ["starter", "reseller", "shop"].includes(plan) && me.active !== false;
  if (plan === "shop") {
    return {
      paid: true,
      lines: [_L("Listings ohne Monatslimit"), _L("Scans ohne Limit")],
      bar: null,
    };
  }
  if (plan === "starter" || plan === "reseller") {
    const lim = limit || (plan === "starter" ? 30 : 200);
    return {
      paid: true,
      lines: [
        _LF("{0} von {1} Listings in diesem Monat", used, lim),
        _L("Scans ohne Limit"),
      ],
      bar: { used, limit: lim },
    };
  }
  // Testphase / Free
  const days = me.trial_days_left ?? 0;
  const scansUsed = settings?.scans_used ?? 0;
  const scansLimit = settings?.scans_limit ?? 50;
  const lines = [];
  if (days > 0) lines.push(_LF("Noch {0} Tage Testphase", days));
  else lines.push(_L("Testphase beendet"));
  if (!settings?.premium) {
    lines.push(_LF("{0} von {1} Gratis-Scans", scansUsed, scansLimit));
  } else {
    lines.push(_L("Scans ohne Limit"));
  }
  return { paid: false, lines, bar: !settings?.premium ? { used: scansUsed, limit: scansLimit } : null };
}

function fmtMemberSince(ts) {
  if (!ts) return "—";
  const d = new Date((Number(ts) < 1e12 ? Number(ts) * 1000 : Number(ts)));
  if (Number.isNaN(d.getTime())) return "—";
  try {
    return d.toLocaleDateString(typeof LANG !== "undefined" && LANG === "en" ? "en-GB" : "de-DE", {
      year: "numeric", month: "long", day: "numeric",
    });
  } catch {
    return d.toISOString().slice(0, 10);
  }
}

function shortEmail(email) {
  if (!email) return "";
  if (email.length <= 28) return email;
  const [u, d] = String(email).split("@");
  if (!d) return email.slice(0, 25) + "…";
  const uu = u.length > 12 ? u.slice(0, 10) + "…" : u;
  return uu + "@" + d;
}

function platformLabel() {
  const standalone = window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent);
  if (standalone && ios) return "iOS PWA";
  if (standalone) return "PWA";
  return "Web";
}

function settingsRow({ id, iconName, title, sub, value, danger, switchId, checked, chevron = true }) {
  const right = switchId
    ? `<span class="sw"><input type="checkbox" id="${_esc(switchId)}" ${checked ? "checked" : ""} aria-labelledby="${_esc(id)}-lab"><i></i></span>`
    : (value != null && value !== ""
      ? `<span class="set-val">${_esc(value)}</span>` : "")
      + (chevron && !danger ? `<span class="chev">${_icon("chevron", 14)}</span>` : "");
  const tag = switchId ? "div" : "button";
  const type = switchId ? "" : `type="button"`;
  return `<${tag} class="set-row${danger ? " danger" : ""}" id="${_esc(id)}" ${type}>
    <span class="set-ic">${_icon(iconName, 18)}</span>
    <span class="set-text">
      <span class="set-title" id="${_esc(id)}-lab">${_L(title)}</span>
      ${sub ? `<span class="set-sub">${_L(sub)}</span>` : ""}
    </span>
    ${right}
  </${tag}>`;
}

function settingsGroup(label, rowsHtml) {
  return `<section class="set-group">
    ${label ? `<h3 class="set-h">${_L(label)}</h3>` : ""}
    <div class="set-card">${rowsHtml}</div>
  </section>`;
}

async function fetchProfileSummary() {
  try {
    const s = await api("/api/app/profile-summary");
    return s;
  } catch (e) {
    return { active_on_ebay: null, in_collection: null, sold: null, error: true };
  }
}

function statCell(val, label, busy) {
  const inner = busy
    ? `<span class="skel skel-stat" aria-hidden="true"></span>`
    : `<b>${_esc((val === null || val === undefined) ? "—" : String(val))}</b>`;
  return `<div class="tv-prof-stat">${inner}<span>${_L(label)}</span></div>`;
}

async function openBillingOrPlans(me) {
  const plan = (me.plan || "trial").toLowerCase();
  const paid = ["starter", "reseller", "shop"].includes(plan);
  if (paid) {
    settingsNav.openRoot("billing", "Tarif & Abrechnung", (body) => renderBillingPane(body, me), document.activeElement);
    return;
  }
  // Testphase: Planauswahl / Premium-Seite, nicht Scan-Paywall missbrauchen
  settingsNav.openRoot("billing", "Tarif & Abrechnung", (body) => renderBillingPane(body, me), document.activeElement);
}

function renderBillingPane(body, me) {
  const usage = planUsageCopy(me, state.settings || {});
  const plan = (me.plan || "trial").toLowerCase();
  const paid = ["starter", "reseller", "shop"].includes(plan);
  let bar = "";
  if (usage.bar && usage.bar.limit) {
    const pct = Math.min(100, Math.round(100 * usage.bar.used / usage.bar.limit));
    bar = `<div class="prof-plan-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>`;
  }
  body.innerHTML = `
    <div class="set-card set-pad">
      <p class="set-plan-name">${_esc(planLabel(plan))}</p>
      ${usage.lines.map((t) => `<p class="set-sub">${_esc(t)}</p>`).join("")}
      ${bar}
      <button type="button" class="btn-primary" id="billAction" style="margin-top:16px">
        ${paid ? _L("Abo verwalten") : _L("Tarif wählen")}
      </button>
      <p class="set-sub" id="billMsg" role="status" aria-live="polite" style="margin-top:10px"></p>
    </div>`;
  const btn = document.getElementById("billAction");
  const msg = document.getElementById("billMsg");
  if (!btn) return;
  btn.onclick = async () => {
    btn.disabled = true;
    if (msg) msg.textContent = "";
    try {
      if (paid) {
        const r = await post("/api/billing-portal");
        if (r.dev) {
          if (msg) msg.textContent = r.message || _L("Billing-Portal im Testmodus nicht verfügbar.");
          toast(r.message || _L("Testmodus"), "info");
          return;
        }
        if (!r.portal_url) {
          if (msg) msg.textContent = _L("Portal-Adresse fehlt. Versuch es erneut.");
          return;
        }
        window.open(r.portal_url, "_blank", "noopener");
      } else {
        const url = (typeof PREMIUM_URL !== "undefined") ? PREMIUM_URL : "https://seromunich.com/premium";
        window.open(url, "_blank", "noopener");
      }
    } catch (e) {
      if (msg) msg.textContent = e.message || _L("Aktion fehlgeschlagen");
      toast(e.message || _L("Aktion fehlgeschlagen"));
    } finally {
      btn.disabled = false;
    }
  };
}

function openProfileEdit(me) {
  let pendingAvatar = null;
  openSheet(_L("Profil bearbeiten"), "",
    `<button type="button" class="pe-ava" id="peAva" aria-label="${_esc(_L("Profilbild ändern"))}">
       ${me.avatar_url ? `<img src="${_esc(me.avatar_url)}" alt="">`
                       : `<span class="pe-letter">${_esc((me.display_name || me.username || me.email || "?")[0].toUpperCase())}</span>`}
       <span class="pe-ava-overlay"><i>${_icon("camera", 20)}</i><em>${_L("Profilbild ändern")}</em></span>
     </button>
     <label class="set-field-lab" for="peName">${_L("Anzeigename")}</label>
     <input id="peName" type="text" maxlength="40" value="${_esc(me.display_name || "")}">
     <p class="field-err" id="peNameErr" hidden></p>
     <label class="set-field-lab" for="peUser">${_L("Anmelde-Kennung")}</label>
     <input id="peUser" type="text" maxlength="24" autocapitalize="none" value="${_esc(me.username || "")}">
     <p class="field-err" id="peUserErr" hidden></p>
     <p class="set-field-lab">${_L("E-Mail")}</p>
     <p class="set-readonly">${_esc(me.email || "—")}</p>
     <p class="pe-note">${_L("Anmeldung per E-Mail-Code, kein Passwort")}</p>
     <p class="set-field-lab">${_L("Mitglied seit")}</p>
     <p class="set-readonly">${_esc(fmtMemberSince(me.member_since))}</p>
     <input id="peFile" type="file" accept="image/*" hidden>`,
    async () => {
      $("sheetSave").disabled = true;
      ["peNameErr", "peUserErr"].forEach((id) => { const el = $(id); if (el) { el.hidden = true; el.textContent = ""; } });
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
        closeSheet();
        renderProfile();
        toast(_L("Profil gespeichert"), "check");
      } catch (e) {
        const msg = e.message || _L("Speichern fehlgeschlagen");
        if (/kenn|user|name/i.test(msg) && $("peUserErr")) {
          $("peUserErr").hidden = false; $("peUserErr").textContent = msg;
        } else if ($("peNameErr")) {
          $("peNameErr").hidden = false; $("peNameErr").textContent = msg;
        }
        $("sheetErr").textContent = msg;
      } finally { $("sheetSave").disabled = false; }
    }, _L("Sichern"));
  $("peAva").onclick = () => $("peFile").click();
  $("peFile").onchange = async () => {
    const f = $("peFile").files[0];
    if (!f) return;
    try {
      pendingAvatar = await squareImageBlob(f, 512);
      const url = URL.createObjectURL(pendingAvatar);
      $("peAva").innerHTML =
        `<img data-blob="1" src="${url}" alt=""><span class="pe-ava-overlay"><i>${_icon("camera", 20)}</i><em>${_L("Profilbild ändern")}</em></span>`;
    } catch (e) {
      pendingAvatar = null;
      toast(e.message || _L("Foto konnte nicht geladen werden"));
    }
  };
}

function renderAccountPane(body, me) {
  body.innerHTML = `
    ${settingsGroup("Konto", `
      ${settingsRow({ id: "accEdit", iconName: "person", title: "Profil bearbeiten", sub: me.email || "", value: "" })}
      ${settingsRow({ id: "accLogout", iconName: "logout", title: "Abmelden", chevron: false, danger: true })}
    `)}
    <section class="set-group danger-zone">
      <h3 class="set-h">${_L("Gefahrenzone")}</h3>
      <div class="set-card set-pad">
        <p class="set-sub">${_L("Löscht Sammlung, Fotos, Entwürfe, Preisverlauf und dein SERO-Konto.")}</p>
        <p class="set-sub warn">${_L("Bereits auf eBay veröffentlichte Angebote bleiben bei eBay bestehen und müssen dort beendet werden.")}</p>
        <button type="button" class="btn-secondary" id="accExportFirst">${_L("Zuerst Sammlung exportieren")}</button>
        <label class="set-field-lab" for="accDelConfirm">${_L("Tippe LÖSCHEN zur Bestätigung")}</label>
        <input id="accDelConfirm" type="text" autocomplete="off" autocapitalize="characters">
        <button type="button" class="btn-primary destructive" id="accDeleteGo" disabled>${_L("Konto endgültig löschen")}</button>
      </div>
    </section>`;
  document.getElementById("accEdit").onclick = () => openProfileEdit(me);
  document.getElementById("accLogout").onclick = async () => {
    await post("/api/logout").catch(() => {});
    try { storeSafe.remove("sero_col"); } catch (_) { /* */ }
    location.reload();
  };
  document.getElementById("accExportFirst").onclick = (e) => exportCollection(e.currentTarget);
  const inp = document.getElementById("accDelConfirm");
  const go = document.getElementById("accDeleteGo");
  /* Das Bestätigungswort muss dem Label folgen, sonst tippt man in der
     englischen App DELETE und der Knopf bleibt grau. */
  const delWord = _L("LÖSCHEN");
  const typedOk = () => inp.value.trim().toUpperCase() === delWord.toUpperCase();
  inp.oninput = () => { go.disabled = !typedOk(); };
  go.onclick = async () => {
    if (!typedOk()) return;
    go.disabled = true;
    try {
      await post("/api/app/account/delete");
      try { storeSafe.remove("sero_col"); } catch (_) { /* */ }
      location.reload();
    } catch (e) {
      toast(e.message);
      go.disabled = false;
    }
  };
}

function renderSellPane(body, me) {
  const ebayVal = me.ebay_needs_reconnect ? _L("Neu verbinden")
    : (me.ebay_connected ? _L("Verbunden") : _L("Nicht verbunden"));
  const setupVal = me.setup_ready ? _L("Bereit") : _L("Einrichtung abschließen");
  body.innerHTML = settingsGroup("eBay", `
    ${settingsRow({ id: "sellEbay", iconName: "link", title: "eBay verbinden", sub: me.ebay_shop || _L("Verkaufskonto"), value: ebayVal })}
    ${settingsRow({ id: "sellSetup", iconName: "gear", title: "Versand & eBay-Richtlinien", sub: _L("Standort und Verkaufsrichtlinien"), value: setupVal })}
    ${settingsRow({ id: "sellTpl", iconName: "doc", title: "Verkaufsvorlage", sub: _L("Format, Preisregel, Bildhintergrund") })}
  `) + settingsGroup("Telegram", `
    ${settingsRow({ id: "sellTg", iconName: "bubble", title: "Telegram",
      value: me.telegram_linked ? _L("Verknüpft") : _L("Nicht verknüpft") })}
  `);
  /* Die Sheets liegen über der Einstellungen-Ansicht. Vorher wurde der ganze
     Stapel geschlossen — nach „Fertig“ stand man auf der Sammlung statt wieder
     in „eBay & Verkaufssetup“. */
  document.getElementById("sellEbay").onclick = () => openEbayConnectSheet(me);
  document.getElementById("sellSetup").onclick = () => openSetupSheet(me);
  document.getElementById("sellTpl").onclick = () => openSellTemplate();
  document.getElementById("sellTg").onclick = () => {
    if (me.telegram_linked) {
      toast(_L("Telegram ist verknüpft"), "check");
      return;
    }
    settingsNav.push("tg", "Telegram", (b) => renderTelegramPane(b, me));
  };
}

async function renderTelegramPane(body, me) {
  body.innerHTML = `<div class="set-card set-pad"><p class="set-sub">${_L("Code wird geladen …")}</p></div>`;
  try {
    const r = await post("/api/telegram-code");
    body.innerHTML = `
      <div class="set-card set-pad">
        <p class="set-sub">${_L("Öffne den SERO-Bot und sende diesen Code:")}</p>
        <p class="tg-code" id="tgCode">${_esc(r.code || "")}</p>
        <button type="button" class="btn-secondary" id="tgCopy">${_L("Code kopieren")}</button>
        <a class="btn-primary" id="tgOpen" href="${_esc(r.url || (r.bot ? ("https://t.me/" + r.bot) : "#"))}" target="_blank" rel="noopener">${_L("SERO-Bot öffnen")}</a>
        <button type="button" class="btn-plain" id="tgRefresh">${_L("Verbindung prüfen")}</button>
        <p class="set-sub" id="tgStatus" role="status"></p>
      </div>`;
    document.getElementById("tgCopy").onclick = async () => {
      try {
        await navigator.clipboard.writeText(r.code || "");
        toast(_L("Code kopiert"), "check");
      } catch { toast(_L("Kopieren nicht möglich")); }
    };
    document.getElementById("tgRefresh").onclick = async () => {
      const fresh = await api("/api/me").catch(() => null);
      if (fresh) state.me = fresh;
      const st = document.getElementById("tgStatus");
      if (fresh?.telegram_linked) {
        if (st) st.textContent = _L("Verknüpft");
        toast(_L("Telegram verknüpft"), "check");
        renderProfile();
      } else if (st) st.textContent = _L("Noch nicht verknüpft");
    };
  } catch (e) {
    body.innerHTML = `<div class="set-card set-pad"><p class="set-sub">${_esc(e.message || _L("Code nicht verfügbar"))}</p></div>`;
  }
}

function themeValueLabel() {
  if (typeof themeIsDark === "function") return themeIsDark() ? _L("Dunkel") : _L("Hell");
  const cur = (typeof storeSafe !== "undefined" ? storeSafe.getString("sero_theme", "auto") : "auto") || "auto";
  return ({ auto: _L("Automatisch"), light: _L("Hell"), dark: _L("Dunkel") })[cur] || _L("Automatisch");
}

function catalogValueLabel() {
  const on = typeof catalogView === "function" ? catalogView() : false;
  return on ? _L("Katalogbilder, wenn verfügbar") : _L("Eigene Fotos");
}

function motionValueLabel() {
  const red = document.documentElement.classList.contains("reduced-effects")
    || (typeof storeSafe !== "undefined" && storeSafe.getString("sero_motion") === "reduced");
  return red ? _L("Reduziert") : _L("Automatisch");
}

function renderAppearPane(body, me, summary) {
  const alertsOn = !!(state.settings?.price_alerts_enabled ?? state.settings?.notifications ?? true);
  const nAlerts = summary?.active_alerts;
  body.innerHTML = settingsGroup("", `
    ${settingsRow({ id: "apTheme", iconName: "gear", title: "Erscheinungsbild", value: themeValueLabel() })}
    ${settingsRow({ id: "apCatalog", iconName: "photo", title: "Bilder in der Sammlung", value: catalogValueLabel() })}
  `) + settingsGroup(_L("Preisalarme"), `
    ${settingsRow({
      id: "apAlerts", iconName: "bell",
      title: alertsOn ? "Preisalarme aktiv" : "Preisalarme pausiert",
      sub: _L("Bestehende Schwellen bleiben beim Pausieren gespeichert")
        + (alertsOn && nAlerts != null ? " · " + _LF("{0} aktiv", nAlerts) : ""),
      switchId: "apAlertsSw", checked: alertsOn, chevron: false,
    })}
  `);
  document.getElementById("apTheme").onclick = () => {
    const cur = storeSafe.getString("sero_theme", "auto") || "auto";
    openOptions(_L("Erscheinungsbild"), [
      { label: _L("Automatisch"), value: "auto", sel: cur === "auto" },
      { label: _L("Hell"), value: "light", sel: cur === "light" },
      { label: _L("Dunkel"), value: "dark", sel: cur === "dark" },
    ], (v) => {
      storeSafe.setString("sero_theme", v);
      applyTheme();
      renderAppearPane(body, me, summary);
    });
  };
  /* Sprachauswahl entfernt (Master 30.08.): die App ist English-only. Ein
     Umschalter, der nur eine Sprache anbietet, ist eine leere Tür. */
  document.getElementById("apCatalog").onclick = () => {
    const on = catalogView();
    openOptions(_L("Bilder in der Sammlung"), [
      { label: _L("Eigene Fotos"), value: "0", sel: !on },
      { label: _L("Katalogbilder, wenn verfügbar"), value: "1", sel: on },
    ], (v) => {
      storeSafe.setString("sero_catalog", v);
      renderCollection();
      renderAppearPane(body, me, summary);
    });
  };
  const sw = document.getElementById("apAlertsSw");
  if (sw) {
    sw.onchange = async (e) => {
      try {
        await post("/api/app/settings", { price_alerts_enabled: e.target.checked });
        state.settings = { ...(state.settings || {}), price_alerts_enabled: e.target.checked, notifications: e.target.checked };
        const lab = document.getElementById("apAlerts-lab");
        if (lab) lab.textContent = _L(e.target.checked ? "Preisalarme aktiv" : "Preisalarme pausiert");
        toast(e.target.checked ? _L("Preisalarme aktiv") : _L("Preisalarme pausiert"), "check");
      } catch {
        e.target.checked = !e.target.checked;
        toast(_L("Einstellung nicht gespeichert. Versuch es erneut."));
      }
    };
  }
}

/* Backup-Download. Vorher stand hier `window.location = "/api/app/export"`:
   schlägt das fehl (Session weg, offline, App-Hülle auf anderer Domain),
   passiert entweder nichts oder die App-Ansicht wird durch eine Fehlerseite
   ersetzt. Jetzt: holen, als Datei anbieten, Ergebnis immer sichtbar melden —
   auch bei leerer Sammlung (gültiges leeres Backup). */
async function exportCollection(rowEl) {
  if (rowEl) rowEl.style.pointerEvents = "none";
  toast(_L("Backup wird erstellt …"), "download");
  try {
    const data = await api("/api/app/export");
    const blob = new Blob([JSON.stringify(data, null, 1)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = "sero-sammlung.json";
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => { try { URL.revokeObjectURL(href); } catch (_) { /* */ } }, 4000);
    const n = Array.isArray(data.items) ? data.items.length : 0;
    toast(_LF("Backup geladen — {0} Stücke", n), "check");
  } catch (e) {
    toast(e.message || _L("Backup fehlgeschlagen"));
  } finally {
    if (rowEl) rowEl.style.pointerEvents = "";
  }
}

function renderDataPane(body) {
  body.innerHTML = settingsGroup("Daten & Backup", `
    ${settingsRow({ id: "dataImport", iconName: "tray", title: "eBay-Listings importieren",
      sub: "Neue und noch nicht vorhandene Listings übernehmen" })}
    ${settingsRow({ id: "dataExport", iconName: "download", title: "Sammlung exportieren",
      sub: "JSON-Backup mit Sammlung und Stammdaten laden" })}
  `) + settingsGroup("Sammlung warten", `
    ${settingsRow({ id: "dataRefresh", iconName: "refresh", title: "Marktwerte neu abrufen",
      sub: "Verwendet echte Belege und kann einige Minuten dauern" })}
    ${settingsRow({ id: "dataRescan", iconName: "scanframe", title: "Erkennung für alle Stücke neu starten",
      sub: "Nur verwenden, wenn Set, Nummer oder Sprache bei vielen Stücken falsch sind" })}
  `);
  document.getElementById("dataImport").onclick = () => { settingsNav.close(); importListings(); };
  document.getElementById("dataExport").onclick = (e) => exportCollection(e.currentTarget);
  document.getElementById("dataRefresh").onclick = async () => {
    // 0 ist eine gültige Zahl — mit `|| "…"` blieb der Platzhalter stehen.
    const n = (state.items || []).length;
    const ok = await confirmSheet(
      _L("Marktwerte neu abrufen"),
      _LF("SERO holt für bis zu {0} Stücke frische Belege. Das kann einige Minuten dauern.", n),
      _L("Jetzt abrufen"));
    if (!ok) return;
    const btn = document.getElementById("dataRefresh");
    if (btn) btn.style.pointerEvents = "none";
    toast(_L("Marktwerte werden abgerufen …"), "refresh");
    try {
      const r = await post("/api/app/collection/refresh", null, { timeout: 600000 });
      toast(_LF("Preise aktualisiert ({0} von {1})", r.updated, r.total), "check");
      loadCollection(); loadDashboard();
    } catch (e) { toast(e.message); }
    finally { if (btn) btn.style.pointerEvents = ""; }
  };
  document.getElementById("dataRescan").onclick = async () => {
    const n = (state.items || []).filter((i) => !i.wishlist && !i.sold).length;
    const ok = await confirmSheet(
      _L("Erkennung neu starten"),
      _LF("SERO analysiert bis zu {0} Stücke mit Foto erneut. Nur nötig, wenn Zuordnung oft falsch ist.", n),
      _L("Neu starten"));
    if (!ok) return;
    const btn = document.getElementById("dataRescan");
    if (btn) btn.style.pointerEvents = "none";
    toast(_L("Erkennung läuft …"), "scanframe");
    try {
      const r = await post("/api/app/collection/rescan-all");
      toast(_LF("{0} Stücke in der Warteschlange", r.enqueued), "check");
      loadCollection();
    } catch (e) { toast(e.message); }
    finally { if (btn) btn.style.pointerEvents = ""; }
  };
}

function renderHelpPane(body) {
  const faq = (typeof window !== "undefined" && typeof window.faqAccordionHtml === "function")
    ? window.faqAccordionHtml("help-faq")
    : "";
  body.innerHTML = settingsGroup("Hilfe & Kontakt", `
    ${settingsRow({ id: "helpGuide", iconName: "question", title: "Anleitung öffnen", sub: "Guide auf der SERO-Website" })}
    ${settingsRow({ id: "helpReport", iconName: "bubble", title: "Problem melden", sub: "E-Mail an den Support" })}
    ${settingsRow({ id: "helpDiag", iconName: "info", title: "Diagnose kopieren", sub: "Version und Browserfamilie, ohne persönliche Daten" })}
    ${settingsRow({ id: "helpShare", iconName: "share", title: "SERO weiterempfehlen" })}
  `) + (faq ? settingsGroup("Häufige Fragen", faq) : "");
  document.getElementById("helpGuide").onclick = () => openExternalUrl(SERO_GUIDE_URL);
  document.getElementById("helpReport").onclick = () => {
    const sub = encodeURIComponent("SERO Support");
    const bodyTxt = encodeURIComponent(`SERO ${SERO_APP_VERSION} · ${platformLabel()}\n\n`);
    window.location = `mailto:hello@seromunich.com?subject=${sub}&body=${bodyTxt}`;
  };
  document.getElementById("helpDiag").onclick = async () => {
    const last = (typeof SM !== "undefined" && SM.errors?.list) ? (SM.errors.list()[0] || null) : null;
    const tab = ["tabHome", "tabCollection", "tabScan", "tabSales", "tabProfile"]
      .find((id) => document.getElementById(id) && !document.getElementById(id).hidden) || "?";
    const lines = [
      `SERO ${SERO_APP_VERSION}`,
      `platform=${platformLabel()}`,
      `standalone=${!!(window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone)}`,
      `online=${navigator.onLine}`,
      `lang=${document.documentElement.lang || "?"}`,
      `tab=${tab}`,
      `uaFamily=${/Safari/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent) ? "Safari" : (/Chrome/.test(navigator.userAgent) ? "Chrome" : "Other")}`,
      last ? `lastError=${String(last.code || last.message || last).slice(0, 80)}` : "lastError=none",
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      toast(_L("Diagnose kopiert"), "check");
    } catch { toast(_L("Kopieren nicht möglich")); }
  };
  document.getElementById("helpShare").onclick = () => shareSero();
}

/* Rechtstexte liegen als statische Seite unter /legal.html. Der Chevron in der
   Zeile verspricht ein Ziel — in der installierten PWA wurde das Fenster von
   window.open aber verschluckt. Darum holt SERO den Abschnitt und zeigt ihn
   direkt in den Einstellungen; scheitert das, gibt es eine sichtbare Meldung
   plus Link statt einer toten Zeile. */
const LEGAL_SECTIONS = {
  legImp: { anchor: "impressum", href: "/legal.html#impressum", title: "Impressum" },
  legPriv: { anchor: "datenschutz", href: "/legal.html#datenschutz", title: "Datenschutz" },
  legTerms: { anchor: "agb", href: "/legal.html#agb", title: "Nutzungsbedingungen" },
};
let _legalDoc = null;

async function legalSectionHtml(anchor) {
  if (!_legalDoc) {
    const res = await fetch("/legal.html", { credentials: "same-origin" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    _legalDoc = new DOMParser().parseFromString(await res.text(), "text/html");
  }
  const start = _legalDoc.getElementById(anchor);
  if (!start) throw new Error("Abschnitt fehlt");
  const parts = [];
  let n = start.nextElementSibling;
  while (n && n.tagName !== "H2") {
    if (n.tagName !== "SCRIPT") parts.push(n.outerHTML);
    n = n.nextElementSibling;
  }
  if (!parts.length) throw new Error("Abschnitt leer");
  return parts.join("");
}

function renderLegalText(body, key) {
  const sec = LEGAL_SECTIONS[key];
  if (!sec) return;
  body.innerHTML = `<section class="set-group"><div class="set-card set-pad">
    <p class="set-sub legal-skel" aria-busy="true">${_L("Rechtstext")}</p></div></section>`;
  legalSectionHtml(sec.anchor).then((html) => {
    body.innerHTML = `<section class="set-group">
      <div class="set-card set-pad legal-pane">${html}</div></section>`;
  }).catch(() => {
    body.innerHTML = `<section class="set-group"><div class="set-card set-pad">
      <p class="set-sub">${_L("Der Text konnte gerade nicht geladen werden.")}</p>
      <button type="button" class="btn-secondary" id="legalExt">${_L("Im Browser öffnen")}</button>
    </div></section>`;
    const b = document.getElementById("legalExt");
    if (b) b.onclick = () => openExternalUrl(sec.href);
  });
}

function renderLegalPane(body) {
  body.innerHTML = settingsGroup("Rechtliches", `
    ${settingsRow({ id: "legImp", iconName: "doc", title: "Impressum" })}
    ${settingsRow({ id: "legPriv", iconName: "shield", title: "Datenschutz" })}
    ${settingsRow({ id: "legTerms", iconName: "doc", title: "Nutzungsbedingungen" })}
  `);
  Object.keys(LEGAL_SECTIONS).forEach((key) => {
    const row = document.getElementById(key);
    if (!row) return;
    row.onclick = () => settingsNav.push(key, LEGAL_SECTIONS[key].title,
      (b) => renderLegalText(b, key));
  });
}

function renderAboutPane(body) {
  body.innerHTML = `
    <div class="set-card set-pad about-card">
      <img src="assets/app-icon.png?v=7" alt="" width="64" height="64" class="about-icon">
      <p class="set-plan-name">SERO</p>
      <p class="set-sub">${_esc(SERO_APP_VERSION)} · ${_esc(platformLabel())}</p>
      <button type="button" class="btn-secondary" id="aboutSite">${_L("Website öffnen")}</button>
    </div>`;
  document.getElementById("aboutSite").onclick = () =>
    openExternalUrl("https://seromunich.com");
}

function hubCount(v) {
  return (v === null || v === undefined || v === "") ? "" : String(v);
}

function openSalesBucket(bucket) {
  try {
    if (typeof settingsNav !== "undefined") settingsNav.close();
  } catch (_) { /* */ }
  try { state.ebayHubFocus = bucket === "ended" ? "ended" : "active"; } catch (_) { /* */ }
  if (typeof switchTab === "function") switchTab("tabSales");
  try {
    state.salesBucket = bucket || "draft";
    state._salesBucketTouched = true;
  } catch (_) { /* */ }
  if (typeof renderSales === "function" && state.sales) renderSales();
  if (typeof loadSales === "function") loadSales();
}

function renderSettingsList(body, me, summary) {
  const themeLab = themeValueLabel();
  const themeShort = (themeLab === _L("Hell") || themeLab === _L("Dunkel"))
    ? themeLab : _L("Dunkel");
  const alertsOn = !!(state.settings?.price_alerts_enabled ?? state.settings?.notifications ?? true);
  const ebayVal = me.ebay_connected ? _L("Verbunden") : _L("Nicht verbunden");
  body.innerHTML = settingsGroup("", `
    ${settingsRow({ id: "setEbay", iconName: "link", title: "eBay verbinden", value: ebayVal })}
    ${settingsRow({ id: "setAppear", iconName: "gear", title: "Darstellung", value: themeShort })}
    ${settingsRow({ id: "setAlerts", iconName: "bell", title: "Preisalarme", value: alertsOn ? _L("An") : _L("Aus") })}
    ${settingsRow({ id: "setData", iconName: "tray", title: "Daten / Export" })}
    ${settingsRow({ id: "setHelp", iconName: "question", title: "Hilfe" })}
    ${settingsRow({ id: "setLegal", iconName: "shield", title: "Rechtliches" })}
    ${settingsRow({ id: "setAbout", iconName: "info", title: "Über SERO", value: SERO_APP_VERSION })}
    ${settingsRow({ id: "setAccount", iconName: "person", title: "Konto & Profil" })}
  `);
  const pushPane = (id, title, fn) => settingsNav.push(id, title, fn);
  const ebay = document.getElementById("setEbay");
  if (ebay) ebay.onclick = () => pushPane("sell", "eBay & Verkaufssetup", (b) => renderSellPane(b, me));
  const appear = document.getElementById("setAppear");
  if (appear) appear.onclick = () => pushPane("appear", "Darstellung", (b) => renderAppearPane(b, me, summary));
  const alerts = document.getElementById("setAlerts");
  if (alerts) alerts.onclick = () => pushPane("appear", "Darstellung", (b) => renderAppearPane(b, me, summary));
  const data = document.getElementById("setData");
  if (data) data.onclick = () => pushPane("data", "Daten & Backup", (b) => renderDataPane(b));
  const help = document.getElementById("setHelp");
  if (help) help.onclick = () => pushPane("help", "Hilfe & Kontakt", (b) => renderHelpPane(b));
  const legal = document.getElementById("setLegal");
  if (legal) legal.onclick = () => pushPane("legal", "Rechtliches", (b) => renderLegalPane(b));
  const about = document.getElementById("setAbout");
  if (about) about.onclick = () => pushPane("about", "Über SERO", (b) => renderAboutPane(b));
  const account = document.getElementById("setAccount");
  if (account) account.onclick = () => pushPane("account", "Konto & Profil", (b) => renderAccountPane(b, me));
}

function paintProfileHub(sc, me, summary, statsBusy) {
  if (!sc || !me) return;
  const usage = planUsageCopy(me, state.settings);
  const handle = me.username ? ("@" + me.username) : shortEmail(me.email);
  const a11y = _LF("Profil von {0} bearbeiten", me.display_name || me.username || me.email || "SERO");
  const trialLine = usage.lines[0] || "";
  const stats = statsBusy
    ? `${statCell(null, "Aktiv", true)}${statCell(null, "Besitz", true)}${statCell(null, "Verkauft", true)}`
    : `${statCell(summary.active_on_ebay, "Aktiv")}${statCell(summary.in_collection, "Besitz")}${statCell(summary.sold, "Verkauft")}`;
  sc.innerHTML = `
    <button type="button" class="tv-prof-card tv-prof-hit" id="profCard" aria-label="${_esc(a11y)}">
      <div class="tv-prof-top">
        <span class="tv-ava" aria-hidden="true">
          ${me.avatar_url
            ? `<img src="${_esc(me.avatar_url)}" alt="">`
            : `<img src="assets/app-icon.png?v=7" alt="">`}
          <span class="tv-ava-cam">${_icon("camera", 14)}</span>
        </span>
        <span class="tv-prof-info">
          <span class="tv-pname">${_esc(me.display_name || me.username || _L("Dein Name"))}</span>
          <span class="tv-phandle">${_esc(me.email || handle)}</span>
          ${trialLine ? `<span class="tv-badge">${_esc(trialLine)}</span>` : ""}
        </span>
        <span class="chev" aria-hidden="true">${_icon("chevron", 16)}</span>
      </div>
      <div class="tv-prof-stats"${statsBusy ? ' aria-busy="true"' : ' aria-live="polite"'}>
        ${stats}
      </div>
    </button>

    <div class="set-card">
      ${settingsRow({ id: "menuSettings", iconName: "gear", title: "Einstellungen" })}
    </div>
    ${me.ebay_needs_reconnect ? `<p class="sheet-hint tv-reconnect">${_L("Damit Verkäufe korrekt erkannt werden, verbinde eBay einmal neu.")}</p>` : ""}
  `;
  const card = document.getElementById("profCard");
  if (card) card.onclick = () => openProfileEdit(me);
  const setOpen = document.getElementById("menuSettings");
  if (setOpen) {
    setOpen.onclick = () => settingsNav.push("settings", "Einstellungen",
      (b) => renderSettingsList(b, me, summary || {}));
  }
}

async function renderProfile(into) {
  let sc = into;
  if (!sc) {
    const overlay = document.getElementById("settingsView");
    const top = settingsNav.stack[settingsNav.stack.length - 1];
    if (overlay && !overlay.hidden && top && top.id === "profile") {
      sc = document.getElementById("settingsBody");
    }
  }
  if (!sc) {
    if (typeof openSeroProfile === "function") {
      openSeroProfile();
      return;
    }
    return;
  }
  if (state.me) paintProfileHub(sc, state.me, null, true);

  let me = state.me;
  try { me = state.me = await api("/api/me"); } catch { /* */ }
  state.settings = await api("/api/app/settings").catch(() => state.settings || { notifications: true, price_alerts_enabled: true });
  const summary = await fetchProfileSummary();
  if (!me) return;

  paintProfileHub(sc, me, summary, false);

  if (typeof paintTopAva === "function") paintTopAva();

  /* Das Wiederöffnen einer Einstellungsseite nach dem Neuladen hing allein am
     Sprachwechsel. Der ist weg (English-only), also auch dieser Umweg — den
     Schlüssel setzte sonst niemand. */
}

function wireSettingsChrome() {
  const back = document.getElementById("settingsBack");
  if (back && !back._seroWired) {
    back._seroWired = true;
    back.onclick = () => settingsNav.pop();
  }
}

wireSettingsChrome();

// Überschreibt die ältere renderProfile aus sero.js, sobald dieses Skript geladen ist.
window.renderProfile = renderProfile;
window.renderAccountPane = renderAccountPane;
window.SERO_APP_VERSION = SERO_APP_VERSION;
window.settingsNav = settingsNav;
window.planUsageCopy = planUsageCopy;
