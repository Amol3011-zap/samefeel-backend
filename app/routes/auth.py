from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth import AuthService
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class SignupRequest(BaseModel):
    phone: str
    name: str
    primary_problem: str
    secondary_problems: list = []
    age: int = None
    gender: str = None
    role: str = "user"
    country: str = None
    state: str = None
    city: str = None
    latitude: float = 19.076
    longitude: float = 72.8777
    address: str = ""
    timezone: str = "Asia/Kolkata"
    distance_preference: int = 10


class SignupResponse(BaseModel):
    id: int
    phone: str
    name: str
    access_token: str
    token_type: str = "bearer"


@router.post("/signup", response_model=SignupResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.phone == request.phone).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")

    user = User(
        phone=request.phone,
        name=request.name,
        primary_problem=request.primary_problem,
        secondary_problems=request.secondary_problems,
        age=request.age,
        gender=request.gender,
        role=request.role,
        country=request.country,
        state=request.state,
        city=request.city,
        latitude=request.latitude,
        longitude=request.longitude,
        address=request.address,
        timezone=request.timezone,
        distance_preference=request.distance_preference,
        phone_verified=True,
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = AuthService.create_access_token(
        data={"sub": str(user.id), "phone": user.phone}
    )

    return SignupResponse(
        id=user.id,
        phone=user.phone,
        name=user.name,
        access_token=access_token
    )


class LoginRequest(BaseModel):
    phone: str
    password: str = None


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == request.phone).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    user.last_active_at = datetime.utcnow()
    db.commit()

    access_token = AuthService.create_access_token(
        data={"sub": str(user.id), "phone": user.phone}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "id": user.id,
        "user_id": user.id,
        "name": user.name,
        "phone": user.phone,
        "role": user.role or "user",
    }
