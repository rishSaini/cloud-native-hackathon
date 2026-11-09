// Card creation as a friendly chat. The app asks fixed questions as chat bubbles; the person's
// answers appear as replies they can edit. There is no AI model here and nothing is sent
// anywhere while chatting: answers stay in the in-memory draft until "Make my card" saves
// them to PUT /api/card.
//
// Accessibility: each question is the real <label> of its input (so screen readers read it
// when focus lands there), every new question is also announced through the live region,
// the transcript is an ordered list, and every answer has an "Edit" button.

import { announce } from "./a11y.js";
import { h } from "./format.js";

// Fixed questions, in order. `ask` can use earlier answers (only to address the person by name).
const QUESTIONS = [
  { key: "name", required: true, max: 60, autocomplete: "given-name",
    ask: () => "Hi! I'm Affinity. What should people call you?",
    hint: "Just the name you'd like on your card." },
  { key: "pronouns", max: 30, list: ["she/her", "he/him", "they/them"],
    ask: (d) => `Nice to meet you, ${d.name}. What are your pronouns?`,
    hint: "Optional. You can skip this." },
  { key: "workingOn", max: 140,
    ask: () => "What are you working on these days?",
    hint: "One line is perfect, like \"making apps start faster\"." },
  { key: "askMeAbout", max: 140,
    ask: () => "What's something people could ask you about?",
    hint: "A topic you could happily talk about for a while." },
  { key: "howToTalk", max: 200, multiline: true,
    ask: () => "How do you like people to talk to you?",
    hint: "We filled this in from your pick. Change it however you like." },
  { key: "reachMe", max: 100,
    ask: () => "What's the best way to reach you after the conference?",
    hint: "Optional. A handle, or \"say hi at the break\"." },
  { key: "lookingFor", max: 140,
    ask: () => "Last one: what are you hoping to find here?",
    hint: "Optional. People, ideas, a job, or just good conversations." },
];

/** Builds the chat. onChange(draft) after each answer; onDone() when the person continues. */
export function cardChat(draft, { onChange, onDone } = {}) {
  let step = 0;          // index into QUESTIONS, or QUESTIONS.length for the consent turn
  let editing = false;   // true while re-answering an earlier question
  let reached = 0;       // how many questions have been answered so far

  const log = h("ol", { class: "chat-log", "aria-label": "Your answers so far" });
  const turn = h("div", { class: "chat-turn" });
  const el = h("div", { class: "chat" }, log, turn);

  const botBubble = (text, attrs = {}) => h("p", { class: "bubble bot", ...attrs }, h("span", { class: "bot-mark", "aria-hidden": "true" }, "a."), h("span", {}, text));

  function paintLog() {
    // Every answered question, except the one being re-answered right now.
    const answered = QUESTIONS.map((q, i) => ({ q, i })).filter(({ i }) => i < reached && !(editing && i === step));
    log.replaceChildren(...answered.map(({ q, i }) => {
      const value = (draft[q.key] || "").trim();
      return h("li", { class: "chat-pair" },
        botBubble(q.ask(draft)),
        h("div", { class: "bubble-row" },
          h("p", { class: `bubble me${value ? "" : " skipped"}` }, value || "Skipped"),
          h("button", {
            type: "button", class: "bubble-edit",
            onclick: () => { editing = true; step = i; paint(); },
          }, "Edit", h("span", { class: "visually-hidden" }, ` your answer to: ${q.ask(draft)}`)),
        ),
      );
    }));
  }

  function questionTurn(q) {
    const id = `chat-${q.key}`;
    const hintId = `${id}-hint`;
    const errId = `${id}-err`;
    const attrs = {
      id, name: q.key, class: "input chat-input", maxlength: q.max,
      autocomplete: q.autocomplete || "off",
      "aria-describedby": `${hintId} ${errId}`,
      required: q.required || null,
      "data-chat-key": q.key,
      "data-autofocus": "",
    };
    const input = q.multiline ? h("textarea", { ...attrs, rows: 3 }) : h("input", { ...attrs, type: "text", list: q.list ? `${id}-list` : null });
    input.value = draft[q.key] || "";
    input.addEventListener("input", () => {
      draft[q.key] = input.value;
      if (q.required && input.value.trim()) { err.hidden = true; input.removeAttribute("aria-invalid"); }
      onChange?.(draft);
    });
    const err = h("p", { class: "field-error", id: errId, hidden: true });
    const form = h("form", { class: "chat-form", novalidate: true },
      h("label", { for: id, class: "bubble bot" }, h("span", { class: "bot-mark", "aria-hidden": "true" }, "a."), h("span", {}, q.ask(draft))),
      h("p", { class: "chat-hint", id: hintId }, q.hint),
      h("div", { class: "chat-compose" },
        input,
        q.list ? h("datalist", { id: `${id}-list` }, q.list.map((v) => h("option", { value: v }))) : null,
        h("div", { class: "chat-actions" },
          q.required ? null : h("button", { type: "button", class: "btn btn-secondary", onclick: () => { draft[q.key] = ""; onChange?.(draft); advance(); } }, "Skip"),
          h("button", { type: "submit", class: "btn btn-primary" }, editing ? "Save" : "Send"),
        ),
      ),
      err,
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (q.required && !input.value.trim()) {
        err.textContent = "I'll need a name to put on your card. Any name you like is fine.";
        err.hidden = false;
        input.setAttribute("aria-invalid", "true");
        input.focus();
        announce(err.textContent);
        return;
      }
      draft[q.key] = input.value.trim();
      onChange?.(draft);
      advance();
    });
    return { form, input };
  }

  function consentTurn() {
    const box = h("input", { type: "checkbox", id: "chat-matching" });
    box.checked = draft.allowMatching !== false;
    box.addEventListener("change", () => { draft.allowMatching = box.checked; onChange?.(draft); });
    const next = h("button", { type: "button", class: "btn btn-primary", "data-chat-next": "", "data-autofocus": "", onclick: () => onDone?.() }, "Looks good, next");
    const wrap = h("div", { class: "chat-form" },
      botBubble(`Lovely, ${draft.name}. Your card is on the right. One more thing:`, { id: "chat-final" }),
      h("div", { class: "check check-tile chat-consent" },
        box,
        h("label", { for: "chat-matching" }, "Use what I'm working on, ask me about and looking for to find me talks and people",
          h("span", { class: "hint" }, "Only those three lines, under a random ID. Your name never is.")),
      ),
      h("div", { class: "chat-actions" }, next),
    );
    return { form: wrap, input: next };
  }

  function advance() {
    if (editing) { editing = false; step = reached; }
    else { step += 1; reached = Math.max(reached, step); }
    paint();
  }

  function paint() {
    paintLog();
    const t = step < QUESTIONS.length ? questionTurn(QUESTIONS[step]) : consentTurn();
    turn.replaceChildren(t.form);
    const text = step < QUESTIONS.length ? QUESTIONS[step].ask(draft) : `Lovely, ${draft.name}. Your card is ready to look at.`;
    announce(text);
    t.input.focus({ preventScroll: true });
    t.form.scrollIntoView?.({ block: "nearest" });
  }

  return { el, start: paint };
}
