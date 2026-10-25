from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl


class Fuel(StrEnum):
    """Wspólny słownik paliw, niezależny od nazw używanych przez portale."""

    PETROL = "petrol"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    PLUGIN_HYBRID = "plugin_hybrid"
    ELECTRIC = "electric"
    LPG = "lpg"
    CNG = "cng"
    HYDROGEN = "hydrogen"
    OTHER = "other"


class ListingCreate(BaseModel):
    """Oferta odczytana z portalu ogłoszeniowego. Identyfikator i historię cen nadaje serwer."""

    model_config = ConfigDict(
        # Nieznane pola są pomijane (tolerant reader): przyszły nadawca, collector-service,
        # może dodawać pola bez łamania kontraktu.
        extra="ignore",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "source": "otomoto",
                    "external_id": "6123456790",
                    "country": "PL",
                    "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID6123456790.html",
                    "title": "BMW Seria 3 320i Sport Line",
                    "make": "BMW",
                    "model": "Seria 3",
                    "year": 2021,
                    "mileage_km": 45000,
                    "fuel": "petrol",
                    "price_amount": 129900,
                    "currency": "PLN",
                    "observed_at": "2026-10-21T08:00:00Z",
                }
            ]
        },
    )

    # Identyfikator portalu, np. otomoto, autoscout24_de, autobazar_eu.
    source: str = Field(pattern=r"^[a-z0-9_]{2,40}$")
    # Numer ogłoszenia nadany przez portal — w otomoto liczba, w AutoScout24 GUID.
    external_id: str = Field(min_length=1, max_length=80)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    url: HttpUrl
    title: str = Field(min_length=1, max_length=200)
    make: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1950, le=2100)
    mileage_km: int = Field(ge=0)
    fuel: Fuel
    # Cena w pełnych jednostkach waluty ogłoszenia, bez przeliczania i bez zaokrągleń float.
    price_amount: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    # Chwila odczytu z portalu; bez strefy czasowej obserwacji z różnych krajów nie da się porównać.
    observed_at: AwareDatetime


class ListingObservation(BaseModel):
    """Kolejna obserwacja znanej oferty: cena i przebieg w chwili observed_at."""

    model_config = ConfigDict(extra="ignore")

    observed_at: AwareDatetime
    price_amount: int = Field(gt=0)
    # Brak przebiegu w obserwacji oznacza, że się nie zmienił.
    mileage_km: int | None = Field(default=None, ge=0)


class PricePoint(BaseModel):
    at: datetime
    amount: int


class Listing(BaseModel):
    id: int
    source: str
    external_id: str
    country: str
    url: HttpUrl
    title: str
    make: str
    model: str
    year: int
    mileage_km: int
    fuel: Fuel
    price_amount: int
    currency: str
    first_seen_at: datetime
    last_seen_at: datetime
    price_history: list[PricePoint]


class ErrorMessage(BaseModel):
    """Treść błędów 404 i 409 zgłaszanych przez HTTPException."""

    detail: str
