"""
Dashboard stats routes.
Aggregates healing streak + points from user_challenge_streaks,
weekly sessions from journey_activities, and live count from in-memory tracker.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, UserChallengeStreak, JourneyActivity
from app.routes.users import get_current_user
from app.services import dashboard_stats as ds

router = APIRouter()

VALID_SESSION_TYPES = {"meditation", "yoga", "chat", "healer", "breathing", "journal"}


# ── GET /api/dashboard/stats ──────────────────────────────────────────────────

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all 4 dashboard metrics for the current user."""

    # ── Healing streak + points (from existing challenges table) ──────────────
    streak_row = db.query(UserChallengeStreak).filter(
        UserChallengeStreak.user_id == current_user.id
    ).first()

    current_streak  = streak_row.current_streak  if streak_row else 0
    longest_streak  = streak_row.longest_streak  if streak_row else 0
    total_points    = streak_row.total_points     if streak_row else 0

    # ── Healing sessions — this week vs last week ─────────────────────────────
    now             = datetime.utcnow()
    week_ago        = now - timedelta(days=7)
    two_weeks_ago   = now - timedelta(days=14)

    this_week_count = db.query(func.count(JourneyActivity.id)).filter(
        JourneyActivity.user_id == current_user.id,
        JourneyActivity.logged_at >= week_ago,
    ).scalar() or 0

    last_week_count = db.query(func.count(JourneyActivity.id)).filter(
        JourneyActivity.user_id == current_user.id,
        JourneyActivity.logged_at >= two_weeks_ago,
        JourneyActivity.logged_at < week_ago,
    ).scalar() or 0

    weekly_change = this_week_count - last_week_count

    # ── Level progress ────────────────────────────────────────────────────────
    level_info = ds.get_level_progress(total_points)

    return {
        "healing_streak": {
            "current":  current_streak,
            "best":     longest_streak,
        },
        "souls_healing": {
            "count": ds.get_live_count(),
        },
        "soul_points": {
            "total":          total_points,
            "level":          level_info["current_level"],
            "next_level":     level_info["next_level"],
            "progress_pct":   level_info["progress_pct"],
            "points_to_next": level_info["points_to_next"],
        },
        "healing_sessions": {
            "this_week":     this_week_count,
            "weekly_change": weekly_change,
            "change_display": f"+{weekly_change}" if weekly_change > 0 else str(weekly_change),
        },
    }


# ── POST /api/dashboard/session/start/{type} ─────────────────────────────────

@router.post("/session/start/{session_type}")
async def start_session(
    session_type: str,
    current_user: User = Depends(get_current_user),
):
    if session_type not in VALID_SESSION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid session type. Use one of: {sorted(VALID_SESSION_TYPES)}")
    ds.session_start(current_user.id, session_type)
    return {"souls_healing_now": ds.get_live_count()}


# ── POST /api/dashboard/session/end ──────────────────────────────────────────

@router.post("/session/end")
async def end_session(
    current_user: User = Depends(get_current_user),
):
    ds.session_end(current_user.id)
    return {"souls_healing_now": ds.get_live_count()}


# ── GET /api/dashboard/live ───────────────────────────────────────────────────

@router.get("/live")
async def get_live_count():
    """Public endpoint — no auth required."""
    return {"souls_healing_now": ds.get_live_count()}
