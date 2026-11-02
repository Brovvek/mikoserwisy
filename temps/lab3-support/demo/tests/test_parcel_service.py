from urllib.error import HTTPError, URLError

import pytest
from httpx import ASGITransport, AsyncClient

from demo.parcel_service.app.main import create_app


class FakeEurekaClient:
    def __init__(self, response=None, error=None):
        self.response = response if response is not None else {
            "id": "KRK-1024",
            "name": "Galeria",
            "address": "Dluga 10",
            "city": "Krakow",
            "status": "online",
        }
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


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_delivery_check_discovers_locker_service_by_name():
    fake = FakeEurekaClient()
    app = create_app(eureka_client=fake)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/delivery-check/KRK-1024")

    assert response.status_code == 200
    assert response.json() == {"destination": "KRK-1024", "locker": fake.response}
    assert fake.calls == [("LOCKER-SERVICE", "/lockers/KRK-1024", "json", 3)]
    assert fake.starts == fake.stops == 1


@pytest.mark.anyio
@pytest.mark.parametrize("error", [URLError("connection refused"), TimeoutError("timeout")])
async def test_delivery_check_returns_service_unavailable_when_dependency_is_down(error):
    fake = FakeEurekaClient(error=error)
    app = create_app(eureka_client=fake)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/delivery-check/KRK-1024")
            health = await client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Locker Service is unavailable"
    assert health.status_code == 200
    assert fake.starts == fake.stops == 1


@pytest.mark.anyio
async def test_delivery_check_preserves_not_found_from_dependency():
    error = HTTPError("http://locker/lockers/UNKNOWN", 404, "Not Found", {}, None)
    fake = FakeEurekaClient(error=error)
    app = create_app(eureka_client=fake)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/delivery-check/UNKNOWN")

    assert response.status_code == 404
    assert response.json()["detail"] == "Destination locker not found"
    assert fake.calls == [("LOCKER-SERVICE", "/lockers/UNKNOWN", "json", 3)]


@pytest.mark.anyio
async def test_delivery_check_maps_dependency_server_error_to_bad_gateway():
    error = HTTPError("http://locker/lockers/KRK-1024", 500, "Internal error", {}, None)
    fake = FakeEurekaClient(error=error)
    app = create_app(eureka_client=fake)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/delivery-check/KRK-1024")
    assert response.status_code == 502
    assert response.json() == {"detail": "Locker Service returned an HTTP error"}


@pytest.mark.anyio
async def test_locker_demo_preserves_lab1_fields_and_lifecycle():
    from demo.locker_service.app.main import create_app as create_locker_app

    fake = FakeEurekaClient()
    app = create_locker_app(eureka_client=fake)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            known = await client.get("/lockers/KRK-1024")
            missing = await client.get("/lockers/UNKNOWN")
    assert known.status_code == 200
    assert known.json() == fake.response
    assert missing.status_code == 404
    assert fake.starts == fake.stops == 1
