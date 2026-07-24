"""Fixed-window rate limiting for the endpoints that cost money or send mail.

Backed by the database rather than Django's cache framework on purpose: the
default cache is per-process, and the deployment runs as serverless function
instances that do not share memory, so an in-memory counter would reset
whenever a new instance handled the request.
"""

from __future__ import annotations

from datetime import timedelta
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone

from ..models import RateLimitEvent


def client_identifier(request) -> str:
    """Who to count against: the account when signed in, otherwise the peer IP."""
    if request.user.is_authenticated:
        return f'user:{request.user.pk}'
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    # Vercel appends the real client IP as the left-most entry.
    ip = forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', '') or 'unknown'
    return f'ip:{ip[:100]}'


def check_and_record(scope: str, identifier: str, limit: int, window_seconds: int) -> bool:
    """Record an attempt. Returns True when the caller is over the limit.

    The window is fixed rather than sliding, which is coarse but adequate here
    and costs one count plus one insert.
    """
    cutoff = timezone.now() - timedelta(seconds=window_seconds)
    scoped = RateLimitEvent.objects.filter(scope=scope, identifier=identifier)
    # Opportunistic cleanup, limited to this caller's own rows so it stays cheap.
    scoped.filter(created_at__lt=cutoff).delete()
    if scoped.filter(created_at__gte=cutoff).count() >= limit:
        return True
    RateLimitEvent.objects.create(scope=scope, identifier=identifier)
    return False


def rate_limit(scope: str, limit: int, window_seconds: int, message: str):
    """Reject a request that exceeds `limit` attempts in `window_seconds`.

    JSON endpoints get 429 with a body; page requests get a message and a
    redirect back, so the limit never looks like a crash to a normal user.
    """
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if check_and_record(scope, client_identifier(request), limit, window_seconds):
                if request.headers.get('Accept', '').startswith('application/json') or \
                        request.content_type == 'application/json':
                    return JsonResponse({'ok': False, 'error': message}, status=429)
                messages.error(request, message)
                return redirect(request.META.get('HTTP_REFERER') or 'home')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
