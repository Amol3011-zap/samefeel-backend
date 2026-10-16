"""
Unit tests for app/services/challenges_tracker.py
Run with: pytest tests/test_challenges_tracker.py -v
"""

import pytest
from datetime import datetime, timedelta
from app.services.challenges_tracker import (
    CHALLENGE_LIBRARY,
    TWO_WEEK_SCHEDULE,
    CYCLE_START,
    get_current_cycle_day,
    get_todays_challenges,
    calculate_streak_bonus,
    calculate_points,
    should_increment_streak,
    get_weekly_summary,
)


# ── get_current_cycle_day ─────────────────────────────────────────────────────

class TestGetCurrentCycleDay:
    def test_epoch_is_day_1(self):
        assert get_current_cycle_day(CYCLE_START) == 1

    def test_day_2(self):
        assert get_current_cycle_day(CYCLE_START + timedelta(days=1)) == 2

    def test_day_14(self):
        assert get_current_cycle_day(CYCLE_START + timedelta(days=13)) == 14

    def test_wraps_to_1_after_14(self):
        assert get_current_cycle_day(CYCLE_START + timedelta(days=14)) == 1

    def test_wraps_correctly_on_day_28(self):
        assert get_current_cycle_day(CYCLE_START + timedelta(days=27)) == 14

    def test_wraps_correctly_on_day_29(self):
        assert get_current_cycle_day(CYCLE_START + timedelta(days=28)) == 1

    def test_returns_int(self):
        result = get_current_cycle_day(CYCLE_START)
        assert isinstance(result, int)

    def test_always_between_1_and_14(self):
        for offset in range(100):
            day = get_current_cycle_day(CYCLE_START + timedelta(days=offset))
            assert 1 <= day <= 14


# ── get_todays_challenges ─────────────────────────────────────────────────────

class TestGetTodaysChallenges:
    def test_returns_3_challenges(self):
        result = get_todays_challenges(set(), 0, CYCLE_START)
        assert len(result) == 3

    def test_day1_challenges_match_schedule(self):
        result = get_todays_challenges(set(), 0, CYCLE_START)
        ids = [c["id"] for c in result]
        assert ids == TWO_WEEK_SCHEDULE[0]["challenges"]

    def test_completed_flag_set_correctly(self):
        completed = {"breathing_3min"}
        result = get_todays_challenges(completed, 0, CYCLE_START)
        breathing = next(c for c in result if c["id"] == "breathing_3min")
        others = [c for c in result if c["id"] != "breathing_3min"]
        assert breathing["completed"] is True
        assert all(c["completed"] is False for c in others)

    def test_streak_bonus_applied_to_all_challenges(self):
        result = get_todays_challenges(set(), 10, CYCLE_START)
        assert all(c["streak_bonus"] == 10 for c in result)

    def test_zero_streak_bonus(self):
        result = get_todays_challenges(set(), 0, CYCLE_START)
        assert all(c["streak_bonus"] == 0 for c in result)

    def test_all_challenges_have_required_keys(self):
        result = get_todays_challenges(set(), 0, CYCLE_START)
        required_keys = {"id", "name", "type", "duration", "points", "icon", "difficulty", "completed", "streak_bonus"}
        for c in result:
            assert required_keys.issubset(c.keys())

    def test_does_not_mutate_challenge_library(self):
        original_points = CHALLENGE_LIBRARY["breathing_3min"]["points"]
        get_todays_challenges(set(), 5, CYCLE_START)
        assert CHALLENGE_LIBRARY["breathing_3min"]["points"] == original_points

    def test_all_14_days_return_3_challenges(self):
        for day_offset in range(14):
            ref = CYCLE_START + timedelta(days=day_offset)
            result = get_todays_challenges(set(), 0, ref)
            assert len(result) == 3, f"Day {day_offset + 1} returned {len(result)} challenges"

    def test_all_challenge_ids_in_library(self):
        for day_offset in range(14):
            ref = CYCLE_START + timedelta(days=day_offset)
            result = get_todays_challenges(set(), 0, ref)
            for c in result:
                assert c["id"] in CHALLENGE_LIBRARY


# ── calculate_streak_bonus ────────────────────────────────────────────────────

class TestCalculateStreakBonus:
    def test_streak_0_returns_0(self):
        assert calculate_streak_bonus(0) == 0

    def test_streak_1_returns_0(self):
        assert calculate_streak_bonus(1) == 0

    def test_streak_2_returns_5(self):
        assert calculate_streak_bonus(2) == 5

    def test_streak_3_returns_10(self):
        assert calculate_streak_bonus(3) == 10

    def test_streak_4_returns_20(self):
        assert calculate_streak_bonus(4) == 20

    def test_streak_5_returns_25(self):
        assert calculate_streak_bonus(5) == 25

    def test_streak_10_returns_50(self):
        assert calculate_streak_bonus(10) == 50

    def test_bonus_increases_with_streak(self):
        bonuses = [calculate_streak_bonus(i) for i in range(1, 8)]
        assert bonuses == sorted(bonuses), "Bonus should be non-decreasing"

    def test_large_streak(self):
        assert calculate_streak_bonus(100) == 500


# ── calculate_points ──────────────────────────────────────────────────────────

class TestCalculatePoints:
    def test_base_points_no_bonus(self):
        result = calculate_points("breathing_3min", 0)
        assert result["base_points"] == 30
        assert result["streak_bonus"] == 0
        assert result["time_bonus"] == 0
        assert result["total_points"] == 30

    def test_streak_bonus_added(self):
        result = calculate_points("breathing_3min", 10)
        assert result["streak_bonus"] == 10
        assert result["total_points"] == 40

    def test_time_bonus_when_faster_than_duration(self):
        # breathing_3min has duration=3; complete in 1 min → 2 mins * 5 = +10
        result = calculate_points("breathing_3min", 0, actual_duration=1)
        assert result["time_bonus"] == 10
        assert result["total_points"] == 40

    def test_no_time_bonus_when_equal_duration(self):
        result = calculate_points("breathing_3min", 0, actual_duration=3)
        assert result["time_bonus"] == 0

    def test_no_time_bonus_when_slower_than_duration(self):
        result = calculate_points("breathing_3min", 0, actual_duration=5)
        assert result["time_bonus"] == 0

    def test_no_time_bonus_when_duration_is_none(self):
        result = calculate_points("breathing_3min", 0, actual_duration=None)
        assert result["time_bonus"] == 0

    def test_all_bonuses_stack(self):
        # breathing_3min base=30, streak_bonus=5, actual_duration=1 (2 min faster → +10)
        result = calculate_points("breathing_3min", 5, actual_duration=1)
        assert result["total_points"] == 30 + 5 + 10

    def test_hard_challenge_higher_base(self):
        result = calculate_points("healer_session", 0)
        assert result["base_points"] == 150

    def test_result_keys_present(self):
        result = calculate_points("meditation_5min", 0)
        assert set(result.keys()) == {"base_points", "streak_bonus", "time_bonus", "total_points"}

    def test_invalid_challenge_id_raises(self):
        with pytest.raises(KeyError):
            calculate_points("nonexistent_challenge", 0)


# ── should_increment_streak ───────────────────────────────────────────────────

class TestShouldIncrementStreak:
    def _today(self):
        return datetime(2024, 6, 15, 10, 0, 0)

    def test_no_last_date_returns_true(self):
        assert should_increment_streak(None, self._today()) is True

    def test_completed_yesterday_returns_true(self):
        yesterday = self._today() - timedelta(days=1)
        assert should_increment_streak(yesterday, self._today()) is True

    def test_completed_today_already_returns_true(self):
        # Same day completion (e.g. second challenge same day)
        same_day = self._today().replace(hour=8)
        assert should_increment_streak(same_day, self._today()) is True

    def test_completed_2_days_ago_returns_false(self):
        two_days_ago = self._today() - timedelta(days=2)
        assert should_increment_streak(two_days_ago, self._today()) is False

    def test_completed_last_week_returns_false(self):
        last_week = self._today() - timedelta(days=7)
        assert should_increment_streak(last_week, self._today()) is False

    def test_returns_bool(self):
        result = should_increment_streak(None, self._today())
        assert isinstance(result, bool)


# ── get_weekly_summary ────────────────────────────────────────────────────────

class TestGetWeeklySummary:
    def test_empty_completions_on_day_1(self):
        result = get_weekly_summary({}, CYCLE_START)
        assert result["cycle_day"] == 1
        assert result["challenges_completed"] == 0
        assert result["total_points_cycle"] == 0
        assert result["days_completed"] == 0
        assert len(result["daily_breakdown"]) == 1

    def test_full_day_1_completion(self):
        day1_date = str(CYCLE_START.date())
        day1_challenges = set(TWO_WEEK_SCHEDULE[0]["challenges"])
        result = get_weekly_summary({day1_date: day1_challenges}, CYCLE_START)
        assert result["challenges_completed"] == 3
        assert result["days_completed"] == 1
        assert result["total_points_cycle"] > 0

    def test_partial_completion(self):
        day1_date = str(CYCLE_START.date())
        partial = {day1_date: {"breathing_3min"}}
        result = get_weekly_summary(partial, CYCLE_START)
        assert result["challenges_completed"] == 1
        assert result["days_completed"] == 0  # Not a full day

    def test_result_keys_present(self):
        result = get_weekly_summary({}, CYCLE_START)
        assert set(result.keys()) == {
            "cycle_day", "theme", "days_completed",
            "challenges_completed", "total_points_cycle", "daily_breakdown"
        }

    def test_daily_breakdown_entry_keys(self):
        result = get_weekly_summary({}, CYCLE_START)
        entry = result["daily_breakdown"][0]
        assert set(entry.keys()) == {"day", "completed", "total", "points"}

    def test_daily_breakdown_length_equals_cycle_day(self):
        # On cycle day 5, breakdown should have 5 entries
        ref = CYCLE_START + timedelta(days=4)  # day 5
        result = get_weekly_summary({}, ref)
        assert len(result["daily_breakdown"]) == 5

    def test_total_is_always_3_per_day(self):
        ref = CYCLE_START + timedelta(days=6)  # day 7
        result = get_weekly_summary({}, ref)
        for entry in result["daily_breakdown"]:
            assert entry["total"] == 3

    def test_theme_matches_schedule(self):
        result = get_weekly_summary({}, CYCLE_START)
        assert result["theme"] == TWO_WEEK_SCHEDULE[0]["theme"]

    def test_points_calculation_correct(self):
        day1_date = str(CYCLE_START.date())
        day1_ids = TWO_WEEK_SCHEDULE[0]["challenges"]
        day1_challenges = set(day1_ids)
        expected_pts = sum(CHALLENGE_LIBRARY[cid]["points"] for cid in day1_ids)
        result = get_weekly_summary({day1_date: day1_challenges}, CYCLE_START)
        assert result["total_points_cycle"] == expected_pts


# ── CHALLENGE_LIBRARY integrity ───────────────────────────────────────────────

class TestChallengeLibraryIntegrity:
    def test_all_library_challenges_have_required_fields(self):
        required = {"id", "name", "description", "type", "duration", "points", "icon", "difficulty"}
        for cid, c in CHALLENGE_LIBRARY.items():
            assert required.issubset(c.keys()), f"Challenge '{cid}' missing fields"

    def test_all_schedule_challenge_ids_exist_in_library(self):
        for day in TWO_WEEK_SCHEDULE:
            for cid in day["challenges"]:
                assert cid in CHALLENGE_LIBRARY, f"'{cid}' in schedule but not in library"

    def test_all_difficulties_valid(self):
        valid = {"easy", "medium", "hard"}
        for cid, c in CHALLENGE_LIBRARY.items():
            assert c["difficulty"] in valid, f"Invalid difficulty for '{cid}'"

    def test_all_points_positive(self):
        for cid, c in CHALLENGE_LIBRARY.items():
            assert c["points"] > 0, f"Non-positive points for '{cid}'"

    def test_all_durations_positive(self):
        for cid, c in CHALLENGE_LIBRARY.items():
            assert c["duration"] > 0, f"Non-positive duration for '{cid}'"

    def test_schedule_has_14_days(self):
        assert len(TWO_WEEK_SCHEDULE) == 14

    def test_schedule_days_are_sequential(self):
        for i, day in enumerate(TWO_WEEK_SCHEDULE):
            assert day["day"] == i + 1
