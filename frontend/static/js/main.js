// Router, app chrome and shared state. Hash routes only, so the backend only ever serves "/".
// The one exception is shared cards at /c/{token}; the token never goes into a hash, query or log.

import { focusScreen, getPrefs, onPrefsChange, setPrefs } from "./a11y.js";
import { api, isMock, onMockChange } from "./api.js";
import { nextBreak } from "./slots.js";
import { subscribe } from "./stream.js";

// Each route lazily imports a screen module: `export default { title, chrome, render(main, ctx) }`.
// render may return a cleanup function, called when the person leaves the screen.
const ROUTES = {
  "/": () => import("./screens/welcome.js"),
  "/home": () => import("./screens/now.js"),
  "/now": () => import("./screens/now.js"), // old links still work
  "/talks": () => import("./screens/talks.js"),
  "/card": () => import("./screens/card.js"),
  "/card/show": () => import("./screens/show.js"),
  "/group": () => import("./screens/group.js"),
  "/report": () => import("./screens/report.js"),
  "/met": () => import("./screens/met.js"),
  "/grow": () => import("./screens/grow-screen.js"),
  "/settings": () => import("./screens/settings.js"),
  "/board": () => import("./board/board.js"),
  "/staff": () => import("./screens/staff.js"),
  "/insights": () => import("./screens/insights.js"),
};

const TAB_FOR = { "/home": "home", "/now": "home", "/talks": "home", "/card": "card", "/card/show": "card", "/group": "group", "/report": "report", "/met": "met", "/grow": "met" };

const main = document.getElementById("main");
const tabbar = document.getElementById("tabbar");
const demoBadge = document.getElementById("demo-badge");

let cleanup = null;
let firstRender = true;
let renderSeq = 0;

export function parseHash(hash = location.hash) {
  const raw = hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  return { path: path.replace(/\/+$/, "") || "/", query: new URLSearchParams(query) };
}

export function navigate(path) {
  location.hash = `#${path}`;
}

function setChrome(route, screen) {
  const chrome = screen.chrome !== false;
  document.body.classList.toggle("no-chrome", !chrome);
  document.body.classList.toggle("on-sky", !!screen.sky);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", screen.sky ? "#0E1430" : "#070818");
  const tab = TAB_FOR[route];
  for (const link of tabbar.querySelectorAll("a[data-tab]")) {
    if (link.dataset.tab === tab) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

async function render() {
  const seq = ++renderSeq;
  const isShared = location.pathname.startsWith("/c/");
  const { path, query } = parseHash();
  const loader = isShared ? () => import("./screens/shared-card.js") : ROUTES[path] || (() => import("./screens/not-found.js"));

  let screen;
  try {
    screen = (await loader()).default;
  } catch {
    screen = (await import("./screens/not-found.js")).default;
  }
  if (seq !== renderSeq) return; // a newer navigation won

  if (typeof cleanup === "function") {
    try { cleanup(); } catch { /* a screen's cleanup must not break navigation */ }
  }
  cleanup = null;

  setChrome(isShared ? null : path, screen);
  document.title = screen.title ? `${screen.title} · Affinity` : "Affinity";
  main.replaceChildren();
  const nextCleanup = await screen.render(main, { path, query, navigate });
  if (seq !== renderSeq) {
    // A newer navigation replaced this screen while it was loading: stop it right away.
    if (typeof nextCleanup === "function") { try { nextCleanup(); } catch { /* ignore */ } }
    return;
  }
  cleanup = nextCleanup;

  if (!firstRender) focusScreen(main);
  firstRender = false;
}

function showDemoBadge() {
  demoBadge.hidden = !isMock();
}

window.addEventListener("hashchange", render);

// ---- Ambient aura: follows your day ----
// Calm (or low-sensory) → emerald; from 15 minutes before a break until it ends → amber/rose;
// otherwise indigo/cyan for talk discovery.
function updateAura() {
  const root = document.documentElement;
  const brk = nextBreak();
  const start = Date.parse(brk.startsAt);
  const now = Date.now();
  const nearBreak = now >= start - 15 * 60000 && now <= start + 30 * 60000;
  const aura = getPrefs().calm ? "calm" : nearBreak ? "break" : "discover";
  for (const a of ["calm", "break", "discover"]) root.classList.toggle(`aura-${a}`, a === aura);
}
updateAura();
setInterval(updateAura, 30000);
onPrefsChange(updateAura);

// ---- Header: the live "N alone" pill and the Human / kubectl toggle ----
const alonePill = document.getElementById("alone-pill");
const aloneText = document.getElementById("alone-text");
function showAlone(board) {
  const n = (board?.board ?? board)?.alone;
  if (n == null) return;
  alonePill.hidden = false;
  alonePill.classList.toggle("zero", n === 0);
  aloneText.textContent = `${n} alone`;
  alonePill.setAttribute("aria-label", `${n} ${n === 1 ? "person" : "people"} alone at this break. Open the big screen.`);
}
async function refreshAlone() {
  try { showAlone(await api.board()); } catch { /* keep the last number */ }
}
refreshAlone();
setInterval(refreshAlone, 15000);
subscribe("board", (data) => showAlone(data));

const modeButtons = document.querySelectorAll(".mode-toggle button");
function paintMode() {
  const k = !!getPrefs().kubectl;
  modeButtons.forEach((b) => b.setAttribute("aria-pressed", String((b.dataset.mode === "kubectl") === k)));
}
modeButtons.forEach((b) => b.addEventListener("click", () => setPrefs({ kubectl: b.dataset.mode === "kubectl" })));
onPrefsChange(paintMode);
paintMode();

// The kubectl drawer loads on first use.
document.getElementById("term-open")?.addEventListener("click", async () => {
  const { openKubectl } = await import("./kubectl.js");
  openKubectl();
});
onMockChange(showDemoBadge);
showDemoBadge();
render();
