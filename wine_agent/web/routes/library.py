"""Library routes for searching and browsing tasting notes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from wine_agent.db.engine import get_session
from wine_agent.db.search import SearchFilters, SearchRepository
from wine_agent.web.templates_config import templates

router = APIRouter(prefix="/library", tags=["library"])


def _parse_int(value: str) -> int | None:
    """Parse a string to int, returning None for empty strings."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@router.get("", response_class=HTMLResponse)
async def library_index(
    request: Request,
    q: str = "",
    score_min: str = "",
    score_max: str = "",
    region: str = "",
    country: str = "",
    grape: str = "",
    producer: str = "",
    vintage_min: str = "",
    vintage_max: str = "",
    drink_or_hold: str = "",
    status: str = "published",
    page: int = 1,
    per_page: int = 20,
) -> HTMLResponse:
    """
    Library search page with filters.

    Args:
        request: The FastAPI request object.
        q: Text search query.
        score_min: Minimum score filter.
        score_max: Maximum score filter.
        region: Region filter.
        country: Country filter.
        grape: Grape variety filter.
        producer: Producer filter.
        vintage_min: Minimum vintage year.
        vintage_max: Maximum vintage year.
        drink_or_hold: Readiness filter.
        status: Status filter (draft/published/all).
        page: Page number (1-indexed).
        per_page: Results per page.

    Returns:
        Rendered library template with search results.
    """
    # Parse integer fields
    score_min_int = _parse_int(score_min)
    score_max_int = _parse_int(score_max)
    vintage_min_int = _parse_int(vintage_min)
    vintage_max_int = _parse_int(vintage_max)

    with get_session() as session:
        search_repo = SearchRepository(session)

        # Build filters
        filters = SearchFilters(
            query=q if q else None,
            score_min=score_min_int,
            score_max=score_max_int,
            region=region if region else None,
            country=country if country else None,
            grape=grape if grape else None,
            producer=producer if producer else None,
            vintage_min=vintage_min_int,
            vintage_max=vintage_max_int,
            drink_or_hold=drink_or_hold if drink_or_hold else None,
            status=status,
        )

        # Calculate offset from page
        offset = (page - 1) * per_page

        # Execute search
        result = search_repo.search(filters=filters, limit=per_page, offset=offset)

        # Get filter options for dropdowns
        filter_options = search_repo.get_filter_options()

    # Build current filters dict for template
    current_filters = {
        "q": q,
        "score_min": score_min_int,
        "score_max": score_max_int,
        "region": region,
        "country": country,
        "grape": grape,
        "producer": producer,
        "vintage_min": vintage_min_int,
        "vintage_max": vintage_max_int,
        "drink_or_hold": drink_or_hold,
        "status": status,
        "page": page,
        "per_page": per_page,
    }

    return templates.TemplateResponse(
        request=request,
        name="library/index.html",
        context={
            "notes": result.notes,
            "total_count": result.total_count,
            "page": result.page,
            "total_pages": result.total_pages,
            "has_more": result.has_more,
            "filters": current_filters,
            "filter_options": filter_options,
        },
    )


@router.get("/results", response_class=HTMLResponse)
async def library_results(
    request: Request,
    q: str = "",
    score_min: str = "",
    score_max: str = "",
    region: str = "",
    country: str = "",
    grape: str = "",
    producer: str = "",
    vintage_min: str = "",
    vintage_max: str = "",
    drink_or_hold: str = "",
    status: str = "published",
    page: int = 1,
    per_page: int = 20,
) -> HTMLResponse:
    """
    HTMX partial endpoint for search results.

    Returns only the results portion for dynamic updates.
    """
    # Parse integer fields
    score_min_int = _parse_int(score_min)
    score_max_int = _parse_int(score_max)
    vintage_min_int = _parse_int(vintage_min)
    vintage_max_int = _parse_int(vintage_max)

    with get_session() as session:
        search_repo = SearchRepository(session)

        filters = SearchFilters(
            query=q if q else None,
            score_min=score_min_int,
            score_max=score_max_int,
            region=region if region else None,
            country=country if country else None,
            grape=grape if grape else None,
            producer=producer if producer else None,
            vintage_min=vintage_min_int,
            vintage_max=vintage_max_int,
            drink_or_hold=drink_or_hold if drink_or_hold else None,
            status=status,
        )

        offset = (page - 1) * per_page
        result = search_repo.search(filters=filters, limit=per_page, offset=offset)

    current_filters = {
        "q": q,
        "score_min": score_min_int,
        "score_max": score_max_int,
        "region": region,
        "country": country,
        "grape": grape,
        "producer": producer,
        "vintage_min": vintage_min_int,
        "vintage_max": vintage_max_int,
        "drink_or_hold": drink_or_hold,
        "status": status,
        "page": page,
        "per_page": per_page,
    }

    return templates.TemplateResponse(
        request=request,
        name="library/results.html",
        context={
            "notes": result.notes,
            "total_count": result.total_count,
            "page": result.page,
            "total_pages": result.total_pages,
            "has_more": result.has_more,
            "filters": current_filters,
        },
    )
