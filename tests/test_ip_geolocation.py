"""
Unit tests for app/services/ip_geolocation.py
Run with: pytest tests/test_ip_geolocation.py -v

Only the synchronous _is_public_ip() gate is tested directly — that's the
one piece of real logic (deciding whether to even attempt a network call).
The async lookup() wrapper around it is a thin httpx call + response
parse; exercising it would mean either a live network dependency in the
test suite or pulling in pytest-asyncio + a mocking layer for one function
that has no branching logic of its own beyond what _is_public_ip already
gates. Not worth the added test dependency for this.
"""
from app.services.ip_geolocation import _is_public_ip


class TestIsPublicIp:
    def test_loopback_is_not_public(self):
        assert _is_public_ip("127.0.0.1") is False

    def test_private_class_a_is_not_public(self):
        assert _is_public_ip("10.0.0.5") is False

    def test_private_class_c_is_not_public(self):
        assert _is_public_ip("192.168.1.1") is False

    def test_link_local_is_not_public(self):
        assert _is_public_ip("169.254.1.1") is False

    def test_real_public_ip_is_public(self):
        assert _is_public_ip("8.8.8.8") is True

    def test_another_real_public_ip_is_public(self):
        assert _is_public_ip("1.1.1.1") is True

    def test_malformed_ip_is_not_public(self):
        assert _is_public_ip("not-an-ip") is False

    def test_empty_string_is_not_public(self):
        assert _is_public_ip("") is False

    def test_unknown_sentinel_is_not_public(self):
        assert _is_public_ip("unknown") is False
