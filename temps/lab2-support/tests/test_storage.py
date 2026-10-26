import pytest
from redis.exceptions import ConnectionError

from cache import JsonCache
from database import Base, make_database
from demo import CachedLockers, LockerRepository


class MemoryRedis:
    """Test double only; does not replace the real Redis exercise."""
    def __init__(self):
        self.values = {}
        self.expirations = {}
        self.down = False

    def check(self):
        if self.down:
            raise ConnectionError("Simulated outage")

    def get(self, key):
        self.check()
        return self.values.get(key)

    def set(self, key, value, ex):
        self.check()
        self.values[key] = value
        self.expirations[key] = ex

    def delete(self, key):
        self.check()
        self.values.pop(key, None)
        self.expirations.pop(key, None)

    def ping(self):
        self.check()
        return True

    def close(self):
        # No sockets to release; compatible with FastAPI lifespan cleanup.
        pass


def test_fake_supports_readiness_and_cleanup():
    client = MemoryRedis()
    assert client.ping() is True
    client.down = True
    with pytest.raises(ConnectionError):
        client.ping()
    client.close()  # Closing resources must also work during an outage.


@pytest.fixture
def setup(tmp_path):
    url = "sqlite:///" + (tmp_path / "test.db").as_posix()
    engine, sessions = make_database(url)
    Base.metadata.create_all(engine)
    repo = LockerRepository(sessions)
    repo.create(dict(id="KRK-1024", name="Galeria", address="Dluga 10",
                     city="Krakow", status="online"))
    client = MemoryRedis()
    cache = JsonCache(client, ttl=30)
    yield url, repo, CachedLockers(repo, cache), client, cache
    engine.dispose()


def test_persists_with_new_engine(setup):
    url, _, _, _, _ = setup
    engine, sessions = make_database(url)
    try:
        assert LockerRepository(sessions).get("KRK-1024")["name"] == "Galeria"
    finally:
        engine.dispose()


def test_duplicate_rolls_back(setup):
    _, repo, _, _, _ = setup
    with pytest.raises(ValueError):
        repo.create(dict(id="KRK-1024", name="Duplicate", address="Other",
                         city="Krakow", status="online"))
    assert repo.get("KRK-1024")["name"] == "Galeria"


def test_miss_hit_and_invalidation(setup, monkeypatch):
    _, repo, service, client, cache = setup
    reads = []
    original_get = repo.get

    def counted_get(locker_id):
        reads.append(locker_id)
        return original_get(locker_id)

    monkeypatch.setattr(repo, "get", counted_get)
    assert service.get("KRK-1024")[1] == "MISS"
    assert client.expirations[cache.key("KRK-1024")] == 30
    assert service.get("KRK-1024")[1] == "HIT"
    assert len(reads) == 1
    assert service.rename("KRK-1024", "Nowa")[1] is True
    assert cache.key("KRK-1024") not in client.expirations
    value, source = service.get("KRK-1024")
    assert source == "MISS"
    assert value["name"] == "Nowa"
    assert len(reads) == 2


def test_failed_cache_set_still_returns_database_value(setup, monkeypatch):
    _, _, service, client, _ = setup

    def failed_set(*args, **kwargs):
        raise ConnectionError("SET failed")

    monkeypatch.setattr(client, "set", failed_set)
    value, source = service.get("KRK-1024")
    assert value["name"] == "Galeria"
    assert source == "BYPASS"


def test_outage_does_not_block_read_or_commit(setup):
    _, repo, service, client, _ = setup
    client.down = True
    assert service.get("KRK-1024")[1] == "BYPASS"
    assert service.rename("KRK-1024", "Nowa")[1] is False
    assert repo.get("KRK-1024")["name"] == "Nowa"


def test_failed_invalidation_can_leave_old_value(setup):
    _, repo, service, client, _ = setup
    service.get("KRK-1024")
    client.down = True
    service.rename("KRK-1024", "Nowa")
    client.down = False
    # Test double does not implement TTL: demonstrates the stale-value window.
    assert service.get("KRK-1024")[0]["name"] == "Galeria"
    assert repo.get("KRK-1024")["name"] == "Nowa"


def test_corrupt_cache_and_missing_record(setup):
    _, _, service, client, cache = setup
    client.values[cache.key("KRK-1024")] = "not-json"
    assert service.get("KRK-1024")[0]["id"] == "KRK-1024"
    with pytest.raises(LookupError):
        service.get("UNKNOWN")
