"""Catalog routes for searching and managing canonical wine entities."""

from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from wine_agent.core.schema_canonical import CatalogSearchRequest
from wine_agent.db.engine import get_session
from wine_agent.services.catalog_service import get_catalog_service
from wine_agent.web.templates_config import templates

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _parse_int(value: str | None) -> int | None:
    """Parse a string to int, returning None for empty strings."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ============================================================================
# HTML Routes (for web UI)
# ============================================================================


@router.get("", response_class=HTMLResponse)
async def catalog_index(
    request: Request,
    q: str = "",
    producer: str = "",
    country: str = "",
    region: str = "",
    grape: str = "",
    vintage: str = "",
    page: int = 1,
    per_page: int = 20,
) -> HTMLResponse:
    """
    Catalog search page.

    Search the canonical wine catalog with filters.
    """
    vintage_int = _parse_int(vintage)

    with get_session() as session:
        service = get_catalog_service(session)

        search_request = CatalogSearchRequest(
            query=q,
            producer=producer if producer else None,
            country=country if country else None,
            region=region if region else None,
            grape=grape if grape else None,
            vintage_year=vintage_int,
            page=page,
            page_size=per_page,
        )

        results, total_count = service.search_catalog(search_request)
        stats = service.get_catalog_stats()

    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    current_filters = {
        "q": q,
        "producer": producer,
        "country": country,
        "region": region,
        "grape": grape,
        "vintage": vintage_int,
        "page": page,
        "per_page": per_page,
    }

    return templates.TemplateResponse(
        request=request,
        name="catalog/index.html",
        context={
            "results": results,
            "total_count": total_count,
            "page": page,
            "total_pages": total_pages,
            "has_more": page < total_pages,
            "filters": current_filters,
            "stats": stats,
        },
    )


@router.get("/results", response_class=HTMLResponse)
async def catalog_results(
    request: Request,
    q: str = "",
    producer: str = "",
    country: str = "",
    region: str = "",
    grape: str = "",
    vintage: str = "",
    page: int = 1,
    per_page: int = 20,
) -> HTMLResponse:
    """HTMX partial endpoint for catalog search results."""
    vintage_int = _parse_int(vintage)

    with get_session() as session:
        service = get_catalog_service(session)

        search_request = CatalogSearchRequest(
            query=q,
            producer=producer if producer else None,
            country=country if country else None,
            region=region if region else None,
            grape=grape if grape else None,
            vintage_year=vintage_int,
            page=page,
            page_size=per_page,
        )

        results, total_count = service.search_catalog(search_request)

    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    current_filters = {
        "q": q,
        "producer": producer,
        "country": country,
        "region": region,
        "grape": grape,
        "vintage": vintage_int,
        "page": page,
        "per_page": per_page,
    }

    return templates.TemplateResponse(
        request=request,
        name="catalog/results.html",
        context={
            "results": results,
            "total_count": total_count,
            "page": page,
            "total_pages": total_pages,
            "has_more": page < total_pages,
            "filters": current_filters,
        },
    )


@router.get("/producers/new", response_class=HTMLResponse)
async def new_producer_form(request: Request) -> HTMLResponse:
    """Form to create a new producer."""
    return templates.TemplateResponse(
        request=request,
        name="catalog/producer_form.html",
        context={"producer": None},
    )


@router.post("/producers", response_class=HTMLResponse)
async def create_producer(
    request: Request,
    canonical_name: str = Form(...),
    country: str = Form(""),
    region: str = Form(""),
    website: str = Form(""),
    aliases: str = Form(""),
) -> HTMLResponse:
    """Create a new canonical producer."""
    with get_session() as session:
        service = get_catalog_service(session)

        # Parse aliases from comma-separated string
        alias_list = [a.strip() for a in aliases.split(",") if a.strip()] if aliases else []

        producer = service.create_producer(
            canonical_name=canonical_name,
            country=country,
            region=region,
            website=website,
            aliases=alias_list,
        )

    return templates.TemplateResponse(
        request=request,
        name="catalog/producer_created.html",
        context={"producer": producer},
    )


@router.get("/wines/new", response_class=HTMLResponse)
async def new_wine_form(
    request: Request,
    producer_id: str = "",
) -> HTMLResponse:
    """Form to create a new wine."""
    producer = None
    if producer_id:
        with get_session() as session:
            service = get_catalog_service(session)
            producer = service.get_producer(producer_id)

    return templates.TemplateResponse(
        request=request,
        name="catalog/wine_form.html",
        context={"wine": None, "producer": producer},
    )


@router.post("/wines", response_class=HTMLResponse)
async def create_wine(
    request: Request,
    producer_id: str = Form(...),
    canonical_name: str = Form(...),
    color: str = Form(""),
    style: str = Form(""),
    appellation: str = Form(""),
    grapes: str = Form(""),
    aliases: str = Form(""),
) -> HTMLResponse:
    """Create a new canonical wine."""
    with get_session() as session:
        service = get_catalog_service(session)

        # Parse grapes and aliases from comma-separated strings
        grape_list = [g.strip() for g in grapes.split(",") if g.strip()] if grapes else []
        alias_list = [a.strip() for a in aliases.split(",") if a.strip()] if aliases else []

        wine = service.create_wine(
            producer_id=producer_id,
            canonical_name=canonical_name,
            color=color if color else None,
            style=style if style else None,
            appellation=appellation,
            grapes=grape_list,
            aliases=alias_list,
        )

        producer = service.get_producer(producer_id)

    return templates.TemplateResponse(
        request=request,
        name="catalog/wine_created.html",
        context={"wine": wine, "producer": producer},
    )


@router.get("/vintages/new", response_class=HTMLResponse)
async def new_vintage_form(
    request: Request,
    wine_id: str = "",
) -> HTMLResponse:
    """Form to create a new vintage."""
    wine = None
    producer = None
    if wine_id:
        with get_session() as session:
            service = get_catalog_service(session)
            wine = service.get_wine(wine_id)
            if wine:
                producer = service.get_producer(wine.producer_id)

    return templates.TemplateResponse(
        request=request,
        name="catalog/vintage_form.html",
        context={"vintage": None, "wine": wine, "producer": producer},
    )


@router.post("/vintages", response_class=HTMLResponse)
async def create_vintage(
    request: Request,
    wine_id: str = Form(...),
    year: int = Form(...),
    bottle_size_ml: int = Form(750),
    abv: str = Form(""),
) -> HTMLResponse:
    """Create a new canonical vintage."""
    with get_session() as session:
        service = get_catalog_service(session)

        abv_float = float(abv) if abv else None

        vintage = service.create_vintage(
            wine_id=wine_id,
            year=year,
            bottle_size_ml=bottle_size_ml,
            abv=abv_float,
        )

        wine = service.get_wine(wine_id)
        producer = service.get_producer(wine.producer_id) if wine else None

    return templates.TemplateResponse(
        request=request,
        name="catalog/vintage_created.html",
        context={"vintage": vintage, "wine": wine, "producer": producer},
    )


@router.get("/stats", response_class=HTMLResponse)
async def catalog_stats(request: Request) -> HTMLResponse:
    """Display catalog statistics."""
    with get_session() as session:
        service = get_catalog_service(session)
        stats = service.get_catalog_stats()
        meilisearch_stats = service.meilisearch.get_stats()

    return templates.TemplateResponse(
        request=request,
        name="catalog/stats.html",
        context={"stats": stats, "meilisearch_stats": meilisearch_stats},
    )


# ============================================================================
# JSON API Routes (for programmatic access)
# ============================================================================


@router.get("/api/search")
async def api_search_catalog(
    q: str = "",
    producer: str = "",
    country: str = "",
    region: str = "",
    grape: str = "",
    vintage: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> JSONResponse:
    """
    API endpoint to search the wine catalog.

    Returns JSON results for programmatic access.
    """
    with get_session() as session:
        service = get_catalog_service(session)

        search_request = CatalogSearchRequest(
            query=q,
            producer=producer if producer else None,
            country=country if country else None,
            region=region if region else None,
            grape=grape if grape else None,
            vintage_year=vintage,
            page=page,
            page_size=page_size,
        )

        results, total_count = service.search_catalog(search_request)

    return JSONResponse({
        "results": results,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
    })


@router.get("/api/producers/{producer_id}")
async def api_get_producer(producer_id: str) -> JSONResponse:
    """Get a producer by ID."""
    with get_session() as session:
        service = get_catalog_service(session)
        producer = service.get_producer(producer_id)

        if not producer:
            raise HTTPException(status_code=404, detail="Producer not found")

        wines = service.get_wines_by_producer(producer_id)

    return JSONResponse({
        "producer": producer.model_dump(mode="json"),
        "wines": [w.model_dump(mode="json") for w in wines],
    })


@router.get("/api/wines/{wine_id}")
async def api_get_wine(wine_id: str) -> JSONResponse:
    """Get a wine by ID."""
    with get_session() as session:
        service = get_catalog_service(session)
        wine = service.get_wine(wine_id)

        if not wine:
            raise HTTPException(status_code=404, detail="Wine not found")

        producer = service.get_producer(wine.producer_id)
        vintages = service.get_vintages_by_wine(wine_id)

    return JSONResponse({
        "wine": wine.model_dump(mode="json"),
        "producer": producer.model_dump(mode="json") if producer else None,
        "vintages": [v.model_dump(mode="json") for v in vintages],
    })


@router.get("/api/vintages/{vintage_id}")
async def api_get_vintage(vintage_id: str) -> JSONResponse:
    """Get a vintage by ID."""
    with get_session() as session:
        service = get_catalog_service(session)
        vintage = service.get_vintage(vintage_id)

        if not vintage:
            raise HTTPException(status_code=404, detail="Vintage not found")

        wine = service.get_wine(vintage.wine_id)
        producer = service.get_producer(wine.producer_id) if wine else None

    return JSONResponse({
        "vintage": vintage.model_dump(mode="json"),
        "wine": wine.model_dump(mode="json") if wine else None,
        "producer": producer.model_dump(mode="json") if producer else None,
    })


@router.post("/api/producers")
async def api_create_producer(
    canonical_name: str = Form(...),
    country: str = Form(""),
    region: str = Form(""),
    website: str = Form(""),
    aliases: str = Form(""),
    wikidata_id: str = Form(""),
) -> JSONResponse:
    """Create a new producer via API."""
    with get_session() as session:
        service = get_catalog_service(session)

        alias_list = [a.strip() for a in aliases.split(",") if a.strip()] if aliases else []

        producer = service.create_producer(
            canonical_name=canonical_name,
            country=country,
            region=region,
            website=website,
            aliases=alias_list,
            wikidata_id=wikidata_id if wikidata_id else None,
        )

    return JSONResponse({"producer": producer.model_dump(mode="json")}, status_code=201)


@router.post("/api/wines")
async def api_create_wine(
    producer_id: str = Form(...),
    canonical_name: str = Form(...),
    color: str = Form(""),
    style: str = Form(""),
    appellation: str = Form(""),
    grapes: str = Form(""),
    aliases: str = Form(""),
) -> JSONResponse:
    """Create a new wine via API."""
    with get_session() as session:
        service = get_catalog_service(session)

        grape_list = [g.strip() for g in grapes.split(",") if g.strip()] if grapes else []
        alias_list = [a.strip() for a in aliases.split(",") if a.strip()] if aliases else []

        wine = service.create_wine(
            producer_id=producer_id,
            canonical_name=canonical_name,
            color=color if color else None,
            style=style if style else None,
            appellation=appellation,
            grapes=grape_list,
            aliases=alias_list,
        )

    return JSONResponse({"wine": wine.model_dump(mode="json")}, status_code=201)


@router.post("/api/vintages")
async def api_create_vintage(
    wine_id: str = Form(...),
    year: int = Form(...),
    bottle_size_ml: int = Form(750),
    abv: float | None = Form(None),
) -> JSONResponse:
    """Create a new vintage via API."""
    with get_session() as session:
        service = get_catalog_service(session)

        vintage = service.create_vintage(
            wine_id=wine_id,
            year=year,
            bottle_size_ml=bottle_size_ml,
            abv=abv,
        )

    return JSONResponse({"vintage": vintage.model_dump(mode="json")}, status_code=201)


@router.post("/api/tastings/{tasting_id}/link")
async def api_link_tasting(
    tasting_id: str,
    vintage_id: str = Form(None),
    wine_id: str = Form(None),
) -> JSONResponse:
    """
    Link a tasting note to a canonical vintage or wine.

    Provide either vintage_id (preferred) or wine_id.
    """
    if not vintage_id and not wine_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide either vintage_id or wine_id",
        )

    with get_session() as session:
        service = get_catalog_service(session)

        if vintage_id:
            success = service.link_tasting_to_vintage(tasting_id, vintage_id)
        else:
            success = service.link_tasting_to_wine(tasting_id, wine_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Tasting note or target entity not found",
            )

    return JSONResponse({"success": True, "tasting_id": tasting_id})


@router.get("/api/stats")
async def api_catalog_stats() -> JSONResponse:
    """Get catalog statistics."""
    with get_session() as session:
        service = get_catalog_service(session)
        stats = service.get_catalog_stats()
        meilisearch_stats = service.meilisearch.get_stats()

    return JSONResponse({
        "catalog": stats.model_dump(mode="json"),
        "meilisearch": meilisearch_stats,
    })
