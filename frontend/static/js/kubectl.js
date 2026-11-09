// The kubectl drawer: a bottom-sheet terminal over the paper layout, for the KubeCon crowd.
// Commands run against the app's own data (placement, group, board). It only ever shows
// random attendee IDs, room IDs and reported room facts: never names, card text or needs.

import { announce } from "./a11y.js";
import { api } from "./api.js";
import { h } from "./format.js";
import { nextBreak } from "./slots.js";
import { currentMe } from "./store.js";

const HELP = `Available commands:
  kubectl get pods                  your break group (opaque IDs only)
  kubectl get nodes                 rooms and their capacity
  kubectl describe node/<room-id>   capacity, conditions and taints for a room
  kubectl get events                recent scheduling events
  kubectl drain attendee/me         sit out the next break round to rest
  kubectl uncordon attendee/me      join the next break round again
  clear                             clear the screen`;

const pad = (s, n) => String(s).padEnd(n);
const STATUS = { here: "Running", late: "Pending", "on-the-way": "Pending" };
const REASON = { here: "", late: "(running late)", "on-the-way": "(on the way)" };

function table(rows) {
  const widths = rows[0].map((_, i) => Math.max(...rows.map((r) => String(r[i]).length)) + 3);
  return rows.map((r) => r.map((c, i) => (i === r.length - 1 ? String(c) : pad(c, widths[i]))).join("")).join("\n");
}

function nodeStatus(room) {
  if (room.status === "CLOSED") return "NotReady,SchedulingDisabled";
  if (room.status === "FULL") return "Ready,SchedulingDisabled";
  if (room.status === "INCIDENT") return "Ready (incident)";
  return "Ready";
}

const COMMANDS = {
  async "get pods"() {
    const me = currentMe()?.displayId || "attendee-me";
    const group = await api.currentGroup().catch(() => null);
    if (!group) {
      const p = await api.currentPlacement().catch(() => null);
      const line = p?.room ? [me, p.status === "Scheduled" ? "Running" : p.status || "Pending", p.room.id] : [me, "Pending", "<none>"];
      return `No break group yet.\n\n${table([["NAME", "STATUS", "NODE"], line])}`;
    }
    const rows = [["NAME", "STATUS", "NODE", ""],
      [`${me} (you)`, STATUS[group.myStatus] || "Pending", group.tableId, REASON[group.myStatus] || ""],
      ...group.members.map((m) => [m.displayId, STATUS[m.status] || "Pending", group.tableId, REASON[m.status] || ""])];
    return `podgroup/${group.id}   ${group.breakId}\n\n${table(rows)}`;
  },

  async "get nodes"() {
    const board = await api.board();
    const rows = [["NAME", "STATUS", "SEATS", "TAKEN"], ...(board.rooms || []).map((r) => [r.id, nodeStatus(r), r.seats, r.taken])];
    return table(rows);
  },

  async describe(arg) {
    const id = (arg || "").replace(/^nodes?\//, "");
    const board = await api.board();
    const room = (board.rooms || []).find((r) => r.id === id);
    if (!room) return `Error from server (NotFound): nodes "${id || "?"}" not found\nTry: kubectl get nodes`;
    const c = room.climate || {};
    const age = c.minutesAgo != null ? `reported ${c.minutesAgo}m ago` : "no reports";
    const captions = room.incident && room.incident.state !== "resolved" ? "False" : c.captions === "working" ? "True" : "Unknown";
    const taints = [];
    if (room.status === "FULL") taints.push("affinity.dev/full:NoSchedule");
    if (room.status === "CLOSED") taints.push("affinity.dev/closed:NoExecute");
    const share = room.seats ? Math.round((room.taken / room.seats) * 100) : 0;
    return [
      `Name:         ${room.id}`,
      `Display:      ${room.name}`,
      `Capacity:     affinity.dev/seats: ${room.seats}`,
      `Occupancy:    ${room.taken} / ${room.seats} (${share}%)`,
      `Taints:       ${taints.join(", ") || "<none>"}`,
      `Conditions:`,
      `  Type              Status    Message`,
      `  CaptionsWorking   ${pad(captions, 10)}${captions === "False" ? "captions down, staff alerted" : captions === "True" ? age : "no reports"}`,
      `  Noise             ${pad(c.noise ? (c.noise === "loud" ? "Loud" : "Quiet") : "Unknown", 10)}${c.noise ? age : "no reports"}`,
      `  Lighting          ${pad(c.light ? c.light[0].toUpperCase() + c.light.slice(1) : "Unknown", 10)}${c.light ? age : "no reports"}`,
      ``,
      `Facts come from attendee reports, with their age. Nothing here is measured.`,
    ].join("\n");
  },

  async "get events"() {
    const board = await api.board();
    const events = (board.events || []).slice(-10);
    if (!events.length) return "No events yet.";
    return table([["TIME", "REASON", "MESSAGE"], ...events.map((e) => [e.at, e.reason, e.message])]);
  },

  async "drain attendee/me"() {
    const brk = nextBreak();
    await api.rsvpBreak(brk.id, false);
    return `attendee/me cordoned\nevicting attendee/me from ${brk.id}\nattendee/me drained. Rest well. Run "kubectl uncordon attendee/me" to join again.`;
  },

  async "uncordon attendee/me"() {
    const brk = nextBreak();
    await api.rsvpBreak(brk.id, true);
    return `attendee/me uncordoned. You're in for ${brk.id}.`;
  },
};

async function run(line) {
  const cmd = line.trim().replace(/^kubectl\s+/, "").replace(/\s+/g, " ");
  if (!cmd || cmd === "help" || cmd === "--help" || cmd === "-h") return HELP;
  if (COMMANDS[cmd]) return COMMANDS[cmd]();
  const m = /^describe (?:node[s]?\/|node[s]? )?(\S+)$/.exec(cmd);
  if (m) return COMMANDS.describe(m[1]);
  if (cmd === "get pod" || cmd === "get po") return COMMANDS["get pods"]();
  if (cmd === "get node" || cmd === "get no") return COMMANDS["get nodes"]();
  return `error: unknown command "${cmd.split(" ")[0]}"\nRun "kubectl help" for the commands this cluster understands.`;
}

let dialog = null;

function build() {
  const output = h("pre", { class: "term-out", "aria-live": "polite", "aria-atomic": "false", tabindex: "0", "aria-label": "Terminal output" });
  const input = h("input", {
    id: "term-input", class: "term-input", type: "text", autocomplete: "off", autocapitalize: "off", spellcheck: "false",
    placeholder: "get pods",
  });
  const history = [];
  let cursor = 0;

  function print(text, cls = "") {
    const block = h("span", { class: `term-block ${cls}` }, text + "\n");
    output.append(block);
    output.scrollTop = output.scrollHeight;
  }

  async function exec(line) {
    if (line.trim() === "clear") { output.replaceChildren(); return; }
    print(`$ kubectl ${line.replace(/^kubectl\s+/, "")}`, "term-cmd");
    try {
      print(await run(line));
    } catch {
      print("Unable to connect to the server. Try again in a moment.", "term-err");
    }
  }

  const form = h("form", { class: "term-form" },
    h("label", { for: "term-input", class: "term-prompt" }, h("span", { "aria-hidden": "true" }, "$ kubectl"), h("span", { class: "visually-hidden" }, "kubectl command")),
    input,
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const line = input.value;
    if (!line.trim()) return;
    history.push(line);
    cursor = history.length;
    input.value = "";
    await exec(line);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp" && cursor > 0) { cursor -= 1; input.value = history[cursor]; e.preventDefault(); }
    if (e.key === "ArrowDown") { cursor = Math.min(history.length, cursor + 1); input.value = history[cursor] || ""; e.preventDefault(); }
  });

  const chips = h("div", { class: "term-chips" },
    ["get pods", "get nodes", "describe node/room-251", "get events", "drain attendee/me", "help"].map((c) =>
      h("button", { type: "button", class: "term-chip", onclick: () => { exec(c); input.focus(); } }, c)));

  const d = h("dialog", { class: "term-sheet", "aria-labelledby": "term-h" },
    h("div", { class: "term-bar" },
      h("span", { class: "term-dots", "aria-hidden": "true" }, h("i"), h("i"), h("i")),
      h("h2", { id: "term-h", class: "term-title" }, "kubectl · affinity cluster"),
      h("button", { type: "button", class: "term-close", onclick: () => d.close() }, "Close", h("span", { class: "visually-hidden" }, " terminal")),
    ),
    output,
    chips,
    form,
  );
  d.addEventListener("click", (e) => { if (e.target === d) d.close(); }); // tap the backdrop to close
  print("Welcome to the Affinity cluster. Attendees are Pods, rooms are Nodes.\nType a command, or tap one below. Try: kubectl help", "term-muted");
  document.body.append(d);
  return d;
}

/** Opens the drawer and focuses the prompt. */
export function openKubectl() {
  dialog ||= build();
  if (!dialog.open) dialog.showModal();
  dialog.querySelector("#term-input")?.focus();
  announce("kubectl terminal open.");
}
