// Router, app chrome and shared state. Hash routes only, so the backend only ever serves "/".
// The one exception is shared cards at /c/{token}; the token never goes into a hash, query or log.

import { focusScreen } from "./a11y.js";
import { isMock, onMockChange } from "./api.js";

// Each route lazily imports a screen module: `export default { title, chrome, render(main, ctx) }`.
// render may return a cleanup function, called when the person leaves the screen.
const ROUTES = {
  "/": () => import("./screens/welcome.js"),
  "/now": () => import("./screens/now.js"),
  "/talks": () => import("./screens/talks.js"),
  "/card": () => import("./screens/card.js"),
  "/card/show": () => import("./screens/show.js"),
  "/group": () => import("./screens/group.js"),
  "/report": () => import("./screens/report.js"),
  "/met": () => import("./screens/met.js"),
  "/settings": () => import("./screens/settings.js"),
  "/board": () => import("./board/board.js"),
  "/staff": () => import("./screens/staff.js"),
};

const TAB_FOR = { "/now": "now", "/talks": "now", "/card": "card", "/card/show": "card", "/group": "group", "/report": "report", "/met": "met" };

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
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", screen.sky ? "#0E1430" : "#FBF7F0");
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
onMockChange(showDemoBadge);
showDemoBadge();
render();
