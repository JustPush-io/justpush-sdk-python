"""Synchronous JustPush client. Uses only the standard library."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping
from typing import Any

from . import _core
from .exceptions import JustPushConnectionError, JustPushNotFoundError
from .models import (
    Acknowledgement,
    Button,
    ButtonGroup,
    Image,
    MessageDetails,
    Priority,
    SendResult,
    Sound,
    Topic,
)


class JustPush:
    """Send push notifications through the JustPush API.

    >>> client = JustPush("YOUR_API_TOKEN")
    >>> client.send("The backup finished", title="Backups")
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = _core.DEFAULT_BASE_URL,
        timeout: float = _core.DEFAULT_TIMEOUT,
    ) -> None:
        self._token = _core.check_token(token)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def __repr__(self) -> str:
        return f"JustPush(base_url={self._base_url!r})"

    def send(
        self,
        message: str | None = None,
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
    ) -> SendResult:
        """Queue a push notification and return its key.

        ``topic`` is a topic *name*: an existing topic with that name is used,
        otherwise a new one is created. ``topic_token`` targets a topic by its
        API token instead. Without either, the message goes to your default topic.
        """
        body = _core.message_payload(
            message,
            title=title,
            topic=topic,
            topic_token=topic_token,
            priority=priority,
            sound=sound,
            buttons=buttons,
            button_groups=button_groups,
            images=images,
            expiry=expiry,
            acknowledge=acknowledge,
        )
        data, response_headers = self._request("POST", "/messages", body)
        return _core.send_result(data, response_headers)

    def get_message(self, key: str) -> MessageDetails:
        """Fetch a message you sent, e.g. to check whether it was acknowledged."""
        path = "/messages/" + _core.check_path_part(key, "key")
        data, _ = self._request("GET", path)
        return MessageDetails.from_api(_core.as_mapping(data))

    def verify_token(self) -> None:
        """Check that the token is valid without sending anything or using quota.

        Raises :class:`JustPushAuthenticationError` for an invalid token and
        :class:`JustPushConnectionError` when the API can't be reached.
        """
        try:
            self._request("GET", _core.verify_token_path())
        except JustPushNotFoundError:
            return

    def create_topic(
        self,
        title: str,
        *,
        avatar_url: str | None = None,
        avatar_image: bytes | None = None,
    ) -> Topic:
        """Create a topic. Give it an avatar from a public URL or from image bytes."""
        body = _core.topic_payload(title, avatar_url=avatar_url, avatar_image=avatar_image, required=True)
        data, _ = self._request("POST", "/topics", body)
        return Topic.from_api(_core.as_mapping(data))

    def get_topic(self, uuid: str) -> Topic:
        """Fetch one of your topics by its UUID."""
        data, _ = self._request("GET", "/topics/" + _core.check_path_part(uuid, "uuid"))
        return Topic.from_api(_core.as_mapping(data))

    def update_topic(
        self,
        uuid: str,
        *,
        title: str | None = None,
        avatar_url: str | None = None,
        avatar_image: bytes | None = None,
    ) -> Topic:
        """Rename a topic or change its avatar. The default topic can't be renamed."""
        body = _core.topic_payload(title, avatar_url=avatar_url, avatar_image=avatar_image, required=False)
        path = "/topics/" + _core.check_path_part(uuid, "uuid")
        data, _ = self._request("PUT", path, body)
        return Topic.from_api(_core.as_mapping(data))

    def _request(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> tuple[Any, dict[str, str]]:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self._base_url + path,
            data=payload,
            method=method,
            headers=_core.headers(self._token),
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                status = response.status
                raw = response.read()
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as err:
            status = err.code
            raw = err.read()
            response_headers = dict(err.headers.items()) if err.headers else {}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            raise JustPushConnectionError(f"Could not reach JustPush: {err}") from err

        try:
            data: Any = json.loads(raw) if raw else None
        except ValueError:
            data = raw.decode("utf-8", "replace")

        _core.raise_for_status(status, data, response_headers)
        return data, response_headers
