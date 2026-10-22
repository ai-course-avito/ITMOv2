class UnlinkError(Exception):
    """Base exception for all Unlink client errors."""

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class NotFound(UnlinkError):
    """Raised when the requested resource does not exist (HTTP 404)."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class NoAccess(UnlinkError):
    """Raised when the token is invalid or lacks permission (HTTP 401/403)."""

    def __init__(self, message: str = "Access denied: invalid or missing token"):
        super().__init__(message, status_code=403)


class Conflict(UnlinkError):
    """Raised when the request conflicts with the current state (HTTP 409)."""

    def __init__(self, message: str = "Conflict: resource already exists"):
        super().__init__(message, status_code=409)


class InvalidRequest(UnlinkError):
    """Raised when the service rejects the data of a request (HTTP 422)."""

    def __init__(self, message: str = "Invalid request"):
        super().__init__(message, status_code=422)


class UpstreamError(UnlinkError):
    """Raised when what the service depends on failed: the model provider or an MCP
    server returned an error (HTTP 502) or timed out (HTTP 504). The service itself
    works; the message says what went wrong, and a retry may help."""

    def __init__(
        self, message: str = "Upstream service failed", status_code: int = 502
    ):
        super().__init__(message, status_code=status_code)


class ConnectionError(UnlinkError):
    """Raised when the client cannot reach the API."""

    def __init__(self, message: str = "Cannot connect to the API"):
        super().__init__(message)


class StreamError(UnlinkError):
    """Raised when the server reports an error in the middle of a streamed response."""

    def __init__(self, message: str = "Streaming failed"):
        super().__init__(message)
