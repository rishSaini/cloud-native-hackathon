// People you've met: saved only when both people agreed. Each card says where you met.
// "Your constellation" draws you in the middle with everyone you met around you.

import { api } from "../api.js";
import { accentColor, avatarColor, starColor } from "../color.js";
import { formatDayTime, h } from "../format.js";
import { loadErrorView } from "../load-error.js";
import { currentMe, loadMe } from "../store.js";

function constellation(people, myId) {
  const n = people.length;
  const cx = 160, cy = 110, r = 78;
  const pts = people.map((p, i) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2 + 0.7; // tilted, so two people make a diagonal, not a pole
    return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), color: starColor(p.displayId) };
  });
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 320 220");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("met-sky");
  const lines = pts.map((p) => `<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}"/>`).join("");
  const stars = pts.map((p, i) => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="16" fill="${p.color}" opacity="0.16"/><circle class="met-star" style="animation-delay:${(i * 0.4).toFixed(1)}s" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="7" fill="${p.color}"/>`).join("");
  // Faint background stars, placed the same way every time.
  let seed = 7;
  const rnd = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  const dust = Array.from({ length: 34 }, () => `<circle cx="${(rnd() * 320).toFixed(0)}" cy="${(rnd() * 220).toFixed(0)}" r="${(0.5 + rnd() * 1.1).toFixed(1)}" fill="#F4F1FF" opacity="${(0.25 + rnd() * 0.4).toFixed(2)}"/>`).join("");
  const ring = pts.length > 2 ? `<polygon points="${pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}" fill="none" stroke="rgba(244,241,255,0.14)" stroke-width="1"/>` : "";
  const me = myId ? starColor(myId) : "#F4F1FF";
  svg.innerHTML = `<rect width="320" height="220" rx="22" fill="#0E1430"/>
    ${dust}${ring}
    <g stroke="rgba(244,241,255,0.4)" stroke-width="1.2">${lines}</g>
    ${stars}
    <circle cx="${cx}" cy="${cy}" r="11" fill="${me}"/><circle cx="${cx}" cy="${cy}" r="20" fill="${me}" opacity="0.18"/>`;
  return svg;
}

export default {
  title: "People you've met",
  async render(main) {
    const { error } = await loadMe();
    if (error) { main.append(loadErrorView()); return; }
    main.append(h("h1", { class: "screen-title" }, "People you've met"));

    let people = [];
    try { people = await api.connections(); } catch {
      main.append(h("p", { class: "notice" }, "We couldn't load your connections. Please try again in a moment."));
      return;
    }

    if (!people.length) {
      main.append(h("section", { class: "card coming-soon", "aria-labelledby": "met-h" },
        h("h2", { id: "met-h" }, "Nobody saved yet"),
        h("p", { class: "muted" }, "At your break table, tap \"Exchange stars\". If the other person agrees too, they show up here with where you met."),
        h("a", { class: "btn btn-secondary", href: "#/group" }, "Go to your group"),
      ));
      return;
    }

    main.append(
      h("section", { class: "card met-constellation", "aria-labelledby": "const-h" },
        h("h2", { id: "const-h" }, "Your constellation"),
        constellation(people, currentMe()?.displayId),
        h("p", { class: "muted" }, `You and ${people.length} ${people.length === 1 ? "person" : "people"} you met. Screenshot it to keep.`),
      ),
      h("ul", { class: "met-list" }, people.map((p) => {
        const avatar = h("span", { class: "avatar", "aria-hidden": "true" }, (p.name || "?").slice(0, 1).toUpperCase());
        avatar.style.background = avatarColor(p.displayId);
        const li = h("li", { class: "member met-card" },
          h("div", { class: "member-head" },
            avatar,
            h("div", { class: "member-who" },
              h("p", { class: "member-name" }, p.name, p.pronouns ? h("span", { class: "member-pronouns" }, ` (${p.pronouns})`) : null),
              h("p", { class: "met-where" }, [p.landmark || p.place, p.metAt ? formatDayTime(p.metAt) : null].filter(Boolean).join(" · ")),
            ),
          ),
          p.workingOn ? h("p", { class: "met-working" }, `Working on ${p.workingOn}`) : null,
        );
        li.style.setProperty("--accent", accentColor(p.displayId));
        return li;
      })),
    );
  },
};
