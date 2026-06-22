"""Dhanada FastAPI application."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

from dhanada.auth.api import AuthManager
from dhanada.auth.config import AuthConfig
from dhanada.auth.fastapi.router import auth_router
from dhanada.auth.rate_limit import limiter
from dhanada.crm.fastapi.router import crm_router

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL = 900  # 15 minutes


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    config = AuthConfig()  # type: ignore[call-arg]
    auth = AuthManager(config)

    async def cleanup_loop() -> None:
        while True:
            try:
                await asyncio.sleep(_CLEANUP_INTERVAL)
                count = await auth.cleanup_expired_users()
                if count:
                    logger.info("Cleaned up %d expired inactive accounts", count)
            except Exception:
                logger.exception("Error during expired user cleanup")

    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    await auth.close()


app = FastAPI(title="Dhanada", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(crm_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
