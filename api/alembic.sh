#!/bin/bash

docker compose exec --user $(id -u):$(id -g) -e UV_CACHE_DIR=/tmp/uv-cache api uv run --no-sync alembic -c ../alembic.ini "$@"
