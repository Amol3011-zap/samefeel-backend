from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Healer, HealerSession, User
from app.routes.users import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


@router.get("/")
async def list_healers(
    problem: str = None,
    city: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(Healer).filter(Healer.is_verified == True)

    if problem:
        query = query.filter(Healer.specializations.contains([problem]))

    healers = query.all()

    return {
        "total": len(healers),
        "healers": [
            {
                "id": h.id,
                "name": h.name,
                "specializations": h.specializations,
                "hourly_rate": h.hourly_rate,
                "experience_years": h.experience_years,
                "rating": h.total_rating,
                "review_count": h.review_count,
                "avatar_url": h.avatar_url,
                "bio": h.bio
            }
            for h in healers
        ]
    }


@router.get("/{healer_id}")
async def get_healer_detail(healer_id: int, db: Session = Depends(get_db)):
    healer = db.query(Healer).filter(
        Healer.id == healer_id,
        Healer.is_verified == True
    ).first()

    if not healer:
        raise HTTPException(status_code=404, detail="Healer not found")

    return {
        "id": healer.id,
        "name": healer.name,
        "bio": healer.bio,
        "specializations": healer.specializations,
        "experience_years": healer.experience_years,
        "hourly_rate": healer.hourly_rate,
        "rating": healer.total_rating,
        "review_count": healer.review_count,
        "availability": healer.availability,
        "avatar_url": healer.avatar_url
    }


class BookSessionRequest(BaseModel):
    healer_id: int
    scheduled_time: datetime
    problem_type: str
    duration_minutes: int = 60
    user_notes: str = None


@router.post("/book-session")
async def book_healer_session(
    request: BookSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    healer = db.query(Healer).filter(
        Healer.id == request.healer_id,
        Healer.is_verified == True
    ).first()

    if not healer:
        raise HTTPException(status_code=404, detail="Healer not found")

    amount = int((request.duration_minutes / 60) * healer.hourly_rate)
    commission = int(amount * 0.25)
    healer_earning = amount - commission

    session = HealerSession(
        healer_id=request.healer_id,
        user_id=current_user.id,
        problem_type=request.problem_type,
        scheduled_time=request.scheduled_time,
        duration_minutes=request.duration_minutes,
        amount=amount,
        platform_commission=commission,
        healer_earning=healer_earning,
        user_notes=request.user_notes,
        status="pending"
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "healer": healer.name,
        "scheduled_time": session.scheduled_time,
        "amount": amount,
        "status": "pending",
        "message": "Session booked. Waiting for payment."
    }
