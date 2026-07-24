"""Shared configuration for the external model boundary.

Both `interview_coach` and `career_memory` own their own `_request_json`, but
they must agree on how long a single call may take. This lives in its own
module because `interview_coach` already imports from `career_memory`, so
either of them owning it would create an import cycle.
"""

from django.conf import settings


def request_timeout_ms() -> int:
    """Deadline for a single Gemini call, in milliseconds.

    google-genai leaves `HttpOptions.timeout` as None and passes that straight
    to httpx, which disables connect/read/write/pool deadlines entirely. A
    stalled call would then run until the platform kills the invocation, and
    the deterministic fallback — which only runs on an exception, never on a
    hang — would never be reached.

    Keep this comfortably below the deployment's function duration limit.
    """
    return int(getattr(settings, 'AI_REQUEST_TIMEOUT_SECONDS', 20)) * 1000
