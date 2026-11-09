// Real photographs for a personal touch (Unsplash License; see /static/img/CREDITS.md).
// Each has descriptive alt text and a small visible credit.

import { h } from "./format.js";

const PHOTOS = {
  welcome: { src: "/static/img/welcome.jpg", alt: "Coffee, a notebook and two people's hands on a café table", credit: "Alejandro Escamilla", w: 1100, h: 1400 },
  table: { src: "/static/img/table.jpg", alt: "A café table by a tall window", credit: "Luke Chesser", w: 1200, h: 700 },
  met: { src: "/static/img/met.jpg", alt: "Two people sitting together on a bench at sunset", credit: "Charlie Foster", w: 1200, h: 700 },
  grow: { src: "/static/img/grow.jpg", alt: "Sneakers on a path through a field", credit: "Ilham Rahmansyah", w: 1200, h: 700 },
  stage: { src: "/static/img/stage.jpg", alt: "A stage under bright lights", credit: "Daniel Robert", w: 1200, h: 600 },
};

export function photo(name, { cls = "band-photo", caption = null, eager = false } = {}) {
  const p = PHOTOS[name];
  return h("figure", { class: `photo ${cls}` },
    h("img", { src: p.src, alt: p.alt, width: p.w, height: p.h, loading: eager ? "eager" : "lazy", decoding: "async" }),
    caption ? h("figcaption", {}, caption) : null,
    h("span", { class: "credit" }, `Photo: ${p.credit} / Unsplash`),
  );
}
