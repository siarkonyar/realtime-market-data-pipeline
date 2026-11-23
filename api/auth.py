from dataclasses import dataclass
from functools import lru_cache

from fastapi import Cookie, Depends, HTTPException, status

from config import load_config
from tokens import TokenError, decode_token

# The cookie login sets. httpOnly, so React never reads it: the browser sends
# it with every request, and with the WebSocket handshake.
SESSION_COOKIE = "session"
ADMIN_ROLE = "admin"


@dataclass(frozen=True)
class AuthenticatedUser: # could have been dict
    email: str
    role: str


def user_from_token(secret, token):
    """The user a session cookie proves it is, or None.

    One check for both doors: get_current_user for HTTP, and /ws/candles when
    a socket opens. None covers a missing, empty, forged or expired cookie.
    """
    if not token:
        return None

    try:
        claims = decode_token(secret, token)
    except TokenError:
        return None

    # decode_token requires sub and role, so neither lookup can KeyError here.
    return AuthenticatedUser(email=claims["sub"], role=claims["role"])


@lru_cache(maxsize=1)
def get_config():
    return load_config()


def get_current_user(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    config=Depends(get_config),
):
    user = user_from_token(config.jwt_secret, session)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    return user


def require_admin(user=Depends(get_current_user)):
    if user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this action needs an admin account",
        )

    return user
