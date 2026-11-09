// The flip card. Front: name, pronouns, working on, ask me about.
// Back: how to talk to me, best way to reach me, looking for.
// Only the visible face is exposed to assistive tech; the other face is inert.

import { motionOK, announce } from "./a11y.js";
import { accentColor } from "./color.js";
import { h } from "./format.js";

export const FIELDS = {
  name: "Name",
  pronouns: "Pronouns",
  workingOn: "Working on",
  askMeAbout: "Ask me about",
  howToTalk: "How to talk to me",
  reachMe: "Best way to reach me",
  lookingFor: "Looking for",
};

function row(label, value, cls = "") {
  if (!value) return null;
  return h("div", { class: `card-row ${cls}` }, h("dt", {}, label), h("dd", {}, value));
}

function face(card, side) {
  if (side === "front") {
    return h("dl", { class: "card-fields" },
      row(FIELDS.workingOn, card.workingOn),
      row(FIELDS.askMeAbout, card.askMeAbout),
    );
  }
  return h("dl", { class: "card-fields" },
    row(FIELDS.howToTalk, card.howToTalk, "card-row-big"),
    row(FIELDS.reachMe, card.reachMe),
    row(FIELDS.lookingFor, card.lookingFor),
  );
}

function header(card) {
  return h("div", { class: "card-head" },
    h("p", { class: "card-name" }, card.name || "Your name"),
    card.pronouns ? h("p", { class: "card-pronouns" }, card.pronouns) : null,
  );
}

/** A static card face, used for the live preview while typing. */
export function cardPreview(card, { side = "front", displayId = null } = {}) {
  const el = h("div", { class: "name-card" }, header(card), face(card, side));
  el.style.setProperty("--accent", displayId ? accentColor(displayId) : "var(--coral-text)");
  const empty = side === "front" ? !card.workingOn && !card.askMeAbout : !card.howToTalk && !card.reachMe && !card.lookingFor;
  if (empty) el.append(h("p", { class: "card-empty muted" }, side === "front" ? "What you're working on shows here." : "How to talk to you shows here."));
  return el;
}

/** The interactive flip card with a visible Flip button. Returns { el, flip }. */
export function flipCard(card, { displayId = null } = {}) {
  let showingBack = false;

  const front = h("div", { class: "flip-face flip-front", id: "card-front" }, header(card), face(card, "front"),
    h("p", { class: "flip-hint muted", "aria-hidden": "true" }, "Tap to see how to talk to me"));
  const back = h("div", { class: "flip-face flip-back", id: "card-back" }, header(card), face(card, "back"));
  const inner = h("div", { class: "flip-inner" }, front, back);
  const scene = h("div", { class: "flip-scene name-card-flip" }, inner);
  scene.style.setProperty("--accent", displayId ? accentColor(displayId) : "var(--coral-text)");

  const flipBtn = h("button", { class: "btn btn-secondary", type: "button", "aria-controls": "card-front card-back" }, "Flip to the back");

  function render() {
    scene.classList.toggle("is-flipped", showingBack);
    scene.classList.toggle("no-motion", !motionOK());
    front.inert = showingBack;
    back.inert = !showingBack;
    front.setAttribute("aria-hidden", String(showingBack));
    back.setAttribute("aria-hidden", String(!showingBack));
    flipBtn.textContent = showingBack ? "Flip to the front" : "Flip to the back";
  }

  function flip() {
    showingBack = !showingBack;
    render();
    announce(showingBack ? "Showing the back: how to talk to me." : "Showing the front.");
  }

  // Tapping the card flips it too; the button is the discoverable, keyboard-friendly way.
  scene.addEventListener("click", flip);
  flipBtn.addEventListener("click", flip);
  render();

  return { el: h("div", { class: "flip-wrap" }, scene, flipBtn), flip };
}
