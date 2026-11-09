// Big-screen board for a 1920×1080 projector: constellation in the center, the "people alone"
// hero number top right, room status cards on the right, an events ticker at the bottom,
// and a QR code to join. Shows only random IDs and room-level facts: never names, card
// text or access needs.
//
// The canvas is decorative for screen readers; a visually hidden summary carries the
// same facts. With reduced motion or calm mode the canvas is replaced by a plain grid.

import { announce, motionOK, onPrefsChange, getPrefs, setPrefs } from "../a11y.js";
import { demo as mockDemo } from "../mock-api.js";
import { api } from "../api.js";
import { formatTime, h } from "../format.js";
import { isLive, subscribe } from "../stream.js";
import { createSky } from "./sky.js";

const POLL_MS = 5000;
const FIXED_SHOW_MS = 60000;
const TICKER_LINES = 7;
const QR_SRC = "https://cdnjs.cloudflare.com/ajax/libs/qrcode-generator/1.4.4/qrcode.min.js";

const INCIDENT_WORDS = { captions: "Captions down", access: "Access problem", loud: "Very loud" };

function ensureStyles() {
  if (document.getElementById("board-css")) return;
  document.head.append(h("link", { id: "board-css", rel: "stylesheet", href: "/static/css/board.css" }));
}

function loadQrLib() {
  if (window.qrcode) return Promise.resolve(window.qrcode);
  return new Promise((resolve, reject) => {
    const s = h("script", { src: QR_SRC, crossorigin: "anonymous", referrerpolicy: "no-referrer" });
    s.onload = () => (window.qrcode ? resolve(window.qrcode) : reject(new Error("qr")));
    s.onerror = () => reject(new Error("qr"));
    document.head.append(s);
  });
}

async function renderQr(slot, url) {
  try {
    const qrcode = await loadQrLib();
    const qr = qrcode(0, "M");
    qr.addData(url);
    qr.make();
    const n = qr.getModuleCount();
    let d = "";
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `-2 -2 ${n + 4} ${n + 4}`);
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("shape-rendering", "crispEdges");
    svg.innerHTML = `<rect x="-2" y="-2" width="${n + 4}" height="${n + 4}" fill="#fff"/><path d="${d}" fill="#0E1430"/>`;
    slot.replaceChildren(svg);
  } catch {
    slot.replaceChildren(); // the URL text below still works
  }
}

export default {
  title: "Board",
  chrome: false,
  sky: true,
  async render(main, { query } = {}) {
    const demoMode = query?.get("demo") === "1";
    ensureStyles();
    let board = null;
    const fixedSeen = new Map();  // roomId -> { at: Date.now(), fixedAt }
    const tickerSeen = new Set();
    const tickerLines = [];

    // ---- skeleton ----
    const heroNum = h("span", { class: "hero-num" }, "–");
    const heroWord = h("span", { class: "hero-word" }, " people alone");
    // Anonymous: the share of reflections that said everyone got a turn.
    const heardLine = h("p", { class: "hero-heard", hidden: true });
    const finale = h("div", { class: "finale", hidden: true, "aria-hidden": "true" },
      h("p", { class: "finale-num" }, "0"), h("p", { class: "finale-word" }, "people alone"));
    const hint = demoMode ? h("p", { class: "demo-hint code", "aria-hidden": "true" },
      "demo  C close room · G groups · I incident · F finale · K kubectl · R reset") : null;
    const clock = h("p", { class: "board-clock code" });
    const pill = h("p", { class: "board-pill", role: "status", hidden: true }, "Reconnecting");
    const banner = h("div", { class: "board-banner", hidden: true });
    let bannerTimer = null;
    let firstEvents = true; // events already in the first snapshot don't trigger a banner
    let incidentNo = 400;
    const canvas = h("canvas", { class: "sky-canvas", "aria-hidden": "true" });
    const fallback = h("ul", { class: "room-grid", hidden: true, "aria-hidden": "true" });
    const cards = h("ul", { class: "status-cards" });
    const ticker = h("ol", { class: "ticker-lines" });
    const qrSlot = h("div", { class: "qr" });
    const joinUrl = `${location.origin}/`;
    const summaryRooms = h("ul", {});
    const summaryAlone = h("p", {});

    const view = h("section", { class: "board", "aria-labelledby": "board-h" },
      h("header", { class: "board-head" },
        h("div", {},
          h("h1", { id: "board-h" }, "Affinity"),
          h("p", { class: "board-tagline" }, "Nobody should fly to a conference and end up standing alone."),
          clock,
          pill,
        ),
        h("div", { class: "hero", "aria-hidden": "true" },
          h("p", { class: "hero-line" }, heroNum, heroWord),
          h("p", { class: "hero-label" }, "at this break"),
          heardLine,
        ),
      ),
      h("div", { class: "board-sky" }, banner, canvas, fallback, finale),
      h("aside", { class: "board-side", "aria-labelledby": "rooms-h" },
        h("h2", { id: "rooms-h", class: "side-title" }, "Rooms"),
        cards,
        h("div", { class: "join" },
          qrSlot,
          h("div", {},
            h("p", { class: "join-line" }, "Scan to join. Then look for your star."),
            h("p", { class: "join-url code" }, joinUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")),
          ),
        ),
      ),
      h("footer", { class: "ticker" },
        h("h2", { class: "ticker-title code" }, "$ kubectl get events -w"),
        ticker,
      ),
      h("section", { class: "visually-hidden", "aria-labelledby": "summary-h" },
        h("h2", { id: "summary-h" }, "Summary"),
        summaryAlone,
        summaryRooms,
      ),
    );
    main.append(view);
    renderQr(qrSlot, joinUrl);

    const sky = createSky(canvas, { motion: motionOK() });

    // ---- painting ----
    function cardFor(room) {
      const status = room.status || "OPEN";
      const inc = room.incident;
      const fixed = fixedSeen.get(room.id);
      const lines = [
        h("p", { class: "status-line" },
          h("span", { class: "room-name" }, kube() ? `node/${room.id}` : room.name),
          h("span", { class: "sep", "aria-hidden": "true" }, " · "),
          h("span", { class: `status-word s-${status.toLowerCase()}` }, status),
          h("span", { class: "sep", "aria-hidden": "true" }, " · "),
          h("span", { class: "count" }, `${room.taken} of ${room.seats}`),
        ),
      ];
      if (inc && inc.state !== "resolved") {
        lines.push(h("p", { class: "incident-line" },
          `${INCIDENT_WORDS[inc.type] || "Problem reported"} · reported ${inc.reportedAt} · ${inc.state === "acknowledged" ? "staff on it" : "staff alerted"}`));
      } else if (fixed) {
        lines.push(h("p", { class: "fixed-line" }, `Fixed ${fixed.fixedAt}`));
      }
      const fading = fixed && Date.now() - fixed.at > FIXED_SHOW_MS - 5000;
      return h("li", { class: `status-card c-${status.toLowerCase()}${fading ? " fading" : ""}` }, lines);
    }

    function trackFixed() {
      for (const room of board.rooms || []) {
        const inc = room.incident;
        if (inc && inc.state === "resolved" && !fixedSeen.has(room.id)) {
          fixedSeen.set(room.id, { at: Date.now(), fixedAt: inc.fixedAt || formatTime(new Date()) });
        }
        if (inc && inc.state !== "resolved") fixedSeen.delete(room.id);
      }
      for (const [id, f] of fixedSeen) if (Date.now() - f.at > FIXED_SHOW_MS) fixedSeen.delete(id);
    }

    function addTicker(events = []) {
      for (const ev of events) {
        const key = ev.id || `${ev.at}|${ev.reason}|${ev.message}`;
        if (tickerSeen.has(key)) continue;
        tickerSeen.add(key);
        tickerLines.push({ ...ev, key, fresh: true });
        if (!firstEvents) maybeBanner(ev);
      }
      firstEvents = false;
      while (tickerLines.length > TICKER_LINES) tickerLines.shift();
      if (tickerSeen.size > 500) tickerSeen.clear();
    }

    // "[INCIDENT-402] Room 251 closed ➔ evicting 35 pods to room-155, room-hall-b"
    function maybeBanner(ev) {
      let text = null;
      const evict = /^(\d+) pods: (\S+) closed → (.+)$/.exec(ev.message || "");
      if (ev.reason === "Evicted" && evict) {
        text = `${evict[2]} closed ➔ evicting ${evict[1]} pods to ${evict[3]}`;
      } else if (ev.reason === "Incident") {
        text = `${ev.message} ➔ staff alerted, rescheduling pods that need it`;
      }
      if (!text) return;
      incidentNo += 1;
      banner.replaceChildren(
        h("span", { class: "banner-tag code" }, `[INCIDENT-${incidentNo}]`),
        h("span", { class: "banner-text code" }, text),
      );
      banner.hidden = false;
      banner.classList.remove("enter");
      void banner.offsetWidth; // restart the glide
      banner.classList.add("enter");
      clearTimeout(bannerTimer);
      bannerTimer = setTimeout(() => { banner.hidden = true; }, 9000);
    }

    function paintTicker() {
      if (!tickerLines.length) {
        ticker.replaceChildren(h("li", { class: "t-waiting" }, h("span", { class: "t-at" }, "--:--"), h("span", {}, "Watching"), h("span", { class: "t-msg" }, "Waiting for the first event…")));
        return;
      }
      ticker.replaceChildren(...tickerLines.map((ev) => {
        const li = h("li", { class: ev.fresh ? "fresh" : "" },
          h("span", { class: "t-at" }, ev.at),
          h("span", { class: `t-reason r-${String(ev.reason).toLowerCase()}` }, ev.reason),
          h("span", { class: "t-msg" }, ev.message),
        );
        ev.fresh = false;
        return li;
      }));
    }

    function paintFallback() {
      fallback.replaceChildren(...(board.rooms || []).map((r) => {
        const share = Math.round(((r.taken || 0) / (r.seats || 1)) * 100);
        return h("li", { class: `grid-room c-${String(r.status).toLowerCase()}` },
          h("p", { class: "grid-name" }, r.name),
          h("p", { class: "grid-status code" }, r.status),
          h("p", { class: "grid-count" }, `${r.taken} of ${r.seats} seats taken`),
          h("div", { class: "grid-bar" }, h("span", { style: `width:${Math.min(100, share)}%` })),
        );
      }));
    }

    function kube() { return !!getPrefs().kubectl; }

    function paintMode() {
      view.classList.toggle("kubectl", kube());
      sky.setKubectl(kube());
      heroWord.textContent = kube() ? " pods unscheduled" : " people alone";
      if (board) paint();
      const still = !motionOK();
      canvas.hidden = still;
      fallback.hidden = !still;
      view.classList.toggle("calm", !!getPrefs().calm);
      sky.setMotion(!still);
    }

    function paint() {
      if (!board) return;
      trackFixed();
      addTicker(board.events);
      heroNum.textContent = String(board.alone ?? 0);
      heardLine.hidden = board.feltHeard == null;
      if (board.feltHeard != null) heardLine.textContent = `${board.feltHeard}% felt heard`;
      cards.replaceChildren(...(board.rooms || []).map(cardFor));
      paintTicker();
      paintFallback();
      sky.update(board);
      summaryAlone.textContent = `${board.alone ?? 0} people alone at this break.`;
      summaryRooms.replaceChildren(...(board.rooms || []).map((r) =>
        h("li", {}, `${r.name}: ${r.status}, ${r.taken} of ${r.seats} seats taken${r.incident && r.incident.state !== "resolved" ? `, ${INCIDENT_WORDS[r.incident.type] || "problem reported"}` : ""}.`)));
    }

    function setBoard(next) {
      const data = next?.board ?? next;
      if (!data?.rooms) return;
      board = data;
      paint();
    }

    async function refresh() {
      try {
        setBoard(await api.board());
        pill.hidden = true;
      } catch {
        pill.hidden = false; // keep the last known state
      }
    }

    const tickClock = () => { clock.textContent = `${formatTime(new Date())} MT`; };
    tickClock();

    const unsubs = [
      subscribe("board", (data) => { if (data?.rooms || data?.board) setBoard(data); else refresh(); }),
      onPrefsChange(paintMode),
    ];
    const poll = setInterval(() => { if (!isLive()) refresh(); }, POLL_MS);
    const clockTimer = setInterval(() => { tickClock(); if (board) { trackFixed(); cards.replaceChildren(...board.rooms.map(cardFor)); } }, 5000);

    // ---- demo mode: #/board?demo=1 ----
    function playFinale() {
      mockDemo.finale();
      banner.hidden = true; // a clean stage for the finale
      // Stars drift into constellations first; then "0 people alone" fades in.
      finale.hidden = false;
      finale.classList.remove("show");
      setTimeout(() => finale.classList.add("show"), motionOK() ? 1400 : 0);
      announce("Finale: everyone is in a group. Zero people alone.");
    }
    const KEYS = {
      c: () => { mockDemo.closeBusiest(); announce("Closed the busiest room."); },
      g: () => { mockDemo.formGroups(); announce("Formed break groups."); },
      i: () => { mockDemo.openIncident(); announce("Opened a captions incident."); },
      f: playFinale,
      k: () => { setPrefs({ kubectl: !kube() }); announce(kube() ? "kubectl mode on." : "kubectl mode off."); },
      r: () => {
        mockDemo.reset();
        finale.hidden = true; finale.classList.remove("show");
        tickerLines.length = 0; tickerSeen.clear(); banner.hidden = true;
        announce("Board reset.");
      },
    };
    function onKey(e) {
      if (e.metaKey || e.ctrlKey || e.altKey || e.target.closest?.("input, textarea, select, [contenteditable]")) return;
      const key = e.key.toLowerCase();
      const fn = KEYS[key];
      if (!fn) return;
      e.preventDefault();
      if (key !== "f" && key !== "k") { finale.hidden = true; finale.classList.remove("show"); }
      fn();
    }
    if (demoMode) {
      document.addEventListener("keydown", onKey);
      view.append(hint);
    }

    paintMode();
    await refresh();

    // For rehearsal checks: how many stars are drawn.
    view.dataset.ready = "true";
    Object.defineProperty(view, "starCount", { get: () => sky.starCount });

    return () => {
      unsubs.forEach((u) => u());
      clearInterval(poll);
      clearInterval(clockTimer);
      clearTimeout(bannerTimer);
      sky.destroy();
      document.removeEventListener("keydown", onKey);
    };
  },
};
