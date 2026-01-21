"""Settings routes for Wine Agent configuration."""

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from wine_agent.db.engine import get_database_url, get_session
from wine_agent.db.repositories import InboxRepository, TastingNoteRepository
from wine_agent.web.templates_config import templates

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_db_path() -> Path:
    """Get the current database file path."""
    url = get_database_url()
    if url.startswith("sqlite:///"):
        return Path(url[10:])
    return Path(url)


def _get_ai_status() -> dict:
    """Get AI provider configuration status."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    provider = os.environ.get("AI_PROVIDER", "anthropic")

    if anthropic_key and anthropic_key != "your-anthropic-api-key-here":
        return {
            "configured": True,
            "provider": "Anthropic",
            "key_preview": f"{anthropic_key[:8]}...{anthropic_key[-4:]}" if len(anthropic_key) > 12 else "***",
        }
    elif openai_key and openai_key != "your-openai-api-key-here":
        return {
            "configured": True,
            "provider": "OpenAI",
            "key_preview": f"{openai_key[:8]}...{openai_key[-4:]}" if len(openai_key) > 12 else "***",
        }
    else:
        return {
            "configured": False,
            "provider": None,
            "key_preview": None,
        }


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


@router.get("", response_class=HTMLResponse)
async def settings_index(request: Request) -> HTMLResponse:
    """
    Settings and configuration page.

    Shows AI provider status, database info, and application configuration.

    Args:
        request: The FastAPI request object.

    Returns:
        Rendered settings template.
    """
    # AI configuration status
    ai_status = _get_ai_status()

    # Database information
    db_path = _get_db_path()
    db_exists = db_path.exists()
    db_size = _format_size(db_path.stat().st_size) if db_exists else "N/A"

    # Database statistics
    db_stats = {
        "inbox_items": 0,
        "draft_notes": 0,
        "published_notes": 0,
    }
    if db_exists:
        with get_session() as session:
            inbox_repo = InboxRepository(session)
            note_repo = TastingNoteRepository(session)

            all_inbox = inbox_repo.list_all(include_converted=True)
            db_stats["inbox_items"] = len(all_inbox)

            all_notes = note_repo.list_all()
            db_stats["draft_notes"] = sum(1 for n in all_notes if n.status.value == "draft")
            db_stats["published_notes"] = sum(1 for n in all_notes if n.status.value == "published")

    # Environment configuration
    env_config = {
        "AI_PROVIDER": os.environ.get("AI_PROVIDER", "anthropic (default)"),
        "AI_MODEL": os.environ.get("AI_MODEL", "auto-detect"),
    }

    return templates.TemplateResponse(
        request=request,
        name="settings/index.html",
        context={
            "ai_status": ai_status,
            "db_path": str(db_path),
            "db_exists": db_exists,
            "db_size": db_size,
            "db_stats": db_stats,
            "env_config": env_config,
            "version": "0.1.0",
        },
    )
