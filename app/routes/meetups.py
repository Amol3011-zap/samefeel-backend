from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Meetup, MeetupAttendee, User
from app.routes.users import get_current_user
from pydantic import BaseModel

router = APIRouter()


@router.get("/")
async def list_meetups(
    problem: str = None,
    city: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(Meetup).filter(Meetup.status == "upcoming")

    if problem:
        query = query.filter(Meetup.problem_type == problem)

    if city:
        query = query.filter(Meetup.city == city)

    meetups = query.order_by(Meetup.scheduled_time).all()

    return {
        "total": len(meetups),
        "meetups": [
            {
                "id": m.id,
                "title": m.title,
                "problem": m.problem_type,
                "location": m.location_name,
                "city": m.city,
                "scheduled_time": m.scheduled_time,
                "duration_minutes": m.duration_minutes,
                "attendees": len(m.attendees),
                "max_attendees": m.max_attendees,
                "rating": m.avg_rating,
                "description": m.description
            }
            for m in meetups
        ]
    }


@router.get("/my-meetups")
async def my_meetups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    attendances = db.query(MeetupAttendee).filter(
        MeetupAttendee.user_id == current_user.id
    ).all()

    return {
        "total": len(attendances),
        "meetups": [
            {
                "id": a.meetup.id,
                "title": a.meetup.title,
                "scheduled_time": a.meetup.scheduled_time,
                "location": a.meetup.location_name,
                "status": a.status,
                "rating": a.rating
            }
            for a in attendances
        ]
    }


@router.get("/{meetup_id}")
async def get_meetup_detail(meetup_id: int, db: Session = Depends(get_db)):
    meetup = db.query(Meetup).filter(Meetup.id == meetup_id).first()

    if not meetup:
        raise HTTPException(status_code=404, detail="Meetup not found")

    return {
        "id": meetup.id,
        "title": meetup.title,
        "description": meetup.description,
        "problem": meetup.problem_type,
        "location": meetup.location_name,
        "coordinates": {"lat": meetup.latitude, "lng": meetup.longitude},
        "scheduled_time": meetup.scheduled_time,
        "duration_minutes": meetup.duration_minutes,
        "attendees": len(meetup.attendees),
        "max_attendees": meetup.max_attendees,
        "rating": meetup.avg_rating,
        "status": meetup.status
    }


class JoinMeetupRequest(BaseModel):
    meetup_id: int


@router.post("/join")
async def join_meetup(
    request: JoinMeetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meetup = db.query(Meetup).filter(Meetup.id == request.meetup_id).first()

    if not meetup:
        raise HTTPException(status_code=404, detail="Meetup not found")

    existing = db.query(MeetupAttendee).filter(
        MeetupAttendee.meetup_id == request.meetup_id,
        MeetupAttendee.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already joined")

    if len(meetup.attendees) >= meetup.max_attendees:
        raise HTTPException(status_code=400, detail="Meetup is full")

    attendee = MeetupAttendee(
        meetup_id=request.meetup_id,
        user_id=current_user.id,
        status="confirmed"
    )

    db.add(attendee)
    db.commit()

    return {
        "message": "Joined meetup!",
        "meetup": meetup.title,
        "scheduled_time": meetup.scheduled_time,
        "location": meetup.location_name
    }
