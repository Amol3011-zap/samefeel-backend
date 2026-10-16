from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Match, MatchStatus
from app.services.matching import MatchingService
from app.routes.users import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


@router.post("/find")
async def find_matches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    matches = MatchingService.find_matches(current_user, db, limit=3)

    if not matches:
        return {"message": "No matches found yet", "matches": [], "count": 0}

    response = []
    for match_data in matches:
        response.append({
            "id": match_data["user"].id,
            "name": match_data["user"].name,
            "problem": match_data["user"].primary_problem,
            "distance_km": round(match_data["distance_km"], 1),
            "match_score": match_data["score"],
            "match_reason": match_data["reason"],
            "city": match_data["user"].city,
            "problem_context": match_data["user"].problem_context
        })

    return {"message": f"Found {len(response)} matches", "matches": response, "count": len(response)}


class AcceptMatchRequest(BaseModel):
    matched_user_id: int


@router.post("/accept")
async def accept_match(
    request: AcceptMatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    matched_user = db.query(User).filter(User.id == request.matched_user_id).first()

    if not matched_user:
        raise HTTPException(status_code=404, detail="User not found")

    distance_km = MatchingService.haversine_distance(
        current_user.latitude, current_user.longitude,
        matched_user.latitude, matched_user.longitude
    )

    score, reason = MatchingService.calculate_match_score(current_user, matched_user, distance_km)

    match = MatchingService.create_match(
        user_1_id=current_user.id,
        user_2_id=matched_user.id,
        problem=current_user.primary_problem,
        distance_km=distance_km,
        score=score,
        reason=reason,
        db=db
    )

    match.status = MatchStatus.ACTIVE
    match.accepted_at = datetime.utcnow()
    db.commit()

    return {
        "match_id": match.id,
        "message": "Match accepted! Start chatting.",
        "matched_user": {
            "id": matched_user.id,
            "name": matched_user.name,
            "problem": matched_user.primary_problem
        }
    }


@router.get("/history")
async def match_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    matches = db.query(Match).filter(
        (Match.user_1_id == current_user.id) | (Match.user_2_id == current_user.id)
    ).order_by(Match.matched_at.desc()).all()

    return {
        "total_matches": len(matches),
        "matches": [
            {
                "id": m.id,
                "problem": m.problem_matched,
                "rating": m.rating_from_1 if m.user_1_id == current_user.id else m.rating_from_2,
                "matched_at": m.matched_at,
                "status": m.status
            }
            for m in matches
        ]
    }
