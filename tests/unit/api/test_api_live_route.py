"""WS /ws/candles?symbol=NVDA - the live candle, end to end inside the api.

The order on every connection:
  1. accept, then check the session cookie the browser sent with the handshake
     (a bad one is closed with 1008 AFTER accepting: a refused handshake
     reaches the browser as a bare 1006, and React could not tell "sign in
     again" from "network blip")
  2. join the hub (the mailbox starts collecting from here)
  3. read the snapshot from Redis and send it, if there is one
  4. send whatever reaches the mailbox, until either side goes away

The hub is real. The snapshot reader is a fake that can deliver candles into
the hub WHILE it is "reading", which is exactly the race step 2 exists for.
"""
import json
from datetime import UTC, datetime

import pytest
import redis
from fastapi import WebSocketDisconnect, status
from fastapi.testclient import TestClient

SECRET = "a-test-secret-that-is-long-enough-to-pass"
EXPIRES_IN = 3600
PATH = "/ws/candles?symbol=NVDA"

SNAPSHOT = json.dumps({"symbol": "NVDA", "minute": "2026-11-11T12:00:00+00:00"})
UPDATE = json.dumps({"symbol": "NVDA", "minute": "2026-11-11T12:01:00+00:00"})


@pytest.fixture(autouse=True)
def clear_overrides(api_main):
    yield
    api_main.app.dependency_overrides.clear()


class FakeSnapshots:
    """Stands in for the Redis snapshot read.

    It checks the mailbox already exists (step 2 before step 3), then drops
    `updates` into the hub as if the stream published them mid-read.
    """

    def __init__(self, hub, snapshot=SNAPSHOT, updates=(), error=None):
        self.hub = hub
        self.snapshot = snapshot
        self.updates = updates
        self.error = error
        self.symbols_read = []

    async def __call__(self, symbol):
        self.symbols_read.append(symbol)
        assert self.hub.listener_count(symbol) == 1, "read before joining the hub"
        if self.error:
            raise self.error
        for update in self.updates:
            self.hub.deliver(symbol, update)
        return self.snapshot


def make_client(api_main, api_config, api_live_hub, **snapshot_options):
    hub = api_live_hub.CandleHub()
    snapshots = FakeSnapshots(hub, **snapshot_options)
    overrides = api_main.app.dependency_overrides
    overrides[api_main.get_config] = lambda: api_config.load_config(
        {"JWT_SECRET": SECRET}
    )
    overrides[api_main.get_hub] = lambda: hub
    overrides[api_main.get_snapshot_reader] = lambda: snapshots

    return TestClient(api_main.app), hub, snapshots


def session_cookie(api_tokens, secret=SECRET):
    """The Cookie header the browser sends with the handshake, as it does on
    every request to the site once login has stored the cookie."""
    token = api_tokens.create_token(
        secret, "ada@example.com", "user", datetime.now(UTC), EXPIRES_IN
    )
    return {"Cookie": f"session={token}"}


def closed_with(websocket):
    """The close code the server sent, once it has closed the socket."""
    with pytest.raises(WebSocketDisconnect) as closed:
        websocket.receive_text()
    return closed.value.code


# --- getting in ---

BAD_COOKIE = {"Cookie": "session=not-a-token"}


def test_a_wrong_cookie_closes_the_socket(api_main, api_config, api_live_hub):
    client, _, _ = make_client(api_main, api_config, api_live_hub)

    with client.websocket_connect(PATH, headers=BAD_COOKIE) as websocket:
        assert closed_with(websocket) == status.WS_1008_POLICY_VIOLATION


def test_a_wrong_cookie_never_reaches_redis_or_the_hub(
    api_main, api_config, api_live_hub
):
    client, hub, snapshots = make_client(api_main, api_config, api_live_hub)

    with client.websocket_connect(PATH, headers=BAD_COOKIE) as websocket:
        closed_with(websocket)

    assert snapshots.symbols_read == []
    assert hub.listener_count("NVDA") == 0


def test_no_cookie_closes_the_socket(api_main, api_config, api_live_hub):
    client, _, _ = make_client(api_main, api_config, api_live_hub)

    with client.websocket_connect(PATH) as websocket:
        assert closed_with(websocket) == status.WS_1008_POLICY_VIOLATION


def test_a_token_in_the_first_message_is_no_longer_a_way_in(
    api_main, api_config, api_live_hub, api_tokens
):
    """The old way: no cookie, the token sent as a message. Cookie only now,
    so it is closed like any socket without a cookie."""
    client, _, snapshots = make_client(api_main, api_config, api_live_hub)
    token = session_cookie(api_tokens)["Cookie"].removeprefix("session=")

    with client.websocket_connect(PATH) as websocket:
        websocket.send_json({"token": token})

        assert closed_with(websocket) == status.WS_1008_POLICY_VIOLATION

    assert snapshots.symbols_read == []


def test_a_missing_symbol_is_refused(api_main, api_config, api_live_hub):
    client, _, _ = make_client(api_main, api_config, api_live_hub)

    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws/candles"):
            pass

    assert closed.value.code == status.WS_1008_POLICY_VIOLATION


def test_a_symbol_longer_than_ten_characters_is_refused(
    api_main, api_config, api_live_hub
):
    client, _, _ = make_client(api_main, api_config, api_live_hub)

    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws/candles?symbol=ABCDEFGHIJK"):
            pass

    assert closed.value.code == status.WS_1008_POLICY_VIOLATION


# --- the snapshot, then the updates ---

def test_the_snapshot_comes_before_an_update_published_during_the_read(
    api_main, api_config, api_live_hub, api_tokens
):
    """The update reached the mailbox first, yet it is sent second: an older
    snapshot must never land on top of a newer update."""
    client, _, _ = make_client(
        api_main, api_config, api_live_hub, updates=(UPDATE,)
    )

    with client.websocket_connect(
        PATH, headers=session_cookie(api_tokens)
    ) as websocket:
        assert websocket.receive_text() == SNAPSHOT
        assert websocket.receive_text() == UPDATE


def test_no_snapshot_means_the_first_message_is_an_update(
    api_main, api_config, api_live_hub, api_tokens
):
    client, _, _ = make_client(
        api_main, api_config, api_live_hub, snapshot=None, updates=(UPDATE,)
    )

    with client.websocket_connect(
        PATH, headers=session_cookie(api_tokens)
    ) as websocket:
        assert websocket.receive_text() == UPDATE


def test_the_symbol_is_upper_cased(api_main, api_config, api_live_hub, api_tokens):
    client, _, snapshots = make_client(api_main, api_config, api_live_hub)

    with client.websocket_connect(
        "/ws/candles?symbol=nvda", headers=session_cookie(api_tokens)
    ) as websocket:
        websocket.receive_text()

    assert snapshots.symbols_read == ["NVDA"]


# --- leaving ---

def test_a_reader_that_closes_leaves_the_hub(
    api_main, api_config, api_live_hub, api_tokens
):
    """A closed browser tab must not keep a mailbox in the hub until the next
    trade, which after hours can be many hours away."""
    client, hub, _ = make_client(api_main, api_config, api_live_hub)

    with client.websocket_connect(
        PATH, headers=session_cookie(api_tokens)
    ) as websocket:
        websocket.receive_text()

    assert hub.listener_count("NVDA") == 0


def test_a_full_mailbox_closes_the_socket_to_try_again(
    api_main, api_config, api_live_hub, api_tokens
):
    """101 updates before the reader could take one: too slow, so it is closed
    and React reconnects for a fresh snapshot."""
    too_many = (UPDATE,) * (api_live_hub.MAILBOX_SIZE + 1)
    client, hub, _ = make_client(
        api_main, api_config, api_live_hub, updates=too_many
    )

    with client.websocket_connect(
        PATH, headers=session_cookie(api_tokens)
    ) as websocket:
        assert websocket.receive_text() == SNAPSHOT
        assert closed_with(websocket) == status.WS_1013_TRY_AGAIN_LATER

    assert hub.listener_count("NVDA") == 0


def test_redis_down_during_the_snapshot_closes_with_a_server_error(
    api_main, api_config, api_live_hub, api_tokens
):
    client, hub, _ = make_client(
        api_main,
        api_config,
        api_live_hub,
        error=redis.ConnectionError("Connection refused"),
    )

    with client.websocket_connect(
        PATH, headers=session_cookie(api_tokens)
    ) as websocket:
        assert closed_with(websocket) == status.WS_1011_INTERNAL_ERROR

    assert hub.listener_count("NVDA") == 0
