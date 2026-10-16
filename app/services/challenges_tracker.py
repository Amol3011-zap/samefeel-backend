"""
Daily Challenges Algorithm — adapted from daily_challenges_algorithm.py
for the SoulConnect FastAPI backend.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional


class ChallengeType(str, Enum):
    MEDITATION = "meditation"
    BREATHING = "breathing"
    JOURNAL = "journal"
    GRATITUDE = "gratitude"
    YOGA = "yoga"
    REFLECTION = "reflection"
    CHAT = "chat_support"
    HEALER = "healer_session"


CHALLENGE_LIBRARY = {
    "breathing_3min":     {"id": "breathing_3min",     "name": "3-Min Breathing",       "description": "Deep breathing to calm your mind",           "type": "breathing",      "duration": 3,  "points": 30,  "icon": "🌬️", "difficulty": "easy"},
    "gratitude_journal":  {"id": "gratitude_journal",  "name": "Gratitude Journal",      "description": "Write 3 things you're grateful for today",   "type": "gratitude",      "duration": 5,  "points": 50,  "icon": "📔", "difficulty": "easy"},
    "meditation_5min":    {"id": "meditation_5min",    "name": "5-Min Meditation",       "description": "Guided meditation for peace and clarity",     "type": "meditation",     "duration": 5,  "points": 70,  "icon": "🧘", "difficulty": "medium"},
    "yoga_10min":         {"id": "yoga_10min",         "name": "10-Min Yoga",            "description": "Gentle yoga flow for body and mind",          "type": "yoga",           "duration": 10, "points": 80,  "icon": "🧘‍♀️", "difficulty": "medium"},
    "reflection":         {"id": "reflection",         "name": "Daily Reflection",       "description": "Reflect on today's experiences",             "type": "reflection",     "duration": 5,  "points": 40,  "icon": "💭", "difficulty": "easy"},
    "journal_deep":       {"id": "journal_deep",       "name": "Deep Journal",           "description": "Write freely about your feelings",           "type": "journal",        "duration": 10, "points": 60,  "icon": "✍️", "difficulty": "medium"},
    "chat_support":       {"id": "chat_support",       "name": "Peer Support Chat",      "description": "Connect with someone for emotional support", "type": "chat_support",   "duration": 15, "points": 100, "icon": "💬", "difficulty": "hard"},
    "healer_session":     {"id": "healer_session",     "name": "Healer Session",         "description": "Book a session with a professional healer",  "type": "healer_session", "duration": 30, "points": 150, "icon": "✨", "difficulty": "hard"},
    "breathing_extended": {"id": "breathing_extended", "name": "Extended Breathing",     "description": "Advanced breathing techniques (10 min)",     "type": "breathing",      "duration": 10, "points": 60,  "icon": "🌬️", "difficulty": "medium"},
    "meditation_guided":  {"id": "meditation_guided",  "name": "Guided Meditation",      "description": "10-minute guided meditation",                "type": "meditation",     "duration": 10, "points": 100, "icon": "🧘", "difficulty": "medium"},
    "affirmations":       {"id": "affirmations",       "name": "Daily Affirmations",     "description": "Speak positive affirmations for yourself",   "type": "reflection",     "duration": 3,  "points": 25,  "icon": "💫", "difficulty": "easy"},
    "nature_walk":        {"id": "nature_walk",        "name": "Nature Walk",            "description": "Take a mindful walk in nature (15 min)",     "type": "reflection",     "duration": 15, "points": 75,  "icon": "🌿", "difficulty": "medium"},
}

TWO_WEEK_SCHEDULE = [
    {"day": 1,  "challenges": ["breathing_3min", "gratitude_journal", "meditation_5min"],         "theme": "Mindfulness Basics"},
    {"day": 2,  "challenges": ["meditation_5min", "reflection", "breathing_3min"],                "theme": "Inner Peace"},
    {"day": 3,  "challenges": ["gratitude_journal", "yoga_10min", "breathing_3min"],              "theme": "Body & Mind"},
    {"day": 4,  "challenges": ["journal_deep", "meditation_5min", "affirmations"],                "theme": "Self Discovery"},
    {"day": 5,  "challenges": ["breathing_extended", "reflection", "meditation_guided"],          "theme": "Deep Healing"},
    {"day": 6,  "challenges": ["yoga_10min", "journal_deep", "breathing_3min"],                   "theme": "Balance & Flow"},
    {"day": 7,  "challenges": ["meditation_guided", "gratitude_journal", "nature_walk"],          "theme": "Connection"},
    {"day": 8,  "challenges": ["breathing_3min", "meditation_5min", "journal_deep"],              "theme": "Reset Week"},
    {"day": 9,  "challenges": ["affirmations", "yoga_10min", "reflection"],                       "theme": "Empowerment"},
    {"day": 10, "challenges": ["meditation_guided", "breathing_extended", "gratitude_journal"],   "theme": "Abundance"},
    {"day": 11, "challenges": ["chat_support", "journal_deep", "breathing_3min"],                 "theme": "Connection"},
    {"day": 12, "challenges": ["yoga_10min", "meditation_5min", "reflection"],                    "theme": "Integration"},
    {"day": 13, "challenges": ["nature_walk", "breathing_extended", "meditation_guided"],         "theme": "Renewal"},
    {"day": 14, "challenges": ["gratitude_journal", "journal_deep", "breathing_3min"],            "theme": "Gratitude & Release"},
]

CYCLE_START = datetime(2024, 1, 1)


def get_current_cycle_day(reference_date: datetime = None) -> int:
    if reference_date is None:
        reference_date = datetime.utcnow()
    days = (reference_date - CYCLE_START).days
    return (days % 14) + 1


def get_todays_challenges(completed_ids: set, streak_bonus: int, reference_date: datetime = None) -> List[Dict]:
    cycle_day = get_current_cycle_day(reference_date)
    schedule = TWO_WEEK_SCHEDULE[cycle_day - 1]
    challenges = []
    for cid in schedule["challenges"]:
        c = dict(CHALLENGE_LIBRARY[cid])
        c["completed"] = cid in completed_ids
        c["streak_bonus"] = streak_bonus
        challenges.append(c)
    return challenges


def calculate_streak_bonus(current_streak: int) -> int:
    if current_streak <= 1:
        return 0
    elif current_streak == 2:
        return 5
    elif current_streak == 3:
        return 10
    else:
        return 5 * current_streak


def calculate_points(challenge_id: str, streak_bonus: int, actual_duration: Optional[int] = None) -> Dict:
    c = CHALLENGE_LIBRARY[challenge_id]
    base = c["points"]
    time_bonus = 0
    if actual_duration and actual_duration < c["duration"]:
        time_bonus = (c["duration"] - actual_duration) * 5
    total = base + streak_bonus + time_bonus
    return {"base_points": base, "streak_bonus": streak_bonus, "time_bonus": time_bonus, "total_points": total}


def should_increment_streak(last_date: Optional[datetime], today: datetime) -> bool:
    """Returns True if streak should increment (completed today and yesterday had activity or streak=0)."""
    if last_date is None:
        return True
    yesterday = (today - timedelta(days=1)).date()
    return last_date.date() == yesterday or last_date.date() == today.date()


def get_weekly_summary(completed_ids_by_date: Dict[str, set], reference_date: datetime = None) -> Dict:
    if reference_date is None:
        reference_date = datetime.utcnow()
    cycle_day = get_current_cycle_day(reference_date)
    cycle_start = reference_date - timedelta(days=cycle_day - 1)
    total_completed = 0
    total_points = 0
    days_completed = 0
    daily_breakdown = []
    for day in range(1, cycle_day + 1):
        day_date = (cycle_start + timedelta(days=day - 1)).date()
        completed_set = completed_ids_by_date.get(str(day_date), set())
        schedule = TWO_WEEK_SCHEDULE[day - 1]
        total = len(schedule["challenges"])
        completed = len([c for c in schedule["challenges"] if c in completed_set])
        day_pts = sum(CHALLENGE_LIBRARY[c]["points"] for c in schedule["challenges"] if c in completed_set)
        daily_breakdown.append({"day": day, "completed": completed, "total": total, "points": day_pts})
        total_completed += completed
        total_points += day_pts
        if completed == total:
            days_completed += 1
    return {
        "cycle_day": cycle_day,
        "theme": TWO_WEEK_SCHEDULE[cycle_day - 1]["theme"],
        "days_completed": days_completed,
        "challenges_completed": total_completed,
        "total_points_cycle": total_points,
        "daily_breakdown": daily_breakdown,
    }
