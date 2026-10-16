from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models import User, UserJourney, JourneyActivity, ActivityTypeEnum
from app.routes.users import get_current_user
from app.services import journey_tracker as jt

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class ActivityRequest(BaseModel):
    activity_type: ActivityTypeEnum
    duration_minutes: int = 0
    intensity: int = Field(default=5, ge=1, le=10)
    notes: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_journey(user: User, db: Session) -> UserJourney:
    journey = db.query(UserJourney).filter(UserJourney.user_id == user.id).first()
    if not journey:
        journey = UserJourney(user_id=user.id)
        db.add(journey)
        db.commit()
        db.refresh(journey)
    return journey


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/activity")
async def log_activity(
    payload: ActivityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a new healing activity for the authenticated user."""
    journey = _get_or_create_journey(current_user, db)

    activity = JourneyActivity(
        journey_id=journey.id,
        user_id=current_user.id,
        activity_type=payload.activity_type,
        duration_minutes=payload.duration_minutes,
        intensity=payload.intensity,
        notes=payload.notes,
        logged_at=datetime.utcnow(),
    )
    db.add(activity)
    journey.total_activities += 1
    db.commit()
    db.refresh(activity)

    return {
        "message": "Activity logged",
        "activity_id": activity.id,
        "timestamp": activity.logged_at.isoformat(),
    }


@router.get("/progress")
async def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's current journey progress."""
    journey = _get_or_create_journey(current_user, db)
    activities = journey.activities

    if not activities:
        return {
            "user_id": current_user.id,
            "current_stage": "beginning",
            "stage_progress": 0,
            "overall_wellness_score": 0.0,
            "weekly_growth_percentage": 0.0,
            "total_activities": 0,
            "stage_metrics": {},
        }

    current_stage = jt.get_current_stage(activities)
    stage_progress = jt.calculate_stage_progress(activities, current_stage)
    metrics = jt.get_stage_metrics(activities)

    return {
        "user_id": current_user.id,
        "current_stage": current_stage.value,
        "stage_progress": round(stage_progress, 1),
        "overall_wellness_score": jt.calculate_wellness_score(activities),
        "weekly_growth_percentage": jt.calculate_weekly_growth(activities),
        "total_activities": len(activities),
        "stage_metrics": {
            k: {
                "completion_percentage": v.completion_percentage,
                "activities_completed": v.activities_completed,
                "days_in_stage": v.days_in_stage,
                "wellness_contribution": v.wellness_contribution,
            }
            for k, v in metrics.items()
        },
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.get("/activities")
async def get_activities(
    days: int = 30,
    activity_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's activity history (last N days)."""
    journey = _get_or_create_journey(current_user, db)
    cutoff = datetime.utcnow() - timedelta(days=days)

    acts = [a for a in journey.activities if a.logged_at >= cutoff]
    if activity_type:
        acts = [a for a in acts if a.activity_type.value == activity_type]

    acts.sort(key=lambda a: a.logged_at, reverse=True)

    return {
        "user_id": current_user.id,
        "activities": [
            {
                "id": a.id,
                "activity_type": a.activity_type.value,
                "duration_minutes": a.duration_minutes,
                "intensity": a.intensity,
                "notes": a.notes,
                "logged_at": a.logged_at.isoformat(),
            }
            for a in acts
        ],
        "count": len(acts),
    }


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return aggregated stats for the user's journey."""
    journey = _get_or_create_journey(current_user, db)
    activities = journey.activities

    if not activities:
        return {
            "user_id": current_user.id,
            "total_sessions": 0,
            "total_meditation_minutes": 0,
            "average_intensity": 0,
            "activity_breakdown": {},
            "weekly_trend": [],
        }

    total_meditation = sum(
        a.duration_minutes for a in activities
        if a.activity_type == ActivityTypeEnum.MEDITATION
    )
    avg_intensity = round(sum(a.intensity for a in activities) / len(activities), 1)

    breakdown = {}
    for a in activities:
        breakdown[a.activity_type.value] = breakdown.get(a.activity_type.value, 0) + 1

    now = datetime.utcnow()
    weekly_trend = []
    for week in range(4):
        start = now - timedelta(days=7 * (week + 1))
        end = now - timedelta(days=7 * week)
        count = sum(1 for a in activities if start <= a.logged_at <= end)
        weekly_trend.append({"week": f"Week {4 - week}", "activities": count})
    weekly_trend.reverse()

    return {
        "user_id": current_user.id,
        "total_sessions": len(activities),
        "total_meditation_minutes": total_meditation,
        "average_intensity": avg_intensity,
        "activity_breakdown": breakdown,
        "weekly_trend": weekly_trend,
    }
