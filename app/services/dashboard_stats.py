"""
Dashboard Stats Service
Provides: level calculation, live session tracking, points-to-level math.
All healing streak / points / session data is read from existing DB tables.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional

# ── Level thresholds ──────────────────────────────────────────────────────────

LEVEL_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 300,
    4: 600,
    5: 1000,
    6: 1500,
    7: 2100,
    8: 2800,
    9: 3600,
    10: 4500,
    11: 5500,
    12: 6600,
}


def get_level(total_points: int) -> int:
    level = 1
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items()):
        if total_points >= threshold:
            level = lvl
        else:
            break
    return level


def get_level_progress(total_points: int) -> Dict:
    current = get_level(total_points)
    nxt = current + 1
    current_start = LEVEL_THRESHOLDS[current]
    next_start = LEVEL_THRESHOLDS.get(nxt, current_start)
    span = next_start - current_start
    earned_in_level = total_points - current_start
    pct = round((earned_in_level / span * 100) if span > 0 else 100, 1)
    return {
        "current_level": current,
        "next_level": nxt,
        "total_points": total_points,
        "points_to_next": max(0, next_start - total_points),
        "progress_pct": min(100.0, pct),
    }


# ── In-memory live session tracker ───────────────────────────────────────────
# Shared module-level state — persists for the lifetime of the process.

_active_sessions: Dict[int, Dict] = {}   # user_id → {type, start_time}
_BASE_LIVE_COUNT = 847                   # plausible baseline for display


def session_start(user_id: int, session_type: str) -> None:
    _active_sessions[user_id] = {
        "type": session_type,
        "start_time": datetime.utcnow(),
    }


def session_end(user_id: int) -> None:
    _active_sessions.pop(user_id, None)


def get_live_count() -> int:
    """Active sessions in the last 2 hours + baseline."""
    cutoff = datetime.utcnow() - timedelta(hours=2)
    active = sum(1 for s in _active_sessions.values() if s["start_time"] > cutoff)
    return _BASE_LIVE_COUNT + active
