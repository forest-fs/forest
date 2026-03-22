"""
Process entrypoint: HTTP server (Uvicorn) serving Slack webhooks and health routes.
"""

import logging
import sys

import uvicorn

from forest.api.app import create_app
from forest.config import get_settings


def setup_logging() -> None:
    """Configure stdlib logging from ``Settings.log_level`` (default INFO)."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def main() -> None:
    """CLI entrypoint: start the HTTP server."""
    setup_logging()
    log = logging.getLogger("forest.main")
    settings = get_settings()

    try:
        uvicorn.run(
            create_app(),
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
        )
    except KeyboardInterrupt:
        log.info("shutdown requested")


if __name__ == "__main__":
    main()
