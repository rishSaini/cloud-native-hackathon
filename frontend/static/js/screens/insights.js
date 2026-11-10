// Insights (K17): how full each room is, how each talk held its room, and whether
// people with access needs wait longer for a seat. Counts only: no person is tracked.
// Data: GET /api/insights (mock-api.js in demo mode). Refreshes every few seconds.

import { api } from "../api.js";
import { h, twoTone } from "../format.js";

const REFRESH_MS = 5000;
const SLO_GAP = 5; // seconds: the equity gap we promise to stay under
const ROOM_NAME = { "room-101": "Room 101", "room-155": "Room 155", "room-251": "Room 251", "room-hall-b": "Hall B" };
const WORD_CLASS = { HELD: "ins-held", STEADY: "ins-steady", DROPPED: "ins-dropped" };
const SVG_NS = "http://www.w3.org/2000/svg";

const roomName = (id) => ROOM_NAME[id] || id;
const pct = (x) => `${Math.round(x * 100)}%`;
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

function svg(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

/** The engagement curve: people in the room since the talk started, as a step line. */
function curve(room, startedAt, span) {
  const e = room.engagement;
  const W = 600, H = 150, top = 16, bottom = 22;
  const ymax = Math.max(5, Math.ceil(e.peak * 1.15));
  const x = (t) => (t / span) * W;
  const y = (v) => top + (1 - v / ymax) * (H - top - bottom);
  const t0 = Date.parse(startedAt);
  let d = `M0 ${y(0)}`;
  for (const p of room.history) {
    const t = (Date.parse(p.at) - t0) / 1000;
    d += ` H${x(t).toFixed(1)} V${y(p.taken).toFixed(1)}`;
  }
  d += ` H${W}`;

  const el = svg("svg", {
    class: `ins-curve ${WORD_CLASS[e.word]}`, viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img",
    "aria-label": `${roomName(room.room)}: peak ${e.peak} people at ${mmss(e.peakAtSeconds)}, now ${e.now}, ${pct(e.kept)} stayed`
      + (e.drop ? `. ${e.drop.people} people left between ${mmss(e.drop.fromSeconds)} and ${mmss(e.drop.toSeconds)}.` : "."),
  });
  el.append(svg("line", { class: "ins-axis", x1: 0, x2: W, y1: y(0), y2: y(0) }));
  if (e.drop) {
    el.append(svg("rect", {
      class: "ins-dropband", x: x(e.drop.fromSeconds), y: top,
      width: Math.max(3, x(e.drop.toSeconds) - x(e.drop.fromSeconds)), height: H - top - bottom,
    }));
  }
  el.append(svg("path", { class: "ins-area", d: `${d} V${y(0)} H0 Z` }));
  el.append(svg("path", { class: "ins-line", d, "vector-effect": "non-scaling-stroke" }));
  // The SVG stretches to the card's width, so the dot and the labels are HTML on top: they keep their shape.
  const at = (px, py) => `left:${((px / W) * 100).toFixed(2)}%;top:${((py / H) * 100).toFixed(2)}%`;
  const step = span > 1800 ? 900 : span > 600 ? 300 : 60;
  const ticks = [];
  for (let s = 0; s <= span - step / 3; s += step) {
    ticks.push(h("span", { class: `ins-tick${s === 0 ? " ins-tick-start" : ""}`, style: `left:${((x(s) / W) * 100).toFixed(2)}%` },
      s === 0 ? "start" : `+${mmss(s)}`));
  }
  return h("div", { class: "ins-chart" }, el,
    h("span", { class: "ins-peak", style: at(x(e.peakAtSeconds), y(e.peak)), "aria-hidden": "true" }),
    h("div", { class: "ins-ticks", "aria-hidden": "true" }, ticks));
}

function talkCard(room, startedAt, span) {
  const e = room.engagement;
  const talk = room.talk || {};
  return h("li", { class: `card ins-talk ${WORD_CLASS[e.word]}` },
    h("p", { class: "section-eyebrow" }, [roomName(room.room), talk.track].filter(Boolean).join(" · ")),
    h("h3", { class: "ins-talk-title" }, talk.title || roomName(room.room)),
    h("p", { class: "ins-stats" },
      h("span", { class: "ins-word" }, e.word),
      h("span", {}, "now ", h("b", {}, String(e.now)), " of peak ", h("b", {}, String(e.peak))),
      h("span", {}, h("b", {}, pct(e.kept)), " stayed"),
    ),
    curve(room, startedAt, span),
    h("p", { class: "muted small" }, e.drop
      ? `Sharpest drop: ${e.drop.people} people left between +${mmss(e.drop.fromSeconds)} and +${mmss(e.drop.toSeconds)}.`
      : "No sharp drop so far."),
  );
}

function roomRow(r) {
  const full = r.taken >= r.seats;
  return h("li", { class: "ins-room" },
    h("div", { class: "ins-room-line" },
      h("span", { class: "ins-room-name" }, roomName(r.room)),
      h("span", { class: `ins-room-status ${full ? "ins-dropped" : "ins-held"}` }, full ? "FULL" : "OPEN"),
      h("span", { class: "ins-room-count" }, `${r.taken} of ${r.seats}`),
    ),
    h("div", { class: "ins-bar", role: "img", "aria-label": `${roomName(r.room)}: ${r.taken} of ${r.seats} seats taken` },
      h("span", { style: `width:${Math.min(100, Math.round((r.occupancy || 0) * 100))}%` })),
  );
}

function fairCard(t) {
  const max = Math.max(1, t.withNeeds.p95Seconds || 0, t.withoutNeeds.p95Seconds || 0);
  const row = (label, b, cls) => b.hidden
    ? h("div", { class: "ins-fair-row" },
        h("div", { class: "ins-room-line" }, h("span", {}, label), h("span", { class: "ins-room-count" }, "–")),
        h("p", { class: "muted small" }, `Too few people to show (${b.count}). We show a group from 5 people.`))
    : h("div", { class: "ins-fair-row" },
        h("div", { class: "ins-room-line" }, h("span", {}, label), h("span", { class: "ins-room-count" }, `${b.p95Seconds.toFixed(1)} s`)),
        h("div", { class: `ins-bar ${cls}`, role: "img", "aria-label": `${label}: 95% seated within ${b.p95Seconds.toFixed(1)} seconds` },
          h("span", { style: `width:${(b.p95Seconds / max) * 100}%` })));
  const gap = t.p95GapSeconds;
  const ok = gap != null && gap <= SLO_GAP;
  return h("section", { class: "card ins-fair", "aria-labelledby": "fair-h" },
    h("p", { class: "section-eyebrow" }, "Fair seating"),
    h("h2", { id: "fair-h" }, "95% of people seated within"),
    row("With access needs", t.withNeeds, "ins-bar-needs"),
    row("Without", t.withoutNeeds, "ins-bar-noneeds"),
    gap == null ? null : h("p", { class: "ins-gap" },
      h("span", { class: "ins-gap-num" }, `${gap > 0 ? "+" : ""}${gap.toFixed(1)} s`),
      h("span", { class: "muted" }, " longer wait for people with access needs. "),
      h("span", { class: `ins-word ${ok ? "ins-held" : "ins-dropped"}` }, ok ? "Within goal" : "Over goal"),
      h("span", { class: "muted" }, ` (under ${SLO_GAP} s)`)),
  );
}

export default {
  title: "Insights",
  async render(main) {
    main.append(
      h("h1", { id: "screen-h", class: "screen-title" }, twoTone("Rooms, ", "right now.")),
      h("p", { class: "lede" }, "How full each room is, how each talk held its room, and whether everyone gets a seat as fast. Counts only: we never track a person."),
    );
    const region = h("div", { class: "stack ins", "aria-busy": "true" }) // no aria-live: it refreshes every few seconds;
    main.append(region);

    let failed = false;
    async function load() {
      let d;
      try { d = await api.insights(); } catch {
        if (!failed) region.replaceChildren(h("p", { class: "notice" }, "We couldn't load the room numbers right now. We'll keep trying."));
        failed = true;
        return;
      }
      failed = false;
      region.setAttribute("aria-busy", "false");
      const span = Math.max(180, (Date.parse(d.generatedAt) - Date.parse(d.startedAt)) / 1000);
      const talks = d.rooms.filter((r) => r.engagement);
      const order = Object.keys(ROOM_NAME);
      talks.sort((a, b) => order.indexOf(a.room) - order.indexOf(b.room));
      region.replaceChildren(
        h("section", { class: "card ins-hero", "aria-labelledby": "hero-h" },
          h("p", { class: "section-eyebrow", id: "hero-h" }, `Seats taken · slot ${d.slot}`),
          d.totals.seats
            ? h("p", { class: "ins-hero-line" },
                h("span", { class: "own-num" }, pct(d.totals.occupancy)),
                h("span", { class: "muted" }, ` ${d.totals.taken} of ${d.totals.seats} seats across all rooms`))
            : h("p", { class: "muted" }, "No seats are taken in this slot yet."),
          h("ul", { class: "ins-rooms" }, d.rooms.map(roomRow)),
        ),
        fairCard(d.timeToSeat),
        h("section", { "aria-labelledby": "eng-h" },
          h("p", { class: "section-eyebrow" }, "Engagement"),
          h("h2", { id: "eng-h" }, "How each talk held its room"),
          h("p", { class: "muted" }, "People in the room since the talk started. A shaded band marks the sharpest drop."),
          talks.length
            ? h("ul", { class: "ins-talks" }, talks.map((r) => talkCard(r, d.startedAt, span)))
            : h("p", { class: "muted" }, "No talk has started yet in this slot."),
        ),
        h("p", { class: "muted small ins-privacy" }, d.privacy, " Engagement curves are room counts, never people."),
      );
    }

    await load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  },
};
