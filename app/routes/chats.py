from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Match, Chat, User
from app.routes.users import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class SendMessageRequest(BaseModel):
    match_id: int
    message: str


@router.post("/send")
async def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter(Match.id == request.match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if match.user_1_id != current_user.id and match.user_2_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    chat = Chat(
        match_id=request.match_id,
        sender_id=current_user.id,
        message=request.message,
        is_read=False
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return {"id": chat.id, "message": request.message, "sent_at": chat.created_at}


@router.get("/{match_id}/history")
async def get_chat_history(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if match.user_1_id != current_user.id and match.user_2_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    messages = db.query(Chat).filter(Chat.match_id == match_id).order_by(Chat.created_at).all()

    return {
        "match_id": match_id,
        "total_messages": len(messages),
        "messages": [
            {"id": m.id, "sender_id": m.sender_id, "message": m.message, "created_at": m.created_at}
            for m in messages
        ]
    }


class RateMatchRequest(BaseModel):
    match_id: int
    rating: int
    feedback: str = None


@router.post("/rate")
async def rate_match(
    request: RateMatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter(Match.id == request.match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if request.rating < 1 or request.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    if match.user_1_id == current_user.id:
        match.rating_from_1 = request.rating
        match.feedback_from_1 = request.feedback
    elif match.user_2_id == current_user.id:
        match.rating_from_2 = request.rating
        match.feedback_from_2 = request.feedback
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    match.completed_at = datetime.utcnow()
    db.commit()

    return {"message": "Rating saved"}
