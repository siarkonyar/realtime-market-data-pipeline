"""browser -> nginx (frontend container) -> api

nginx is the one door the browser uses: it hands out the React page and
passes /api/... and /ws/... on to the api. Only a real request through the
real image shows that its config works.
"""

import pytest
import requests
import websocket

FRONTEND_PORT = 80
TIMEOUT_SECONDS = 10

# A session cookie whose token the api cannot decode.
BAD_COOKIE = "session=not-a-real-token"

# The div React draws into. Seeing it means we got index.html back.
REACT_ROOT = '<div id="root"></div>'


@pytest.fixture(scope="session")
def frontend_address(compose):
    """host:port of nginx. A bare address, not a url, because the tests need
    both http:// and ws:// in front of it."""
    host = compose.get_service_host("frontend", FRONTEND_PORT)
    port = compose.get_service_port("frontend", FRONTEND_PORT)
    return f"{host}:{port}"


def test_the_frontend_serves_the_react_page(frontend_address):
    response = requests.get(f"http://{frontend_address}/", timeout=TIMEOUT_SECONDS)

    assert response.status_code == 200
    assert REACT_ROOT in response.text


def test_the_frontend_sends_an_unknown_path_to_the_react_page(frontend_address):
    """A page link like /login has no file on disk. React decides what to show
    for it, so nginx must answer with index.html instead of a 404."""
    response = requests.get(f"http://{frontend_address}/login", timeout=TIMEOUT_SECONDS)

    assert response.status_code == 200
    assert REACT_ROOT in response.text


# admin_token is asked for only to wait: it returns once the api is fully up.
def test_the_frontend_strips_the_api_prefix(frontend_address, admin_token):
    """The api has /health, not /api/health. A 200 here means nginx cut the
    /api off before passing the request on."""
    response = requests.get(
        f"http://{frontend_address}/api/health", timeout=TIMEOUT_SECONDS
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_frontend_passes_the_session_cookie_on_to_the_api(
    frontend_address, admin_headers
):
    """/symbols needs a signed-in user, so a 200 means the Cookie header made
    it through nginx."""
    response = requests.get(
        f"http://{frontend_address}/api/symbols",
        headers=admin_headers,
        timeout=TIMEOUT_SECONDS,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_the_frontend_answers_who_is_signed_in(frontend_address, admin_headers):
    """React's first call on every page load. If nginx broke it, nobody would
    get past "Checking your sign-in"."""
    response = requests.get(
        f"http://{frontend_address}/api/auth/session",
        headers=admin_headers,
        timeout=TIMEOUT_SECONDS,
    )

    assert response.status_code == 200
    # The seeded admin from docker-compose.e2e.yaml.
    assert response.json() == {"email": "admin@example.com", "role": "admin"}


def test_the_frontend_upgrades_the_candle_websocket(frontend_address, admin_token):
    """A wrong cookie gets close code 1008 from the api itself. Receiving it
    means the WebSocket handshake, cookie included, went through nginx and
    reached the api."""
    connection = websocket.create_connection(
        f"ws://{frontend_address}/ws/candles?symbol=NVDA",
        cookie=BAD_COOKIE,
        timeout=TIMEOUT_SECONDS,
    )
    try:
        opcode, frame = connection.recv_data_frame(control_frame=True)
    finally:
        connection.close()

    assert opcode == websocket.ABNF.OPCODE_CLOSE
    assert int.from_bytes(frame.data[:2], "big") == 1008
