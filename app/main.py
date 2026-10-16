from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from app.routes import auth, users, matching, chats, healers, sessions, meetups, admin
from app.routes import journey
from app.routes import challenges
from app.routes import dashboard
from app.routes import analytics, consent, privacy
from app.routes import early_access
from app.routes import pulse
from app.routes import soul_climate
from app.config import get_allowed_origins
from app.database import engine, Base

# Must import all models before create_all so SQLAlchemy registers every table
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sqlalchemy import text
    print("Database connection initialized")
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Running column migrations...")
    try:
        from app.database import get_engine
        with get_engine().connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'user'"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS state VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS country VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR"))
            # Waitlist / early access columns
            conn.execute(text("ALTER TABLE early_access_submissions ADD COLUMN IF NOT EXISTS struggle VARCHAR(100)"))
            conn.execute(text("ALTER TABLE early_access_submissions ADD COLUMN IF NOT EXISTS referral_code VARCHAR(100)"))
            conn.execute(text("ALTER TABLE early_access_submissions ADD COLUMN IF NOT EXISTS referral_source VARCHAR(50)"))
            conn.execute(text("ALTER TABLE early_access_submissions ALTER COLUMN name DROP NOT NULL"))
            # Global Pulse — internal-record location fields (never exposed by any API response)
            conn.execute(text("ALTER TABLE pulse_checkins ADD COLUMN IF NOT EXISTS city VARCHAR(120)"))
            conn.execute(text("ALTER TABLE pulse_checkins ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45)"))
            # Visitor analytics — hostname + internal-traffic flag (see app/routes/analytics.py)
            conn.execute(text("ALTER TABLE visitor_analytics ADD COLUMN IF NOT EXISTS hostname VARCHAR(255)"))
            conn.execute(text("ALTER TABLE visitor_analytics ADD COLUMN IF NOT EXISTS is_internal BOOLEAN DEFAULT FALSE NOT NULL"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_visitor_analytics_hostname ON visitor_analytics (hostname)"
            ))
            # Soul Climate daily check-in (reuses user_moods; one per user per local date)
            conn.execute(text("ALTER TABLE user_moods ADD COLUMN IF NOT EXISTS local_date DATE"))
            conn.execute(text("ALTER TABLE user_moods ADD COLUMN IF NOT EXISTS timezone VARCHAR(64)"))
            conn.execute(text("ALTER TABLE user_moods ADD COLUMN IF NOT EXISTS source VARCHAR(20)"))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_user_moods_daily_checkin "
                "ON user_moods (user_id, local_date) WHERE source = 'soul_climate'"
            ))
            conn.commit()
        print("Column migrations complete!")
    except Exception as e:
        print(f"Migration note: {e}")
    print("SoulConnect API started successfully!")
    yield
    print("SoulConnect API shutting down...")


_debug = os.getenv("DEBUG", "False").lower() in ("true", "1")

app = FastAPI(
    title="SoulConnect API",
    description="Problem-solver peer support + healer platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

_allowed_origins = get_allowed_origins()  # required + validated; fails startup if missing/invalid

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(matching.router, prefix="/api/matches", tags=["Matching"])
app.include_router(chats.router, prefix="/api/chats", tags=["Chat"])
app.include_router(healers.router, prefix="/api/healers", tags=["Healers"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(meetups.router, prefix="/api/meetups", tags=["Meetups"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(journey.router, prefix="/api/journey", tags=["Soul Journey"])
app.include_router(challenges.router, prefix="/api/challenges", tags=["Daily Challenges"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(consent.router, prefix="/api/consent", tags=["Consent"])
app.include_router(privacy.router, prefix="/api/privacy", tags=["Privacy & GDPR"])
app.include_router(early_access.router, prefix="/api/early-access", tags=["Early Access"])
app.include_router(pulse.router, prefix="/api/pulse", tags=["Global Pulse"])
app.include_router(soul_climate.router, prefix="/api/soul-climate", tags=["Soul Climate"])


@app.get("/")
async def root():
    return {"message": "SoulConnect API", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        # Uvicorn's default forwarded_allow_ips is "127.0.0.1", which makes
        # it trust X-Forwarded-For from any loopback connection — including
        # a local attacker or a direct (non-proxied) client. Disabling it
        # means request.client.host is always the true direct TCP peer, so
        # app/services/client_ip.py's TRUSTED_PROXY_IPS allowlist is the
        # only thing that can ever make X-Forwarded-For trusted.
        forwarded_allow_ips=[],
    )
