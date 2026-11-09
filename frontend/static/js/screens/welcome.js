// Welcome. The full onboarding flow (templates, card form, done moment) lands in build step 2.

import { h } from "../format.js";

export default {
  title: "Welcome",
  render(main) {
    main.append(
      h("section", { class: "welcome", "aria-labelledby": "welcome-h" },
        h("div", { class: "welcome-sky decor", "aria-hidden": "true" },
          h("span", { class: "welcome-star s1" }), h("span", { class: "welcome-star s2" }), h("span", { class: "welcome-star s3" }),
        ),
        h("h1", { id: "welcome-h" }, "Find your talk. Find your people."),
        h("p", { class: "lede" }, "Make a small card about what you're working on and how people should talk to you. We'll find you a good talk and a friendly table at every break."),
        h("a", { class: "btn btn-primary btn-block", href: "#/card" }, "Make my card"),
        h("p", { class: "muted welcome-note" }, "Your card is private. Only people in your group see it."),
      ),
    );
  },
};
