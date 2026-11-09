// Settings: calm mode, reduced motion, text size, human or kubectl mode, delete my card and
// data, and a plain-language privacy note. Display preferences are the only thing this
// phone stores (localStorage "affinity.prefs"); they never include card text.

import { announce, getPrefs, onPrefsChange, setPrefs, textSizes } from "../a11y.js";
import { h } from "../format.js";
import { deleteMyCard, loadMe } from "../store.js";
import { confirmDelete } from "./card.js";

const systemReduce = window.matchMedia?.("(prefers-reduced-motion: reduce)");
const SIZE_LABELS = { default: "Default", large: "Large", larger: "Larger" };

function radioGroup({ name, legend, hint, options, value, onChange }) {
  return h("fieldset", { class: "setting-group" },
    h("legend", {}, legend),
    hint ? h("p", { class: "hint" }, hint) : null,
    h("div", { class: "setting-options" }, options.map((o) => {
      const id = `${name}-${o.value}`;
      const input = h("input", { type: "radio", name, id, value: o.value, class: "setting-radio" });
      input.checked = o.value === value;
      input.addEventListener("change", () => { if (input.checked) onChange(o.value); });
      return h("div", { class: "setting-option" },
        input,
        h("label", { for: id }, h("span", { class: "setting-option-label" }, o.label), o.detail ? h("span", { class: "setting-option-detail" }, o.detail) : null),
      );
    })),
  );
}

export default {
  title: "Settings",
  async render(main, { navigate }) {
    // Display settings work even if the card can't load; only the delete section depends on it.
    let { card, error } = await loadMe();
    const region = h("div", { class: "stack settings" });
    main.append(h("h1", { class: "screen-title" }, "Settings"), region);

    function paint() {
      const prefs = getPrefs();
      const focusedId = document.activeElement?.id;

      const calm = h("input", { type: "checkbox", id: "calm", role: "switch", class: "switch-input" });
      calm.checked = !!prefs.calm;
      calm.addEventListener("change", () => {
        setPrefs({ calm: calm.checked });
        announce(calm.checked ? "Calm mode on." : "Calm mode off.");
      });

      const systemWord = systemReduce?.matches ? "reduce motion" : "allow motion";
      const motionValue = prefs.reduceMotion == null ? "system" : prefs.reduceMotion ? "reduce" : "allow";

      region.replaceChildren(
        h("section", { class: "card stack", "aria-labelledby": "display-h" },
          h("h2", { id: "display-h" }, "Display"),
          h("div", { class: "switch" },
            calm,
            h("label", { for: "calm" }, "Calm mode",
              h("span", { class: "hint" }, "Softer colors, no animation, no sounds, and fewer things on screen.")),
          ),
          radioGroup({
            name: "motion", legend: "Motion",
            hint: calm.checked ? "Calm mode already turns all motion off." : null,
            value: motionValue,
            options: [
              { value: "system", label: "Follow my device", detail: `Your device says: ${systemWord}` },
              { value: "reduce", label: "Reduce motion", detail: "Things appear in place, cards crossfade" },
              { value: "allow", label: "Allow motion", detail: "Gentle glides and a card flip" },
            ],
            onChange: (v) => {
              setPrefs({ reduceMotion: v === "system" ? null : v === "reduce" });
              announce(v === "system" ? "Motion follows your device." : v === "reduce" ? "Motion reduced." : "Motion allowed.");
            },
          }),
          radioGroup({
            name: "text-size", legend: "Text size",
            hint: "Your browser's own text size and zoom still apply on top.",
            value: prefs.textSize || "default",
            options: textSizes.map((s) => ({ value: s, label: SIZE_LABELS[s] })),
            onChange: (v) => { setPrefs({ textSize: v }); announce(`Text size ${SIZE_LABELS[v]}.`); },
          }),
          h("p", { class: "text-preview", "aria-hidden": "true" }, "Find your talk. Find your people."),
        ),

        h("section", { class: "card stack", "aria-labelledby": "mode-h" },
          h("h2", { id: "mode-h" }, "How things are shown"),
          radioGroup({
            name: "mode", legend: "Mode",
            value: prefs.kubectl ? "kubectl" : "human",
            options: [
              { value: "human", label: "Human", detail: "\"You're in Room 251, 2:30 PM\"" },
              { value: "kubectl", label: "kubectl", detail: "attendee-7f3k   Running   room-251" },
            ],
            onChange: (v) => { setPrefs({ kubectl: v === "kubectl" }); announce(v === "kubectl" ? "kubectl mode on." : "Human mode on."); },
          }),
          h("p", { class: "hint" }, "kubectl mode is just for fun. It shows the same things as Kubernetes would, with random IDs only, never your card or your needs."),
        ),

        h("section", { class: "card stack", "aria-labelledby": "privacy-h" },
          h("h2", { id: "privacy-h" }, "Your privacy"),
          h("ul", { class: "privacy-list" },
            h("li", {}, "Your card is encrypted. Only people in your break group, or someone you share it with, can read it."),
            h("li", {}, "What helps you in a room stays private. It's only used to pick rooms and tables, never shown to anyone."),
            h("li", {}, "The big screen shows a random ID like attendee-7f3k, never your name."),
            h("li", {}, "This phone keeps only these display settings. Your card isn't stored on it."),
          ),
        ),

        h("section", { class: "card stack danger-zone", "aria-labelledby": "delete-h" },
          h("h2", { id: "delete-h" }, "Delete my card and data"),
          h("p", { class: "muted" }, error
            ? "We couldn't check your card right now. Your data is safe. Check your connection and try again."
            : card
              ? "This removes your card, your private needs, your groups and any links you've shared. It can't be undone, but you can make a new card any time."
              : "You don't have a card right now, so there's nothing to delete."),
          error ? h("button", { type: "button", class: "btn btn-secondary btn-block", "data-key": "retry", onclick: retryLoad }, "Try again") : null,
          card && !error ? h("button", { type: "button", class: "btn btn-danger btn-block", onclick: () => dialog.showModal() }, "Delete my card and data") : null,
          status,
        ),
      );
      if (focusedId) document.getElementById(focusedId)?.focus();
    }

    const status = h("p", { class: "form-status", role: "status" });
    async function retryLoad() {
      ({ card, error } = await loadMe({ force: true }));
      paint();
    }
    const dialog = confirmDelete(async () => {
      status.textContent = "Deleting…";
      try {
        await deleteMyCard();
        announce("Your card and data were deleted.");
        navigate("/");
      } catch {
        status.textContent = "We couldn't delete your data. Please try again.";
      }
    });
    main.append(dialog);

    paint();
    const unsub = onPrefsChange(() => paint());
    const onSystem = () => paint();
    systemReduce?.addEventListener?.("change", onSystem);
    return () => { unsub(); systemReduce?.removeEventListener?.("change", onSystem); };
  },
};
