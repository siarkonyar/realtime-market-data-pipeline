import os
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# price_alerts is created by the api, not by schema.sql here. Only the api can
# create alerts, so until it has started there is nothing to wait for anyway.
PENDING_ALERTS_SQL = text(
    """
    SELECT alert_id, symbol, direction, threshold
      FROM price_alerts
     WHERE triggered_at IS NULL
    """
)

# Seeds a live price in Redis. A range on trade_ts rather than a cast to a
# date, so the (symbol, trade_ts) index can serve it.
DAY_STATS_SQL = text(
    """
    SELECT symbol,
           count(*)                                AS trades_today,
           (array_agg(price ORDER BY trade_ts))[1] AS day_open,
           max(price)                              AS day_high,
           min(price)                              AS day_low
      FROM raw_trades
     WHERE symbol = ANY(:symbols)
       AND trade_ts >= :day_start
       AND trade_ts <  :day_end
     GROUP BY symbol
    """
)

# Seeds a live candle in Redis. unnest turns the two lists into rows of
# (symbol, minute_start), so one query serves every symbol, each at its own
# minute. Ranges on trade_ts again, for the (symbol, trade_ts) index.
MINUTE_CANDLES_SQL = text(
    """
    SELECT wanted.symbol,
           (array_agg(t.price ORDER BY t.trade_ts))[1]      AS open,
           max(t.price)                                     AS high,
           min(t.price)                                     AS low,
           (array_agg(t.price ORDER BY t.trade_ts DESC))[1] AS close,
           coalesce(sum(t.volume), 0)                       AS volume
      FROM unnest(CAST(:symbols AS text[]), CAST(:minutes AS timestamptz[]))
               AS wanted(symbol, minute_start)
      JOIN raw_trades AS t
        ON t.symbol = wanted.symbol
       AND t.trade_ts >= wanted.minute_start
       AND t.trade_ts <  wanted.minute_start + interval '1 minute'
     GROUP BY wanted.symbol
    """
)


def get_engine(env=None):
    env = os.environ if env is None else env

    host = env.get("DESTINATION_POSTGRES_HOST", "destination_postgres")
    port = env.get("DESTINATION_POSTGRES_PORT", "5432")
    db_name = env.get("DESTINATION_POSTGRES_DB", "destination_db")
    user = env.get("DESTINATION_POSTGRES_USER", "postgres")
    password = env.get("DESTINATION_POSTGRES_PASSWORD")

    if not password:
        raise RuntimeError(
            "DESTINATION_POSTGRES_PASSWORD is not set. "
            "Check that docker-compose.yaml passes ./.env to the stream service."
        )

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
    return create_engine(url)


def apply_schema(connection, schema_path=SCHEMA_PATH):
    """Run the CREATE TABLE IF NOT EXISTS statements in schema.sql."""
    connection.exec_driver_sql(schema_path.read_text(encoding="utf-8"))


def read_pending_alerts(connection):
    return connection.execute(PENDING_ALERTS_SQL).all()


def read_day_stats(connection, symbols, day):
    """symbol -> its stats for one UTC day, {} for a symbol with no trades."""
    day_start = datetime.combine(day, time(), tzinfo=UTC)
    rows = connection.execute(
        DAY_STATS_SQL,
        {
            "symbols": list(symbols),
            "day_start": day_start,
            "day_end": day_start + timedelta(days=1),
        },
    ).mappings()

    found = {
        row["symbol"]: {
            "day": day,
            "day_open": float(row["day_open"]),
            "day_high": float(row["day_high"]),
            "day_low": float(row["day_low"]),
            "trades_today": row["trades_today"],
        }
        for row in rows
    }
    return {symbol: found.get(symbol, {}) for symbol in symbols}


def read_minute_candles(connection, minute_by_symbol):
    """symbol -> its candle for the minute asked, {} for a symbol with no
    trades in that minute. Each symbol may ask for a different minute."""
    symbols = list(minute_by_symbol)
    rows = connection.execute(
        MINUTE_CANDLES_SQL,
        {"symbols": symbols, "minutes": [minute_by_symbol[s] for s in symbols]},
    ).mappings()

    found = {
        row["symbol"]: {
            "minute": minute_by_symbol[row["symbol"]],
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        for row in rows
    }
    return {symbol: found.get(symbol, {}) for symbol in symbols}
