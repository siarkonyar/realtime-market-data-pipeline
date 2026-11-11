import json
from datetime import datetime
from itertools import groupby

KEY_PREFIX = "candle:"
CHANNEL_PREFIX = "candles:"

# Redis stores only strings. Each stored field and how to read it back.
PARSERS = {
    "minute": datetime.fromisoformat,
    "open": float,
    "high": float,
    "low": float,
    "close": float,
    "volume": float,
}


def minute_of(moment):
    """12:00:59.9 -> 12:00:00. The minute a trade's candle belongs to."""
    return moment.replace(second=0, microsecond=0)


def _candle(minute, trades, old):
    """One minute's candle. trades are that minute's, already in time order;
    old is the stored candle for the same minute, or empty."""
    prices = [trade.price for trade in trades]
    volume = sum(trade.volume for trade in trades)

    if not old:
        return {
            "minute": minute,
            "open": trades[0].price,
            "high": max(prices),
            "low": min(prices),
            "close": trades[-1].price,
            "volume": volume,
        }

    return {
        "minute": minute,
        "open": old["open"],
        "high": max(old["high"], *prices),
        "low": min(old["low"], *prices),
        "close": trades[-1].price,
        "volume": old["volume"] + volume,
    }


def merge_candle(old, trades):
    """One symbol's stored candle plus a batch of its trades -> new candles.

    Returns one candle per minute that has trades, in time order. The last
    one is the current minute; any before it are finished.

    old is empty, or the candle for the batch's earliest minute: the caller
    seeds it from Postgres otherwise. trades is never empty and may arrive in
    any order. Returns new dicts; old is left untouched.
    """
    ordered = sorted(trades, key=lambda trade: trade.trade_ts)
    by_minute = [
        (minute, list(group))
        for minute, group in groupby(ordered, key=lambda t: minute_of(t.trade_ts))
    ]

    first_minute, first_trades = by_minute[0]
    return [_candle(first_minute, first_trades, old)] + [
        _candle(minute, minute_trades, {}) for minute, minute_trades in by_minute[1:]
    ]


def to_redis(candle):
    return {
        field: value.isoformat() if isinstance(value, datetime) else str(value)
        for field, value in candle.items()
    }


def from_redis(raw):
    return {field: PARSERS[field](text) for field, text in raw.items()}


def to_message(symbol, candle):
    """The JSON the api forwards to React. Same field names as GET /candles."""
    return json.dumps(
        {"symbol": symbol, **candle, "minute": candle["minute"].isoformat()}
    )


def _key(symbol):
    return f"{KEY_PREFIX}{symbol}"


def _channel(symbol):
    return f"{CHANNEL_PREFIX}{symbol}"


def read_live_candles(client, symbols):
    """symbol -> stored candle, {} where nothing is stored. One round trip."""
    pipe = client.pipeline()
    for symbol in symbols:
        pipe.hgetall(_key(symbol))

    return {
        symbol: from_redis(raw)
        for symbol, raw in zip(symbols, pipe.execute(), strict=True)
    }


def write_live_candles(client, candles_by_symbol):
    """The newest candle into each hash, then every candle published in time
    order. One round trip for every symbol in the batch."""
    pipe = client.pipeline()
    for symbol, candles in candles_by_symbol.items():
        pipe.hset(_key(symbol), mapping=to_redis(candles[-1]))
        for candle in candles:
            pipe.publish(_channel(symbol), to_message(symbol, candle))
    pipe.execute()
