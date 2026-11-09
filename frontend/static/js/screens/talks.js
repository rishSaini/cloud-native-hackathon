// Find a talk. Search works now (via /api/talks/search, falling back to /api/search);
// the "Ask about the talks" box lands in build step 9.

import { api } from "../api.js";
import { announce } from "../a11y.js";
import { formatDayTime, h } from "../format.js";
import { densityBar } from "../climate.js";

const BADGE = {
  seats: { word: "Seats left", tone: "ok", icon: '<path d="M5 11V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v5M4 11h16v4H4zM6 15v4M18 15v4"/>' },
  full: { word: "Full", tone: "alert", icon: '<circle cx="12" cy="12" r="8"/><path d="M8 12h8"/>' },
  captions: { word: "Captions on", tone: "ok", icon: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 13h4M13 13h4M7 10h10"/>' },
  "captions-down": { word: "Captions down", tone: "warn", icon: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M5 5l14 14"/>' },
  quiet: { word: "Reported quiet", tone: "ok", icon: '<path d="M4 9.5h3l4-3.5v12l-4-3.5H4z"/>' },
  loud: { word: "Reported loud", tone: "warn", icon: '<path d="M4 9.5h3l4-3.5v12l-4-3.5H4z"/><path d="M15 9a4 4 0 0 1 0 6M17.5 6.5a7.5 7.5 0 0 1 0 11"/>' },
  dim: { word: "Reported dim", tone: "warn", icon: '<circle cx="12" cy="12" r="3.6"/>' },
};

export function badgeList(badges = []) {
  const items = badges.filter((b) => BADGE[b]).map((b) => {
    const spec = BADGE[b];
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = spec.icon; // static markup from this file
    return h("li", { class: `badge ${spec.tone}` }, icon, spec.word);
  });
  return items.length ? h("ul", { class: "badges", "aria-label": "Room status" }, items) : null;
}

// Reported noise and light as extra badges in search results (captions are already a badge).
function climateBadges(climate) {
  if (!climate) return [];
  return [climate.noise === "quiet" && "quiet", climate.noise === "loud" && "loud", climate.light === "dim" && "dim"].filter(Boolean);
}

export function talkCard(talk) {
  const meta = [talk.startsAt ? formatDayTime(talk.startsAt) : null, talk.roomName].filter(Boolean).join(" · ");
  return h("li", { class: "card" },
    h("h3", { class: "result-title" }, talk.title),
    meta ? h("p", { class: "result-meta" }, meta) : null,
    talk.abstract ? h("p", { class: "result-abstract" }, talk.abstract) : null,
    talk.seats ? densityBar(talk.taken || 0, talk.seats) : null,
    badgeList([...(talk.badges || []), ...climateBadges(talk.climate)]),
  );
}

export default {
  title: "Find a talk",
  render(main) {
    const status = h("p", { class: "muted", id: "search-status" });
    const results = h("ul", { class: "results", "aria-labelledby": "results-h" });
    const input = h("input", {
      class: "input", id: "q", type: "search", name: "q", autocomplete: "off",
      placeholder: "Search talks, like 'security for beginners'",
      "aria-describedby": "search-status",
    });
    const button = h("button", { class: "btn btn-primary", type: "submit" }, "Search");

    const form = h("form", { role: "search", class: "stack", "aria-labelledby": "search-h" },
      h("div", { class: "field" },
        h("label", { for: "q", id: "search-h" }, "Search talks"),
        h("div", { class: "input-row" }, input, button),
      ),
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const q = input.value.trim();
      if (!q) { input.focus(); return; }
      status.textContent = "Searching…";
      button.disabled = true;
      try {
        const data = await api.searchTalks(q);
        const hits = data.hits || [];
        results.replaceChildren(...hits.map(talkCard));
        const summary = data.note || (hits.length ? `${hits.length} ${hits.length === 1 ? "talk" : "talks"} found.` : "No talks matched. Try fewer or different words.");
        status.textContent = summary;
        announce(summary);
      } catch {
        status.textContent = "We couldn't reach the server. Please try again in a moment.";
        announce(status.textContent);
      } finally {
        button.disabled = false;
      }
    });

    main.append(
      h("a", { class: "back-link", href: "#/now" }, "← Back to now"),
      h("h1", { class: "screen-title" }, "Find a talk"),
      form,
      status,
      h("h2", { id: "results-h", class: "visually-hidden" }, "Results"),
      results,
    );
  },
};
