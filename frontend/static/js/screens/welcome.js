// Welcome and onboarding: welcome → template → card → private needs → done.
// The steps live inside #/ (not separate routes), so nothing the person types can reach a URL.
// The draft is kept in memory only.

import { announce, focusScreen, motionOK } from "../a11y.js";
import { emptyCard, livePreview, needsFields, TEMPLATES } from "../card-form.js";
import { cardChat } from "../card-chat.js";
import { accentColor } from "../color.js";
import { h, twoTone } from "../format.js";
import { loadErrorView } from "../load-error.js";
import { loadMe, saveMyCard } from "../store.js";

const STEPS = ["template", "card", "needs"];
let draft = null; // survives navigating away and back during this visit

// A small constellation: five people joined into a group, one of them "you".
// Static, decorative markup (no user content).
const HERO_SVG = `
<svg viewBox="0 0 320 170" aria-hidden="true" focusable="false">
  <defs>
    <radialGradient id="hg-c" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#E8735A"/><stop offset="1" stop-color="#E8735A" stop-opacity="0"/></radialGradient>
    <radialGradient id="hg-t" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#2BA59A"/><stop offset="1" stop-color="#2BA59A" stop-opacity="0"/></radialGradient>
    <radialGradient id="hg-s" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#E2A93B"/><stop offset="1" stop-color="#E2A93B" stop-opacity="0"/></radialGradient>
    <radialGradient id="hg-p" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#9B6A99"/><stop offset="1" stop-color="#9B6A99" stop-opacity="0"/></radialGradient>
  </defs>
  <g class="hero-lines" fill="none" stroke="#C9B9A6" stroke-width="1.4" stroke-dasharray="3 5" stroke-linecap="round">
    <path d="M60 110 L128 52 L196 96 L262 44"/><path d="M128 52 L160 132 L196 96"/>
  </g>
  <g class="hero-dust" fill="#D9CBB8"><circle cx="24" cy="40" r="1.6"/><circle cx="300" cy="120" r="1.8"/><circle cx="230" cy="150" r="1.4"/><circle cx="96" cy="150" r="1.3"/><circle cx="286" cy="22" r="1.2"/><circle cx="40" cy="148" r="1.1"/></g>
  <circle class="tw t1" cx="60" cy="110" r="20" fill="url(#hg-t)"/>
  <circle class="tw t2" cx="128" cy="52" r="24" fill="url(#hg-s)"/>
  <circle class="tw t3" cx="196" cy="96" r="30" fill="url(#hg-c)"/>
  <circle class="tw t4" cx="262" cy="44" r="20" fill="url(#hg-p)"/>
  <circle class="tw t5" cx="160" cy="132" r="18" fill="url(#hg-t)"/>
  <text x="196" y="140" text-anchor="middle" class="hero-you">you</text>
</svg>`;

function heroArt() {
  const el = h("div", { class: "hero-art decor", "aria-hidden": "true" });
  el.innerHTML = HERO_SVG;
  return el;
}

function tileIcon(paths) {
  const el = h("span", { class: "tile-icon", "aria-hidden": "true" });
  el.innerHTML = `<svg viewBox="0 0 24 24" focusable="false">${paths}</svg>`; // static icon paths from card-form.js
  return el;
}

export default {
  title: "Welcome",
  async render(main) {
    const { card, error } = await loadMe();
    if (error) { main.append(loadErrorView()); return; }
    let step = "welcome";
    if (!draft) draft = emptyCard();

    const go = async (next) => {
      step = next;
      await paint();
      focusScreen(main);
    };

    function progress(name) {
      const n = STEPS.indexOf(name) + 1;
      return h("div", { class: "progress" },
        h("p", { class: "step-count" }, `Step ${n} of ${STEPS.length}`),
        h("div", { class: "progress-dots", "aria-hidden": "true" },
          STEPS.map((_, i) => h("span", { class: i < n ? "on" : "" }))),
      );
    }

    function backButton(to) {
      return h("button", { type: "button", class: "back-link", onclick: () => go(to) }, "← Back");
    }

    const screens = {
      welcome() {
        return h("section", { class: "welcome", "aria-labelledby": "step-h" },
          h("figure", { class: "welcome-visual" },
            heroArt(),
            h("figcaption", { class: "welcome-caption" }, "Your break table, as a constellation"),
          ),
          h("p", { class: "eyebrow" }, "KubeCon · Salt Lake City"),
          h("h1", { id: "step-h" }, twoTone("Find your talk. ", "Find your people.")),
          h("p", { class: "lede" }, "Here on your own? First conference? Not big on small talk? Same for lots of people here. Make a small card, and we'll find you a good talk and a friendly table at every break."),
          card
            ? h("a", { class: "btn btn-primary btn-block", href: "#/card" }, "See my card")
            : h("button", { type: "button", class: "btn btn-primary btn-block", onclick: () => go("template") }, "Make my card"),
          card
            ? h("p", { class: "welcome-note" }, h("a", { href: "#/talks" }, "Browse talks"))
            : h("p", { class: "muted welcome-note" }, "About 30 seconds. Only people at your table see your card."),
        );
      },

      template() {
        const tiles = TEMPLATES.map((t) =>
          h("li", {},
            h("button", {
              type: "button", class: "tile",
              onclick: () => {
                if (t.howToTalk || !draft.howToTalk) draft.howToTalk = t.howToTalk;
                go("card");
              },
            }, tileIcon(t.icon), h("span", { class: "tile-label" }, t.label), h("span", { class: "tile-arrow", "aria-hidden": "true" }, "→")),
          ));
        return h("section", { "aria-labelledby": "step-h" },
          backButton("welcome"),
          progress("template"),
          h("h1", { id: "step-h" }, twoTone("How do you like to ", "meet people?")),
          h("p", { class: "muted" }, "Pick whatever sounds most like you. Everyone here is meeting new people too."),
          h("ul", { class: "tiles" }, tiles),
        );
      },

      card() {
        // A friendly chat: fixed questions, answers as replies, the card growing on the side.
        const preview = livePreview(draft);
        const chat = cardChat(draft, { onChange: preview.update, onDone: () => go("needs") });
        const view = h("section", { class: "onboard-card" },
          backButton("template"),
          progress("card"),
          h("h1", { id: "step-h" }, twoTone("Let's make your ", "card.")),
          h("p", { class: "muted" }, "A few quick questions. Only your name is needed; skip anything else."),
          h("div", { class: "form-with-preview chat-layout" }, chat.el, preview.el),
        );
        // Start after the view is on screen, so focus and the announcement land on the first question.
        queueMicrotask(() => chat.start());
        return view;
      },

      needs() {
        const status = h("p", { class: "form-status", role: "status" });
        const submit = h("button", { type: "submit", class: "btn btn-primary btn-block" }, "Make my card");
        const form = h("form", { class: "stack", "aria-labelledby": "step-h" },
          needsFields(draft, { idPrefix: "ob" }),
          status,
          submit,
        );
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          submit.disabled = true;
          status.textContent = "Saving your card…";
          try {
            const { me } = await saveMyCard({ ...draft });
            draft = null;
            go("done");
            if (me?.displayId) announce(`Your card is ready. You're ${me.displayId}.`);
          } catch {
            status.textContent = "We couldn't save your card. Check your connection and try again.";
            submit.disabled = false;
          }
        });
        return h("section", {},
          backButton("card"),
          progress("needs"),
          h("h1", { id: "step-h" }, twoTone("What\u2019s your break-time ", "vibe?")),
          h("p", { class: "muted" }, "Pick any, or none. You can change this later."),
          form,
        );
      },

      async done() {
        const { me } = await loadMe();
        const id = me?.displayId || "a new star";
        const star = h("div", { class: `done-star decor ${motionOK() ? "animate" : ""}`, "aria-hidden": "true" });
        if (me?.displayId) star.style.setProperty("--star", accentColor(me.displayId));
        return h("section", { class: "done", "aria-labelledby": "step-h" },
          star,
          h("h1", { id: "step-h" }, twoTone("Your card is ", "ready.")),
          h("p", { class: "lede" }, "You're ", h("code", { class: "display-id" }, id), ". Look for yourself on the big screen."),
          h("a", { class: "btn btn-primary btn-block", href: "#/card" }, "See my card"),
          h("p", { class: "welcome-note" }, h("a", { href: "#/group" }, "Find me a break group")),
        );
      },
    };

    async function paint() {
      const view = await screens[step]();
      main.replaceChildren(view);
      document.title = step === "welcome" ? "Welcome · Affinity" : step === "done" ? "Card ready · Affinity" : `Make your card · Affinity`;
    }

    await paint();
  },
};
