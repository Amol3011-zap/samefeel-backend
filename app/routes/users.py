from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    from app.services.auth import AuthService
    payload = AuthService.decode_token(credentials.credentials)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "phone": current_user.phone,
        "primary_problem": current_user.primary_problem,
        "secondary_problems": current_user.secondary_problems,
        "city": current_user.city,
        "distance_preference": current_user.distance_preference,
        "avatar_url": current_user.avatar_url,
        "bio": current_user.bio
    }


class UpdateProfileRequest(BaseModel):
    name: str = None
    bio: str = None
    avatar_url: str = None
    distance_preference: int = None


@router.put("/me")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if request.name:
        current_user.name = request.name
    if request.bio:
        current_user.bio = request.bio
    if request.avatar_url:
        current_user.avatar_url = request.avatar_url
    if request.distance_preference:
        current_user.distance_preference = request.distance_preference

    current_user.last_active_at = datetime.utcnow()
    db.commit()

    return {"message": "Profile updated"}
