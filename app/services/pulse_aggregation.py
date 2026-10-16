"""
Global Pulse Aggregation Service

Pure functions that turn raw (problems, country_code, created_at) check-in
rows into the public, privacy-safe Global Pulse snapshot. No DB access here
— routes fetch rows and pass them in, which keeps this logic unit-testable
without a database connection.

Privacy model (see docstring on each function for detail):
  1. Minimum group size (MIN_AGGREGATION_THRESHOLD) — a country or category
     is never shown with fewer than this many check-ins behind it, and this
     applies independently to *every* count in the response: totals per
     category, per country, and per category-within-country.
  2. Visibility delay (VISIBILITY_DELAY) — a check-in only counts toward
     what's displayed once it is older than this delay. This is the load-
     bearing mitigation for before/after polling attacks (see
     build_snapshot's docstring): an attacker's own fresh submission cannot
     move any number in the response until it has aged past the delay, so
     "submit one check-in, diff the aggregate immediately" reveals nothing.
  3. Count bucketing (bucket_count) — once a group is large enough to show,
     its displayed count is a coarse range (e.g. "5-9") rather than an exact
     integer, so crossing a boundary can't be read back as "exactly N now."
"""
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# A country/category is never shown with fewer than this many check-ins
# behind it. Configurable via PULSE_MIN_AGGREGATION_THRESHOLD; defaults to 5
# (k-anonymity-style floor — small enough to reach quickly in early growth,
# large enough that a single-digit count can't be read back as "probably
# one specific person").
MIN_AGGREGATION_THRESHOLD = int(os.getenv("PULSE_MIN_AGGREGATION_THRESHOLD", "5"))

# A check-in only contributes to the displayed snapshot once it is at least
# this old. Configurable via PULSE_VISIBILITY_DELAY_MINUTES; defaults to 15.
# This decouples "when did the count change" from "when did a specific
# person submit," which is what makes the threshold in (1) actually hold up
# against an attacker polling immediately before/after a known event —
# without this, the exact request that pushes a group past the threshold
# is trivially identifiable by its timing alone.
VISIBILITY_DELAY_MINUTES = int(os.getenv("PULSE_VISIBILITY_DELAY_MINUTES", "15"))

# Window for the always-visible "recent activity" count — a single number
# with no category/geography attached, so it carries essentially none of
# the fingerprinting risk that motivates thresholding/delaying `categories`/
# `countries`/`map`: a bare count of recent submissions doesn't tell an
# observer WHAT anyone selected or WHERE they are, only that some number of
# people did something recently. Not threshold-gated, not delay-gated,
# same treatment as `total`. Configurable via PULSE_RECENT_WINDOW_HOURS.
RECENT_WINDOW_HOURS = int(os.getenv("PULSE_RECENT_WINDOW_HOURS", "1"))

PROBLEM_IDS = {
    "anxiety", "relationships", "mood", "loneliness", "burnout",
    "family", "selfworth", "identity", "grief", "career", "sleep", "other",
}

PROBLEM_LABELS = {
    "anxiety": "Anxiety & Overthinking",
    "relationships": "Relationship Problems",
    "mood": "Low Mood",
    "loneliness": "Loneliness & Disconnection",
    "burnout": "Burnout & Stress",
    "family": "Family Problems",
    "selfworth": "Self-Worth & Confidence",
    "identity": "Identity & Acceptance",
    "grief": "Grief & Loss",
    "career": "Career & Life Pressure",
    "sleep": "Sleep & Routine",
    "other": "Something Else",
}


def visibility_cutoff(now: datetime, delay_minutes: int = VISIBILITY_DELAY_MINUTES) -> datetime:
    """Check-ins created after this instant are not yet eligible to be
    reflected in any displayed aggregate (see module docstring, point 2)."""
    return now - timedelta(minutes=delay_minutes)


def bucket_count(count: int, threshold: int = MIN_AGGREGATION_THRESHOLD) -> str:
    """Coarse, non-exact display string for a count that has already
    cleared the visibility threshold. Widening bucket sizes as counts grow
    means an exact crossing is never directly observable from the response,
    and a "before" bucket vs "after" bucket comparison narrows the true
    count to a range rather than a single integer.

    threshold=5 examples: 5-9 -> "5-9", 23 -> "20-49", 1500 -> "1000+".
    """
    if count < threshold:
        return "0"
    if count < threshold * 2:
        return f"{threshold}-{threshold * 2 - 1}"
    if count < 50:
        return "10-49" if threshold <= 10 else f"{threshold * 2}-49"
    if count < 100:
        return "50-99"
    if count < 500:
        return "100-499"
    if count < 1000:
        return "500-999"
    return "1000+"


def build_category_breakdown(
    problem_rows: List[List[str]],
    threshold: int = MIN_AGGREGATION_THRESHOLD,
) -> List[Dict]:
    """problem_rows: list of each check-in's `problems` list (1-2 ids each),
    already filtered by the caller to check-ins older than the visibility
    cutoff.

    Categories with fewer than `threshold` tags are omitted entirely — at
    very low volume, a 100%/50% breakdown over 1-2 check-ins would reveal
    exactly which categories a specific early submitter chose. Displayed
    counts are bucketed (see bucket_count) rather than exact.
    """
    counts: Dict[str, int] = defaultdict(int)
    for problems in problem_rows:
        for p in (problems or []):
            if p in PROBLEM_IDS:
                counts[p] += 1

    total = sum(counts.values())
    return [
        {
            "id": pid,
            "label": PROBLEM_LABELS[pid],
            "count_range": bucket_count(count, threshold),
            "percentage": round((count / total) * 100) if total else 0,
        }
        for pid, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        if count >= threshold
    ]


def build_country_list(
    country_counts: List[Tuple[Optional[str], Optional[str], int]],
    threshold: int = MIN_AGGREGATION_THRESHOLD,
) -> List[Dict]:
    """country_counts: list of (code, name, count) tuples, one per country,
    already filtered by the caller to check-ins older than the visibility
    cutoff."""
    return [
        {"code": code, "name": name, "count_range": bucket_count(count, threshold)}
        for code, name, count in country_counts
        if code and count >= threshold
    ]


def build_map_points(
    checkin_rows: List[Tuple[Optional[str], List[str]]],
    threshold: int = MIN_AGGREGATION_THRESHOLD,
) -> List[Dict]:
    """checkin_rows: list of (country_code, problems) per check-in, already
    filtered by the caller to check-ins older than the visibility cutoff.

    Both the country total AND each category-within-country are
    independently subject to `threshold` — a country with 5 check-ins that
    are 4-anxiety + 1-other must not show a 100%/anxiety breakdown, since
    that would single out the 5th (differently-categorized) submitter just
    as precisely as omitting the country entirely would have failed to
    protect them.
    """
    country_category_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    country_totals: Dict[str, int] = defaultdict(int)

    for code, problems in checkin_rows:
        if not code:
            continue
        country_totals[code] += 1
        for p in (problems or []):
            if p in PROBLEM_IDS:
                country_category_counts[code][p] += 1

    points = []
    for code, cat_counts in country_category_counts.items():
        if country_totals[code] < threshold:
            continue
        cat_total = sum(cat_counts.values()) or 1
        breakdown = {
            pid: round((c / cat_total) * 100)
            for pid, c in sorted(cat_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
            if c >= threshold  # per-category-within-country floor, not just per-country
        }
        if not breakdown:
            # Country cleared the threshold but no single category within
            # it did — show the point with no breakdown rather than a
            # misleadingly precise (or single-category) one.
            continue
        points.append({
            "country_code": code,
            "count_range": bucket_count(country_totals[code], threshold),
            "breakdown": breakdown,
        })
    return points


def build_snapshot(
    total: int,
    problem_rows: List[List[str]],
    country_counts: List[Tuple[Optional[str], Optional[str], int]],
    checkin_rows: List[Tuple[Optional[str], List[str]]],
    threshold: int = MIN_AGGREGATION_THRESHOLD,
    recent_checkins: int = 0,
) -> Dict:
    """Build the public snapshot.

    IMPORTANT: `problem_rows`, `country_counts`, and `checkin_rows` must
    already be restricted by the caller (see app/routes/pulse.py) to
    check-ins with created_at older than visibility_cutoff(). `total` and
    `recent_checkins` are the exceptions — both reflect check-ins including
    ones still inside the visibility delay, since both are single coarse
    numbers with no category/geography attached and the product wants them
    to move immediately. `recent_checkins` is the caller-supplied count of
    check-ins within RECENT_WINDOW_HOURS (see that constant's docstring for
    why this is safe to leave unthresholded/undelayed).

    Why the before/after polling attack no longer works:
      An attacker submits one check-in and immediately re-queries this
      endpoint. That check-in's created_at is "now," which is always more
      recent than visibility_cutoff() — so it is excluded from every
      per-category and per-country count in `categories`, `countries`, and
      `map` for the next VISIBILITY_DELAY_MINUTES. The response the
      attacker sees immediately after their submission is therefore
      byte-for-byte identical (for those three fields) to the response
      before it. By the time the check-in *does* become eligible (after the
      delay), it has been mixed in among however many other check-ins
      arrived during that same window — the attacker can no longer
      distinguish "this exact submission" from "any other submission that
      also aged in around the same time," and even then only ever observes
      a bucketed range, not an exact count.
    """
    return {
        "total": total,
        "recent_checkins": recent_checkins,
        "recent_window_hours": RECENT_WINDOW_HOURS,
        "categories": build_category_breakdown(problem_rows, threshold),
        "countries": build_country_list(country_counts, threshold),
        "map": build_map_points(checkin_rows, threshold),
        "min_threshold": threshold,
        "visibility_delay_minutes": VISIBILITY_DELAY_MINUTES,
    }
