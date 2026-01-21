"""Analytics routes for Wine Agent dashboard."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from wine_agent.db.engine import get_session
from wine_agent.services.analytics_service import AnalyticsService
from wine_agent.web.templates_config import templates

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_class=HTMLResponse)
async def analytics_index(
    request: Request,
    min_count: int = 2,
) -> HTMLResponse:
    """
    Analytics dashboard page.

    Shows score distribution, top regions/producers, descriptor frequency,
    and scoring trends over time.

    Args:
        request: The FastAPI request object.
        min_count: Minimum notes required for top lists.

    Returns:
        Rendered analytics dashboard template.
    """
    with get_session() as session:
        analytics = AnalyticsService(session)

        # Get all analytics data
        summary = analytics.get_summary_stats()
        score_distribution = analytics.get_score_distribution(bin_size=5)
        top_regions = analytics.get_top_regions(min_count=min_count, limit=10)
        top_producers = analytics.get_top_producers(min_count=min_count, limit=10)
        top_countries = analytics.get_top_countries(min_count=min_count, limit=10)
        nose_descriptors = analytics.get_descriptor_frequency(field="nose", limit=20)
        palate_descriptors = analytics.get_descriptor_frequency(field="palate", limit=20)
        scoring_trends = analytics.get_scoring_trends(period="month")
        quality_bands = analytics.get_quality_band_distribution()
        vintage_distribution = analytics.get_vintage_distribution()

    return templates.TemplateResponse(
        request=request,
        name="analytics/index.html",
        context={
            "summary": summary,
            "score_distribution": score_distribution,
            "top_regions": top_regions,
            "top_producers": top_producers,
            "top_countries": top_countries,
            "nose_descriptors": nose_descriptors,
            "palate_descriptors": palate_descriptors,
            "scoring_trends": scoring_trends,
            "quality_bands": quality_bands,
            "vintage_distribution": vintage_distribution,
            "min_count": min_count,
        },
    )
