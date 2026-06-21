"""Dhanada FastAPI application."""

from fastapi import FastAPI

from dhanada.auth.fastapi.router import auth_router
from dhanada.crm.fastapi.router import crm_router

app = FastAPI(title="Dhanada", version="0.1.0")

app.include_router(auth_router, prefix="/api/auth")
app.include_router(crm_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}