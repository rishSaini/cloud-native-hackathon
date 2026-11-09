// Grow: helping people get better at conversations, so they need this app less over time.
//
// - Fading support: the suggested opener goes from a full question (level 1), to a hint you
//   phrase yourself (2), to "you've got this" (3+).
// - Everyone gets a turn: a gentle round where each person has about a minute, every phone
//   shows whose turn it is, and a rotating host keeps it fair. No microphone, no recording.
// - A 30-second private reflection after each break; the answers adjust your next challenge.
//   Only an anonymous "felt heard" share leaves the phone.

import { announce, motionOK } from "./a11y.js";
import { api } from "./api.js";
import { h } from "./format.js";

export const QUESTION_COACH = [
  { title: "Open questions invite stories", items: ["What got you into …?", "How did you end up working on …?", "What's the hardest part of …?"] },
  { title: "Follow-ups show you're listening", items: ["What happened next?", "How did you figure that out?", "What would you do differently?"] },
  { title: "Bring someone in", items: ["Priya, you mentioned CI earlier. Does that match what you've seen?", "Has anyone tried that?"] },
  { title: "Share a little first", items: ["I'm stuck on …, has that happened to you?", "I'm new to this, so tell me if I've got it wrong."] },
];

/** The opener, with support that fades as you grow. */
export function openerView(group, level = 1) {
  const topic = group.members.find((m) => m.askMeAbout)?.askMeAbout || group.members[0]?.workingOn || "what they're working on";
  const who = group.members.find((m) => m.askMeAbout)?.name || group.members[0]?.name || "someone";
  if (level <= 1 && group.opener) {
    return h("p", { class: "opener" }, h("span", { class: "opener-label" }, "Try asking: "), group.opener);
  }
  if (level === 2) {
    return h("p", { class: "opener hint" }, h("span", { class: "opener-label" }, "Your turn to phrase it: "), `${who} can tell you about ${topic}. How would you ask?`);
  }
  return h("p", { class: "opener free" }, h("span", { class: "opener-label" }, "You've got this. "), "What do you want to know about them? ", h("a", { href: "#/grow" }, "Question ideas"));
}

const TURN_MS = 60000;
const ROUND_PROMPTS = ["One thing you're working on", "Something that surprised you today", "A question you're hoping someone can answer"];

/** "Everyone gets a turn": a gentle round with a rotating host. Local to this phone for now. */
export function turnRound(group, { myName = "You" } = {}) {
  const people = [myName, ...group.members.map((m) => m.name)];
  // The host rotates by group so it isn't always the same kind of person leading.
  const hostIndex = [...group.id].reduce((a, c) => a + c.charCodeAt(0), 0) % people.length;
  // The round goes around the table starting with the host: step 0 is the host, then the next
  // person, and so on. `step === null` means no round is running.
  let round = 0, step = null, timer = null;
  const n = people.length;
  const at = (k) => (hostIndex + k) % n;

  const who = h("p", { class: "turn-who" });
  const ring = h("div", { class: "turn-ring", "aria-hidden": "true" });
  const prompt = h("p", { class: "turn-prompt" });
  const pass = h("button", { type: "button", class: "btn btn-primary" }, "Pass the turn");
  const start = h("button", { type: "button", class: "btn btn-secondary" }, "Start a round");
  const order = h("ol", { class: "turn-order", "aria-label": "Turn order" });

  function paint() {
    const active = step !== null;
    const current = active ? at(step) : -1;
    prompt.textContent = `Round ${round + 1}: ${ROUND_PROMPTS[round % ROUND_PROMPTS.length]}`;
    who.textContent = active
      ? (people[current] === myName ? "Your turn. Take your time." : `${people[current]}'s turn`)
      : round > 0 ? "Everyone had a turn. Start another round?" : `${people[hostIndex]} is hosting this break`;
    // Listed in speaking order, host first.
    order.replaceChildren(...Array.from({ length: n }, (_, k) => {
      const i = at(k);
      const cls = active ? (k === step ? "now" : k < step ? "done" : "") : "";
      return h("li", { class: cls, "aria-current": active && k === step ? "true" : null }, people[i], i === hostIndex ? h("span", { class: "host-tag" }, " · host") : null);
    }));
    pass.hidden = !active;
    start.hidden = active;
    if (active && motionOK()) {
      ring.style.animation = "none";
      void ring.offsetWidth;
      ring.style.animation = `turn-ring ${TURN_MS}ms linear forwards`;
    } else ring.style.animation = "none";
  }

  function speakerChanged() {
    const name = people[at(step)];
    announce(name === myName ? "Your turn." : `${name}'s turn.`);
    clearTimeout(timer);
    timer = setTimeout(() => { who.textContent = `${who.textContent} · about a minute`; }, TURN_MS);
  }

  function next() {
    if (step === null) return;
    step += 1;
    if (step >= n) {
      step = null; round += 1;
      clearTimeout(timer);
      announce("Round complete. Everyone had a turn.");
    } else speakerChanged();
    paint();
  }

  start.addEventListener("click", () => { step = 0; speakerChanged(); paint(); });
  pass.addEventListener("click", next);

  const el = h("section", { class: "card turn-card", "aria-labelledby": "turn-h" },
    h("p", { class: "section-eyebrow" }, "Everyone gets a turn"),
    h("h2", { id: "turn-h", class: "visually-hidden" }, "Everyone gets a turn"),
    h("div", { class: "turn-head" }, ring, h("div", {}, who, prompt)),
    order,
    h("p", { class: "muted turn-note" }, "About a minute each, then pass it on. Nothing is recorded."),
    h("div", { class: "turn-actions" }, start, pass),
  );
  paint();
  return { el, cleanup: () => clearTimeout(timer), hostIsMe: () => people[hostIndex] === myName };
}

/** The 30-second private reflection after a break. onDone(result) gets the API result. */
export function openReflection({ groupId, hosted = false, onDone } = {}) {
  const answers = { comfort: null, askedQuestion: false, sharedWork: false, hosted, everyoneTurn: null, spokeEnough: null };
  const status = h("p", { class: "form-status", role: "status" });

  const scale = h("div", { class: "comfort-scale", role: "radiogroup", "aria-labelledby": "rf-comfort" },
    [1, 2, 3, 4, 5].map((n) => {
      const id = `rf-c${n}`;
      const input = h("input", { type: "radio", name: "rf-comfort", id, value: String(n), class: "setting-radio" });
      input.addEventListener("change", () => { answers.comfort = n; });
      const words = { 1: "Rough", 2: "Uneasy", 3: "Okay", 4: "Good", 5: "Great" };
      return h("div", { class: "scale-option" }, input, h("label", { for: id }, h("span", { class: "scale-num" }, String(n)), h("span", { class: "scale-word" }, words[n])));
    }));

  const check = (key, label) => {
    const id = `rf-${key}`;
    const box = h("input", { type: "checkbox", id });
    box.addEventListener("change", () => { answers[key] = box.checked; });
    return h("div", { class: "check check-tile" }, box, h("label", { for: id }, label));
  };
  const choice = (key, legend, opts) => h("fieldset", { class: "setting-group" },
    h("legend", {}, legend),
    h("div", { class: "pill-options" }, opts.map(([value, label]) => {
      const id = `rf-${key}-${value}`;
      const input = h("input", { type: "radio", name: `rf-${key}`, id, value, class: "setting-radio" });
      input.addEventListener("change", () => { answers[key] = value; });
      return h("div", { class: "pill-option" }, input, h("label", { for: id }, label));
    })));

  const send = h("button", { type: "submit", class: "btn btn-primary" }, "Save reflection");
  const form = h("form", { class: "stack" },
    h("fieldset", { class: "setting-group" }, h("legend", { id: "rf-comfort" }, "How comfortable did that feel?"), scale),
    h("fieldset", { class: "setting-group" }, h("legend", {}, "Did you…"),
      h("div", { class: "stack" }, check("askedQuestion", "Ask someone a question"), check("sharedWork", "Share what you're working on"))),
    choice("everyoneTurn", "Did everyone get a turn to talk?", [["yes", "Yes"], ["mostly", "Mostly"], ["no", "No"]]),
    choice("spokeEnough", "Did you get to say as much as you wanted?", [["yes", "Yes"], ["no", "Not really"]]),
    h("p", { class: "muted" }, "Private to you. Only an anonymous \"felt heard\" number is shared, never your answers."),
    status,
    h("div", { class: "dialog-actions" }, h("button", { type: "button", class: "btn btn-secondary", onclick: () => d.close() }, "Skip"), send),
  );
  const d = h("dialog", { class: "dialog reflect-dialog", "aria-labelledby": "rf-h" }, h("h2", { id: "rf-h" }, "How did that go?"), form);
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!answers.comfort) { status.textContent = "Pick how comfortable it felt, from 1 to 5."; d.querySelector("#rf-c3")?.focus(); return; }
    send.disabled = true;
    status.textContent = "Saving…";
    try {
      const res = await api.reflect({ groupId, ...answers });
      const msg = res.move === "up"
        ? "That was brave. Next time we'll nudge you one step further."
        : res.move === "gentler"
          ? "Thanks for being honest. We'll keep the next one gentler. That's how confidence grows."
          : "Thanks. Every conversation counts.";
      form.replaceWith(h("div", { class: "stack" },
        h("p", { class: "reflect-msg" }, msg),
        res.wins?.length ? h("ul", { class: "win-list" }, res.wins.map((w) => h("li", {}, "✦ ", w))) : null,
        res.growth?.nextChallenge ? h("p", { class: "next-challenge" }, h("strong", {}, "Next challenge: "), res.growth.nextChallenge.title) : null,
        h("div", { class: "dialog-actions" },
          h("a", { class: "btn btn-secondary", href: "#/grow", onclick: () => d.close() }, "See your growth"),
          h("button", { type: "button", class: "btn btn-primary", autofocus: true, onclick: () => d.close() }, "Done")),
      ));
      announce(msg);
      onDone?.(res);
    } catch {
      status.textContent = "We couldn't save that. Please try again.";
      send.disabled = false;
    }
  });
}
