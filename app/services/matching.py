from sqlalchemy.orm import Session
from app.models import User, Match, ProblemEnum, MatchStatus
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timedelta
from typing import List, Tuple


class MatchingService:

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        if not all([lat1, lon1, lat2, lon2]):
            return float('inf')

        R = 6371
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    @staticmethod
    def calculate_match_score(user_1: User, user_2: User, distance_km: float) -> Tuple[int, str]:
        score = 0
        reason_parts = []

        if user_1.primary_problem == user_2.primary_problem:
            score += 100
            reason_parts.append("Same primary problem")

        user_1_all = [user_1.primary_problem] + (user_1.secondary_problems or [])
        user_2_all = [user_2.primary_problem] + (user_2.secondary_problems or [])

        overlap = set(user_1_all) & set(user_2_all)
        if len(overlap) > 1:
            score += 30
            reason_parts.append(f"{len(overlap)} shared issues")

        if distance_km <= 5:
            score += 30
            reason_parts.append(f"{distance_km:.1f}km away")
        elif distance_km <= 10:
            score += 20
            reason_parts.append(f"{distance_km:.1f}km away")
        elif distance_km <= 20:
            score += 10
            reason_parts.append(f"{distance_km:.1f}km away")
        elif distance_km <= (user_2.distance_preference or 10):
            score += 5

        if user_1.timezone == user_2.timezone:
            score += 15
            reason_parts.append("Same timezone")

        now = datetime.utcnow()
        if (user_1.last_active_at and (now - user_1.last_active_at).total_seconds() < 4 * 3600 and
                user_2.last_active_at and (now - user_2.last_active_at).total_seconds() < 4 * 3600):
            score += 10
            reason_parts.append("Both recently active")

        reason = " + ".join(reason_parts) if reason_parts else "Potential match"
        return min(score, 200), reason

    @staticmethod
    def find_matches(user: User, db: Session, limit: int = 3) -> List[dict]:
        potential_matches = db.query(User).filter(
            User.id != user.id,
            User.is_active == True,
            User.primary_problem == user.primary_problem
        ).all()

        if not potential_matches:
            potential_matches = db.query(User).filter(
                User.id != user.id,
                User.is_active == True,
            ).all()

        scored_matches = []

        for potential_match in potential_matches:
            if not potential_match.latitude or not potential_match.longitude:
                continue
            if not user.latitude or not user.longitude:
                continue

            distance_km = MatchingService.haversine_distance(
                user.latitude, user.longitude,
                potential_match.latitude, potential_match.longitude
            )

            if distance_km > (potential_match.distance_preference or 10):
                continue
            if distance_km > (user.distance_preference or 10):
                continue

            existing = db.query(Match).filter(
                ((Match.user_1_id == user.id) & (Match.user_2_id == potential_match.id)) |
                ((Match.user_1_id == potential_match.id) & (Match.user_2_id == user.id))
            ).first()

            if existing:
                continue

            score, reason = MatchingService.calculate_match_score(user, potential_match, distance_km)

            scored_matches.append({
                "user": potential_match,
                "distance_km": distance_km,
                "score": score,
                "reason": reason
            })

        scored_matches.sort(key=lambda x: x["score"], reverse=True)
        return scored_matches[:limit]

    @staticmethod
    def create_match(
        user_1_id: int,
        user_2_id: int,
        problem: ProblemEnum,
        distance_km: float,
        score: int,
        reason: str,
        db: Session
    ) -> Match:
        match = Match(
            user_1_id=user_1_id,
            user_2_id=user_2_id,
            problem_matched=problem,
            distance_km=distance_km,
            match_score=score,
            match_reason=reason,
            status=MatchStatus.PENDING
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        return match
