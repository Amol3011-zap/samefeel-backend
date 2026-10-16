from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass
from app.models import ActivityTypeEnum, JourneyStageEnum


STAGE_ORDER = [
    JourneyStageEnum.BEGINNING,
    JourneyStageEnum.HEALING,
    JourneyStageEnum.GROWTH,
    JourneyStageEnum.TRANSFORMATION,
    JourneyStageEnum.INNER_HARMONY,
]

STAGE_THRESHOLDS = {
    JourneyStageEnum.BEGINNING: 15,
    JourneyStageEnum.HEALING: 40,
    JourneyStageEnum.GROWTH: 70,
    JourneyStageEnum.TRANSFORMATION: 85,
    JourneyStageEnum.INNER_HARMONY: 100,
}

ACTIVITY_WEIGHTS = {
    ActivityTypeEnum.MEDITATION: 2.0,
    ActivityTypeEnum.CHAT_SESSION: 1.5,
    ActivityTypeEnum.HEALER_BOOKING: 3.0,
    ActivityTypeEnum.JOURNAL: 1.0,
    ActivityTypeEnum.CHECK_IN: 0.5,
    ActivityTypeEnum.REFLECTION: 1.2,
}

# Which stage each activity type belongs to
ACTIVITY_STAGE_MAP = {
    ActivityTypeEnum.MEDITATION: JourneyStageEnum.HEALING,
    ActivityTypeEnum.JOURNAL: JourneyStageEnum.HEALING,
    ActivityTypeEnum.CHAT_SESSION: JourneyStageEnum.GROWTH,
    ActivityTypeEnum.HEALER_BOOKING: JourneyStageEnum.TRANSFORMATION,
    ActivityTypeEnum.CHECK_IN: JourneyStageEnum.BEGINNING,
    ActivityTypeEnum.REFLECTION: JourneyStageEnum.GROWTH,
}


@dataclass
class StageMetrics:
    completion_percentage: float
    activities_completed: int
    days_in_stage: int
    wellness_contribution: float


def _get_activity_stage(activity_type: ActivityTypeEnum) -> JourneyStageEnum:
    return ACTIVITY_STAGE_MAP.get(activity_type, JourneyStageEnum.BEGINNING)


def calculate_stage_progress(activities, stage: JourneyStageEnum) -> float:
    stage_acts = [a for a in activities if _get_activity_stage(a.activity_type) == stage]
    if not stage_acts:
        return 0.0
    total_weight = sum(
        ACTIVITY_WEIGHTS[a.activity_type] * (a.intensity / 10.0)
        for a in stage_acts
    )
    return min((total_weight / 20.0) * 100, 100.0)


def calculate_overall_progress(activities) -> float:
    if not activities:
        return 0.0
    return sum(calculate_stage_progress(activities, s) for s in STAGE_ORDER) / len(STAGE_ORDER)


def get_current_stage(activities) -> JourneyStageEnum:
    overall = calculate_overall_progress(activities)
    for stage in reversed(STAGE_ORDER):
        if overall >= STAGE_THRESHOLDS[stage]:
            return stage
    return JourneyStageEnum.BEGINNING


def calculate_wellness_score(activities) -> float:
    if not activities:
        return 0.0
    last_week = datetime.utcnow() - timedelta(days=7)
    week_acts = [a for a in activities if a.logged_at >= last_week]
    if not week_acts:
        return 0.0
    count_score = min(len(week_acts) / 7, 1.0)
    avg_intensity = sum(a.intensity for a in week_acts) / len(week_acts) / 10.0
    variety = min(len({a.activity_type for a in week_acts}) / 4, 1.0)
    return round((count_score * 0.4 + avg_intensity * 0.4 + variety * 0.2) * 10, 1)


def calculate_weekly_growth(activities) -> float:
    now = datetime.utcnow()
    this_week = [a for a in activities if now - timedelta(days=7) <= a.logged_at <= now]
    last_week = [a for a in activities if now - timedelta(days=14) <= a.logged_at < now - timedelta(days=7)]
    if not last_week:
        return 0.0 if not this_week else 100.0
    return round(max(((len(this_week) - len(last_week)) / len(last_week)) * 100, -100.0), 1)


def get_stage_metrics(activities) -> Dict[str, StageMetrics]:
    metrics = {}
    for stage in STAGE_ORDER:
        stage_acts = [a for a in activities if _get_activity_stage(a.activity_type) == stage]
        progress = calculate_stage_progress(activities, stage)
        metrics[stage.value] = StageMetrics(
            completion_percentage=round(progress, 1),
            activities_completed=len(stage_acts),
            days_in_stage=0,  # would need stage_start_dates to compute; omitted for simplicity
            wellness_contribution=round(progress / 10, 1),
        )
    return metrics
