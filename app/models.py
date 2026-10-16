from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Enum, ForeignKey, JSON, Text, Index, text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


# ========== ENUMS ==========

class ProblemEnum(str, enum.Enum):
    ANXIETY = "anxiety"
    DEPRESSION = "depression"
    OCD_INTRUSIVE_THOUGHTS = "ocd_intrusive_thoughts"
    PTSD_TRAUMA = "ptsd_trauma"
    PHOBIAS = "phobias"
    PANIC_ATTACKS = "panic_attacks"
    SELF_HARM = "self_harm"
    RELATIONSHIP_BREAKUP = "relationship_breakup"
    DIVORCE = "divorce"
    MARRIAGE_PROBLEMS = "marriage_problems"
    FAMILY_RELATIONSHIPS = "family_relationships"
    TRUST_ISSUES = "trust_issues"
    UNREQUITED_LOVE = "unrequited_love"
    LONELINESS = "loneliness"
    LACK_OF_CONFIDENCE = "lack_of_confidence"
    BULLYING_HARASSMENT = "bullying_harassment"
    GRIEF_LOSS = "grief_loss"
    WORK_CAREER_STRESS = "work_career_stress"
    FINANCIAL_STRESS = "financial_stress"
    IDENTITY_SEXUAL_ORIENTATION = "identity_sexual_orientation"
    ADDICTION_SUBSTANCE_ABUSE = "addiction_substance_abuse"
    HEALTH_ANXIETY = "health_anxiety"
    SLEEP_PROBLEMS = "sleep_problems"
    EATING_DISORDERS = "eating_disorders"
    ANGER_MANAGEMENT = "anger_management"


class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    REJECTED = "rejected"


# ========== USER MODEL ==========

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    phone_verified = Column(Boolean, default=False)
    name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    bio = Column(String(500), nullable=True)
    role = Column(String, default="user")

    primary_problem = Column(Enum(ProblemEnum), nullable=False)
    secondary_problems = Column(JSON, default=list)
    problem_context = Column(String(500), nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    distance_preference = Column(Integer, default=10)
    hide_location = Column(Boolean, default=False)

    timezone = Column(String, default="Asia/Kolkata")

    is_active = Column(Boolean, default=True)
    interested_in_healer = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    matches = relationship("Match", foreign_keys="[Match.user_1_id]", back_populates="user_1")
    chats = relationship("Chat", back_populates="user")
    healer_sessions = relationship("HealerSession", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    meetups = relationship("MeetupAttendee", back_populates="user")
    journey = relationship("UserJourney", back_populates="user", uselist=False)


# ========== MATCH MODEL ==========

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    user_1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_matched = Column(Enum(ProblemEnum), nullable=False)
    distance_km = Column(Float)
    match_score = Column(Integer)
    match_reason = Column(String(500))
    status = Column(Enum(MatchStatus), default=MatchStatus.PENDING)

    matched_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    rating_from_1 = Column(Integer, nullable=True)
    rating_from_2 = Column(Integer, nullable=True)
    feedback_from_1 = Column(Text, nullable=True)
    feedback_from_2 = Column(Text, nullable=True)

    user_1 = relationship("User", foreign_keys=[user_1_id], back_populates="matches")
    chats = relationship("Chat", back_populates="match")


# ========== CHAT MODEL ==========

class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="chats")
    user = relationship("User", back_populates="chats")


# ========== HEALER MODEL ==========

class Healer(Base):
    __tablename__ = "healers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)

    specializations = Column(JSON, default=[])
    experience_years = Column(Integer, default=1)

    certification_url = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)

    hourly_rate = Column(Integer, default=500)
    availability = Column(JSON, default={})

    total_rating = Column(Float, default=0)
    review_count = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("HealerSession", back_populates="healer")


# ========== HEALER SESSION MODEL ==========

class HealerSession(Base):
    __tablename__ = "healer_sessions"

    id = Column(Integer, primary_key=True, index=True)
    healer_id = Column(Integer, ForeignKey("healers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_type = Column(Enum(ProblemEnum), nullable=False)

    scheduled_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    session_type = Column(String, default="video")

    status = Column(String, default="pending")

    amount = Column(Integer)
    platform_commission = Column(Integer)
    healer_earning = Column(Integer)
    payment_status = Column(String, default="pending")
    razorpay_payment_id = Column(String, nullable=True)

    user_notes = Column(Text, nullable=True)
    healer_notes = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    healer = relationship("Healer", back_populates="sessions")
    user = relationship("User", back_populates="healer_sessions")


# ========== MEETUP MODEL ==========

class Meetup(Base):
    __tablename__ = "meetups"

    id = Column(Integer, primary_key=True, index=True)
    problem_type = Column(Enum(ProblemEnum), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    location_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    city = Column(String, nullable=False)

    scheduled_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=90)

    max_attendees = Column(Integer, default=8)
    host_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    status = Column(String, default="upcoming")

    avg_rating = Column(Float, default=0)
    review_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    attendees = relationship("MeetupAttendee", back_populates="meetup")


# ========== MEETUP ATTENDEE MODEL ==========

class MeetupAttendee(Base):
    __tablename__ = "meetup_attendees"

    id = Column(Integer, primary_key=True, index=True)
    meetup_id = Column(Integer, ForeignKey("meetups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    status = Column(String, default="confirmed")
    joined_at = Column(DateTime, default=datetime.utcnow)

    rating = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)

    meetup = relationship("Meetup", back_populates="attendees")
    user = relationship("User", back_populates="meetups")


# ========== SUBSCRIPTION MODEL ==========

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    plan = Column(String, default="premium")
    amount = Column(Integer, default=299)

    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    status = Column(String, default="active")

    razorpay_subscription_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    payment_status = Column(String, default="pending")

    features = Column(JSON, default={
        "priority_matching": True,
        "unlimited_meetups": True,
        "healer_discount": 0.20,
        "expanded_search_radius": 50,
        "progress_tracking": True,
        "no_ads": True
    })

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")


# ========== SAFETY FLAG MODEL ==========

# ========== DAILY CHALLENGES MODELS ==========

class UserChallengeStreak(Base):
    __tablename__ = "user_challenge_streaks"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    total_points = Column(Integer, default=0)
    last_completion_date = Column(DateTime, nullable=True)

    completions = relationship("UserChallengeCompletion", back_populates="streak_record", cascade="all, delete-orphan", foreign_keys="UserChallengeCompletion.user_id", primaryjoin="UserChallengeStreak.user_id == UserChallengeCompletion.user_id")


class UserChallengeCompletion(Base):
    __tablename__ = "user_challenge_completions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(String, nullable=False)
    challenge_date = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow)
    actual_duration = Column(Integer, nullable=True)
    points_earned = Column(Integer, default=0)

    streak_record = relationship("UserChallengeStreak", foreign_keys=[user_id], primaryjoin="UserChallengeCompletion.user_id == UserChallengeStreak.user_id", back_populates="completions")

    __table_args__ = (
        Index("ix_challenge_completions_user_date", "user_id", "challenge_date"),
    )


# ========== SOUL JOURNEY ENUMS ==========

class JourneyStageEnum(str, enum.Enum):
    BEGINNING = "beginning"
    HEALING = "healing"
    GROWTH = "growth"
    TRANSFORMATION = "transformation"
    INNER_HARMONY = "inner_harmony"


class ActivityTypeEnum(str, enum.Enum):
    MEDITATION = "meditation"
    JOURNAL = "journal"
    CHAT_SESSION = "chat_session"
    HEALER_BOOKING = "healer_booking"
    CHECK_IN = "check_in"
    REFLECTION = "reflection"


# ========== USER JOURNEY MODEL ==========

class UserJourney(Base):
    __tablename__ = "user_journeys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    current_stage = Column(Enum(JourneyStageEnum), default=JourneyStageEnum.BEGINNING)
    joined_at = Column(DateTime, default=datetime.utcnow)
    total_activities = Column(Integer, default=0)

    user = relationship("User", back_populates="journey")
    activities = relationship("JourneyActivity", back_populates="journey", cascade="all, delete-orphan")


# ========== JOURNEY ACTIVITY MODEL ==========

class JourneyActivity(Base):
    __tablename__ = "journey_activities"

    id = Column(Integer, primary_key=True, index=True)
    journey_id = Column(Integer, ForeignKey("user_journeys.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(Enum(ActivityTypeEnum), nullable=False)
    duration_minutes = Column(Integer, default=0)
    intensity = Column(Integer, default=5)  # 1–10
    notes = Column(Text, default="")
    logged_at = Column(DateTime, default=datetime.utcnow)

    journey = relationship("UserJourney", back_populates="activities")

    __table_args__ = (
        Index("ix_journey_activities_user_date", "user_id", "logged_at"),
    )


# ========== SAFETY FLAG MODEL ==========

class SafetyFlag(Base):
    __tablename__ = "safety_flags"

    id = Column(Integer, primary_key=True, index=True)
    flagged_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    flag_type = Column(String)
    description = Column(Text)

    is_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ========== CRISIS RESOURCES MODEL ==========

class CrisisResource(Base):
    __tablename__ = "crisis_resources"

    id = Column(Integer, primary_key=True, index=True)
    country = Column(String)
    organization = Column(String)
    phone = Column(String)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    description = Column(Text)
    available_24_7 = Column(Boolean, default=True)


# ========== VISITOR ANALYTICS ==========

class VisitorAnalytics(Base):
    __tablename__ = "visitor_analytics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(128), unique=True, index=True, nullable=False)
    hostname = Column(String(255))            # window.location.hostname the session was recorded from
    is_internal = Column(Boolean, default=False, nullable=False)  # dev/team traffic, excluded from reporting
    device_type = Column(String(20))          # mobile / tablet / desktop
    browser = Column(String(50))
    os = Column(String(50))
    screen_resolution = Column(String(20))
    country = Column(String(80))
    city = Column(String(80))                 # approximate only
    referral_source = Column(String(500))
    landing_page = Column(String(500))
    pages_viewed = Column(JSON, default=list)
    session_duration_seconds = Column(Integer, default=0)
    click_events = Column(JSON, default=list)
    utm_source = Column(String(200))
    utm_medium = Column(String(200))
    utm_campaign = Column(String(200))
    utm_content = Column(String(200))
    utm_term = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_visitor_analytics_created", "created_at"),
        Index("ix_visitor_analytics_country", "country"),
        Index("ix_visitor_analytics_hostname", "hostname"),
    )


# ========== USER CONSENT ==========

class UserConsent(Base):
    __tablename__ = "user_consent"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(128), nullable=True)   # for pre-auth consent
    privacy_policy_accepted = Column(Boolean, default=False)
    terms_accepted = Column(Boolean, default=False)
    safety_policy_accepted = Column(Boolean, default=False)
    community_guidelines_accepted = Column(Boolean, default=False)
    analytics_consent = Column(Boolean, default=False)
    marketing_consent = Column(Boolean, default=False)
    policy_version = Column(String(20), default="1.0")
    accepted_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))           # IPv4 or IPv6
    user_agent = Column(String(500))


# ========== USER PROFILE (EXTENDED) ==========

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    profile_photo_url = Column(String(500), nullable=True)
    language = Column(String(10), default="en")

    # Onboarding data
    primary_challenges = Column(JSON, default=list)   # ["anxiety","grief",...]
    goals = Column(JSON, default=list)                # ["find_support","join_circles",...]

    # Activity counters (denormalized for perf)
    messages_sent = Column(Integer, default=0)
    circles_joined = Column(Integer, default=0)
    events_attended = Column(Integer, default=0)
    guides_viewed = Column(Integer, default=0)
    bookings_created = Column(Integer, default=0)
    sessions_attended = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ========== USER PREFERENCES ==========

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    notifications_email = Column(Boolean, default=True)
    notifications_push = Column(Boolean, default=True)
    notifications_sms = Column(Boolean, default=False)
    show_online_status = Column(Boolean, default=True)
    allow_anonymous_matching = Column(Boolean, default=True)
    data_sharing_analytics = Column(Boolean, default=True)
    data_sharing_research = Column(Boolean, default=False)

    preferred_guide_gender = Column(String(20), nullable=True)
    preferred_session_type = Column(String(20), default="video")
    theme = Column(String(20), default="light")

    updated_at = Column(DateTime, default=datetime.utcnow)


# ========== USER MOODS ==========

class UserMood(Base):
    __tablename__ = "user_moods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mood_score = Column(Integer, nullable=False)      # 1-10
    mood_label = Column(String(50))                   # anxious / calm / hopeful / etc.
    mood_tags = Column(JSON, default=list)            # ["stressed","tired",...]
    notes = Column(Text, nullable=True)               # encrypted client-side
    logged_at = Column(DateTime, default=datetime.utcnow)
    # Daily Soul Climate check-in: the user's own calendar date + IANA zone it
    # was computed in. source = "soul_climate" rows are limited to one per
    # user per local_date (partial unique index below).
    local_date = Column(Date, nullable=True)
    timezone = Column(String(64), nullable=True)
    source = Column(String(20), nullable=True)

    __table_args__ = (
        Index("ix_user_moods_user_date", "user_id", "logged_at"),
        Index(
            "ux_user_moods_daily_checkin", "user_id", "local_date",
            unique=True,
            postgresql_where=text("source = 'soul_climate'"),
            sqlite_where=text("source = 'soul_climate'"),
        ),
    )


# ========== JOURNAL ENTRIES (ENCRYPTED) ==========

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title_encrypted = Column(Text, nullable=True)    # AES-256 encrypted
    content_encrypted = Column(Text, nullable=False)  # AES-256 encrypted
    mood_score = Column(Integer, nullable=True)       # 1-10, stored plaintext for analytics
    tags = Column(JSON, default=list)                 # topic tags, non-sensitive
    is_private = Column(Boolean, default=True)
    word_count_approx = Column(Integer, default=0)    # for analytics, no content
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_journal_entries_user_date", "user_id", "created_at"),
    )


# ========== GUIDE CERTIFICATIONS ==========

class GuideCertification(Base):
    __tablename__ = "guide_certifications"

    id = Column(Integer, primary_key=True, index=True)
    healer_id = Column(Integer, ForeignKey("healers.id"), nullable=False, index=True)
    category = Column(String(100))      # Mental Health / Meditation / Yoga / etc.
    certification_name = Column(String(200))
    issuing_authority = Column(String(200))
    year_obtained = Column(Integer, nullable=True)
    file_url = Column(String(500), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)


# ========== GUIDE AGREEMENTS ==========

class GuideAgreement(Base):
    __tablename__ = "guide_agreements"

    id = Column(Integer, primary_key=True, index=True)
    healer_id = Column(Integer, ForeignKey("healers.id"), unique=True, nullable=False)
    guide_agreement_version = Column(String(20), default="1.0")

    role_understanding_accepted = Column(Boolean, default=False)
    independent_contractor_accepted = Column(Boolean, default=False)
    confidentiality_accepted = Column(Boolean, default=False)
    safety_training_completed = Column(Boolean, default=False)
    professional_conduct_accepted = Column(Boolean, default=False)
    employment_compliance_accepted = Column(Boolean, default=False)

    qualification_status = Column(String(50), default="pending_review")
    verification_status = Column(String(50), default="unverified")

    accepted_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)


# ========== CIRCLE MEMBERSHIPS ==========

class CircleMembership(Base):
    __tablename__ = "circle_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    meetup_id = Column(Integer, ForeignKey("meetups.id"), nullable=False, index=True)
    role = Column(String(20), default="member")      # host / member / moderator
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index("ix_circle_memberships_user_meetup", "user_id", "meetup_id"),
    )


# ========== CIRCLE ACTIVITY ==========

class CircleActivity(Base):
    __tablename__ = "circle_activity"

    id = Column(Integer, primary_key=True, index=True)
    meetup_id = Column(Integer, ForeignKey("meetups.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    activity_type = Column(String(50))   # message / join / leave / rate / report
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_circle_activity_meetup_date", "meetup_id", "created_at"),
    )


# ========== SECURITY LOGS ==========

class SecurityLog(Base):
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    # login_success / login_failed / password_change / device_change
    # account_recovery / suspicious_activity / data_export / account_delete
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_fingerprint = Column(String(200), nullable=True)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_security_logs_user_date", "user_id", "created_at"),
        Index("ix_security_logs_event", "event_type", "created_at"),
    )


# ========== REPORTS ==========

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reported_guide_id = Column(Integer, ForeignKey("healers.id"), nullable=True)
    report_type = Column(String(20), nullable=False)   # user / guide / circle / message
    reason = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    screenshot_url = Column(String(500), nullable=True)
    is_anonymous = Column(Boolean, default=False)
    status = Column(String(20), default="pending")     # pending / reviewing / resolved / dismissed
    moderator_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_reports_status_date", "status", "created_at"),
    )


# ========== CRISIS ESCALATIONS ==========

class CrisisEscalation(Base):
    __tablename__ = "crisis_escalations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trigger_phrase = Column(String(200))
    context = Column(String(50))    # ai_chat / peer_chat / journal / mood
    status = Column(String(30), default="triggered")   # triggered / acknowledged / resolved
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_crisis_escalations_user_date", "user_id", "created_at"),
    )


# ========== EARLY ACCESS SUBMISSIONS ==========

class EarlyAccessSubmission(Base):
    __tablename__ = "early_access_submissions"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(200), nullable=True)
    email         = Column(String(320), nullable=False, unique=True, index=True)
    struggle      = Column(String(100), nullable=True)   # renamed from challenge
    challenge     = Column(String(100), nullable=True)   # kept for backward compat
    source          = Column(String(100), default="Landing Page")
    referral_code   = Column(String(100), nullable=True)   # for future referral tracking
    referral_source = Column(String(50), nullable=True)    # "How did you hear about us?" dropdown
    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_early_access_created", "created_at"),
    )


# ========== GLOBAL PULSE ==========
# Unauthenticated check-ins for the "How Do You Feel?" / Global Pulse
# feature. No user_id, no name, no email — but as of this table version,
# ip_address and city ARE retained for internal records (product decision;
# see the "Anonymous" label change on the check-in screen, which was
# updated to stop overclaiming). The public API in app/routes/pulse.py
# never returns ip_address or city, and only ever returns aggregated,
# threshold-gated counts — this column existing does not change what the
# public endpoint exposes, only what's kept internally.

class PulseCheckIn(Base):
    __tablename__ = "pulse_checkins"

    id           = Column(Integer, primary_key=True, index=True)
    problems     = Column(JSON, nullable=False)   # list[str], 1-2 problem ids
    country_code = Column(String(2), nullable=True)   # ISO 3166-1 alpha-2, e.g. "IN"
    country_name = Column(String(80), nullable=True)
    city         = Column(String(120), nullable=True)   # IP-derived, best-effort
    ip_address   = Column(String(45), nullable=True)     # internal record only; never returned by any API response. IPv6-safe length.
    created_at   = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_pulse_checkins_created", "created_at"),
        Index("ix_pulse_checkins_country", "country_code"),
    )


# Separate, structurally disconnected from PulseCheckIn on purpose: this
# table only ever answers "has this IP checked in recently" for cooldown
# enforcement. It stores a salted one-way hash of the IP, never the raw IP,
# and has no foreign key or join path to PulseCheckIn — so even direct
# access to this table cannot reveal what a given IP selected or reported.
class PulseCheckInCooldown(Base):
    __tablename__ = "pulse_checkin_cooldowns"

    id           = Column(Integer, primary_key=True, index=True)
    ip_hash      = Column(String(64), unique=True, nullable=False, index=True)  # sha256 hex digest
    last_checkin_at = Column(DateTime, default=datetime.utcnow, nullable=False)
