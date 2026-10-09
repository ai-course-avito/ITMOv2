"""What a use case says when it cannot do what was asked. The API turns each into its status; nothing here knows about HTTP routes."""

from typing import ClassVar


class DomainError(Exception):
    status: ClassVar[int] = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status = 404


class Conflict(DomainError):
    status = 409


class Forbidden(DomainError):
    status = 403


class Invalid(DomainError):
    status = 422


class Failed(DomainError):
    """The service could not do it though the request was fine."""

    status = 500
