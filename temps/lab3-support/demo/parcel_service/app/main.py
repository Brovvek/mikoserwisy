from contextlib import asynccontextmanager
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, HTTPException
from py_eureka_client.eureka_client import EurekaClient

from demo.shared.eureka import create_eureka_client


def create_app(eureka_client: EurekaClient | None = None) -> FastAPI:
    client = eureka_client if eureka_client is not None else create_eureka_client("PARCEL-SERVICE", 8102)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.eureka_client = client
        try:
            await client.start()
            yield
        finally:
            await client.stop()

    app = FastAPI(title="Parcel Service", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "PARCEL-SERVICE"}

    @app.get("/delivery-check/{locker_id}")
    async def check_destination(locker_id: str) -> dict[str, object]:
        try:
            locker = await app.state.eureka_client.do_service(
                "LOCKER-SERVICE",
                f"/lockers/{locker_id}",
                return_type="json",
                timeout=3,
            )
        except HTTPError as exc:
            if exc.code == 404:
                raise HTTPException(
                    status_code=404, detail="Destination locker not found"
                ) from exc
            raise HTTPException(
                status_code=502, detail="Locker Service returned an HTTP error"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(
                status_code=503, detail="Locker Service is unavailable"
            ) from exc

        return {"destination": locker_id, "locker": locker}

    return app


app = create_app()
