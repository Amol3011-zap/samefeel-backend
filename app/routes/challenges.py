from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import time

from app.database import get_db
from app.models import User, UserChallengeStreak, UserChallengeCompletion, UserJourney, JourneyActivity, ActivityTypeEnum
from app.routes.users import get_current_user
from app.services import challenges_tracker as ct
from pydantic import BaseModel

router = APIRouter()

# Maps challenge type → Soul Journey activity type
CHALLENGE_TO_JOURNEY = {
    "meditation":     ActivityTypeEnum.MEDITATION,
    "breathing":      ActivityTypeEnum.MEDITATION,
    "journal":        ActivityTypeEnum.JOURNAL,
    "gratitude":      ActivityTypeEnum.JOURNAL,
    "yoga":           ActivityTypeEnum.MEDITATION,
    "reflection":     ActivityTypeEnum.REFLECTION,
    "chat_support":   ActivityTypeEnum.CHAT_SESSION,
    "healer_session": ActivityTypeEnum.HEALER_BOOKING,
}

# ── In-memory cache (user_id → (timestamp, data)) ─────────────────────────────
_today_cache: dict = {}
CACHE_TTL = 3600  # 1 hour


def _get_cached(user_id: int):
    entry = _today_cache.get(user_id)
    if entry and time.time() - entry[0] < CACHE_TTL:
        return entry[1]
    return None


def _set_cached(user_id: int, data: dict):
    _today_cache[user_id] = (time.time(), data)


def _invalidate_cache(user_id: int):
    _today_cache.pop(user_id, None)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CompleteRequest(BaseModel):
    actual_duration: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_streak(user: User, db: Session) -> UserChallengeStreak:
    streak = db.query(UserChallengeStreak).filter(UserChallengeStreak.user_id == user.id).first()
    if not streak:
        streak = UserChallengeStreak(user_id=user.id)
        db.add(streak)
        db.commit()
        db.refresh(streak)
    return streak


def _completed_today_ids(user_id: int, db: Session) -> set:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    rows = db.query(UserChallengeCompletion).filter(
        UserChallengeCompletion.user_id == user_id,
        UserChallengeCompletion.challenge_date >= today_start,
        UserChallengeCompletion.challenge_date < today_end,
    ).all()
    return {r.challenge_id for r in rows}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/today")
async def get_today_challenges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return today's 3 challenges with completion status. Cached per-user for 1 hour."""
    cached = _get_cached(current_user.id)
    if cached:
        return cached

    streak = _get_or_create_streak(current_user, db)
    completed = _completed_today_ids(current_user.id, db)
    bonus = ct.calculate_streak_bonus(streak.current_streak)
    challenges = ct.get_todays_challenges(completed, bonus)

    completed_count = sum(1 for c in challenges if c["completed"])
    points_remaining = sum(
        c["points"] + bonus for c in challenges if not c["completed"]
    )

    response = {
        "cycle_day": ct.get_current_cycle_day(),
        "theme": ct.TWO_WEEK_SCHEDULE[ct.get_current_cycle_day() - 1]["theme"],
        "challenges": challenges,
        "completed": completed_count,
        "total": len(challenges),
        "points_earned_today": sum(c["points"] + bonus for c in challenges if c["completed"]),
        "points_remaining": points_remaining,
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "total_points": streak.total_points,
    }

    _set_cached(current_user.id, response)
    return response


@router.post("/complete/{challenge_id}")
async def complete_challenge(
    challenge_id: str,
    payload: CompleteRequest = CompleteRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a challenge as completed and award points."""
    if challenge_id not in ct.CHALLENGE_LIBRARY:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Check not already completed today
    completed = _completed_today_ids(current_user.id, db)
    if challenge_id in completed:
        raise HTTPException(status_code=400, detail="Challenge already completed today")

    streak = _get_or_create_streak(current_user, db)
    bonus = ct.calculate_streak_bonus(streak.current_streak)
    pts = ct.calculate_points(challenge_id, bonus, payload.actual_duration)

    # Save completion
    now = datetime.utcnow()
    completion = UserChallengeCompletion(
        user_id=current_user.id,
        challenge_id=challenge_id,
        challenge_date=now,
        completed_at=now,
        actual_duration=payload.actual_duration,
        points_earned=pts["total_points"],
    )
    db.add(completion)

    # Update streak
    if ct.should_increment_streak(streak.last_completion_date, now):
        if streak.last_completion_date is None or streak.last_completion_date.date() < now.date():
            streak.current_streak += 1
    else:
        streak.current_streak = 1

    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak

    streak.total_points += pts["total_points"]
    streak.last_completion_date = now

    # Auto-log to Soul Journey activities
    challenge_info = ct.CHALLENGE_LIBRARY[challenge_id]
    journey_activity_type = CHALLENGE_TO_JOURNEY.get(challenge_info["type"])
    if journey_activity_type:
        journey = db.query(UserJourney).filter(UserJourney.user_id == current_user.id).first()
        if not journey:
            journey = UserJourney(user_id=current_user.id)
            db.add(journey)
            db.flush()
        intensity = min(10, max(1, round(challenge_info["points"] / 15)))
        journey_entry = JourneyActivity(
            journey_id=journey.id,
            user_id=current_user.id,
            activity_type=journey_activity_type,
            duration_minutes=challenge_info["duration"],
            intensity=intensity,
            notes=f"Auto-logged from Daily Challenge: {challenge_info['name']}",
            logged_at=now,
        )
        db.add(journey_entry)
        journey.total_activities += 1

    db.commit()

    # Invalidate cache so next GET /today reflects the completion
    _invalidate_cache(current_user.id)

    return {
        "challenge_id": challenge_id,
        "challenge_name": ct.CHALLENGE_LIBRARY[challenge_id]["name"],
        "base_points": pts["base_points"],
        "streak_bonus": pts["streak_bonus"],
        "time_bonus": pts["time_bonus"],
        "total_points": pts["total_points"],
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "total_earned": streak.total_points,
    }


@router.get("/weekly-summary")
async def get_weekly_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return progress for the current 2-week cycle."""
    cycle_day = ct.get_current_cycle_day()
    cycle_start_dt = datetime.utcnow() - timedelta(days=cycle_day - 1)

    # Fetch all completions in this cycle
    completions = db.query(UserChallengeCompletion).filter(
        UserChallengeCompletion.user_id == current_user.id,
        UserChallengeCompletion.challenge_date >= cycle_start_dt.replace(hour=0, minute=0, second=0, microsecond=0),
    ).all()

    # Build {date_str: set_of_challenge_ids}
    by_date: dict = {}
    for c in completions:
        ds = str(c.challenge_date.date())
        by_date.setdefault(ds, set()).add(c.challenge_id)

    return ct.get_weekly_summary(by_date)


@router.get("/leaderboard")
async def get_leaderboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return top 10 users by total points, plus current user's rank."""
    # Top 10 by total_points
    top_rows = (
        db.query(UserChallengeStreak, User)
        .join(User, User.id == UserChallengeStreak.user_id)
        .filter(UserChallengeStreak.total_points > 0)
        .order_by(UserChallengeStreak.total_points.desc())
        .limit(10)
        .all()
    )

    top10 = []
    my_rank_in_top10 = None
    for rank, (streak, user) in enumerate(top_rows, start=1):
        name = user.name or "Anonymous"
        # Mask name for privacy: "Amol" → "A***"
        masked = name[0].upper() + "***" if len(name) > 1 else name[0].upper()
        is_me = user.id == current_user.id
        if is_me:
            my_rank_in_top10 = rank
        top10.append({
            "rank": rank,
            "name": masked,
            "points": streak.total_points,
            "streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "is_me": is_me,
        })

    # Current user's overall rank (if not in top 10)
    my_streak = db.query(UserChallengeStreak).filter(
        UserChallengeStreak.user_id == current_user.id
    ).first()

    my_points = my_streak.total_points if my_streak else 0
    my_current_streak = my_streak.current_streak if my_streak else 0

    if my_rank_in_top10:
        my_rank = my_rank_in_top10
    else:
        # Count how many users have more points
        above_me = db.query(UserChallengeStreak).filter(
            UserChallengeStreak.total_points > my_points
        ).count()
        my_rank = above_me + 1

    return {
        "top10": top10,
        "my_rank": my_rank,
        "my_points": my_points,
        "my_streak": my_current_streak,
    }
