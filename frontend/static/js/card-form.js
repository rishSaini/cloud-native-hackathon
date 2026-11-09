// Card fields and private room needs, shared by onboarding and "Edit card".
//
// Privacy: values stay in memory and go to the API only in a request body. Dash0's web SDK
// (0.18) records page views, fetch URLs, errors and web vitals; it has no session recording
// and doesn't read input values or request bodies, so card text can't reach it as long as it
// never goes into a URL or an error message.

import { FIELDS, cardPreview } from "./card-view.js";
import { h } from "./format.js";

// Each template has a small line icon (static SVG path data, decorative).
// Templates for everyone: people here alone, first-timers, people who find small talk hard,
// people speaking a second language, and people with access needs.
export const TEMPLATES = [
  { id: "hi", label: "Come say hi, I love meeting people", howToTalk: "Come say hi! I love meeting new people. Ask me what I'm working on.", icon: '<path d="M7 11.5V6.5a1.5 1.5 0 0 1 3 0v4M10 10V5a1.5 1.5 0 0 1 3 0v5M13 10V6a1.5 1.5 0 0 1 3 0v6c0 4-2.5 7-6 7-2.5 0-4-1.5-5.5-4L3 12a1.5 1.5 0 0 1 2.5-1.5L7 12"/>' },
  { id: "alone", label: "I'm here on my own", howToTalk: "I'm here on my own, so please say hi! Ask me what I'm working on.", icon: '<circle cx="12" cy="8" r="3.2"/><path d="M5.5 20c.9-3.6 3.5-5.5 6.5-5.5s5.6 1.9 6.5 5.5"/>' },
  { id: "smalltalk", label: "Skip the small talk, ask about my work", howToTalk: "Small talk isn't my thing. Ask me about my work and I'll talk for ages.", icon: '<path d="M4 6.5h16v9H9l-4 3.5v-3.5H4z"/><path d="M8 10h8M8 12.8h5"/>' },
  { id: "warmup", label: "I'm shy at first, I warm up", howToTalk: "I'm quiet at first but I warm up. Give me a minute and a good question.", icon: '<path d="M12 21c4-2.5 7-6 7-10a7 7 0 0 0-14 0c0 4 3 7.5 7 10z"/><path d="M9.5 11.5c.7.8 1.5 1.2 2.5 1.2s1.8-.4 2.5-1.2"/>' },
  { id: "one", label: "I do better one-on-one", howToTalk: "I do better one-on-one. Come say hi when it's quieter.", icon: '<circle cx="8" cy="9" r="2.6"/><circle cx="16" cy="9" r="2.6"/><path d="M3.5 18.5c.8-2.6 2.6-3.8 4.5-3.8s3.7 1.2 4.5 3.8M11.5 18.5c.8-2.6 2.6-3.8 4.5-3.8s3.7 1.2 4.5 3.8"/>' },
  { id: "language", label: "English isn't my first language", howToTalk: "English isn't my first language, so please speak a little slower. I'm happy to repeat myself too.", icon: '<path d="M4 5h9M8.5 5v2c0 4-2.5 7-5 8M6 10c1.2 2 3.2 3.6 5.5 4.3"/><path d="M13 20l4-9 4 9M14.5 17h5"/>' },
  { id: "first", label: "This is my first conference", howToTalk: "This is my first conference. Say hi and tell me what you're working on.", icon: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>' },
  { id: "blank", label: "Something else, I'll write my own", howToTalk: "", icon: '<path d="M4 20l1-4.5L15.5 5a2.1 2.1 0 0 1 3 3L8 18.5zM13.5 7l3 3"/>' },
];

// Room and table needs. The backend maps these to opaque capability codes (cap-c1 …).
// Things that help people feel comfortable in a room or at a table. Some are access needs,
// some are preferences; all are private and only used for placement.
// Break-time preferences everyone has, then optional access needs (shown collapsed).
// All private; used only for placement.
export const NEEDS = [
  { id: "small_group", label: "Smaller groups (2 or 3 people)" },
  { id: "quiet", label: "A quieter spot" },
  { id: "less_crowded", label: "Not too crowded" },
  { id: "seating", label: "Somewhere to sit" },
  { id: "captions", label: "Working captions", access: true },
  { id: "step_free", label: "Step-free access", access: true },
  { id: "lighting", label: "Good lighting", access: true },
];

const SPECS = [
  { key: "name", required: true, max: 60, autocomplete: "given-name" },
  { key: "pronouns", max: 30, hint: "Optional. For example she/her, he/him or they/them.", list: ["she/her", "he/him", "they/them"] },
  { key: "workingOn", max: 140, hint: "One line, like \"making apps start faster\"." },
  { key: "askMeAbout", max: 140 },
  { key: "howToTalk", max: 200, multiline: true, hint: "Say what helps. You never need to say why." },
  { key: "reachMe", max: 100, hint: "For example \"say hi at the break\" or a handle." },
  { key: "lookingFor", max: 140, hint: "For example \"people new to platform teams\"." },
];

export const emptyCard = () => ({
  name: "", pronouns: "", workingOn: "", askMeAbout: "", howToTalk: "", reachMe: "", lookingFor: "",
  needs: [], allowMatching: true,
});

/** Text fields with a live preview. onChange is called with the updated draft. */
export function cardFields(draft, { onChange, idPrefix = "card" } = {}) {
  const inputs = {};
  const fields = SPECS.map((spec) => {
    const id = `${idPrefix}-${spec.key}`;
    const hintId = spec.hint ? `${id}-hint` : null;
    const errId = `${id}-err`;
    const attrs = {
      id, name: spec.key, class: "input", maxlength: spec.max,
      autocomplete: spec.autocomplete || "off",
      "aria-describedby": [hintId, spec.required ? errId : null].filter(Boolean).join(" ") || null,
      required: spec.required || null,
    };
    let input;
    if (spec.multiline) {
      input = h("textarea", { ...attrs, rows: 3 });
    } else {
      input = h("input", { ...attrs, type: "text", list: spec.list ? `${id}-list` : null });
    }
    input.value = draft[spec.key] || "";
    input.addEventListener("input", () => {
      draft[spec.key] = input.value;
      if (spec.required && input.value.trim()) clearError(input, errId);
      onChange?.(draft);
    });
    inputs[spec.key] = input;
    return h("div", { class: "field" },
      h("label", { for: id }, FIELDS[spec.key], spec.required ? h("span", { class: "req" }, " (required)") : null),
      spec.hint ? h("span", { class: "hint", id: hintId }, spec.hint) : null,
      input,
      spec.list ? h("datalist", { id: `${id}-list` }, spec.list.map((v) => h("option", { value: v }))) : null,
      spec.required ? h("p", { class: "field-error", id: errId, hidden: true }) : null,
    );
  });

  const matching = h("input", { type: "checkbox", id: `${idPrefix}-matching`, name: "allowMatching" });
  matching.checked = draft.allowMatching !== false;
  matching.addEventListener("change", () => { draft.allowMatching = matching.checked; onChange?.(draft); });
  const consent = h("div", { class: "check" },
    matching,
    h("label", { for: `${idPrefix}-matching` },
      "Use what I'm working on, ask me about and looking for to find me talks and people",
      h("span", { class: "hint" }, "Only those three lines are used for matching, under a random ID. Your name never is."),
    ),
  );

  /** Returns true when valid; otherwise shows the error and focuses the field. */
  function validate() {
    const name = inputs.name;
    if (!name.value.trim()) {
      showError(name, `${idPrefix}-name-err`, "Please add your name, or the name you'd like people to use.");
      name.focus();
      return false;
    }
    return true;
  }

  return { el: h("div", { class: "stack" }, ...fields, consent), validate, inputs };
}

function showError(input, errId, message) {
  const err = document.getElementById(errId);
  input.setAttribute("aria-invalid", "true");
  if (err) { err.textContent = message; err.hidden = false; }
}
function clearError(input, errId) {
  const err = document.getElementById(errId);
  input.removeAttribute("aria-invalid");
  if (err) { err.textContent = ""; err.hidden = true; }
}

/** Private needs checkboxes in a fieldset. */
export function needsFields(draft, { idPrefix = "card" } = {}) {
  const set = new Set(draft.needs || []);
  const box = (need) => {
    const id = `${idPrefix}-need-${need.id}`;
    const input = h("input", { type: "checkbox", id, name: "needs", value: need.id, "aria-describedby": `${idPrefix}-needs-hint` });
    input.checked = set.has(need.id);
    input.addEventListener("change", () => {
      if (input.checked) set.add(need.id); else set.delete(need.id);
      draft.needs = NEEDS.map((n) => n.id).filter((nid) => set.has(nid));
    });
    return h("div", { class: "check check-tile" }, input, h("label", { for: id }, need.label));
  };
  const access = NEEDS.filter((n) => n.access);
  const more = h("details", { class: "more-needs" },
    h("summary", {}, "Anything else that helps? (optional)"),
    h("div", { class: "needs" }, access.map(box)),
  );
  if (access.some((n) => set.has(n.id))) more.open = true;
  return h("fieldset", { class: "needs" },
    h("legend", {}, "Your break-time vibe"),
    h("p", { class: "hint", id: `${idPrefix}-needs-hint` }, "Private. We only use this to pick rooms and tables that suit you."),
    ...NEEDS.filter((n) => !n.access).map(box),
    more,
  );
}

/** A live preview that re-renders as the draft changes. Hidden from screen readers: the form already says it all. */
export function livePreview(draft) {
  const wrap = h("div", { class: "preview", "aria-hidden": "true" },
    h("p", { class: "preview-label" }, "Preview"),
  );
  const slot = h("div", { class: "preview-cards" });
  wrap.append(slot);
  const update = () => slot.replaceChildren(cardPreview(draft, { side: "front" }), cardPreview(draft, { side: "back" }));
  update();
  return { el: wrap, update };
}
