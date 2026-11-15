"""live_feed: the api's Redis side. The snapshot read and the relay that hands
every published candle to the hub. Redis is faked here; the real one is in
tests/integration/api/test_api_live_feed_redis.py.
"""
import asyncio
import json

import pytest
import redis

# Exactly what the stream's HSET leaves in candle:NVDA: every value a string.
STORED = {
    "minute": "2026-11-11T12:00:00+00:00",
    "open": "100.0",
    "high": "108.0",
    "low": "95.0",
    "close": "104.0",
    "volume": "12.0",
}


class StopRelay(Exception):
    """Ends run_relay's endless loop from inside a test."""


class RecordingHub:
    def __init__(self):
        self.delivered = []
        self.close_all_calls = 0

    def deliver(self, symbol, message):
        self.delivered.append((symbol, message))

    def close_all(self):
        self.close_all_calls += 1


class FakePubSub:
    """Hands out the scripted messages one per get_message, then raises."""

    def __init__(self, messages=(), fail_subscribe=False):
        self.messages = list(messages)
        self.fail_subscribe = fail_subscribe
        self.patterns = []
        self.is_closed = False

    async def psubscribe(self, *patterns):
        if self.fail_subscribe:
            raise redis.ConnectionError("Connection refused")
        self.patterns.extend(patterns)

    async def get_message(self, ignore_subscribe_messages=False, timeout=0.0):
        if self.messages:
            return self.messages.pop(0)
        raise redis.ConnectionError("Connection lost")

    async def aclose(self):
        self.is_closed = True


class FakeClient:
    def __init__(self, pubsub=None, stored=None):
        self._pubsub = pubsub
        self.stored = stored or {}
        self.keys_read = []
        self.is_closed = False

    def pubsub(self):
        return self._pubsub

    async def hgetall(self, key):
        self.keys_read.append(key)
        return self.stored.get(key, {})

    async def aclose(self):
        self.is_closed = True


class Connector:
    """Stands in for the connect function: each call returns the next client.
    Once they run out it raises StopRelay, so run_relay ends."""

    def __init__(self, *clients):
        self.clients = list(clients)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if not self.clients:
            raise StopRelay
        return self.clients.pop(0)


def pmessage(symbol, data):
    """What a PSUBSCRIBE connection receives for one PUBLISH."""
    return {
        "type": "pmessage",
        "pattern": "candles:*",
        "channel": f"candles:{symbol}",
        "data": data,
    }


def run_relay_until_stopped(api_live_feed, connect, hub):
    with pytest.raises(StopRelay):
        asyncio.run(api_live_feed.run_relay(connect, hub, retry_seconds=0))


# --- the snapshot ---

def test_the_symbol_is_the_channel_without_its_prefix(api_live_feed):
    assert api_live_feed.symbol_of("candles:NVDA") == "NVDA"


def test_an_empty_hash_has_no_snapshot(api_live_feed):
    assert api_live_feed.snapshot_message("NVDA", {}) is None


def test_the_snapshot_has_the_same_shape_as_a_published_candle(api_live_feed):
    """The stream's to_message sends numbers, not strings, so the snapshot must
    too: React treats both the same way."""
    snapshot = json.loads(api_live_feed.snapshot_message("NVDA", STORED))

    assert snapshot == {
        "symbol": "NVDA",
        "minute": "2026-11-11T12:00:00+00:00",
        "open": 100.0,
        "high": 108.0,
        "low": 95.0,
        "close": 104.0,
        "volume": 12.0,
    }


def test_read_snapshot_reads_the_symbols_hash(api_live_feed):
    client = FakeClient(stored={"candle:NVDA": STORED})

    snapshot = asyncio.run(api_live_feed.read_snapshot(client, "NVDA"))

    assert client.keys_read == ["candle:NVDA"]
    assert json.loads(snapshot)["close"] == 104.0


def test_read_snapshot_of_an_unknown_symbol_is_none(api_live_feed):
    snapshot = asyncio.run(api_live_feed.read_snapshot(FakeClient(), "NVDA"))

    assert snapshot is None


# --- relay: one connection, every message to the hub ---

def test_each_message_goes_to_the_hub_under_its_symbol(api_live_feed):
    hub = RecordingHub()
    pubsub = FakePubSub([pmessage("NVDA", "a"), pmessage("AAPL", "b")])

    with pytest.raises(redis.ConnectionError):
        asyncio.run(api_live_feed.relay(pubsub, hub))

    assert hub.delivered == [("NVDA", "a"), ("AAPL", "b")]


def test_a_quiet_second_delivers_nothing(api_live_feed):
    """get_message gives None when its timeout passes with nothing to read."""
    hub = RecordingHub()
    pubsub = FakePubSub([None, pmessage("NVDA", "a")])

    with pytest.raises(redis.ConnectionError):
        asyncio.run(api_live_feed.relay(pubsub, hub))

    assert hub.delivered == [("NVDA", "a")]


# --- run_relay: subscribe once, reconnect when Redis drops ---

def test_the_relay_subscribes_to_every_candle_channel(api_live_feed):
    pubsub = FakePubSub()

    run_relay_until_stopped(
        api_live_feed, Connector(FakeClient(pubsub)), RecordingHub()
    )

    assert pubsub.patterns == ["candles:*"]


def test_a_lost_connection_closes_every_reader(api_live_feed, capsys):
    """Candles published while the relay was gone are lost for good, so every
    reader reconnects for a fresh snapshot instead of showing a stale one."""
    hub = RecordingHub()

    run_relay_until_stopped(api_live_feed, Connector(FakeClient(FakePubSub())), hub)

    assert hub.close_all_calls == 1
    assert "ConnectionError" in capsys.readouterr().err


def test_a_lost_connection_is_closed_before_the_retry(api_live_feed):
    pubsub = FakePubSub()
    client = FakeClient(pubsub)
    connect = Connector(client)

    run_relay_until_stopped(api_live_feed, connect, RecordingHub())

    assert pubsub.is_closed and client.is_closed
    assert connect.calls == 2


def test_the_relay_keeps_retrying_while_redis_is_down(api_live_feed):
    refused = FakeClient(FakePubSub(fail_subscribe=True))
    lost = FakeClient(FakePubSub([pmessage("NVDA", "a")]))
    hub = RecordingHub()
    connect = Connector(refused, lost)

    run_relay_until_stopped(api_live_feed, connect, hub)

    assert connect.calls == 3
    assert hub.delivered == [("NVDA", "a")]
