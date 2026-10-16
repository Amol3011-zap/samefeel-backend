"""
Unit tests for app/services/pulse_aggregation.py
Run with: pytest tests/test_pulse_aggregation.py -v
"""
from datetime import datetime, timedelta

from app.services.pulse_aggregation import (
    MIN_AGGREGATION_THRESHOLD,
    RECENT_WINDOW_HOURS,
    VISIBILITY_DELAY_MINUTES,
    bucket_count,
    build_category_breakdown,
    build_country_list,
    build_map_points,
    build_snapshot,
    visibility_cutoff,
)


# ── bucket_count ───────────────────────────────────────────────────────────────

class TestBucketCount:
    def test_below_threshold_is_zero(self):
        assert bucket_count(0) == "0"
        assert bucket_count(MIN_AGGREGATION_THRESHOLD - 1) == "0"

    def test_at_threshold_starts_first_bucket(self):
        result = bucket_count(MIN_AGGREGATION_THRESHOLD)
        assert result == f"{MIN_AGGREGATION_THRESHOLD}-{MIN_AGGREGATION_THRESHOLD * 2 - 1}"

    def test_same_bucket_for_different_counts_within_range(self):
        # Two different exact counts inside the same bucket must render
        # identically — this is the point: an exact crossing can't be read
        # back from the displayed value.
        low = bucket_count(MIN_AGGREGATION_THRESHOLD, threshold=MIN_AGGREGATION_THRESHOLD)
        high = bucket_count(MIN_AGGREGATION_THRESHOLD * 2 - 1, threshold=MIN_AGGREGATION_THRESHOLD)
        assert low == high

    def test_large_counts_use_wide_buckets(self):
        assert bucket_count(75) == "50-99"
        assert bucket_count(300) == "100-499"
        assert bucket_count(750) == "500-999"
        assert bucket_count(5000) == "1000+"

    def test_never_returns_exact_single_number_for_small_counts(self):
        # No bucket string for any count >= threshold should ever equal the
        # plain str(count) — that would defeat the purpose.
        for n in range(MIN_AGGREGATION_THRESHOLD, 60):
            result = bucket_count(n)
            assert result != str(n) or "-" in result or "+" in result


# ── visibility_cutoff ────────────────────────────────────────────────────────

class TestVisibilityCutoff:
    def test_cutoff_is_before_now_by_delay(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        cutoff = visibility_cutoff(now, delay_minutes=15)
        assert cutoff == now - timedelta(minutes=15)

    def test_default_delay_matches_module_constant(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        cutoff = visibility_cutoff(now)
        assert cutoff == now - timedelta(minutes=VISIBILITY_DELAY_MINUTES)

    def test_custom_delay_of_zero_returns_now(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        assert visibility_cutoff(now, delay_minutes=0) == now


# ── build_category_breakdown ──────────────────────────────────────────────────

class TestBuildCategoryBreakdown:
    def test_empty_input_returns_empty_list(self):
        assert build_category_breakdown([]) == []

    def test_single_problem_below_threshold_is_omitted_by_default(self):
        result = build_category_breakdown([["anxiety"]])
        assert result == []

    def test_single_problem_at_threshold_1(self):
        result = build_category_breakdown([["anxiety"]], threshold=1)
        assert result == [{
            "id": "anxiety",
            "label": "Anxiety & Overthinking",
            "count_range": bucket_count(1, threshold=1),
            "percentage": 100,
        }]

    def test_two_problems_per_checkin_both_counted_with_threshold_1(self):
        result = build_category_breakdown([["anxiety", "relationships"]], threshold=1)
        ids = {c["id"] for c in result}
        assert ids == {"anxiety", "relationships"}

    def test_percentages_sum_to_100_when_counts_divide_evenly(self):
        rows = [["anxiety"]] * 5 + [["mood"]] * 5
        result = build_category_breakdown(rows)
        assert sum(c["percentage"] for c in result) == 100

    def test_sorted_descending_by_count(self):
        rows = [["anxiety"]] * 3 + [["mood"]] * 7
        result = build_category_breakdown(rows, threshold=1)
        assert result[0]["id"] == "mood"
        assert result[1]["id"] == "anxiety"

    def test_category_below_threshold_omitted_even_when_others_pass(self):
        rows = [["anxiety"]] * 2 + [["mood"]] * 5
        result = build_category_breakdown(rows)
        ids = {c["id"] for c in result}
        assert ids == {"mood"}

    def test_category_at_threshold_included(self):
        rows = [["anxiety"]] * MIN_AGGREGATION_THRESHOLD
        result = build_category_breakdown(rows)
        assert len(result) == 1
        assert result[0]["count_range"] != "0"

    def test_result_never_exposes_raw_integer_count(self):
        rows = [["anxiety"]] * MIN_AGGREGATION_THRESHOLD
        result = build_category_breakdown(rows)
        assert "count" not in result[0]
        assert set(result[0].keys()) == {"id", "label", "count_range", "percentage"}

    def test_unknown_problem_id_ignored(self):
        result = build_category_breakdown([["not_a_real_problem"]], threshold=1)
        assert result == []

    def test_none_and_empty_lists_ignored(self):
        rows = [None, [], ["grief"]] + [["grief"]] * (MIN_AGGREGATION_THRESHOLD - 1)
        result = build_category_breakdown(rows)
        assert len(result) == 1
        assert result[0]["id"] == "grief"


# ── build_country_list ────────────────────────────────────────────────────────

class TestBuildCountryList:
    def test_empty_input_returns_empty_list(self):
        assert build_country_list([]) == []

    def test_country_below_threshold_is_omitted(self):
        result = build_country_list([("IN", "India", MIN_AGGREGATION_THRESHOLD - 1)])
        assert result == []

    def test_country_at_threshold_is_included(self):
        result = build_country_list([("IN", "India", MIN_AGGREGATION_THRESHOLD)])
        assert len(result) == 1
        assert result[0]["code"] == "IN"
        assert result[0]["name"] == "India"
        assert result[0]["count_range"] != "0"

    def test_result_never_exposes_raw_integer_count(self):
        result = build_country_list([("US", "United States", 42)])
        assert "count" not in result[0]
        assert set(result[0].keys()) == {"code", "name", "count_range"}

    def test_mixed_countries_only_above_threshold_survive(self):
        result = build_country_list([
            ("IN", "India", 20),
            ("XX", "Tiny", 1),
        ])
        codes = {c["code"] for c in result}
        assert codes == {"IN"}

    def test_null_code_excluded_even_if_count_high(self):
        result = build_country_list([(None, None, 999)])
        assert result == []

    def test_custom_threshold_respected(self):
        result = build_country_list([("IN", "India", 2)], threshold=2)
        assert len(result) == 1

    def test_two_different_exact_counts_in_same_bucket_render_identically(self):
        result_a = build_country_list([("IN", "India", MIN_AGGREGATION_THRESHOLD)])
        result_b = build_country_list([("IN", "India", MIN_AGGREGATION_THRESHOLD * 2 - 1)])
        assert result_a[0]["count_range"] == result_b[0]["count_range"]


# ── build_map_points ──────────────────────────────────────────────────────────

class TestBuildMapPoints:
    def test_empty_input_returns_empty_list(self):
        assert build_map_points([]) == []

    def test_country_below_threshold_omitted(self):
        rows = [("IN", ["anxiety"])] * (MIN_AGGREGATION_THRESHOLD - 1)
        assert build_map_points(rows) == []

    def test_country_at_threshold_included_when_single_category_dominates(self):
        # All 5 rows are the same category, so that category also clears
        # the per-category-within-country threshold.
        rows = [("IN", ["anxiety"])] * MIN_AGGREGATION_THRESHOLD
        result = build_map_points(rows)
        assert len(result) == 1
        assert result[0]["country_code"] == "IN"

    def test_country_clears_threshold_but_no_category_within_it_does(self):
        # 5 total check-ins for IN, but split across 5 different categories
        # (1 each) — country total clears MIN_AGGREGATION_THRESHOLD, but no
        # single category within IN does, so the point must be suppressed
        # entirely rather than showing a misleading/thin breakdown.
        rows = [
            ("IN", ["anxiety"]), ("IN", ["mood"]), ("IN", ["grief"]),
            ("IN", ["career"]), ("IN", ["sleep"]),
        ]
        result = build_map_points(rows)
        assert result == []

    def test_breakdown_omits_categories_below_threshold_even_within_a_visible_country(self):
        # IN has 9 total check-ins: 5 anxiety (clears threshold) + 4 mood
        # (does not clear threshold on its own). Country is visible, but
        # "mood" must not appear in its breakdown.
        rows = [("IN", ["anxiety"])] * 5 + [("IN", ["mood"])] * 4
        result = build_map_points(rows)
        assert len(result) == 1
        assert set(result[0]["breakdown"].keys()) == {"anxiety"}

    def test_breakdown_percentages_computed_per_country(self):
        rows = [("IN", ["anxiety"])] * 5 + [("IN", ["mood"])] * 5
        result = build_map_points(rows)
        breakdown = result[0]["breakdown"]
        assert breakdown["anxiety"] == 50
        assert breakdown["mood"] == 50

    def test_null_country_code_skipped(self):
        rows = [(None, ["anxiety"])] * 10
        assert build_map_points(rows) == []

    def test_breakdown_capped_at_top_5_categories(self):
        problems = ["anxiety", "relationships", "mood", "loneliness", "burnout", "family"]
        rows = [("IN", [p]) for p in problems for _ in range(MIN_AGGREGATION_THRESHOLD)]
        result = build_map_points(rows)
        assert len(result[0]["breakdown"]) <= 5

    def test_no_raw_individual_rows_leak_only_aggregates(self):
        rows = [("IN", ["anxiety"])] * MIN_AGGREGATION_THRESHOLD
        result = build_map_points(rows)
        assert set(result[0].keys()) == {"country_code", "count_range", "breakdown"}
        assert "count" not in result[0]


# ── build_snapshot ────────────────────────────────────────────────────────────

class TestBuildSnapshot:
    def test_zero_data_produces_honest_empty_snapshot(self):
        snapshot = build_snapshot(total=0, problem_rows=[], country_counts=[], checkin_rows=[])
        assert snapshot["total"] == 0
        assert snapshot["categories"] == []
        assert snapshot["countries"] == []
        assert snapshot["map"] == []

    def test_min_threshold_is_exposed_in_response(self):
        snapshot = build_snapshot(total=0, problem_rows=[], country_counts=[], checkin_rows=[])
        assert snapshot["min_threshold"] == MIN_AGGREGATION_THRESHOLD

    def test_visibility_delay_is_exposed_in_response(self):
        snapshot = build_snapshot(total=0, problem_rows=[], country_counts=[], checkin_rows=[])
        assert snapshot["visibility_delay_minutes"] == VISIBILITY_DELAY_MINUTES

    def test_snapshot_never_includes_raw_checkin_fields(self):
        snapshot = build_snapshot(
            total=1,
            problem_rows=[["anxiety"]],
            country_counts=[("IN", "India", MIN_AGGREGATION_THRESHOLD)],
            checkin_rows=[("IN", ["anxiety"])] * MIN_AGGREGATION_THRESHOLD,
        )
        serialized_keys = set(snapshot.keys())
        assert serialized_keys == {
            "total", "recent_checkins", "recent_window_hours",
            "categories", "countries", "map",
            "min_threshold", "visibility_delay_minutes",
        }
        for country in snapshot["countries"]:
            assert set(country.keys()) == {"code", "name", "count_range"}

    def test_recent_checkins_defaults_to_zero(self):
        snapshot = build_snapshot(total=0, problem_rows=[], country_counts=[], checkin_rows=[])
        assert snapshot["recent_checkins"] == 0

    def test_recent_checkins_passes_through_undelayed_and_unthresholded(self):
        # recent_checkins reflects the caller's own count directly — unlike
        # categories/countries/map, it is not derived from problem_rows/
        # country_counts/checkin_rows and has no threshold applied.
        snapshot = build_snapshot(
            total=1, problem_rows=[], country_counts=[], checkin_rows=[],
            recent_checkins=1,
        )
        assert snapshot["recent_checkins"] == 1

    def test_recent_window_hours_is_exposed_in_response(self):
        snapshot = build_snapshot(total=0, problem_rows=[], country_counts=[], checkin_rows=[])
        assert snapshot["recent_window_hours"] == RECENT_WINDOW_HOURS

    def test_low_volume_snapshot_hides_categories_and_countries_but_shows_total(self):
        snapshot = build_snapshot(
            total=1,
            problem_rows=[["anxiety", "relationships"]],
            country_counts=[("IN", "India", 1)],
            checkin_rows=[("IN", ["anxiety", "relationships"])],
        )
        assert snapshot["total"] == 1
        assert snapshot["categories"] == []
        assert snapshot["countries"] == []
        assert snapshot["map"] == []

    def test_before_after_single_checkin_diff_reveals_nothing_once_caller_filters_by_visibility(self):
        # This models what app/routes/pulse.py does: it only ever passes
        # rows already older than visibility_cutoff() into build_snapshot.
        # A fresh check-in (simulated here by simply not including it in
        # the "after" call's rows, exactly as the route's SQL filter would
        # exclude it) produces an identical categories/countries/map
        # response before and after, because build_snapshot itself never
        # sees the new row until the caller decides it's old enough.
        before = build_snapshot(
            total=5,
            problem_rows=[["anxiety"]] * 5,
            country_counts=[("IN", "India", 5)],
            checkin_rows=[("IN", ["anxiety"])] * 5,
        )
        # "after": total bumps immediately (route always recomputes this
        # from all rows), but the fresh row is NOT in problem_rows/
        # country_counts/checkin_rows because it hasn't cleared the
        # visibility delay yet.
        after = build_snapshot(
            total=6,
            problem_rows=[["anxiety"]] * 5,
            country_counts=[("IN", "India", 5)],
            checkin_rows=[("IN", ["anxiety"])] * 5,
        )
        assert after["total"] == before["total"] + 1
        assert after["categories"] == before["categories"]
        assert after["countries"] == before["countries"]
        assert after["map"] == before["map"]
