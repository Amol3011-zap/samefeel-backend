"""
Lightweight helper for writing to the security_logs table.

Used to record suspicious/abusive activity on the public, unauthenticated
endpoints (rate-limit trips, forged Origin headers, failed admin-key
attempts) so there's a queryable trail of "someone is trying something"
without needing a full auth/user system behind it.

Never raises - a failure to write a security log must not break the
request it's attached to. Any DB error here is swallowed and logged
locally instead.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import SecurityLog

logger = logging.getLogger("security")


def log_event(
    db: Session,
    event_type: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> None:
    """Record a security event. Best-effort: never raises.

    event_type examples used in this codebase:
      rate_limit_exceeded     - a client tripped an endpoint's rate limiter
      forged_origin_blocked   - a request's Origin header wasn't on the allowlist
      admin_auth_failed       - a request to an admin-only endpoint had a
                                 missing/wrong X-Admin-Key
    """
    try:
        entry = SecurityLog(
            event_type=event_type,
            ip_address=(ip_address or None),
            user_agent=(user_agent or "")[:500] or None,
            extra_data=extra_data or {},
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error("Failed to write security log (type=%s, ip=%s): %s", event_type, ip_address, e)
    else:
        logger.warning("security_event type=%s ip=%s extra=%s", event_type, ip_address, extra_data)
