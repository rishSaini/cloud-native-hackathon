// Your break group: opt in, countdown, the reveal, member cards ("how to talk to me" first),
// a suggested opener, check-in, and safety actions (block, report a concern, leave).

import { announce, focusScreen, getPrefs, motionOK } from "../a11y.js";
import { api } from "../api.js";
import { accentColor, avatarColor } from "../color.js";
import { formatDayTime, formatTime, h } from "../format.js";
import { loadErrorView } from "../load-error.js";
import { confirmLeave, openBlock, openReport } from "../safety.js";
import { comfortOf, comfortPill } from "../comfort.js";
import { openerView, openReflection, turnRound } from "../grow.js";
import { photo } from "../photos.js";
import { nextBreak } from "../slots.js";
import { currentCard, loadMe } from "../store.js";
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

function pinIcon() {
  const el = h("span", { class: "pin", "aria-hidden": "true" });
  el.innerHTML = '<svg viewBox="0 0 24 24" focusable="false"><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.4"/></svg>';
  return el;
}

// Stars drifting together; "joined" draws the lines between them. Static, decorative markup.
function starsArt(joined) {
  const el = h("div", { class: `exchange-art${joined ? " joined" : ""}`, "aria-hidden": "true" });
  el.innerHTML = `<svg viewBox="0 0 200 80" focusable="false">
    <g class="ex-lines" fill="none" stroke="#C9B9A6" stroke-width="1.5" stroke-linecap="round"><path d="M40 52 L100 24 L160 50 M40 52 L160 50"/></g>
    <circle class="ex-star s1" cx="40" cy="52" r="9"/><circle class="ex-star s2" cx="100" cy="24" r="11"/><circle class="ex-star s3" cx="160" cy="50" r="9"/>
  </svg>`;
  return el;
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
    let connected = new Set();
    let exchanging = false;
    let growthLevel = 1;
    let reflected = false;
    let round = null; // the turn-taking round, kept across repaints for this group
    const roundFor = (g) => {
      if (!round || round.groupId !== g.id) { round?.cleanup(); round = { ...turnRound(g), groupId: g.id }; }
      return round.el;
    };
    api.growth().then((g) => { growthLevel = g?.level || 1; if (group) paint(); }).catch(() => {});
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
      avatar.style.background = avatarColor(m.displayId);
      const el = h("li", { class: "member" },
        h("div", { class: "member-head" },
          avatar,
          h("div", { class: "member-who" },
            h("p", { class: "member-name" }, m.name, m.pronouns ? h("span", { class: "member-pronouns" }, ` (${m.pronouns})`) : null),
            h("p", { class: `member-status st-${m.status || "on-the-way"}` }, STATUS_WORDS[m.status] || "On the way"),
          ),
          menuBtn,
        ),
        comfortPill(m.comfort),
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
        dot.style.background = avatarColor(m.displayId);
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

      const arrived = group.myStatus === "here";
      const everyoneHere = arrived && group.members.every((m) => m.status === "here");

      // Navigation mode: before you arrive, the page is about finding the table.
      const navigation = h("section", { class: "card nav-panel", "aria-labelledby": "g-h" },
        photo("table"),
        h("p", { class: "nav-eyebrow" }, started ? "Your group is meeting now" : h("span", {}, "Your table in ", countdown)),
        h("h2", { id: "g-h", class: "nav-landmark" }, pinIcon(), group.landmark || group.place),
        h("p", { class: "nav-place" }, `${formatTime(group.startsAt)}, ${group.place}`),
        group.directions ? h("p", { class: "nav-directions" }, group.directions) : null,
        h("ul", { class: "nav-who", "aria-label": "Who's there" },
          h("li", { class: `who ${group.myStatus === "late" ? "st-late" : ""}` }, h("span", { class: "who-name" }, "You"), h("span", { class: "who-status" }, group.myStatus === "late" ? "Running late" : "On your way")),
          group.members.map((m) => h("li", { class: `who st-${m.status || "on-the-way"}` },
            h("span", { class: "who-name" }, m.name), h("span", { class: "who-status" }, STATUS_WORDS[m.status] || "On the way")))),
        noShow ? h("p", { class: "notice merge-glow", role: "status" }, "Merging your group so nobody waits alone…") : null,
        h("div", { class: "group-actions" },
          h("button", { type: "button", class: "btn btn-primary", disabled: busy || null, "data-key": "here", onclick: arrive }, "I'm here"),
          h("button", { type: "button", class: "btn btn-secondary", disabled: busy || null, "data-key": "late", onclick: checkIn("late") }, "Running late"),
        ),
      );

      // Card mode: once you're at the table, the people come first.
      const atTable = h("div", { class: "stack" },
        reveal(group.members),
        h("div", { class: "card group-when" },
          h("h2", { id: "g-h" }, "You're at the table"),
          h("p", { class: "group-place" }, `${group.landmark ? `${group.landmark} · ` : ""}${group.place}`),
          comfortOf(currentCard()) === "recharge" ? h("p", { class: "comfort-pill recharge" }, "You're recharging. Your group sees: listening only, no conversation expected.") : null,
          noShow ? h("p", { class: "notice merge-glow", role: "status" }, "Merging your group so nobody waits alone…") : null,
        ),
        roundFor(group),
        everyoneHere ? exchangeView() : null,
        h("section", { class: "card reflect-card", "aria-labelledby": "rf-cta" },
          h("h2", { id: "rf-cta" }, reflected ? "Thanks for reflecting" : "After the break: 30 seconds for you"),
          h("p", { class: "muted" }, reflected ? "Your next challenge is waiting in Grow." : "A quick, private check-in helps you grow, and tells us if everyone got a turn."),
          reflected
            ? h("a", { class: "btn btn-secondary btn-block", href: "#/grow" }, "See your growth")
            : h("button", { type: "button", class: "btn btn-secondary btn-block", "data-key": "reflect", onclick: () => openReflection({
              groupId: group.id, hosted: round?.hostIsMe?.() || false,
              onDone: (res) => { reflected = true; growthLevel = res?.growth?.level || growthLevel; paint(); },
            }) }, "How did that go?"),
        ),
      );

      return h("section", { class: "stack" },
        arrived ? atTable : navigation,
        h("h2", { class: "section-title" }, arrived ? `With ${group.members.map((m) => m.name).join(" and ")}` : "Read their cards on the way"),
        h("ul", { class: "members" }, group.members.map(memberCard)),
        openerView(group, growthLevel),
        h("div", { class: "group-safety" },
          h("button", { type: "button", class: "btn btn-secondary", "data-key": "report", onclick: () => openReport({ groupId: group.id }) }, "Report a concern"),
          h("button", { type: "button", class: "btn btn-quiet-ink", "data-key": "leave", onclick: () => confirmLeave(leave) }, "Leave group"),
        ),
      );

      async function arrive() {
        await checkIn("here")();
        if (group?.myStatus !== "here") return;
        // "You've arrived": a double pulse, then the cards take over.
        if (navigator.vibrate && navigator.userActivation?.hasBeenActive !== false && !getPrefs().calm) {
          try { navigator.vibrate([80, 60, 80]); } catch { /* not allowed */ }
        }
        revealed.delete(group.id);
        paint();
        focusScreen(main);
      }
    }

    function exchangeView() {
      const names = group.members.map((m) => m.name).join(" and ");
      const allConnected = group.members.every((m) => connected.has(m.displayId));
      if (allConnected) {
        return h("section", { class: "card exchange done", "aria-labelledby": "ex-h" },
          starsArt(true),
          h("h2", { id: "ex-h" }, "Stars exchanged"),
          h("p", {}, `You're connected with ${names}. We saved where you met.`),
          h("a", { class: "btn btn-secondary btn-block", href: "#/met" }, "See people you've met"),
        );
      }
      return h("section", { class: `card exchange${exchanging ? " sending" : ""}`, "aria-labelledby": "ex-h" },
        starsArt(false),
        h("h2", { id: "ex-h" }, "Everyone's here!"),
        h("p", {}, "Exchange stars to stay connected. It's saved only if they agree too, and you keep their name and where you met."),
        h("button", {
          type: "button", class: "btn btn-primary btn-block", "data-key": "exchange", disabled: exchanging || null,
          onclick: exchangeStars,
        }, exchanging ? "Waiting for them to agree…" : "Exchange stars"),
      );
    }

    async function exchangeStars() {
      exchanging = true;
      paint();
      announce("Sent. Waiting for them to agree.");
      try {
        await Promise.all(group.members.filter((m) => !connected.has(m.displayId)).map((m) => api.proposeConnection(m.displayId, group.id)));
      } catch {
        exchanging = false;
        notice = "We couldn't send that. Please try again.";
        paint();
      }
    }

    async function refreshConnections() {
      try {
        const list = await api.connections();
        const before = connected.size;
        connected = new Set(list.map((c) => c.displayId));
        if (group && exchanging && group.members.every((m) => connected.has(m.displayId))) {
          exchanging = false;
          announce("Stars exchanged. They're saved in People you've met.");
        }
        if (connected.size !== before) paint();
      } catch { /* keep what we have */ }
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
      if (isNew || (!next && group)) { notice = null; reflected = false; } // per-group state
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
      if (data && "group" in data) { setGroup(data.group, { fromEvent: true }); refreshConnections(); }
      else refresh(); // a summary event: fetch our own group
    });

    paint();
    await refresh();
    refreshConnections();
    const connPoll = setInterval(() => { if (exchanging) refreshConnections(); }, 3000);
    return () => { clearInterval(tick); clearInterval(connPoll); unsub(); round?.cleanup(); };
  },
};
