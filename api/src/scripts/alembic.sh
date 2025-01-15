#!/bin/bash

ALL_ARGS="$@"
docker compose exec api ash -c "cd ../ && alembic $ALL_ARGS"
