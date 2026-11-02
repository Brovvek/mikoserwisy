from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from py_eureka_client.eureka_client import EurekaClient

from demo.shared.eureka import create_eureka_client


LOCKERS = {
    "KRK-1024": {
        "id": "KRK-1024",
        "name": "Galeria",
        "address": "Dluga 10",
        "city": "Krakow",
        "status": "online",
    }
}


def create_app(eureka_client: EurekaClient | None = None) -> FastAPI:
    client = eureka_client if eureka_client is not None else create_eureka_client("LOCKER-SERVICE", 8101)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.eureka_client = client
        try:
            await client.start()
            yield
        finally:
            await client.stop()

    app = FastAPI(title="Locker Service", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "LOCKER-SERVICE"}

    @app.get("/lockers/{locker_id}")
    async def get_locker(locker_id: str) -> dict[str, str]:
        locker = LOCKERS.get(locker_id)
        if locker is None:
            raise HTTPException(status_code=404, detail="Locker not found")
        return locker

    return app


app = create_app()
