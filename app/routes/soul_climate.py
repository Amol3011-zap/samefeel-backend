"""
Soul Climate — daily emotional-weather check-in for the authenticated user.

GET  /api/soul-climate/today?timezone=Asia/Kolkata
POST /api/soul-climate/checkin   {"weather": "clear-sky", "timezone": "Asia/Kolkata"}

Both require a valid bearer token; the user always comes from the token,
never from the request. Responses only ever contain the caller's own data.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routes.users import get_current_user
from app.services import soul_climate as sc

router = APIRouter()

WeatherId = Literal["clear-sky", "hope", "blooming", "fog", "heavy-rain", "storm"]


class CheckInRequest(BaseModel):
    weather: WeatherId
    timezone: str = Field(min_length=1, max_length=64)


def _day(tz_name: str):
    try:
        return sc.local_today(tz_name)
    except sc.InvalidTimezone:
        raise HTTPException(status_code=422, detail="Invalid timezone")


@router.get("/today")
async def get_today(
    timezone: str = Query(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Has the caller checked in on their current local date?"""
    day = _day(timezone)
    return sc.serialize(sc.get_for_date(db, current_user.id, day), day)


@router.post("/checkin")
async def check_in(
    payload: CheckInRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record today's check-in. One per user per local calendar day: a second
    attempt on the same day returns 409 with the existing check-in."""
    day = _day(payload.timezone)
    entry, created = sc.check_in(db, current_user.id, payload.weather, payload.timezone)
    body = sc.serialize(entry, day)
    if not created:
        raise HTTPException(status_code=409, detail={"message": "Already checked in today", **body})
    return body
