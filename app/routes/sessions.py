from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import HealerSession, User
from app.routes.users import get_current_user

router = APIRouter()


@router.get("/my-sessions")
async def my_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(HealerSession).filter(
        HealerSession.user_id == current_user.id
    ).order_by(HealerSession.scheduled_time.desc()).all()

    return {
        "total": len(sessions),
        "sessions": [
            {
                "id": s.id,
                "healer_id": s.healer_id,
                "scheduled_time": s.scheduled_time,
                "duration_minutes": s.duration_minutes,
                "amount": s.amount,
                "status": s.status,
                "payment_status": s.payment_status
            }
            for s in sessions
        ]
    }
