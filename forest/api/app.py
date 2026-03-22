"""
FastAPI application: health endpoints and Slack webhook routes.
"""

from fastapi import FastAPI
from sqlalchemy import text

from forest.api.slack_routes import router as slack_router
from forest.db.session import engine


def create_app() -> FastAPI:
    """
    Build and return the FastAPI application instance.

    Includes health/readiness probes and Slack Events API routes.
    """
    app = FastAPI(title="Forest", version="0.1.0")
    app.include_router(slack_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        """Human-friendly entry when curling the tunnel or load-balancer root."""
        return {"service": "forest", "healthz": "/healthz", "ready": "/ready"}

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness: process is running (no dependency checks)."""
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        """Readiness: database reachable."""
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return {"status": "not_ready"}
        return {"status": "ready"}

    return app
