// Shown when the person's card couldn't be loaded. We never guess "no card" from an error.

import { h } from "./format.js";

export function loadErrorView(headingId = "screen-h") {
  return h("section", { class: "card stack", "aria-labelledby": headingId },
    h("h1", { id: headingId }, "We couldn't load your card"),
    h("p", { class: "muted" }, "We couldn't reach the server. Your card is safe. Please try again in a moment."),
    h("button", {
      type: "button", class: "btn btn-primary btn-block",
      onclick: () => window.dispatchEvent(new HashChangeEvent("hashchange")),
    }, "Try again"),
  );
}
