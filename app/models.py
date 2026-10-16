from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Index
from datetime import datetime

from app.database import Base


# ========== VISITOR ANALYTICS ==========

class VisitorAnalytics(Base):
    __tablename__ = "visitor_analytics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(128), unique=True, index=True, nullable=False)
    hostname = Column(String(255))            # window.location.hostname the session was recorded from
    is_internal = Column(Boolean, default=False, nullable=False)  # dev/team traffic, excluded from reporting
    device_type = Column(String(20))          # mobile / tablet / desktop
    browser = Column(String(50))
    os = Column(String(50))
    screen_resolution = Column(String(20))
    country = Column(String(80))
    city = Column(String(80))                 # approximate only
    referral_source = Column(String(500))
    landing_page = Column(String(500))
    pages_viewed = Column(JSON, default=list)
    session_duration_seconds = Column(Integer, default=0)
    click_events = Column(JSON, default=list)
    utm_source = Column(String(200))
    utm_medium = Column(String(200))
    utm_campaign = Column(String(200))
    utm_content = Column(String(200))
    utm_term = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_visitor_analytics_created", "created_at"),
        Index("ix_visitor_analytics_country", "country"),
        Index("ix_visitor_analytics_hostname", "hostname"),
    )


# ========== SECURITY LOGS ==========
# Standalone event log — no foreign key to a users table (there isn't one
# in this trimmed schema). user_id, if ever populated, is just an opaque
# int the caller supplies; nothing in this codebase currently writes to
# this table, it's kept so the data already in it is preserved and so a
# future feature can log into it without a migration.

class SecurityLog(Base):
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_fingerprint = Column(String(200), nullable=True)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_security_logs_user_date", "user_id", "created_at"),
        Index("ix_security_logs_event", "event_type", "created_at"),
    )


# ========== EARLY ACCESS / WAITLIST ==========

class EarlyAccessSubmission(Base):
    __tablename__ = "early_access_submissions"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(200), nullable=True)
    email           = Column(String(320), nullable=False, unique=True, index=True)
    struggle        = Column(String(100), nullable=True)   # renamed from challenge
    challenge       = Column(String(100), nullable=True)   # kept for backward compat
    source          = Column(String(100), default="Landing Page")
    referral_code   = Column(String(100), nullable=True)   # for future referral tracking
    referral_source = Column(String(50), nullable=True)    # "How did you hear about us?" dropdown
    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_early_access_created", "created_at"),
    )


# ========== GLOBAL PULSE ==========
# Unauthenticated check-ins for the "How Do You Feel?" / Global Pulse
# feature. No user_id, no name, no email — but ip_address and city ARE
# retained for internal records (product decision). The public API in
# app/routes/pulse.py never returns ip_address or city, and only ever
# returns aggregated, threshold-gated counts.

class PulseCheckIn(Base):
    __tablename__ = "pulse_checkins"

    id           = Column(Integer, primary_key=True, index=True)
    problems     = Column(JSON, nullable=False)   # list[str], 1-2 problem ids
    country_code = Column(String(2), nullable=True)   # ISO 3166-1 alpha-2, e.g. "IN"
    country_name = Column(String(80), nullable=True)
    city         = Column(String(120), nullable=True)   # IP-derived, best-effort
    ip_address   = Column(String(45), nullable=True)     # internal record only; never returned by any API response. IPv6-safe length.
    created_at   = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_pulse_checkins_created", "created_at"),
        Index("ix_pulse_checkins_country", "country_code"),
    )
