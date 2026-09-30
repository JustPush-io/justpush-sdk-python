"""Request bodies must match what the backend's MessageCreateRequest accepts."""

import json

import pytest

from justpush import (
    Acknowledgement,
    Button,
    ButtonGroup,
    Image,
    JustPush,
    JustPushValidationError,
    Priority,
    Sound,
)
from justpush._core import message_payload, topic_payload


def test_minimal_message():
    assert message_payload("Hi") == {"message": "Hi"}
    assert message_payload(None, title="T") == {"title": "T"}


def test_needs_message_or_title():
    with pytest.raises(JustPushValidationError):
        message_payload(None)
    with pytest.raises(JustPushValidationError):
        message_payload("", title="")


def test_full_message_uses_backend_field_names():
    body = message_payload(
        "Water detected",
        title="Leak",
        topic="Home",
        priority="highest",
        sound="SIREN",
        buttons=[Button("Open", "https://example.com", action_required=True)],
        button_groups=[ButtonGroup("Links", "More", [Button("A", "https://a.example")])],
        images=[Image(url="https://example.com/a.jpg", caption="Cam"), Image.from_bytes(b"\x89PNG")],
        expiry=60,
        acknowledge=Acknowledgement(
            retry=True, interval=30, max_retries=5,
            callback_url="https://example.com/cb", callback_params={"a": 1},
        ),
    )
    assert body == {
        "title": "Leak",
        "message": "Water detected",
        "topic": "Home",
        "priority": 2,
        "sound": "siren",
        "expiry_ttl": 60,
        "buttons": [{"cta": "Open", "url": "https://example.com", "action_required": True}],
        "button_groups": [
            {"name": "Links", "cta": "More", "action_required": False,
             "buttons": [{"cta": "A", "url": "https://a.example"}]}
        ],
        "images": [
            {"url": "https://example.com/a.jpg", "caption": "Cam"},
            {"body": "iVBORw=="},
        ],
        "requires_acknowledgement": True,
        "acknowledgement": {
            "requires_retry": True,
            "interval": 30,
            "max_retries": 5,
            "callback": {"required": True, "url": "https://example.com/cb", "params": json.dumps({"a": 1})},
        },
    }


def test_acknowledge_true_without_details():
    assert message_payload("x", acknowledge=True) == {"message": "x", "requires_acknowledgement": True}


@pytest.mark.parametrize(
    "value, expected",
    [(2, 2), (-2, -2), ("high", 1), ("LOWEST", -2), (" normal ", 0), ("-1", -1), (Priority.LOW, -1)],
)
def test_priority_parsing(value, expected):
    assert message_payload("x", priority=value)["priority"] == expected


@pytest.mark.parametrize("value", [3, -3, "loud", True, 1.5, None.__class__])
def test_bad_priority(value):
    with pytest.raises(JustPushValidationError):
        message_payload("x", priority=value)


def test_sounds():
    assert message_payload("x", sound=Sound.CASHREGISTER)["sound"] == "cashregister"
    assert message_payload("x", sound="Cosmic")["sound"] == "cosmic"
    with pytest.raises(JustPushValidationError):
        message_payload("x", sound="kazoo")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"buttons": [Button("b", "https://x")] * 11},
        {"button_groups": [ButtonGroup("g", "c", [])] * 5},
        {"button_groups": [ButtonGroup("g", "c", [Button("b", "https://x")] * 11)]},
        {"images": [Image(url="https://x")] * 11},
        {"expiry": -1},
        {"expiry": True},
        {"topic": "a", "topic_token": "b"},
        {"acknowledge": Acknowledgement(retry=True, interval=5)},
        {"acknowledge": Acknowledgement(retry=True, max_retries=256)},
    ],
)
def test_limits(kwargs):
    with pytest.raises(JustPushValidationError):
        message_payload("x", **kwargs)


def test_image_needs_exactly_one_source():
    with pytest.raises(JustPushValidationError):
        Image()
    with pytest.raises(JustPushValidationError):
        Image(url="https://x", body="abc")


def test_image_from_file(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x89PNG")
    assert Image.from_file(path).to_dict() == {"body": "iVBORw=="}


def test_topic_payloads():
    assert topic_payload("Home", required=True) == {"title": "Home"}
    assert topic_payload("Home", avatar_url="https://x/a.png", required=True) == {
        "title": "Home", "avatar": {"external_url": "https://x/a.png"}}
    assert topic_payload(None, avatar_image=b"\x89PNG", required=False) == {"avatar": {"body": "iVBORw=="}}
    for kwargs in ({"title": None, "required": True}, {"title": "x" * 101, "required": True},
                   {"title": "a", "avatar_url": "u", "avatar_image": b"i", "required": True}):
        with pytest.raises(JustPushValidationError):
            topic_payload(**kwargs)


def test_token_required():
    with pytest.raises(JustPushValidationError):
        JustPush("")
    with pytest.raises(JustPushValidationError):
        JustPush("   ")
