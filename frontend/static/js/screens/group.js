// Your break group: opt in, countdown, the reveal, member cards ("how to talk to me" first),
// a suggested opener, check-in, and safety actions (block, report a concern, leave).

import { announce, focusScreen, getPrefs, motionOK } from "../a11y.js";
import { api } from "../api.js";
import { accentColor } from "../color.js";
import { formatDayTime, formatTime, h } from "../format.js";
import { loadErrorView } from "../load-error.js";
import { confirmLeave, openBlock, openReport } from "../safety.js";
import { nextBreak } from "../slots.js";
import { loadMe } from "../store.js";
import { subscribe } from "../stream.js";

const NO_SHOW_MS = 3 * 60000;
const STATUS_WORDS = { here: "Here", late: "Running late", "on-the-way": "On the way" };

// Kept for this visit.
let optedIn = false;
const revealed = new Set();

const initials = (name = "") => name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() || "").join("") || "?";

function countdownText(startsAt, now = Date.now()) {
  const ms = Date.parse(startsAt) - now;
  if (ms <= 0) return null;
  if (ms > 60 * 60000) return formatDayTime(startsAt);
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default {
  title: "Your break group",
  async render(main) {
    const { card, error } = await loadMe();
    if (error) { main.append(loadErrorView()); return; }

    main.append(h("h1", { class: "screen-title" }, "Your break group"));
    const region = h("div", { class: "group stack" });
    main.append(region);

    if (!card) {
      region.append(h("section", { class: "card stack", "aria-labelledby": "g-h" },
        h("h2", { id: "g-h" }, "Make your card first"),
        h("p", { class: "muted" }, "Your group reads your card before you meet, so nobody has to explain themselves."),
        h("a", { class: "btn btn-primary btn-block", href: "#/" }, "Make my card"),
      ));
      return;
    }

    let group = null;
    let busy = false;
    let notice = null;
    const brk = nextBreak();

    // ---- views ----
    function optInView() {
      const toggle = h("input", { type: "checkbox", id: "opt-in", role: "switch", class: "switch-input", "data-key": "opt-in" });
      toggle.checked = optedIn;
      toggle.addEventListener("change", async () => {
        toggle.disabled = true;
        try {
          await api.rsvpBreak(brk.id, toggle.checked);
          optedIn = toggle.checked;
          announce(optedIn ? "You're in for the next break. We'll find you a table." : "Okay, no group this break.");
        } catch {
          toggle.checked = optedIn;
          notice = "We couldn't save that. Please try again.";
        }
        paint();
        // The switch was disabled while saving, which drops focus: put it back.
        region.querySelector("#opt-in")?.focus();
      });
      return h("section", { class: "card stack", "aria-labelledby": "g-h" },
        h("h2", { id: "g-h" }, optedIn ? "Finding you a table" : "No group yet"),
        h("p", { class: "muted" }, optedIn
          ? `When the break starts at ${formatTime(brk.startsAt)}, your group shows here. We'll match you with people working on similar things.`
          : "Turn on \"Find me a group\" to join the next break. You'll get a small table with people working on similar things."),
        h("div", { class: "switch" },
          toggle,
          h("label", { for: "opt-in" }, "Find me a group at the next break",
            h("span", { class: "hint" }, `Next break: ${formatDayTime(brk.startsAt)}`)),
        ),
      );
    }

    function memberCard(m) {
      const color = accentColor(m.displayId);
      const menuId = `menu-${m.displayId}`;
      const menuBtn = h("button", {
        type: "button", class: "member-menu-btn", "aria-expanded": "false", "aria-controls": menuId,
        "data-key": `menu-${m.displayId}`,
      }, "⋯", h("span", { class: "visually-hidden" }, `More for ${m.name}`));
      const menu = h("div", { class: "member-menu", id: menuId, hidden: true },
        h("button", { type: "button", class: "btn btn-secondary", onclick: () => openBlock({
          displayId: m.displayId, name: m.name,
          onBlocked: () => { notice = `You blocked ${m.name}. You can leave this group if you'd like.`; paint(); },
        }) }, "Block this person"),
        h("button", { type: "button", class: "btn btn-secondary", onclick: () => openReport({ aboutDisplayId: m.displayId, aboutName: m.name, groupId: group.id }) }, "Report a concern"),
      );
      menuBtn.addEventListener("click", () => {
        const open = menu.hidden;
        menu.hidden = !open;
        menuBtn.setAttribute("aria-expanded", String(open));
      });
      const avatar = h("span", { class: "avatar", "aria-hidden": "true" }, initials(m.name));
      avatar.style.background = color;
      const el = h("li", { class: "member" },
        h("div", { class: "member-head" },
          avatar,
          h("div", { class: "member-who" },
            h("p", { class: "member-name" }, m.name, m.pronouns ? h("span", { class: "member-pronouns" }, ` (${m.pronouns})`) : null),
            h("p", { class: `member-status st-${m.status || "on-the-way"}` }, STATUS_WORDS[m.status] || "On the way"),
          ),
          menuBtn,
        ),
        m.howToTalk ? h("p", { class: "member-talk" }, m.howToTalk) : null,
        h("dl", { class: "card-fields" },
          m.workingOn ? h("div", { class: "card-row" }, h("dt", {}, "Working on"), h("dd", {}, m.workingOn)) : null,
          m.askMeAbout ? h("div", { class: "card-row" }, h("dt", {}, "Ask me about"), h("dd", {}, m.askMeAbout)) : null,
        ),
        menu,
      );
      el.style.setProperty("--accent", color);
      return el;
    }

    function reveal(members) {
      // Initials slide together into one group; with reduced motion they simply appear.
      const animate = motionOK() && !revealed.has(group.id);
      revealed.add(group.id);
      const dots = members.map((m, i) => {
        const dot = h("span", { class: "avatar avatar-lg" }, initials(m.name));
        dot.style.background = accentColor(m.displayId);
        if (animate) {
          const angle = (i / Math.max(1, members.length)) * Math.PI * 2;
          dot.style.setProperty("--from-x", `${Math.cos(angle) * 140}px`);
          dot.style.setProperty("--from-y", `${Math.sin(angle) * 60}px`);
        }
        return dot;
      });
      const me = h("span", { class: "avatar avatar-lg avatar-me" }, "You");
      return h("div", { class: `reveal${animate ? " animate" : ""}`, "aria-hidden": "true" }, me, ...dots);
    }

    function groupView() {
      const startsIn = countdownText(group.startsAt);
      const started = Date.parse(group.startsAt) <= Date.now();
      const missing = group.members.filter((m) => m.status !== "here");
      const noShow = started && Date.now() - Date.parse(group.startsAt) > NO_SHOW_MS && missing.length > 0;
      const countdown = h("span", { class: "countdown", "data-countdown": "" }, startsIn || "now");

      const checkIn = (status) => async () => {
        busy = true; paint();
        try {
          await api.checkIn(group.id, status);
          group.myStatus = status;
          announce(status === "here" ? "Checked in. Your group can see you're here." : "Okay, we'll let your group know you're running late.");
        } catch {
          notice = "We couldn't check you in. Please try again.";
        }
        busy = false; paint();
      };

      return h("section", { class: "stack", "aria-labelledby": "g-h" },
        reveal(group.members),
        h("div", { class: "card group-when" },
          h("h2", { id: "g-h" }, started ? "Your group is meeting now" : "Your table in ", started ? null : countdown),
          h("p", { class: "group-place" }, `${formatTime(group.startsAt)}, ${group.place}`),
          group.myStatus ? h("p", { class: "my-status" }, `You: ${STATUS_WORDS[group.myStatus] || group.myStatus}`) : null,
          noShow ? h("p", { class: "notice", role: "status" }, "We're adding someone so nobody waits alone.") : null,
        ),
        h("h2", { class: "section-title" }, `With ${group.members.map((m) => m.name).join(" and ")}`),
        h("ul", { class: "members" }, group.members.map(memberCard)),
        group.opener ? h("p", { class: "opener" }, h("span", { class: "opener-label" }, "Try asking: "), group.opener) : null,
        h("div", { class: "group-actions" },
          h("button", { type: "button", class: "btn btn-primary", disabled: busy || null, "data-key": "here", onclick: checkIn("here") }, "I'm here"),
          h("button", { type: "button", class: "btn btn-secondary", disabled: busy || null, "data-key": "late", onclick: checkIn("late") }, "Running late"),
        ),
        h("div", { class: "group-safety" },
          h("button", { type: "button", class: "btn btn-secondary", "data-key": "report", onclick: () => openReport({ groupId: group.id }) }, "Report a concern"),
          h("button", { type: "button", class: "btn btn-quiet-ink", "data-key": "leave", onclick: () => confirmLeave(leave) }, "Leave group"),
        ),
      );
    }

    async function leave() {
      try {
        await api.leaveGroup(group.id);
        group = null;
        optedIn = false;
        notice = null;
        announce("You left the group.");
        paint();
        focusScreen(main);
      } catch {
        notice = "We couldn't leave the group just now. Please try again.";
        paint();
      }
    }

    function paint() {
      const focusedKey = document.activeElement?.closest?.("[data-key]")?.dataset.key;
      region.replaceChildren(
        notice ? h("p", { class: "notice", role: "status" }, notice) : "",
        group ? groupView() : optInView(),
      );
      if (focusedKey) region.querySelector(`[data-key="${focusedKey}"]`)?.focus();
    }

    function setGroup(next, { fromEvent = false } = {}) {
      const isNew = next && (!group || group.id !== next.id);
      if (isNew || (!next && group)) notice = null; // notices belong to the group they were about
      group = next || null;
      if (isNew && fromEvent) {
        announce(`Your break group is ready: ${formatTime(group.startsAt)}, ${group.place}, with ${group.members.map((m) => m.name).join(" and ")}.`);
        if (navigator.vibrate && navigator.userActivation?.hasBeenActive !== false && !getPrefs().calm) {
          try { navigator.vibrate([60, 60, 60]); } catch { /* not allowed */ }
        }
      }
      paint();
    }

    async function refresh() {
      try { setGroup(await api.currentGroup()); } catch { notice = "We couldn't reach the server. We'll keep trying."; paint(); }
    }

    // Countdown: updates the numbers only, once a second, without announcing every tick.
    const tick = setInterval(() => {
      if (!group) return;
      const el = region.querySelector("[data-countdown]");
      const text = countdownText(group.startsAt);
      if (el && text) el.textContent = text;
      else if (el && !text) paint(); // the break started
      else if (Date.parse(group.startsAt) + NO_SHOW_MS < Date.now() && !region.querySelector(".notice")) paint();
    }, 1000);

    const unsub = subscribe("group", (data) => {
      if (data && "group" in data) setGroup(data.group, { fromEvent: true });
      else refresh(); // a summary event: fetch our own group
    });

    paint();
    await refresh();
    return () => { clearInterval(tick); unsub(); };
  },
};
