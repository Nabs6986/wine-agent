"""Flight comparison routes for Wine Agent."""

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from wine_agent.db.engine import get_session
from wine_agent.db.search import SearchFilters, SearchRepository
from wine_agent.db.repositories import TastingNoteRepository
from wine_agent.web.templates_config import templates

router = APIRouter(prefix="/flight", tags=["flight"])


def _parse_int(value: str) -> int | None:
    """Parse a string to int, returning None for empty strings."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@router.get("", response_class=HTMLResponse)
async def flight_select(
    request: Request,
    region: str = "",
    vintage_min: str = "",
    vintage_max: str = "",
) -> HTMLResponse:
    """
    Flight selection page.

    Shows recent published notes with checkboxes for selection.

    Args:
        request: The FastAPI request object.
        region: Optional region filter.
        vintage_min: Optional minimum vintage filter.
        vintage_max: Optional maximum vintage filter.
    """
    # Parse integer fields
    vintage_min_int = _parse_int(vintage_min)
    vintage_max_int = _parse_int(vintage_max)

    with get_session() as session:
        search_repo = SearchRepository(session)

        # Build filters
        filters = SearchFilters(
            region=region if region else None,
            vintage_min=vintage_min_int,
            vintage_max=vintage_max_int,
            status="published",
        )

        # Get recent notes for selection (up to 50)
        result = search_repo.search(filters=filters, limit=50, offset=0)

        # Get filter options for dropdowns
        filter_options = search_repo.get_filter_options()

    return templates.TemplateResponse(
        request=request,
        name="flight/select.html",
        context={
            "notes": result.notes,
            "total_count": result.total_count,
            "filter_options": filter_options,
            "current_filters": {
                "region": region,
                "vintage_min": vintage_min_int,
                "vintage_max": vintage_max_int,
            },
        },
    )


@router.get("/compare", response_class=HTMLResponse)
async def flight_compare(
    request: Request,
    ids: str = Query(..., description="Comma-separated note IDs"),
) -> HTMLResponse:
    """
    Flight comparison view.

    Shows selected notes side-by-side for comparison.

    Args:
        request: The FastAPI request object.
        ids: Comma-separated list of note UUIDs to compare.
    """
    note_ids = [id.strip() for id in ids.split(",") if id.strip()]

    if len(note_ids) < 2:
        return HTMLResponse(
            content="<p>Please select at least 2 notes to compare.</p>",
            status_code=400,
        )

    if len(note_ids) > 4:
        note_ids = note_ids[:4]  # Limit to 4 notes

    with get_session() as session:
        repo = TastingNoteRepository(session)

        notes = []
        for note_id in note_ids:
            note = repo.get_by_id(note_id)
            if note:
                notes.append(note)

    if len(notes) < 2:
        return HTMLResponse(
            content="<p>Could not find enough notes to compare.</p>",
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="flight/compare.html",
        context={
            "notes": notes,
            "note_count": len(notes),
        },
    )
