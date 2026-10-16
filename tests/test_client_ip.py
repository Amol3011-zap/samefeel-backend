"""
Unit tests for app/services/client_ip.py
Run with: pytest tests/test_client_ip.py -v
"""
import os
from unittest.mock import MagicMock

import pytest

from app.services import client_ip as client_ip_module
from app.services.client_ip import get_client_ip


def make_request(peer_ip, forwarded_for=None):
    req = MagicMock()
    req.client.host = peer_ip
    req.headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}
    return req


@pytest.fixture(autouse=True)
def clear_trusted_proxy_cache():
    # _trusted_proxy_networks() is lru_cache'd, so each test must clear it
    # after changing TRUSTED_PROXY_IPS or reads would be stale.
    yield
    client_ip_module._trusted_proxy_networks.cache_clear()
    os.environ.pop("TRUSTED_PROXY_IPS", None)


class TestGetClientIpNoTrustedProxyConfigured:
    def test_uses_direct_peer_when_no_forwarded_header(self):
        req = make_request("203.0.113.5")
        assert get_client_ip(req) == "203.0.113.5"

    def test_ignores_forwarded_header_when_no_proxy_trusted(self):
        # This is the core fix: with TRUSTED_PROXY_IPS unset (the default),
        # a client cannot pick its own IP via X-Forwarded-For.
        req = make_request("203.0.113.5", forwarded_for="1.2.3.4")
        assert get_client_ip(req) == "203.0.113.5"

    def test_different_spoofed_headers_all_collapse_to_same_real_peer(self):
        for spoofed in ["1.1.1.1", "8.8.8.8", "192.168.1.1", "10.0.0.1"]:
            req = make_request("203.0.113.5", forwarded_for=spoofed)
            assert get_client_ip(req) == "203.0.113.5"

    def test_localhost_dev_works_with_no_configuration(self):
        req = make_request("127.0.0.1")
        assert get_client_ip(req) == "127.0.0.1"

    def test_unknown_peer_when_no_client_info(self):
        req = MagicMock()
        req.client = None
        req.headers = {}
        assert get_client_ip(req) == "unknown"


class TestGetClientIpWithTrustedProxyConfigured:
    def test_forwarded_header_trusted_when_peer_is_configured_proxy(self):
        os.environ["TRUSTED_PROXY_IPS"] = "10.0.0.5"
        client_ip_module._trusted_proxy_networks.cache_clear()
        req = make_request("10.0.0.5", forwarded_for="198.51.100.7")
        assert get_client_ip(req) == "198.51.100.7"

    def test_forwarded_header_still_ignored_from_untrusted_peer(self):
        os.environ["TRUSTED_PROXY_IPS"] = "10.0.0.5"
        client_ip_module._trusted_proxy_networks.cache_clear()
        req = make_request("203.0.113.99", forwarded_for="198.51.100.7")
        assert get_client_ip(req) == "203.0.113.99"

    def test_cidr_range_is_honored(self):
        os.environ["TRUSTED_PROXY_IPS"] = "10.0.0.0/8"
        client_ip_module._trusted_proxy_networks.cache_clear()
        req = make_request("10.5.5.5", forwarded_for="198.51.100.7")
        assert get_client_ip(req) == "198.51.100.7"

    def test_peer_just_outside_cidr_range_not_trusted(self):
        os.environ["TRUSTED_PROXY_IPS"] = "10.0.0.0/8"
        client_ip_module._trusted_proxy_networks.cache_clear()
        req = make_request("11.0.0.1", forwarded_for="198.51.100.7")
        assert get_client_ip(req) == "11.0.0.1"

    def test_first_entry_used_when_forwarded_chain_has_multiple_hops(self):
        os.environ["TRUSTED_PROXY_IPS"] = "10.0.0.5"
        client_ip_module._trusted_proxy_networks.cache_clear()
        req = make_request("10.0.0.5", forwarded_for="198.51.100.7, 10.0.0.5")
        assert get_client_ip(req) == "198.51.100.7"

    def test_malformed_trusted_proxy_config_entry_ignored_not_crashed(self):
        os.environ["TRUSTED_PROXY_IPS"] = "not-an-ip, 10.0.0.5"
        client_ip_module._trusted_proxy_networks.cache_clear()
        req = make_request("10.0.0.5", forwarded_for="198.51.100.7")
        assert get_client_ip(req) == "198.51.100.7"
