"""R4: sessions, card encryption, and what leaves the card."""

import pytest
from cryptography.exceptions import InvalidTag
from fastapi.testclient import TestClient

from app import auth
from app.cards import crypto
from app.cards.store import get_store
from app.main import app

CARD = {
    "name": "Alex", "pronouns": "they/them", "workingOn": "making apps start faster",
    "askMeAbout": "my first time running Kubernetes", "howToTalk": "Please face me, I read lips",
    "reachMe": "say hi at the break", "lookingFor": "people to learn from",
    "needs": ["captions", "quiet"], "allowMatching": True,
}


class MemoryStore:
    def __init__(self):
        self.attendees, self.rows, self.codes = set(), {}, {}

    def create_attendee(self, attendee_id):
        if attendee_id in self.attendees:
            return False
        self.attendees.add(attendee_id)
        return True

    def ensure_attendee(self, attendee_id):
        self.attendees.add(attendee_id)

    def save(self, attendee_id, card, codes):
        self.rows[attendee_id] = crypto.encrypt(attendee_id, card)
        self.codes[attendee_id] = codes

    def load(self, attendee_id):
        row = self.rows.get(attendee_id)
        return crypto.decrypt(attendee_id, *row) if row else None

    def delete(self, attendee_id):
        self.rows.pop(attendee_id, None)
        self.codes.pop(attendee_id, None)


@pytest.fixture
def env(monkeypatch):
    store = MemoryStore()
    calls = []
    monkeypatch.setattr("app.search.people.upsert_person", lambda aid, text: calls.append(("upsert", aid, text)))
    monkeypatch.setattr("app.search.people.delete_person", lambda aid: calls.append(("delete", aid)))
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app), store, calls
    app.dependency_overrides.clear()


# ---- encryption ----

def test_encryption_round_trip_with_fresh_nonces():
    c1, n1 = crypto.encrypt("ab12cd", CARD)
    c2, n2 = crypto.encrypt("ab12cd", CARD)
    assert n1 != n2 and c1 != c2
    assert crypto.decrypt("ab12cd", c1, n1) == CARD
    assert b"Alex" not in c1 and b"read lips" not in c1


def test_tampered_ciphertext_fails():
    ciphertext, nonce = crypto.encrypt("ab12cd", CARD)
    tampered = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]
    with pytest.raises(InvalidTag):
        crypto.decrypt("ab12cd", tampered, nonce)


def test_ciphertext_does_not_decrypt_for_another_attendee():
    ciphertext, nonce = crypto.encrypt("ab12cd", CARD)
    with pytest.raises(InvalidTag):
        crypto.decrypt("zz99yy", ciphertext, nonce)


# ---- sessions ----

def test_session_cookie_is_signed():
    value = auth.session_value("ab12cd")
    assert auth.attendee_from_session(value) == "ab12cd"
    assert auth.attendee_from_session("zz99yy." + value.split(".")[1]) is None
    assert auth.attendee_from_session("ab12cd.forged") is None
    assert auth.attendee_from_session(None) is None


def test_create_attendee_sets_httponly_cookie_and_is_idempotent(env):
    client, store, _ = env
    first = client.post("/api/attendees")
    assert first.status_code == 200
    body = first.json()
    assert body["displayId"] == f"attendee-{body['attendeeId']}"
    assert "httponly" in first.headers["set-cookie"].lower()
    assert client.post("/api/attendees").json()["attendeeId"] == body["attendeeId"]


def test_card_routes_need_a_session(env):
    client, _, _ = env
    assert TestClient(app).get("/api/card").status_code == 401


# ---- card routes ----

def test_save_and_read_card_with_codes_only_for_needs(env):
    client, store, _ = env
    attendee = client.post("/api/attendees").json()["attendeeId"]
    assert client.put("/api/card", json=CARD).status_code == 200
    assert store.codes[attendee] == ["cap-c1", "cap-c3"]
    got = client.get("/api/card").json()
    assert got["howToTalk"] == "Please face me, I read lips"
    assert got["displayId"] == f"attendee-{attendee}"


def test_only_consented_interest_text_reaches_the_people_index(env):
    client, _, calls = env
    attendee = client.post("/api/attendees").json()["attendeeId"]
    client.put("/api/card", json=CARD)
    assert calls == [("upsert", attendee, "making apps start faster my first time running Kubernetes people to learn from")]
    text = calls[0][2]
    for private in ("Alex", "they/them", "read lips", "say hi", "captions", "quiet"):
        assert private not in text


def test_withdrawing_consent_or_deleting_removes_the_person(env):
    client, store, calls = env
    attendee = client.post("/api/attendees").json()["attendeeId"]
    client.put("/api/card", json={**CARD, "allowMatching": False})
    assert calls[-1] == ("delete", attendee)
    client.put("/api/card", json=CARD)
    assert client.delete("/api/card").status_code == 200
    assert calls[-1] == ("delete", attendee)
    assert attendee not in store.rows
    assert client.get("/api/card").json() is None


def test_unknown_need_is_rejected(env):
    client, _, _ = env
    client.post("/api/attendees")
    assert client.put("/api/card", json={**CARD, "needs": ["telepathy"]}).status_code == 422
