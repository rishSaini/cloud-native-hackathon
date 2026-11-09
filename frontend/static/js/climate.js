// Room climate: noise, light and captions as attendees reported them, with how long ago,
// plus how full the room is. We show only what people reported, never a measured number
// and never an accessibility claim nobody confirmed (AFFINITY.md: "Only state what we know").

import { ago, h } from "./format.js";

const CHIPS = {
  noise: { quiet: ["Quiet", "ok"], loud: ["Loud", "warn"] },
  light: { good: ["Good light", "ok"], dim: ["Lights dim", "warn"], bright: ["Very bright", "warn"] },
  captions: { working: ["Captions working", "ok"], down: ["Captions down", "alert"] },
};
const ICONS = {
  noise: '<path d="M4 9.5h3l4-3.5v12l-4-3.5H4z"/><path d="M15 9a4 4 0 0 1 0 6M17.5 6.5a7.5 7.5 0 0 1 0 11"/>',
  light: '<circle cx="12" cy="12" r="3.6"/><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6 18 18M6 18l1.4-1.4M16.6 7.4 18 6"/>',
  captions: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 13h4M13 13h4M7 10h10"/>',
};

function icon(kind) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = ICONS[kind]; // static markup from this file
  return svg;
}

/** A seat-density bar with the share as text, e.g. "52% full · 58 seats left". */
export function densityBar(taken, seats) {
  if (!seats) return null;
  const share = Math.max(0, Math.min(100, Math.round((taken / seats) * 100)));
  const left = Math.max(0, seats - taken);
  const tone = share >= 100 ? "alert" : share >= 85 ? "warn" : "ok";
  return h("div", { class: `density ${tone}` },
    h("div", { class: "density-bar", role: "img", "aria-label": `${share}% of seats taken` },
      h("span", { style: `width:${share}%` })),
    h("p", { class: "density-text" }, share >= 100 ? `Full · ${seats} seats` : `${share}% full · ${left} seats left`),
  );
}

/** Chips for what people reported, or a plain "no reports yet". */
export function climateView(climate, { seats, taken } = {}) {
  const chips = [];
  for (const kind of ["noise", "light", "captions"]) {
    const value = climate?.[kind];
    const spec = value && CHIPS[kind][value];
    if (spec) chips.push(h("li", { class: `badge ${spec[1]}` }, icon(kind), spec[0]));
  }
  const age = climate?.minutesAgo;
  return h("div", { class: "climate" },
    h("p", { class: "climate-title" }, "Room right now"),
    densityBar(taken, seats),
    chips.length
      ? h("ul", { class: "badges", "aria-label": "Reported by attendees" }, chips)
      : h("p", { class: "muted climate-none" }, "No reports about this room yet."),
    chips.length && age != null ? h("p", { class: "report-age muted" }, `Reported by attendees ${ago(age)}`) : null,
  );
}
