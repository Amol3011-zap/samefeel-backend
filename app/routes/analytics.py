"""
Anonymous Visitor Analytics — privacy-first, no PII collected.
"""
import os
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from app.config import get_allowed_origins
from app.database import get_db
from app.models import VisitorAnalytics

router = APIRouter()

# Single source of truth for "what counts as our production site" - the
# same allow-list the CORS middleware uses (app/main.py), via the same
# required ALLOWED_ORIGINS env var (see app.config.get_allowed_origins).
_ALLOWED_ORIGINS = set(get_allowed_origins())
# Hostnames of those origins; sessions from any other host count as internal traffic.
_PRODUCTION_HOSTNAMES = {urlparse(o).hostname for o in _ALLOWED_ORIGINS}

# Local/dev escape hatch — off by default everywhere, including production.
# Only set ALLOW_DEV_ORIGINS=true in a local .env; never on Railway.
_ALLOW_DEV_ORIGINS = os.getenv("ALLOW_DEV_ORIGINS", "false").lower() in ("true", "1")
_DEV_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}


def _is_allowed_origin(origin: Optional[str]) -> bool:
    """
    True if this request is allowed to write to visitor_analytics.

    No Origin header at all = same-origin / non-browser request (server-to-
    server calls, curl, the Vite dev proxy stripping Origin before forwarding
    to the real backend). We only reject a *wrong* Origin, never a missing
    one, since genuine same-origin browser requests never send Origin.
    """
    if origin is None:
        return True
    if origin in _ALLOWED_ORIGINS:
        return True
    if _ALLOW_DEV_ORIGINS and origin in _DEV_ORIGINS:
        return True
    return False


class VisitorSessionCreate(BaseModel):
    session_id: str
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    screen_resolution: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    referral_source: Optional[str] = None
    landing_page: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None


class VisitorSessionUpdate(BaseModel):
    session_id: str
    pages_viewed: Optional[List[str]] = None
    session_duration_seconds: Optional[int] = None
    click_events: Optional[List[dict]] = None


@router.post("/session/start")
def start_visitor_session(data: VisitorSessionCreate, request: Request, response: Response, db: Session = Depends(get_db)):
    """Record the start of an anonymous visitor session."""
    if not _is_allowed_origin(request.headers.get("origin")):
        # Disallowed Origin: no error page, no write, no information leak —
        # just a bare 204 so a forged/foreign caller learns nothing.
        response.status_code = 204
        return None

    existing = db.query(VisitorAnalytics).filter(
        VisitorAnalytics.session_id == data.session_id
    ).first()
    if existing:
        return {"status": "exists", "session_id": data.session_id}

    is_internal = bool(data.hostname) and data.hostname not in _PRODUCTION_HOSTNAMES
    session = VisitorAnalytics(
        session_id=data.session_id,
        hostname=data.hostname,
        is_internal=is_internal,
        device_type=data.device_type,
        browser=data.browser,
        os=data.os,
        screen_resolution=data.screen_resolution,
        country=data.country,
        city=data.city,
        referral_source=data.referral_source,
        landing_page=data.landing_page,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        utm_content=data.utm_content,
        utm_term=data.utm_term,
    )
    db.add(session)
    db.commit()
    return {"status": "created", "session_id": data.session_id}


@router.post("/session/update")
def update_visitor_session(data: VisitorSessionUpdate, request: Request, response: Response, db: Session = Depends(get_db)):
    """Update session with page views and duration."""
    if not _is_allowed_origin(request.headers.get("origin")):
        response.status_code = 204
        return None

    session = db.query(VisitorAnalytics).filter(
        VisitorAnalytics.session_id == data.session_id
    ).first()
    if not session:
        return {"status": "not_found"}

    if data.pages_viewed is not None:
        session.pages_viewed = data.pages_viewed
    if data.session_duration_seconds is not None:
        session.session_duration_seconds = data.session_duration_seconds
    if data.click_events is not None:
        session.click_events = data.click_events
    session.last_seen_at = datetime.utcnow()

    db.commit()
    return {"status": "updated"}


@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    """Public summary stats — no PII returned. Excludes internal/dev traffic."""
    now = datetime.utcnow()
    last_30 = now - timedelta(days=30)
    last_7 = now - timedelta(days=7)

    base = db.query(VisitorAnalytics).filter(VisitorAnalytics.is_internal.is_(False))
    total_sessions = base.count()
    sessions_30d = base.filter(VisitorAnalytics.created_at >= last_30).count()
    sessions_7d = base.filter(VisitorAnalytics.created_at >= last_7).count()

    return {
        "total_sessions": total_sessions,
        "sessions_last_30_days": sessions_30d,
        "sessions_last_7_days": sessions_7d,
    }
