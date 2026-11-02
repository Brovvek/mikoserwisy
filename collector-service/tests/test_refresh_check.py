import json
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError

import pytest
from httpx import ASGITransport, AsyncClient
from py_eureka_client.eureka_client import DiscoverException, WalkNodeException

from app.main import create_app
from app.models import Source

LISTING = {
    "id": 1,
    "source": "otomoto",
    "external_id": "6123456789",
    "country": "PL",
    "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID6123456789.html",
    "title": "BMW Seria 3 320d xDrive M Sport",
    "make": "BMW",
    "model": "Seria 3",
    "year": 2019,
    "mileage_km": 98500,
    "fuel": "diesel",
    "price_amount": 104900,
    "currency": "PLN",
    "first_seen_at": "2026-10-20T08:00:00Z",
    "last_seen_at": "2026-10-20T08:00:00Z",
    "price_history": [{"at": "2026-10-20T08:00:00Z", "amount": 104900}],
}


class FakeEurekaClient:
    """Zamiennik klienta Eureki: zapisuje wywołania, nie łączy się z siecią."""

    def __init__(self, response=None, error=None):
        self.response = response if response is not None else LISTING
        self.error = error
        self.calls = []
        self.starts = 0
        self.stops = 0

    async def start(self):
        self.starts += 1

    async def stop(self):
        self.stops += 1

    async def do_service(self, service_name, path, return_type=None, timeout=None):
        self.calls.append((service_name, path, return_type, timeout))
        if self.error:
            raise self.error
        return self.response


def http_error(code):
    return HTTPError("http://market/listings/1", code, "error", {}, None)


def source(**changes):
    return Source(**{"id": "otomoto", "label": "OTOMOTO", "country": "PL", "domain": "www.otomoto.pl", "enabled": True} | changes)


async def get(fake, path, **app_options):
    app = create_app(eureka_client=fake, **app_options)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_refresh_check_discovers_market_service_by_name():
    fake = FakeEurekaClient()

    response = await get(fake, "/refresh-check/1")

    assert response.status_code == 200
    assert fake.calls == [("MARKET-SERVICE", "/listings/1", "json", 3)]
    body = response.json()
    assert body["can_refresh"] is True
    assert body["blocker"] is None
    assert body["source"]["id"] == "otomoto"
    # Z oferty zostają tylko pola potrzebne collectorowi; cena należy do market-service.
    assert body["listing"] == {
        "id": 1,
        "source": "otomoto",
        "external_id": "6123456789",
        "url": LISTING["url"],
        "last_seen_at": "2026-10-20T08:00:00Z",
    }


@pytest.mark.anyio
async def test_refresh_check_uses_requested_identifier():
    fake = FakeEurekaClient()

    await get(fake, "/refresh-check/42")

    assert fake.calls == [("MARKET-SERVICE", "/listings/42", "json", 3)]


@pytest.mark.anyio
async def test_refresh_check_returns_404_when_market_does_not_know_listing():
    fake = FakeEurekaClient(error=http_error(404))

    response = await get(fake, "/refresh-check/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Listing not found in Market Service"}
    assert fake.calls == [("MARKET-SERVICE", "/listings/999", "json", 3)]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [
        URLError("connection refused"),
        TimeoutError("timeout"),
        DiscoverException("registry not loaded"),
        WalkNodeException("no up instance", []),
    ],
)
async def test_refresh_check_returns_503_and_stays_healthy_when_market_is_down(error):
    fake = FakeEurekaClient(error=error)
    app = create_app(eureka_client=fake)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/refresh-check/1")
            health = await client.get("/health")
            own_data = await client.get("/sources/otomoto")

    assert response.status_code == 503
    assert response.json() == {"detail": "Market Service is unavailable"}
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "collector-service"}
    assert own_data.status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("code", [400, 409, 500, 503])
async def test_refresh_check_maps_other_http_errors_to_502(code):
    response = await get(FakeEurekaClient(error=http_error(code)), "/refresh-check/1")

    assert response.status_code == 502
    assert response.json() == {"detail": "Market Service returned an HTTP error"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fake",
    [
        FakeEurekaClient(error=json.JSONDecodeError("Expecting value", "<html>", 0)),
        FakeEurekaClient(response={"id": 1}),
        FakeEurekaClient(response=[LISTING]),
    ],
    ids=["not-json", "missing-fields", "not-an-object"],
)
async def test_refresh_check_maps_response_breaking_contract_to_502(fake):
    response = await get(fake, "/refresh-check/1")

    assert response.status_code == 502
    assert response.json() == {"detail": "Market Service returned an invalid response"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("sources", "can_refresh", "blocker"),
    [
        ([source(enabled=False)], False, "source_disabled"),
        ([source(blocked_until=datetime.now(UTC) + timedelta(hours=1))], False, "source_blocked"),
        ([source(blocked_until=datetime.now(UTC) - timedelta(hours=1))], True, None),
        ([], False, "source_unknown"),
    ],
    ids=["disabled", "blocked", "block-expired", "unknown"],
)
async def test_refresh_check_applies_own_rule_to_market_data(sources, can_refresh, blocker):
    response = await get(FakeEurekaClient(), "/refresh-check/1", sources=sources)

    assert response.status_code == 200
    assert response.json()["can_refresh"] is can_refresh
    assert response.json()["blocker"] == blocker


@pytest.mark.anyio
async def test_invalid_identifier_is_rejected_before_calling_market():
    fake = FakeEurekaClient()

    response = await get(fake, "/refresh-check/abc")

    assert response.status_code == 422
    assert fake.calls == []


@pytest.mark.anyio
async def test_eureka_client_starts_and_stops_with_application():
    fake = FakeEurekaClient()
    app = create_app(eureka_client=fake)
    assert (fake.starts, fake.stops) == (0, 0)

    async with app.router.lifespan_context(app):
        assert app.state.eureka_client is fake
        assert (fake.starts, fake.stops) == (1, 0)

    assert (fake.starts, fake.stops) == (1, 1)


@pytest.mark.anyio
async def test_sources_are_served_without_calling_market():
    fake = FakeEurekaClient()
    app = create_app(eureka_client=fake)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            all_sources = await client.get("/sources")
            known = await client.get("/sources/autobazar_eu")
            missing = await client.get("/sources/unknown")

    assert [item["id"] for item in all_sources.json()] == ["otomoto", "autoscout24_de", "autobazar_eu"]
    assert known.json()["enabled"] is False
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Source not found"}
    assert fake.calls == []
