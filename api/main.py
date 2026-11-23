import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Literal

import redis
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field, StringConstraints
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.exc import SQLAlchemyError

import db
from auth import (
    ADMIN_ROLE,
    SESSION_COOKIE,
    AuthenticatedUser,
    get_config,
    get_current_user,
    require_admin,
    user_from_token,
)
from config import ConfigError
from emails import EMAIL_PATTERN, MAX_EMAIL_LENGTH
from live_feed import read_snapshot, run_relay
from live_hub import STOP, CandleHub
from passwords import hash_password, verify_password
from serialize import alert_to_dict, candle_to_dict
from tokens import create_token

NEW_USER_ROLE = "user"


def prepare_database(connection, config):
    db.apply_schema(connection)

    if not config.admin_email or not config.admin_password:
        print("no seed admin configured", file=sys.stderr)
        return

    db.create_user(
        connection,
        email=config.admin_email.strip().lower(),
        password_hash=hash_password(config.admin_password),
        role=ADMIN_ROLE,
    )


@asynccontextmanager
async def lifespan(app):
    """Runs once per container, before the first request is served.

    The two failure modes get opposite treatment on purpose.

    ConfigError is re-raised. The container dies, compose restarts it, and the
    log says JWT_SECRET is not set. A visible crash loop is the right answer to
    a missing secret; a server that boots happily without one is worse.

    SQLAlchemyError is swallowed. Postgres blinking during boot must not take
    the process down - /health stays green and the next login reports the real
    problem, rather than the whole service disappearing over a slow database.
    """
    try:
        with _engine().begin() as connection:
            prepare_database(connection, get_config())
    except ConfigError:
        print("the api cannot start without its settings", file=sys.stderr)
        raise
    except SQLAlchemyError as error:
        print(f"could not prepare the database at startup: {error}", file=sys.stderr)

    # One Redis subscription for the whole process, after the checks above so
    # a missing JWT_SECRET never gets this far. It retries on its own while
    # Redis is down, so it never holds up the rest of the api.
    relay = asyncio.create_task(run_relay(_relay_client, get_hub()))
    relay.add_done_callback(_report_relay_end)

    try:
        yield
    finally:
        relay.cancel()
        # wait, not await relay: a relay that crashed has been reported by
        # _report_relay_end already and must not crash the shutdown too.
        await asyncio.wait({relay})


def _report_relay_end(task):
    """run_relay only ever ends by being cancelled at shutdown. Any other end
    means live candles have stopped while the rest of the api keeps going."""
    if not task.cancelled() and task.exception() is not None:
        print(f"candle relay stopped: {task.exception()!r}", file=sys.stderr)


app = FastAPI(title="ELT candles API", lifespan=lifespan)

@app.get("/health")
def health():
  return {"status": "ok"}

@lru_cache(maxsize=1)
def _engine():
  return db.get_engine()

def read_candles(symbol, hours):
  return db.read_candles(_engine(), symbol, hours)

def get_reader():
  return read_candles

@app.get("/candles")
def candles(
    symbol: str = Query(..., min_length=1, max_length=10),
    hours: int = Query(1, ge=1, le=24),
    reader=Depends(get_reader),
    #this already raises an error if the user is not authenticated
    user: AuthenticatedUser=Depends(get_current_user)
):
    return [candle_to_dict(row) for row in reader(symbol.upper(), hours)]


@app.get("/symbols")
def symbols(
    config=Depends(get_config),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """STOCK_SYMBOLS, the list the stream follows, in its order."""
    return list(config.symbols)


# ------------------------------------------------------------ live candles

# The snapshot read gives up quickly, so a hung Redis closes the socket with
# an error instead of leaving the browser waiting.
REDIS_TIMEOUT_SECONDS = 0.5

# The relay's connection is quiet for hours after the market closes. A ping
# this often notices a Redis that went away without saying goodbye.
HEALTH_CHECK_SECONDS = 30


@lru_cache(maxsize=1)
def get_hub():
    """One hub per api process, shared by the relay and every WebSocket."""
    return CandleHub()


@lru_cache(maxsize=1)
def _snapshot_client():
    return AsyncRedis.from_url(
        get_config().redis_url,
        decode_responses=True,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
    )


def _relay_client():
    """A new client for every attempt: run_relay closes the old one when it
    drops. No socket_timeout, because a quiet channel is not a broken one."""
    return AsyncRedis.from_url(
        get_config().redis_url,
        decode_responses=True,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        health_check_interval=HEALTH_CHECK_SECONDS,
    )


async def read_live_snapshot(symbol):
    return await read_snapshot(_snapshot_client(), symbol)


def get_snapshot_reader():
    return read_live_snapshot


async def _send_snapshot(websocket, symbol, snapshot_reader):
    """False when Redis could not be read; the socket is closed by then."""
    try:
        snapshot = await snapshot_reader(symbol)
    except redis.RedisError as error:
        print(
            f"live snapshot for {symbol} failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return False

    if snapshot is not None:
        await websocket.send_text(snapshot)
    return True


async def _forward(websocket, mailbox):
    """Mailbox to browser until the hub says STOP: this reader is too slow, or
    Redis dropped. Either way React reconnects for a fresh snapshot."""
    while (letter := await mailbox.get()) is not STOP:
        await websocket.send_text(letter)

    await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)


async def _wait_for_disconnect(websocket):
    """Nothing is expected from the browser after the handshake, but reading is
    the only way to hear that it left."""
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass


async def _forward_until_closed(websocket, mailbox):
    """Whichever ends first, the forwarding or the browser, ends the other."""
    tasks = {
        asyncio.create_task(_forward(websocket, mailbox)),
        asyncio.create_task(_wait_for_disconnect(websocket)),
    }

    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # Also when this endpoint is itself cancelled: no task outlives it.
        for task in tasks:
            task.cancel()
        # wait, not gather(return_exceptions=True): gather can turn a cancel of
        # this endpoint into a normal return, and the cancel is lost.
        await asyncio.wait(tasks)

    for task in done:
        task.result()  # re-raises if it failed, so the error is not lost


async def _stream_candles(websocket, hub, symbol, snapshot_reader):
    # Join before reading the snapshot: a candle published during the read
    # waits in the mailbox instead of being lost.
    mailbox = hub.join(symbol)

    try:
        if await _send_snapshot(websocket, symbol, snapshot_reader):
            await _forward_until_closed(websocket, mailbox)
    finally:
        hub.leave(symbol, mailbox)


@app.websocket("/ws/candles")
async def live_candles(
    websocket: WebSocket,
    symbol: str = Query(..., min_length=1, max_length=10),
    config=Depends(get_config),
    hub=Depends(get_hub),
    snapshot_reader=Depends(get_snapshot_reader),
):
    # Accept first, then check: a handshake refused before accept reaches the
    # browser as a bare 1006, and React could not tell "sign in again" from a
    # network blip. 1008 after accept is a close code React can act on.
    await websocket.accept()
    token = websocket.cookies.get(SESSION_COOKIE)

    try:
        if user_from_token(config.jwt_secret, token) is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await _stream_candles(websocket, hub, symbol.upper(), snapshot_reader)
    except WebSocketDisconnect:
        # The browser left. The hub was already left in _stream_candles.
        return


def read_user(email):
    with _engine().connect() as connection:
        return db.read_user(connection, email)

def get_user_reader():
    return read_user

# Trimmed and lower-cased before the pattern runs, so " Ada@Example.com " is
# accepted and stored as "ada@example.com". Postgres compares case-sensitively,
# so without the lower-casing one person could hold two accounts.
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        max_length=MAX_EMAIL_LENGTH,
        pattern=EMAIL_PATTERN,
    ),
]

class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=72)

class RegisterRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=72)

def _session_cookie_options(config):
    """Shared by login and logout. A browser only replaces or deletes a cookie
    whose name and path match, so the two must never drift apart."""
    return {
        "key": SESSION_COOKIE,
        "path": "/",
        # JavaScript cannot read it, so a script injected into the page
        # cannot steal it.
        "httponly": True,
        # Never sent on a request started by another site: the CSRF defence.
        "samesite": "strict",
        "secure": config.cookie_secure,
    }


@app.post("/auth/login")
def login(
    credentials: LoginRequest,
    response: Response,
    reader=Depends(get_user_reader),
    config=Depends(get_config),
):
    email = credentials.email
    user = reader(email)

    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="wrong email or password",
        )

    token = create_token(
        config.jwt_secret,
        email,
        user.role,
        datetime.now(UTC),
        config.token_expiry_seconds,
    )

    # The cookie lives exactly as long as the token inside it.
    response.set_cookie(
        value=token,
        max_age=config.token_expiry_seconds,
        **_session_cookie_options(config),
    )

    return {"email": email, "role": user.role}


@app.get("/auth/session")
def current_session(user: AuthenticatedUser = Depends(get_current_user)):
    """Who the cookie belongs to. React cannot read an httpOnly cookie, so it
    asks here once on page load."""
    return {"email": user.email, "role": user.role}


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, config=Depends(get_config)):
    """No sign-in needed: a broken or expired cookie is exactly the one a user
    wants gone. The token itself stays valid until it expires; only this
    browser forgets it."""
    response.delete_cookie(**_session_cookie_options(config))

def create_user(email, hashed_password, role=NEW_USER_ROLE):
    with _engine().begin() as connection:
        return db.create_user(
            connection,
            email=email,
            password_hash=hashed_password,
            role=role,
        )

def get_user_creator():
    return create_user

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(
    credentials: RegisterRequest,
    user_creator=Depends(get_user_creator),
):
    email = credentials.email
    password = credentials.password

    hashed_password = hash_password(password=password)

    user_id = user_creator(email, hashed_password, NEW_USER_ROLE)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an account with that email already exists",
        )

    return {"email": email, "role": NEW_USER_ROLE}


AlertSymbol = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_upper=True, min_length=1, max_length=10
    ),
]

class AlertRequest(BaseModel):
    symbol: AlertSymbol
    direction: Literal["above", "below"]
    threshold: float = Field(gt=0)

def create_alert(email, symbol, direction, threshold):
    with _engine().begin() as connection:
        return db.create_alert(
            connection,
            email=email,
            symbol=symbol,
            direction=direction,
            threshold=threshold,
        )

def get_alert_creator():
    return create_alert

@app.post("/alerts", status_code=status.HTTP_201_CREATED)
def add_alert(
    alert: AlertRequest,
    creator=Depends(get_alert_creator),
    user: AuthenticatedUser = Depends(get_current_user),
):
    alert_id = creator(user.email, alert.symbol, alert.direction, alert.threshold)

    # The token is valid but its account is gone - deleted after it was issued.
    if alert_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="this account no longer exists",
        )

    return {
        "alert_id": alert_id,
        "symbol": alert.symbol,
        "direction": alert.direction,
        "threshold": alert.threshold,
    }

def read_alerts(email):
    with _engine().connect() as connection:
        return db.read_alerts(connection, email)

def get_alert_reader():
    return read_alerts

@app.get("/alerts")
def list_alerts(
    reader=Depends(get_alert_reader),
    user: AuthenticatedUser = Depends(get_current_user),
):
    # None tells read_alerts not to filter by owner.
    email = None if user.role == ADMIN_ROLE else user.email
    return [alert_to_dict(row) for row in reader(email)]
    #REVIEW: ask if this is safe or not


def delete_alert(alert_id):
    with _engine().begin() as connection:
        return db.delete_alert(connection, alert_id)

def get_alert_deleter():
    return delete_alert

@app.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_alert(
    alert_id: int,
    deleter=Depends(get_alert_deleter),
    #this already raises an error if the user is not authenticated
    user: AuthenticatedUser = Depends(require_admin),
):
    if deleter(alert_id) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no such alert",
        )
