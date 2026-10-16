import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Match, Healer, HealerSession, Meetup
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def require_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> None:
    """Allow the request only for an admin. Fails closed.

    Accepts either X-Admin-Key matching ADMIN_SECRET (constant-time compare;
    disabled when ADMIN_SECRET is unset) or a valid bearer token for a user
    whose role is "admin".
    """
    secret = os.getenv("ADMIN_SECRET", "")
    provided = request.headers.get("x-admin-key", "")
    if secret and provided and hmac.compare_digest(provided.encode(), secret.encode()):
        return

    if credentials is not None:
        from app.services.auth import AuthService

        payload = AuthService.decode_token(credentials.credentials)
        sub = payload.get("sub") if payload else None
        if sub is not None:
            try:
                user = db.query(User).filter(User.id == int(sub)).first()
            except (TypeError, ValueError):
                user = None
            if user is not None and getattr(user, "role", None) == "admin":
                return

    raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/stats", dependencies=[Depends(require_admin)])
async def get_stats(db: Session = Depends(get_db)):
    return {
        "total_users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),
        "total_matches": db.query(Match).count(),
        "verified_healers": db.query(Healer).filter(Healer.is_verified == True).count(),
        "total_sessions": db.query(HealerSession).count(),
        "total_meetups": db.query(Meetup).count(),
        "platform_health": "Healthy"
    }


class HealerRegistrationRequest(BaseModel):
    name: str
    phone: str
    email: str
    specializations: list
    hourly_rate: int
    bio: str
    experience_years: int
    certification_url: str


@router.post("/healers/register")
async def register_healer(request: HealerRegistrationRequest, db: Session = Depends(get_db)):
    existing = db.query(Healer).filter(Healer.phone == request.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Healer already registered")

    healer = Healer(
        name=request.name,
        phone=request.phone,
        email=request.email,
        specializations=request.specializations,
        hourly_rate=request.hourly_rate,
        bio=request.bio,
        experience_years=request.experience_years,
        certification_url=request.certification_url,
        is_verified=False
    )

    db.add(healer)
    db.commit()
    db.refresh(healer)

    return {"message": "Registration submitted. Verification pending.", "healer_id": healer.id}


@router.post("/healers/{healer_id}/verify", dependencies=[Depends(require_admin)])
async def verify_healer(healer_id: int, db: Session = Depends(get_db)):
    healer = db.query(Healer).filter(Healer.id == healer_id).first()

    if not healer:
        raise HTTPException(status_code=404, detail="Healer not found")

    healer.is_verified = True
    healer.verified_at = datetime.utcnow()
    db.commit()

    return {"message": f"{healer.name} is now verified!"}
