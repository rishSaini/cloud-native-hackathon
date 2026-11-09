// The real API client. Every method falls back to mock-api.js when the page URL has mock=1,
// or when its endpoint doesn't exist yet (FastAPI's route-level 404). The "Demo data" badge
// shows whenever any method is using the mock.
//
// Privacy: request bodies carry card text, questions and reports, so they are never put in
// URLs and never logged. Errors carry only the HTTP status and path.

import { api as mock, demo as mockDemo } from "./mock-api.js";

const params = new URLSearchParams(location.search + "&" + (location.hash.split("?")[1] || ""));
const forceMock = params.get("mock") === "1";

// In mock mode, expose the demo controls for rehearsals: affinityDemo.closeMine() shows a reroute.
if (forceMock) window.affinityDemo = mockDemo;

const mockedMethods = new Set();
const mockListeners = new Set();

export function isMock() {
  return forceMock || mockedMethods.size > 0;
}

export function onMockChange(fn) {
  mockListeners.add(fn);
  return () => mockListeners.delete(fn);
}

function useMockFor(name) {
  const before = isMock();
  mockedMethods.add(name);
  if (!before) mockListeners.forEach((fn) => fn(true));
}

export class ApiError extends Error {
  constructor(status, path) {
    super(`Request to ${path} failed (HTTP ${status})`);
    this.status = status;
    this.path = path;
  }
}

/** Thrown when the route itself is missing on the server (not a "not found" for real data). */
class MissingRoute extends ApiError {}

async function request(method, path, body) {
  const init = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, path);
  }
  if (res.status === 204) return null;
  if (res.status === 404 || res.status === 405) {
    // FastAPI answers an unknown route with exactly {"detail": "Not Found"} or "Method Not Allowed".
    const data = await res.json().catch(() => null);
    if (data && (data.detail === "Not Found" || data.detail === "Method Not Allowed")) throw new MissingRoute(res.status, path);
    if (res.status === 404) return null;
  }
  if (!res.ok) throw new ApiError(res.status, path);
  const type = res.headers.get("content-type") || "";
  return type.includes("application/json") ? res.json() : null;
}

/** Wraps a real call so it uses the mock when forced, or when the route doesn't exist yet. */
function withFallback(name, real) {
  return async (...args) => {
    if (forceMock || mockedMethods.has(name)) return mock[name](...args);
    try {
      return await real(...args);
    } catch (err) {
      if (err instanceof MissingRoute) {
        useMockFor(name);
        return mock[name](...args);
      }
      throw err;
    }
  };
}

const enc = encodeURIComponent;

// Normalizes search hits from /api/talks/search or the original /api/search.
function normalizeHits(data) {
  const hits = (data?.hits || []).map((h) => ({
    id: h.id,
    title: h.title || h.id,
    abstract: h.abstract || "",
    room: h.room || null,
    roomName: h.roomName || h.room_name || h.room || null,
    startsAt: h.startsAt || h.starts_at || null,
    slot: h.slot || null,
    badges: h.badges || [],
  }));
  return { hits, total: data?.total ?? hits.length, note: data?.note || null };
}

export const api = {
  createAttendee: withFallback("createAttendee", () => request("POST", "/api/attendees", {})),
  getCard: withFallback("getCard", () => request("GET", "/api/card")),
  saveCard: withFallback("saveCard", (card) => request("PUT", "/api/card", card)),
  deleteCard: withFallback("deleteCard", () => request("DELETE", "/api/card")),
  shareCard: withFallback("shareCard", () => request("POST", "/api/card/share", {})),

  // preferRoom asks for a specific room (Undo after a reroute, or picking another option). Confirm with Rishabh.
  requestPlacement: withFallback("requestPlacement", (slot, { preferRoom = null } = {}) =>
    request("POST", "/api/placements", preferRoom ? { slot, preferRoom } : { slot })),
  currentPlacement: withFallback("currentPlacement", async () => {
    const data = await request("GET", "/api/placements/current");
    return data?.placement ?? data;
  }),

  rsvpBreak: withFallback("rsvpBreak", (breakId, going = true) =>
    request("POST", `/api/breaks/${enc(breakId)}/rsvp`, { going })),
  checkIn: withFallback("checkIn", (groupId, status = "here") =>
    request("POST", `/api/groups/${enc(groupId)}/check-in`, { status })),
  // Not in the task plans yet (confirm with Rishabh): the person's current break group, and leaving it.
  currentGroup: withFallback("currentGroup", async () => {
    const data = await request("GET", "/api/groups/current");
    return data?.group ?? data;
  }),
  leaveGroup: withFallback("leaveGroup", (groupId) => request("POST", `/api/groups/${enc(groupId)}/leave`, {})),
  // groupId lets the server record where you met. Saved only when both people propose it.
  proposeConnection: withFallback("proposeConnection", (displayId, groupId = null) =>
    request("POST", "/api/connections", groupId ? { displayId, groupId } : { displayId })),
  // Not in the task plans yet (confirm with Rishabh): people you've met, both agreed.
  connections: withFallback("connections", async () => {
    const data = await request("GET", "/api/connections");
    return Array.isArray(data) ? data : data?.connections || [];
  }),
  // Grow (not in the task plans yet; confirm with Rishabh). Reflections are private to the person;
  // only an anonymous "felt heard" share reaches the board.
  reflect: withFallback("reflect", (reflection) => request("POST", "/api/reflections", reflection)),
  growth: withFallback("growth", () => request("GET", "/api/growth")),
  startedOnOwn: withFallback("startedOnOwn", () => request("POST", "/api/growth/independent", {})),
  block: withFallback("block", (blockedDisplayId) => request("POST", "/api/blocks", { blockedDisplayId })),
  safetyReport: withFallback("safetyReport", (report) => request("POST", "/api/safety-reports", report)),

  // Search: /api/talks/search when it exists, else the original /api/search, else the mock.
  searchTalks: async (q) => {
    if (forceMock || mockedMethods.has("searchTalks")) return mock.searchTalks(q);
    try {
      return normalizeHits(await request("GET", `/api/talks/search?q=${enc(q)}`));
    } catch (err) {
      if (!(err instanceof MissingRoute)) throw err;
    }
    try {
      return normalizeHits(await request("GET", `/api/search?q=${enc(q)}`));
    } catch (err) {
      if (!(err instanceof MissingRoute)) throw err;
      useMockFor("searchTalks");
      return mock.searchTalks(q);
    }
  },
  // The question goes in the body only: never the URL, the hash or a log.
  ask: withFallback("ask", (question, slot) => request("POST", "/api/ask", slot ? { question, slot } : { question })),

  reportRoom: withFallback("reportRoom", (roomId, signal) =>
    request("POST", `/api/rooms/${enc(roomId)}/reports`, { signal })),
  board: withFallback("board", async () => {
    const data = await request("GET", "/api/board");
    return data?.board ?? data;
  }),
  // The token goes in the body only, never the URL, so it stays out of access logs and traces.
  staffLogin: (token) => request("POST", "/api/staff/login", { token }),
  staffIncidents: withFallback("staffIncidents", () => request("GET", "/api/staff/incidents")),
  updateIncident: withFallback("updateIncident", (id, patch) =>
    request("PATCH", `/api/staff/incidents/${enc(id)}`, patch)),
};
