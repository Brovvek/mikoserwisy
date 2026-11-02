"""Tabele bazy danych. Kontrakt API opisują osobne modele Pydantic w app/models.py."""
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UtcDateTime(TypeDecorator):
    """Czas zapisywany w UTC. SQLite nie przechowuje strefy, więc przy odczycie dopisujemy UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class ListingRow(Base):
    __tablename__ = "listing"
    # Ta sama oferta portalu może być zapisana tylko raz — także przy równoległych zapisach.
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_listing_source_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(2))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(200))
    make: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(80))
    year: Mapped[int]
    mileage_km: Mapped[int]
    fuel: Mapped[str] = mapped_column(String(20))
    # Aktualna cena; poprzednie są w price_change.
    price_amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    first_seen_at: Mapped[datetime] = mapped_column(UtcDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime)

    price_changes: Mapped[list["PriceChangeRow"]] = relationship(
        order_by="PriceChangeRow.changed_at", cascade="all, delete-orphan"
    )


class PriceChangeRow(Base):
    """Jedna zmiana ceny oferty. Wiersz powstaje tylko wtedy, gdy nowsza obserwacja ma inną cenę."""

    __tablename__ = "price_change"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"), index=True)
    changed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    old_amount: Mapped[int]
    new_amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
