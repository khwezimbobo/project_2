"""
Login lockout: refuse logins after too many failures.

Failures are counted per (username, IP address) in the cache, so:
  * guessing a password for one account from one machine is stopped, and
  * a stranger cannot lock a real user out from a different IP address.

Limits come from settings.LOCKOUT_MAX_ATTEMPTS and settings.LOCKOUT_SECONDS.
Behind a reverse proxy, REMOTE_ADDR is the proxy's address; configure the
proxy to pass the real client address before relying on per-IP counting.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _cache_key(request, username):
    """Build a fixed-length cache key so odd usernames never break the cache."""
    ip_address = request.META.get("REMOTE_ADDR", "")
    raw = f"{str(username).strip().lower()}|{ip_address}"
    return "lockout:" + hashlib.sha256(raw.encode()).hexdigest()


def is_locked(request, username):
    """True when this username/IP pair has used up its allowed failures."""
    failures = cache.get(_cache_key(request, username), 0)
    return failures >= settings.LOCKOUT_MAX_ATTEMPTS


def record_failure(request, username):
    """Count one failed login. The counter expires LOCKOUT_SECONDS after the first failure."""
    key = _cache_key(request, username)

    # add() only sets the key (and its expiry) when it does not exist yet.
    cache.add(key, 0, timeout=settings.LOCKOUT_SECONDS)
    failures = cache.incr(key)

    if failures == settings.LOCKOUT_MAX_ATTEMPTS:
        logger.warning(
            "Login locked for username '%s' after %s failed attempts.", username, failures
        )


def clear_failures(request, username):
    """Forget earlier failures after a successful login."""
    cache.delete(_cache_key(request, username))


def lockout_message():
    """Text shown to the person who is locked out."""
    minutes = max(1, settings.LOCKOUT_SECONDS // 60)
    return f"Too many failed login attempts. Please try again in {minutes} minutes."
