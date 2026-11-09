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
  // ?attendees=1000 sizes the crowd for the board's performance check (50–2000).
  const wanted = Number(new URLSearchParams(location.search).get("attendees")) || 200;
  const crowd = Math.min(2000, Math.max(50, wanted));
  while (attendees.length < crowd) {
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
  // Room climate comes only from attendee reports. Seed a few, with their age.
  const seeds = [{ noise: "quiet", light: "good" }, { noise: "loud" }, { light: "dim" }, {}];
  rooms.forEach((r, i) => { r.climate = { ...seeds[i % seeds.length], at: Date.now() - (2 + i * 3) * 60000 }; });
  // "Alone" = not yet in a break group. It starts high and the finale brings it to 0.
  return { rooms, attendees, groups: [], alone: attendees.length, events: [] };
}

function updateStatus(room) {
  const before = room.status;
  if (room.closed) room.status = "CLOSED";
  else if (room.incident && room.incident.state !== "resolved") room.status = "INCIDENT";
  else if (room.taken >= room.seats) room.status = "FULL";
  else room.status = "OPEN";
  if (before && before !== room.status) emit("room", { id: room.id, name: room.name, status: room.status });
}

function stamp() {
  return new Intl.DateTimeFormat("en-US", { timeZone: "America/Denver", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date());
}

let eventSeq = 0;
function logEvent(reason, message) {
  eventSeq += 1;
  const ev = { id: `ev-${eventSeq}`, at: stamp(), reason, message };
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
      climate: climateFor(r),
    })),
    attendees: state.attendees.map((a) => ({ ...a })),
    groups: state.groups.map((g) => ({ ...g, members: [...g.members] })),
    alone: state.alone,
    feltHeard: heardTotal ? Math.round((heardYes / heardTotal) * 100) : state.feltHeard ?? null,
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
  /** Everyone in the phone's group arrives now (for rehearsing "Exchange stars"). */
  everyoneHere() {
    if (!myGroup) return;
    myGroup.members.forEach((m) => { m.status = "here"; });
    emit("group", { group: groupCopy() });
  },
  /** Forms the phone's group now; startedMinutesAgo > 3 shows the no-show message. */
  formMyGroup(opts = {}) { formMyGroup("brk-tue-1530", opts); },
  closeBusiest() {
    ensureState();
    const busiest = [...state.rooms].filter((r) => !r.closed).sort((a, b) => b.taken / b.seats - a.taken / a.seats)[0];
    if (busiest) demo.closeRoom(busiest.id);
  },
  /** Closes the room the phone's attendee is placed in, to show a reroute. */
  closeMine() {
    if (myPlacement?.room?.id) demo.closeRoom(myPlacement.room.id);
  },
  reopenRoom(id) {
    ensureState();
    const room = state.rooms.find((r) => r.id === id);
    if (!room) return;
    room.closed = false;
    updateStatus(room);
    logEvent("Ready", `${room.id} open`);
  },
  closeRoom(id) {
    ensureState();
    const busiest = state.rooms.find((r) => r.id === id);
    if (!busiest || busiest.closed) return;
    busiest.closed = true;
    updateStatus(busiest);
    logEvent("Evicted", `${busiest.id} closed`);
    const evicted = state.attendees.filter((a) => a.roomId === busiest.id);
    const targets = state.rooms.filter((r) => !r.closed && r.taken < r.seats).map((r) => r.id).slice(0, 2);
    if (evicted.length) logEvent("Evicted", `${evicted.length} pods: ${busiest.id} closed → ${targets.join(", ") || "Pending"}`);
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
    state.feltHeard = 94; // rehearsal value: everyone reflected after the finale break
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
    // Nobody is grouped alone: a single leftover joins the previous group (groups of 2–4).
    if (members.length === 1 && state.groups.length) {
      const last = state.groups[state.groups.length - 1];
      members[0].groupId = last.id;
      last.members.push(members[0].displayId);
      break;
    }
    const id = `g-${randomId()}`;
    const tableId = TABLES[t % TABLES.length];
    t += 1;
    members.forEach((m) => { m.groupId = id; });
    state.groups.push({ id, tableId, members: members.map((m) => m.displayId) });
    if (i < 9) logEvent("Grouped", `${id} → ${tableId} (${members.length} people)`);
  }
  state.alone = state.attendees.filter((a) => !a.groupId).length;
  emit("group", { count: state.groups.length });
  emit("board", snapshot());
}

function reroute(fromRoom) {
  if (!myPlacement?.talk) return;
  const to = openRooms(fromRoom.id)[0];
  if (!to) return;
  const talk = talks.find((t) => t.room === to.id && t.slot === myPlacement.talk.slot) || myPlacement.talk;
  myPlacement = placementFor(talk, to, "Scheduled");
  myPlacement.kubectl = `${me.displayId}   Evicted → Pending → Scheduled   ${to.id}`;
  emit("reroute", { id: `rr-${randomId()}`, from: { id: fromRoom.id, name: fromRoom.name }, reason: fromRoom.closed ? "closed" : "full", placement: { ...myPlacement } });
}

function openRooms(exceptId) {
  return state.rooms
    .filter((r) => r.status === "OPEN" && r.id !== exceptId)
    .sort((a, b) => a.taken / a.seats - b.taken / b.seats);
}

const WALK = {
  "room-101": "First floor, past registration on the left.",
  "room-155": "First floor, end of the east hallway.",
  "room-251": "Second floor, take the elevator by the coffee bar.",
  "room-hall-b": "Ground level, follow signs for Hall B.",
};

function optionsFor(slot, exceptId) {
  return openRooms(exceptId).slice(0, 3).map((r) => {
    const t = talks.find((x) => x.slot === slot && x.room === r.id);
    return t && { talk: { id: t.id, title: t.title, startsAt: t.startsAt, slot }, room: { id: r.id, name: r.name, seatsLeft: r.seats - r.taken } };
  }).filter(Boolean);
}

/** Only what attendees reported, with how long ago. Never a measured number. */
function climateFor(r) {
  const c = r.climate || {};
  const captions = r.incident && r.incident.state !== "resolved" ? "down" : c.captions || null;
  return {
    noise: c.noise || null,
    light: c.light || null,
    captions,
    minutesAgo: c.at ? Math.max(0, Math.round((Date.now() - c.at) / 60000)) : null,
  };
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
    room: { id: r.id, name: r.name, seatsLeft, seats: r.seats, taken: r.taken, badges, walkingHint: WALK[r.id] || null, climate: climateFor(r) },
    reason: null,
    options: optionsFor(talk.slot, r.id),
    kubectl: `${me.displayId}   ${status === "Scheduled" ? "Running" : status}   ${r.id}`,
    reportedMinutesAgo: Math.floor(Math.random() * 5),
  };
}

// ---- the phone's own break group ----
let myGroup = null;
const myConnections = [];
let groupTimer = null;
const MEMBER_CARDS = [
  { pronouns: "she/her", howToTalk: "Give me time to finish my words.", workingOn: "making apps start faster", askMeAbout: "checkpoint and restore" },
  { pronouns: "they/them", howToTalk: "Say your name when you walk up.", workingOn: "testing startup speed in CI", askMeAbout: "flaky benchmarks", comfort: "recharge" },
  { pronouns: "he/him", howToTalk: "I do better one-on-one. Come say hi when it's quieter.", workingOn: "smaller container images", askMeAbout: "distroless images" },
];

function formMyGroup(breakId, { startedMinutesAgo = null } = {}) {
  const names = [...FAKE_NAMES].sort(() => Math.random() - 0.5);
  const startsAt = startedMinutesAgo == null
    ? new Date(Date.now() + 2 * 60000).toISOString()
    : new Date(Date.now() - startedMinutesAgo * 60000).toISOString();
  myGroup = {
    id: `g-${randomId()}`,
    breakId: breakId || "brk-tue-1530",
    tableId: "tbl-quiet-window",
    place: "the quiet table by the window",
    landmark: "Next to the red couch",
    directions: "Second floor lounge, past the coffee bar, by the tall windows.",
    startsAt,
    opener: "How do you test startup speed?",
    myStatus: null,
    members: MEMBER_CARDS.slice(0, 2).map((card, i) => ({
      displayId: `attendee-${randomId()}`,
      name: names[i],
      ...card,
      status: "on-the-way",
    })),
  };
  emit("group", { group: groupCopy() });
  // One person arrives a little later; the second later still (or never, for a group that
  // already started, to show the no-show rule).
  setTimeout(() => {
    if (!myGroup) return;
    myGroup.members[0].status = "here";
    emit("group", { group: groupCopy() });
  }, 12000);
  if (startedMinutesAgo == null) setTimeout(() => {
    if (!myGroup) return;
    myGroup.members[1].status = "here";
    emit("group", { group: groupCopy() });
  }, 25000);
}

function groupCopy() {
  return myGroup ? { ...myGroup, members: myGroup.members.map((m) => ({ ...m })) } : null;
}

// ---- Grow: private reflections, an adaptive comfort ladder, independence ----
// Like reinforcement: a good, brave break steps you up a rung; a hard one steps you back,
// kindly. The top rungs are doing it without the app.
const LADDER = [
  { level: 1, title: "Join a matched table", detail: "We pick the people and suggest the first question." },
  { level: 2, title: "Ask the first question", detail: "We give a hint; you phrase it your way." },
  { level: 3, title: "Host a round", detail: "Make sure everyone at the table gets a turn." },
  { level: 4, title: "Start one on your own", detail: "Walk up to someone without a match. You've got this." },
];
const myGrowth = { level: 1, reflections: [], startedOnOwn: 0, wins: [] };
let heardYes = 0, heardTotal = 0;

function nextChallenge() {
  const next = LADDER.find((r) => r.level === Math.min(4, myGrowth.level + (myGrowth.level === 4 ? 0 : 0))) || LADDER[0];
  if (myGrowth.level >= 4) return { title: "Start a conversation on your own", detail: "No match needed. Then tell us here so you can see how far you've come." };
  return { title: LADDER[myGrowth.level]?.title || next.title, detail: LADDER[myGrowth.level]?.detail || next.detail };
}

function growthCopy() {
  return {
    level: myGrowth.level,
    ladder: LADDER,
    nextChallenge: nextChallenge(),
    comfortTrend: myGrowth.reflections.map((r) => r.comfort),
    wins: [...myGrowth.wins].reverse(),
    startedOnOwn: myGrowth.startedOnOwn,
    breaks: myGrowth.reflections.length,
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
    return myCard ? { ...myCard, displayId: me?.displayId } : null;
  },
  async saveCard(card) {
    await sleep(250);
    if (!me) await api.createAttendee();
    myCard = { ...card };
    return { ...myCard, displayId: me.displayId };
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
  async requestPlacement(slot, { preferRoom = null } = {}) {
    ensureState();
    if (!me) await api.createAttendee();
    await sleep(400);
    myPlacement = { status: "Pending", talk: null, room: null, reason: null, slot, kubectl: `${me.displayId}   Pending   <none>` };
    setTimeout(() => {
      const preferred = preferRoom && state.rooms.find((r) => r.id === preferRoom && r.status === "OPEN");
      // Low-sensory: prefer a room people reported as quiet.
      const quiet = myCard?.comfort === "low" && openRooms().find((r) => r.climate?.noise === "quiet");
      const room = preferred || quiet || openRooms()[0];
      const talk = room && talks.find((t) => t.slot === slot && t.room === room.id);
      if (!room || !talk) {
        myPlacement = {
          status: "Pending", talk: null, room: null, slot,
          reason: "Every matching talk is full right now. We'll keep looking and tell you when a seat opens.",
          options: [],
          kubectl: `Pending: 0/${state.rooms.length} nodes available: ${state.rooms.length} Insufficient affinity.dev/seats`,
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
    clearTimeout(groupTimer);
    if (going && !myGroup) groupTimer = setTimeout(() => formMyGroup(breakId), 2500);
    return { breakId, status: going ? "going" : "not-going" };
  },
  async checkIn(groupId, status = "here") {
    await sleep(250);
    if (myGroup?.id === groupId) {
      myGroup.myStatus = status;
      emit("group", { group: groupCopy() });
    }
    return { groupId, status };
  },
  async currentGroup() {
    await sleep(150);
    return groupCopy();
  },
  async leaveGroup(groupId) {
    await sleep(250);
    if (myGroup?.id === groupId) {
      myGroup = null;
      emit("group", { group: null });
    }
    return { ok: true };
  },
  async proposeConnection(displayId, groupId = null) {
    await sleep(300);
    // In the mock the other person agrees a moment later.
    const member = myGroup?.members.find((m) => m.displayId === displayId);
    setTimeout(() => {
      if (!member || myConnections.some((c) => c.displayId === displayId)) return;
      myConnections.push({
        displayId, name: member.name, pronouns: member.pronouns, workingOn: member.workingOn,
        place: myGroup?.place || "a break table", landmark: myGroup?.landmark || null,
        metAt: myGroup?.startsAt || new Date().toISOString(), groupId,
      });
      emit("group", { group: groupCopy() });
    }, 1500);
    return { displayId, status: "pending" };
  },
  async reflect(r) {
    await sleep(300);
    myGrowth.reflections.push({ ...r, at: Date.now() });
    if (r.everyoneTurn) { heardTotal += 1; if (r.everyoneTurn === "yes") heardYes += 1; }
    const brave = r.askedQuestion || r.sharedWork || r.hosted;
    const wins = [];
    if (r.askedQuestion) wins.push("You asked a question");
    if (r.sharedWork) wins.push("You shared what you're working on");
    if (r.hosted) wins.push("You hosted a round so everyone got a turn");
    let move = "stay";
    if (r.comfort >= 4 && brave && myGrowth.level < 4) { myGrowth.level += 1; move = "up"; }
    else if (r.comfort <= 2 && myGrowth.level > 1) { myGrowth.level -= 1; move = "gentler"; }
    wins.forEach((w) => myGrowth.wins.push({ text: w, at: Date.now() }));
    emit("board", snapshot());
    return { move, wins, growth: growthCopy() };
  },
  async growth() {
    await sleep(150);
    return growthCopy();
  },
  async startedOnOwn() {
    await sleep(200);
    myGrowth.startedOnOwn += 1;
    myGrowth.wins.push({ text: "You started a conversation on your own", at: Date.now() });
    return growthCopy();
  },
  async connections() {
    await sleep(150);
    return myConnections.map((c) => ({ ...c }));
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
    ensureState();
    await sleep(300);
    const room = state.rooms.find((r) => r.id === roomId);
    const staffAlerted = signal === "captions_down" || signal === "access_blocked";
    if (room) {
      const c = (room.climate ||= {});
      const effects = {
        very_loud: { noise: "loud" }, quiet: { noise: "quiet" },
        too_dim: { light: "dim" }, too_bright: { light: "bright" },
        captions_working: { captions: "working" },
      };
      Object.assign(c, effects[signal] || {}, { at: Date.now() });
      if (signal === "full") { room.taken = room.seats; updateStatus(room); }
      if (staffAlerted && (!room.incident || room.incident.state === "resolved")) {
        room.incident = { id: `inc-${randomId()}`, type: signal === "captions_down" ? "captions" : "access", reportedAt: stamp(), state: "open", reports: 1 };
        updateStatus(room);
        logEvent("Incident", `${room.id} ${signal === "captions_down" ? "captions down" : "access problem"}`);
        emit("incident", { roomId: room.id, ...room.incident });
      } else if (staffAlerted) {
        room.incident.reports += 1;
      }
      logEvent("Reported", `${room.id} ${signal}`);
    }
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
  return {
    id: t.id, title: t.title, abstract: t.abstract, room: t.room, roomName: t.roomName, startsAt: t.startsAt, slot: t.slot, badges,
    seats: room?.seats, taken: room?.taken, climate: room ? climateFor(room) : null,
  };
}

export const fakeName = () => pick(FAKE_NAMES);
export const fixtures = { SLOTS, SLOT_TIMES, ROOMS, TABLES, TABLE_NAMES };
