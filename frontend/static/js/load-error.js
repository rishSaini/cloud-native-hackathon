// Shown when the person's card couldn't be loaded. We never guess "no card" from an error.

import { h } from "./format.js";

/** A truthful message for a failed save: blame the connection only when the request never arrived. */
export function saveErrorMessage(err) {
  const status = err?.status;
  if (status === 0 || status === undefined) return "We couldn't save your card. Check your connection and try again.";
  if (status === 401) return "Your session ended. Reload the page and try again.";
  if (status === 422) return "Some of your answers couldn't be saved. Check them and try again.";
  if (status >= 500) return "Something went wrong on our side. Your answers are still here. Please try again in a minute.";
  return "We couldn't save your card. Please try again.";
}

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
