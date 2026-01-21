"""Calibration routes for Wine Agent."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from wine_agent.db.engine import get_session
from wine_agent.services.calibration_service import CalibrationService
from wine_agent.web.templates_config import templates

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("", response_class=HTMLResponse)
async def calibration_index(request: Request) -> HTMLResponse:
    """
    Calibration page with score reference and personal stats.

    Shows user-defined calibration notes for score levels,
    along with personal scoring statistics and trends.
    """
    with get_session() as session:
        calibration = CalibrationService(session)

        # Get all calibration notes
        notes = calibration.get_calibration_notes()

        # Get personal stats
        personal_stats = calibration.get_personal_stats()

        # Get scoring averages over time
        scoring_trends = calibration.get_scoring_averages_over_time(period="month")

        # Get score consistency
        consistency = calibration.get_score_consistency()

    # Default score levels for reference
    default_score_levels = [50, 60, 70, 80, 85, 90, 95]

    # Map existing notes by score value
    notes_by_score = {note.score_value: note for note in notes}

    return templates.TemplateResponse(
        request=request,
        name="calibration/index.html",
        context={
            "notes": notes,
            "notes_by_score": notes_by_score,
            "default_score_levels": default_score_levels,
            "personal_stats": personal_stats,
            "scoring_trends": scoring_trends,
            "consistency": consistency,
        },
    )


@router.post("", response_class=HTMLResponse)
async def save_calibration_note(
    request: Request,
    score_value: int = Form(...),
    description: str = Form(...),
    examples: str = Form(""),
    note_id: str = Form(""),
) -> RedirectResponse:
    """
    Save a calibration note.

    Creates a new note or updates an existing one.

    Args:
        score_value: The score value (e.g., 70, 80, 90).
        description: Description of what this score means.
        examples: Comma-separated list of example wines.
        note_id: Optional ID if updating existing note.
    """
    with get_session() as session:
        calibration = CalibrationService(session)

        # Parse examples from comma-separated string
        example_list = [ex.strip() for ex in examples.split(",") if ex.strip()]

        calibration.set_calibration_note(
            score_value=score_value,
            description=description,
            examples=example_list,
            note_id=note_id if note_id else None,
        )

    return RedirectResponse(url="/calibration", status_code=303)


@router.post("/{note_id}/delete", response_class=HTMLResponse)
async def delete_calibration_note(note_id: str) -> RedirectResponse:
    """
    Delete a calibration note.

    Args:
        note_id: The UUID of the calibration note to delete.
    """
    with get_session() as session:
        calibration = CalibrationService(session)
        calibration.delete_calibration_note(note_id)

    return RedirectResponse(url="/calibration", status_code=303)


@router.get("/edit/{note_id}", response_class=HTMLResponse)
async def edit_calibration_note(request: Request, note_id: str) -> HTMLResponse:
    """
    Edit form for a specific calibration note.

    Returns an HTMX partial with the edit form.
    """
    with get_session() as session:
        calibration = CalibrationService(session)
        note = calibration.get_calibration_note(note_id)

    if not note:
        return HTMLResponse(content="<p>Note not found</p>", status_code=404)

    return templates.TemplateResponse(
        request=request,
        name="calibration/edit_form.html",
        context={"note": note},
    )


@router.get("/add/{score_value}", response_class=HTMLResponse)
async def add_calibration_note_form(request: Request, score_value: int) -> HTMLResponse:
    """
    Add form for a new calibration note at a specific score level.

    Returns an HTMX partial with the add form.
    """
    return templates.TemplateResponse(
        request=request,
        name="calibration/add_form.html",
        context={"score_value": score_value},
    )
