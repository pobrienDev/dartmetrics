"""Shared rate limiter (one instance, imported by main and the routers).

Keyed by client IP. Behind a reverse proxy uvicorn must be run with
--proxy-headers and --forwarded-allow-ips so the real client address,
not the proxy's, is what gets limited.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
