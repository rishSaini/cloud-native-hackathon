// Now. The placement card, status pill and reroute banner land in build step 3.

import { h } from "../format.js";

export default {
  title: "Now",
  render(main) {
    main.append(
      h("h1", { class: "screen-title" }, "Now"),
      h("section", { class: "card stack", "aria-labelledby": "now-next" },
        h("h2", { id: "now-next" }, "Your next talk"),
        h("p", { class: "muted" }, "Soon we'll find you a talk that fits, with seats and what you need from the room."),
        h("a", { class: "btn btn-primary btn-block", href: "#/talks" }, "Find a talk"),
      ),
    );
  },
};
