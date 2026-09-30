"""Typed building blocks for messages, and the objects the API returns."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any

from .exceptions import JustPushValidationError


class Priority(IntEnum):
    """Message priority. Higher priorities break through quiet hours on the device."""

    LOWEST = -2
    LOW = -1
    NORMAL = 0
    HIGH = 1
    HIGHEST = 2

    @classmethod
    def parse(cls, value: Priority | int | str) -> Priority:
        """Accept a Priority, an int from -2 to 2, or a name such as ``"high"``."""
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            raise JustPushValidationError(f"Invalid priority: {value!r}")
        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError:
                raise JustPushValidationError(
                    f"Priority must be between -2 and 2, got {value}"
                ) from None
        if isinstance(value, str):
            text = value.strip()
            if text.lstrip("-").isdigit():
                return cls.parse(int(text))
            try:
                return cls[text.upper()]
            except KeyError:
                pass
        raise JustPushValidationError(f"Invalid priority: {value!r}")


class Sound(str, Enum):
    """Notification sounds the JustPush apps can play."""

    NONE = "none"
    DEFAULT = "default"
    BIKE = "bike"
    BUGLE = "bugle"
    CASHREGISTER = "cashregister"
    CLASSICAL = "classical"
    COSMIC = "cosmic"
    FALLING = "falling"
    GAMELAN = "gamelan"
    INCOMING = "incoming"
    INTERMISSION = "intermission"
    MAGIC = "magic"
    MECHANICAL = "mechanical"
    PIANOBAR = "pianobar"
    SIREN = "siren"
    SPACEALARM = "spacealarm"
    TUGBOAT = "tugboat"
    ALIEN = "alien"
    CLIMB = "climb"
    PERSISTENT = "persistent"
    ECHO = "echo"
    UPDOWN = "updown"
    VIBRATE = "vibrate"

    @classmethod
    def parse(cls, value: Sound | str) -> Sound:
        """Accept a Sound or its name in any case (``"COSMIC"``, ``"cosmic"``)."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            names = ", ".join(s.value for s in cls)
            raise JustPushValidationError(
                f"Unknown sound {value!r}. Use one of: {names}"
            ) from None


@dataclass(frozen=True)
class Button:
    """A button under the message that opens ``url``.

    With ``action_required`` the message stays pending until someone taps it.
    The API cuts ``cta`` to 25 characters.
    """

    cta: str
    url: str
    action_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"cta": self.cta, "url": self.url, "action_required": self.action_required}


@dataclass(frozen=True)
class ButtonGroup:
    """A single button (``cta``) that opens a named list of buttons (at most 10)."""

    name: str
    cta: str
    buttons: list[Button]
    action_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        if len(self.buttons) > 10:
            raise JustPushValidationError("A button group can hold at most 10 buttons")
        return {
            "name": self.name,
            "cta": self.cta,
            "action_required": self.action_required,
            "buttons": [{"cta": b.cta, "url": b.url} for b in self.buttons],
        }


@dataclass(frozen=True)
class Image:
    """An image attached to the message: a public ``url`` or base64 ``body``.

    The first image becomes the banner of the push notification.
    """

    url: str | None = None
    body: str | None = None
    caption: str | None = None

    def __post_init__(self) -> None:
        if (self.url is None) == (self.body is None):
            raise JustPushValidationError("An image needs either a url or a body, not both")

    @classmethod
    def from_bytes(cls, data: bytes, caption: str | None = None) -> Image:
        """Attach raw image bytes (JPEG, PNG, …), e.g. a camera snapshot."""
        return cls(body=base64.b64encode(data).decode("ascii"), caption=caption)

    @classmethod
    def from_file(cls, path: str | Path, caption: str | None = None) -> Image:
        """Attach an image file from disk."""
        return cls.from_bytes(Path(path).read_bytes(), caption=caption)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"url": self.url} if self.url is not None else {"body": self.body}
        if self.caption is not None:
            data["caption"] = self.caption
        return data


@dataclass(frozen=True)
class Acknowledgement:
    """Ask for the message to be acknowledged on a device.

    - ``retry``: keep re-sending until acknowledged, every ``interval`` seconds
      (10–65535), at most ``max_retries`` times (0–255).
    - ``callback_url``: JustPush calls this URL once the message is acknowledged,
      passing ``callback_params`` along.
    """

    retry: bool = False
    interval: int | None = None
    max_retries: int | None = None
    callback_url: str | None = None
    callback_params: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.retry:
            if self.interval is not None and not 10 <= self.interval <= 65535:
                raise JustPushValidationError("Acknowledgement interval must be 10–65535 seconds")
            if self.max_retries is not None and not 0 <= self.max_retries <= 255:
                raise JustPushValidationError("Acknowledgement max_retries must be 0–255")
            data["requires_retry"] = True
            if self.interval is not None:
                data["interval"] = self.interval
            if self.max_retries is not None:
                data["max_retries"] = self.max_retries
        if self.callback_url is not None:
            data["callback"] = {"required": True, "url": self.callback_url}
            if self.callback_params is not None:
                data["callback"]["params"] = json.dumps(dict(self.callback_params))
        return data


@dataclass(frozen=True)
class RateLimit:
    """Your plan's monthly message allowance, from the response headers."""

    limit: int | None
    remaining: int | None
    reset_seconds: int | None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> RateLimit:
        lower = {k.lower(): v for k, v in headers.items()}

        def number(name: str) -> int | None:
            try:
                return int(lower[name])
            except (KeyError, TypeError, ValueError):
                return None

        return cls(
            limit=number("x-limit-app-limit"),
            remaining=number("x-limit-app-remaining"),
            reset_seconds=number("x-limit-app-reset"),
        )


@dataclass(frozen=True)
class SendResult:
    """What the API returns for a queued message."""

    key: str
    rate_limit: RateLimit


@dataclass(frozen=True)
class Topic:
    """A topic groups messages in the app. ``api_token`` can be passed as ``topic_token``."""

    uuid: str
    title: str
    slug: str | None = None
    avatar: str | None = None
    has_custom_avatar: bool = False
    api_token: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> Topic:
        return cls(
            uuid=str(data.get("uuid", "")),
            title=str(data.get("title", "")),
            slug=data.get("slug"),
            avatar=data.get("avatar"),
            has_custom_avatar=bool(data.get("has_custom_avatar")),
            api_token=data.get("api_token"),
            raw=dict(data),
        )


@dataclass(frozen=True)
class MessageDetails:
    """A message as stored by JustPush. ``raw`` holds the full API response."""

    key: str
    title: str | None
    message: str | None
    priority: int | None
    sound: str | None
    topic: Topic | None
    requires_acknowledgement: bool
    is_acknowledged: bool
    pending_actions: Any
    received_at: str | None
    processed_at: str | None
    expires_at: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> MessageDetails:
        topic = data.get("topic")
        ack = data.get("acknowledgement") or {}
        return cls(
            key=str(data.get("key", "")),
            title=data.get("title"),
            message=data.get("message"),
            priority=data.get("priority"),
            sound=data.get("sound"),
            topic=Topic.from_api(topic) if isinstance(topic, Mapping) else None,
            requires_acknowledgement=bool(data.get("requires_acknowledgement")),
            is_acknowledged=bool(ack.get("is_acknowledged")) if isinstance(ack, Mapping) else False,
            pending_actions=data.get("pending_actions"),
            received_at=data.get("received_at"),
            processed_at=data.get("processed_at"),
            expires_at=data.get("expires_at"),
            raw=dict(data),
        )
