from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.db_models import ListingRow, PriceChangeRow
from app.models import Listing, ListingCreate, ListingObservation, PricePoint


class ListingNotFoundError(Exception):
    """Brak oferty o podanym identyfikatorze — API zwraca 404."""


class ListingConflictError(Exception):
    """Operacja koliduje z aktualnym stanem ofert — API zwraca 409."""


def to_listing(row: ListingRow) -> Listing:
    """Wiersz bazy → model API. Pierwszy punkt historii to cena z pierwszej obserwacji."""
    changes = row.price_changes
    history = [PricePoint(at=row.first_seen_at, amount=changes[0].old_amount if changes else row.price_amount)]
    history += [PricePoint(at=change.changed_at, amount=change.new_amount) for change in changes]
    return Listing(
        id=row.id,
        source=row.source,
        external_id=row.external_id,
        country=row.country,
        url=row.url,
        title=row.title,
        make=row.make,
        model=row.model,
        year=row.year,
        mileage_km=row.mileage_km,
        fuel=row.fuel,
        price_amount=row.price_amount,
        currency=row.currency,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        price_history=history,
    )


class ListingRepository:
    """Oferty w bazie danych. Każda operacja ma własną sesję; zapis to jedna transakcja."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def is_empty(self) -> bool:
        with self.sessions() as db:
            return db.scalar(select(ListingRow.id).limit(1)) is None

    def list_listings(
        self, make: str | None = None, model: str | None = None, country: str | None = None
    ) -> list[Listing]:
        query = select(ListingRow).options(selectinload(ListingRow.price_changes)).order_by(ListingRow.id)
        if make is not None:
            query = query.where(ListingRow.make == make)
        if model is not None:
            query = query.where(ListingRow.model == model)
        if country is not None:
            query = query.where(ListingRow.country == country)
        with self.sessions() as db:
            return [to_listing(row) for row in db.scalars(query)]

    def get(self, listing_id: int) -> Listing:
        with self.sessions() as db:
            return to_listing(self._get_row(db, listing_id))

    def create(self, data: ListingCreate) -> Listing:
        try:
            # Wyjście z bloku begin() zatwierdza transakcję, a wyjątek ją wycofuje.
            with self.sessions.begin() as db:
                # Duplikat jest sprawdzany przed zapisem, więc odrzucenie niczego nie zmienia.
                existing = self._find_by_source(db, data.source, data.external_id)
                if existing is not None:
                    raise self._duplicate(data, existing)
                row = ListingRow(
                    **data.model_dump(mode="json", exclude={"observed_at"}),
                    first_seen_at=data.observed_at,
                    last_seen_at=data.observed_at,
                )
                db.add(row)
                db.flush()  # nadaje id
                result = to_listing(row)
        except IntegrityError:
            # Równoległy zapis tej samej oferty przeszedł sprawdzenie wyżej, ale zatrzymało go
            # ograniczenie unikalności. 409 tylko wtedy, gdy oferta naprawdę już istnieje —
            # inny błąd bazy nie jest konfliktem.
            with self.sessions() as db:
                existing = self._find_by_source(db, data.source, data.external_id)
            if existing is None:
                raise
            raise self._duplicate(data, existing) from None
        return result

    def record_observation(self, listing_id: int, observation: ListingObservation) -> Listing:
        # Kolejność: odczyt stanu → sprawdzenie reguły → zmiana → commit.
        with self.sessions.begin() as db:
            row = self._get_row(db, listing_id)
            mileage_km = row.mileage_km if observation.mileage_km is None else observation.mileage_km
            # Reguła biznesowa: stan oferty zmienia tylko obserwacja nowsza niż ostatnia.
            if observation.observed_at <= row.last_seen_at:
                repeated = (
                    observation.observed_at == row.last_seen_at
                    and observation.price_amount == row.price_amount
                    and mileage_km == row.mileage_km
                )
                if repeated:
                    return to_listing(row)  # ponowne przesłanie ostatniej obserwacji niczego nie zmienia
                raise ListingConflictError(
                    f"Observation from {observation.observed_at.isoformat()} is not newer than "
                    f"the last observation of listing {listing_id} ({row.last_seen_at.isoformat()})"
                )
            if observation.price_amount != row.price_amount:
                row.price_changes.append(
                    PriceChangeRow(
                        changed_at=observation.observed_at,
                        old_amount=row.price_amount,
                        new_amount=observation.price_amount,
                        currency=row.currency,
                    )
                )
            row.price_amount = observation.price_amount
            row.mileage_km = mileage_km
            row.last_seen_at = observation.observed_at
            db.flush()
            result = to_listing(row)
        return result

    @staticmethod
    def _get_row(db: Session, listing_id: int) -> ListingRow:
        row = db.get(ListingRow, listing_id)
        if row is None:
            raise ListingNotFoundError(f"Listing {listing_id} not found")
        return row

    @staticmethod
    def _find_by_source(db: Session, source: str, external_id: str) -> ListingRow | None:
        return db.scalar(
            select(ListingRow).where(ListingRow.source == source, ListingRow.external_id == external_id)
        )

    @staticmethod
    def _duplicate(data: ListingCreate, existing: ListingRow) -> ListingConflictError:
        return ListingConflictError(
            f"Listing {data.source}/{data.external_id} already exists (listing {existing.id})"
        )
