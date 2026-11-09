// Announcements, reduced motion, calm mode, text size and display mode.
// Only these display preferences live in localStorage. Never card text.

const PREFS_KEY = "affinity.prefs";
const TEXT_SIZES = ["default", "large", "larger"];

const defaults = {
  calm: false,
  reduceMotion: null, // null = follow the system setting
  textSize: "default",
  kubectl: false,
};

const systemReduce = window.matchMedia?.("(prefers-reduced-motion: reduce)");
const listeners = new Set();

function load() {
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    return { ...defaults, ...(raw ? JSON.parse(raw) : {}) };
  } catch {
    return { ...defaults };
  }
}

let prefs = load();

function apply() {
  const root = document.documentElement;
  root.classList.toggle("calm", !!prefs.calm);
  root.classList.toggle("reduce-motion", !motionOK());
  root.classList.toggle("kubectl", !!prefs.kubectl);
  root.dataset.textSize = TEXT_SIZES.includes(prefs.textSize) ? prefs.textSize : "default";
}

export function getPrefs() {
  return { ...prefs };
}

export function setPrefs(patch) {
  prefs = { ...prefs, ...patch };
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* private mode: prefs last for this visit only */
  }
  apply();
  listeners.forEach((fn) => fn(getPrefs()));
}

export function onPrefsChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** True when animation is allowed: not calm mode, and reduced motion is off (app toggle, else system). */
export function motionOK() {
  if (prefs.calm) return false;
  if (prefs.reduceMotion != null) return !prefs.reduceMotion;
  return !systemReduce?.matches;
}

export const textSizes = TEXT_SIZES;

systemReduce?.addEventListener?.("change", () => {
  apply();
  listeners.forEach((fn) => fn(getPrefs()));
});
apply();

// ---- Polite, throttled announcements ----
// Screen reader users shouldn't be flooded: at most one message every 2 seconds,
// duplicates in the queue are dropped, and only the 3 newest messages are kept.

const GAP_MS = 2000;
const queue = [];
let lastAt = 0;
let timer = null;

function flush() {
  timer = null;
  const region = document.getElementById("live-region");
  const next = queue.shift();
  if (!region || !next) return;
  // Clearing first makes screen readers re-read an identical message.
  region.textContent = "";
  requestAnimationFrame(() => { region.textContent = next; });
  lastAt = Date.now();
  if (queue.length) timer = setTimeout(flush, GAP_MS);
}

export function announce(message) {
  if (!message || queue.includes(message)) return;
  queue.push(message);
  while (queue.length > 3) queue.shift();
  if (timer) return;
  const wait = Math.max(0, lastAt + GAP_MS - Date.now());
  timer = setTimeout(flush, wait);
}

/** Moves focus to a screen's heading after navigation, so keyboard and screen reader users land in the right place. */
export function focusScreen(container) {
  const target = container.querySelector("[data-autofocus]") || container.querySelector("h1") || container;
  if (!target.hasAttribute("tabindex") && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(target.tagName)) {
    target.setAttribute("tabindex", "-1");
  }
  target.focus({ preventScroll: false });
}
