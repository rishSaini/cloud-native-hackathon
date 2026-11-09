// Talk slots from the shared contract (docs/tasks/*.md), with their Mountain Time start times.
// Used to pick "the next slot" for Find me a talk.

export const SLOTS = [
  { id: "tue-0900", startsAt: "2026-11-10T09:00:00-07:00" },
  { id: "tue-1030", startsAt: "2026-11-10T10:30:00-07:00" },
  { id: "tue-1330", startsAt: "2026-11-10T13:30:00-07:00" },
  { id: "tue-1430", startsAt: "2026-11-10T14:30:00-07:00" },
  { id: "tue-1600", startsAt: "2026-11-10T16:00:00-07:00" },
];

const TALK_MINUTES = 50;

/** The slot running now, else the next one to start, else the last one. */
export function nextSlot(now = Date.now()) {
  for (const slot of SLOTS) {
    const start = Date.parse(slot.startsAt);
    if (now < start + TALK_MINUTES * 60000) return slot;
  }
  return SLOTS[SLOTS.length - 1];
}

/** True if a talk starting at startsAt is on right now. */
export function isRunning(startsAt, now = Date.now()) {
  if (!startsAt) return false;
  const start = Date.parse(startsAt);
  return now >= start && now < start + TALK_MINUTES * 60000;
}
