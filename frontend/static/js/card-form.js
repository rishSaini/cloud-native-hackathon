// Card fields and private room needs, shared by onboarding and "Edit card".
//
// Privacy: values stay in memory and go to the API only in a request body. Dash0's web SDK
// (0.18) records page views, fetch URLs, errors and web vitals; it has no session recording
// and doesn't read input values or request bodies, so card text can't reach it as long as it
// never goes into a URL or an error message.

import { FIELDS, cardPreview } from "./card-view.js";
import { h } from "./format.js";

export const TEMPLATES = [
  { id: "face", label: "Please face me when you talk", howToTalk: "Please face me when you talk." },
  { id: "time", label: "Give me time to finish my words", howToTalk: "Give me time to finish my words." },
  { id: "name", label: "Say your name when you walk up", howToTalk: "Say your name when you walk up." },
  { id: "one", label: "I do better one-on-one", howToTalk: "I do better one-on-one. Come say hi when it's quieter." },
  { id: "first", label: "This is my first conference", howToTalk: "This is my first conference. Say hi and tell me what you're working on." },
  { id: "blank", label: "Start from scratch", howToTalk: "" },
];

// Room and table needs. The backend maps these to opaque capability codes (cap-c1 …).
export const NEEDS = [
  { id: "captions", label: "Working captions" },
  { id: "quiet", label: "A quieter room or table" },
  { id: "step_free", label: "Step-free access" },
  { id: "lighting", label: "Good lighting" },
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
  return h("fieldset", { class: "needs" },
    h("legend", {}, "What helps you in a room or at a table"),
    h("p", { class: "hint", id: `${idPrefix}-needs-hint` }, "Private. Only used to pick rooms and tables that suit you. Nobody else sees this."),
    ...NEEDS.map((need) => {
      const id = `${idPrefix}-need-${need.id}`;
      const box = h("input", { type: "checkbox", id, name: "needs", value: need.id, "aria-describedby": `${idPrefix}-needs-hint` });
      box.checked = set.has(need.id);
      box.addEventListener("change", () => {
        if (box.checked) set.add(need.id); else set.delete(need.id);
        draft.needs = NEEDS.map((n) => n.id).filter((nid) => set.has(nid));
      });
      return h("div", { class: "check check-tile" }, box, h("label", { for: id }, need.label));
    }),
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
