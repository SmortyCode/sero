/* SERO mobile stability helpers — Storage, Gesten, Viewport, Latest-Wins, Diagnose.
   Wird vor sero.js geladen. Kein Framework. Testbar über window.SeroMobile. */
"use strict";

(function (global) {
  const SeroMobile = global.SeroMobile || {};

  /* ── sicherer Browser-Speicher ── */
  const mem = Object.create(null);
  function storeGetRaw(key) {
    try {
      if (typeof localStorage === "undefined") return mem[key] ?? null;
      return localStorage.getItem(key);
    } catch (_) {
      return mem[key] ?? null;
    }
  }
  function storeSetRaw(key, val) {
    try {
      if (typeof localStorage !== "undefined") localStorage.setItem(key, val);
      mem[key] = val;
      return true;
    } catch (e) {
      mem[key] = val;
      return false;
    }
  }
  function storeRemove(key) {
    try {
      if (typeof localStorage !== "undefined") localStorage.removeItem(key);
    } catch (_) { /* blockiert */ }
    delete mem[key];
  }
  function getString(key, fallback = null) {
    const v = storeGetRaw(key);
    return v === null || v === undefined ? fallback : v;
  }
  function setString(key, val) {
    return storeSetRaw(key, String(val));
  }
  function getJSON(key, fallback = null) {
    const raw = storeGetRaw(key);
    if (raw === null || raw === undefined || raw === "") return fallback;
    try {
      return JSON.parse(raw);
    } catch (_) {
      storeRemove(key);
      return fallback;
    }
  }
  function setJSON(key, val) {
    try {
      return storeSetRaw(key, JSON.stringify(val));
    } catch (_) {
      return false;
    }
  }
  SeroMobile.store = { getString, setString, remove: storeRemove, getJSON, setJSON, _mem: mem };

  /* ── Latest-Request-Wins ── */
  function makeLatestWins() {
    let gen = 0;
    let ctrl = null;
    return {
      begin() {
        gen += 1;
        const my = gen;
        if (ctrl) try { ctrl.abort(); } catch (_) { /* */ }
        ctrl = (typeof AbortController !== "undefined") ? new AbortController() : null;
        return {
          id: my,
          signal: ctrl ? ctrl.signal : undefined,
          isCurrent() { return my === gen; },
        };
      },
      current() { return gen; },
    };
  }
  SeroMobile.makeLatestWins = makeLatestWins;

  /* ── Gestenentscheidung (testbar, ohne DOM-Zwang) ── */
  const HORIZONTAL_SEL = [
    "[data-horizontal-scroll]",
    ".chips", ".col-chips", ".ph-strip", ".add-strip", ".recent-strip", ".d-photos",
    ".d-gallery-main", ".d-gallery-thumbs",
    ".feed", ".gitem", ".range-row",
  ].join(",");
  const INTERACTIVE_SEL = "input, textarea, select, button, a, label, [role='button'], [contenteditable='true']";

  function axisLock(dx, dy, threshold = 12) {
    const ax = Math.abs(dx), ay = Math.abs(dy);
    if (ax < threshold && ay < threshold) return null;
    return ax > ay * 1.15 ? "x" : ay > ax * 1.15 ? "y" : null;
  }

  function shouldAllowTabSwipe(opts) {
    const {
      dx, dy,
      sheetOpen = false, detailOpen = false, modalOpen = false,
      target = null, minDx = 70, maxDy = 50,
      hasHorizontalAncestor = null,
      isInteractive = null,
    } = opts || {};
    if (sheetOpen || detailOpen || modalOpen) return false;
    if (Math.abs(dx) < minDx || Math.abs(dy) > maxDy) return false;
    if (Math.abs(dx) <= Math.abs(dy) * 1.2) return false;
    const el = target;
    if (el && typeof el.closest === "function") {
      if (el.closest(HORIZONTAL_SEL)) return false;
      if (el.closest(INTERACTIVE_SEL)) return false;
    }
    if (typeof hasHorizontalAncestor === "function" && hasHorizontalAncestor()) return false;
    if (typeof isInteractive === "function" && isInteractive(el)) return false;
    return true;
  }

  SeroMobile.gestures = {
    HORIZONTAL_SEL,
    INTERACTIVE_SEL,
    axisLock,
    shouldAllowTabSwipe,
  };

  /* ── visualViewport → CSS-Variablen ── */
  function installViewportController(root) {
    root = root || (typeof document !== "undefined" ? document.documentElement : null);
    if (!root) return { stop() {}, sync() {} };
    let raf = 0;
    const write = () => {
      raf = 0;
      const vv = global.visualViewport;
      const layoutH = global.innerHeight || 0;
      const h = vv ? vv.height : layoutH;
      const offsetTop = vv ? vv.offsetTop : 0;
      const offsetLeft = vv ? vv.offsetLeft : 0;
      const kb = Math.max(0, Math.round(layoutH - h - offsetTop));
      root.style.setProperty("--vv-height", Math.round(h) + "px");
      root.style.setProperty("--vv-offset-top", Math.round(offsetTop) + "px");
      root.style.setProperty("--vv-offset-left", Math.round(offsetLeft) + "px");
      root.style.setProperty("--vv-keyboard", kb + "px");
      root.style.setProperty("--app-height", Math.round(h) + "px");
      root.classList.toggle("vv-keyboard", kb > 60);
    };
    const schedule = () => {
      if (raf) return;
      raf = global.requestAnimationFrame ? global.requestAnimationFrame(write) : (write(), 0);
    };
    write();
    const vv = global.visualViewport;
    if (vv) {
      vv.addEventListener("resize", schedule);
      vv.addEventListener("scroll", schedule);
    }
    global.addEventListener("resize", schedule);
    global.addEventListener("orientationchange", schedule);
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", () => { if (!document.hidden) schedule(); });
    }
    return { sync: write, stop() {} };
  }
  SeroMobile.installViewportController = installViewportController;

  /* ── In-flight Dedup: gleicher Schlüssel teilt ein Promise ── */
  function makeInflightDedup() {
    const inflight = new Map();
    return {
      run(key, fn) {
        if (inflight.has(key)) return inflight.get(key);
        let p;
        try { p = Promise.resolve(fn()); }
        catch (e) { p = Promise.reject(e); }
        p = p.finally(() => inflight.delete(key));
        inflight.set(key, p);
        return p;
      },
      has(key) { return inflight.has(key); },
    };
  }
  SeroMobile.makeInflightDedup = makeInflightDedup;

  /* ── Fehler-Ring (bereinigt, max. 20) ── */
  const errorRing = [];
  function pushError(entry) {
    const clean = {
      t: Date.now(),
      area: String(entry.area || "app").slice(0, 40),
      type: String(entry.type || "Error").slice(0, 60),
      status: entry.status == null ? null : Number(entry.status) || 0,
      tab: String(entry.tab || "").slice(0, 24),
      online: typeof navigator !== "undefined" ? !!navigator.onLine : null,
      hidden: typeof document !== "undefined" ? !!document.hidden : null,
      standalone: typeof navigator !== "undefined"
        && (!!navigator.standalone || (global.matchMedia && matchMedia("(display-mode: standalone)").matches)),
      req: entry.req ? String(entry.req).slice(0, 24) : null,
    };
    errorRing.push(clean);
    while (errorRing.length > 20) errorRing.shift();
    return clean;
  }
  function safeAsync(fn, area) {
    return async function wrapped() {
      try {
        return await fn.apply(this, arguments);
      } catch (e) {
        pushError({
          area: area || (fn && fn.name) || "async",
          type: (e && e.name) || "Error",
          status: e && e.status,
        });
        throw e;
      }
    };
  }
  SeroMobile.errors = { push: pushError, list: () => errorRing.slice(), safeAsync };

  /* ── Holo: max. 1 Schreibzyklus pro Frame ── */
  function makeHoloController() {
    let wraps = [];
    let pending = null;
    let raf = 0;
    let active = false;
    let onOrient = null;
    let writeCount = 0;
    const apply = () => {
      raf = 0;
      if (!pending || !active) return;
      const p = pending; pending = null;
      writeCount += 1;
      wraps.forEach((w) => {
        if (!w.isConnected) return;
        w.classList.add("tilting");
        w.style.setProperty("--rx", p.rx);
        w.style.setProperty("--ry", p.ry);
        w.style.setProperty("--gx", p.gx);
        w.style.setProperty("--gy", p.gy);
      });
    };
    const queue = (vals) => {
      pending = vals;
      if (!raf) raf = global.requestAnimationFrame(apply);
    };
    return {
      setWraps(list) { wraps = Array.from(list || []); },
      queue,
      get writeCount() { return writeCount; },
      activate(handlerFactory) {
        if (active) return;
        active = true;
        onOrient = (e) => {
          if (!active || (typeof document !== "undefined" && document.hidden)) return;
          if (!wraps.length) return;
          const vals = handlerFactory(e);
          if (vals) queue(vals);
        };
        global.addEventListener("deviceorientation", onOrient);
      },
      deactivate() {
        active = false;
        if (onOrient) global.removeEventListener("deviceorientation", onOrient);
        onOrient = null;
        wraps.forEach((w) => {
          w.classList.remove("tilting");
          w.style.setProperty("--rx", "0deg");
          w.style.setProperty("--ry", "0deg");
        });
        wraps = [];
        pending = null;
      },
      get active() { return active; },
    };
  }
  SeroMobile.makeHoloController = makeHoloController;
  SeroMobile.COL_CHUNK = 60;

  /* ── Android-/Browser-Zurück: reine Entscheidung (testbar) ── */
  function resolveBackAction(snap) {
    const s = snap || {};
    if (s.sheetOpen) return "closeSheet";
    if (s.partyOpen) return "closeParty";
    if ((s.settingsDepth || 0) > 1) return "settingsPop";
    if ((s.settingsDepth || 0) === 1) return "settingsClose";
    if (s.detailOpen) return "closeDetail";
    if (s.tab && s.homeTab && s.tab !== s.homeTab) return "goHome";
    return "confirmExit";
  }

  function installBackController(opts) {
    const o = opts || {};
    const historyObj = o.history || (typeof global.history !== "undefined" ? global.history : null);
    const win = o.window || global;
    if (!historyObj || !win || typeof win.addEventListener !== "function") {
      return { stop() {}, resolve: resolveBackAction };
    }
    let leaving = false;
    let exitPrompt = false;
    const pushTrap = () => {
      try { historyObj.pushState({ seroNav: 1 }, ""); } catch (_) { /* */ }
    };
    const onPop = () => {
      if (leaving) return;
      // Während Exit-Dialog: Zurück = Abbrechen (Sheet schließen)
      if (exitPrompt) {
        const snap = typeof o.snapshot === "function" ? o.snapshot() : {};
        if (snap.sheetOpen && typeof o.run === "function") o.run("closeSheet");
        pushTrap();
        return;
      }
      const snap = typeof o.snapshot === "function" ? o.snapshot() : {};
      const action = resolveBackAction(snap);
      if (action === "confirmExit") {
        exitPrompt = true;
        const ask = typeof o.confirmExit === "function" ? o.confirmExit() : Promise.resolve(false);
        Promise.resolve(ask).then((leave) => {
          exitPrompt = false;
          if (leave) {
            leaving = true;
            try { historyObj.back(); } catch (_) { /* */ }
          } else {
            pushTrap();
          }
        }).catch(() => {
          exitPrompt = false;
          pushTrap();
        });
        return;
      }
      if (typeof o.run === "function") o.run(action);
      pushTrap();
    };
    pushTrap();
    win.addEventListener("popstate", onPop);
    return {
      stop() { try { win.removeEventListener("popstate", onPop); } catch (_) { /* */ } },
      resolve: resolveBackAction,
      _pushTrap: pushTrap,
    };
  }

  SeroMobile.resolveBackAction = resolveBackAction;
  SeroMobile.installBackController = installBackController;

  global.SeroMobile = SeroMobile;
  if (typeof module !== "undefined" && module.exports) module.exports = SeroMobile;
})(typeof window !== "undefined" ? window : globalThis);
