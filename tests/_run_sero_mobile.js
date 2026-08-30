const fs = require("fs");
const vm = require("vm");
const path = require("path");
const code = fs.readFileSync(path.join(__dirname, "../frontend/sero-mobile.js"), "utf8");
const sandbox = {
  console,
  AbortController,
  requestAnimationFrame: (fn) => { sandbox.__rafs.push(fn); return sandbox.__rafs.length; },
  __rafs: [],
  matchMedia: () => ({ matches: false }),
  navigator: { onLine: true },
  document: { hidden: false, documentElement: { style: { setProperty() {} } }, addEventListener() {}, removeEventListener() {} },
  addEventListener() {},
  removeEventListener() {},
  window: {},
  module: { exports: {} },
  globalThis: {},
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.runInNewContext(code, sandbox);
const SM = sandbox.SeroMobile;

function assert(c, m) { if (!c) { console.error("FAIL", m); process.exit(1); } }

assert(!SM.gestures.shouldAllowTabSwipe({ dx: 80, dy: 10, sheetOpen: true }), "sheet blocks");
assert(!SM.gestures.shouldAllowTabSwipe({ dx: 80, dy: 10, detailOpen: true }), "detail blocks");
assert(!SM.gestures.shouldAllowTabSwipe({ dx: 40, dy: 5 }), "too short");
assert(!SM.gestures.shouldAllowTabSwipe({ dx: 80, dy: 60 }), "too vertical");
assert(SM.gestures.shouldAllowTabSwipe({ dx: 80, dy: 10 }), "free swipe ok");
const fakeChip = { closest: (sel) => (String(sel).includes(".chips") ? {} : null) };
assert(!SM.gestures.shouldAllowTabSwipe({ dx: 80, dy: 10, target: fakeChip }), "chips block");
assert(SM.gestures.axisLock(20, 2) === "x", "axis x");
assert(SM.gestures.axisLock(2, 20) === "y", "axis y");

const st = SM.store;
st.setString("k", "v");
assert(st.getString("k") === "v", "getString");
st.setJSON("j", { a: 1 });
assert(st.getJSON("j").a === 1, "json");
st._mem.bad = "{";
assert(st.getJSON("bad", { ok: 1 }).ok === 1, "bad json");

const w = SM.makeLatestWins();
const t1 = w.begin();
const t2 = w.begin();
assert(!t1.isCurrent() && t2.isCurrent(), "latest");

const h = SM.makeHoloController();
const el = { isConnected: true, classList: { add() {}, remove() {} }, style: { setProperty() {} } };
h.setWraps([el]);
h.activate(() => ({ rx: "1deg", ry: "2deg", gx: "50%", gy: "50%" }));
for (let i = 0; i < 100; i++) h.queue({ rx: i + "deg", ry: "0deg", gx: "50%", gy: "50%" });
assert(sandbox.__rafs.length === 1, "one raf");
sandbox.__rafs[0]();
assert(h.writeCount === 1, "one write");
h.deactivate();
assert(!h.active, "inactive");

assert(SM.resolveBackAction({ sheetOpen: true }) === "closeSheet", "back sheet");
assert(SM.resolveBackAction({ partyOpen: true }) === "closeParty", "back party");
assert(SM.resolveBackAction({ settingsDepth: 2 }) === "settingsPop", "back settings pop");
assert(SM.resolveBackAction({ settingsDepth: 1 }) === "settingsClose", "back settings close");
assert(SM.resolveBackAction({ detailOpen: true }) === "closeDetail", "back detail");
assert(SM.resolveBackAction({ tab: "tabSales", homeTab: "tabHome" }) === "goHome", "back home");
assert(SM.resolveBackAction({ tab: "tabHome", homeTab: "tabHome" }) === "confirmExit", "back exit");
assert(typeof SM.installBackController === "function", "install back");

const dedup = SM.makeInflightDedup();
let n = 0;
const p1 = dedup.run("k", () => { n += 1; return Promise.resolve("a"); });
const p2 = dedup.run("k", () => { n += 1; return Promise.resolve("b"); });
Promise.resolve(p1).then((a) => {
  assert(a === "a", "dedup first wins");
});
assert(n === 1, "dedup one runner");

console.log("SERO-MOBILE-OK");
