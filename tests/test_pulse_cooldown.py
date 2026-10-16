"""
Unit tests for app/services/pulse_cooldown.py
Run with: pytest tests/test_pulse_cooldown.py -v
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from app.services.pulse_cooldown import COOLDOWN_HOURS, hash_ip, is_on_cooldown, record_checkin


class TestHashIp:
    def test_same_ip_hashes_identically(self):
        assert hash_ip("203.0.113.5") == hash_ip("203.0.113.5")

    def test_different_ips_hash_differently(self):
        assert hash_ip("203.0.113.5") != hash_ip("203.0.113.6")

    def test_hash_is_not_the_raw_ip(self):
        h = hash_ip("203.0.113.5")
        assert "203.0.113.5" not in h

    def test_hash_is_a_64_char_hex_digest(self):
        h = hash_ip("203.0.113.5")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


def make_db_with_row(row):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    return db


def make_empty_db():
    return make_db_with_row(None)


class TestIsOnCooldown:
    def test_no_prior_checkin_not_on_cooldown(self):
        db = make_empty_db()
        assert is_on_cooldown(db, "203.0.113.5") is False

    def test_recent_checkin_is_on_cooldown(self):
        row = MagicMock(last_checkin_at=datetime.utcnow() - timedelta(hours=1))
        db = make_db_with_row(row)
        assert is_on_cooldown(db, "203.0.113.5") is True

    def test_checkin_older_than_cooldown_window_not_on_cooldown(self):
        row = MagicMock(last_checkin_at=datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS + 1))
        db = make_db_with_row(row)
        assert is_on_cooldown(db, "203.0.113.5") is False

    def test_checkin_just_inside_window_is_on_cooldown(self):
        row = MagicMock(last_checkin_at=datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS - 1))
        db = make_db_with_row(row)
        assert is_on_cooldown(db, "203.0.113.5") is True


class TestRecordCheckin:
    def test_creates_new_row_when_none_exists(self):
        db = make_empty_db()
        record_checkin(db, "203.0.113.5")
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.ip_hash == hash_ip("203.0.113.5")

    def test_updates_existing_row_instead_of_creating_duplicate(self):
        row = MagicMock(last_checkin_at=datetime.utcnow() - timedelta(hours=30))
        db = make_db_with_row(row)
        record_checkin(db, "203.0.113.5")
        db.add.assert_not_called()
        assert row.last_checkin_at > datetime.utcnow() - timedelta(seconds=5)
