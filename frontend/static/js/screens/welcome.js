// Welcome and onboarding: welcome → template → card → private needs → done.
// The steps live inside #/ (not separate routes), so nothing the person types can reach a URL.
// The draft is kept in memory only.

import { announce, focusScreen, motionOK } from "../a11y.js";
import { cardFields, emptyCard, livePreview, needsFields, TEMPLATES } from "../card-form.js";
import { starColor } from "../color.js";
import { h } from "../format.js";
import { loadMe, saveMyCard } from "../store.js";

const STEPS = ["template", "card", "needs"];
let draft = null; // survives navigating away and back during this visit

export default {
  title: "Welcome",
  async render(main) {
    const { card } = await loadMe();
    let step = "welcome";
    if (!draft) draft = emptyCard();

    const go = async (next) => {
      step = next;
      await paint();
      focusScreen(main);
    };

    function progress(name) {
      const n = STEPS.indexOf(name) + 1;
      return h("p", { class: "step-count" }, `Step ${n} of ${STEPS.length}`);
    }

    function backButton(to) {
      return h("button", { type: "button", class: "back-link", onclick: () => go(to) }, "← Back");
    }

    const screens = {
      welcome() {
        return h("section", { class: "welcome", "aria-labelledby": "step-h" },
          h("div", { class: "welcome-sky decor", "aria-hidden": "true" },
            h("span", { class: "welcome-star s1" }), h("span", { class: "welcome-star s2" }), h("span", { class: "welcome-star s3" }),
          ),
          h("h1", { id: "step-h" }, "Find your talk. Find your people."),
          h("p", { class: "lede" }, "Make a small card about what you're working on and how people should talk to you. We'll find you a good talk and a friendly table at every break."),
          card
            ? h("a", { class: "btn btn-primary btn-block", href: "#/now" }, "Go to now")
            : h("button", { type: "button", class: "btn btn-primary btn-block", onclick: () => go("template") }, "Make my card"),
          card
            ? h("p", { class: "welcome-note" }, h("a", { href: "#/card" }, "See my card"))
            : h("p", { class: "muted welcome-note" }, "It takes about 30 seconds. Your card is private: only people in your group see it."),
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
            }, t.label),
          ));
        return h("section", { "aria-labelledby": "step-h" },
          backButton("welcome"),
          progress("template"),
          h("h1", { id: "step-h" }, "How should people talk to you?"),
          h("p", { class: "muted" }, "Pick one to start. You can change the words next."),
          h("ul", { class: "tiles" }, tiles),
        );
      },

      card() {
        const preview = livePreview(draft);
        const fields = cardFields(draft, { onChange: preview.update, idPrefix: "ob" });
        const form = h("form", { class: "stack", novalidate: true, "aria-labelledby": "step-h" },
          fields.el,
          h("button", { type: "submit", class: "btn btn-primary btn-block" }, "Next"),
        );
        form.addEventListener("submit", (e) => {
          e.preventDefault();
          if (fields.validate()) go("needs");
        });
        return h("section", { class: "onboard-card" },
          backButton("template"),
          progress("card"),
          h("h1", { id: "step-h" }, "Your card"),
          h("p", { class: "muted" }, "Only your name is required. The preview shows what your group will see."),
          h("div", { class: "form-with-preview" }, form, preview.el),
        );
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
          h("h1", { id: "step-h" }, "What helps you?"),
          h("p", { class: "muted" }, "Tick anything that helps, or none. You can change this later."),
          form,
        );
      },

      async done() {
        const { me } = await loadMe();
        const id = me?.displayId || "a new star";
        const star = h("div", { class: `done-star decor ${motionOK() ? "animate" : ""}`, "aria-hidden": "true" });
        if (me?.displayId) star.style.setProperty("--star", starColor(me.displayId));
        return h("section", { class: "done", "aria-labelledby": "step-h" },
          star,
          h("h1", { id: "step-h" }, "Your card is ready"),
          h("p", { class: "lede" }, "You're ", h("code", { class: "display-id" }, id), ". Look for yourself on the big screen."),
          h("a", { class: "btn btn-primary btn-block", href: "#/now" }, "Find me a talk"),
          h("p", { class: "welcome-note" }, h("a", { href: "#/card" }, "See my card")),
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
