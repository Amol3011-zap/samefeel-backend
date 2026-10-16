from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from app.routes import early_access
from app.routes import pulse
from app.routes import analytics
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
            conn.commit()
        print("Column migrations complete!")
    except Exception as e:
        print(f"Migration note: {e}")
    print("SameFeel API started successfully!")
    yield
    print("SameFeel API shutting down...")


_debug = os.getenv("DEBUG", "False").lower() in ("true", "1")

app = FastAPI(
    title="SameFeel API",
    description="Early access, Global Pulse check-ins, and visitor analytics",
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

app.include_router(early_access.router, prefix="/api/early-access", tags=["Early Access"])
app.include_router(pulse.router, prefix="/api/pulse", tags=["Global Pulse"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])


@app.get("/")
async def root():
    return {"message": "SameFeel API", "status": "running", "docs": "/docs"}


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
