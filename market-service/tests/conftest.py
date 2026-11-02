import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.memory_redis import MemoryRedis

CACHE_PREFIX = "lab2:test:market-service"


def cache_key(listing_id):
    return f"{CACHE_PREFIX}:listing:{listing_id}"


@pytest.fixture(autouse=True)
def cache_settings(monkeypatch):
    # Konfiguracja z terminala (np. inny TTL) nie wpływa na testy.
    monkeypatch.setenv("CACHE_PREFIX", CACHE_PREFIX)
    monkeypatch.setenv("CACHE_TTL_SECONDS", "60")


@pytest.fixture
def database_url(tmp_path):
    # Osobny plik bazy dla każdego testu; pusta baza dostaje dane początkowe.
    return "sqlite:///" + (tmp_path / "test.db").as_posix()


@pytest.fixture
def fake_redis():
    return MemoryRedis()


@pytest.fixture
def client(database_url, fake_redis):
    with TestClient(create_app(database_url=database_url, redis_client=fake_redis)) as test_client:
        yield test_client
