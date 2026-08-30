/* SERO-Maskottchen: gleitet hinter der Pill-Tabbar. Nur transform + opacity. */
(function () {
  "use strict";

  /* ── Tunables ── */
  const IDLE_MIN_MS = 3500;
  const IDLE_MAX_MS = 7000;
  const MOVE_MIN_MS = 700;
  const MOVE_MAX_MS = 1000;
  const START_DELAY_MS = 480;
  const BOB_PX = 2.5;
  const SIZE_MIN = 0.90;
  const SIZE_MAX = 1.10;
  const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
  const SLOTS = ["left", "mid", "right"];
  const SRC = "assets/sero-mascot.png";

  let cleanupFn = null;

  function rand(a, b) {
    return a + Math.random() * (b - a);
  }
  function reduced() {
    try {
      return matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (_) {
      return false;
    }
  }
  function appVisible() {
    const app = document.getElementById("viewApp");
    return !!(app && !app.hidden);
  }

  function ensureDock() {
    let dock = document.querySelector(".tabbar-dock");
    if (dock) return dock;
    const bar = document.querySelector("#viewApp > nav.tabbar") || document.querySelector("nav.tabbar");
    if (!bar || !bar.parentElement) return null;
    dock = document.createElement("div");
    dock.className = "tabbar-dock";
    bar.parentElement.insertBefore(dock, bar);
    dock.appendChild(bar);
    return dock;
  }

  function initFloatingSeroMascot() {
    if (cleanupFn) cleanupFn();

    const dock = ensureDock();
    if (!dock) return function () {};
    const bar = dock.querySelector(".tabbar");
    if (!bar) return function () {};

    const root = document.createElement("div");
    root.className = "sero-mascot";
    root.setAttribute("aria-hidden", "true");
    root.innerHTML =
      '<span class="sero-mascot-trail"><i></i><i></i></span>' +
      '<span class="sero-mascot-bob">' +
      '<img alt="" draggable="false">' +
      "</span>";
    const img = root.querySelector("img");
    img.src = SRC;
    img.width = 110;
    img.height = 90;
    dock.insertBefore(root, bar);

    let slot = "right";
    let slots = { left: 0, mid: 0, right: 0 };
    let idleTimer = 0;
    let startTimer = 0;
    let raf = 0;
    let moveAnim = null;
    let paused = false;
    let armed = false;
    const mq = matchMedia("(prefers-reduced-motion: reduce)");

    function setX(x, moving) {
      root.classList.toggle("is-moving", !!moving);
      root.style.transform = "translate3d(" + x + "px,-50%,0)";
    }

    function measure() {
      const dockR = dock.getBoundingClientRect();
      const barR = bar.getBoundingClientRect();
      const h = Math.max(32, bar.offsetHeight || barR.height || 44);
      const lo = Math.round(h * SIZE_MIN);
      const hi = Math.round(h * SIZE_MAX);
      const pref = Math.round(h);
      root.style.height = "clamp(" + lo + "px," + pref + "px," + hi + "px)";
      root.style.setProperty("--sero-bob", BOB_PX + "px");
      const w = root.offsetWidth || Math.round(size * 1.15);
      const rel = function (cx) { return cx - dockR.left - w / 2; };
      const vis = function (el) {
        if (!el) return false;
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden") return false;
        const r = el.getBoundingClientRect();
        return r.width > 4 && r.height > 4;
      };
      const col = bar.querySelector('[data-tab="tabCollection"]');
      const cam = bar.querySelector("#btnCamera");
      const left = vis(col)
        ? rel(col.getBoundingClientRect().left + col.getBoundingClientRect().width / 2)
        : rel(barR.left + barR.width / 6);
      const mid = vis(cam)
        ? rel(cam.getBoundingClientRect().left + cam.getBoundingClientRect().width / 2)
        : rel(barR.left + barR.width / 2);
      const right = rel(barR.left + (barR.width * 5) / 6);
      slots = { left: left, mid: mid, right: right };
      return slots;
    }

    function cancelMove() {
      if (moveAnim) {
        try { moveAnim.cancel(); } catch (_) {}
        moveAnim = null;
      }
      root.classList.remove("is-moving");
    }

    function goTo(next, duration, fromOff) {
      measure();
      const to = slots[next];
      const from = fromOff != null ? fromOff : slots[slot];
      slot = next;
      if (reduced() || duration <= 0) {
        cancelMove();
        setX(to, false);
        return;
      }
      cancelMove();
      setX(from, true);
      if (typeof root.animate !== "function") {
        setX(to, false);
        return;
      }
      moveAnim = root.animate(
        [
          { transform: "translate3d(" + from + "px,-50%,0)" },
          { transform: "translate3d(" + to + "px,-50%,0)" }
        ],
        { duration: duration, easing: EASE, fill: "forwards" }
      );
      const done = function () {
        moveAnim = null;
        setX(to, false);
      };
      moveAnim.onfinish = done;
      moveAnim.oncancel = function () { root.classList.remove("is-moving"); };
    }

    function clearIdle() {
      if (idleTimer) {
        clearTimeout(idleTimer);
        idleTimer = 0;
      }
    }

    function scheduleIdle() {
      clearIdle();
      if (reduced() || paused || document.hidden) return;
      idleTimer = setTimeout(function () {
        idleTimer = 0;
        if (paused || document.hidden || reduced() || !appVisible()) {
          scheduleIdle();
          return;
        }
        const others = SLOTS.filter(function (s) { return s !== slot; });
        const next = others[Math.floor(Math.random() * others.length)] || "left";
        goTo(next, rand(MOVE_MIN_MS, MOVE_MAX_MS));
        scheduleIdle();
      }, rand(IDLE_MIN_MS, IDLE_MAX_MS));
    }

    function snap() {
      measure();
      cancelMove();
      setX(slots[slot], false);
    }

    function onResize() {
      if (raf) return;
      raf = requestAnimationFrame(function () {
        raf = 0;
        snap();
      });
    }

    function onVis() {
      if (document.hidden) {
        paused = true;
        clearIdle();
        cancelMove();
        if (root.getAnimations) {
          root.getAnimations().forEach(function (a) {
            try { a.pause(); } catch (_) {}
          });
        }
        return;
      }
      paused = false;
      snap();
      if (root.getAnimations) {
        root.getAnimations().forEach(function (a) {
          try { a.play(); } catch (_) {}
        });
      }
      if (!reduced()) scheduleIdle();
    }

    function applyMotionPref() {
      root.classList.toggle("no-bob", reduced());
      if (!armed) return;
      snap();
      clearIdle();
      if (!reduced() && !document.hidden) scheduleIdle();
    }

    function startIntro() {
      measure();
      const rest = slots.right;
      const enter = rest + Math.max(36, root.offsetWidth * 0.45);
      if (reduced()) {
        setX(rest, false);
        return;
      }
      setX(enter, false);
      startTimer = setTimeout(function () {
        startTimer = 0;
        goTo("right", rand(MOVE_MIN_MS, MOVE_MAX_MS), enter);
        scheduleIdle();
      }, START_DELAY_MS);
    }

    function onReady() {
      root.classList.toggle("no-bob", reduced());
      startIntro();
      armed = true;
    }

    if (img.complete && img.naturalWidth) onReady();
    else img.addEventListener("load", onReady, { once: true });
    img.addEventListener("error", onReady, { once: true });

    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("orientationchange", onResize, { passive: true });
    document.addEventListener("visibilitychange", onVis);
    if (mq.addEventListener) mq.addEventListener("change", applyMotionPref);
    else if (mq.addListener) mq.addListener(applyMotionPref);

    function cleanup() {
      clearIdle();
      if (startTimer) clearTimeout(startTimer);
      if (raf) cancelAnimationFrame(raf);
      cancelMove();
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
      document.removeEventListener("visibilitychange", onVis);
      if (mq.removeEventListener) mq.removeEventListener("change", applyMotionPref);
      else if (mq.removeListener) mq.removeListener(applyMotionPref);
      if (root.parentNode) root.parentNode.removeChild(root);
      cleanupFn = null;
    }

    window.addEventListener("pagehide", cleanup, { once: true });
    cleanupFn = cleanup;
    return cleanup;
  }

  window.initFloatingSeroMascot = initFloatingSeroMascot;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFloatingSeroMascot);
  } else {
    initFloatingSeroMascot();
  }
})();
