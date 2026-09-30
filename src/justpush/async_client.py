"""Asynchronous JustPush client, built on aiohttp.

Pass your own ``aiohttp.ClientSession`` to share it (Home Assistant integrations
must use ``async_get_clientsession(hass)``). Without one, the client creates a
session and closes it in ``close()`` or when the ``async with`` block ends.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Mapping
from typing import Any

import aiohttp

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


class AsyncJustPush:
    """Async version of :class:`justpush.JustPush` with the same methods.

    >>> async with AsyncJustPush("YOUR_API_TOKEN") as client:
    ...     await client.send("Someone rang the doorbell", title="Doorbell")
    """

    def __init__(
        self,
        token: str,
        *,
        session: aiohttp.ClientSession | None = None,
        base_url: str = _core.DEFAULT_BASE_URL,
        timeout: float = _core.DEFAULT_TIMEOUT,
    ) -> None:
        self._token = _core.check_token(token)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session
        self._owns_session = session is None

    def __repr__(self) -> str:
        return f"AsyncJustPush(base_url={self._base_url!r})"

    async def __aenter__(self) -> AsyncJustPush:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session, if this client created it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def send(
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
        """Queue a push notification and return its key. See :meth:`JustPush.send`."""
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
        data, response_headers = await self._request("POST", "/messages", body)
        return _core.send_result(data, response_headers)

    async def get_message(self, key: str) -> MessageDetails:
        """Fetch a message you sent, e.g. to check whether it was acknowledged."""
        path = "/messages/" + _core.check_path_part(key, "key")
        data, _ = await self._request("GET", path)
        return MessageDetails.from_api(_core.as_mapping(data))

    async def verify_token(self) -> None:
        """Check that the token is valid without sending anything or using quota.

        Raises :class:`JustPushAuthenticationError` for an invalid token and
        :class:`JustPushConnectionError` when the API can't be reached.
        """
        try:
            await self._request("GET", _core.verify_token_path())
        except JustPushNotFoundError:
            return

    async def create_topic(
        self,
        title: str,
        *,
        avatar_url: str | None = None,
        avatar_image: bytes | None = None,
    ) -> Topic:
        """Create a topic. Give it an avatar from a public URL or from image bytes."""
        body = _core.topic_payload(title, avatar_url=avatar_url, avatar_image=avatar_image, required=True)
        data, _ = await self._request("POST", "/topics", body)
        return Topic.from_api(_core.as_mapping(data))

    async def get_topic(self, uuid: str) -> Topic:
        """Fetch one of your topics by its UUID."""
        data, _ = await self._request("GET", "/topics/" + _core.check_path_part(uuid, "uuid"))
        return Topic.from_api(_core.as_mapping(data))

    async def update_topic(
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
        data, _ = await self._request("PUT", path, body)
        return Topic.from_api(_core.as_mapping(data))

    async def _request(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> tuple[Any, dict[str, str]]:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

        try:
            async with self._session.request(
                method,
                self._base_url + path,
                data=json.dumps(body) if body is not None else None,
                headers=_core.headers(self._token),
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as response:
                raw = await response.read()
                status = response.status
                response_headers = dict(response.headers.items())
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise JustPushConnectionError(f"Could not reach JustPush: {err}") from err

        try:
            data: Any = json.loads(raw) if raw else None
        except ValueError:
            data = raw.decode("utf-8", "replace")

        _core.raise_for_status(status, data, response_headers)
        return data, response_headers
