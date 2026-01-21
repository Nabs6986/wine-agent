# Wine Agent

A local-first desktop application for capturing, structuring, and managing wine tasting notes with AI-assisted conversion.

## Features

- **Inbox Capture**: Paste free-form tasting notes for later processing
- **AI Conversion**: Convert unstructured notes to structured format using Claude or GPT
- **Draft Review & Edit**: Full-featured editor with 40+ fields for wine identity, scores, and descriptors
- **Publishing & Revisions**: Publish notes with immutable audit trail
- **Full-Text Search**: Search and filter your library by producer, region, score, vintage, and more
- **Analytics Dashboard**: Score distribution, top regions/producers, descriptor frequency analysis
- **Calibration Tools**: Personal scoring reference and consistency tracking
- **Flight Comparison**: Side-by-side comparison of multiple notes
- **Multi-Format Export**: Export as Markdown, CSV, or JSON
- **Backup & Restore**: CLI commands for data safety

## Requirements

- Python 3.11+
- (Optional) Anthropic or OpenAI API key for AI-powered conversion

## Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd wine-agent

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Start the web server
wine-agent run
```

Open your browser to http://127.0.0.1:8000

## Configuration

### Environment Variables

Create a `.env` file in the project root (or copy `.env.example`):

```bash
# AI Provider Configuration (optional, but required for AI conversion)
ANTHROPIC_API_KEY=your-anthropic-api-key-here
# Or use OpenAI:
# OPENAI_API_KEY=your-openai-api-key-here

# Provider selection (default: anthropic)
AI_PROVIDER=anthropic

# Model override (optional, uses sensible defaults)
# AI_MODEL=claude-3-sonnet-20240229

# Database location (optional, defaults to ~/.wine_agent/wine_agent.db)
# DATABASE_URL=sqlite:///./my_wine_notes.db
```

**Without AI configuration**: The app works fully, but "Convert" will create placeholder drafts you fill in manually.

**With AI configuration**: Converting inbox items uses the LLM to extract structured data from your raw notes.

## CLI Commands

```bash
# Start the web server
wine-agent run [--host HOST] [--port PORT] [--reload]

# Create a timestamped database backup
wine-agent backup [--output-dir PATH] [--include-exports]

# Restore database from a backup file
wine-agent restore <backup-path> [--force]

# Initialize the database (usually automatic)
wine-agent init-db

# Check configuration status
wine-agent check-config

# Show version
wine-agent version
```

### Backup & Restore

**Create a backup:**
```bash
# Basic backup (database only)
wine-agent backup

# Backup with JSON and CSV exports
wine-agent backup --include-exports

# Backup to specific directory
wine-agent backup --output-dir /path/to/backups
```

**Restore from backup:**
```bash
# Interactive restore (prompts for confirmation)
wine-agent restore wine_agent_backup_20240115_143022.db

# Force restore without confirmation
wine-agent restore wine_agent_backup_20240115_143022.db --force
```

Note: Restore automatically creates a safety backup of your current database before overwriting.

## User Workflow

### 1. Capture Notes
Navigate to **Inbox** and paste your raw tasting notes. Add optional tags like "to research" or "restaurant".

### 2. Convert to Structured Format
Click **Convert** on an inbox item to process it with AI (or create a placeholder draft if AI is not configured).

### 3. Review and Edit
The draft editor shows all fields organized by category:
- Wine identity (producer, vintage, region, grapes)
- Scores (7 subscores totaling 100 points)
- Structure levels (acidity, tannin, body, etc.)
- Tasting notes (nose, palate, finish)
- Readiness assessment

### 4. Publish
Once reviewed, click **Publish** to finalize the note. Published notes are immutable with full revision history.

### 5. Search and Analyze
Use the **Library** to search and filter your collection. View insights in the **Analytics** dashboard.

## Web Interface

| Page | Path | Description |
|------|------|-------------|
| Inbox | `/inbox` | Raw note capture and conversion |
| Notes | `/notes` | List all draft and published notes |
| Library | `/library` | Search and filter published notes |
| Analytics | `/analytics` | Score distribution, top regions, trends |
| Calibration | `/calibration` | Personal scoring reference |
| Flight | `/flight` | Side-by-side note comparison |
| Settings | `/settings` | Configuration status and CLI help |

## Scoring System

Total score (0-100) is computed from 7 subscores:

| Component | Range | Description |
|-----------|-------|-------------|
| Appearance | 0-2 | Clarity, intensity, hue |
| Nose | 0-12 | Aromas, condition, development |
| Palate | 0-20 | Flavors, texture, balance |
| Structure & Balance | 0-20 | Integration, harmony |
| Finish | 0-10 | Length and quality |
| Typicity & Complexity | 0-16 | Regional character, layers |
| Overall Judgment | 0-20 | Holistic quality assessment |

**Quality Bands:**
- 95-100: Outstanding
- 90-94: Very Good
- 80-89: Good
- 70-79: Acceptable
- 0-69: Poor

## Project Structure

```
wine_agent/
├── core/               # Domain models and business logic
│   ├── enums.py        # Wine-related enumerations
│   ├── schema.py       # Canonical Pydantic models
│   └── scoring.py      # Score calculation and validation
├── db/                 # Database layer
│   ├── engine.py       # SQLite engine and session management
│   ├── models.py       # SQLAlchemy ORM models
│   ├── repositories.py # Repository pattern CRUD operations
│   ├── search.py       # Full-text search with FTS5
│   └── migrations/     # Alembic migration scripts
├── services/           # Application services
│   ├── ai/             # AI conversion pipeline
│   │   ├── client.py   # Provider abstraction
│   │   ├── conversion.py # Conversion orchestration
│   │   ├── prompts.py  # LLM prompts
│   │   └── providers/  # Anthropic, OpenAI implementations
│   ├── analytics_service.py
│   ├── calibration_service.py
│   ├── export_service.py
│   └── publishing_service.py
├── web/                # Web application
│   ├── app.py          # FastAPI application factory
│   ├── routes/         # Route handlers
│   ├── templates/      # Jinja2 templates
│   └── static/         # CSS and static assets
└── cli/                # Command-line interface
    └── main.py         # Typer CLI commands

tests/                  # Test suite
├── test_schema.py
├── test_scoring.py
├── test_db.py
├── test_search.py
├── test_ai_conversion.py
├── test_notes.py
├── test_export.py
├── test_analytics.py
├── test_calibration.py
└── test_web.py
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=wine_agent

# Run specific test file
pytest tests/test_schema.py
```

### Code Quality

```bash
# Linting
ruff check .

# Auto-fix linting issues
ruff check . --fix

# Type checking
mypy wine_agent
```

### Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1
```

## Data Storage

- **Database**: SQLite at `~/.wine_agent/wine_agent.db` (configurable via `DATABASE_URL`)
- **Backups**: Created via `wine-agent backup` with timestamps
- **Exports**: JSON, CSV, or Markdown with YAML frontmatter

## API Documentation

When the server is running, interactive API documentation is available at:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Troubleshooting

**AI conversion not working:**
- Check that `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set in `.env`
- Run `wine-agent check-config` to verify configuration
- Check the Settings page in the web UI

**Database not found:**
- Run `wine-agent init-db` to initialize
- Check the database path in Settings

**Search not returning results:**
- Ensure notes are published (drafts are not searchable in Library)
- Try broader search terms

## License

MIT
