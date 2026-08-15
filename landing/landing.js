/* SERO Landing — Motion. Wenig, bewusst, 60fps.
   1) Reveal-on-scroll mit Stagger (IntersectionObserver)
   2) Hero-Parallax (zwei Ebenen, rAF, transform-only)
   Beides aus bei prefers-reduced-motion. */

(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── 1 · Reveals ─────────────────────────────────────────────── */
  var reveals = Array.prototype.slice.call(document.querySelectorAll(".reveal"));

  if (reduced || !("IntersectionObserver" in window)) {
    reveals.forEach(function (el) { el.classList.add("in"); });
  } else {
    // Stagger: Geschwister-Reveals innerhalb einer Section leicht versetzt
    var bySection = new Map();
    reveals.forEach(function (el) {
      var key = el.closest("section") || document.body;
      var n = bySection.get(key) || 0;
      el.style.setProperty("--d", Math.min(n * 0.09, 0.45) + "s");
      bySection.set(key, n + 1);
    });

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.15 });

    reveals.forEach(function (el) { io.observe(el); });
  }

  /* ── 2 · Hero-Parallax ───────────────────────────────────────── */
  if (!reduced) {
    var layers = Array.prototype.slice.call(document.querySelectorAll("[data-parallax]"));
    if (layers.length) {
      var ticking = false;
      var update = function () {
        ticking = false;
        var y = window.scrollY || 0;
        if (y > window.innerHeight * 1.2) return;   // Hero längst vorbei
        layers.forEach(function (el) {
          var f = parseFloat(el.getAttribute("data-parallax")) || 0;
          el.style.transform = "translate3d(0," + (y * f).toFixed(1) + "px,0)";
        });
      };
      window.addEventListener("scroll", function () {
        if (!ticking) { ticking = true; requestAnimationFrame(update); }
      }, { passive: true });
    }
  }

  /* ── 3 · FAQ: nur ein offenes Element (Fallback ohne name=) ──── */
  var faqs = Array.prototype.slice.call(document.querySelectorAll(".faq details"));
  faqs.forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) {
        faqs.forEach(function (other) {
          if (other !== d && other.open) other.open = false;
        });
      }
    });
  });
})();
