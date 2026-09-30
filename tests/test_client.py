import asyncio

import aiohttp
import pytest

from justpush import (
    AsyncJustPush,
    JustPush,
    JustPushAPIError,
    JustPushAuthenticationError,
    JustPushConnectionError,
    JustPushForbiddenError,
    JustPushNotFoundError,
    JustPushRateLimitError,
    JustPushSubscriptionError,
    JustPushValidationError,
    Priority,
)

MESSAGE = {
    "user_uuid": "u1",
    "topic": {"uuid": "t1", "title": "Home", "slug": "home", "avatar": None,
              "has_custom_avatar": False, "api_token": "tok"},
    "key": "abc123",
    "title": "Hi",
    "message": "There",
    "priority": 1,
    "sound": "default",
    "requires_acknowledgement": True,
    "acknowledgement": {"is_acknowledged": True},
    "pending_actions": 0,
    "received_at": "2026-09-30T10:00:00Z",
    "processed_at": "2026-09-30T10:00:01Z",
    "expires_at": None,
}
TOPIC = MESSAGE["topic"]

ERRORS = [
    (401, {"error": {"type": "unauthorized", "message": "Unauthenticated"}}, JustPushAuthenticationError),
    (403, {"error": "Not your topic", "code": 403}, JustPushForbiddenError),
    (404, {"error": {"type": "not_found", "message": "Message not found"}}, JustPushNotFoundError),
    (410, {"error": {"type": "subscription_expired", "message": "Expired"}}, JustPushSubscriptionError),
    (422, {"message": "The sound is invalid.", "errors": {"sound": ["The sound is invalid."]}},
     JustPushValidationError),
    (429, {"message": "Too Many Attempts."}, JustPushRateLimitError),
    (500, b"<html>oops</html>", JustPushAPIError),
]


# --- sync ---------------------------------------------------------------------------------------

def test_send(api):
    result = JustPush(" tok ", base_url=api.url + "/").send("There", title="Hi", priority=Priority.HIGH)
    assert result.key == "abc123"
    assert (result.rate_limit.limit, result.rate_limit.remaining, result.rate_limit.reset_seconds) == (
        10000, 9895, 234512)
    req = api.last
    assert (req["method"], req["path"]) == ("POST", "/messages")
    assert req["headers"]["authorization"] == "Bearer tok"
    assert req["headers"]["content-type"] == "application/json"
    assert req["headers"]["user-agent"].startswith("justpush-python/")
    assert req["json"] == {"title": "Hi", "message": "There", "priority": 1}


def test_rate_limit_headers_missing(api):
    api.headers = {}
    result = JustPush("tok", base_url=api.url).send("x")
    assert result.rate_limit.remaining is None


def test_send_without_key_is_an_error(api):
    api.respond(201, {"status": 1})
    with pytest.raises(Exception, match="no key"):
        JustPush("tok", base_url=api.url).send("x")


def test_get_message(api):
    api.respond(200, MESSAGE)
    details = JustPush("tok", base_url=api.url).get_message("abc 123/x")
    assert api.last["path"] == "/messages/abc%20123%2Fx"
    assert details.key == "abc123" and details.is_acknowledged and details.topic.api_token == "tok"
    assert details.raw["user_uuid"] == "u1"


def test_topics(api):
    client = JustPush("tok", base_url=api.url)
    api.respond(201, TOPIC)
    topic = client.create_topic("Home", avatar_url="https://example.com/a.png")
    assert api.last["json"] == {"title": "Home", "avatar": {"external_url": "https://example.com/a.png"}}
    assert topic.uuid == "t1" and topic.api_token == "tok"

    api.respond(200, {"data": TOPIC})
    assert client.get_topic("t1").title == "Home"
    assert (api.last["method"], api.last["path"]) == ("GET", "/topics/t1")

    api.respond(200, TOPIC)
    client.update_topic("t1", title="New")
    assert (api.last["method"], api.last["json"]) == ("PUT", {"title": "New"})


@pytest.mark.parametrize("status, body, exc", ERRORS)
def test_errors(api, status, body, exc):
    api.respond(status, body, {"Retry-After": "30"} if status == 429 else {})
    with pytest.raises(exc) as info:
        JustPush("tok", base_url=api.url).send("x")
    if status == 422:
        assert info.value.errors == {"sound": ["The sound is invalid."]}
    if status == 429:
        assert info.value.retry_after == 30
    if status in (401, 404):
        assert str(info.value) in ("Unauthenticated", "Message not found")
    if status == 403:
        assert str(info.value) == "Not your topic"


def test_connection_error():
    with pytest.raises(JustPushConnectionError):
        JustPush("tok", base_url="http://127.0.0.1:9").send("x")


def test_timeout(api):
    api.delay = 0.5
    with pytest.raises(JustPushConnectionError):
        JustPush("tok", base_url=api.url, timeout=0.1).send("x")


def test_validation_happens_before_any_request(api):
    with pytest.raises(JustPushValidationError):
        JustPush("tok", base_url=api.url).send("x", priority=9)
    assert api.requests == []


# --- async --------------------------------------------------------------------------------------

def test_async_send_and_topics(api):
    async def run():
        async with AsyncJustPush("tok", base_url=api.url) as client:
            result = await client.send("There", title="Hi", sound="magic")
            assert result.key == "abc123" and result.rate_limit.remaining == 9895
            assert api.last["json"] == {"title": "Hi", "message": "There", "sound": "magic"}
            assert api.last["headers"]["authorization"] == "Bearer tok"

            api.respond(200, MESSAGE)
            assert (await client.get_message("abc123")).title == "Hi"

            api.respond(201, TOPIC)
            assert (await client.create_topic("Home")).slug == "home"
            api.respond(200, TOPIC)
            assert (await client.get_topic("t1")).uuid == "t1"
            await client.update_topic("t1", avatar_image=b"\x89PNG")
            assert api.last["json"] == {"avatar": {"body": "iVBORw=="}}
            session = client._session
        assert session.closed and client._session is None  # closed on exit

    asyncio.run(run())


@pytest.mark.parametrize("status, body, exc", ERRORS)
def test_async_errors(api, status, body, exc):
    api.respond(status, body)

    async def run():
        async with AsyncJustPush("tok", base_url=api.url) as client:
            await client.send("x")

    with pytest.raises(exc):
        asyncio.run(run())


def test_async_shared_session_is_not_closed(api):
    async def run():
        async with aiohttp.ClientSession() as session:
            async with AsyncJustPush("tok", session=session, base_url=api.url) as client:
                await client.send("x")
            assert not session.closed

    asyncio.run(run())


def test_async_connection_errors(api):
    async def unreachable():
        async with AsyncJustPush("tok", base_url="http://127.0.0.1:9") as client:
            await client.send("x")

    async def slow():
        api.delay = 0.5
        async with AsyncJustPush("tok", base_url=api.url, timeout=0.1) as client:
            await client.send("x")

    for coro in (unreachable, slow):
        with pytest.raises(JustPushConnectionError):
            asyncio.run(coro())


# --- verify_token -------------------------------------------------------------------------------

def test_verify_token(api):
    api.respond(404, {"error": {"type": "not_found", "message": "Message not found"}})
    JustPush("tok", base_url=api.url).verify_token()
    assert api.last["method"] == "GET"
    assert api.last["path"].startswith("/messages/verify-")

    api.respond(401, {"error": {"type": "unauthorized", "message": "Unauthenticated"}})
    with pytest.raises(JustPushAuthenticationError):
        JustPush("tok", base_url=api.url).verify_token()


def test_async_verify_token(api):
    async def run():
        async with AsyncJustPush("tok", base_url=api.url) as client:
            await client.verify_token()

    api.respond(404, {"error": {"type": "not_found", "message": "Message not found"}})
    asyncio.run(run())
    api.respond(401, {"error": {"type": "unauthorized", "message": "Unauthenticated"}})
    with pytest.raises(JustPushAuthenticationError):
        asyncio.run(run())
