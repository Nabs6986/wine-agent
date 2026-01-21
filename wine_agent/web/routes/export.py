"""Export routes for downloading tasting notes in various formats."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from wine_agent.db.engine import get_session
from wine_agent.services.export_service import ExportService

router = APIRouter(tags=["export"])


@router.get("/notes/{note_id}/export/md")
async def export_note_markdown(note_id: str) -> Response:
    """
    Export a single tasting note as Markdown with YAML frontmatter.

    Args:
        note_id: The UUID of the note to export.

    Returns:
        Markdown file download.
    """
    with get_session() as session:
        export_service = ExportService(session)
        markdown = export_service.export_note_markdown(note_id)

        if markdown is None:
            raise HTTPException(status_code=404, detail="Tasting note not found")

    # Generate filename from note ID (first 8 chars)
    filename = f"tasting_note_{note_id[:8]}.md"

    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/export/csv")
async def export_notes_csv(status: str = "published") -> Response:
    """
    Export all tasting notes as CSV.

    Args:
        status: Filter by status (published, draft, all).

    Returns:
        CSV file download.
    """
    with get_session() as session:
        export_service = ExportService(session)
        csv_content = export_service.export_notes_csv(status=status)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="tasting_notes.csv"',
        },
    )


@router.get("/export/json")
async def export_notes_json(status: str = "published") -> Response:
    """
    Export all tasting notes as JSON.

    Args:
        status: Filter by status (published, draft, all).

    Returns:
        JSON file download.
    """
    with get_session() as session:
        export_service = ExportService(session)
        json_content = export_service.export_notes_json(status=status)

    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="tasting_notes.json"',
        },
    )
