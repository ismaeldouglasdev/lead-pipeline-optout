"""Opt-out service — public unsubscribe endpoint (LGPD / RFC 8058).

Standalone FastAPI app deployed to Render (free tier). The private
lead-pipeline polls /api/optouts to sync opt-outs into its own DB.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.db import engine
from app.models import Base
from app.routes.optout import router as optout_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the optouts table on startup (idempotent).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Lead Pipeline Opt-Out",
    description="Public unsubscribe endpoint (LGPD / RFC 8058 one-click).",
    version="1.0.0",
    lifespan=lifespan,
)

# Only allow requests with a known Host header (Starlette >= 1.x: `*.domain` wildcard).
allowed_hosts = [
    "localhost",
    "127.0.0.1",
    "*.onrender.com",
    "*.ismaeltech.com",
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

app.include_router(optout_router)
