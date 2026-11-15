"""CandleHub: one mailbox per WebSocket, filled by the Redis relay.

asyncio.Queue's put_nowait and get_nowait need no running event loop, so
these tests stay synchronous.
"""


def drain(mailbox):
    """Everything waiting in a mailbox, oldest first. Empties it."""
    letters = []
    while not mailbox.empty():
        letters.append(mailbox.get_nowait())
    return letters


def test_a_new_mailbox_starts_empty(api_live_hub):
    hub = api_live_hub.CandleHub()

    mailbox = hub.join("NVDA")

    assert mailbox.empty()
    assert hub.listener_count("NVDA") == 1


def test_a_message_reaches_every_mailbox_of_its_symbol(api_live_hub):
    hub = api_live_hub.CandleHub()
    first = hub.join("NVDA")
    second = hub.join("NVDA")

    hub.deliver("NVDA", "candle-1")

    assert drain(first) == ["candle-1"]
    assert drain(second) == ["candle-1"]


def test_a_message_does_not_reach_other_symbols(api_live_hub):
    hub = api_live_hub.CandleHub()
    aapl = hub.join("AAPL")

    hub.deliver("NVDA", "candle-1")

    assert aapl.empty()


def test_messages_keep_their_order(api_live_hub):
    hub = api_live_hub.CandleHub()
    mailbox = hub.join("NVDA")

    hub.deliver("NVDA", "12:00")
    hub.deliver("NVDA", "12:01")

    assert drain(mailbox) == ["12:00", "12:01"]


def test_a_symbol_nobody_listens_to_is_ignored(api_live_hub):
    hub = api_live_hub.CandleHub()

    hub.deliver("NVDA", "candle-1")

    assert hub.listener_count("NVDA") == 0


def test_a_mailbox_that_left_gets_nothing(api_live_hub):
    hub = api_live_hub.CandleHub()
    mailbox = hub.join("NVDA")

    hub.leave("NVDA", mailbox)
    hub.deliver("NVDA", "candle-1")

    assert mailbox.empty()
    assert hub.listener_count("NVDA") == 0


def test_leaving_twice_is_harmless(api_live_hub):
    """close_all already removed it, then the WebSocket's own cleanup leaves."""
    hub = api_live_hub.CandleHub()
    mailbox = hub.join("NVDA")

    hub.close_all()
    hub.leave("NVDA", mailbox)

    assert hub.listener_count("NVDA") == 0


def test_a_full_mailbox_is_told_to_stop_and_dropped(api_live_hub):
    """The 101st letter for a slow reader: its mailbox is emptied down to a
    single STOP, so it closes at once instead of sending 100 stale candles."""
    hub = api_live_hub.CandleHub()
    slow = hub.join("NVDA")
    fast = hub.join("NVDA")

    for number in range(api_live_hub.MAILBOX_SIZE):
        hub.deliver("NVDA", f"candle-{number}")
        drain(fast)
    hub.deliver("NVDA", "one-too-many")

    assert drain(slow) == [api_live_hub.STOP]
    assert hub.listener_count("NVDA") == 1


def test_a_full_mailbox_does_not_hold_up_the_others(api_live_hub):
    hub = api_live_hub.CandleHub()
    slow = hub.join("NVDA")
    fast = hub.join("NVDA")

    for number in range(api_live_hub.MAILBOX_SIZE):
        hub.deliver("NVDA", f"candle-{number}")
        drain(fast)
    hub.deliver("NVDA", "one-too-many")

    assert drain(fast) == ["one-too-many"]
    assert slow.full() is False


def test_close_all_stops_every_mailbox_and_empties_the_hub(api_live_hub):
    """Redis dropped: every reader may have missed candles, so each one is
    closed and reconnects for a fresh snapshot."""
    hub = api_live_hub.CandleHub()
    nvda = hub.join("NVDA")
    aapl = hub.join("AAPL")
    hub.deliver("NVDA", "candle-1")

    hub.close_all()

    assert drain(nvda) == [api_live_hub.STOP]
    assert drain(aapl) == [api_live_hub.STOP]
    assert hub.listener_count("NVDA") == 0
    assert hub.listener_count("AAPL") == 0
