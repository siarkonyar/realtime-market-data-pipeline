"""user_from_token, the pure half of api/auth.py.

The session cookie holds a JWT. Both doors into the api check it with this one
function: get_current_user for HTTP requests, and /ws/candles when a socket
opens. The FastAPI side is tested through real requests in test_api_routes.py
and test_api_live_route.py.
"""
from datetime import UTC, datetime, timedelta

SECRET = "a-test-secret-that-is-long-enough-to-pass"
OTHER_SECRET = "a-different-secret-that-is-also-long-enough"
EXPIRES_IN = 3600


def token(api_tokens, secret=SECRET, now=None, role="user"):
    return api_tokens.create_token(
        secret, "ada@example.com", role, now or datetime.now(UTC), EXPIRES_IN
    )


def test_the_cookie_is_called_session(api_auth):
    """React never reads it, but nginx logs, the e2e tests and anyone opening
    the browser's dev tools see this name."""
    assert api_auth.SESSION_COOKIE == "session"


def test_a_valid_token_gives_its_user(api_auth, api_tokens):
    user = api_auth.user_from_token(SECRET, token(api_tokens, role="admin"))

    assert user == api_auth.AuthenticatedUser(email="ada@example.com", role="admin")


def test_a_missing_cookie_gives_no_user(api_auth):
    """None is what FastAPI passes when the browser sent no session cookie,
    so it has to be an ordinary input here, not a crash."""
    assert api_auth.user_from_token(SECRET, None) is None


def test_an_empty_cookie_gives_no_user(api_auth):
    """What a browser may still send for a moment after sign-out."""
    assert api_auth.user_from_token(SECRET, "") is None


def test_a_cookie_that_is_not_a_token_gives_no_user(api_auth):
    assert api_auth.user_from_token(SECRET, "not-a-token") is None


def test_a_token_signed_with_another_secret_gives_no_user(api_auth, api_tokens):
    forged = token(api_tokens, secret=OTHER_SECRET)

    assert api_auth.user_from_token(SECRET, forged) is None


def test_an_expired_token_gives_no_user(api_auth, api_tokens):
    two_hours_ago = datetime.now(UTC) - timedelta(hours=2)

    expired = token(api_tokens, now=two_hours_ago)

    assert api_auth.user_from_token(SECRET, expired) is None
