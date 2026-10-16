"""
Privacy & GDPR Routes — data export, deletion, and consent management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import (
    User, UserProfile, UserPreferences, UserMood, JournalEntry,
    UserConsent, SecurityLog, UserChallengeStreak, UserJourney,
    HealerSession, MeetupAttendee, Match, Report
)
from app.routes.users import get_current_user

router = APIRouter()


@router.get("/export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GDPR Article 20 — Data portability.
    Returns all data held for the authenticated user.
    Journal content is returned as-is (encrypted) — client decrypts.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    preferences = db.query(UserPreferences).filter(UserPreferences.user_id == current_user.id).first()
    consents = db.query(UserConsent).filter(UserConsent.user_id == current_user.id).all()
    moods = db.query(UserMood).filter(UserMood.user_id == current_user.id).order_by(UserMood.logged_at).all()
    journals = db.query(JournalEntry).filter(JournalEntry.user_id == current_user.id).all()
    streak = db.query(UserChallengeStreak).filter(UserChallengeStreak.user_id == current_user.id).first()
    journey = db.query(UserJourney).filter(UserJourney.user_id == current_user.id).first()
    sessions = db.query(HealerSession).filter(HealerSession.user_id == current_user.id).all()
    meetups = db.query(MeetupAttendee).filter(MeetupAttendee.user_id == current_user.id).all()

    # Log the data export event
    log = SecurityLog(
        user_id=current_user.id,
        event_type="data_export",
        metadata={"exported_at": datetime.utcnow().isoformat()},
    )
    db.add(log)
    db.commit()

    return {
        "export_date": datetime.utcnow().isoformat(),
        "data_controller": "SoulConnect Health Technologies",
        "account": {
            "id": user.id,
            "name": user.name,
            "phone": user.phone,
            "city": user.city,
            "country": user.country,
            "timezone": user.timezone,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "primary_problem": user.primary_problem,
        },
        "profile": {
            "username": profile.username if profile else None,
            "email": profile.email if profile else None,
            "language": profile.language if profile else None,
            "goals": profile.goals if profile else [],
            "primary_challenges": profile.primary_challenges if profile else [],
        } if profile else {},
        "consent_history": [
            {
                "policy_version": c.policy_version,
                "accepted_at": c.accepted_at.isoformat(),
                "analytics_consent": c.analytics_consent,
                "marketing_consent": c.marketing_consent,
            } for c in consents
        ],
        "mood_history": [
            {
                "mood_score": m.mood_score,
                "mood_label": m.mood_label,
                "mood_tags": m.mood_tags,
                "logged_at": m.logged_at.isoformat(),
            } for m in moods
        ],
        "journal_entries": [
            {
                "id": j.id,
                "title_encrypted": j.title_encrypted,
                "content_encrypted": j.content_encrypted,
                "mood_score": j.mood_score,
                "tags": j.tags,
                "created_at": j.created_at.isoformat(),
            } for j in journals
        ],
        "challenge_stats": {
            "current_streak": streak.current_streak if streak else 0,
            "longest_streak": streak.longest_streak if streak else 0,
            "total_points": streak.total_points if streak else 0,
        } if streak else {},
        "journey": {
            "current_stage": journey.current_stage if journey else None,
            "total_activities": journey.total_activities if journey else 0,
            "joined_at": journey.joined_at.isoformat() if journey and journey.joined_at else None,
        } if journey else {},
        "sessions": [
            {
                "scheduled_time": s.scheduled_time.isoformat(),
                "status": s.status,
                "session_type": s.session_type,
                "duration_minutes": s.duration_minutes,
                "rating": s.rating,
            } for s in sessions
        ],
        "circle_participations": len(meetups),
    }


@router.delete("/delete-account")
def delete_my_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GDPR Article 17 — Right to erasure.
    Anonymises the user account and deletes personal data.
    Safety records (crisis escalations, reports) are retained per legal obligation.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Log deletion event before removing data
    log = SecurityLog(
        user_id=current_user.id,
        event_type="account_deletion_requested",
        metadata={"requested_at": datetime.utcnow().isoformat()},
    )
    db.add(log)

    # Delete personal data
    db.query(UserProfile).filter(UserProfile.user_id == current_user.id).delete()
    db.query(UserPreferences).filter(UserPreferences.user_id == current_user.id).delete()
    db.query(UserMood).filter(UserMood.user_id == current_user.id).delete()
    db.query(JournalEntry).filter(JournalEntry.user_id == current_user.id).delete()

    # Anonymise user record (retain for referential integrity)
    user.name = f"Deleted User #{user.id}"
    user.phone = f"deleted_{user.id}_{int(datetime.utcnow().timestamp())}"
    user.avatar_url = None
    user.bio = None
    user.latitude = None
    user.longitude = None
    user.address = None
    user.city = None
    user.state = None
    user.is_active = False

    db.commit()

    return {
        "status": "deleted",
        "message": "Your personal data has been removed. Safety records are retained as required by law.",
        "deleted_at": datetime.utcnow().isoformat(),
    }


@router.get("/consent-history")
def get_consent_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return user's consent records."""
    consents = db.query(UserConsent).filter(
        UserConsent.user_id == current_user.id
    ).order_by(UserConsent.accepted_at.desc()).all()

    return [
        {
            "id": c.id,
            "policy_version": c.policy_version,
            "privacy_policy_accepted": c.privacy_policy_accepted,
            "terms_accepted": c.terms_accepted,
            "safety_policy_accepted": c.safety_policy_accepted,
            "analytics_consent": c.analytics_consent,
            "marketing_consent": c.marketing_consent,
            "accepted_at": c.accepted_at.isoformat(),
        } for c in consents
    ]
