// Report this room: one-thumb buttons for seats, sound, light, captions and access.
// Captions down and access problems alert staff and look different.
// Rate limit on the phone: one report per room per signal every 2 minutes.

import { announce } from "../a11y.js";
import { api } from "../api.js";
import { h } from "../format.js";
import { loadErrorView } from "../load-error.js";
import { loadMe } from "../store.js";

const LIMIT_MS = 2 * 60000;
const lastSent = new Map(); // `${roomId}|${signal}` -> time, for this visit

const I = {
  seat: '<path d="M6 11V6.5A1.5 1.5 0 0 1 7.5 5h9A1.5 1.5 0 0 1 18 6.5V11M4 11h16v4H4zM6 15v4M18 15v4"/>',
  stand: '<circle cx="12" cy="5" r="2"/><path d="M12 7.5v7M12 14.5l-3 5.5M12 14.5l3 5.5M8 10.5h8"/>',
  full: '<circle cx="12" cy="12" r="8.5"/><path d="M8 12h8"/>',
  loud: '<path d="M4 9.5h3l4-3.5v12l-4-3.5H4z"/><path d="M15 9a4 4 0 0 1 0 6M17.5 6.5a7.5 7.5 0 0 1 0 11"/>',
  quiet: '<path d="M4 9.5h3l4-3.5v12l-4-3.5H4z"/><path d="M16 10l4 4M20 10l-4 4"/>',
  dim: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  bright: '<circle cx="12" cy="12" r="3.6"/><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6 18 18M6 18l1.4-1.4M16.6 7.4 18 6"/>',
  cc: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 13h4M13 13h4M7 10h10"/>',
  ccOff: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M4 4l16 16"/>',
  access: '<path d="M12 4.5a1.6 1.6 0 1 0 0 .01M8 8.5h8M12 8.5v5l-3 6M12 13.5l3 6"/><path d="M4 4l16 16"/>',
};

export const SIGNALS = [
  { id: "seats_available", label: "Seats left", icon: I.seat },
  { id: "standing_room", label: "Standing room", icon: I.stand },
  { id: "full", label: "Full", icon: I.full },
  { id: "very_loud", label: "Too loud", icon: I.loud },
  { id: "quiet", label: "Nice and quiet", icon: I.quiet },
  { id: "too_dim", label: "Too dim", icon: I.dim },
  { id: "too_bright", label: "Too bright", icon: I.bright },
  { id: "captions_working", label: "Captions working", icon: I.cc },
  { id: "captions_down", label: "Captions down", icon: I.ccOff, staff: true },
  { id: "access_blocked", label: "Elevator or aisle problem", icon: I.access, staff: true },
];

function iconEl(paths) {
  const el = h("span", { class: "signal-icon", "aria-hidden": "true" });
  el.innerHTML = `<svg viewBox="0 0 24 24" focusable="false">${paths}</svg>`; // static icon markup
  return el;
}

export default {
  title: "Report this room",
  async render(main) {
    const { error } = await loadMe();
    if (error) { main.append(loadErrorView()); return; }

    // Which room: the one you're placed in, else the first room; you can change it.
    let rooms = [];
    let roomId = null;
    try {
      const [placement, board] = await Promise.all([api.currentPlacement().catch(() => null), api.board().catch(() => null)]);
      rooms = (board?.rooms || []).map((r) => ({ id: r.id, name: r.name }));
      roomId = placement?.room?.id || rooms[0]?.id || null;
      if (placement?.room && !rooms.some((r) => r.id === placement.room.id)) rooms.unshift({ id: placement.room.id, name: placement.room.name });
    } catch { /* handled below */ }

    const result = h("p", { class: "report-result", role: "status" });
    const roomName = () => rooms.find((r) => r.id === roomId)?.name || "this room";
    const heading = h("h1", { class: "screen-title" }, `Report ${roomName()}`);

    const picker = h("select", { id: "room-pick", class: "input" },
      rooms.map((r) => h("option", { value: r.id, selected: r.id === roomId || null }, r.name)));
    picker.addEventListener("change", () => {
      roomId = picker.value;
      heading.textContent = `Report ${roomName()}`;
      result.textContent = "";
    });
    const changeRoom = h("details", { class: "change-room" },
      h("summary", {}, "Change room"),
      h("div", { class: "field" }, h("label", { for: "room-pick" }, "Which room are you in?"), picker),
    );

    async function send(signal, button) {
      if (!roomId) return;
      const key = `${roomId}|${signal.id}`;
      const since = Date.now() - (lastSent.get(key) || 0);
      if (since < LIMIT_MS) {
        const wait = Math.ceil((LIMIT_MS - since) / 60000);
        result.textContent = `Thanks, we already have your "${signal.label}" report for ${roomName()}. You can send it again in ${wait} min.`;
        result.className = "report-result info";
        announce(result.textContent);
        return;
      }
      button.disabled = true;
      try {
        const res = await api.reportRoom(roomId, signal.id);
        lastSent.set(key, Date.now());
        const others = res?.agreeing ?? 0;
        const msg = res?.staffAlerted
          ? "Thanks. Staff have been alerted."
          : others > 0 ? `Thanks. ${others} ${others === 1 ? "other person" : "others"} said the same.` : "Thanks. Your report helps everyone pick a good room.";
        result.textContent = msg;
        result.className = `report-result ${res?.staffAlerted ? "staff" : "ok"}`;
        announce(msg);
      } catch {
        result.textContent = "We couldn't send that. Please try again in a moment.";
        result.className = "report-result error";
      } finally {
        button.disabled = false;
      }
    }

    const grid = h("ul", { class: "signal-grid" }, SIGNALS.map((sig) => {
      const btn = h("button", { type: "button", class: `signal${sig.staff ? " signal-staff" : ""}` },
        iconEl(sig.icon),
        h("span", { class: "signal-label" }, sig.label),
        sig.staff ? h("span", { class: "signal-note" }, "Staff will be alerted.") : null,
      );
      btn.addEventListener("click", () => send(sig, btn));
      return h("li", { class: sig.staff ? "wide" : "" }, btn);
    }));

    main.append(
      heading,
      rooms.length
        ? h("p", { class: "muted" }, "Tap what you notice. It takes one second and helps everyone find a good room.")
        : h("p", { class: "notice" }, "We couldn't load the room list. Please try again in a moment."),
      rooms.length ? changeRoom : "",
      result,
      rooms.length ? grid : "",
    );
  },
};
