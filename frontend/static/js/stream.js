// Live updates: Server-Sent Events from /api/stream, plus the mock's event bus.
// If the stream drops, it retries with backoff (1s → 30s) and screens fall back to
// polling every 10 seconds (see isLive). Handlers must be safe to receive the same event twice;
// events with an id are also de-duplicated here.

import { on as mockOn } from "./mock-api.js";

const TYPES = ["placement", "reroute", "group", "room", "incident", "board"];
const handlers = new Map(TYPES.map((t) => [t, new Set()]));
const seen = new Set();

let source = null;
let opened = false;   // has the real stream ever connected?
let live = false;     // is it connected right now?
let backoff = 1000;
let retryTimer = null;
let started = false;

const pill = () => document.getElementById("conn-pill");

function dispatch(type, data) {
  const id = data && (data.eventId || data.id);
  if (id && (type === "reroute" || type === "incident" || type === "group")) {
    const key = `${type}:${id}:${data.state || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    if (seen.size > 500) seen.delete(seen.values().next().value);
  }
  handlers.get(type)?.forEach((fn) => {
    try { fn(data); } catch { /* one bad handler must not stop the others */ }
  });
}

function connect() {
  if (!("EventSource" in window)) return;
  source = new EventSource("/api/stream", { withCredentials: true });
  source.onopen = () => {
    opened = true;
    live = true;
    backoff = 1000;
    if (pill()) pill().hidden = true;
  };
  source.onerror = () => {
    live = false;
    source.close();
    source = null;
    // Only show "Reconnecting" once a real stream has worked; a missing route is not an outage.
    if (opened && pill()) pill().hidden = false;
    clearTimeout(retryTimer);
    retryTimer = setTimeout(connect, backoff);
    backoff = Math.min(backoff * 2, 30000);
  };
  for (const type of TYPES) {
    source.addEventListener(type, (ev) => {
      let data = null;
      try { data = JSON.parse(ev.data); } catch { return; }
      dispatch(type, data);
    });
  }
}

function start() {
  if (started) return;
  started = true;
  const forced = /[?&]mock=1\b/.test(location.search + location.hash);
  if (!forced) connect();
  for (const type of TYPES) mockOn(type, (data) => dispatch(type, data));
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !source && !forced) { clearTimeout(retryTimer); connect(); }
  });
}

/** Subscribes to one event type. Returns an unsubscribe function. */
export function subscribe(type, fn) {
  start();
  handlers.get(type)?.add(fn);
  return () => handlers.get(type)?.delete(fn);
}

/** True while the real stream is connected; screens poll every 10 s when it isn't. */
export const isLive = () => live;
export const POLL_MS = 10000;
