"""Send a push notification. Run: JUSTPUSH_TOKEN=... python examples/send_message.py"""

import os

from justpush import Button, JustPush, Priority

client = JustPush(os.environ["JUSTPUSH_TOKEN"])
result = client.send(
    "Sent from the JustPush Python SDK",
    title="Hello 👋",
    priority=Priority.NORMAL,
    buttons=[Button("Open JustPush", "https://justpush.io")],
)
print(f"Queued {result.key}, {result.rate_limit.remaining} messages left this month")
