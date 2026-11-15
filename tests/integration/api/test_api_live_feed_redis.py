"""live_feed against a real Redis: the snapshot reads what the stream's HSET
wrote, and the relay hears what the stream's PUBLISH sent.
"""
import asyncio
import contextlib
import json

import redis.asyncio

# Pub/Sub ignores the database number, and a running dev stream publishes
# real symbols on the same server. No feed trades this one.
SYMBOL = "ZZTEST"
CHANNEL = f"candles:{SYMBOL}"

STORED = {
    "minute": "2026-11-11T12:00:00+00:00",
    "open": "100.0",
    "high": "108.0",
    "low": "95.0",
    "close": "104.0",
    "volume": "12.0",
}

DELIVERY_TIMEOUT_SECONDS = 3.0
REPUBLISH_EVERY_SECONDS = 0.1


def connector(redis_url):
    return lambda: redis.asyncio.Redis.from_url(redis_url, decode_responses=True)


async def read_snapshot(api_live_feed, redis_url):
    client = connector(redis_url)()
    try:
        return await api_live_feed.read_snapshot(client, SYMBOL)
    finally:
        await client.aclose()


async def publish_until_delivered(redis_client, mailbox, message):
    """The relay subscribes in the background, and a PUBLISH sent before that
    is lost. So keep publishing until one arrives."""
    while True:
        redis_client.publish(CHANNEL, message)
        try:
            return await asyncio.wait_for(mailbox.get(), REPUBLISH_EVERY_SECONDS)
        except TimeoutError:
            continue


async def relay_one_message(api_live_feed, api_live_hub, redis_client, redis_url):
    hub = api_live_hub.CandleHub()
    mailbox = hub.join(SYMBOL)
    relay = asyncio.create_task(
        api_live_feed.run_relay(connector(redis_url), hub, retry_seconds=0.1)
    )

    try:
        return await asyncio.wait_for(
            publish_until_delivered(redis_client, mailbox, "a-candle"),
            DELIVERY_TIMEOUT_SECONDS,
        )
    finally:
        relay.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay


def test_the_snapshot_is_the_hash_the_stream_wrote(
    api_live_feed, redis_client, redis_url
):
    redis_client.hset(f"candle:{SYMBOL}", mapping=STORED)

    snapshot = asyncio.run(read_snapshot(api_live_feed, redis_url))

    assert json.loads(snapshot) == {
        "symbol": SYMBOL,
        "minute": "2026-11-11T12:00:00+00:00",
        "open": 100.0,
        "high": 108.0,
        "low": 95.0,
        "close": 104.0,
        "volume": 12.0,
    }


def test_a_symbol_with_no_hash_has_no_snapshot(
    api_live_feed, redis_client, redis_url
):
    assert asyncio.run(read_snapshot(api_live_feed, redis_url)) is None


def test_the_relay_hands_a_published_candle_to_the_hub(
    api_live_feed, api_live_hub, redis_client, redis_url
):
    delivered = asyncio.run(
        relay_one_message(api_live_feed, api_live_hub, redis_client, redis_url)
    )

    assert delivered == "a-candle"
