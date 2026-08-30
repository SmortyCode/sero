const fs = require("fs");
const path = require("path");
const vm = require("vm");

const js = fs.readFileSync(path.join(__dirname, "../frontend/sero.js"), "utf8");
const start = js.indexOf("function colHubDeltaFromPoints");
const end = js.indexOf("\nfunction colHubHistoryPoints");
if (start < 0 || end < 0 || end <= start) {
  console.error("FAIL extract colHubDeltaFromPoints");
  process.exit(1);
}
const sandbox = {};
vm.runInNewContext(js.slice(start, end) + "\nthis.colHubDeltaFromPoints = colHubDeltaFromPoints;", sandbox);
const delta = sandbox.colHubDeltaFromPoints;

function assert(c, m) {
  if (!c) { console.error("FAIL", m); process.exit(1); }
}

const DAY = 86400000;
const now = Date.parse("2026-08-18T12:00:00");

assert(delta([]).kind === "none", "empty is none");
assert(delta(null).kind === "none", "null is none");
assert(delta([{ t: now, v: 749.88 }]).kind === "none", "single point is none, no fake pct");
assert(delta([{ v: 100 }, { v: 200 }]).kind === "none", "undated points are none");

const young = delta([
  { t: now - 10 * DAY, v: 667.78 },
  { t: now, v: 749.88 },
], now);
assert(young.kind === "since_start", "under 30 days is since_start, not d30");
assert(Math.abs(young.euro - 82.10) < 0.001, "since_start euro from first point");
assert(young.kind !== "d30", "must not invent a 30-day window");

const d30 = delta([
  { t: now - 40 * DAY, v: 667.78 },
  { t: now - 10 * DAY, v: 700 },
  { t: now, v: 749.88 },
], now);
assert(d30.kind === "d30", "point older than 30 days is d30");
assert(Math.abs(d30.then - 667.78) < 0.001, "uses last point at or before cutoff");
assert(Math.abs(d30.euro - 82.10) < 0.001, "euro = now - then");
assert(Math.abs(d30.pct - (82.10 / 667.78)) < 1e-9, "pct = (now-then)/then");

const older = delta([
  { t: now - 80 * DAY, v: 500 },
  { t: now - 35 * DAY, v: 667.78 },
  { t: now, v: 749.88 },
], now);
assert(older.kind === "d30", "several old points still d30");
assert(Math.abs(older.then - 667.78) < 0.001, "next older than 30 days, not the oldest");

const zeroThen = delta([
  { t: now - 40 * DAY, v: 0 },
  { t: now, v: 50 },
], now);
assert(zeroThen.kind === "d30", "then=0 still d30");
assert(zeroThen.pct === null, "then=0 omits percent");
assert(zeroThen.euro === 50, "then=0 still has euro");

const down = delta([
  { t: now - 40 * DAY, v: 100 },
  { t: now, v: 90 },
], now);
assert(down.kind === "d30" && down.euro === -10, "negative euro is honest minus");
assert(Math.abs(down.pct + 0.1) < 1e-9, "negative percent");

console.log("SERO-COL-HUB-DELTA-OK");
