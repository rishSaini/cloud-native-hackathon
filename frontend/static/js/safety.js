// Safety actions, reused on the Group screen, each member card and (step 9) shared cards.
//
// Privacy: report text goes only in the request body. It is never logged, never shown again
// after sending, and the field is cleared as soon as it's sent.

import { announce } from "./a11y.js";
import { api } from "./api.js";
import { h } from "./format.js";

// The event's Code of Conduct contact. Organizers: put the real contact here before the event.
export const CODE_OF_CONDUCT = {
  line: "If you feel unsafe right now, go to any event staff member or the registration desk and ask for the Code of Conduct team.",
};

function dialog(titleId, ...children) {
  const d = h("dialog", { class: "dialog", "aria-labelledby": titleId }, ...children);
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
  return d;
}

/** Confirms and blocks someone. Calls onBlocked() after it succeeds. */
export function openBlock({ displayId, name, onBlocked }) {
  const status = h("p", { class: "form-status", role: "status" });
  const confirm = h("button", { type: "button", class: "btn btn-danger" }, "Block");
  const d = dialog("block-h",
    h("h2", { id: "block-h" }, `Block ${name || "this person"}?`),
    h("p", {}, "You won't be grouped with this person again. They won't be told."),
    status,
    h("div", { class: "dialog-actions" },
      h("button", { type: "button", class: "btn btn-secondary", autofocus: true, onclick: () => d.close() }, "Cancel"),
      confirm,
    ),
  );
  confirm.addEventListener("click", async () => {
    confirm.disabled = true;
    status.textContent = "Blocking…";
    try {
      await api.block(displayId);
      d.close();
      announce(`Blocked. You won't be grouped with ${name || "this person"} again.`);
      onBlocked?.();
    } catch {
      status.textContent = "We couldn't block just now. Please try again, or tell any staff member.";
      confirm.disabled = false;
    }
  });
}

/** A short report form for organizers. aboutDisplayId and groupId are optional. */
export function openReport({ aboutDisplayId = null, aboutName = null, groupId = null } = {}) {
  const text = h("textarea", { id: "report-text", class: "input", rows: 4, maxlength: 1000, autocomplete: "off" });
  const contact = h("input", { type: "checkbox", id: "report-contact" });
  const status = h("p", { class: "form-status", role: "status" });
  const send = h("button", { type: "submit", class: "btn btn-primary" }, "Send to organizers");
  const form = h("form", { class: "stack" },
    h("div", { class: "field" },
      h("label", { for: "report-text" }, "What happened ", h("span", { class: "req" }, "(optional)")),
      h("span", { class: "hint", id: "report-hint" }, "Only organizers see this. You can leave it empty."),
      text,
    ),
    h("div", { class: "check" }, contact, h("label", { for: "report-contact" }, "I'd like an organizer to contact me")),
    h("p", { class: "muted coc" }, CODE_OF_CONDUCT.line),
    status,
    h("div", { class: "dialog-actions" },
      h("button", { type: "button", class: "btn btn-secondary", onclick: () => d.close() }, "Cancel"),
      send,
    ),
  );
  text.setAttribute("aria-describedby", "report-hint");
  const d = dialog("report-h",
    h("h2", { id: "report-h" }, aboutName ? `Report a concern about ${aboutName}` : "Report a concern"),
    form,
  );
  text.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    send.disabled = true;
    status.textContent = "Sending…";
    const body = { text: text.value.trim() || null, wantsContact: contact.checked };
    if (aboutDisplayId) body.aboutDisplayId = aboutDisplayId;
    if (groupId) body.groupId = groupId;
    try {
      await api.safetyReport(body);
      text.value = ""; // never shown again
      body.text = null;
      form.replaceWith(h("div", { class: "stack" },
        h("p", { class: "report-thanks" }, "Thanks. Organizers have your report."),
        h("p", { class: "muted coc" }, CODE_OF_CONDUCT.line),
        h("div", { class: "dialog-actions" },
          h("button", { type: "button", class: "btn btn-primary", autofocus: true, onclick: () => d.close() }, "Done")),
      ));
      d.querySelector(".dialog-actions .btn")?.focus();
      announce("Thanks. Organizers have your report.");
    } catch {
      status.textContent = "We couldn't send your report. Please try again, or tell any staff member.";
      send.disabled = false;
    }
  });
}

/** Asks before leaving a group. Calls onConfirm() if they're sure. */
export function confirmLeave(onConfirm) {
  const d = dialog("leave-h",
    h("h2", { id: "leave-h" }, "Leave this group?"),
    h("p", {}, "You can turn on \"Find me a group\" again for the next break."),
    h("div", { class: "dialog-actions" },
      h("button", { type: "button", class: "btn btn-secondary", autofocus: true, onclick: () => d.close() }, "Stay"),
      h("button", { type: "button", class: "btn btn-danger", onclick: () => { d.close(); onConfirm(); } }, "Leave group"),
    ),
  );
}
