"""
Migration: Create daily challenges tables
- user_challenge_streaks
- user_challenge_completions
Run with: python migrate_daily_challenges.py
"""

import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise SystemExit("DATABASE_URL is not set - refusing to run (no default database).")

print("Connecting to the database from DATABASE_URL...")
engine = create_engine(DB_URL)

with engine.connect() as conn:

    # ── user_challenge_streaks ────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS user_challenge_streaks (
            user_id             INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            current_streak      INTEGER NOT NULL DEFAULT 0,
            longest_streak      INTEGER NOT NULL DEFAULT 0,
            total_points        INTEGER NOT NULL DEFAULT 0,
            last_completion_date TIMESTAMP NULL
        )
    """))
    print("✓ user_challenge_streaks table ready")

    # ── user_challenge_completions ────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS user_challenge_completions (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            challenge_id    VARCHAR NOT NULL,
            challenge_date  TIMESTAMP NOT NULL,
            completed_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            actual_duration INTEGER NULL,
            points_earned   INTEGER NOT NULL DEFAULT 0
        )
    """))
    print("✓ user_challenge_completions table ready")

    # ── Index on (user_id, challenge_date) ────────────────────────────────────
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_challenge_completions_user_date
        ON user_challenge_completions (user_id, challenge_date)
    """))
    print("✓ index ix_challenge_completions_user_date ready")

    conn.commit()

print("\nDaily challenges migration complete!")
