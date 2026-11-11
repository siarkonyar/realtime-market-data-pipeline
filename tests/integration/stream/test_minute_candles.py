from datetime import UTC, datetime, timedelta

from db import read_minute_candles
from socket_client import Trade
from writer import insert_trades

TWELVE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
TWELVE_ONE = TWELVE + timedelta(minutes=1)


def make_trade(symbol, when, price, volume=1.0):
    return Trade(
        symbol=symbol, trade_ts=when, price=price, volume=volume, conditions=""
    )


def test_one_minute_of_trades_becomes_one_candle(stream_db):
    insert_trades(stream_db, (
        # Inserted out of time order: open and close are first and last by time.
        make_trade("NVDA", TWELVE + timedelta(seconds=40), 104.0, 4.0),
        make_trade("NVDA", TWELVE + timedelta(seconds=10), 100.0, 1.0),
        make_trade("NVDA", TWELVE + timedelta(seconds=30), 95.0, 3.0),
        make_trade("NVDA", TWELVE + timedelta(seconds=20), 108.0, 2.0),
    ))

    candles = read_minute_candles(stream_db, {"NVDA": TWELVE})

    assert candles["NVDA"] == {
        "minute": TWELVE,
        "open": 100.0,
        "high": 108.0,
        "low": 95.0,
        "close": 104.0,
        "volume": 10.0,
    }


def test_a_symbol_with_no_trades_in_that_minute_gets_nothing(stream_db):
    insert_trades(stream_db, (make_trade("AAPL", TWELVE, 230.0),))

    candles = read_minute_candles(stream_db, {"AAPL": TWELVE, "NVDA": TWELVE})

    assert candles["NVDA"] == {}


def test_only_trades_inside_the_minute_count(stream_db):
    insert_trades(stream_db, (
        make_trade("NVDA", TWELVE - timedelta(microseconds=1), 999.0),
        make_trade("NVDA", TWELVE, 100.0),
        make_trade("NVDA", TWELVE_ONE, 1.0),
    ))

    candles = read_minute_candles(stream_db, {"NVDA": TWELVE})

    assert candles["NVDA"]["volume"] == 1.0
    assert candles["NVDA"]["open"] == 100.0
    assert candles["NVDA"]["close"] == 100.0


def test_each_symbol_is_read_for_its_own_minute(stream_db):
    """One call can ask AAPL for 12:00 and NVDA for 12:01. NVDA's 12:00
    trade must not leak into its 12:01 candle."""
    insert_trades(stream_db, (
        make_trade("AAPL", TWELVE + timedelta(seconds=30), 230.0),
        make_trade("NVDA", TWELVE + timedelta(seconds=30), 999.0),
        make_trade("NVDA", TWELVE_ONE + timedelta(seconds=5), 130.0),
    ))

    candles = read_minute_candles(stream_db, {"AAPL": TWELVE, "NVDA": TWELVE_ONE})

    assert candles["AAPL"]["minute"] == TWELVE
    assert candles["AAPL"]["close"] == 230.0
    assert candles["NVDA"]["minute"] == TWELVE_ONE
    assert candles["NVDA"]["high"] == 130.0
