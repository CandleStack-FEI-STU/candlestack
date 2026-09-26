from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from candlestack.core import Settings, create_http_client, request_with_retry, retry_after
from candlestack.core import http as http_module

URL = "https://upstream.test/api/v3/klines"

pytestmark = pytest.mark.anyio


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Records the waits of request_with_retry instead of sleeping."""
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(http_module, "_sleep", sleep)
    return delays


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as client:
        yield client


@respx.mock
async def test_retries_server_errors_with_backoff(client, sleeps: list[float]) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200, json=[])]
    )

    response = await request_with_retry(client, "GET", URL)

    assert response.status_code == 200
    assert route.call_count == 3
    assert sleeps == [0.5, 1.0]


@respx.mock
async def test_honours_retry_after_seconds(client, sleeps: list[float]) -> None:
    respx.get(URL).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)]
    )

    response = await request_with_retry(client, "GET", URL)

    assert response.status_code == 200
    assert sleeps == [7.0]


@respx.mock
async def test_returns_the_response_when_retry_after_is_too_long(
    client, sleeps: list[float]
) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "60"}))

    response = await request_with_retry(client, "GET", URL, max_delay=10)

    assert response.status_code == 429
    assert route.call_count == 1
    assert sleeps == []


@respx.mock
async def test_returns_the_last_response_when_attempts_run_out(client, sleeps: list[float]) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(503))

    response = await request_with_retry(client, "GET", URL, attempts=3)

    assert response.status_code == 503
    assert route.call_count == 3
    assert len(sleeps) == 2


@pytest.mark.parametrize("status", [200, 400, 404, 418])
@respx.mock
async def test_does_not_retry_other_statuses(client, sleeps: list[float], status: int) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(status))

    response = await request_with_retry(client, "GET", URL)

    assert response.status_code == status
    assert route.call_count == 1


@respx.mock
async def test_retries_connection_errors(client, sleeps: list[float]) -> None:
    route = respx.get(URL).mock(
        side_effect=[
            httpx.ConnectError("refused"),
            httpx.ConnectTimeout("slow"),
            httpx.Response(200),
        ]
    )

    response = await request_with_retry(client, "GET", URL)

    assert response.status_code == 200
    assert route.call_count == 3


@respx.mock
async def test_raises_the_last_connection_error(client, sleeps: list[float]) -> None:
    route = respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(httpx.ConnectError):
        await request_with_retry(client, "GET", URL, attempts=2)

    assert route.call_count == 2


@respx.mock
async def test_does_not_retry_read_timeouts(client, sleeps: list[float]) -> None:
    route = respx.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(httpx.ReadTimeout):
        await request_with_retry(client, "GET", URL)

    assert route.call_count == 1


@pytest.mark.parametrize(
    ("header", "expected"),
    [(None, None), ("0", 0.0), ("2.5", 2.5), ("-3", 0.0), ("soon", None)],
)
def test_retry_after(header: str | None, expected: float | None) -> None:
    headers = {"Retry-After": header} if header is not None else {}

    assert retry_after(httpx.Response(429, headers=headers)) == expected


def test_retry_after_http_date() -> None:
    when = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)

    delay = retry_after(httpx.Response(503, headers={"Retry-After": when}))

    assert delay is not None
    assert 25 < delay <= 30


async def test_shared_client_identifies_itself() -> None:
    async with create_http_client(Settings(app_version="v0.2.0")) as client:
        assert client.headers["User-Agent"] == "candlestack/v0.2.0"
        assert client.timeout.connect == 5.0
        assert client.timeout.read == 10.0
