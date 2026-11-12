import json

from auth import AuthenticatedUser
from tokens import TokenError, decode_token


def _token_of(text):
    """The token in {"token": "..."}, or None for anything else.

    The text comes straight from the browser, so every step is checked: it
    may not be JSON, may not be an object, and its token may not be text.
    """
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(body, dict):
        return None

    token = body.get("token")
    return token if isinstance(token, str) and token else None


def user_from_auth_message(secret, text):
    """The user a WebSocket's first message proves it is, or None.

    The same check get_current_user does for a header: a browser's WebSocket
    cannot send headers, so the token arrives as a message instead.
    """
    token = _token_of(text)
    if token is None:
        return None

    try:
        claims = decode_token(secret, token)
    except TokenError:
        return None

    # decode_token requires sub and role, so neither lookup can KeyError here.
    return AuthenticatedUser(email=claims["sub"], role=claims["role"])
