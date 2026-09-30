"""Shared request building and response handling for the sync and async clients."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .exceptions import (
    JustPushAPIError,
    JustPushAuthenticationError,
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

DEFAULT_BASE_URL = "https://api.justpush.io"
DEFAULT_TIMEOUT = 10.0

__version__ = "0.2.0"
USER_AGENT = f"justpush-python/{__version__}"


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def check_token(token: str) -> str:
    if not isinstance(token, str) or not token.strip():
        raise JustPushValidationError("A JustPush API token is required")
    return token.strip()


def message_payload(
    message: str | None,
    *,
    title: str | None = None,
    topic: str | None = None,
    topic_token: str | None = None,
    priority: Priority | int | str | None = None,
    sound: Sound | str | None = None,
    buttons: Iterable[Button] | None = None,
    button_groups: Iterable[ButtonGroup] | None = None,
    images: Iterable[Image] | None = None,
    expiry: int | None = None,
    acknowledge: bool | Acknowledgement = False,
) -> dict[str, Any]:
    """Build the JSON body for ``POST /messages``, validating what the API would reject."""
    if not message and not title:
        raise JustPushValidationError("A message needs a message or a title")
    if topic and topic_token:
        raise JustPushValidationError("Pass either topic or topic_token, not both")

    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if message:
        body["message"] = message
    if topic:
        body["topic"] = topic
    if topic_token:
        body["topic_token"] = topic_token
    if priority is not None:
        body["priority"] = int(Priority.parse(priority))
    if sound is not None:
        body["sound"] = Sound.parse(sound).value
    if expiry is not None:
        if isinstance(expiry, bool) or not isinstance(expiry, int) or not 0 <= expiry <= 2_147_483_647:
            raise JustPushValidationError("expiry must be a whole number of seconds, 0 or more")
        body["expiry_ttl"] = expiry

    button_list = list(buttons or [])
    if len(button_list) > 10:
        raise JustPushValidationError("A message can have at most 10 buttons")
    if button_list:
        body["buttons"] = [b.to_dict() for b in button_list]

    group_list = list(button_groups or [])
    if len(group_list) > 4:
        raise JustPushValidationError("A message can have at most 4 button groups")
    if group_list:
        body["button_groups"] = [g.to_dict() for g in group_list]

    image_list = list(images or [])
    if len(image_list) > 10:
        raise JustPushValidationError("A message can have at most 10 images")
    if image_list:
        body["images"] = [i.to_dict() for i in image_list]

    if acknowledge:
        body["requires_acknowledgement"] = True
        if isinstance(acknowledge, Acknowledgement):
            details = acknowledge.to_dict()
            if details:
                body["acknowledgement"] = details

    return body


def topic_payload(
    title: str | None,
    *,
    avatar_url: str | None = None,
    avatar_image: bytes | None = None,
    required: bool,
) -> dict[str, Any]:
    import base64

    if required and not title:
        raise JustPushValidationError("A topic needs a title")
    if title is not None and len(title) > 100:
        raise JustPushValidationError("A topic title can be at most 100 characters")
    if avatar_url and avatar_image:
        raise JustPushValidationError("Pass either avatar_url or avatar_image, not both")

    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if avatar_url:
        body["avatar"] = {"external_url": avatar_url}
    elif avatar_image:
        body["avatar"] = {"body": base64.b64encode(avatar_image).decode("ascii")}
    return body


def verify_token_path() -> str:
    """A message path that can't exist, so the API answers 404 for a valid token and 401 otherwise.

    There is no account endpoint, and this uses no quota.
    """
    import secrets

    return "/messages/verify-" + secrets.token_hex(16)


def check_path_part(value: str, name: str) -> str:
    from urllib.parse import quote

    if not isinstance(value, str) or not value.strip():
        raise JustPushValidationError(f"{name} is required")
    return quote(value.strip(), safe="")


def _error_message(body: Any, fallback: str) -> str:
    """Pull a readable message out of the API's several error shapes."""
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str) and error:
            return error
        if body.get("message"):
            return str(body["message"])
    return fallback


def raise_for_status(status: int, body: Any, response_headers: Mapping[str, str]) -> None:
    if 200 <= status < 300:
        return

    message = _error_message(body, f"JustPush API returned HTTP {status}")

    if status == 401:
        raise JustPushAuthenticationError(message, status, body)
    if status == 403:
        raise JustPushForbiddenError(message, status, body)
    if status == 404:
        raise JustPushNotFoundError(message, status, body)
    if status == 410:
        raise JustPushSubscriptionError(message, status, body)
    if status == 422:
        errors = body.get("errors") if isinstance(body, Mapping) else None
        raise JustPushValidationError(message, errors if isinstance(errors, dict) else None)
    if status == 429:
        lower = {k.lower(): v for k, v in response_headers.items()}
        try:
            retry_after: int | None = int(lower.get("retry-after", ""))
        except ValueError:
            retry_after = None
        raise JustPushRateLimitError(message, status, body, retry_after)
    raise JustPushAPIError(message, status, body)


def send_result(body: Any, response_headers: Mapping[str, str]) -> SendResult:
    if not isinstance(body, Mapping) or not body.get("key"):
        raise JustPushError("JustPush accepted the message but returned no key")
    return SendResult(key=str(body["key"]), rate_limit=RateLimit.from_headers(response_headers))


def as_mapping(body: Any) -> Mapping[str, Any]:
    if not isinstance(body, Mapping):
        raise JustPushError("Unexpected response from the JustPush API")
    # Laravel resources are sometimes wrapped in "data".
    data = body.get("data")
    return data if isinstance(data, Mapping) else body


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "MessageDetails",
    "Topic",
    "__version__",
]
