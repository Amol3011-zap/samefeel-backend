"""
Trusted-proxy client IP extraction.

`X-Forwarded-For` is a client-settable HTTP header — trusting it
unconditionally lets any caller pick their own rate-limit identity by
sending a different value on every request. This module only honors the
header when the request's *direct* TCP peer (request.client.host, which
cannot be spoofed at the HTTP layer) is itself a configured trusted proxy.

Configuration:
  TRUSTED_PROXY_IPS — comma-separated list of proxy IPs/CIDRs allowed to set
  X-Forwarded-For (e.g. your hosting platform's edge). Unset in local dev,
  where request.client.host (typically 127.0.0.1) is used directly.

  Example for a platform that always fronts the app (Railway, etc.), once
  its edge IP range is known:
    TRUSTED_PROXY_IPS=10.0.0.0/8

If TRUSTED_PROXY_IPS is unset, X-Forwarded-For is never trusted and
request.client.host is always used — this is the safe default and also
what makes plain localhost development work with no extra configuration.
"""
import os
from ipaddress import ip_address, ip_network
from functools import lru_cache

from fastapi import Request


@lru_cache(maxsize=1)
def _trusted_proxy_networks():
    raw = os.getenv("TRUSTED_PROXY_IPS", "")
    networks = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ip_network(entry, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _is_trusted_proxy(peer_ip: str) -> bool:
    networks = _trusted_proxy_networks()
    if not networks:
        return False
    try:
        addr = ip_address(peer_ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def get_client_ip(request: Request) -> str:
    """Best-effort real client IP, resistant to header spoofing.

    Only reads X-Forwarded-For when the direct connection came from a
    configured trusted proxy; otherwise always uses the direct TCP peer.
    """
    peer_ip = request.client.host if request.client else "unknown"

    if peer_ip != "unknown" and _is_trusted_proxy(peer_ip):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # First entry is the original client as seen by the trusted
            # edge; still client-influenced content but only reachable via
            # a hop we've explicitly decided to trust.
            return forwarded.split(",")[0].strip()

    return peer_ip
