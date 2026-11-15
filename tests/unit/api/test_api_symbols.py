"""GET /symbols - the symbols React can ask candles for.

They come from STOCK_SYMBOLS, the same list the stream follows, so a symbol
is listed even before its first trade has reached Postgres.
"""
import pytest
from fastapi.testclient import TestClient

SECRET = "a-test-secret-that-is-long-enough-to-pass"


@pytest.fixture(autouse=True)
def clear_overrides(api_main):
    yield
    api_main.app.dependency_overrides.clear()


def make_client(api_main, api_config, symbols="TSLA,AMZN", signed_in=True):
    overrides = api_main.app.dependency_overrides
    overrides[api_main.get_config] = lambda: api_config.load_config(
        {"JWT_SECRET": SECRET, "STOCK_SYMBOLS": symbols}
    )
    if signed_in:
        overrides[api_main.get_current_user] = lambda: api_main.AuthenticatedUser(
            email="ada@example.com", role="user"
        )

    return TestClient(api_main.app)


def test_the_configured_symbols_are_listed_in_order(api_main, api_config):
    client = make_client(api_main, api_config)

    response = client.get("/symbols")

    assert response.status_code == 200
    assert response.json() == ["TSLA", "AMZN"]


def test_the_symbols_are_listed_as_cleaned(api_main, api_config):
    client = make_client(api_main, api_config, symbols="nvda, nvda")

    assert client.get("/symbols").json() == ["NVDA"]


def test_listing_symbols_needs_a_token(api_main, api_config):
    """Like /candles: nothing in the app is readable before signing in."""
    client = make_client(api_main, api_config, signed_in=False)

    response = client.get("/symbols")

    assert response.status_code == 401
