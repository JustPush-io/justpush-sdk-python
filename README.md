<p align="center"><img src="https://cdn.justpush.io/core/app%20icon_nobackground.svg" width="150" height="auto"></p>

## JustPush — Python SDK

The official Python SDK for [JustPush](https://justpush.io). Send push notifications to your
iOS and Android devices from any Python script, server or Home Assistant integration.

- A sync client that uses only the standard library, and an async client on `aiohttp`
- Typed models for buttons, button groups, images, sounds and acknowledgements
- Checks the message before sending it, so you get a clear error instead of a rejected request
- Rate-limit information on every send

## Installation

```bash
pip install justpush
```

Python 3.10 or newer.

## Send a message

```python
from justpush import JustPush

client = JustPush("YOUR_API_TOKEN")
result = client.send("The nightly backup finished", title="Backups")

print(result.key)                    # use it with get_message()
print(result.rate_limit.remaining)   # messages left this month
```

Get your API token from the JustPush app.

### Everything a message can do

```python
from justpush import Acknowledgement, Button, ButtonGroup, Image, JustPush, Priority, Sound

client = JustPush("YOUR_API_TOKEN")

client.send(
    "Water detected under the washing machine",
    title="💧 Leak",
    topic="Home",                        # topic name; created if it doesn't exist yet
    priority=Priority.HIGHEST,           # or 2, or "highest"
    sound=Sound.SIREN,                   # or "siren"
    buttons=[Button("Open camera", "https://example.com/cam")],
    images=[Image.from_file("snapshot.jpg", caption="Kitchen")],
    expiry=3600,                         # hide the message after an hour
    acknowledge=Acknowledgement(
        retry=True, interval=60, max_retries=10,
        callback_url="https://example.com/acknowledged",
        callback_params={"sensor": "kitchen"},
    ),
)
```

| Argument | |
| --- | --- |
| `message`, `title` | At least one is required. Titles over 255 characters are cut short. |
| `topic` | A topic **name**. An existing topic with that name is used, or a new one is created. |
| `topic_token` | Target a topic by its API token instead (`Topic.api_token`). |
| `priority` | `-2`…`2`, a `Priority`, or `"lowest"`, `"low"`, `"normal"`, `"high"`, `"highest"`. |
| `sound` | A `Sound`, or its name in any case. `Sound.NONE` is silent. |
| `buttons` | Up to 10 `Button(cta, url, action_required=False)`. Labels over 25 characters are cut. |
| `button_groups` | Up to 4 `ButtonGroup(name, cta, buttons)`, each with up to 10 buttons. |
| `images` | Up to 10 `Image(url=…)` or `Image.from_bytes(…)` / `Image.from_file(…)`. The first one becomes the notification banner. |
| `expiry` | Seconds until the message is hidden. |
| `acknowledge` | `True`, or an `Acknowledgement` for retries (`interval` 10–65535 s, `max_retries` 0–255) and a callback URL. |

### Check a message

```python
details = client.get_message(result.key)
print(details.is_acknowledged, details.processed_at)
```

## Async

```python
import asyncio
from justpush import AsyncJustPush

async def main():
    async with AsyncJustPush("YOUR_API_TOKEN") as client:
        await client.send("Someone rang the doorbell", title="🔔 Doorbell")

asyncio.run(main())
```

Pass `session=` to reuse your own `aiohttp.ClientSession`, for example
`async_get_clientsession(hass)` in a Home Assistant integration. The client never closes
a session it didn't create.

## Topics

```python
topic = client.create_topic("Servers", avatar_url="https://example.com/server.png")
client.update_topic(topic.uuid, title="Production servers")
client.get_topic(topic.uuid)
client.send("Disk almost full", topic_token=topic.api_token)
```

## Errors

Every error is a `JustPushError`.

| Exception | When |
| --- | --- |
| `JustPushValidationError` | The message is invalid, either caught before sending or a 422 from the API. `.errors` holds per-field messages. It's also a `ValueError`. |
| `JustPushAuthenticationError` | 401: the token is missing or wrong. |
| `JustPushForbiddenError` | 403: not allowed, e.g. a topic you don't own, or a plan limit. |
| `JustPushNotFoundError` | 404: unknown message key or topic. |
| `JustPushSubscriptionError` | 410: the subscription expired. |
| `JustPushRateLimitError` | 429: too many requests; see `.retry_after`. |
| `JustPushAPIError` | Any other error status; see `.status` and `.body`. |
| `JustPushConnectionError` | Network error or timeout (default 10 s, change with `timeout=`). |

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/mypy
```

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).
