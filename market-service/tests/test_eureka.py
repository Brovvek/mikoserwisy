import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.fake_eureka import FakeEurekaClient
from tests.memory_redis import MemoryRedis


def test_eureka_client_starts_and_stops_with_application(database_url):
    fake = FakeEurekaClient()
    app = create_app(database_url=database_url, redis_client=MemoryRedis(), eureka_client=fake)
    assert (fake.starts, fake.stops) == (0, 0)

    with TestClient(app) as client:
        assert (fake.starts, fake.stops) == (1, 0)
        assert client.app.state.eureka_client is fake
        assert client.get("/listings/1").status_code == 200

    assert (fake.starts, fake.stops) == (1, 1)


def test_instance_registers_only_after_storage_is_ready(database_url):
    # Zarejestrowana instancja musi już obsługiwać żądania: repozytorium i dane początkowe są gotowe przed start().
    seen = []
    app = create_app(
        database_url=database_url,
        redis_client=MemoryRedis(),
        eureka_client=FakeEurekaClient(on_start=lambda: seen.append(app.state.repository.get(1).id)),
    )

    with TestClient(app):
        pass

    assert seen == [1]


def test_stop_runs_and_storage_closes_when_registration_fails(database_url):
    class UnreachableRegistry(FakeEurekaClient):
        async def start(self):
            await super().start()
            raise ConnectionError("registry down")

    redis = MemoryRedis()
    closed = []
    redis.close = lambda: closed.append(True)
    fake = UnreachableRegistry()
    app = create_app(database_url=database_url, redis_client=redis, eureka_client=fake)

    with pytest.raises(ConnectionError), TestClient(app):
        pass

    assert (fake.starts, fake.stops) == (1, 1)
    assert closed == [True]
