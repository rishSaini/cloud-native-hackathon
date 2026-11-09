// Synthetic data with the same methods as api.js, so every screen runs before the backend exists.
// IDs follow the shared contract in docs/tasks/*.md (rooms, slots, breaks, tables).
// Names here are clearly made up. Card text stays in memory only, never in storage.

const SLOTS = ["tue-0900", "tue-1030", "tue-1330", "tue-1430", "tue-1600"];
const SLOT_TIMES = {
  "tue-0900": "2026-11-10T09:00:00-07:00",
  "tue-1030": "2026-11-10T10:30:00-07:00",
  "tue-1330": "2026-11-10T13:30:00-07:00",
  "tue-1430": "2026-11-10T14:30:00-07:00",
  "tue-1600": "2026-11-10T16:00:00-07:00",
};
const ROOMS = [
  { id: "room-101", name: "Room 101", seats: 40 },
  { id: "room-155", name: "Room 155", seats: 80 },
  { id: "room-251", name: "Room 251", seats: 120 },
  { id: "room-hall-b", name: "Hall B", seats: 300 },
];
const TABLES = ["tbl-01", "tbl-02", "tbl-03", "tbl-04", "tbl-05", "tbl-06", "tbl-quiet-window"];
const TABLE_NAMES = { "tbl-quiet-window": "the quiet table by the window" };
const FAKE_NAMES = ["Juniper", "Marlo", "Quill", "Sprocket", "Wren", "Pixel", "Bramble", "Tango", "Nimbus", "Ziggy", "Clover", "Orbit"];

const TITLES = [
  ["Kubernetes for your first week", "Faster app startup with checkpoints", "Secrets without the sweat", "Scheduling, explained with pizza"],
  ["Security for beginners", "eBPF in plain words", "Running Postgres on Kubernetes", "What we learned from 1,000 clusters"],
  ["Observability that answers questions", "GitOps without tears", "Platform teams that people like", "Cost: the other SLO"],
  ["Accessible dashboards", "Progressive delivery in practice", "Your first operator", "Making apps start faster tomorrow"],
  ["Multi-tenant clusters done kindly", "Debugging DNS, again", "Edge clusters on a budget", "Lightning talks"],
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const randomId = () => Math.random().toString(36).slice(2, 6).padEnd(4, "0");

// ---- tiny event bus, same event types as /api/stream ----
const handlers = new Map();
export function on(type, fn) {
  if (!handlers.has(type)) handlers.set(type, new Set());
  handlers.get(type).add(fn);
  start();
  return () => handlers.get(type)?.delete(fn);
}
function emit(type, data) {
  handlers.get(type)?.forEach((fn) => fn(data));
  handlers.get("*")?.forEach((fn) => fn({ type, data }));
}

// ---- state ----
const talks = SLOTS.flatMap((slot, i) =>
  ROOMS.map((room, j) => ({
    id: `t-${i}${j}`,
    title: TITLES[i][j],
    abstract: `A friendly session on ${TITLES[i][j].toLowerCase()}. Good for people who want practical steps they can try next week.`,
    slot,
    room: room.id,
    roomName: room.name,
    startsAt: SLOT_TIMES[slot],
  })),
);

let state;
let me;
let myCard = null;
let myPlacement = null;
let ticker = null;

function freshState() {
  const rooms = ROOMS.map((r) => ({ ...r, taken: 0, status: "OPEN", incident: null }));
  const attendees = [];
  const seen = new Set();
  while (attendees.length < 200) {
    const id = `attendee-${randomId()}`;
    if (seen.has(id)) continue;
    seen.add(id);
    attendees.push({ displayId: id, roomId: null, groupId: null });
  }
  // Fill rooms unevenly so the board has something to show.
  const weights = [0.12, 0.22, 0.36, 0.3];
  for (const a of attendees) {
    let r = Math.random();
    let idx = 0;
    while (idx < weights.length - 1 && r > weights[idx]) { r -= weights[idx]; idx += 1; }
    const room = rooms[idx];
    if (room.taken < room.seats) { a.roomId = room.id; room.taken += 1; }
  }
  rooms.forEach(updateStatus);
  return { rooms, attendees, groups: [], alone: 0, events: [] };
}

function updateStatus(room) {
  if (room.incident && room.incident.state !== "resolved") room.status = "INCIDENT";
  else if (room.closed) room.status = "CLOSED";
  else if (room.taken >= room.seats) room.status = "FULL";
  else room.status = "OPEN";
}

function stamp() {
  return new Intl.DateTimeFormat("en-US", { timeZone: "America/Denver", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date());
}

function logEvent(reason, message) {
  const ev = { at: stamp(), reason, message };
  state.events.push(ev);
  if (state.events.length > 50) state.events.shift();
  emit("board", snapshot());
  return ev;
}

function snapshot() {
  return {
    rooms: state.rooms.map((r) => ({
      id: r.id, name: r.name, seats: r.seats, taken: r.taken, status: r.status,
      incident: r.incident ? { ...r.incident } : null,
    })),
    attendees: state.attendees.map((a) => ({ ...a })),
    groups: state.groups.map((g) => ({ ...g, members: [...g.members] })),
    alone: state.alone,
    events: state.events.slice(-12),
  };
}

function ensureState() {
  if (!state) state = freshState();
}

function start() {
  ensureState();
  if (ticker) return;
  ticker = setInterval(tick, 4000);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { clearInterval(ticker); ticker = null; } else if (!ticker) ticker = setInterval(tick, 4000);
  });
}

function moveAttendee(a, toRoom, reason = "Scheduled") {
  const from = state.rooms.find((r) => r.id === a.roomId);
  if (from) from.taken -= 1;
  a.roomId = toRoom.id;
  toRoom.taken += 1;
  if (from) updateStatus(from);
  updateStatus(toRoom);
  return logEvent(reason, `${a.displayId} → ${toRoom.id}`);
}

function tick() {
  const roll = Math.random();
  const open = state.rooms.filter((r) => r.status === "OPEN");
  if (roll < 0.6 && open.length) {
    const unplaced = state.attendees.filter((a) => !a.roomId);
    const a = unplaced.length ? pick(unplaced) : pick(state.attendees);
    moveAttendee(a, pick(open));
  } else if (roll < 0.7) {
    openIncident();
  } else if (roll < 0.85) {
    const inc = state.rooms.find((r) => r.incident && r.incident.state !== "resolved");
    if (inc) resolveIncident(inc.id);
  }
}

// ---- demo controls (board shortcuts drive these) ----
export const demo = {
  closeBusiest() {
    ensureState();
    const busiest = [...state.rooms].filter((r) => !r.closed).sort((a, b) => b.taken / b.seats - a.taken / a.seats)[0];
    if (!busiest) return;
    busiest.closed = true;
    updateStatus(busiest);
    logEvent("Evicted", `${busiest.id} closed`);
    const evicted = state.attendees.filter((a) => a.roomId === busiest.id);
    for (const a of evicted) {
      const target = state.rooms.filter((r) => !r.closed && r.taken < r.seats).sort((x, y) => x.taken / x.seats - y.taken / y.seats)[0];
      if (target) moveAttendee(a, target, "Scheduled");
      else { a.roomId = null; busiest.taken -= 1; }
    }
    if (myPlacement?.room?.id === busiest.id) reroute(busiest);
  },
  formGroups() { formGroups(); },
  openIncident() { openIncident(true); },
  finale() {
    formGroups(true);
    state.alone = 0;
    emit("board", snapshot());
  },
  reset() {
    state = freshState();
    emit("board", snapshot());
  },
};

function openIncident(force = false) {
  const candidates = state.rooms.filter((r) => !r.incident || r.incident.state === "resolved");
  if (!candidates.length) return;
  if (!force && Math.random() < 0.5) return;
  const room = pick(candidates);
  room.incident = { id: `inc-${randomId()}`, type: "captions", reportedAt: stamp(), state: "open", reports: 3 };
  updateStatus(room);
  logEvent("Incident", `${room.id} captions down`);
  emit("incident", { roomId: room.id, ...room.incident });
}

function resolveIncident(roomId) {
  const room = state.rooms.find((r) => r.id === roomId);
  if (!room?.incident) return;
  room.incident.state = "resolved";
  room.incident.fixedAt = stamp();
  updateStatus(room);
  logEvent("Fixed", `${room.id} captions working`);
  emit("incident", { roomId: room.id, ...room.incident });
}

function formGroups(everyone = false) {
  ensureState();
  const pool = state.attendees.filter((a) => !a.groupId);
  const take = everyone ? pool : pool.slice(0, Math.min(pool.length, 21));
  let t = 0;
  for (let i = 0; i < take.length; i += 3) {
    const members = take.slice(i, i + 3);
    const id = `g-${randomId()}`;
    const tableId = TABLES[t % TABLES.length];
    t += 1;
    members.forEach((m) => { m.groupId = id; });
    state.groups.push({ id, tableId, members: members.map((m) => m.displayId) });
    if (i < 9) logEvent("Grouped", `${id} → ${tableId} (${members.length} people)`);
  }
  state.alone = everyone ? 0 : Math.max(0, state.attendees.filter((a) => !a.groupId).length % 3);
  emit("group", { count: state.groups.length });
  emit("board", snapshot());
}

function reroute(fromRoom) {
  const to = state.rooms.filter((r) => !r.closed && r.status !== "FULL" && r.id !== fromRoom.id)[0];
  if (!to || !myPlacement) return;
  const talk = talks.find((t) => t.room === to.id && t.slot === myPlacement.talk.slot) || myPlacement.talk;
  myPlacement = placementFor(talk, to, "Scheduled");
  emit("reroute", { from: { id: fromRoom.id, name: fromRoom.name }, placement: myPlacement });
}

function placementFor(talk, room, status) {
  const r = state.rooms.find((x) => x.id === room.id) || room;
  const seatsLeft = Math.max(0, r.seats - (r.taken || 0));
  const badges = [];
  if (seatsLeft > 0) badges.push("seats");
  if (!r.incident || r.incident.state === "resolved") badges.push("captions");
  return {
    status,
    talk: { id: talk.id, title: talk.title, startsAt: talk.startsAt, slot: talk.slot },
    room: { id: r.id, name: r.name, seatsLeft, badges },
    reason: null,
    kubectl: `${me.displayId}   ${status === "Scheduled" ? "Running" : status}   ${r.id}`,
    reportedMinutesAgo: Math.floor(Math.random() * 5),
  };
}

// ---- API methods (same names and shapes as api.js) ----
export const api = {
  async createAttendee() {
    await sleep(200);
    if (!me) me = { attendeeId: `a-${randomId()}${randomId()}`, displayId: `attendee-${randomId()}` };
    return { ...me };
  },
  async getCard() {
    await sleep(150);
    return myCard ? { ...myCard } : null;
  },
  async saveCard(card) {
    await sleep(250);
    if (!me) await api.createAttendee();
    myCard = { ...card };
    return { ...myCard };
  },
  async deleteCard() {
    await sleep(250);
    myCard = null;
    myPlacement = null;
    me = null;
    return null;
  },
  async shareCard() {
    await sleep(200);
    const token = randomId() + randomId() + randomId();
    return { url: `${location.origin}/c/${token}`, expiresInSeconds: 600 };
  },
  async requestPlacement(slot) {
    ensureState();
    if (!me) await api.createAttendee();
    await sleep(400);
    myPlacement = { status: "Pending", talk: null, room: null, reason: null, kubectl: `${me.displayId}   Pending   <none>` };
    setTimeout(() => {
      const room = state.rooms.filter((r) => r.status === "OPEN").sort((a, b) => a.taken / a.seats - b.taken / b.seats)[0];
      const talk = talks.find((t) => t.slot === slot && t.room === room?.id) || talks.find((t) => t.slot === slot);
      if (!room || !talk) {
        myPlacement = {
          status: "Pending", talk: null, room: null,
          reason: "Every matching talk is full right now. We'll keep looking.",
          kubectl: `Pending: 0/${state.rooms.length} nodes available: Insufficient affinity.dev/seats`,
        };
      } else {
        myPlacement = placementFor(talk, room, "Scheduled");
      }
      emit("placement", { ...myPlacement });
    }, 1400);
    return { status: "Pending" };
  },
  async currentPlacement() {
    await sleep(150);
    return myPlacement ? { ...myPlacement } : null;
  },
  async rsvpBreak(breakId, going = true) {
    await sleep(250);
    return { breakId, status: going ? "going" : "not-going" };
  },
  async checkIn(groupId, status = "here") {
    await sleep(250);
    return { groupId, status };
  },
  async proposeConnection(displayId) {
    await sleep(300);
    return { displayId, status: "pending" };
  },
  async block() {
    await sleep(300);
    return { ok: true };
  },
  async safetyReport() {
    await sleep(400);
    return { ok: true };
  },
  async searchTalks(q) {
    ensureState();
    await sleep(250);
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const scored = talks
      .map((t) => ({ t, s: words.filter((w) => `${t.title} ${t.abstract}`.toLowerCase().includes(w)).length }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .map((x) => decorate(x.t));
    return scored.length
      ? { hits: scored, total: scored.length }
      : { hits: talks.slice(0, 4).map(decorate), total: 0, note: "No talks matched. Here are a few to start with." };
  },
  async ask() {
    ensureState();
    await sleep(1500);
    const cited = [talks[0], talks[15]];
    return {
      answer: `Two talks look like a good fit. "${cited[0].title}" walks through the basics step by step, and "${cited[1].title}" covers practical tricks you can try the same day.`,
      talkIds: cited.map((t) => t.id),
      talks: cited.map(decorate),
    };
  },
  async reportRoom(roomId, signal) {
    await sleep(300);
    const staffAlerted = signal === "captions_down" || signal === "access_blocked";
    return { agreeing: Math.floor(Math.random() * 5), staffAlerted };
  },
  async board() {
    ensureState();
    start();
    await sleep(100);
    return snapshot();
  },
  async staffIncidents() {
    ensureState();
    await sleep(150);
    return state.rooms
      .filter((r) => r.incident && r.incident.state !== "resolved")
      .map((r) => ({ id: r.incident.id, room: r.id, roomName: r.name, kind: r.incident.type, state: r.incident.state, openedAt: r.incident.reportedAt, reports: r.incident.reports }));
  },
  async updateIncident(id, patch) {
    ensureState();
    await sleep(200);
    const room = state.rooms.find((r) => r.incident?.id === id);
    if (!room) return null;
    if (patch.state === "resolved") resolveIncident(room.id);
    else { room.incident.state = patch.state; updateStatus(room); emit("board", snapshot()); }
    return { id, ...patch };
  },
};

function decorate(t) {
  const room = state?.rooms.find((r) => r.id === t.room);
  const badges = [];
  if (room) {
    badges.push(room.status === "FULL" ? "full" : "seats");
    if (room.incident && room.incident.state !== "resolved") badges.push("captions-down");
    else badges.push("captions");
  }
  return { id: t.id, title: t.title, abstract: t.abstract, room: t.room, roomName: t.roomName, startsAt: t.startsAt, slot: t.slot, badges };
}

export const fakeName = () => pick(FAKE_NAMES);
export const fixtures = { SLOTS, SLOT_TIMES, ROOMS, TABLES, TABLE_NAMES };
