"""FastAPI application factory for Wine Agent."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from wine_agent.db.engine import init_db

# Load .env file from project root
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# Static file directory
STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Wine Agent",
        description="A local-first app for capturing and managing wine tasting notes",
        version="0.1.0",
    )

    # Initialize database tables
    init_db()

    # Mount static files
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Include routers (import here to avoid circular imports)
    from wine_agent.web.routes import analytics, calibration, export, flight, inbox, library, notes, settings

    app.include_router(inbox.router)
    app.include_router(notes.router)
    app.include_router(library.router)
    app.include_router(export.router)
    app.include_router(analytics.router)
    app.include_router(calibration.router)
    app.include_router(flight.router)
    app.include_router(settings.router)

    return app


# Application instance
app = create_app()
