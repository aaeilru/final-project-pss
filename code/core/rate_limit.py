from django.core.cache import cache
from ninja.errors import HttpError


def rate_limit(request, limit=60, window=60):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"rate_limit:{ip}"

    current = cache.get(key)

    if current is None:
        cache.set(key, 1, timeout=window)
        return

    if current >= limit:
        raise HttpError(429, "Rate limit exceeded. Maksimal 60 requests per minute.")

    cache.incr(key)