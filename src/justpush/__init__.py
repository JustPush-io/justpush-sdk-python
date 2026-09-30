"""Official Python SDK for JustPush (https://justpush.io)."""

from ._core import __version__
from .client import JustPush
from .exceptions import (
    JustPushAPIError,
    JustPushAuthenticationError,
    JustPushConnectionError,
    JustPushError,
    JustPushForbiddenError,
    JustPushNotFoundError,
    JustPushRateLimitError,
    JustPushSubscriptionError,
    JustPushValidationError,
)
from .models import (
    Acknowledgement,
    Button,
    ButtonGroup,
    Image,
    MessageDetails,
    Priority,
    RateLimit,
    SendResult,
    Sound,
    Topic,
)


def __getattr__(name: str) -> type:
    # Import lazily so the sync client works without aiohttp installed.
    if name == "AsyncJustPush":
        from .async_client import AsyncJustPush

        return AsyncJustPush
    raise AttributeError(f"module 'justpush' has no attribute {name!r}")


__all__ = [
    "Acknowledgement",
    "AsyncJustPush",
    "Button",
    "ButtonGroup",
    "Image",
    "JustPush",
    "JustPushAPIError",
    "JustPushAuthenticationError",
    "JustPushConnectionError",
    "JustPushError",
    "JustPushForbiddenError",
    "JustPushNotFoundError",
    "JustPushRateLimitError",
    "JustPushSubscriptionError",
    "JustPushValidationError",
    "MessageDetails",
    "Priority",
    "RateLimit",
    "SendResult",
    "Sound",
    "Topic",
    "__version__",
]
