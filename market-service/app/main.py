from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException

from app.models import ErrorMessage, Fuel, Listing, ListingCreate, ListingObservation
from app.store import ListingConflictError, ListingNotFoundError, ListingStore

SERVICE_NAME = "market-service"

# Każda nowa instancja aplikacji — także po restarcie procesu — zaczyna od tych ofert.
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Market Service",
        description="Oferty z portali ogłoszeniowych z samochodami i historia ich cen — LAB1",
        version="0.1.0",
    )
    # Każda instancja aplikacji ma własny magazyn w pamięci z tymi samymi danymi początkowymi.
    app.state.listings = ListingStore()
    for data in INITIAL_LISTINGS:
        app.state.listings.create(data)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": SERVICE_NAME}

    @app.get("/listings")
    def list_listings(
        make: str | None = None, model: str | None = None, country: str | None = None
    ) -> list[Listing]:
        """Lista ofert, opcjonalnie tylko jednej marki, modelu lub kraju."""
        return app.state.listings.list_listings(make=make, model=model, country=country)

    @app.get("/listings/{listing_id}", responses={404: error_response("Listing not found")})
    def get_listing(listing_id: int) -> Listing:
        try:
            return app.state.listings.get(listing_id)
        except ListingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/listings",
        status_code=201,
        responses={409: error_response("Listing from this source already exists")},
    )
    def create_listing(data: ListingCreate) -> Listing:
        """Rejestruje nową ofertę odczytaną z portalu."""
        try:
            return app.state.listings.create(data)
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
            return app.state.listings.record_observation(listing_id, observation)
        except ListingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ListingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
