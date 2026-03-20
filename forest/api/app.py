"""
FastAPI application: ``/healthz`` (liveness) and ``/ready`` (DB connectivity).

Metrics and full telemetry are explicitly out of scope for the MVP.
"""

from fastapi import FastAPI
from sqlalchemy import text

from forest.db.session import engine


def create_app() -> FastAPI:
    """
    Build and return the FastAPI application instance.

    Returns
    -------
    FastAPI
        Configured app with MVP routes only.

    Notes
    -----
    ``/ready`` performs a trivial ``SELECT 1`` against the configured database.
    It does not validate Discord or OpenRouter connectivity.
    """
    app = FastAPI(title="Forest", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness: process is running (no dependency checks)."""
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        """
        Readiness: database reachable.

        Returns
        -------
        dict[str, str]
            ``{"status": "ready"}`` on success, or ``{"status": "not_ready"}`` if
            the database ping fails.
        """
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return {"status": "not_ready"}
        return {"status": "ready"}

    return app
