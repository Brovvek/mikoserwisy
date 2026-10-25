from app.models import Listing, ListingCreate, ListingObservation, PricePoint


class ListingNotFoundError(Exception):
    """Brak oferty o podanym identyfikatorze — API zwraca 404."""


class ListingConflictError(Exception):
    """Operacja koliduje z aktualnym stanem ofert — API zwraca 409."""


class ListingStore:
    """Oferty w pamięci procesu. Każda instancja aplikacji tworzy własny magazyn."""

    def __init__(self) -> None:
        self._listings: dict[int, Listing] = {}
        self._last_id = 0

    def list_listings(
        self, make: str | None = None, model: str | None = None, country: str | None = None
    ) -> list[Listing]:
        return [
            listing
            for listing in self._listings.values()
            if (make is None or listing.make == make)
            and (model is None or listing.model == model)
            and (country is None or listing.country == country)
        ]

    def get(self, listing_id: int) -> Listing:
        listing = self._listings.get(listing_id)
        if listing is None:
            raise ListingNotFoundError(f"Listing {listing_id} not found")
        return listing

    def create(self, data: ListingCreate) -> Listing:
        # Duplikat jest sprawdzany przed nadaniem numeru i zapisem, więc odrzucenie niczego nie zmienia.
        existing = self._find_by_source(data.source, data.external_id)
        if existing is not None:
            raise ListingConflictError(
                f"Listing {data.source}/{data.external_id} already exists (listing {existing.id})"
            )
        self._last_id += 1
        listing = Listing(
            id=self._last_id,
            **data.model_dump(exclude={"observed_at"}),
            first_seen_at=data.observed_at,
            last_seen_at=data.observed_at,
            price_history=[PricePoint(at=data.observed_at, amount=data.price_amount)],
        )
        self._listings[listing.id] = listing
        return listing

    def record_observation(self, listing_id: int, observation: ListingObservation) -> Listing:
        listing = self.get(listing_id)
        mileage_km = listing.mileage_km if observation.mileage_km is None else observation.mileage_km
        # Reguła biznesowa: stan oferty zmienia tylko obserwacja nowsza niż ostatnia.
        if observation.observed_at <= listing.last_seen_at:
            repeated = (
                observation.observed_at == listing.last_seen_at
                and observation.price_amount == listing.price_amount
                and mileage_km == listing.mileage_km
            )
            if repeated:
                return listing  # ponowne przesłanie ostatniej obserwacji niczego nie zmienia
            raise ListingConflictError(
                f"Observation from {observation.observed_at.isoformat()} is not newer than "
                f"the last observation of listing {listing_id} ({listing.last_seen_at.isoformat()})"
            )
        history = listing.price_history
        if observation.price_amount != listing.price_amount:
            history = [*history, PricePoint(at=observation.observed_at, amount=observation.price_amount)]
        # Nowy obiekt podmieniany jednym przypisaniem — nie ma stanu częściowo zmienionego.
        updated = listing.model_copy(
            update={
                "price_amount": observation.price_amount,
                "mileage_km": mileage_km,
                "last_seen_at": observation.observed_at,
                "price_history": history,
            }
        )
        self._listings[listing_id] = updated
        return updated

    def _find_by_source(self, source: str, external_id: str) -> Listing | None:
        for listing in self._listings.values():
            if listing.source == source and listing.external_id == external_id:
                return listing
        return None
