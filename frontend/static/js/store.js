// In-memory app state. Card text is kept here for this page visit only: it is fetched from
// the API when needed and never written to localStorage, sessionStorage or a URL.
//
// Identity safety: a new attendee is created only when the server has positively said this
// browser has no card (GET /api/card returned nothing, or 401 with no session). A failed
// load is never cached and never treated as "no card", so an existing cardholder can't be
// sent back through onboarding or given a second identity.

import { api } from "./api.js";

let me = null;            // { displayId } once known
let card = null;          // the person's card, or null
let loaded = false;       // a load succeeded this visit
let knownNoCard = false;  // the server confirmed there is no card for this session

/** Loads the person's card once per page visit. Returns { me, card, error }. */
export async function loadMe({ force = false } = {}) {
  if (loaded && !force) return { me, card, error: null };
  try {
    const data = await api.getCard();
    card = data ? stripMeta(data) : null;
    if (data?.displayId) me = { displayId: data.displayId };
    knownNoCard = !data;
  } catch (err) {
    if (err?.status !== 401) return { me, card, error: err }; // not cached: the next call retries
    card = null;           // 401: no session yet, so no card
    knownNoCard = true;
  }
  loaded = true;
  return { me, card, error: null };
}

export async function saveMyCard(next) {
  if (!loaded) {
    const { error } = await loadMe();
    if (error) throw error;
  }
  if (knownNoCard && !card && !me) {
    const created = await api.createAttendee();
    if (created?.displayId) me = { displayId: created.displayId };
  }
  const saved = await api.saveCard(next);
  card = stripMeta(saved || next);
  if (saved?.displayId) me = { displayId: saved.displayId };
  knownNoCard = false;
  loaded = true;
  return { me, card };
}

export async function deleteMyCard() {
  await api.deleteCard();
  me = null;
  card = null;
  knownNoCard = true;
  loaded = true;
}

export const currentCard = () => card;
export const currentMe = () => me;

function stripMeta(data) {
  const { displayId, attendeeId, ...rest } = data;
  return rest;
}
