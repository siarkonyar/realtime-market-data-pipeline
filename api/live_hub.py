import asyncio

# How far a reader may fall behind before it is closed. A candle changes about
# once a second, so 100 waiting letters means it is well over a minute behind.
MAILBOX_SIZE = 100

# Never a real letter: every candle message is a JSON string.
STOP = None


def _stop(mailbox):
    """Throws away what is waiting, so STOP is the very next letter."""
    while not mailbox.empty():
        mailbox.get_nowait()
    mailbox.put_nowait(STOP)


class CandleHub:
    """symbol -> the mailboxes of every WebSocket watching it.

    Everything here runs on the api's one event loop and nothing awaits, so
    no other task can run halfway through a method: no lock is needed.
    """

    def __init__(self):
        self._mailboxes = {}

    def listener_count(self, symbol):
        return len(self._mailboxes.get(symbol, ()))

    def join(self, symbol):
        mailbox = asyncio.Queue(maxsize=MAILBOX_SIZE)
        watching = self._mailboxes.get(symbol, frozenset())
        self._mailboxes = {**self._mailboxes, symbol: watching | {mailbox}}
        return mailbox

    def leave(self, symbol, mailbox):
        """Safe to call for a mailbox the hub already dropped."""
        remaining = self._mailboxes.get(symbol, frozenset()) - {mailbox}
        others = {s: boxes for s, boxes in self._mailboxes.items() if s != symbol}
        self._mailboxes = {**others, symbol: remaining} if remaining else others

    def deliver(self, symbol, message):
        """One letter into every mailbox of the symbol. Never waits: a full
        mailbox is told to stop and dropped, the others carry on."""
        for mailbox in self._mailboxes.get(symbol, ()):
            try:
                mailbox.put_nowait(message)
            except asyncio.QueueFull:
                self.leave(symbol, mailbox)
                _stop(mailbox)

    def close_all(self):
        """Every reader is told to stop, and the hub starts empty."""
        everyone = [box for boxes in self._mailboxes.values() for box in boxes]
        self._mailboxes = {}
        for mailbox in everyone:
            _stop(mailbox)
