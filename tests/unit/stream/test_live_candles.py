import json
from datetime import UTC, datetime, timedelta

from live_candles import from_redis, merge_candle, to_message, to_redis
from socket_client import Trade

TWELVE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
TWELVE_ONE = TWELVE + timedelta(minutes=1)


def trade(minute, second, price):
    """A one-share NVDA trade at 12:<minute>:<second>."""
    return Trade(
        symbol="NVDA",
        trade_ts=TWELVE + timedelta(minutes=minute, seconds=second),
        price=price,
        volume=1.0,
        conditions="",
    )


def candle(minute, open, high, low, close, volume):
    return {
        "minute": minute,
        "open": open,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


# --- merge_candle: the three cases from the design ---

def test_a_with_nothing_stored_the_candle_starts_from_the_batch():
    """Case A: no hash (or a seed that found nothing for this minute)."""
    batch = (trade(0, 10, 100.0), trade(0, 20, 108.0))

    assert merge_candle({}, batch) == [candle(TWELVE, 100.0, 108.0, 100.0, 108.0, 2.0)]


def test_b_a_batch_in_the_same_minute_updates_the_stored_candle():
    """Case B: open stays, high/low widen, close is the last trade, volume adds."""
    old = candle(TWELVE, 100.0, 108.0, 100.0, 108.0, 3.0)
    batch = (trade(0, 30, 95.0), trade(0, 40, 104.0))

    assert merge_candle(old, batch) == [candle(TWELVE, 100.0, 108.0, 95.0, 104.0, 5.0)]


def test_c_a_batch_that_crosses_a_minute_finishes_the_old_candle_then_starts_one():
    """Case C: two candles in time order. The caller publishes both and keeps
    the last one in the hash."""
    old = candle(TWELVE, 100.0, 108.0, 95.0, 104.0, 10.0)
    batch = (trade(0, 59.7, 101.0), trade(0, 59.9, 102.0), trade(1, 0.2, 103.0))

    assert merge_candle(old, batch) == [
        candle(TWELVE, 100.0, 108.0, 95.0, 102.0, 12.0),
        candle(TWELVE_ONE, 103.0, 103.0, 103.0, 103.0, 1.0),
    ]


# --- merge_candle: the details ---

def test_open_and_close_are_first_and_last_by_time_not_by_list_order():
    """Trades may arrive in any order, so the list order means nothing."""
    batch = (trade(0, 30, 105.0), trade(0, 10, 100.0), trade(0, 20, 110.0))

    [only] = merge_candle({}, batch)

    assert only["open"] == 100.0
    assert only["close"] == 105.0


def test_a_batch_that_skips_a_minute_gives_one_candle_per_minute_with_trades():
    """A stalled flush can hold trades from 12:00 and 12:02 and none from 12:01.
    No empty 12:01 candle is invented."""
    batch = (trade(0, 50, 100.0), trade(2, 5, 101.0))

    candles = merge_candle({}, batch)

    assert [c["minute"] for c in candles] == [TWELVE, TWELVE + timedelta(minutes=2)]


def test_the_stored_candle_is_not_modified():
    old = candle(TWELVE, 100.0, 108.0, 100.0, 108.0, 3.0)
    before = dict(old)

    merge_candle(old, (trade(0, 30, 95.0),))

    assert old == before


# --- to_redis / from_redis ---

def test_every_candle_value_is_stored_as_a_string():
    """Redis has no numbers or dates, only strings."""
    stored = to_redis(candle(TWELVE, 100.0, 108.0, 95.0, 104.0, 10.0))

    assert all(isinstance(value, str) for value in stored.values())


def test_a_candle_comes_back_from_redis_unchanged():
    original = candle(TWELVE, 100.0, 108.0, 95.0, 104.0, 10.0)

    assert from_redis(to_redis(original)) == original


def test_a_missing_candle_hash_reads_as_empty():
    """HGETALL on a key that does not exist returns {}."""
    assert from_redis({}) == {}


# --- to_message ---

def test_the_message_is_json_with_the_same_field_names_as_get_candles():
    """React reads history from GET /candles and live updates from these
    messages, so both use one shape."""
    message = to_message("NVDA", candle(TWELVE, 100.0, 108.0, 95.0, 104.0, 10.0))

    assert json.loads(message) == {
        "symbol": "NVDA",
        "minute": "2026-11-11T12:00:00+00:00",
        "open": 100.0,
        "high": 108.0,
        "low": 95.0,
        "close": 104.0,
        "volume": 10.0,
    }
