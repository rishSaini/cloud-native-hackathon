// A friendly stand-in for screens that later build steps fill in.

import { h } from "../format.js";

const STAR = `<svg viewBox="0 0 48 48" aria-hidden="true" focusable="false"><path fill="currentColor" d="M24 4l5.2 11 12 1.4-8.9 8.2 2.4 11.9L24 30.6 13.3 36.5l2.4-11.9-8.9-8.2 12-1.4z" opacity=".85"/></svg>`;

export function placeholder({ title, heading, body, action }) {
  return {
    title,
    render(main) {
      const star = h("div", { class: "decor-star decor" });
      star.innerHTML = STAR; // static markup, no user content
      main.append(
        h("section", { class: "card coming-soon", "aria-labelledby": "screen-h" },
          star,
          h("h1", { id: "screen-h" }, heading),
          h("p", { class: "muted" }, body),
          action ? h("a", { class: "btn btn-secondary", href: action.href }, action.label) : null,
        ),
      );
    },
  };
}
