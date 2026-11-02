import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import db_models  # noqa: F401 — rejestruje tabele we wspólnym Base.metadata
from app.cache import JsonCache, make_redis
from app.database import Base, make_database
from app.models import ErrorMessage, Fuel, Listing, ListingCreate, ListingObservation
from app.repository import ListingConflictError, ListingNotFoundError, ListingRepository

SERVICE_NAME = "market-service"

# Dane początkowe trafiają tylko do pustej bazy, więc restart nie cofa zapisanych zmian.
INITIAL_LISTINGS = (
    ListingCreate(
        source="otomoto",
        external_id="6123456789",
        country="PL",
        url="https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID6123456789.html",
        title="BMW Seria 3 320d xDrive M Sport",
        make="BMW",
        model="Seria 3",
        year=2019,
        mileage_km=98500,
        fuel=Fuel.DIESEL,
        price_amount=104900,
        currency="PLN",
        observed_at=datetime(2026, 10, 20, 8, 0, tzinfo=UTC),
    ),
    ListingCreate(
        source="autoscout24_de",
        external_id="a8d3f1c2-0b5e-4c7a-9e21-5f6b7c8d9e01",
        country="DE",
        url="https://www.autoscout24.de/angebote/bmw-320-d-touring-luxury-line-diesel-a8d3f1c2-0b5e-4c7a-9e21-5f6b7c8d9e01",
        title="BMW 320d Touring Luxury Line",
        make="BMW",
        model="Seria 3",
        year=2020,
        mileage_km=71200,
        fuel=Fuel.DIESEL,
        price_amount=22400,
        currency="EUR",
        observed_at=datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
    ),
    ListingCreate(
        source="autobazar_eu",
        external_id="198765432",
        country="SK",
        url="https://www.autobazar.eu/detail/skoda-octavia-combi-2-0-tdi-style/198765432/",
        title="Skoda Octavia Combi 2.0 TDI Style",
        make="Skoda",
        model="Octavia",
        year=2018,
        mileage_km=142000,
        fuel=Fuel.DIESEL,
        price_amount=15900,
        currency="EUR",
        observed_at=datetime(2026, 10, 20, 10, 0, tzinfo=UTC),
    ),
)


def error_response(description: str) -> dict:
    """Opis błędu w OpenAPI, widoczny w /docs."""
    return {"model": ErrorMessage, "description": description}


def create_app(database_url: str | None = None, redis_client=None) -> FastAPI:
    """Adres bazy i klienta Redis można podać jawnie (testy); domyślnie pochodzą ze zmiennych środowiska."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessions = make_database(
            database_url or os.getenv("DATABASE_URL", "sqlite:///./app.db")
        )
        client = None
        try:
            client = redis_client if redis_client is not None else make_redis(
                os.getenv("REDIS_URL", "redis://localhost:6379/0")
            )
            Base.metadata.create_all(engine)  # tworzy brakujące tabele; nie zmienia istniejących
            repository = ListingRepository(sessions)
            if repository.is_empty():
                for data in INITIAL_LISTINGS:
                    repository.create(data)
            app.state.engine = engine
            app.state.redis = client
            app.state.repository = repository
            app.state.cache = JsonCache(
                client,
                prefix=os.environ["CACHE_PREFIX"],
                ttl=int(os.getenv("CACHE_TTL_SECONDS", "60")),
                resource_name="listing",
            )
            yield
        finally:
            try:
                if client is not None:
                    client.close()
            finally:
                engine.dispose()

    app = FastAPI(
        title="Market Service",
        description="Oferty z portali ogłoszeniowych z samochodami i historia ich cen — LAB2",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": SERVICE_NAME}

    @app.get("/ready")
    def readiness() -> JSONResponse:
        """Gotowość: baza jest wymagana (503 bez niej), Redis opcjonalny (bez niego „degraded”, 200)."""
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            db_ok = True
        except SQLAlchemyError:
            db_ok = False
        try:
            cache_ok = bool(app.state.redis.ping())
        except RedisError:
            cache_ok = False
        status = "ok" if (db_ok and cache_ok) else ("degraded" if db_ok else "error")
        return JSONResponse(
            status_code=200 if db_ok else 503,
            content={
                "service": SERVICE_NAME,
                "status": status,
                "database": "ok" if db_ok else "down",
                "cache": "ok" if cache_ok else "down",
            },
        )

    @app.get("/listings")
    def list_listings(
        make: str | None = None, model: str | None = None, country: str | None = None
    ) -> list[Listing]:
        """Lista ofert, opcjonalnie tylko jednej marki, modelu lub kraju."""
        return app.state.repository.list_listings(make=make, model=model, country=country)

    @app.get("/listings/{listing_id}", responses={404: error_response("Listing not found")})
    def get_listing(listing_id: int, response: Response) -> Listing:
        """Szczegóły oferty. Nagłówek X-Cache: HIT, MISS albo BYPASS (cache niedostępny)."""
        # Cache-aside: najpierw kopia w Redis, przy jej braku baza i zapis kopii z TTL.
        cached, source = app.state.cache.get(listing_id)
        if cached is not None:
            response.headers["X-Cache"] = source
            return cached
        try:
            listing = app.state.repository.get(listing_id)
        except ListingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if source != "BYPASS" and not app.state.cache.put(listing_id, listing.model_dump(mode="json")):
            source = "BYPASS"
        response.headers["X-Cache"] = source
        return listing

    @app.post(
        "/listings",
        status_code=201,
        responses={409: error_response("Listing from this source already exists")},
    )
    def create_listing(data: ListingCreate) -> Listing:
        """Rejestruje nową ofertę odczytaną z portalu."""
        try:
            return app.state.repository.create(data)
        except ListingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch(
        "/listings/{listing_id}",
        responses={
            404: error_response("Listing not found"),
            409: error_response("Observation is not newer than the last one"),
        },
    )
    def record_observation(listing_id: int, observation: ListingObservation) -> Listing:
        """Zapisuje nowszą obserwację oferty: aktualną cenę i przebieg."""
        try:
            listing = app.state.repository.record_observation(listing_id, observation)
        except ListingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ListingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        # Unieważnienie dopiero po commicie. Nieudane nie cofa zapisu — stara kopia żyje najdłużej do TTL.
        app.state.cache.delete(listing_id)
        return listing

    return app


app = create_app()
