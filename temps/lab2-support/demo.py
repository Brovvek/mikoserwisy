"""Small runnable storage example, not a replacement for the LAB1 application."""
import argparse
import os
import sys

from sqlalchemy import String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, make_database
from cache import JsonCache, make_redis


class LockerRow(Base):
    __tablename__ = "lockers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="online")


def payload(row):
    return {field: getattr(row, field)
            for field in ("id", "name", "address", "city", "status")}


class LockerRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    def create(self, data):
        try:
            with self.sessions.begin() as db:
                row = LockerRow(**data)
                db.add(row)
                db.flush()
                result = payload(row)
            return result
        except IntegrityError as exc:
            raise ValueError("Duplicate or invalid locker") from exc

    def get(self, locker_id):
        with self.sessions() as db:
            row = db.get(LockerRow, locker_id)
            if row is None:
                raise LookupError(locker_id)
            return payload(row)

    def rename(self, locker_id, name):
        with self.sessions.begin() as db:
            row = db.get(LockerRow, locker_id)
            if row is None:
                raise LookupError(locker_id)
            row.name = name
            result = payload(row)
        return result


class CachedLockers:
    def __init__(self, repository, cache):
        self.repository, self.cache = repository, cache

    def get(self, locker_id):
        value, source = self.cache.get(locker_id)
        if value is not None:
            return value, source
        value = self.repository.get(locker_id)
        if source != "BYPASS" and not self.cache.put(locker_id, value):
            source = "BYPASS"
        return value, source

    def rename(self, locker_id, name):
        value = self.repository.rename(locker_id, name)  # commit first
        invalidated = self.cache.delete(locker_id)
        return value, invalidated


def main():
    # Preserve the terminal's encoding; escape unsupported characters instead
    # of crashing after a successful database commit (also for redirected I/O).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "get", "rename"])
    parser.add_argument("--name", default="Nowa Nazwa")
    args = parser.parse_args()
    engine, sessions = make_database(os.getenv("DATABASE_URL", "sqlite:///./demo.db"))
    Base.metadata.create_all(engine)  # creates missing tables; does not migrate them
    repository = LockerRepository(sessions)
    redis_client = make_redis(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    service = CachedLockers(repository, JsonCache(
        redis_client, os.getenv("CACHE_PREFIX", "lab2:demo"),
        int(os.getenv("CACHE_TTL_SECONDS", "60")),
    ))
    try:
        if args.action == "seed":
            try:
                print(repository.get("KRK-1024"))
            except LookupError:
                print(repository.create(dict(
                    id="KRK-1024", name="Krakow Galeria",
                    address="ul. Dluga 10", city="Krakow", status="online",
                )))
        elif args.action == "get":
            value, source = service.get("KRK-1024")
            print(source, value)
        else:
            value, invalidated = service.rename("KRK-1024", args.name)
            print("cache_invalidated=", invalidated, value)
    finally:
        redis_client.close()
        engine.dispose()


if __name__ == "__main__":
    main()
