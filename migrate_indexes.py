"""
Migration: Add performance indexes across all tables.
Run with: python migrate_indexes.py

Indexes added:
  users               — phone (unique, already exists), last_active_at, city, primary_problem
  matches             — (user_1_id, status), (user_2_id, status), matched_at
  chats               — (match_id, created_at), (sender_id, created_at)
  healer_sessions     — (user_id, status), (healer_id, status), scheduled_time
  meetup_attendees    — (user_id, status), meetup_id
  user_challenge_completions  — (user_id, challenge_date) [already exists, ensured]
  user_challenge_streaks      — total_points DESC (leaderboard queries)
  journey_activities  — (user_id, logged_at) [already exists, ensured]
  user_journeys       — user_id (unique, already exists)
"""

import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise SystemExit("DATABASE_URL is not set - refusing to run (no default database).")

print("Connecting to the database from DATABASE_URL...")
engine = create_engine(DB_URL)

INDEXES = [
    # ── users ──────────────────────────────────────────────────────────────────
    ("ix_users_last_active_at",
     "CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at DESC)"),

    ("ix_users_city",
     "CREATE INDEX IF NOT EXISTS ix_users_city ON users (city)"),

    ("ix_users_primary_problem",
     "CREATE INDEX IF NOT EXISTS ix_users_primary_problem ON users (primary_problem)"),

    ("ix_users_is_active",
     "CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active)"),

    # ── matches ────────────────────────────────────────────────────────────────
    ("ix_matches_user1_status",
     "CREATE INDEX IF NOT EXISTS ix_matches_user1_status ON matches (user_1_id, status)"),

    ("ix_matches_user2_status",
     "CREATE INDEX IF NOT EXISTS ix_matches_user2_status ON matches (user_2_id, status)"),

    ("ix_matches_matched_at",
     "CREATE INDEX IF NOT EXISTS ix_matches_matched_at ON matches (matched_at DESC)"),

    # ── chats ──────────────────────────────────────────────────────────────────
    ("ix_chats_match_created",
     "CREATE INDEX IF NOT EXISTS ix_chats_match_created ON chats (match_id, created_at DESC)"),

    ("ix_chats_sender_created",
     "CREATE INDEX IF NOT EXISTS ix_chats_sender_created ON chats (sender_id, created_at DESC)"),

    # ── healer_sessions ────────────────────────────────────────────────────────
    ("ix_healer_sessions_user_status",
     "CREATE INDEX IF NOT EXISTS ix_healer_sessions_user_status ON healer_sessions (user_id, status)"),

    ("ix_healer_sessions_healer_status",
     "CREATE INDEX IF NOT EXISTS ix_healer_sessions_healer_status ON healer_sessions (healer_id, status)"),

    ("ix_healer_sessions_scheduled_time",
     "CREATE INDEX IF NOT EXISTS ix_healer_sessions_scheduled_time ON healer_sessions (scheduled_time DESC)"),

    # ── meetup_attendees ───────────────────────────────────────────────────────
    ("ix_meetup_attendees_user_status",
     "CREATE INDEX IF NOT EXISTS ix_meetup_attendees_user_status ON meetup_attendees (user_id, status)"),

    ("ix_meetup_attendees_meetup_id",
     "CREATE INDEX IF NOT EXISTS ix_meetup_attendees_meetup_id ON meetup_attendees (meetup_id)"),

    # ── meetups ────────────────────────────────────────────────────────────────
    ("ix_meetups_city_scheduled",
     "CREATE INDEX IF NOT EXISTS ix_meetups_city_scheduled ON meetups (city, scheduled_time DESC)"),

    ("ix_meetups_problem_type",
     "CREATE INDEX IF NOT EXISTS ix_meetups_problem_type ON meetups (problem_type)"),

    # ── user_challenge_completions ─────────────────────────────────────────────
    ("ix_challenge_completions_user_date",
     "CREATE INDEX IF NOT EXISTS ix_challenge_completions_user_date ON user_challenge_completions (user_id, challenge_date DESC)"),

    ("ix_challenge_completions_challenge_id",
     "CREATE INDEX IF NOT EXISTS ix_challenge_completions_challenge_id ON user_challenge_completions (challenge_id)"),

    # ── user_challenge_streaks (leaderboard) ───────────────────────────────────
    ("ix_challenge_streaks_total_points",
     "CREATE INDEX IF NOT EXISTS ix_challenge_streaks_total_points ON user_challenge_streaks (total_points DESC)"),

    ("ix_challenge_streaks_current_streak",
     "CREATE INDEX IF NOT EXISTS ix_challenge_streaks_current_streak ON user_challenge_streaks (current_streak DESC)"),

    # ── journey_activities ─────────────────────────────────────────────────────
    ("ix_journey_activities_user_date",
     "CREATE INDEX IF NOT EXISTS ix_journey_activities_user_date ON journey_activities (user_id, logged_at DESC)"),

    ("ix_journey_activities_type",
     "CREATE INDEX IF NOT EXISTS ix_journey_activities_type ON journey_activities (activity_type)"),

    # ── user_journeys ──────────────────────────────────────────────────────────
    ("ix_user_journeys_user_id",
     "CREATE INDEX IF NOT EXISTS ix_user_journeys_user_id ON user_journeys (user_id)"),
]

with engine.connect() as conn:
    for name, sql in INDEXES:
        try:
            conn.execute(text(sql))
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    conn.commit()

print("\nIndex migration complete!")
print(f"  {len(INDEXES)} indexes processed")
