"""
Soul Climate daily check-in.

One check-in per user per LOCAL calendar day. The day is computed on the
server from the user's IANA timezone (never from a client-sent date), and the
database enforces it with the partial unique index ux_user_moods_daily_checkin
on user_moods (user_id, local_date) WHERE source = 'soul_climate'.

Check-ins are stored in the existing user_moods table so they sit alongside
the rest of the user's mood history (and are covered by the privacy
export/delete routes). Mood values are never logged.
"""
from datetime import date, datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import UserMood

SOURCE = "soul_climate"

# weather id -> (mood_label, mood_score 1-10)
WEATHERS = {
    "clear-sky": ("clear", 9),
    "hope": ("hope", 7),
    "blooming": ("blooming", 9),
    "fog": ("fog", 5),
    "heavy-rain": ("heavy_rain", 3),
    "storm": ("storm", 2),
}
LABEL_TO_WEATHER = {label: wid for wid, (label, _) in WEATHERS.items()}


class InvalidTimezone(ValueError):
    pass


def resolve_zone(tz_name: str) -> ZoneInfo:
    if not tz_name or len(tz_name) > 64:
        raise InvalidTimezone("Invalid timezone")
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise InvalidTimezone("Invalid timezone")


def local_today(tz_name: str, now: datetime | None = None) -> date:
    """The user's current calendar date in their timezone."""
    zone = resolve_zone(tz_name)
    now = now or datetime.now(dt_timezone.utc)
    return now.astimezone(zone).date()


def serialize(entry: UserMood | None, local_date: date) -> dict:
    if not entry:
        return {"checked_in": False, "local_date": local_date.isoformat(), "weather": None, "checked_in_at": None}
    return {
        "checked_in": True,
        "local_date": entry.local_date.isoformat(),
        "weather": LABEL_TO_WEATHER.get(entry.mood_label),
        "checked_in_at": entry.logged_at.replace(tzinfo=dt_timezone.utc).isoformat() if entry.logged_at else None,
    }


def get_for_date(db: Session, user_id: int, local_date: date) -> UserMood | None:
    return (
        db.query(UserMood)
        .filter(UserMood.user_id == user_id, UserMood.source == SOURCE, UserMood.local_date == local_date)
        .first()
    )


def check_in(db: Session, user_id: int, weather: str, tz_name: str, now: datetime | None = None):
    """Record today's check-in. Returns (entry, created). created is False when
    the user already checked in on this local date (the existing entry wins)."""
    day = local_today(tz_name, now)
    existing = get_for_date(db, user_id, day)
    if existing:
        return existing, False

    label, score = WEATHERS[weather]
    entry = UserMood(
        user_id=user_id,
        mood_score=score,
        mood_label=label,
        mood_tags=[],
        logged_at=(now or datetime.now(dt_timezone.utc)).astimezone(dt_timezone.utc).replace(tzinfo=None),
        local_date=day,
        timezone=tz_name,
        source=SOURCE,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent request for the same day.
        db.rollback()
        return get_for_date(db, user_id, day), False
    db.refresh(entry)
    return entry, True
