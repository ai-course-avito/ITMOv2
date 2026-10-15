import logfire
import time
from typing import Optional

from core import error_response
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core import metrics
from services.auth import AuthError, AuthService

# Reachable without a token
PUBLIC_PATHS = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/docs/oauth2-redirect",
    "/healthz",
    "/readyz",
    "/metrics",
)

# Public as a whole: the files of the promo videos the landing page plays (`/api/v1/media/omnixon-ad-ru.mp4`, ...)
PUBLIC_PREFIXES = ("/api/v1/media/",)


# An admin sends this to use the service as another agent (users, knowledge, answers; usage is
# still written on the admin's own token)
ACT_AS_HEADER = "X-Act-As-Agent"


def _get_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]

    return None


class DatabaseMiddleware:
    """Authenticates the token (its sha256 is looked up) and gives the request its database access
    (`request.state.db`), and logs one line per request.

    A plain ASGI middleware, not BaseHTTPMiddleware: that one wraps the request's
    `receive`, so a route could not notice that the client has gone away."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        status = {"code": None, "token_id": None}

        async def send_and_note(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        request = Request(scope, receive)
        metrics.HTTP_IN_FLIGHT.inc()
        try:
            await self._handle(request, scope, receive, send_and_note, status)
        except Exception as exc:
            error, detail = error_response(exc)
            log = logfire.exception if error == 500 else logfire.warning
            log(
                "Request failed with {status} on {method} {path}",
                status=error,
                method=request.method,
                path=request.url.path,
                _exc_info=exc,
            )
            if status["code"] is None:  # nothing was sent yet: answer properly
                await JSONResponse(status_code=error, content={"detail": detail})(
                    scope, receive, send_and_note
                )
        finally:
            metrics.HTTP_IN_FLIGHT.dec()
            elapsed = time.monotonic() - started
            route = scope.get("route")  # set by the router once it matched
            template = getattr(route, "path", None) or "unmatched"
            metrics.HTTP_REQUESTS.labels(
                request.method, template, str(status["code"])
            ).inc()
            metrics.HTTP_DURATION.labels(request.method, template).observe(elapsed)
            if template not in ("/healthz", "/readyz", "/metrics"):  # probes are noise
                logfire.info(
                    "{method} {path} -> {status}",
                    method=request.method,
                    path=request.url.path,
                    status=status["code"],
                    duration_ms=round(elapsed * 1000, 1),
                    token_id=status["token_id"],
                )

    async def _handle(
        self, request: Request, scope: Scope, receive: Receive, send: Send, status: dict
    ) -> None:
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith(PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        token = _get_token(request)
        if token is None:
            logfire.warning("Request without an API token")
            await Response(
                status_code=403, content="Authentication failed: API token is missing"
            )(scope, receive, send)
            return

        auth: AuthService = request.app.state.container.get(AuthService)
        try:
            principal = await auth.authenticate(token, request.headers.get(ACT_AS_HEADER))
        except AuthError as refusal:
            if not refusal.as_json:
                logfire.warning("Request with an unknown API token")
            answer = (
                JSONResponse(status_code=refusal.status, content={"detail": refusal.body})
                if refusal.as_json
                else Response(status_code=refusal.status, content=refusal.body)
            )
            await answer(scope, receive, send)
            return

        status["token_id"] = principal.token.id
        scope.setdefault("state", {})["principal"] = principal
        await self.app(scope, receive, send)
