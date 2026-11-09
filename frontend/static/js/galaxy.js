// A small galaxy unique to each person, grown from their random ID and what they're working
// on. Same inputs, same galaxy. Decorative: it carries no information on its own.

import { personHue } from "./color.js";

function seeded(text) {
  let s = 2166136261;
  for (const ch of String(text)) s = Math.imul(s ^ ch.charCodeAt(0), 16777619) >>> 0;
  return () => {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

export function galaxySvg({ id = "you", interests = "", size = 112 } = {}) {
  const rnd = seeded(`${id}|${interests}`);
  const hue = personHue(id);
  const hue2 = (hue + 40 + Math.floor(rnd() * 80)) % 360;
  const arms = 2 + Math.floor(rnd() * 2);
  const count = 10 + Math.floor(rnd() * 6);
  const c = 56;
  const stars = [];
  for (let i = 0; i < count; i++) {
    const arm = i % arms;
    const t = (i / count) * 2.6 + rnd() * 0.25;
    const angle = t * 2.2 + (arm / arms) * Math.PI * 2;
    const r = 8 + t * 15;
    stars.push({ x: c + r * Math.cos(angle), y: c + r * Math.sin(angle), s: 1 + rnd() * 2.2, h: rnd() < 0.5 ? hue : hue2 });
  }
  const lines = stars.slice(0, Math.min(5, stars.length - 1)).map((p, i) => {
    const q = stars[i + 1];
    return `<line x1="${p.x.toFixed(1)}" y1="${p.y.toFixed(1)}" x2="${q.x.toFixed(1)}" y2="${q.y.toFixed(1)}"/>`;
  }).join("");
  const dots = stars.map((p) => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${p.s.toFixed(1)}" fill="hsl(${p.h} 80% 80%)"/>`).join("");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 112 112");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("galaxy");
  svg.innerHTML = `
    <defs><radialGradient id="gx-${hue}" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="hsl(${hue} 90% 85%)" stop-opacity=".95"/>
      <stop offset=".25" stop-color="hsl(${hue} 80% 60%)" stop-opacity=".45"/>
      <stop offset="1" stop-color="hsl(${hue2} 70% 40%)" stop-opacity="0"/>
    </radialGradient></defs>
    <circle cx="56" cy="56" r="54" fill="url(#gx-${hue})"/>
    <g stroke="hsl(${hue} 70% 85% / .35)" stroke-width=".8">${lines}</g>
    ${dots}
    <circle cx="56" cy="56" r="4.5" fill="#fff"/>`;
  return svg;
}
