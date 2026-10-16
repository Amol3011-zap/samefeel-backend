"""
IP-based geolocation for Global Pulse check-ins.

Product decision (not the original design): check-in records now retain
the submitter's IP address and an IP-derived city, for internal records.
This is a deliberate reversal of the earlier "fully anonymous, no IP ever
stored" model — see PulseCheckIn's docstring in app/models.py. The public
API (GET /api/pulse/global) never returns ip_address or city; only this
stored record is more precise than before.

Uses ip-api.com's free tier (no API key, HTTP only — the free tier does
not offer HTTPS). Best-effort: any failure (timeout, rate limit, private/
loopback IP in local dev) returns all-None fields rather than raising, so
a geolocation hiccup never blocks a check-in from being recorded.
"""
import ipaddress
import logging

import httpx

logger = logging.getLogger("pulse.geolocation")

_TIMEOUT_SECONDS = 3.0
_API_URL_TEMPLATE = "http://ip-api.com/json/{ip}?fields=status,country,countryCode,city"


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


async def lookup(ip: str) -> dict:
    """Returns {"country_code": str|None, "country_name": str|None, "city": str|None}."""
    empty = {"country_code": None, "country_name": None, "city": None}

    if not ip or ip == "unknown" or not _is_public_ip(ip):
        # Local dev (127.0.0.1, private LAN ranges) has no meaningful
        # IP-geolocation result — don't waste a request on it.
        return empty

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.get(_API_URL_TEMPLATE.format(ip=ip))
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("IP geolocation lookup failed: %s", e)
        return empty

    if data.get("status") != "success":
        return empty

    return {
        "country_code": data.get("countryCode"),
        "country_name": data.get("country"),
        "city": data.get("city"),
    }
