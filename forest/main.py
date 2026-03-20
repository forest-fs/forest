"""
Process entrypoint: logging, concurrent HTTP (Uvicorn) and Discord bot.

The MVP runs FastAPI and ``discord.py`` in a single asyncio loop so they share
``Settings``, the database engine, and the in-memory ingest queue owned by the bot.
"""

import asyncio
import logging
import sys

import uvicorn

from forest.api.app import create_app
from forest.config import get_settings
from forest.platforms.discord.bot import create_bot, run_bot


def setup_logging() -> None:
    """
    Configure stdlib logging from ``Settings.log_level`` (default INFO).

    Notes
    -----
    Uses a single stream handler to stdout; structured fields are attached
    elsewhere via ``logging`` ``extra=`` at call sites (MVP).
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


async def run_http() -> None:
    """
    Run Uvicorn with the FastAPI app from :func:`forest.api.app.create_app`.

    Returns
    -------
    None
        This coroutine runs until the server is stopped (typically never returns
        in normal operation).
    """
    settings = get_settings()
    config = uvicorn.Config(
        create_app(),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """
    CLI entrypoint: start Discord bot and HTTP server together.

    Notes
    -----
    ``KeyboardInterrupt`` is handled to exit cleanly without a traceback spam
    at shutdown.
    """
    setup_logging()
    log = logging.getLogger("forest.main")

    async def _run() -> None:
        bot = create_bot()
        await asyncio.gather(
            run_bot(bot),
            run_http(),
        )

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        log.info("shutdown requested")


if __name__ == "__main__":
    main()
