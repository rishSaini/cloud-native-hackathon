// The Comfort dial: energy and sensory capacity change through a 3-day event, so this is a
// quick, changeable setting rather than a fixed form field. It's saved on the card
// (`comfort`) so matching can use it, and it changes a few things on this phone:
//   low-sensory  → turns on calm mode (and turns it off again if the dial turned it on)
//   recharge     → your group sees "Recharging · listening only", no conversation expected

import { announce, getPrefs, setPrefs } from "./a11y.js";
import { h } from "./format.js";
import { currentCard, saveMyCard } from "./store.js";

export const COMFORT = [
  { id: "high", label: "High energy", short: "Up for anything", detail: "Bigger break groups and lively talks.", icon: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>' },
  { id: "steady", label: "Steady", short: "The usual", detail: "A good mix. This is the default.", icon: '<circle cx="12" cy="12" r="8"/><path d="M8 12h8"/>' },
  { id: "low", label: "Low key", short: "Quiet please", detail: "Quieter rooms, smaller tables, and calmer colors on your phone. Private: your group isn't told.", icon: '<path d="M5 19c0-7 5-12 14-14-1 9-6 14-13 14"/><path d="M5 19c3-3 6-5 9-6"/>' },
  { id: "recharge", label: "Recharging", short: "Listening only", detail: "You keep your seat. Your group sees: listening only, no conversation expected.", icon: '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10.5v3M6.5 10v4"/>' },
];

export const comfortOf = (card) => card?.comfort || "steady";

let calmFromDial = false;

function applyLocal(value) {
  const prefs = getPrefs();
  if (value === "low" && !prefs.calm) { setPrefs({ calm: true }); calmFromDial = true; }
  if (value !== "low" && calmFromDial) { setPrefs({ calm: false }); calmFromDial = false; }
}

/** The dial as a radio group. compact = one-line version for Now. */
export function comfortDial({ compact = false, idPrefix = "comfort", onChange } = {}) {
  let value = comfortOf(currentCard());
  const status = h("p", { class: "comfort-status", role: "status" });
  const detail = h("p", { class: "comfort-detail" });

  const describe = () => {
    const c = COMFORT.find((x) => x.id === value);
    detail.textContent = c.detail;
  };

  const options = COMFORT.map((c) => {
    const id = `${idPrefix}-${c.id}`;
    const input = h("input", { type: "radio", name: `${idPrefix}-dial`, id, value: c.id, class: "comfort-radio" });
    input.checked = c.id === value;
    input.addEventListener("change", async () => {
      if (!input.checked) return;
      const before = value;
      value = c.id;
      describe();
      status.textContent = "Saving…";
      try {
        const card = currentCard();
        if (card) await saveMyCard({ ...card, comfort: value });
        applyLocal(value);
        status.textContent = value === "low" ? "Saved. Calm mode is on." : "Saved.";
        announce(`Comfort set to ${c.label}.`);
        onChange?.(value);
      } catch {
        value = before;
        status.textContent = "We couldn't save that. Please try again.";
        container.querySelector(`#${idPrefix}-${before}`).checked = true;
        describe();
      }
    });
    const icon = h("span", { class: "comfort-icon", "aria-hidden": "true" });
    icon.innerHTML = `<svg viewBox="0 0 24 24" focusable="false">${c.icon}</svg>`; // static icon markup
    return h("div", { class: "comfort-option" },
      input,
      h("label", { for: id }, icon, h("span", { class: "comfort-label" }, c.label), compact ? null : h("span", { class: "comfort-short" }, c.short)),
    );
  });

  const container = h("fieldset", { class: `comfort${compact ? " compact" : ""}` },
    h("legend", {}, compact ? "How are you feeling?" : "How are you feeling right now?"),
    h("div", { class: "comfort-options" }, options),
    compact ? null : detail,
    status,
  );
  describe();
  return container;
}

/** A pill for a group member who is recharging. Only "recharge" is shared with the group:
 *  low-sensory stays private, like other needs. */
export function comfortPill(comfort) {
  if (comfort === "recharge") return h("p", { class: "comfort-pill recharge" }, "Recharging · listening only, no conversation expected");
  return null;
}
