// All conference times show in Mountain Time, whatever the device's time zone.

const TZ = "America/Denver";

const timeFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "numeric", minute: "2-digit" });
const dayTimeFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, weekday: "long", hour: "numeric", minute: "2-digit" });

const toDate = (value) => (value instanceof Date ? value : new Date(value));

export const formatTime = (value) => timeFmt.format(toDate(value));
export const formatDayTime = (value) => dayTimeFmt.format(toDate(value));

/** "Reported 2 min ago" style ages. */
export function ago(minutes) {
  if (minutes == null) return "";
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${Math.round(minutes)} min ago`;
  const hours = Math.round(minutes / 60);
  return `${hours} hr ago`;
}

/** Creates an element with attributes and children. Text is always set as text, never HTML. */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(el.dataset, value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}
