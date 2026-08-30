/* SERO detail — local view-model, notes, confidence. No network. */
"use strict";

(function (root) {
  const MIN_COMPS_FOR_PRICE = 3;

  function nz(v) {
    if (v == null) return null;
    const s = String(v).trim();
    return s === "" ? null : s;
  }

  function identField(item, key) {
    const ident = item && item.canonical_identity;
    if (!ident) return null;
    const fields = ident.fields || {};
    if (fields[key] && fields[key].value != null) return nz(fields[key].value);
    return nz(ident[key]);
  }

  function pick() {
    for (let i = 0; i < arguments.length; i++) {
      const v = nz(arguments[i]);
      if (v != null) return v;
    }
    return null;
  }

  function yearFromText(text) {
    const m = String(text || "").match(/\b((?:19|20)\d{2})\b/);
    return m ? m[1] : null;
  }

  function productKind(item, view) {
    const identKind = identField(item, "kind") || (item && item.canonical_identity && item.canonical_identity.kind);
    const cat = String((view && view.category) || (item && item.category) || "").toLowerCase();
    const blob = `${cat} ${view && view.title || ""} ${(item && item.name) || ""}`.toLowerCase();
    if (identKind === "graded_slab" || (item && item.graded && (item.graded.grade || item.graded.grader)))
      return "graded";
    if (identKind === "video_game" || cat === "games" || /\b(ps1|ps2|ps3|ps4|ps5|switch|xbox|n64|wii)\b/.test(blob))
      return "game";
    if (identKind === "manga_comic" || cat === "manga" || cat === "comics")
      return "collectible";
    if (identKind === "raw_card" || /pokémon|pokemon|one piece|magic|yu-?gi|lorcana|dragon ball|tcg|karte/.test(blob))
      return "tcg";
    if (/kleidung|clothing|apparel|shirt|hoodie/.test(blob)) return "clothing";
    if (/elektronik|electronics|console|handy|iphone/.test(blob)) return "electronics";
    return "general";
  }

  function detailImages(item, opts) {
    opts = opts || {};
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
    /* eBay-Pane: Listing-Foto (Studio) zuerst; ohne Design bleibt das Scan-Foto. */
    if (opts.preferDesign && designUrl) add(designUrl, "design");
    photos.forEach((u, i) => add(u, i === 0 ? "front" : (i === 1 ? "back" : "extra")));
    if (designUrl) add(designUrl, "design");
    return out;
  }

  function compsInfo(item) {
    const sold = (item && item.sold_comps) || {};
    const sales = Array.isArray(sold.sales) ? sold.sales : [];
    let n = Number(sold.n_avg) || 0;
    if (!n) n = sales.length;
    if (!n && item && Array.isArray(item.comps)) n = item.comps.length;
    let stale = !!(sold.stale) || (item && item.price_reason === "BELEGE_ALT");
    let ageDays = null;
    if (item && item.price_updated) {
      const ts = Number(item.price_updated);
      if (ts > 0) {
        const now = (item._now != null) ? Number(item._now) : Date.now() / 1000;
        ageDays = Math.floor((now - ts) / 86400);
        if (ageDays > 90) stale = true;
      }
    }
    const market = (item && item.market) || {};
    const nAsk = Number(market.count) || (Array.isArray(market.samples) ? market.samples.length : 0);
    return { n: n, nAsk: nAsk, stale: stale, ageDays: ageDays, sales: sales };
  }

  function priceRange(item) {
    const market = (item && item.market) || {};
    const lo = item && (item.price_low != null ? item.price_low : market.min);
    const hi = item && (item.price_high != null ? item.price_high : market.max);
    if (lo != null && hi != null && Number(lo) !== Number(hi)) {
      return { low: Number(lo), high: Number(hi) };
    }
    const sales = compsInfo(item).sales;
    const prices = sales.map((s) => s && s.price_eur).filter((v) => v != null && v !== "");
    if (prices.length >= 2) {
      return { low: Math.min.apply(null, prices.map(Number)), high: Math.max.apply(null, prices.map(Number)) };
    }
    return null;
  }

  function priceConfidence(item) {
    const info = compsInfo(item);
    const state = (item && item.price_state) || "unbekannt";
    let level = null;
    if (info.n <= 0) level = null;
    else if (info.n === 1 || info.stale) level = "low";
    else if (info.n >= 2 && info.n <= 4) level = "mid";
    else if (info.n >= 5) level = "high";
    if (state === "unbekannt" && level === "high") level = "mid";
    const dots = level === "high" ? 3 : level === "mid" ? 2 : level === "low" ? 1 : 0;
    return {
      level: level,
      dots: dots,
      n: info.n,
      stale: info.stale,
      ageDays: info.ageDays,
    };
  }

  function priceCardModel(item) {
    const conf = priceConfidence(item);
    const state = (item && item.price_state) || "unbekannt";
    const reason = (item && item.price_reason) || null;
    const source = (item && item.price_source) || null;
    const raw = item && item.est_value;
    const hasNum = raw != null && raw !== "" && isFinite(Number(raw));
    const isEstimate = source === "estimate" || reason === "KI_RICHTWERT";
    const isManual = state === "eigener_wert" || source === "manual";
    const unknown = state === "unbekannt" || !hasNum;

    let showValue = false;
    if (isManual && hasNum) showValue = true;
    else if (isEstimate && hasNum) showValue = true;
    else if (!unknown && conf.n >= MIN_COMPS_FOR_PRICE && hasNum) showValue = true;

    if (isEstimate && conf.level === "high") conf.level = "low";

    let label = "Wert unbekannt";
    if (showValue) {
      if (isManual) label = "Eigener Wert";
      else if (isEstimate) label = "Richtwert";
      else if (state === "spanne") label = "Marktwert (Richtwert)";
      else label = "Marktwert";
    }

    const confLabel = conf.level === "high" ? "Hoch"
      : conf.level === "mid" ? "Mittel"
        : conf.level === "low" ? "Niedrig" : null;

    return {
      heading: "Marktwert",
      label: label,
      showValue: showValue,
      value: showValue ? Number(raw) : null,
      range: showValue ? priceRange(item) : null,
      confidence: conf.level,
      confidenceLabel: confLabel,
      dots: conf.dots,
      compsCount: conf.n > 0 ? conf.n : null,
      updated: (item && item.price_updated) || null,
      reason: reason,
      unknown: !showValue,
      hint: !showValue ? "Noch keine verlässliche Preisschätzung" : null,
    };
  }

  function detailView(item) {
    item = item || {};
    const c = item.card || {};
    const ci = item.card_info || {};
    const g = item.graded || {};
    const title = pick(item.name, identField(item, "name"), c.name, ci.name, item.analysis_title) || "";
    const setName = pick(identField(item, "set_name"), c.set_name, ci.set_name, ci.set_hint, ci.set);
    const number = pick(identField(item, "number"), c.number, ci.number, ci.local_id);
    const language = pick(identField(item, "language"), c.language, ci.language);
    const variant = pick(identField(item, "variant"), identField(item, "edition"), c.rarity, ci.rarity, ci.edition, ci.variant);
    const rarity = pick(identField(item, "rarity"), c.rarity, ci.rarity);
    const character = pick(identField(item, "character"), ci.character, c.character);
    const year = pick(identField(item, "year"), ci.year, c.year, yearFromText(title), yearFromText(item.analysis_title));
    const grader = pick(g.grader, identField(item, "grader"));
    const grade = pick(g.grade, identField(item, "grade"));
    const cert = pick(g.cert_number, identField(item, "cert_number"), item.cert_number, item.psa_cert);
    const brand = pick(identField(item, "brand"), ci.brand, item.brand);
    const platform = pick(identField(item, "platform"), ci.platform);
    const model = pick(identField(item, "model"), ci.model);
    const series = pick(identField(item, "series"), ci.series);
    const volume = pick(identField(item, "volume"), ci.volume);
    const description = pick(
      item.scan_description,
      item.analysis && item.analysis.description_plain,
      ci.description,
    );
    const view = {
      id: item.id || null,
      title: title,
      category: item.category || null,
      brand: brand,
      images: detailImages(item),
      year: year,
      set: setName,
      number: number,
      character: character,
      variant: variant,
      rarity: rarity,
      language: language,
      quantity: item.quantity != null ? item.quantity : null,
      condition: item.condition || null,
      grader: grader,
      grade: grade,
      cert: cert,
      platform: platform,
      model: model,
      series: series,
      volume: volume,
      prices: {
        est: item.est_value,
        state: item.price_state || null,
        reason: item.price_reason || null,
        source: item.price_source || null,
        updated: item.price_updated || null,
      },
      compsCount: compsInfo(item).n,
      description: description,
      notes: nz(item.notes),
      favorite: !!item.favorite,
      ebayStatus: item.draft_status || null,
      owner: pick(item.owner, item.owner_name) || "Du",
    };
    view.kind = productKind(item, view);
    view.sources = collectSources(item);
    return view;
  }

  function collectSources(item) {
    const out = [];
    const seen = {};
    const add = (label, url) => {
      const u = nz(url);
      if (!u || !/^https?:\/\//i.test(u)) return;
      const key = u.split("#")[0];
      if (seen[key]) return;
      seen[key] = true;
      out.push({ label: nz(label) || "Quelle", url: u });
    };
    const src = item && item.sources;
    if (Array.isArray(src)) {
      src.forEach((s) => {
        if (!s) return;
        if (typeof s === "string") add("Quelle", s);
        else add(s.label || s.name || s.source, s.url || s.href);
      });
    }
    if (item && item.item_url) add("eBay", item.item_url);
    const pd = (item && item.price_detail) || {};
    add("TCGplayer", pd.tcgplayer_url || pd.tcgplayer);
    add("PriceCharting", pd.pricecharting_url || pd.pricecharting);
    add("Cardmarket", pd.cardmarket_url || pd.cardmarket);
    if (item && item.card_info) {
      add("TCGplayer", item.card_info.tcgplayer_url);
      add("Quelle", item.card_info.url);
    }
    return out;
  }

  function fact(label, value) {
    const v = nz(value);
    if (!v) return null;
    return { label: label, value: v };
  }

  function notesModel(item) {
    const view = (item && item.title !== undefined && item.kind) ? item : detailView(item);
    const collector = view.kind === "tcg" || view.kind === "graded" || view.kind === "collectible";
    const heading = collector ? "Sammlerhinweise" : "Produktinformationen";
    const why = (view.set && view.year && view.variant)
      ? `${view.set} (${view.year}), ${view.variant}.`
      : null;
    const bits = [];
    if (view.set) bits.push(view.set);
    if (view.number) bits.push("#" + view.number);
    if (view.variant) bits.push(view.variant);
    if (view.language) bits.push(view.language);
    if (view.grader && view.grade) bits.push(view.grader + " " + view.grade);
    else if (view.grade) bits.push(String(view.grade));
    if (view.platform) bits.push(view.platform);
    if (view.brand) bits.push(view.brand);
    if (view.model) bits.push(view.model);
    if (view.series) bits.push(view.series);
    if (view.volume) bits.push("Bd. " + view.volume);
    const collectorLine = bits.length ? bits.join(" \u00b7 ") : null;
    const body = view.description || null;

    const kindLine = (
      view.kind === "tcg" ? "Das ist eine Sammelkarte."
      : view.kind === "graded" ? "Das ist eine bewertete Karte im Slab."
      : view.kind === "game" ? "Das ist ein Videospiel."
      : view.kind === "collectible" ? "Das ist ein Sammlerstück."
      : view.kind === "clothing" ? "Das ist Kleidung."
      : view.kind === "electronics" ? "Das ist ein elektronisches Gerät."
      : null
    );
    const whatParts = [];
    if (kindLine) whatParts.push(kindLine);
    if (view.character) whatParts.push("Abgebildet: " + view.character + ".");
    const setBits = [];
    if (view.set) setBits.push("Set " + view.set);
    if (view.number) setBits.push("Nummer " + view.number);
    if (view.year) setBits.push("Jahr " + view.year);
    if (setBits.length) whatParts.push(setBits.join(", ") + ".");
    if (view.variant) whatParts.push("Variante: " + view.variant + ".");
    if (view.rarity && view.rarity !== view.variant) {
      whatParts.push("Seltenheit: " + view.rarity + ".");
    }
    if (view.language) whatParts.push("Sprache: " + view.language + ".");
    if (view.grader && view.grade) {
      let g = "Bewertet von " + view.grader + " mit Note " + view.grade;
      if (view.cert) g += ", Zertifikat " + view.cert;
      whatParts.push(g + ".");
    } else if (view.grade) {
      whatParts.push("Note: " + view.grade + ".");
    }
    if (view.platform) whatParts.push("Plattform: " + view.platform + ".");
    if (view.brand) whatParts.push("Marke: " + view.brand + ".");
    if (view.model) whatParts.push("Modell: " + view.model + ".");
    if (view.series) whatParts.push("Serie: " + view.series + ".");
    if (view.volume) whatParts.push("Band " + view.volume + ".");
    const what = whatParts.length ? whatParts.join(" ") : null;

    const facts = [
      fact("Variante", view.variant),
      fact("Nummer", view.number ? "#" + view.number : null),
      fact("Set", view.set),
      fact("Jahr", view.year),
      fact("Sprache", view.language),
      fact("Grade", view.grader && view.grade ? `${view.grader} ${view.grade}` : view.grade),
      fact("Zertifikat", view.cert),
      fact("Figur", view.character),
      fact("Seltenheit", view.rarity && view.rarity !== view.variant ? view.rarity : null),
      fact("Plattform", view.platform),
      fact("Marke", view.brand),
      fact("Modell", view.model),
      fact("Serie", view.series),
      fact("Band", view.volume),
    ].filter(Boolean);

    const sections = [];
    if (view.title) sections.push({ id: "title", heading: null, body: view.title });
    if (what) sections.push({ id: "what", heading: null, body: what });
    if (why) sections.push({ id: "why", heading: "Warum es interessant ist", body: why });
    if (collectorLine) sections.push({ id: "notes", heading: heading, body: collectorLine });
    if (body) sections.push({ id: "scan", heading: null, body: body });

    return {
      heading: "Notizen",
      kind: view.kind,
      collector: collector,
      sections: sections,
      facts: facts,
      sources: view.sources || [],
      disclaimer: sections.length || facts.length
        ? "Automatisch erzeugte Angaben — bitte prüfen."
        : null,
    };
  }

  function detailChips(item) {
    const view = (item && item.title !== undefined && item.kind) ? item : detailView(item);
    const chips = [];
    const add = (label, value) => {
      const v = nz(value);
      if (!v) return;
      chips.push({ label: label, value: v });
    };
    add("Set", view.set);
    add("Figur", view.character);
    add("Variante", view.variant);
    add("Seltenheit", view.rarity && view.rarity !== view.variant ? view.rarity : null);
    add("Nummer", view.number);
    add("Sprache", view.language);
    add("Jahr", view.year);
    add("Grade", view.grade);
    add("Grader", view.grader);
    add("Zertifikat", view.cert);
    add("Kategorie", view.category);
    add("Marke", view.brand);
    add("Plattform", view.platform);
    add("Modell", view.model);
    add("Serie", view.series);
    add("Band", view.volume);
    return chips;
  }

  function escHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function ebayDescPlain(raw, item) {
    let t = String(raw || "").replace(/\r\n/g, "\n").replace(/\u00a0/g, " ").trim();
    if (!t) {
      if (!item) return "";
      const notes = notesModel(item);
      return ebayDescFromNotes(notes);
    }
    t = t.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n");
    if (/\n/.test(t)) return t;
    if ((t.match(/(?:^|\s)\d+[.)]\s+\S/g) || []).length >= 2) {
      return t.replace(/\s+(?=\d+[.)]\s+\S)/g, "\n\n").trim();
    }
    if (t.indexOf(" \u00b7 ") >= 0) {
      return t.split(" \u00b7 ").map(function (p) { return p.trim(); }).filter(Boolean).join("\n");
    }
    const parts = t.split(/(?<=[.!?])\s+(?=[A-ZÄÖÜ][a-zäöüß]{2,})/);
    if (parts.length >= 2) {
      const paras = [];
      for (let i = 0; i < parts.length; i += 2) paras.push(parts.slice(i, i + 2).join(" "));
      return paras.join("\n\n");
    }
    return t;
  }

  function ebayDescFromNotes(notes) {
    if (!notes) return "";
    const byId = {};
    (notes.sections || []).forEach(function (s) { byId[s.id] = s; });
    const out = [];
    if (byId.title && byId.title.body) out.push(byId.title.body);
    const numbered = [];
    if (byId.why && byId.why.body) {
      numbered.push("1) " + (byId.why.heading || "Warum es interessant ist") + "\n" + byId.why.body);
    }
    const hint = byId.notes || byId.what;
    if (hint && hint.body) {
      numbered.push((numbered.length + 1) + ") " + (hint.heading || "Hinweise") + "\n" + hint.body);
    }
    if (notes.facts && notes.facts.length) {
      const fl = notes.facts.map(function (f) { return f.label + ": " + f.value; }).join("\n");
      numbered.push((numbered.length + 1) + ") Fakten\n" + fl);
    }
    if (byId.scan && byId.scan.body) out.push(byId.scan.body);
    if (numbered.length) out.push(numbered.join("\n\n"));
    return out.filter(Boolean).join("\n\n");
  }

  function ebayDescHtml(plain) {
    const t = String(plain || "").replace(/\r\n/g, "\n").trim();
    if (!t) return "";
    const blocks = t.split(/\n{2,}/).map(function (b) { return b.trim(); }).filter(Boolean);
    let html = "";
    let listItems = [];
    const inline = function (s) { return escHtml(s).replace(/\n/g, "<br>"); };
    const flushList = function () {
      if (!listItems.length) return;
      html += "<ol>" + listItems.map(function (li) { return "<li>" + li + "</li>"; }).join("") + "</ol>";
      listItems = [];
    };
    for (let i = 0; i < blocks.length; i++) {
      const b = blocks[i];
      const m = b.match(/^(\d+)[.)]\s+([\s\S]+)$/);
      if (m) {
        const rest = m[2];
        const nl = rest.indexOf("\n");
        if (nl > 0) {
          const head = rest.slice(0, nl).trim();
          const body = rest.slice(nl + 1).trim();
          listItems.push("<strong>" + inline(head) + "</strong>" + (body ? "<br>" + inline(body) : ""));
        } else {
          listItems.push(inline(rest));
        }
        continue;
      }
      flushList();
      html += "<p>" + inline(b) + "</p>";
    }
    flushList();
    return html;
  }

  function parseEuro(raw) {
    if (raw == null || raw === "") return NaN;
    let t = String(raw).replace(/€/gi, "").replace(/EUR/gi, "").replace(/\u00a0/g, "");
    t = t.replace(/\s+/g, "").trim();
    if (!t) return NaN;
    const neg = t.charAt(0) === "-";
    t = t.replace(/^[+-]/, "");
    if (!/^[0-9.,]+$/.test(t)) return NaN;
    const c = t.lastIndexOf(",");
    const p = t.lastIndexOf(".");
    if (c >= 0 && p >= 0) {
      const dez = Math.max(c, p);
      t = t.slice(0, dez).replace(/[.,]/g, "") + "." + t.slice(dez + 1);
    } else if (c >= 0) {
      t = t.replace(/\./g, "").replace(",", ".");
    } else if (p >= 0) {
      const idx = t.lastIndexOf(".");
      const rest = t.slice(idx + 1);
      const ganz = t.slice(0, idx).replace(/\./g, "");
      t = rest.length === 3 ? ganz + rest : ganz + "." + rest;
    }
    const n = parseFloat(t);
    if (!isFinite(n)) return NaN;
    return neg ? -n : n;
  }

  function listingIssue(o) {
    o = o || {};
    const field = String(o.field || o.fieldId || "");
    const severity = o.severity || (o.blocking === false ? "warn" : "error");
    const type = o.type || (severity === "warn" ? "review" : "missing");
    const blocking = o.blocking != null ? !!o.blocking : (severity === "error" && type !== "loading");
    return {
      fieldId: String(o.fieldId || field),
      field: field,
      type: type,
      severity: severity,
      blocking: blocking,
      source: o.source || "preflight",
      message: o.message || "",
      section: o.section || "product",
    };
  }

  function isCardLike(item, draft) {
    const cat = (item && item.category) || (draft && draft.category_name) || "";
    const kind = productKind(item || {}, { category: cat, title: (draft && draft.title) || "" });
    return kind === "tcg" || kind === "graded";
  }

  function identityUncertain(item, draft) {
    if (!item && !draft) return false;
    if ((item && item.identity_user_confirmed) || (draft && draft.identity_user_confirmed)) return false;
    if ((draft && draft.item_listing_ready) || (item && item.identity_eval && item.identity_eval.listing_ready))
      return false;
    const ev = (item && item.identity_eval) || {};
    const rec = String(ev.recognition_state || draft && draft.item_recognition || "").trim();
    const ist = String((item && item.status) || (draft && draft.item_status) || "").trim();
    if (rec === "needs_review" || rec === "uncertain" || rec === "error") return true;
    if (ist === "needs_review" || ist === "uncertain") return true;
    return false;
  }

  function listingValidation(draft, item, preflight) {
    const issues = [];
    const seen = {};
    const add = (raw) => {
      const iss = listingIssue(raw);
      if (!iss.fieldId && !iss.message) return;
      const key = iss.fieldId + "\t" + iss.message + "\t" + iss.severity;
      if (seen[key]) return;
      seen[key] = true;
      issues.push(iss);
    };

    const st = String((draft && draft.status) || "").trim();
    const ist = String((item && item.status) || (draft && draft.item_status) || "").trim();
    if (["analyzing", "downloading", "waiting"].includes(st)
        || ["analyzing", "downloading", "waiting"].includes(ist)) {
      add({
        fieldId: "status", field: "status", type: "loading", severity: "info",
        blocking: true, source: "form", message: "Analyse läuft noch", section: "product",
      });
    }
    if (st === "publishing" || (draft && draft.stage && !draft.stage.done)) {
      add({
        fieldId: "status", field: "status", type: "loading", severity: "info",
        blocking: true, source: "form", message: "Upload läuft gerade", section: "product",
      });
    }
    if (draft && (draft.question || draft.pending_frage || draft.pending === "graded"
        || draft.pending === "graded_update")) {
      add({
        fieldId: "question", field: "question", type: "invalid", severity: "error",
        blocking: true, source: "form", message: "Offene Rückfrage zuerst beantworten",
        section: "product",
      });
    }

    const pfIssues = (preflight && preflight.issues) || [];
    pfIssues.forEach((iss) => {
      const field = String(iss.field || iss.field_id || iss.fieldId || "");
      const msg = String(iss.message || "");
      if (field === "identity" || field === "item_status" && iss.severity === "warn") return;
      if (/Identität unsicher|Stück zuerst prüfen|Identität bestätigen/.test(msg)) return;
      if (field === "price") {
        const saved = parseEuro(draft && draft.price);
        if (saved > 0 && (iss.code === "MISSING" || /Preis festlegen/.test(msg))) return;
      }
      add({
        fieldId: field,
        field: field,
        type: iss.type || (iss.code === "MISSING" ? "missing" : iss.code === "ANALYZING" ? "loading" : "invalid"),
        severity: iss.severity || (iss.blocking === false ? "warn" : "error"),
        blocking: iss.blocking != null ? !!iss.blocking : iss.severity !== "warn",
        source: iss.source || "preflight",
        message: msg,
        section: iss.section || "product",
      });
    });

    if (!preflight && draft) {
      const title = (draft.title || (draft.listing && draft.listing.title) || "").trim();
      if (!title) add({ fieldId: "title", field: "title", type: "missing", severity: "error",
        blocking: true, source: "form", message: "Titel fehlt", section: "product" });
      const priceN = parseEuro(draft.price);
      if (!(priceN > 0)) add({ fieldId: "price", field: "price", type: "missing", severity: "error",
        blocking: true, source: "form", message: "Preis festlegen", section: "offer" });
      const photos = draft.photos || [];
      const urls = draft.image_urls || [];
      if (!photos.length && !urls.length) add({
        fieldId: "photos", field: "photos", type: "missing", severity: "error",
        blocking: true, source: "form", message: "Mindestens ein Bild nötig", section: "photos",
      });
    }

    /* Gespeicherter Listing-Preis ist die Quelle, nicht der alte KI-Flag.
       Fehlt der Preis, ist nur das Preisfeld rot (oben). Gelb „Bitte prüfen"
       am Preis entfällt, sobald draft.price gültig ist. */

    const loading = issues.some((i) => i.type === "loading");
    const blocking = issues.filter((i) => i.blocking && i.severity === "error");
    return {
      issues: issues,
      blockingCount: blocking.length,
      ready: !loading && blocking.length === 0,
      loading: loading,
    };
  }

  root.SeroDetail = {
    MIN_COMPS_FOR_PRICE: MIN_COMPS_FOR_PRICE,
    detailView: detailView,
    detailImages: detailImages,
    compsInfo: compsInfo,
    priceConfidence: priceConfidence,
    priceCardModel: priceCardModel,
    notesModel: notesModel,
    detailChips: detailChips,
    productKind: productKind,
    ebayDescPlain: ebayDescPlain,
    ebayDescHtml: ebayDescHtml,
    listingIssue: listingIssue,
    listingValidation: listingValidation,
    isCardLike: isCardLike,
    identityUncertain: identityUncertain,
    parseEuro: parseEuro,
  };
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this));
