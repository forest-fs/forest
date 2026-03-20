#!/bin/sh
# Apply migrations against DATABASE_URL, then start the Forest process (bot + HTTP).
set -e
cd /app
poetry run alembic upgrade head
exec poetry run forest
