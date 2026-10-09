"""Security response headers.

The container serves the React build itself, so the API is the right
place to send these; nothing in front of it (Render's proxy) adds
them. The Content-Security-Policy matters most: the access token lives
in localStorage, so an injected script could read it, and the policy
is what stops such a script from loading or running in the first
place. Only the app's own origin may serve scripts; styles and fonts
may also come from Google Fonts, which index.html links.

The interactive API docs are the one exception: Swagger UI and ReDoc
load their bundles from a CDN and run inline scripts, so /docs and
/redoc get the other headers but no CSP.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

SECURITY_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"strict-origin-when-cross-origin",
}

_DOCS_PREFIXES = ("/docs", "/redoc")


class SecurityHeadersMiddleware:
    """Pure ASGI middleware: adds the headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        send_csp = not path.startswith(_DOCS_PREFIXES)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(SECURITY_HEADERS.items())
                if send_csp:
                    headers.append(
                        (b"content-security-policy", CONTENT_SECURITY_POLICY.encode())
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
