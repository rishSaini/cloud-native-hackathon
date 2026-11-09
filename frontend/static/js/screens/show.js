// Show across the table: full screen, huge high-contrast text. The top half is turned 180°
// toward the person opposite (your name and how to talk to you); the bottom half faces you
// (what to talk about). Keeps the screen awake where the Wake Lock API allows.

import { announce } from "../a11y.js";
import { h } from "../format.js";
import { loadErrorView } from "../load-error.js";
import { loadMe } from "../store.js";

export default {
  title: "Show across the table",
  chrome: false,
  async render(main, { navigate }) {
    const { card, error } = await loadMe();
    if (error) { main.append(loadErrorView()); return; }
    if (!card) { navigate("/card"); return; }

    let flippedWhole = false;
    const theirs = h("section", { class: "show-half show-theirs", "aria-label": "For the person across from you" },
      h("p", { class: "show-name" }, card.name),
      card.pronouns ? h("p", { class: "show-pronouns" }, card.pronouns) : null,
      card.howToTalk ? h("p", { class: "show-talk" }, card.howToTalk) : null,
    );
    const mine = h("section", { class: "show-half show-mine", "aria-labelledby": "show-h" },
      h("h1", { id: "show-h", class: "show-mine-title" }, "Show across the table"),
      h("p", { class: "show-hint" }, "The top half faces them. Things you could talk about:"),
      h("ul", { class: "show-starters" },
        card.workingOn ? h("li", {}, `I'm working on ${card.workingOn}`) : null,
        card.askMeAbout ? h("li", {}, `Ask me about ${card.askMeAbout}`) : null,
        card.lookingFor ? h("li", {}, `I'm looking for ${card.lookingFor}`) : null,
        h("li", {}, "What are you working on right now?"),
      ),
      h("div", { class: "show-actions" },
        h("button", { type: "button", class: "btn btn-secondary", "aria-pressed": "false", onclick: (e) => {
          flippedWhole = !flippedWhole;
          view.classList.toggle("whole", flippedWhole);
          e.currentTarget.setAttribute("aria-pressed", String(flippedWhole));
          e.currentTarget.textContent = flippedWhole ? "Show both halves" : "Whole screen for them";
          announce(flippedWhole ? "The whole screen now faces them." : "Back to two halves.");
        } }, "Whole screen for them"),
        h("a", { class: "btn btn-primary", href: "#/card" }, "Done"),
      ),
    );
    const view = h("div", { class: "show" }, theirs, mine);
    main.append(view);

    // Keep the screen on while showing the card; fail silently where unsupported.
    let lock = null;
    let disposed = false;
    const requestLock = async () => {
      try {
        const next = await navigator.wakeLock?.request("screen");
        // If the person left while we were waiting, let go straight away.
        if (disposed) { try { next?.release(); } catch { /* ignore */ } return; }
        lock = next;
      } catch { lock = null; }
    };
    requestLock();
    const onVisible = () => { if (!document.hidden) requestLock(); };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      disposed = true;
      document.removeEventListener("visibilitychange", onVisible);
      try { lock?.release(); } catch { /* already released */ }
    };
  },
};
