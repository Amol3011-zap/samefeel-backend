"""
Consent Management — GDPR-compliant consent recording.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models import UserConsent

router = APIRouter()


class ConsentCreate(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[int] = None          # supplied by authenticated callers
    privacy_policy_accepted: bool = False
    terms_accepted: bool = False
    safety_policy_accepted: bool = False
    community_guidelines_accepted: bool = False
    analytics_consent: bool = False
    marketing_consent: bool = False
    policy_version: str = "1.0"


class ConsentResponse(BaseModel):
    id: int
    policy_version: str
    analytics_consent: bool
    marketing_consent: bool
    accepted_at: datetime

    class Config:
        from_attributes = True


@router.post("/record")
def record_consent(
    data: ConsentCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Record user consent. Called on cookie banner accept."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    consent = UserConsent(
        session_id=data.session_id,
        privacy_policy_accepted=data.privacy_policy_accepted,
        terms_accepted=data.terms_accepted,
        safety_policy_accepted=data.safety_policy_accepted,
        community_guidelines_accepted=data.community_guidelines_accepted,
        analytics_consent=data.analytics_consent,
        marketing_consent=data.marketing_consent,
        policy_version=data.policy_version,
        ip_address=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    return {
        "status": "recorded",
        "consent_id": consent.id,
        "policy_version": consent.policy_version,
    }


@router.post("/record-authenticated")
def record_consent_authenticated(
    data: ConsentCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Record consent for logged-in users (user_id passed in request body)."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    consent = UserConsent(
        user_id=data.user_id,
        session_id=data.session_id,
        privacy_policy_accepted=data.privacy_policy_accepted,
        terms_accepted=data.terms_accepted,
        safety_policy_accepted=data.safety_policy_accepted,
        community_guidelines_accepted=data.community_guidelines_accepted,
        analytics_consent=data.analytics_consent,
        marketing_consent=data.marketing_consent,
        policy_version=data.policy_version,
        ip_address=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    return {
        "status": "recorded",
        "consent_id": consent.id,
        "policy_version": consent.policy_version,
    }
