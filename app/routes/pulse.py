"""
Global Pulse — emotional check-ins ("How Do You Feel?").

Data model (updated — product decision, not the original design):
  - No auth, no user_id, no name/email.
  - ip_address and an IP-derived city ARE now retained on the check-in row
    for internal records. Location is resolved server-side from the
    request IP via app/services/ip_geolocation.py (falls back to the
    client-reported locale hint if that lookup fails), rather than
    trusting only the browser's language setting.
  - The public GET endpoint still only ever returns aggregates, computed
    by app/services/pulse_aggregation.py, and NEVER returns ip_address or
    city. Any country/category whose count is below
    MIN_AGGREGATION_THRESHOLD is omitted rather than exposing a small,
    potentially identifying number.
"""
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PulseCheckIn
from app.services.client_ip import get_client_ip
from app.services.ip_geolocation import lookup as geolocate_ip
from app.services.iso_countries import ISO_3166_1_ALPHA2
from app.services.pulse_aggregation import (
    MIN_AGGREGATION_THRESHOLD,
    PROBLEM_IDS,
    RECENT_WINDOW_HOURS,
    build_snapshot,
    visibility_cutoff,
)
from app.services.pulse_cooldown import COOLDOWN_HOURS, is_on_cooldown, record_checkin

router = APIRouter()

MAX_PROBLEMS_PER_CHECKIN = 2

# ─── In-memory rate limiter ───────────────────────────────────────────────────
# Keyed on get_client_ip(), which only trusts X-Forwarded-For from a
# configured trusted proxy (see app/services/client_ip.py) — otherwise the
# direct TCP peer is used, so a client can't pick its own rate-limit bucket.
_rate_store: dict = defaultdict(list)
RATE_LIMIT = 5
RATE_WINDOW = timedelta(minutes=10)


def _check_rate_limit(ip: str):
    now = datetime.utcnow()
    cutoff = now - RATE_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > cutoff]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many check-ins. Please wait a few minutes and try again.",
        )
    _rate_store[ip].append(now)


# ─── Short-lived cache for the aggregation query (mirrors challenges.py) ─────
_snapshot_cache: dict = {}
CACHE_TTL = 60  # seconds


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CheckInRequest(BaseModel):
    problems: List[str]
    country_code: Optional[str] = None
    country_name: Optional[str] = None

    @field_validator("problems")
    @classmethod
    def validate_problems(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one problem must be selected")
        if len(v) > MAX_PROBLEMS_PER_CHECKIN:
            raise ValueError(f"At most {MAX_PROBLEMS_PER_CHECKIN} problems may be selected")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate problem ids are not allowed")
        unknown = [p for p in v if p not in PROBLEM_IDS]
        if unknown:
            raise ValueError(f"Unknown problem id(s): {unknown}")
        return v

    @field_validator("country_code", mode="before")
    @classmethod
    def normalise_country_code(cls, v):
        # Country is a client-supplied classification (e.g. browser locale),
        # not verified geographic truth — normalize and check it against the
        # real ISO 3166-1 alpha-2 list rather than trusting arbitrary text.
        # An unrecognized value is treated as "not provided" (None) rather
        # than rejecting the whole check-in, since this field is optional.
        if not v or not isinstance(v, str):
            return None
        candidate = v.strip().upper()
        if candidate not in ISO_3166_1_ALPHA2:
            return None
        return candidate

    @field_validator("country_name", mode="before")
    @classmethod
    def clean_country_name(cls, v):
        if not v or not isinstance(v, str):
            return None
        return v.strip()[:80] or None


class CheckInResponse(BaseModel):
    success: bool


# ─── POST /api/pulse/checkin ──────────────────────────────────────────────────

@router.post("/checkin", response_model=CheckInResponse)
async def submit_checkin(
    data: CheckInRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = get_client_ip(request)
    _check_rate_limit(ip)

    if is_on_cooldown(db, ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You've already checked in recently. Please try again in up to {COOLDOWN_HOURS} hours.",
        )

    # IP-based geolocation is authoritative when it succeeds (it doesn't
    # depend on the visitor's browser language matching their actual
    # location); the client-reported locale hint is only a fallback for
    # when the lookup fails (e.g. local dev, private IP, third-party
    # outage).
    geo = await geolocate_ip(ip)
    country_code = geo["country_code"] or data.country_code
    country_name = geo["country_name"] or data.country_name

    checkin = PulseCheckIn(
        problems=data.problems,
        country_code=country_code,
        country_name=country_name,
        city=geo["city"],
        ip_address=ip if ip != "unknown" else None,
        created_at=datetime.utcnow(),
    )
    db.add(checkin)
    record_checkin(db, ip)
    db.commit()

    _snapshot_cache.clear()

    return CheckInResponse(success=True)


# ─── GET /api/pulse/global ─────────────────────────────────────────────────────

@router.get("/global")
async def get_global_pulse(db: Session = Depends(get_db)):
    """Public aggregated snapshot. Never returns individual check-in rows.

    `total` and `recent_checkins` reflect every check-in ever recorded and
    update immediately — both are single coarse numbers with no category/
    geography attached, so the product surfaces them without the threshold/
    delay gating the rest of the response needs (see RECENT_WINDOW_HOURS's
    docstring in pulse_aggregation.py for why that's safe).

    Every other field (`categories`, `countries`, `map`) only reflects
    check-ins older than visibility_cutoff() — a freshly-submitted check-in
    cannot move any of those numbers until it ages past the delay. This is
    what prevents an attacker from submitting one check-in and diffing the
    response immediately before/after to infer its category or country;
    see build_snapshot()'s docstring for the full explanation.
    """
    cached = _snapshot_cache.get("snapshot")
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    total = db.query(PulseCheckIn).count()

    recent_since = datetime.utcnow() - timedelta(hours=RECENT_WINDOW_HOURS)
    recent_checkins = db.query(PulseCheckIn).filter(PulseCheckIn.created_at >= recent_since).count()

    cutoff = visibility_cutoff(datetime.utcnow())
    visible = db.query(PulseCheckIn).filter(PulseCheckIn.created_at <= cutoff)

    problem_rows = [row[0] for row in visible.with_entities(PulseCheckIn.problems).all()]

    country_counts = (
        visible.with_entities(
            PulseCheckIn.country_code,
            PulseCheckIn.country_name,
            func.count(PulseCheckIn.id).label("count"),
        )
        .filter(PulseCheckIn.country_code.isnot(None))
        .group_by(PulseCheckIn.country_code, PulseCheckIn.country_name)
        .order_by(func.count(PulseCheckIn.id).desc())
        .all()
    )

    checkin_rows = (
        visible.with_entities(PulseCheckIn.country_code, PulseCheckIn.problems)
        .filter(PulseCheckIn.country_code.isnot(None))
        .all()
    )

    snapshot = build_snapshot(
        total=total,
        problem_rows=problem_rows,
        country_counts=country_counts,
        checkin_rows=checkin_rows,
        threshold=MIN_AGGREGATION_THRESHOLD,
        recent_checkins=recent_checkins,
    )

    _snapshot_cache["snapshot"] = (time.time(), snapshot)
    return snapshot
