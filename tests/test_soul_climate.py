"""
Tests for the Soul Climate daily check-in (app/routes/soul_climate.py,
app/services/soul_climate.py).

Runs against an in-memory SQLite database with only the Soul Climate router
mounted — never a real DATABASE_URL. Uses real signed bearer tokens so the
authentication path is exercised end to end.
Run with: pytest tests/test_soul_climate.py -v
"""
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import User, UserMood, ProblemEnum
from app.routes import soul_climate as route
from app.services import soul_climate as sc
from app.services.auth import AuthService


@pytest.fixture()
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    User.__table__.create(engine)
    UserMood.__table__.create(engine)  # includes the partial unique index
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = Session()
    problem = list(ProblemEnum)[0]
    alice = User(phone="+910000000001", name="Alice", primary_problem=problem)
    bob = User(phone="+910000000002", name="Bob", primary_problem=problem)
    db.add_all([alice, bob]); db.commit()
    ids = {"alice": alice.id, "bob": bob.id}
    db.close()

    app = FastAPI()
    app.include_router(route.router, prefix="/api/soul-climate")

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    def auth(name):
        token = AuthService.create_access_token({"sub": str(ids[name])})
        return {"Authorization": f"Bearer {token}"}

    return client, auth, Session, ids


TZ = "Asia/Kolkata"


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_today_requires_authentication(env):
    client, *_ = env
    r = client.get("/api/soul-climate/today", params={"timezone": TZ})
    assert r.status_code in (401, 403)


def test_checkin_requires_authentication(env):
    client, *_ = env
    r = client.post("/api/soul-climate/checkin", json={"weather": "clear-sky", "timezone": TZ})
    assert r.status_code in (401, 403)


def test_invalid_token_rejected(env):
    client, *_ = env
    r = client.post("/api/soul-climate/checkin", json={"weather": "clear-sky", "timezone": TZ},
                    headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


# ── Behaviour ─────────────────────────────────────────────────────────────────

def test_fresh_user_not_checked_in(env):
    client, auth, *_ = env
    r = client.get("/api/soul-climate/today", params={"timezone": TZ}, headers=auth("alice"))
    assert r.status_code == 200
    body = r.json()
    assert body["checked_in"] is False and body["weather"] is None


def test_checkin_then_today_reports_it(env):
    client, auth, *_ = env
    r = client.post("/api/soul-climate/checkin", json={"weather": "clear-sky", "timezone": TZ}, headers=auth("alice"))
    assert r.status_code == 200
    assert r.json()["checked_in"] is True and r.json()["weather"] == "clear-sky"

    r = client.get("/api/soul-climate/today", params={"timezone": TZ}, headers=auth("alice"))
    assert r.json()["checked_in"] is True and r.json()["weather"] == "clear-sky"


def test_second_checkin_same_day_is_rejected_and_keeps_first(env):
    client, auth, Session, ids = env
    client.post("/api/soul-climate/checkin", json={"weather": "hope", "timezone": TZ}, headers=auth("alice"))
    r = client.post("/api/soul-climate/checkin", json={"weather": "storm", "timezone": TZ}, headers=auth("alice"))
    assert r.status_code == 409
    assert r.json()["detail"]["weather"] == "hope"
    s = Session()
    assert s.query(UserMood).filter(UserMood.user_id == ids["alice"]).count() == 1
    s.close()


def test_users_are_isolated(env):
    client, auth, *_ = env
    client.post("/api/soul-climate/checkin", json={"weather": "fog", "timezone": TZ}, headers=auth("alice"))
    r = client.get("/api/soul-climate/today", params={"timezone": TZ}, headers=auth("bob"))
    assert r.json()["checked_in"] is False
    r = client.post("/api/soul-climate/checkin", json={"weather": "blooming", "timezone": TZ}, headers=auth("bob"))
    assert r.status_code == 200 and r.json()["weather"] == "blooming"


def test_client_cannot_choose_the_user(env):
    client, auth, Session, ids = env
    # Extra fields such as user_id are ignored; the row belongs to the token's user.
    client.post("/api/soul-climate/checkin", json={"weather": "fog", "timezone": TZ, "user_id": ids["bob"]},
                headers=auth("alice"))
    s = Session()
    row = s.query(UserMood).one()
    assert row.user_id == ids["alice"]
    s.close()


def test_rejects_unknown_weather_and_bad_timezone(env):
    client, auth, *_ = env
    assert client.post("/api/soul-climate/checkin", json={"weather": "tornado", "timezone": TZ},
                       headers=auth("alice")).status_code == 422
    assert client.post("/api/soul-climate/checkin", json={"weather": "fog", "timezone": "Mars/Olympus"},
                       headers=auth("alice")).status_code == 422
    assert client.get("/api/soul-climate/today", params={"timezone": "Nope/Zone"},
                      headers=auth("alice")).status_code == 422


def test_stored_record_fields(env):
    client, auth, Session, ids = env
    client.post("/api/soul-climate/checkin", json={"weather": "heavy-rain", "timezone": TZ}, headers=auth("alice"))
    s = Session()
    row = s.query(UserMood).one()
    assert row.source == "soul_climate" and row.timezone == TZ
    assert row.mood_label == "heavy_rain" and 1 <= row.mood_score <= 10
    assert row.local_date is not None and row.logged_at is not None
    s.close()


# ── Local calendar day (service level, fixed clock) ──────────────────────────

def test_local_date_uses_user_timezone_not_utc():
    # 20:00 UTC on Sep 24 is already 01:30 on Sep 25 in India.
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)
    assert sc.local_today("Asia/Kolkata", now) == date(2026, 9, 25)
    assert sc.local_today("America/New_York", now) == date(2026, 9, 24)


def test_one_per_local_day_and_new_day_allowed(env):
    _, _, Session, ids = env
    s = Session()
    late = datetime(2026, 9, 25, 18, 20, tzinfo=timezone.utc)      # 23:50 IST Sep 25
    also_25 = datetime(2026, 9, 25, 5, 0, tzinfo=timezone.utc)     # 10:30 IST Sep 25
    after_midnight = datetime(2026, 9, 25, 18, 40, tzinfo=timezone.utc)  # 00:10 IST Sep 26

    e1, created1 = sc.check_in(s, ids["alice"], "clear-sky", TZ, also_25)
    e2, created2 = sc.check_in(s, ids["alice"], "storm", TZ, late)
    e3, created3 = sc.check_in(s, ids["alice"], "hope", TZ, after_midnight)
    assert created1 is True and e1.local_date == date(2026, 9, 25)
    assert created2 is False and e2.id == e1.id and e2.mood_label == "clear"
    assert created3 is True and e3.local_date == date(2026, 9, 26)
    assert s.query(UserMood).count() == 2   # history kept
    s.close()


def test_database_enforces_uniqueness_even_without_the_precheck(env):
    _, _, Session, ids = env
    from sqlalchemy.exc import IntegrityError
    s = Session()
    for _ in range(2):
        s.add(UserMood(user_id=ids["alice"], mood_score=5, mood_label="fog", mood_tags=[],
                       local_date=date(2026, 9, 25), timezone=TZ, source="soul_climate"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
    # Other mood-tracker rows on the same day are unaffected by the constraint.
    s.add_all([UserMood(user_id=ids["alice"], mood_score=5, mood_label="okay", mood_tags=[], local_date=date(2026, 9, 25)),
               UserMood(user_id=ids["alice"], mood_score=6, mood_label="good", mood_tags=[], local_date=date(2026, 9, 25))])
    s.commit()
    s.close()
