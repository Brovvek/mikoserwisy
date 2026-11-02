from collections.abc import Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, HTTPException

from app.eureka import create_eureka_client
from app.models import ErrorMessage, ListingReference, RefreshBlocker, RefreshCheck, Source

SERVICE_NAME = "collector-service"
# Nazwa logiczna zależności. Adres instancji pochodzi z lokalnej kopii rejestru, nigdy z kodu.
MARKET_SERVICE = "MARKET-SERVICE"
MARKET_TIMEOUT_SECONDS = 3

# Mały lokalny zestaw danych LAB3 (tak pozwala instrukcja). Docelowo tabela w bazie collectora, jak source_state w AutoRadar.
INITIAL_SOURCES = (
    Source(id="otomoto", label="OTOMOTO", country="PL", domain="www.otomoto.pl", enabled=True),
    Source(id="autoscout24_de", label="AutoScout24 (DE)", country="DE", domain="www.autoscout24.de", enabled=True),
    Source(id="autobazar_eu", label="autobazar.eu", country="SK", domain="www.autobazar.eu", enabled=False),
)


def error_response(description: str) -> dict:
    """Opis błędu w OpenAPI, widoczny w /docs."""
    return {"model": ErrorMessage, "description": description}


def find_blocker(source: Source | None, now: datetime) -> RefreshBlocker | None:
    """Reguła collectora: co stoi na przeszkodzie pobraniu strony z portalu."""
    if source is None:
        return RefreshBlocker.SOURCE_UNKNOWN
    if not source.enabled:
        return RefreshBlocker.SOURCE_DISABLED
    if source.blocked_until is not None and source.blocked_until > now:
        return RefreshBlocker.SOURCE_BLOCKED
    return None


def create_app(eureka_client=None, sources: Iterable[Source] = INITIAL_SOURCES) -> FastAPI:
    """Klienta Eureki i stan portali można podać jawnie (testy); domyślnie klient powstaje z konfiguracji środowiska."""
    eureka = eureka_client if eureka_client is not None else create_eureka_client("COLLECTOR-SERVICE", 8102)
    sources_by_id = {source.id: source for source in sources}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.eureka_client = eureka
        try:
            await eureka.start()
            yield
        finally:
            await eureka.stop()

    app = FastAPI(
        title="Collector Service",
        description="Portale ogłoszeniowe i decyzja, czy można z nich teraz pobierać — LAB3",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": SERVICE_NAME}

    @app.get("/sources")
    def list_sources() -> list[Source]:
        """Stan wszystkich portali."""
        return list(sources_by_id.values())

    @app.get("/sources/{source_id}", responses={404: error_response("Source not found")})
    def get_source(source_id: str) -> Source:
        """Stan jednego portalu."""
        source = sources_by_id.get(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        return source

    @app.get(
        "/refresh-check/{listing_id}",
        responses={
            404: error_response("Listing not found in Market Service"),
            502: error_response("Market Service returned an HTTP error or an invalid response"),
            503: error_response("Market Service is unavailable"),
        },
    )
    async def refresh_check(listing_id: int) -> RefreshCheck:
        """Czy ofertę można teraz ponownie pobrać: ofertę zna market-service, stan jej portalu — ta usługa."""
        try:
            response = await app.state.eureka_client.do_service(
                MARKET_SERVICE,
                f"/listings/{listing_id}",
                return_type="json",
                timeout=MARKET_TIMEOUT_SECONDS,
            )
            listing = ListingReference.model_validate(response)
        # HTTPError dziedziczy po URLError, więc musi być obsłużony wcześniej.
        except HTTPError as exc:
            if exc.code == 404:
                raise HTTPException(status_code=404, detail="Listing not found in Market Service") from exc
            raise HTTPException(status_code=502, detail="Market Service returned an HTTP error") from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(status_code=503, detail="Market Service is unavailable") from exc
        # Odpowiedź 200 niezgodna z kontraktem: JSONDecodeError (nie JSON) i ValidationError (brak pól) to ValueError.
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Market Service returned an invalid response") from exc

        source = sources_by_id.get(listing.source)
        blocker = find_blocker(source, datetime.now(UTC))
        return RefreshCheck(listing=listing, source=source, can_refresh=blocker is None, blocker=blocker)

    return app


app = create_app()
