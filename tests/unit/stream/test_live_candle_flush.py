from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import redis

import main
from live_candles import merge_candle
from main import load_live_candles, save_live_candles
from socket_client import Trade

TWELVE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
TWELVE_ONE = TWELVE + timedelta(minutes=1)
ELEVEN_FIFTY_EIGHT = TWELVE - timedelta(minutes=2)


def trade(symbol, minute, second, price=100.0):
    return Trade(
        symbol=symbol,
        trade_ts=TWELVE + timedelta(minutes=minute, seconds=second),
        price=price,
        volume=1.0,
        conditions="",
    )


def stored_candle(minute):
    return {
        "minute": minute,
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 105.0,
        "volume": 10.0,
    }


def must_not_be_called(*args, **kwargs):
    raise AssertionError("called when it should not have been")


def redis_is_down(*args, **kwargs):
    raise redis.ConnectionError("Connection refused")


class FakeEngine:
    @contextmanager
    def begin(self):
        yield "connection"


class EngineThatMustNotBeUsed:
    def begin(self):
        raise AssertionError("opened a transaction")


class SeedRecorder:
    """Stands in for read_minute_candles and remembers what it was asked for."""

    def __init__(self):
        self.calls = []

    def __call__(self, connection, minute_by_symbol):
        self.calls.append(dict(minute_by_symbol))
        return {symbol: stored_candle(m) for symbol, m in minute_by_symbol.items()}


# --- load_live_candles ---

def test_an_empty_batch_touches_neither_redis_nor_postgres(monkeypatch):
    monkeypatch.setattr(main, "read_live_candles", must_not_be_called)

    assert load_live_candles("client", EngineThatMustNotBeUsed(), (), False) == {}


def test_a_reseed_skips_redis_and_seeds_each_symbol_at_its_earliest_minute(
    monkeypatch,
):
    """NVDA's batch starts in 12:00, AAPL's only trade is in 12:01, so each
    symbol is seeded for its own first minute."""
    seed = SeedRecorder()
    monkeypatch.setattr(main, "read_live_candles", must_not_be_called)
    monkeypatch.setattr(main, "read_minute_candles", seed)
    batch = (trade("NVDA", 1, 0.2), trade("NVDA", 0, 59.9), trade("AAPL", 1, 0.1))

    stored = load_live_candles("client", FakeEngine(), batch, True)

    assert seed.calls == [{"AAPL": TWELVE_ONE, "NVDA": TWELVE}]
    assert stored == {"AAPL": stored_candle(TWELVE_ONE), "NVDA": stored_candle(TWELVE)}


def test_only_missing_or_other_minute_candles_are_seeded(monkeypatch):
    """AAPL's hash is from 12:00 and its batch starts in 12:00, so it is
    trusted even though the batch crosses into 12:01 (case C)."""
    seed = SeedRecorder()
    aapls = stored_candle(TWELVE)
    monkeypatch.setattr(
        main,
        "read_live_candles",
        lambda client, symbols: {
            "AAPL": aapls,
            "NVDA": stored_candle(ELEVEN_FIFTY_EIGHT),
            "TSLA": {},
        },
    )
    monkeypatch.setattr(main, "read_minute_candles", seed)
    batch = (
        trade("AAPL", 0, 59.9),
        trade("AAPL", 1, 0.2),
        trade("NVDA", 0, 40),
        trade("TSLA", 0, 40),
    )

    stored = load_live_candles("client", FakeEngine(), batch, False)

    assert seed.calls == [{"NVDA": TWELVE, "TSLA": TWELVE}]
    assert stored["AAPL"] is aapls
    assert stored["NVDA"] == stored_candle(TWELVE)
    assert stored["TSLA"] == stored_candle(TWELVE)


def test_no_seed_query_when_every_candle_is_from_the_batch_minute(monkeypatch):
    monkeypatch.setattr(
        main,
        "read_live_candles",
        lambda client, symbols: {"AAPL": stored_candle(TWELVE)},
    )
    monkeypatch.setattr(main, "read_minute_candles", must_not_be_called)

    stored = load_live_candles(
        "client", EngineThatMustNotBeUsed(), (trade("AAPL", 0, 40),), False
    )

    assert stored == {"AAPL": stored_candle(TWELVE)}


def test_a_redis_failure_while_loading_candles_is_logged_and_skips_redis(
    monkeypatch, capsys
):
    monkeypatch.setattr(main, "read_live_candles", redis_is_down)

    stored = load_live_candles("client", FakeEngine(), (trade("AAPL", 0, 40),), False)

    assert stored is None
    assert "ConnectionError" in capsys.readouterr().err


# --- save_live_candles ---

def test_each_symbol_is_saved_as_its_merged_candles(monkeypatch):
    written = {}
    monkeypatch.setattr(
        main, "write_live_candles", lambda client, candles: written.update(candles)
    )
    aapl = (trade("AAPL", 0, 59.9, 101.0), trade("AAPL", 1, 0.2, 103.0))
    nvda = (trade("NVDA", 0, 40, 130.0),)
    stored = {"AAPL": stored_candle(TWELVE), "NVDA": {}}

    assert save_live_candles("client", stored, aapl + nvda) is True
    assert written == {
        "AAPL": merge_candle(stored_candle(TWELVE), list(aapl)),
        "NVDA": merge_candle({}, list(nvda)),
    }


def test_a_redis_failure_while_saving_candles_is_logged_and_reported(
    monkeypatch, capsys
):
    monkeypatch.setattr(main, "write_live_candles", redis_is_down)

    saved = save_live_candles(
        "client", {"AAPL": stored_candle(TWELVE)}, (trade("AAPL", 0, 40),)
    )

    assert saved is False
    assert "ConnectionError" in capsys.readouterr().err
