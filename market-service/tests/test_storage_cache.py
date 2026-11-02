from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from sqlalchemy.exc import OperationalError

from app.main import create_app
from tests.conftest import cache_key
from tests.fake_eureka import FakeEurekaClient
from tests.memory_redis import MemoryRedis
from tests.test_listings import listing_payload

NEWER_OBSERVATION = {"observed_at": "2026-10-22T08:00:00Z", "price_amount": 99900, "mileage_km": 98700}


def count_repository_reads(client, monkeypatch):
    """Podmienia repository.get na wersję liczącą wywołania, czyli odczyty bazy."""
    repository = client.app.state.repository
    reads = []
    original_get = repository.get

    def counted_get(listing_id):
        reads.append(listing_id)
        return original_get(listing_id)

    monkeypatch.setattr(repository, "get", counted_get)
    return reads


def test_listing_survives_restart_with_empty_cache(database_url):
    with TestClient(create_app(database_url=database_url, redis_client=MemoryRedis(), eureka_client=FakeEurekaClient())) as first:
        created = first.post("/listings", json=listing_payload()).json()
        assert first.patch("/listings/1", json=NEWER_OBSERVATION).status_code == 200

    # Nowa instancja z tą samą bazą i nowym, pustym cache — odpowiedź musi pochodzić z bazy.
    with TestClient(create_app(database_url=database_url, redis_client=MemoryRedis(), eureka_client=FakeEurekaClient())) as second:
        response = second.get("/listings/4")
        assert response.status_code == 200
        assert response.headers["X-Cache"] == "MISS"
        assert response.json() == created

        listing = second.get("/listings/1").json()
        assert listing["price_amount"] == 99900
        assert listing["last_seen_at"] == "2026-10-22T08:00:00Z"
        assert listing["price_history"] == [
            {"at": "2026-10-20T08:00:00Z", "amount": 104900},
            {"at": "2026-10-22T08:00:00Z", "amount": 99900},
        ]
        # Dane początkowe nie zostały dodane drugi raz ani nie nadpisały zmiany.
        assert [item["id"] for item in second.get("/listings").json()] == [1, 2, 3, 4]


def test_miss_then_hit_reads_database_once(client, fake_redis, monkeypatch):
    reads = count_repository_reads(client, monkeypatch)

    first = client.get("/listings/1")
    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert fake_redis.expirations[cache_key(1)] == 60

    second = client.get("/listings/1")
    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"
    assert second.json() == first.json()
    assert reads == [1]  # przy HIT repozytorium nie było wywołane


def test_observation_invalidates_cached_listing(client, fake_redis, monkeypatch):
    reads = count_repository_reads(client, monkeypatch)
    client.get("/listings/1")
    assert client.get("/listings/1").headers["X-Cache"] == "HIT"

    assert client.patch("/listings/1", json=NEWER_OBSERVATION).status_code == 200
    assert cache_key(1) not in fake_redis.values

    response = client.get("/listings/1")
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["price_amount"] == 99900
    assert reads == [1, 1]


def test_rejected_observation_changes_neither_database_nor_cache(client, fake_redis):
    before = client.get("/listings/1").json()
    cached = fake_redis.values[cache_key(1)]

    response = client.patch(
        "/listings/1", json={"observed_at": "2026-10-19T08:00:00Z", "price_amount": 109900}
    )

    assert response.status_code == 409
    assert fake_redis.values[cache_key(1)] == cached  # wycofana operacja nie unieważnia cache
    fake_redis.values.clear()
    assert client.get("/listings/1").json() == before  # baza bez zmian


def test_cache_outage_does_not_block_read_or_write(client, fake_redis):
    fake_redis.down = True

    response = client.get("/listings/1")
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json()["price_amount"] == 104900

    # Zapis zostaje zatwierdzony mimo nieudanego unieważnienia.
    assert client.patch("/listings/1", json=NEWER_OBSERVATION).status_code == 200
    assert client.post("/listings", json=listing_payload()).status_code == 201
    response = client.get("/listings/1")
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json()["price_amount"] == 99900

    fake_redis.down = False
    response = client.get("/listings/1")
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["price_amount"] == 99900


def test_failed_cache_set_still_returns_database_value(client, fake_redis, monkeypatch):
    def failed_set(*args, **kwargs):
        raise ConnectionError("SET failed")

    monkeypatch.setattr(fake_redis, "set", failed_set)

    response = client.get("/listings/1")
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json()["price_amount"] == 104900


def test_failed_invalidation_leaves_old_value_until_ttl(client, fake_redis):
    client.get("/listings/1")  # MISS — kopia z ceną 104 900
    fake_redis.down = True
    assert client.patch("/listings/1", json=NEWER_OBSERVATION).status_code == 200
    fake_redis.down = False

    # Ograniczenie cache-aside: po nieudanym DEL wraca stara kopia.
    stale = client.get("/listings/1")
    assert stale.headers["X-Cache"] == "HIT"
    assert stale.json()["price_amount"] == 104900

    # Zamiennik nie odlicza TTL; wygaśnięcie wpisu symuluje jego usunięcie.
    del fake_redis.values[cache_key(1)]
    fresh = client.get("/listings/1")
    assert fresh.headers["X-Cache"] == "MISS"
    assert fresh.json()["price_amount"] == 99900


def test_duplicate_stopped_by_unique_constraint_returns_409(client, monkeypatch):
    # Symulacja równoległego zapisu: wstępne sprawdzenie duplikatu „nie widzi” oferty 1,
    # więc zatrzymuje ją dopiero ograniczenie UNIQUE(source, external_id) w bazie.
    repository = client.app.state.repository
    original_find = repository._find_by_source
    calls = []

    def find_missing_first_time(db, source, external_id):
        calls.append(source)
        return None if len(calls) == 1 else original_find(db, source, external_id)

    monkeypatch.setattr(repository, "_find_by_source", find_missing_first_time)
    before = client.get("/listings").json()

    response = client.post("/listings", json=listing_payload(external_id="6123456789"))

    assert response.status_code == 409
    assert response.json() == {"detail": "Listing otomoto/6123456789 already exists (listing 1)"}
    assert client.get("/listings").json() == before  # transakcja wycofana


def test_ready_reports_degraded_cache_and_missing_database(client, fake_redis, monkeypatch):
    assert client.get("/ready").json() == {
        "service": "market-service", "status": "ok", "database": "ok", "cache": "ok"
    }

    fake_redis.down = True
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"

    def broken_connect():
        raise OperationalError("SELECT 1", {}, Exception("database is down"))

    monkeypatch.setattr(client.app.state.engine, "connect", broken_connect)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "service": "market-service", "status": "error", "database": "down", "cache": "down"
    }
    assert client.get("/health").status_code == 200  # /health bez zmian względem LAB1
