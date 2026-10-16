import os
import re
from dotenv import load_dotenv

load_dotenv()


def get_allowed_origins() -> list:
    """Exact browser origins allowed to call this API (CORS + analytics).

    ALLOWED_ORIGINS is required - there is deliberately no default, so a
    deployment can never silently inherit another site's origins. Format:
    comma-separated, each like https://samefeel.co (scheme + host, no path, no
    trailing slash, no wildcard). Plain http:// is accepted only for
    localhost/127.0.0.1 and only when ALLOW_DEV_ORIGINS=true.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        raise RuntimeError(
            "ALLOWED_ORIGINS is not set. Set it to the exact frontend origin(s), "
            "e.g. ALLOWED_ORIGINS=https://samefeel.co,https://www.samefeel.co"
        )
    allow_dev = os.getenv("ALLOW_DEV_ORIGINS", "false").lower() in ("true", "1")
    origins = []
    for o in (x.strip() for x in raw.split(",")):
        if not o:
            continue
        m = re.fullmatch(r"(https?)://([A-Za-z0-9.-]+)(:\d+)?", o)
        if not m:
            raise RuntimeError(f"ALLOWED_ORIGINS has an invalid origin: {o!r} (use scheme://host[:port], no path or wildcard)")
        scheme, host = m.group(1), m.group(2)
        if scheme == "http" and not (allow_dev and host in ("localhost", "127.0.0.1")):
            raise RuntimeError(f"ALLOWED_ORIGINS must use https (got {o!r}); http is only allowed for localhost with ALLOW_DEV_ORIGINS=true")
        origins.append(o)
    if not origins:
        raise RuntimeError("ALLOWED_ORIGINS contains no valid origins")
    return origins


DEBUG = os.getenv("DEBUG", "False") == "True"
APP_NAME = "SameFeel"
APP_VERSION = "1.0.0"
