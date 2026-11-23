import dataclasses

import pytest

# Long enough to clear MIN_SECRET_LENGTH. A shorter one would raise before
# load_config ever reached the setting under test, so the test would pass
# for the wrong reason.
SECRET = "a-test-secret-that-is-long-enough-to-pass"


def test_a_missing_jwt_secret_is_rejected(api_config):
    with pytest.raises(api_config.ConfigError):
        api_config.load_config({})


def test_the_defaults_are_used_when_only_a_secret_is_given(api_config):
    config = api_config.load_config({"JWT_SECRET": SECRET})

    assert config.token_expiry_seconds == 3600
    assert config.admin_email is None
    assert config.admin_password is None


def test_values_are_read_from_the_environment(api_config):
    config = api_config.load_config(
        {
            "JWT_SECRET": SECRET,
            "JWT_EXPIRY_SECONDS": "900",
            "API_ADMIN_EMAIL": "ada@example.com",
            "API_ADMIN_PASSWORD": "a-password",
        }
    )

    assert config.jwt_secret == SECRET
    assert config.token_expiry_seconds == 900
    assert config.admin_email == "ada@example.com"
    assert config.admin_password == "a-password"


def test_a_blank_jwt_secret_is_rejected(api_config):
    """Whitespace, not "". An empty string is already falsy, so it takes the
    same branch as a missing one. Spaces are the case a naive `if not raw`
    would let straight through."""
    with pytest.raises(api_config.ConfigError):
        api_config.load_config({"JWT_SECRET": "   "})


def test_a_secret_shorter_than_thirty_two_characters_is_rejected(api_config):
    with pytest.raises(api_config.ConfigError):
        api_config.load_config({"JWT_SECRET": "too-short"})


def test_a_secret_of_exactly_thirty_two_characters_is_accepted(api_config):
    shortest_allowed = "a" * api_config.MIN_SECRET_LENGTH

    config = api_config.load_config({"JWT_SECRET": shortest_allowed})

    assert config.jwt_secret == shortest_allowed


def test_the_error_for_a_short_secret_does_not_contain_the_secret(api_config):
    """A ConfigError ends up in container logs and CI job summaries. Every
    other setting in this repo reports `got {raw!r}`; this one must not."""
    secret = "short-but-memorable"

    with pytest.raises(api_config.ConfigError) as caught:
        api_config.load_config({"JWT_SECRET": secret})

    assert secret not in str(caught.value)


def test_an_unparseable_expiry_is_rejected(api_config):
    with pytest.raises(api_config.ConfigError):
        api_config.load_config(
            {"JWT_SECRET": SECRET, "JWT_EXPIRY_SECONDS": "not-a-number"}
        )


def test_a_zero_expiry_is_rejected(api_config):
    with pytest.raises(api_config.ConfigError):
        api_config.load_config({"JWT_SECRET": SECRET, "JWT_EXPIRY_SECONDS": "0"})


def test_an_expiry_longer_than_a_day_is_rejected(api_config):
    with pytest.raises(api_config.ConfigError):
        api_config.load_config({"JWT_SECRET": SECRET, "JWT_EXPIRY_SECONDS": "86401"})


def test_an_expiry_of_exactly_a_day_is_accepted(api_config):
    longest_allowed = str(api_config.MAX_EXPIRY_SECONDS)

    config = api_config.load_config(
        {"JWT_SECRET": SECRET, "JWT_EXPIRY_SECONDS": longest_allowed}
    )

    assert config.token_expiry_seconds == api_config.MAX_EXPIRY_SECONDS


def test_an_admin_email_without_a_password_is_rejected(api_config):
    with pytest.raises(api_config.ConfigError):
        api_config.load_config(
            {"JWT_SECRET": SECRET, "API_ADMIN_EMAIL": "ada@example.com"}
        )


def test_an_admin_email_that_is_not_an_email_is_rejected(api_config):
    """Login refuses anything that is not an address, so a seeded admin named
    plain "admin" would exist and still never be able to sign in."""
    with pytest.raises(api_config.ConfigError):
        api_config.load_config(
            {
                "JWT_SECRET": SECRET,
                "API_ADMIN_EMAIL": "admin",
                "API_ADMIN_PASSWORD": "a-password",
            }
        )


def test_an_admin_password_without_an_email_is_rejected(api_config):
    """The dangerous direction: a password with nobody to belong to must not
    quietly seed an account under some default name."""
    with pytest.raises(api_config.ConfigError):
        api_config.load_config(
            {"JWT_SECRET": SECRET, "API_ADMIN_PASSWORD": "a-password"}
        )


def test_the_config_cannot_be_mutated_after_it_is_built(api_config):
    config = api_config.load_config({"JWT_SECRET": SECRET})

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.jwt_secret = "something-else-entirely"


def test_the_redis_url_defaults_to_the_compose_redis(api_config):
    config = api_config.load_config({"JWT_SECRET": SECRET})

    assert config.redis_url == "redis://redis:6379/0"


def test_the_redis_url_is_read_from_the_environment(api_config):
    config = api_config.load_config(
        {"JWT_SECRET": SECRET, "REDIS_URL": "redis://localhost:6379/15"}
    )

    assert config.redis_url == "redis://localhost:6379/15"


# --- symbols: the same rules as stream/config.py's parse_symbols ---

def test_the_default_symbols_match_the_stream(api_config):
    config = api_config.load_config({"JWT_SECRET": SECRET})

    assert config.symbols == ("AMZN", "NVDA", "GOOGL", "TSLA", "NFLX")


def test_symbols_are_read_from_the_environment(api_config):
    config = api_config.load_config(
        {"JWT_SECRET": SECRET, "STOCK_SYMBOLS": "TSLA,AMZN"}
    )

    assert config.symbols == ("TSLA", "AMZN")


def test_symbols_are_cleaned_like_the_stream_cleans_them(api_config):
    """Upper-cased, trimmed, blanks dropped, duplicates dropped, order kept."""
    config = api_config.load_config(
        {"JWT_SECRET": SECRET, "STOCK_SYMBOLS": "nvda, AMZN,, NVDA "}
    )

    assert config.symbols == ("NVDA", "AMZN")


def test_a_symbol_list_with_nothing_usable_in_it_is_rejected(api_config):
    with pytest.raises(api_config.ConfigError):
        api_config.load_config({"JWT_SECRET": SECRET, "STOCK_SYMBOLS": " , , "})


# --- COOKIE_SECURE: whether the session cookie is sent over https only ---

def test_the_session_cookie_is_https_only_by_default(api_config):
    """Safe by default: a deploy that forgets the setting still keeps the
    cookie off plain http."""
    config = api_config.load_config({"JWT_SECRET": SECRET})

    assert config.cookie_secure is True


def test_cookie_secure_can_be_turned_off_for_local_http(api_config):
    config = api_config.load_config({"JWT_SECRET": SECRET, "COOKIE_SECURE": "false"})

    assert config.cookie_secure is False


def test_cookie_secure_can_be_turned_on_explicitly(api_config):
    config = api_config.load_config({"JWT_SECRET": SECRET, "COOKIE_SECURE": "true"})

    assert config.cookie_secure is True


def test_cookie_secure_is_read_whatever_its_case(api_config):
    config = api_config.load_config({"JWT_SECRET": SECRET, "COOKIE_SECURE": " False "})

    assert config.cookie_secure is False


def test_a_cookie_secure_that_is_not_true_or_false_is_rejected(api_config):
    """"yes" or "0" could mean either to whoever wrote it, so the api refuses
    to guess and stops at startup instead."""
    with pytest.raises(api_config.ConfigError):
        api_config.load_config({"JWT_SECRET": SECRET, "COOKIE_SECURE": "yes"})
