import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import attendee_hash, current_attendee_id
from app.breaks.inputs import load_break_people
from app.k8s.seats import free_seats


def _app():
    app = FastAPI()

    @app.get("/me")
    def me(attendee_id: str = Depends(current_attendee_id)):
        return {"id": attendee_id}

    return app


def test_current_attendee_id_is_401_without_session():
    assert TestClient(_app()).get("/me").status_code == 401


def test_current_attendee_id_can_be_overridden():
    app = _app()
    app.dependency_overrides[current_attendee_id] = lambda: "att-123"
    assert TestClient(app).get("/me").json() == {"id": "att-123"}


def test_attendee_hash_is_stable_hmac(monkeypatch):
    monkeypatch.delenv("SESSION_SIGNING_KEY", raising=False)
    h = attendee_hash("att-123")
    assert h == attendee_hash("att-123")
    assert len(h) == 64 and "att-123" not in h
    assert h != attendee_hash("att-456")


def test_attendee_hash_uses_signing_key(monkeypatch):
    monkeypatch.delenv("SESSION_SIGNING_KEY", raising=False)
    dev = attendee_hash("att-123")
    monkeypatch.setenv("SESSION_SIGNING_KEY", "other-key")
    assert attendee_hash("att-123") != dev


def test_unimplemented_stubs_raise():
    with pytest.raises(NotImplementedError):
        load_break_people("brk-tue-1000")
    # free_seats is real since R6 (see test_placement.py); it only needs a client.
    assert callable(free_seats)
