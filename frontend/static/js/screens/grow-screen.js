// Your growth: the comfort ladder, your next challenge, small wins, how comfortable breaks
// have felt, conversations you started on your own, and a pocket question coach.
// The point is to need this app less: the top rungs are doing it without a match.

import { announce } from "../a11y.js";
import { api } from "../api.js";
import { h } from "../format.js";
import { QUESTION_COACH } from "../grow.js";
import { photo } from "../photos.js";

function sparkline(values) {
  if (values.length < 2) return null;
  const w = 280, hgt = 70, pad = 8;
  const pts = values.map((v, i) => [pad + (i * (w - pad * 2)) / (values.length - 1), hgt - pad - ((v - 1) / 4) * (hgt - pad * 2)]);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${hgt}`);
  svg.setAttribute("class", "sparkline");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `Comfort after each break, from 1 to 5: ${values.join(", ")}`);
  svg.innerHTML = `<polyline fill="none" stroke="url(#spark)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${pts.map((p) => p.map((n) => n.toFixed(1)).join(",")).join(" ")}"/>
    <defs><linearGradient id="spark" x1="0" x2="1"><stop offset="0" stop-color="#A5B4FC"/><stop offset="1" stop-color="#5EEAD4"/></linearGradient></defs>
    ${pts.map((p) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="4" fill="#F1F0FA"/>`).join("")}`;
  return svg;
}

export default {
  title: "Your growth",
  async render(main) {
    main.append(h("h1", { class: "screen-title" }, "Your growth"));
    const region = h("div", { class: "stack grow-page" });
    main.append(region);

    let g;
    try { g = await api.growth(); } catch {
      region.append(h("p", { class: "notice" }, "We couldn't load your growth right now. Please try again in a moment."));
      return;
    }

    function paint() {
      region.replaceChildren(
        photo("grow", { caption: "One step at a time" }),
        h("p", { class: "lede" }, "Every break is practice. The goal is to need us less: the top step is starting conversations on your own."),

        h("section", { class: "card", "aria-labelledby": "ladder-h" },
          h("h2", { id: "ladder-h" }, "Your comfort ladder"),
          h("ol", { class: "ladder" }, g.ladder.map((rung) => h("li", {
            class: rung.level < g.level ? "done" : rung.level === g.level ? "current" : "",
            "aria-current": rung.level === g.level ? "step" : null,
          },
            h("span", { class: "rung-num" }, rung.level < g.level ? "✓" : String(rung.level)),
            h("div", {}, h("p", { class: "rung-title" }, rung.title), h("p", { class: "rung-detail" }, rung.detail)),
          ))),
        ),

        h("section", { class: "card next-card", "aria-labelledby": "next-h" },
          h("p", { class: "section-eyebrow" }, "Next challenge"),
          h("h2", { id: "next-h" }, g.nextChallenge.title),
          h("p", { class: "muted" }, g.nextChallenge.detail),
          h("p", { class: "muted small" }, "It adapts: after a good, brave break we nudge you up a step; after a hard one we keep it gentle."),
        ),

        h("section", { class: "card", "aria-labelledby": "own-h" },
          h("h2", { id: "own-h" }, "On your own"),
          h("p", { class: "own-count" }, h("span", { class: "own-num" }, String(g.startedOnOwn)), ` ${g.startedOnOwn === 1 ? "conversation" : "conversations"} you started without a match`),
          h("button", { type: "button", class: "btn btn-primary btn-block", "data-key": "own", onclick: async () => {
            try {
              g = await api.startedOnOwn();
              announce("Nice. That's one more conversation you started on your own.");
              paint();
              region.querySelector('[data-key="own"]')?.focus();
            } catch { /* keep the count */ }
          } }, "I started one on my own"),
        ),

        h("section", { class: "card", "aria-labelledby": "wins-h" },
          h("h2", { id: "wins-h" }, "Small wins"),
          g.wins.length
            ? h("ul", { class: "win-list" }, g.wins.slice(0, 8).map((w) => h("li", {}, "✦ ", w.text)))
            : h("p", { class: "muted" }, "After your first break, tap \"How did that go?\" on the Group screen. Your wins show up here."),
          g.comfortTrend.length >= 2 ? h("p", { class: "section-eyebrow" }, "How comfortable breaks felt") : null,
          sparkline(g.comfortTrend),
        ),

        h("section", { class: "card", "aria-labelledby": "coach-h" },
          h("h2", { id: "coach-h" }, "Question coach"),
          h("p", { class: "muted" }, "Borrow these until they feel like yours."),
          ...QUESTION_COACH.map((group) => h("details", { class: "coach" },
            h("summary", {}, group.title),
            h("ul", {}, group.items.map((q) => h("li", {}, q))),
          )),
        ),
      );
    }
    paint();
  },
};
