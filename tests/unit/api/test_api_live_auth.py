"""The first WebSocket message carries the token: {"token": "..."}.

A browser's WebSocket cannot send an Authorization header, and a token in
the URL ends up in access logs, so the token arrives as a message instead.
"""
import json
from datetime import UTC, datetime, timedelta

SECRET = "a-test-secret-that-is-long-enough-to-pass"
OTHER_SECRET = "a-different-secret-that-is-also-long-enough"
EXPIRES_IN = 3600


def token(api_tokens, secret=SECRET, now=None):
    return api_tokens.create_token(
        secret, "ada@example.com", "user", now or datetime.now(UTC), EXPIRES_IN
    )


def message(value):
    return json.dumps({"token": value})


def test_a_valid_token_gives_its_user(api_live_auth, api_tokens, api_auth):
    user = api_live_auth.user_from_auth_message(SECRET, message(token(api_tokens)))

    assert user == api_auth.AuthenticatedUser(email="ada@example.com", role="user")


def test_text_that_is_not_json_is_refused(api_live_auth):
    assert api_live_auth.user_from_auth_message(SECRET, "hello") is None


def test_json_that_is_not_an_object_is_refused(api_live_auth):
    assert api_live_auth.user_from_auth_message(SECRET, '["a", "b"]') is None


def test_an_object_without_a_token_is_refused(api_live_auth):
    assert api_live_auth.user_from_auth_message(SECRET, '{"symbol": "NVDA"}') is None


def test_a_token_that_is_not_text_is_refused(api_live_auth):
    assert api_live_auth.user_from_auth_message(SECRET, message(123)) is None


def test_a_token_signed_with_another_secret_is_refused(api_live_auth, api_tokens):
    forged = token(api_tokens, secret=OTHER_SECRET)

    assert api_live_auth.user_from_auth_message(SECRET, message(forged)) is None


def test_an_expired_token_is_refused(api_live_auth, api_tokens):
    two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
    expired = token(api_tokens, now=two_hours_ago)

    assert api_live_auth.user_from_auth_message(SECRET, message(expired)) is None
