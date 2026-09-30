"""Exceptions raised by the JustPush SDK."""

from __future__ import annotations

from typing import Any


class JustPushError(Exception):
    """Base class for every error this SDK raises."""


class JustPushConnectionError(JustPushError):
    """The API couldn't be reached, or it didn't answer in time."""


class JustPushValidationError(JustPushError, ValueError):
    """The message or topic is invalid.

    Raised before sending when the SDK can tell on its own (for example, more
    than 10 buttons), and for a 422 from the API. ``errors`` maps each field to
    its messages when the API returns them.
    """

    def __init__(self, message: str, errors: dict[str, list[str]] | None = None) -> None:
        super().__init__(message)
        self.errors: dict[str, list[str]] = errors or {}


class JustPushAPIError(JustPushError):
    """The API answered with an error status."""

    def __init__(self, message: str, status: int, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class JustPushAuthenticationError(JustPushAPIError):
    """401: the token is missing, unknown or revoked."""


class JustPushForbiddenError(JustPushAPIError):
    """403: the token may not do this, or the plan doesn't allow it."""


class JustPushNotFoundError(JustPushAPIError):
    """404: no message or topic with that key or UUID for this account."""


class JustPushSubscriptionError(JustPushAPIError):
    """410: the account's subscription has expired."""


class JustPushRateLimitError(JustPushAPIError):
    """429: too many requests. ``retry_after`` is in seconds when the API sends it."""

    def __init__(
        self, message: str, status: int, body: Any = None, retry_after: int | None = None
    ) -> None:
        super().__init__(message, status, body)
        self.retry_after = retry_after
