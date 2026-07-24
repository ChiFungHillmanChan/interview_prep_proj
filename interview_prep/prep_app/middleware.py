"""Response security headers that Django does not ship itself."""

from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """Send a Content-Security-Policy on every response.

    The point of this policy is the origin restriction: every script and
    stylesheet must come from our own origin, so a compromised CDN or npm
    package cannot execute in a session that renders private Career Memory.
    All front-end assets are committed under ``static/`` for that reason.

    ``'unsafe-inline'`` and ``'unsafe-eval'`` are still allowed for scripts.
    Several templates carry inline blocks and handlers, and Alpine evaluates
    its directive expressions with ``new Function``. Removing them means
    nonce-ing every inline block and moving to Alpine's CSP build, which is a
    separate piece of work — the policy below is deliberately the version that
    could ship without breaking a page.
    """

    DEFAULT_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # An empty setting means "use the policy below", not "send no policy".
        self.policy = getattr(settings, 'CONTENT_SECURITY_POLICY', '') or self.DEFAULT_POLICY

    def __call__(self, request):
        response = self.get_response(request)
        if self.policy and 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = self.policy
        return response
