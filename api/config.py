import os
from dataclasses import dataclass

from emails import is_email

DEFAULTS = {
    "JWT_EXPIRY_SECONDS": "3600",
    # The compose Redis, the same default the stream uses.
    "REDIS_URL": "redis://redis:6379/0",
    # The stream's default too: the api lists exactly what the stream follows.
    "STOCK_SYMBOLS": "AMZN,NVDA,GOOGL,TSLA,NFLX",
    # Safe by default: a deploy that forgets the setting keeps the session
    # cookie off plain http. Local http turns it off in .env.
    "COOKIE_SECURE": "true",
}

FLAG_VALUES = {"true": True, "false": False}

# HS256 signatures are only as strong as the key behind them, and a short key
# is a guessable key. 32 is what `openssl rand -hex 32` produces.
MIN_SECRET_LENGTH = 32

# A stateless token cannot be revoked, so its lifetime is also the longest a
# demoted admin keeps the old powers. A day is already generous.
MAX_EXPIRY_SECONDS = 86400


class ConfigError(RuntimeError):
    """Raised when a setting is missing, unparseable, or out of range."""


def parse_symbols(raw):
    """"amzn, NVDA,, NVDA " -> ("AMZN", "NVDA")

    A copy of stream/config.py's rules. The services share no code, and the
    two must agree, or React asks for candles the stream never wrote.
    """
    cleaned = [piece.strip().upper() for piece in raw.split(",")]
    symbols = tuple(dict.fromkeys(piece for piece in cleaned if piece))

    if not symbols:
        raise ConfigError(f"STOCK_SYMBOLS has no usable symbols in it: {raw!r}")

    return symbols


@dataclass(frozen=True)
class ApiConfig:
    jwt_secret: str
    token_expiry_seconds: int
    admin_email: str | None
    admin_password: str | None
    redis_url: str
    symbols: tuple
    cookie_secure: bool


def _read_number(env, name, parse):
    raw = env.get(name) or DEFAULTS[name]
    try:
        return parse(raw)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from error


def _read_flag(env, name):
    """Only true or false. "yes" or "0" could mean either to whoever wrote
    it, so the api refuses to guess."""
    raw = env.get(name) or DEFAULTS[name]
    flag = FLAG_VALUES.get(raw.strip().lower())

    if flag is None:
        raise ConfigError(f"{name} must be true or false, got {raw!r}")

    return flag


def _read_secret(env):
    # Stripped, because a trailing newline in .env would otherwise become part
    # of the signing key, and every token would break the next time someone
    # retyped the file.
    raw = (env.get("JWT_SECRET") or "").strip()

    if not raw:
        raise ConfigError(
            "JWT_SECRET is not set. Generate one with `openssl rand -hex 32` "
            "and put it in .env."
        )

    # Reports the length, never the value. Every other setting in this repo
    # ends its error with `got {raw!r}`, but this one reaches container logs
    # and CI job summaries, and the secret is the whole of the security.
    if len(raw) < MIN_SECRET_LENGTH:
        raise ConfigError(
            f"JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters, "
            f"got {len(raw)}."
        )

    return raw


def _read_admin(env):
    """Both or neither.

    A password with no email would otherwise seed an account under some
    invented default name, which is how installations end up with credentials
    nobody chose. Unset is a valid answer: it means seed no admin at all.
    """
    # The password is not stripped - spaces can be part of one.
    email = (env.get("API_ADMIN_EMAIL") or "").strip() or None
    password = env.get("API_ADMIN_PASSWORD") or None

    if email and not password:
        raise ConfigError(
            "API_ADMIN_EMAIL is set but API_ADMIN_PASSWORD is not. Set both "
            "to seed an admin, or neither to seed none."
        )

    if password and not email:
        raise ConfigError(
            "API_ADMIN_PASSWORD is set but API_ADMIN_EMAIL is not. Set both "
            "to seed an admin, or neither to seed none."
        )

    # Login refuses anything that is not an address, so an admin seeded under
    # one would exist and still never be able to sign in.
    if email and not is_email(email):
        raise ConfigError(f"API_ADMIN_EMAIL must be an email address, got {email!r}")

    return email, password


def load_config(env=None):
    env = os.environ if env is None else env

    secret = _read_secret(env)
    expiry = _read_number(env, "JWT_EXPIRY_SECONDS", int)

    if expiry < 1:
        raise ConfigError(f"JWT_EXPIRY_SECONDS must be at least 1, got {expiry}")

    if expiry > MAX_EXPIRY_SECONDS:
        raise ConfigError(
            f"JWT_EXPIRY_SECONDS must be at most {MAX_EXPIRY_SECONDS}, got "
            f"{expiry}. A token nobody can revoke should not outlive a day."
        )

    admin_email, admin_password = _read_admin(env)

    return ApiConfig(
        jwt_secret=secret,
        token_expiry_seconds=expiry,
        admin_email=admin_email,
        admin_password=admin_password,
        redis_url=env.get("REDIS_URL") or DEFAULTS["REDIS_URL"],
        symbols=parse_symbols(env.get("STOCK_SYMBOLS") or DEFAULTS["STOCK_SYMBOLS"]),
        cookie_secure=_read_flag(env, "COOKIE_SECURE"),
    )
