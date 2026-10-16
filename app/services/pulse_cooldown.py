"""
Global Pulse per-IP cooldown.

Enforces "one check-in per IP per COOLDOWN_HOURS" on top of the existing
short-window burst rate limiter in app/routes/pulse.py. The two serve
different purposes: the burst limiter stops rapid-fire scripted abuse
within a 10-minute window; this stops the same person from submitting
repeatedly over hours/days once that window resets.

Trade-off, stated plainly: this is IP-based, not identity-based. It will
not stop someone determined to bypass it (new IP via mobile data, VPN,
different device), and it can occasionally block a different real person
sharing the same IP (office/college/public Wi-Fi, carrier-grade NAT) from
checking in for the cooldown period. That's an accepted limitation of any
IP-based approach without accounts — see PulseCheckInCooldown's docstring
in app/models.py for why we don't go further than this.
"""
import hashlib
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import PulseCheckInCooldown

COOLDOWN_HOURS = int(os.getenv("PULSE_COOLDOWN_HOURS", "3"))

# Only used to make the stored hash non-trivially-reversible; this is not a
# security secret in the auth sense (nothing sensitive is protected by it
# being unknown) — it just means the ip_hash column isn't a raw, greppable
# list of IPs. Set PULSE_IP_HASH_SALT in production for a project-specific
# salt; the default is fine for local dev.
_SALT = os.getenv("PULSE_IP_HASH_SALT", "soulconnect-pulse-cooldown-dev-salt")


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{_SALT}:{ip}".encode("utf-8")).hexdigest()


def is_on_cooldown(db: Session, ip: str) -> bool:
    ip_hash = hash_ip(ip)
    row = db.query(PulseCheckInCooldown).filter(PulseCheckInCooldown.ip_hash == ip_hash).first()
    if not row:
        return False
    cutoff = datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)
    return row.last_checkin_at > cutoff


def record_checkin(db: Session, ip: str) -> None:
    ip_hash = hash_ip(ip)
    row = db.query(PulseCheckInCooldown).filter(PulseCheckInCooldown.ip_hash == ip_hash).first()
    now = datetime.utcnow()
    if row:
        row.last_checkin_at = now
    else:
        db.add(PulseCheckInCooldown(ip_hash=ip_hash, last_checkin_at=now))
