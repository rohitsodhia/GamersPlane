# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GamersPlane is a tabletop RPG community platform. The repo has two active sub-projects:

- `api/` — Python/FastAPI backend (async, SQLAlchemy 2.0, PostgreSQL)
- `frontend/` — React 19 SPA using TanStack Start (SSR-capable), TanStack Router, TanStack Query

There is also a `cli/` directory for internal tooling and a `docker/` directory for infrastructure config.

## Development Environment

The full stack runs via Docker Compose. The `compose.sh` wrapper handles environment selection:

```bash
# Start in dev mode (proxy on port 81, API with hot-reload)
./compose.sh -e dev up

# Optional overlays
./compose.sh --email up       # include email (postfix/opendkim)
./compose.sh -o compose.pgadmin.yml up  # include pgAdmin on :8080
```

The API is exposed at `localhost:8000` directly and via nginx proxy.

## API (`api/`)

**Runtime:** Python 3.13, managed with `uv`. All commands run from `api/`.

```bash
# Install dependencies
uv sync

# Run dev server (with hot-reload)
uv run uvicorn --factory main:create_app --host 0.0.0.0 --reload --app-dir src

# Lint
uv run ruff check src/

# Format
uv run ruff format src/

# Run all tests (from api/src/)
cd src && uv run pytest

# Run a single test file
cd src && uv run pytest tests/auth/test_user.py

# Run a single test by name
cd src && uv run pytest tests/auth/test_user.py::test_name
```

Tests use a real PostgreSQL database named `{DATABASE_DATABASE}_test` (drops/recreates tables on each test function). There is no mocking of the database layer.

**Alembic migrations** live in `api/src/alembic/`. Run via `api/src/scripts/alembic.sh`.

## Frontend (`frontend/`)

**Runtime:** Node.js with npm (not pnpm despite pnpm section in package.json).

```bash
# Install dependencies
npm install

# Dev server (port 3000)
npm run dev

# Build
npm run build

# Lint (Biome)
npm run lint

# Format (Biome)
npm run format

# Lint + format + organize imports
npm run check

# Tests (Vitest)
npm test

# Regenerate route tree after adding/removing route files
npm run generate-routes
```

Biome uses tabs for indentation and double quotes for JS/TS strings. The `routeTree.gen.ts` file is auto-generated — never edit it manually.

## API Architecture

### App structure

- `src/app/main.py` — `create_app()` factory; wires middleware, CORS, and routers
- `src/app/configs.py` — `ConfigStore` singleton loaded from env vars via `configs.from_env()`
- `src/app/database.py` — `DatabaseSessionManager` with optional SSH tunnel support for remote DB; `DBSessionDependency` is the FastAPI dependency type alias
- `src/app/middleware.py` — cookie-based auth (`loginHash` cookie) and JWT auth (Bearer token); `AuthedUser` dependency for getting the current user in route handlers
- `src/app/schema_base.py` — `SchemaBase` (Pydantic base class) with a pipeline system for transforming string fields (strip whitespace, nl2br, escape HTML) via `filtered_str()`

### Route organization

Each domain has its own directory under `src/app/` with `routes.py` (new API) and `legacy_routes.py` (compatibility shim for the old PHP frontend). Current domains: `auth`, `characters`, `forums`, `gamers`, `games`, `me`, `permissions`, `pms`, `referral_links`, `systems`, `tools`, `users`.

### Auth flow

All routes require authentication by default. Mark a route handler with `@public` decorator (`app.helpers.decorators`) to allow unauthenticated access. Auth is resolved per-request via `validate_cookie` middleware using a `loginHash` cookie (legacy format: `username|hash`). JWT Bearer auth is also implemented but currently commented out in `create_app()`.

### Models

- `src/app/models/base.py` defines `Base` (SQLAlchemy `DeclarativeBase`), `SoftDeleteMixin` (adds `deleted` timestamp; automatically filtered from all SELECTs via a session event listener), and `TimestampMixin` (`created_at`, `updated_at`)
- `src/app/models/legacy/` — read-only models mapping to the existing MySQL/PostgreSQL schema from the legacy PHP app; used by legacy routes
- `src/app/models/` (non-legacy) — new normalized models for the rebuilt API

### Repositories

`src/app/repositories/` contains data access classes. `legacy/` subdirectory holds repositories for the legacy schema.

## Frontend Architecture

Uses **TanStack Start** (SSR-capable React framework built on Vite + Nitro) with file-based routing.

- `src/routes/__root.tsx` — root layout: `<Header>`, `<main class="page-wrap">`, `<Footer>`; attaches global CSS and TanStack devtools
- `src/router.tsx` — creates the router with TanStack Query integration via `setupRouterSsrQueryIntegration`
- `src/routes/` — file-based routes; each file exports a `Route` object; the router CLI generates `routeTree.gen.ts` from this directory
- `src/integrations/tanstack-query/root-provider.tsx` — provides `QueryClient` as router context
- Path aliases: `#/*` maps to `src/*` (configured in `package.json` imports and `tsconfig.json`)

The React Compiler is enabled via Babel plugin (`babel-plugin-react-compiler`) — avoid manual `useMemo`/`useCallback` unless there's a specific reason the compiler can't optimize it.
