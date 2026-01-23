"""Notes routes for Wine Agent."""

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from wine_agent.core.enums import (
    AlcoholLevel,
    BodyLevel,
    DecantLevel,
    DrinkOrHold,
    IntensityLevel,
    NoteStatus,
    OakLevel,
    StructureLevel,
    Sweetness,
    SweetnessLevel,
    WineColor,
    WineStyle,
)
from wine_agent.db.engine import get_session
from wine_agent.db.repositories import InboxRepository, TastingNoteRepository
from wine_agent.services.publishing_service import PublishingService
from wine_agent.web.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["notes"])


def _get_enum_choices() -> dict[str, list[tuple[str, str]]]:
    """Get enum choices for form dropdowns."""
    return {
        "wine_colors": [(e.value, e.value.replace("_", " ").title()) for e in WineColor],
        "wine_styles": [(e.value, e.value.replace("_", " ").title()) for e in WineStyle],
        "sweetness_types": [(e.value, e.value.replace("_", " ").title()) for e in Sweetness],
        "structure_levels": [(e.value, e.value.replace("_", " ").title()) for e in StructureLevel],
        "body_levels": [(e.value, e.value.replace("_", " ").title()) for e in BodyLevel],
        "alcohol_levels": [(e.value, e.value.replace("_", " ").title()) for e in AlcoholLevel],
        "sweetness_levels": [(e.value, e.value.replace("_", " ").title()) for e in SweetnessLevel],
        "intensity_levels": [(e.value, e.value.replace("_", " ").title()) for e in IntensityLevel],
        "oak_levels": [(e.value, e.value.replace("_", " ").title()) for e in OakLevel],
        "decant_levels": [(e.value, e.value.replace("_", " ").title()) for e in DecantLevel],
        "drink_or_hold": [(e.value, e.value.replace("_", " ").title()) for e in DrinkOrHold],
    }


@router.get("", response_class=HTMLResponse)
async def notes_list(request: Request, status: str = "all") -> HTMLResponse:
    """
    List all tasting notes with optional status filter.

    Args:
        request: The FastAPI request object.
        status: Filter by status ('draft', 'published', 'all').

    Returns:
        Rendered notes list template.
    """
    with get_session() as session:
        note_repo = TastingNoteRepository(session)

        if status == "draft":
            notes = note_repo.list_all(status="draft")
        elif status == "published":
            notes = note_repo.list_all(status="published")
        else:
            notes = note_repo.list_all()

    return templates.TemplateResponse(
        request=request,
        name="notes/list.html",
        context={
            "notes": notes,
            "current_status": status,
        },
    )


@router.get("/draft/{note_id}", response_class=HTMLResponse)
async def draft_detail(request: Request, note_id: str) -> HTMLResponse:
    """
    Display draft tasting note detail (read-only view).

    Args:
        request: The FastAPI request object.
        note_id: The UUID of the tasting note.

    Returns:
        Rendered draft note template.
    """
    logger.info(f"Loading draft note: {note_id}")
    with get_session() as session:
        note_repo = TastingNoteRepository(session)
        note = note_repo.get_by_id(note_id)

        if note is None:
            logger.warning(f"Draft note not found: {note_id}")
            raise HTTPException(status_code=404, detail="Tasting note not found")

        logger.info(
            f"Loaded draft note: id={note.id}, "
            f"producer='{note.wine.producer}', "
            f"cuvee='{note.wine.cuvee}', "
            f"source={note.source.value}"
        )

        # Get associated inbox item if exists
        inbox_item = None
        if note.inbox_item_id:
            inbox_repo = InboxRepository(session)
            inbox_item = inbox_repo.get_by_id(note.inbox_item_id)

    return templates.TemplateResponse(
        request=request,
        name="notes/draft.html",
        context={
            "note": note,
            "inbox_item": inbox_item,
        },
    )


@router.get("/draft/{note_id}/edit", response_class=HTMLResponse)
async def draft_edit(request: Request, note_id: str) -> HTMLResponse:
    """
    Display edit form for a draft tasting note.

    Args:
        request: The FastAPI request object.
        note_id: The UUID of the tasting note.

    Returns:
        Rendered edit form template.
    """
    with get_session() as session:
        note_repo = TastingNoteRepository(session)
        note = note_repo.get_by_id(note_id)

        if note is None:
            raise HTTPException(status_code=404, detail="Tasting note not found")

        if note.status == NoteStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="Cannot edit published notes")

        # Get associated inbox item if exists
        inbox_item = None
        if note.inbox_item_id:
            inbox_repo = InboxRepository(session)
            inbox_item = inbox_repo.get_by_id(note.inbox_item_id)

    return templates.TemplateResponse(
        request=request,
        name="notes/edit.html",
        context={
            "note": note,
            "inbox_item": inbox_item,
            "errors": {},
            **_get_enum_choices(),
        },
    )


@router.post("/draft/{note_id}", response_model=None)
async def draft_save(
    request: Request,
    note_id: str,
    # Wine identity
    producer: str = Form(""),
    cuvee: str = Form(""),
    vintage: str = Form(""),
    country: str = Form(""),
    region: str = Form(""),
    appellation: str = Form(""),
    grapes: str = Form(""),
    color: str = Form(""),
    style: str = Form(""),
    sweetness: str = Form(""),
    alcohol_percent: str = Form(""),
    # Tasting context
    tasting_date: str = Form(""),
    location: str = Form(""),
    occasion: str = Form(""),
    food_pairing: str = Form(""),
    companions: str = Form(""),
    glassware: str = Form(""),
    decant: str = Form(""),
    decant_minutes: str = Form(""),
    # Sensory notes
    appearance_notes: str = Form(""),
    nose_notes: str = Form(""),
    palate_notes: str = Form(""),
    structure_notes: str = Form(""),
    finish_notes: str = Form(""),
    overall_notes: str = Form(""),
    conclusion: str = Form(""),
    # Structure levels
    acidity: str = Form(""),
    tannin: str = Form(""),
    body: str = Form(""),
    alcohol_level: str = Form(""),
    sweetness_level: str = Form(""),
    intensity: str = Form(""),
    oak: str = Form(""),
    # Scores
    score_appearance: str = Form("0"),
    score_nose: str = Form("0"),
    score_palate: str = Form("0"),
    score_structure_balance: str = Form("0"),
    score_finish: str = Form("0"),
    score_typicity_complexity: str = Form("0"),
    score_overall_judgment: str = Form("0"),
    personal_enjoyment: str = Form(""),
    # Readiness
    drink_or_hold: str = Form("drink"),
    window_start_year: str = Form(""),
    window_end_year: str = Form(""),
    readiness_notes: str = Form(""),
) -> Response:
    """
    Save updates to a draft tasting note.

    Args:
        request: The FastAPI request object.
        note_id: The UUID of the tasting note.
        ... form fields ...

    Returns:
        Redirect to draft view on success, or edit form with errors.
    """
    # Build updates dictionary
    updates: dict[str, Any] = {
        "wine": {
            "producer": producer,
            "cuvee": cuvee,
            "vintage": int(vintage) if vintage.isdigit() else None,
            "country": country,
            "region": region,
            "appellation": appellation,
            "grapes": [g.strip() for g in grapes.split(",") if g.strip()],
            "color": WineColor(color) if color else None,
            "style": WineStyle(style) if style else None,
            "sweetness": Sweetness(sweetness) if sweetness else None,
            "alcohol_percent": float(alcohol_percent) if alcohol_percent else None,
        },
        "context": {
            "tasting_date": date.fromisoformat(tasting_date) if tasting_date else None,
            "location": location,
            "occasion": occasion,
            "food_pairing": food_pairing,
            "companions": companions,
            "glassware": glassware,
            "decant": DecantLevel(decant) if decant else None,
            "decant_minutes": int(decant_minutes) if decant_minutes.isdigit() else None,
        },
        "structure_levels": {
            "acidity": StructureLevel(acidity) if acidity else None,
            "tannin": StructureLevel(tannin) if tannin else None,
            "body": BodyLevel(body) if body else None,
            "alcohol": AlcoholLevel(alcohol_level) if alcohol_level else None,
            "sweetness": SweetnessLevel(sweetness_level) if sweetness_level else None,
            "intensity": IntensityLevel(intensity) if intensity else None,
            "oak": OakLevel(oak) if oak else None,
        },
        "scores": {
            "subscores": {
                "appearance": int(score_appearance) if score_appearance.isdigit() else 0,
                "nose": int(score_nose) if score_nose.isdigit() else 0,
                "palate": int(score_palate) if score_palate.isdigit() else 0,
                "structure_balance": int(score_structure_balance) if score_structure_balance.isdigit() else 0,
                "finish": int(score_finish) if score_finish.isdigit() else 0,
                "typicity_complexity": int(score_typicity_complexity) if score_typicity_complexity.isdigit() else 0,
                "overall_judgment": int(score_overall_judgment) if score_overall_judgment.isdigit() else 0,
            },
            "personal_enjoyment": int(personal_enjoyment) if personal_enjoyment.isdigit() else None,
        },
        "readiness": {
            "drink_or_hold": DrinkOrHold(drink_or_hold) if drink_or_hold else DrinkOrHold.DRINK,
            "window_start_year": int(window_start_year) if window_start_year.isdigit() else None,
            "window_end_year": int(window_end_year) if window_end_year.isdigit() else None,
            "notes": readiness_notes,
        },
        "appearance_notes": appearance_notes,
        "nose_notes": nose_notes,
        "palate_notes": palate_notes,
        "structure_notes": structure_notes,
        "finish_notes": finish_notes,
        "overall_notes": overall_notes,
        "conclusion": conclusion,
    }

    with get_session() as session:
        service = PublishingService(session)
        result = service.save_draft(note_id, updates)

        if result.success:
            session.commit()
            return RedirectResponse(url=f"/notes/draft/{note_id}", status_code=303)
        else:
            # Get note for re-rendering form
            note_repo = TastingNoteRepository(session)
            note = note_repo.get_by_id(note_id)

            inbox_item = None
            if note and note.inbox_item_id:
                inbox_repo = InboxRepository(session)
                inbox_item = inbox_repo.get_by_id(note.inbox_item_id)

            return templates.TemplateResponse(
                request=request,
                name="notes/edit.html",
                context={
                    "note": note,
                    "inbox_item": inbox_item,
                    "errors": {"general": result.error_message},
                    **_get_enum_choices(),
                },
            )


@router.post("/draft/{note_id}/publish", response_model=None)
async def draft_publish(request: Request, note_id: str) -> Response:
    """
    Publish a draft tasting note.

    Args:
        request: The FastAPI request object.
        note_id: The UUID of the tasting note.

    Returns:
        Redirect to published note view on success.
    """
    with get_session() as session:
        service = PublishingService(session)
        result = service.publish_note(note_id)

        if result.success:
            session.commit()
            return RedirectResponse(url=f"/notes/{note_id}", status_code=303)
        else:
            # Get note for re-rendering
            note_repo = TastingNoteRepository(session)
            note = note_repo.get_by_id(note_id)

            inbox_item = None
            if note and note.inbox_item_id:
                inbox_repo = InboxRepository(session)
                inbox_item = inbox_repo.get_by_id(note.inbox_item_id)

            return templates.TemplateResponse(
                request=request,
                name="notes/draft.html",
                context={
                    "note": note,
                    "inbox_item": inbox_item,
                    "publish_error": result.error_message,
                },
            )


@router.get("/{note_id}", response_class=HTMLResponse)
async def note_detail(request: Request, note_id: str) -> HTMLResponse:
    """
    Display published tasting note detail (read-only).

    Args:
        request: The FastAPI request object.
        note_id: The UUID of the tasting note.

    Returns:
        Rendered published note template.
    """
    with get_session() as session:
        note_repo = TastingNoteRepository(session)
        note = note_repo.get_by_id(note_id)

        if note is None:
            raise HTTPException(status_code=404, detail="Tasting note not found")

        # Get associated inbox item if exists
        inbox_item = None
        if note.inbox_item_id:
            inbox_repo = InboxRepository(session)
            inbox_item = inbox_repo.get_by_id(note.inbox_item_id)

        # Get revisions
        service = PublishingService(session)
        revisions = service.get_revisions(note_id)

    return templates.TemplateResponse(
        request=request,
        name="notes/published.html",
        context={
            "note": note,
            "inbox_item": inbox_item,
            "revisions": revisions,
        },
    )


@router.get("/{note_id}/revisions", response_class=HTMLResponse)
async def note_revisions(request: Request, note_id: str) -> HTMLResponse:
    """
    Display revision history for a tasting note.

    Args:
        request: The FastAPI request object.
        note_id: The UUID of the tasting note.

    Returns:
        Rendered revisions template.
    """
    with get_session() as session:
        note_repo = TastingNoteRepository(session)
        note = note_repo.get_by_id(note_id)

        if note is None:
            raise HTTPException(status_code=404, detail="Tasting note not found")

        service = PublishingService(session)
        revisions = service.get_revisions(note_id)

    return templates.TemplateResponse(
        request=request,
        name="notes/revisions.html",
        context={
            "note": note,
            "revisions": revisions,
        },
    )


@router.post("/{note_id}/delete", response_model=None)
async def note_delete(note_id: str) -> Response:
    """
    Delete a draft tasting note.

    Args:
        note_id: The UUID of the tasting note.

    Returns:
        Redirect to notes list on success.
    """
    with get_session() as session:
        service = PublishingService(session)
        result = service.delete_note(note_id)

        if result.success:
            session.commit()
            return RedirectResponse(url="/notes", status_code=303)
        else:
            raise HTTPException(status_code=400, detail=result.error_message)
