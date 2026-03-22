#!/bin/sh
# Apply migrations against DATABASE_URL, then start the Forest HTTP server.
set -e
cd /app
poetry run alembic upgrade head
exec poetry run forest
