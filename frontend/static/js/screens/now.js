// Now: your current or next talk, the Pending → Scheduled → Running pill, "Find me a talk",
// the reroute banner, other options, and plain-language reasons when nothing fits.

import { announce, getPrefs, onPrefsChange } from "../a11y.js";
import { api } from "../api.js";
import { ago, formatDayTime, formatTime, h } from "../format.js";
import { isRunning, nextSlot } from "../slots.js";
import { loadErrorView } from "../load-error.js";
import { loadMe } from "../store.js";
import { isLive, POLL_MS, subscribe } from "../stream.js";
import { badgeList } from "./talks.js";
import { climateView } from "../climate.js";
import { COMFORT, comfortDial, comfortOf } from "../comfort.js";
import { avatarColor } from "../color.js";
import { nextBreak } from "../slots.js";

const STEPS = [
  { key: "Pending", word: "Finding you a seat" },
  { key: "Scheduled", word: "You're in. Head over." },
  { key: "Running", word: "Enjoy the talk" },
];

// Kept for this visit so coming back to Now doesn't re-request.
let autoRequested = false;

export default {
  title: "Now",
  async render(main) {
    const { card, error: loadError } = await loadMe();
    if (loadError) { main.append(loadErrorView()); return; }

    let placement = null;
    let requesting = false;
    let pendingSince = null;
    let banner = null;          // { fromId, fromName, toName, reason, reopened }
    let showOptions = false;
    let error = null;
    const slot = nextSlot();

    const region = h("div", { class: "now" });
    main.append(h("h1", { class: "screen-title" }, "Now"), region);

    if (!card) {
      region.append(h("section", { class: "card stack", "aria-labelledby": "now-h" },
        h("h2", { id: "now-h" }, "Make your card first"),
        h("p", { class: "muted" }, "Your card tells us what you're working on and what helps, so we can find you a good talk."),
        h("a", { class: "btn btn-primary btn-block", href: "#/" }, "Make my card"),
        h("a", { class: "btn btn-secondary btn-block", href: "#/talks" }, "Browse talks"),
      ));
      return;
    }

    // A personal greeting, then the dial, so the day feels tuned to you.
    const hour = Number(new Intl.DateTimeFormat("en-US", { timeZone: "America/Denver", hour: "numeric", hour12: false }).format(new Date()));
    const partOfDay = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
    const tuned = h("p", { class: "tuned" });
    const paintTuned = () => {
      const c = COMFORT.find((x) => x.id === comfortOf(card));
      tuned.replaceChildren("Your day is tuned for ", h("span", { class: "tuned-chip" }, c?.label || "Steady"));
    };
    paintTuned();
    const greeting = h("div", { class: "greeting" },
      h("p", { class: "greeting-line" }, `${partOfDay}, `, h("span", { class: "accent-word" }, `${card.name || "friend"}.`)),
      tuned,
    );
    main.querySelector("h1")?.replaceWith(h("h1", { class: "visually-hidden" }, "Now"));
    main.insertBefore(greeting, region);
    main.insertBefore(comfortDial({ compact: true, idPrefix: "now-comfort", onChange: (v) => { card.comfort = v; paintTuned(); } }), region);

    // Your upcoming break: the group as a tiny constellation, or an invitation to join one.
    const breakSlot = h("div", { class: "now-aside" });
    async function paintBreak() {
      const brk = nextBreak();
      let group = null;
      try { group = await api.currentGroup(); } catch { /* show the invitation */ }
      if (!group) {
        breakSlot.replaceChildren(h("section", { class: "card break-card", "aria-labelledby": "brk-h" },
          h("p", { class: "section-eyebrow" }, `Your upcoming break · ${formatTime(brk.startsAt)}`),
          h("h2", { id: "brk-h" }, "Want company at the break?"),
          h("p", { class: "muted" }, "We'll find you a small table with people working on similar things."),
          h("a", { class: "btn btn-secondary btn-block", href: "#/group" }, "Find me a group"),
        ));
        return;
      }
      const people = [{ name: "You", id: null }, ...group.members.map((m) => ({ name: m.name, id: m.displayId }))];
      const chain = h("ol", { class: "mini-constellation", "aria-label": `You, ${group.members.map((m) => m.name).join(", ")}` },
        people.map((p) => {
          const dot = h("span", { class: "mini-star", "aria-hidden": "true" }, p.name.slice(0, 1));
          if (p.id) dot.style.background = avatarColor(p.id);
          return h("li", {}, dot, h("span", { class: "mini-name" }, p.name));
        }));
      breakSlot.replaceChildren(h("section", { class: "card break-card", "aria-labelledby": "brk-h" },
        h("p", { class: "section-eyebrow" }, `Your upcoming break · ${formatTime(group.startsAt)}`),
        h("h2", { id: "brk-h" }, group.landmark || group.place),
        h("p", { class: "muted" }, group.place),
        chain,
        group.opener ? h("p", { class: "icebreaker" }, h("span", {}, "Icebreaker: "), group.opener) : null,
        h("a", { class: "btn btn-secondary btn-block", href: "#/group" }, "Open your group"),
      ));
    }

    // ---- data ----
    function statusOf(p) {
      if (!p) return null;
      if (p.status === "Running" || (p.status === "Scheduled" && isRunning(p.talk?.startsAt))) return "Running";
      return p.status === "Scheduled" ? "Scheduled" : "Pending";
    }

    function setPlacement(next, { quiet = false } = {}) {
      const before = placement;
      const incoming = next && (next.placement ?? next);
      const wasRequesting = requesting;
      // While our own request is in flight, ignore "nothing yet" and stale answers.
      if (wasRequesting && (!incoming || statusOf(incoming) !== "Scheduled") && !incoming?.reason) return;
      placement = incoming;
      if (statusOf(placement) === "Pending") pendingSince ??= Date.now();
      else pendingSince = null;
      if (statusOf(placement) !== "Pending" || placement?.reason) requesting = false;

      // A room change we didn't ask for is a reroute, even if we only saw it by polling.
      if (!quiet && !wasRequesting && before?.room && placement?.room && before.room.id !== placement.room.id && !banner) {
        showReroute({ id: before.room.id, name: before.room.name }, placement);
        return;
      }
      if (!quiet && statusOf(placement) === "Scheduled" && statusOf(before) !== "Scheduled") {
        announce(`You're in ${placement.room.name} for ${placement.talk.title} at ${formatTime(placement.talk.startsAt)}.`);
      }
      paint();
    }

    function showReroute(from, next, reason) {
      placement = next;
      requesting = false;
      showOptions = false;
      banner = { fromId: from.id, fromName: from.name, toName: next.room?.name, reason, reopened: false, fresh: true };
      if (navigator.vibrate && navigator.userActivation?.hasBeenActive !== false && !getPrefs().calm) { try { navigator.vibrate(120); } catch { /* not allowed */ } }
      announce(`${from.name} ${reason === "closed" ? "closed" : "filled up"}. We moved you to ${next.room?.name}.`);
      paint();
    }

    async function refresh() {
      try {
        setPlacement(await api.currentPlacement());
        error = null;
      } catch {
        error = "We couldn't reach the server. We'll keep trying.";
        paint();
      }
    }

    async function findMeATalk(preferRoom = null) {
      const slotId = placement?.talk?.slot || placement?.slot || slot.id;
      requesting = true;
      error = null;
      banner = null;
      showOptions = false;
      placement = { status: "Pending", slot: slotId, reason: null, options: [], kubectl: null };
      pendingSince = Date.now();
      paint();
      announce("Finding you a seat.");
      try {
        await api.requestPlacement(slotId, { preferRoom });
        // The result arrives as a placement event, or by polling below.
      } catch {
        requesting = false;
        error = "We couldn't ask for a seat just now. Please try again.";
        paint();
      }
    }

    // ---- view ----
    function statusPill(status) {
      const index = STEPS.findIndex((s) => s.key === status);
      return h("div", { class: "status" },
        h("ol", { class: "status-steps", "aria-label": "Placement status" },
          STEPS.map((s, i) => h("li", {
            class: i < index ? "done" : i === index ? "current" : "",
            "aria-current": i === index ? "step" : null,
          }, h("span", { class: "code" }, s.key))),
        ),
        h("p", { class: "status-word" }, STEPS[index]?.word || ""),
      );
    }

    function optionsList(options = []) {
      if (!options.length) return h("p", { class: "muted" }, "No other talks have space in this slot right now. We'll keep looking.");
      return h("ul", { class: "options" }, options.map((o) =>
        h("li", { class: "option" },
          h("div", {},
            h("p", { class: "option-title" }, o.talk.title),
            h("p", { class: "result-meta" }, `${o.room.name} · ${o.room.seatsLeft} seats left`),
          ),
          h("button", { type: "button", class: "btn btn-secondary", "data-key": `opt-${o.room.id}`, onclick: () => findMeATalk(o.room.id) },
            "Go here", h("span", { class: "visually-hidden" }, ` instead: ${o.talk.title}, ${o.room.name}`)),
        )));
    }

    function bannerView() {
      if (!banner) return null;
      const verb = banner.reason === "closed" ? "closed" : "filled up";
      // Slide in once, when the banner first appears, not on every repaint.
      const enter = banner.fresh;
      banner.fresh = false;
      return h("section", { class: `reroute${enter ? " enter" : ""}`, role: "region", "aria-labelledby": "reroute-h" },
        h("h2", { id: "reroute-h", class: "reroute-title" }, `${banner.fromName} ${verb}. We moved you to ${banner.toName}.`),
        h("div", { class: "reroute-actions" },
          h("button", { type: "button", class: "btn btn-secondary", "data-key": "show-options", "aria-expanded": String(showOptions), onclick: () => { showOptions = !showOptions; paint(); } },
            showOptions ? "Hide other options" : "Show other options"),
          banner.reopened
            ? h("button", { type: "button", class: "btn btn-secondary", "data-key": "undo", onclick: () => findMeATalk(banner.fromId) }, `Undo: go back to ${banner.fromName}`)
            : null,
          h("button", { type: "button", class: "btn btn-quiet-ink", "data-key": "dismiss", onclick: () => { banner = null; paint(); } }, "Dismiss"),
        ),
      );
    }

    function kubectlView() {
      if (!getPrefs().kubectl || !placement?.kubectl) return null;
      return h("pre", { class: "kubectl-panel", "aria-label": "kubectl view" }, h("code", {}, `$ kubectl get pod -l me\n${placement.kubectl}`));
    }

    function placementView() {
      const status = statusOf(placement);
      if (!placement || (!status && !requesting)) {
        return h("section", { class: "card stack", "aria-labelledby": "now-h" },
          h("h2", { id: "now-h" }, "No talk yet"),
          h("p", { class: "muted" }, `The next talks start ${formatDayTime(slot.startsAt)}.`),
          h("button", { type: "button", class: "btn btn-primary btn-block", "data-key": "find", onclick: () => findMeATalk() }, "Find me a talk"),
        );
      }

      if (status === "Pending") {
        const slow = pendingSince && Date.now() - pendingSince > 20000;
        return h("section", { class: "card stack now-card", "aria-labelledby": "now-h", "aria-busy": requesting ? "true" : null },
          statusPill("Pending"),
          h("h2", { id: "now-h" }, placement.reason ? "Matching talks are full" : "Looking for a good fit"),
          placement.reason
            ? h("p", {}, placement.reason)
            : h("p", { class: "muted" }, slow ? "Still looking. This can take a minute when rooms are busy." : "We're checking seats, captions and the room before we send you anywhere."),
          placement.reason ? h("h3", {}, "Closest options with space") : null,
          placement.reason ? optionsList(placement.options) : null,
          placement.reason
            ? h("button", { type: "button", class: "btn btn-primary btn-block", "data-key": "find", onclick: () => findMeATalk() }, "Try again")
            : null,
        );
      }

      const { talk, room } = placement;
      return h("section", { class: "card stack now-card", "aria-labelledby": "now-h" },
        statusPill(status),
        h("h2", { id: "now-h", class: "now-title" }, talk.title),
        h("p", { class: "now-when" }, `${formatDayTime(talk.startsAt)} · `, h("strong", {}, room.name)),
        room.walkingHint ? h("p", { class: "now-walk" }, room.walkingHint) : null,
        // Report-based climate when the API sends it; otherwise the simple badges.
        room.climate
          ? climateView(room.climate, { seats: room.seats, taken: room.taken })
          : badgeList(room.badges),
        !room.climate && placement.reportedMinutesAgo != null ? h("p", { class: "report-age muted" }, `Room status reported ${ago(placement.reportedMinutesAgo)}`) : null,
        banner ? null : h("button", {
          type: "button", class: "btn btn-secondary btn-block", "data-key": "show-options",
          "aria-expanded": String(showOptions), onclick: () => { showOptions = !showOptions; paint(); },
        }, showOptions ? "Hide other options" : "Show other options"),
      );
    }

    function paint() {
      const focusedKey = document.activeElement?.closest?.("[data-key]")?.dataset.key;
      region.replaceChildren(
        bannerView() || "",
        error ? h("p", { class: "notice error", role: "alert" }, error) : "",
        h("p", { class: "section-eyebrow" }, "Current recommended talk"),
        placementView(),
        showOptions && placement?.options ? h("section", { class: "card", "aria-labelledby": "opts-h" }, h("h2", { id: "opts-h" }, "Other talks with space"), optionsList(placement.options)) : "",
        kubectlView() || "",
        h("a", { class: "btn btn-secondary btn-block find-link", href: "#/talks" }, "Browse and search talks"),
        breakSlot,
      );
      if (focusedKey) region.querySelector(`[data-key="${focusedKey}"]`)?.focus();
    }

    // ---- live updates ----
    const unsubs = [
      subscribe("placement", (data) => setPlacement(data)),
      subscribe("reroute", (data) => showReroute(data.from, data.placement, data.reason)),
      subscribe("room", (room) => {
        if (banner && room.id === banner.fromId && room.status === "OPEN" && !banner.reopened) {
          banner.reopened = true;
          announce(`${banner.fromName} has seats again. You can go back if you like.`);
          paint();
        }
      }),
      onPrefsChange(() => paint()),
    ];

    // Poll when the stream isn't connected, and quickly while a request is pending.
    const poll = setInterval(() => { if (!isLive()) refresh(); }, POLL_MS);
    const fastPoll = setInterval(() => { if (requesting && !isLive()) refresh(); }, 3000);

    paint();
    paintBreak();
    unsubs.push(subscribe("group", () => paintBreak()));
    await refresh();
    if (!placement && !autoRequested) {
      autoRequested = true;
      findMeATalk();
    }

    return () => {
      unsubs.forEach((u) => u());
      clearInterval(poll);
      clearInterval(fastPoll);
    };
  },
};
