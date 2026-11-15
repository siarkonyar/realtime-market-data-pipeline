import json
from datetime import UTC, datetime, timedelta

import pytest

from live_candles import read_live_candles, write_live_candles

TWELVE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
TWELVE_ONE = TWELVE + timedelta(minutes=1)

# Pub/Sub ignores the database number: a channel is shared by every database
# on the server. The test Redis is the compose Redis, so a running dev stream
# could publish to candles:NVDA in the middle of a test. No real feed trades
# this symbol, so nothing else ever talks on its channel.
SYMBOL = "ZZTEST"
CHANNEL = f"candles:{SYMBOL}"

MESSAGE_TIMEOUT_SECONDS = 1.0


def candle(minute, close):
    return {
        "minute": minute,
        "open": 100.0,
        "high": 108.0,
        "low": 95.0,
        "close": close,
        "volume": 12.0,
    }


@pytest.fixture
def listener(redis_client):
    """Subscribed before the test publishes anything: a message sent with
    nobody listening is gone."""
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(CHANNEL)
    # Reads Redis's "you are subscribed" reply, so the subscription is live
    # before the test goes on.
    pubsub.get_message(timeout=MESSAGE_TIMEOUT_SECONDS)
    yield pubsub
    pubsub.close()


def next_message(pubsub):
    message = pubsub.get_message(timeout=MESSAGE_TIMEOUT_SECONDS)
    assert message is not None, f"nothing arrived on {CHANNEL}"
    return json.loads(message["data"])


def test_the_hash_keeps_the_newest_candle(redis_client):
    write_live_candles(
        redis_client, {SYMBOL: [candle(TWELVE, 102.0), candle(TWELVE_ONE, 103.0)]}
    )

    assert read_live_candles(redis_client, [SYMBOL]) == {
        SYMBOL: candle(TWELVE_ONE, 103.0)
    }


def test_a_symbol_never_written_reads_as_empty(redis_client):
    assert read_live_candles(redis_client, [SYMBOL]) == {SYMBOL: {}}


def test_the_hash_lives_at_candle_symbol(redis_client):
    write_live_candles(redis_client, {SYMBOL: [candle(TWELVE, 102.0)]})

    assert redis_client.hget(f"candle:{SYMBOL}", "close") == "102.0"
    assert redis_client.hget(f"candle:{SYMBOL}", "minute") == TWELVE.isoformat()


def test_every_candle_is_published_in_time_order(redis_client, listener):
    """Case C: the finished 12:00 candle first, then the new 12:01 one."""
    write_live_candles(
        redis_client, {SYMBOL: [candle(TWELVE, 102.0), candle(TWELVE_ONE, 103.0)]}
    )

    first = next_message(listener)
    second = next_message(listener)

    assert (first["minute"], first["close"]) == (TWELVE.isoformat(), 102.0)
    assert (second["minute"], second["close"]) == (TWELVE_ONE.isoformat(), 103.0)
    assert first["symbol"] == SYMBOL
