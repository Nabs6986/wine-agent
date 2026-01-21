# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wine Agent is a local-first desktop application for capturing, structuring, and managing wine tasting notes with AI-assisted conversion. Built with Python 3.11+, FastAPI, SQLAlchemy, and Jinja2 templates with HTMX for interactivity.

## Common Commands

```bash
# Development
pip install -e ".[dev,ai,ingestion]"    # Install with all dependencies
wine-agent run --reload                  # Start dev server with auto-reload
wine-agent check-config                  # Verify environment setup

# Testing
pytest                                   # Run all tests
pytest tests/test_schema.py -v           # Run specific test file
pytest --cov=wine_agent                  # Run with coverage
pytest -k "test_convert" -vv             # Run tests matching pattern

# Code Quality
ruff check .                             # Lint
ruff check . --fix                       # Auto-fix lint issues
mypy wine_agent                          # Type checking

# Database
alembic upgrade head                     # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
wine-agent init-db                       # Initialize database

# Infrastructure (for ingestion pipeline)
docker-compose up -d                     # Start Meilisearch + Redis
docker-compose down                      # Stop services
```

## Architecture

### Layer Structure
- **core/**: Pure domain models (Pydantic v2) - no infrastructure dependencies
  - `schema.py`: Basic tasting note schema for user captures
  - `schema_canonical.py`: Extended canonical schema for wine catalog
  - `scoring.py`: 100-point composite scoring logic
- **db/**: Database layer with repository pattern
  - All database access flows through repositories, never access models directly from routes
  - `migrations/versions/`: Alembic versioned migrations
- **services/**: Application services layer
  - `ai/`: Provider abstraction (Anthropic/OpenAI) with bounded retry JSON repair loop
  - Each service encapsulates specific business logic (analytics, calibration, export, publishing)
- **web/**: FastAPI application with server-rendered Jinja2 templates
  - Routes return `TemplateResponse` with context data
  - HTMX handles interactive forms without page reloads
- **cli/**: Typer CLI commands
- **ingestion/**: Wine catalog ingestion pipeline (adapters, crawler, normalizer, resolver)

### Key Patterns
- **Repository Pattern**: All CRUD through `repositories.py` / `repositories_canonical.py`
- **Session Management**: Use `with get_session() as session:` context manager
- **UUID Identifiers**: All entities use UUID4 string IDs
- **Datetime Handling**: Always `datetime.now(UTC)` for timezone-aware timestamps, stored in UTC
- **AI Provider Abstraction**: `AIClient` with provider interface - prompts versioned (`PROMPT_VERSION`) for reproducibility
- **JSON in DB**: Some columns store JSON-serialized data (`tags_json`, `data_json`)

### Data Flow
1. User pastes raw notes → InboxItem created
2. Convert → AI provider extracts structured data → TastingNote draft + AIConversionRun record
3. User edits draft (40+ fields) → scores calculated
4. Publish → immutable Revision record created
5. Published notes indexed in FTS5 → searchable in Library

## Testing

Tests are in `tests/` directory with comprehensive coverage:
- Schema validation: `test_schema.py`, `test_schema_canonical.py`
- Database operations: `test_db.py`, `test_db_canonical.py`
- AI conversion: `test_ai_conversion.py`
- Services: `test_analytics.py`, `test_calibration.py`, `test_export.py`
- Web routes: `test_web.py`
- Ingestion pipeline: `test_ingestion_*.py`

## Configuration

Environment variables in `.env` (see `.env.example`):
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` for AI conversion
- `AI_PROVIDER`: `anthropic` (default) or `openai`
- `DATABASE_URL`: defaults to `~/.wine_agent/wine_agent.db`
- Ingestion: `REDIS_HOST`, `MEILISEARCH_URL`, `SOURCES_CONFIG_PATH`

## Scoring System

100-point composite from 7 subscores: Appearance (0-2), Nose (0-12), Palate (0-20), Structure & Balance (0-20), Finish (0-10), Typicity & Complexity (0-16), Overall Judgment (0-20). Logic in `core/scoring.py`.
