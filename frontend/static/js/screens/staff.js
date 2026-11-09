// Staff incidents: plain and fast. Open incidents with room, type, when, and how many reports,
// with "On it" (acknowledged) and "Fixed" (resolved).

import { announce } from "../a11y.js";
import { api } from "../api.js";
import { h } from "../format.js";
import { isLive, subscribe } from "../stream.js";

const KIND = { captions: "Captions down", access: "Elevator or aisle problem", loud: "Too loud" };

export default {
  title: "Staff incidents",
  chrome: false,
  async render(main) {
    const list = h("ul", { class: "incidents" });
    const status = h("p", { class: "muted", role: "status" });

    // Shown when the API says 401. The token is POSTed in the body; the server answers with a cookie.
    const tokenInput = h("input", { type: "password", id: "staff-token", autocomplete: "current-password", required: true });
    const login = h("form", { class: "staff-login", hidden: true },
      h("label", { for: "staff-token" }, "Staff token"),
      tokenInput,
      h("button", { type: "submit", class: "btn btn-primary" }, "Sign in"),
    );
    login.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await api.staffLogin(tokenInput.value);
        tokenInput.value = "";
        login.hidden = true;
        list.hidden = false;
        await refresh();
      } catch {
        status.textContent = "That token didn't work. Please check it and try again.";
      }
    });

    main.append(h("section", { class: "staff" },
      h("h1", {}, "Staff incidents"),
      h("p", { class: "muted" }, "Open reports from attendees. Tap \"On it\" when someone is going, and \"Fixed\" when it's sorted."),
      status,
      login,
      list,
    ));

    let busy = new Set();

    async function act(inc, state) {
      busy.add(inc.id);
      paint(current);
      try {
        await api.updateIncident(inc.id, { state });
        announce(state === "resolved" ? `${inc.roomName || inc.room}: marked fixed.` : `${inc.roomName || inc.room}: you're on it.`);
      } catch {
        status.textContent = "We couldn't update that. Please try again.";
      }
      busy.delete(inc.id);
      await refresh();
    }

    let current = [];
    function paint(incidents) {
      current = incidents;
      if (!incidents.length) {
        list.replaceChildren(h("li", { class: "incident empty" }, "No open incidents. Nice."));
        return;
      }
      list.replaceChildren(...incidents.map((inc) => h("li", { class: `incident ${inc.state}` },
        h("div", { class: "incident-main" },
          h("p", { class: "incident-room" }, inc.roomName || inc.room),
          h("p", { class: "incident-kind" }, KIND[inc.kind] || inc.kind),
          h("p", { class: "incident-meta" },
            `Reported ${inc.openedAt} · ${inc.reports || 1} ${inc.reports === 1 ? "report" : "reports"} · `,
            h("strong", {}, inc.state === "acknowledged" ? "ON IT" : "OPEN")),
        ),
        h("div", { class: "incident-actions" },
          inc.state === "acknowledged" ? null
            : h("button", { type: "button", class: "btn btn-secondary", disabled: busy.has(inc.id) || null, onclick: () => act(inc, "acknowledged") }, "On it"),
          h("button", { type: "button", class: "btn btn-primary", disabled: busy.has(inc.id) || null, onclick: () => act(inc, "resolved") }, "Fixed"),
        ),
      )));
    }

    async function refresh() {
      try {
        const data = await api.staffIncidents();
        paint(Array.isArray(data) ? data : data?.incidents || []);
        status.textContent = "";
      } catch (err) {
        if (err?.status === 401) {
          login.hidden = false;
          list.hidden = true;
          status.textContent = "Sign in with the staff token to see incidents.";
          return;
        }
        status.textContent = "Reconnecting. Showing the last list we had.";
      }
    }

    const unsub = subscribe("incident", () => refresh());
    const poll = setInterval(() => { if (!isLive()) refresh(); }, 5000);
    await refresh();
    return () => { unsub(); clearInterval(poll); };
  },
};
