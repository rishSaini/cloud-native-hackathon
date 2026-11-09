// In-memory app state. Card text is kept here for this page visit only: it is fetched from
// the API when needed and never written to localStorage, sessionStorage or a URL.

import { api } from "./api.js";

let me = null;      // { displayId } once known
let card = null;    // the person's card, or null
let loaded = false;

/** Loads the person's card once per page visit. Returns { me, card }. */
export async function loadMe({ force = false } = {}) {
  if (loaded && !force) return { me, card };
  try {
    const data = await api.getCard();
    card = data ? stripMeta(data) : null;
    if (data?.displayId) me = { displayId: data.displayId };
  } catch {
    card = null;
  }
  loaded = true;
  return { me, card };
}

export async function saveMyCard(next) {
  if (!me) {
    const created = await api.createAttendee();
    if (created?.displayId) me = { displayId: created.displayId };
  }
  const saved = await api.saveCard(next);
  card = stripMeta(saved || next);
  if (saved?.displayId) me = { displayId: saved.displayId };
  loaded = true;
  return { me, card };
}

export async function deleteMyCard() {
  await api.deleteCard();
  me = null;
  card = null;
  loaded = true;
}

export const currentCard = () => card;
export const currentMe = () => me;

function stripMeta(data) {
  const { displayId, attendeeId, ...rest } = data;
  return rest;
}
