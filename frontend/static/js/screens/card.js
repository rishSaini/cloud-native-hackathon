// Your card: flip card, edit in place, delete with confirmation.
// Sharing by QR lands in build step 9 with "Show across the table".

import { announce, focusScreen } from "../a11y.js";
import { cardFields, livePreview, needsFields } from "../card-form.js";
import { flipCard } from "../card-view.js";
import { comfortDial } from "../comfort.js";
import { galaxySvg } from "../galaxy.js";
import { NEEDS } from "../card-form.js";
import { h, twoTone } from "../format.js";
import { loadErrorView } from "../load-error.js";
import { deleteMyCard, loadMe, saveMyCard } from "../store.js";

export default {
  title: "Your card",
  async render(main, { navigate }) {
    const loaded = await loadMe();
    if (loaded.error) { main.append(loadErrorView()); return; }
    let { me, card } = loaded;

    function empty() {
      return h("section", { class: "card coming-soon", "aria-labelledby": "screen-h" },
        h("h1", { id: "screen-h" }, "No card yet"),
        h("p", { class: "muted" }, "Make a small card so people know what you're working on and how to talk to you."),
        h("a", { class: "btn btn-primary", href: "#/?start=card" }, "Make my card"),
      );
    }

    function view() {
      const flip = flipCard(card, { displayId: me?.displayId });
      const status = h("p", { class: "form-status", role: "status" });
      const dialog = confirmDelete(async () => {
        status.textContent = "Deleting your card…";
        try {
          await deleteMyCard();
          announce("Your card and data were deleted.");
          navigate("/");
        } catch {
          status.textContent = "We couldn't delete your card. Please try again.";
        }
      });
      return h("section", { class: "card-page", "aria-labelledby": "screen-h" },
        h("h1", { id: "screen-h", class: "screen-title" }, twoTone("Your ", "card.")),
        h("div", { class: "star-id" },
          galaxySvg({ id: me?.displayId || card.name, interests: `${card.workingOn || ""} ${card.askMeAbout || ""} ${card.lookingFor || ""}` }),
          h("div", {},
            h("p", { class: "star-id-label" }, "Your star ID"),
            me?.displayId ? h("p", { class: "star-id-code" }, h("code", { class: "display-id" }, me.displayId)) : null,
            h("p", { class: "muted star-id-note" }, "This is how you appear on the big screen. Your name never does."),
          ),
        ),
        comfortDial({ idPrefix: "card-comfort" }),
        flip.el,
        privateNeeds(card),
        h("div", { class: "card-actions" },
          h("a", { class: "btn btn-primary btn-block", href: "#/card/show" }, "Show across the table"),
          h("button", { type: "button", class: "btn btn-secondary btn-block", onclick: () => paint(edit) }, "Edit"),
          h("button", { type: "button", class: "btn btn-quiet btn-block", onclick: () => dialog.showModal() }, "Delete my card"),
        ),
        status,
        dialog,
      );
    }

    function edit() {
      const draft = { ...card, needs: [...(card.needs || [])] };
      const preview = livePreview(draft);
      const fields = cardFields(draft, { onChange: preview.update, idPrefix: "edit" });
      const status = h("p", { class: "form-status", role: "status" });
      const save = h("button", { type: "submit", class: "btn btn-primary btn-block" }, "Save card");
      const form = h("form", { class: "stack", novalidate: true, "aria-labelledby": "screen-h" },
        fields.el,
        needsFields(draft, { idPrefix: "edit" }),
        status,
        save,
        h("button", { type: "button", class: "btn btn-secondary btn-block", onclick: () => paint(view) }, "Cancel"),
      );
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!fields.validate()) return;
        save.disabled = true;
        status.textContent = "Saving…";
        try {
          ({ me, card } = await saveMyCard(draft));
          announce("Your card is saved.");
          paint(view);
        } catch {
          status.textContent = "We couldn't save your card. Check your connection and try again.";
          save.disabled = false;
        }
      });
      return h("section", { class: "onboard-card" },
        h("h1", { id: "screen-h", class: "screen-title" }, "Edit your card"),
        h("div", { class: "form-with-preview" }, form, preview.el),
      );
    }

    function paint(fn, focus = true) {
      main.replaceChildren(fn());
      if (focus) focusScreen(main);
    }

    paint(card ? view : empty, false);
  },
};

// What helps you in a room: shown only here, on your own phone, inside a "private" box.
function privateNeeds(card) {
  const labels = NEEDS.filter((n) => (card.needs || []).includes(n.id)).map((n) => n.label);
  return h("section", { class: "private-lock", "aria-labelledby": "lock-h" },
    h("p", { class: "lock-badge" }, h("span", { "aria-hidden": "true" }, "🔒"), " Private"),
    h("h2", { id: "lock-h", class: "lock-title" }, "Your break-time vibe"),
    labels.length
      ? h("ul", { class: "lock-list" }, labels.map((l) => h("li", {}, l)))
      : h("p", { class: "muted" }, "Nothing set. You can add things with Edit."),
    h("p", { class: "lock-note" }, "Only the scheduler uses this, to pick rooms and tables. Nobody else sees it."),
  );
}

export function confirmDelete(onConfirm) {
  const dialog = h("dialog", { class: "dialog", "aria-labelledby": "del-h", "aria-describedby": "del-body" },
    h("h2", { id: "del-h" }, "Delete your card?"),
    h("p", { id: "del-body" }, "This deletes your card and your private needs. It also removes you from any group and turns off links you've shared. You can make a new card any time."),
  );
  const cancel = h("button", { type: "button", class: "btn btn-secondary", autofocus: true, onclick: () => dialog.close() }, "Keep my card");
  const confirm = h("button", { type: "button", class: "btn btn-danger", onclick: () => { dialog.close(); onConfirm(); } }, "Delete my card");
  dialog.append(h("div", { class: "dialog-actions" }, cancel, confirm));
  return dialog;
}
