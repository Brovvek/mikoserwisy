from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict


class ErrorMessage(BaseModel):
    detail: str


class Source(BaseModel):
    """Stan portalu ogłoszeniowego. Właścicielem tych danych jest collector-service."""

    id: str
    label: str
    country: str
    domain: str
    enabled: bool
    # Wstrzymanie po serii odmów portalu (403, 429): do tej chwili nie wolno pobierać stron.
    blocked_until: AwareDatetime | None = None


class ListingReference(BaseModel):
    """Pola oferty potrzebne collectorowi. Właścicielem oferty jest market-service, kopia nie jest zapisywana."""

    # Nieznane pola są pomijane (tolerant reader): market-service może rozwijać swój model.
    model_config = ConfigDict(extra="ignore")

    id: int
    source: str
    external_id: str
    url: str
    last_seen_at: datetime


class RefreshBlocker(StrEnum):
    SOURCE_UNKNOWN = "source_unknown"
    SOURCE_DISABLED = "source_disabled"
    SOURCE_BLOCKED = "source_blocked"


class RefreshCheck(BaseModel):
    """Czy ofertę można teraz ponownie pobrać z jej portalu."""

    listing: ListingReference
    source: Source | None
    can_refresh: bool
    blocker: RefreshBlocker | None
