import asyncio
import json
import sys

import redis

# The names the stream writes under: the hash is the current candle, the
# channel is where every change of it is published.
KEY_PREFIX = "candle:"
CHANNEL_PREFIX = "candles:"
CHANNEL_PATTERN = f"{CHANNEL_PREFIX}*"

# The hash keeps every value as a string. These go back to numbers so the
# snapshot looks exactly like a published candle.
NUMBER_FIELDS = ("open", "high", "low", "close", "volume")

# How long one get_message waits for a letter. Short, so the client gets a
# turn between waits to ping Redis and notice a dead connection.
LISTEN_TIMEOUT_SECONDS = 1.0

# The pause before reconnecting, so a Redis that is down is not hammered.
RETRY_SECONDS = 1.0


def symbol_of(channel):
    """candles:NVDA -> NVDA"""
    return channel.removeprefix(CHANNEL_PREFIX)


def snapshot_message(symbol, raw):
    """The stored hash as the same JSON the stream publishes. None if empty."""
    if not raw:
        return None

    numbers = {field: float(raw[field]) for field in NUMBER_FIELDS}
    return json.dumps({"symbol": symbol, "minute": raw["minute"], **numbers})


async def read_snapshot(client, symbol):
    return snapshot_message(symbol, await client.hgetall(f"{KEY_PREFIX}{symbol}"))


async def relay(pubsub, hub):
    """Hands every published candle to the hub. Returns only by raising."""
    while True:
        message = await pubsub.get_message(
            ignore_subscribe_messages=True, timeout=LISTEN_TIMEOUT_SECONDS
        )
        # None: the timeout passed with nothing published.
        if message is not None:
            hub.deliver(symbol_of(message["channel"]), message["data"])


async def run_relay(connect, hub, retry_seconds=RETRY_SECONDS):
    """One subscription for the whole api, kept alive for as long as it runs.

    connect() returns a new redis.asyncio client with decode_responses=True.
    Ends only when cancelled, at api shutdown.
    """
    while True:
        client = connect()
        pubsub = client.pubsub()

        try:
            await pubsub.psubscribe(CHANNEL_PATTERN)
            await relay(pubsub, hub)
        except redis.RedisError as error:
            print(
                f"candle relay lost Redis: {type(error).__name__}: {error}",
                file=sys.stderr,
            )
            # Whatever was published while we were gone is lost for good, so
            # every reader reconnects for a fresh snapshot.
            hub.close_all()
        finally:
            await pubsub.aclose()
            await client.aclose()

        await asyncio.sleep(retry_seconds)
