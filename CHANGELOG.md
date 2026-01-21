# Changelog

All notable changes to Wine Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-21

### Added

#### Phase 1: Foundation
- Project scaffolding with clean architecture (core/db/services/web/cli)
- Canonical Pydantic v2 schema for tasting notes
- Wine domain enums (color, style, sweetness, structure levels)
- 100-point scoring system with 7 subscores
- pyproject.toml with dependency management

#### Phase 2: Persistence
- SQLite database with SQLAlchemy ORM
- Alembic migration system with 3 migrations
- Repository pattern for data access (Inbox, TastingNote, Revision, AIConversion)
- JSON column storage for flexible structured data

#### Phase 3: Inbox MVP
- FastAPI web application with Jinja2 templates
- Inbox CRUD operations (create, list, view, archive)
- Server-rendered UI with HTMX interactivity
- CLI entry point (`wine-agent run`)

#### Phase 4: AI Conversion
- AI provider abstraction supporting Anthropic and OpenAI
- LLM-powered conversion of raw notes to structured format
- JSON repair loop with bounded retries
- Full traceability with AIConversionRun records
- Graceful fallback to placeholder drafts when AI unavailable

#### Phase 5: Publishing
- Draft note editor with 40+ form fields
- Publish workflow with validation
- Revision history with snapshots
- Auto-calculated scores from subscores

#### Phase 6: Search & Export
- Full-text search using SQLite FTS5
- Multi-filter library view (score, region, grape, producer, vintage)
- Export to Markdown with YAML frontmatter
- Bulk export to CSV and JSON

#### Phase 7: Analytics & Polish
- Analytics dashboard with score distribution
- Top regions/producers/countries rankings
- Descriptor frequency analysis
- Scoring trends over time
- Calibration page for personal scoring reference
- Flight mode for side-by-side note comparison

#### Phase 8: Packaging
- CLI backup command with timestamped database copies
- CLI restore command with safety backup
- Settings UI page showing configuration status
- Comprehensive README documentation
- This changelog

### Technical Details
- Python 3.11+ required
- FastAPI 0.100+ for web framework
- SQLAlchemy 2.0+ for ORM
- Pydantic 2.0+ for data validation
- Typer for CLI interface

## [Unreleased]

### Planned
- Batch operations for inbox items
- Quick-tag UI for inbox list view
- Obsidian vault mode (Markdown file sync)
- Import utilities (CSV/JSON)
- Lightweight cellar/inventory tracking
