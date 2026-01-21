"""Inbox routes for Wine Agent."""

import asyncio
import logging
import os
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from wine_agent.core.enums import NoteSource, NoteStatus
from wine_agent.core.schema import InboxItem, TastingNote
from wine_agent.db.engine import get_session
from wine_agent.db.repositories import (
    AIConversionRepository,
    InboxRepository,
    TastingNoteRepository,
)
from wine_agent.web.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["inbox"])


@router.get("/", response_class=RedirectResponse)
async def root() -> RedirectResponse:
    """Redirect root to inbox."""
    return RedirectResponse(url="/inbox", status_code=302)


@router.get("/inbox", response_class=HTMLResponse)
async def inbox_list(request: Request, filter: str = "open") -> HTMLResponse:
    """
    List inbox items with optional filtering.

    Args:
        request: The FastAPI request object.
        filter: Filter type - 'open', 'converted', or 'all'.

    Returns:
        Rendered inbox list template.
    """
    with get_session() as session:
        repo = InboxRepository(session)

        if filter == "open":
            items = repo.list_all(include_converted=False)
        elif filter == "converted":
            all_items = repo.list_all(include_converted=True)
            items = [item for item in all_items if item.converted]
        else:
            items = repo.list_all(include_converted=True)

    return templates.TemplateResponse(
        request=request,
        name="inbox/list.html",
        context={
            "items": items,
            "current_filter": filter,
        },
    )


@router.get("/inbox/new", response_class=HTMLResponse)
async def inbox_new(request: Request) -> HTMLResponse:
    """
    Display form to create a new inbox item.

    Args:
        request: The FastAPI request object.

    Returns:
        Rendered new inbox item form.
    """
    return templates.TemplateResponse(
        request=request,
        name="inbox/new.html",
        context={},
    )


@router.post("/inbox", response_class=RedirectResponse)
async def inbox_create(
    raw_text: str = Form(...),
    tags: str = Form(""),
) -> RedirectResponse:
    """
    Create a new inbox item.

    Args:
        raw_text: The raw tasting note text.
        tags: Comma-separated tags (optional).

    Returns:
        Redirect to the inbox list.
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    item = InboxItem(raw_text=raw_text, tags=tag_list)

    with get_session() as session:
        repo = InboxRepository(session)
        repo.create(item)
        session.commit()

    return RedirectResponse(url=f"/inbox/{item.id}", status_code=303)


@router.get("/inbox/{item_id}", response_class=HTMLResponse)
async def inbox_detail(request: Request, item_id: str) -> HTMLResponse:
    """
    Display inbox item detail.

    Args:
        request: The FastAPI request object.
        item_id: The UUID of the inbox item.

    Returns:
        Rendered inbox item detail template.
    """
    with get_session() as session:
        repo = InboxRepository(session)
        item = repo.get_by_id(item_id)

        if item is None:
            raise HTTPException(status_code=404, detail="Inbox item not found")

        # Check if there's an associated tasting note
        note_repo = TastingNoteRepository(session)
        associated_note = note_repo.get_by_inbox_item_id(item_id)

        # Get conversion history for this item
        conversion_repo = AIConversionRepository(session)
        conversion_runs = conversion_repo.get_by_inbox_item_id(item_id)
        last_conversion = conversion_runs[0] if conversion_runs else None

    return templates.TemplateResponse(
        request=request,
        name="inbox/detail.html",
        context={
            "item": item,
            "associated_note": associated_note,
            "last_conversion": last_conversion,
            "conversion_runs": conversion_runs,
        },
    )


@router.post("/inbox/{item_id}/archive", response_class=RedirectResponse)
async def inbox_archive(item_id: str) -> RedirectResponse:
    """
    Archive an inbox item (mark as converted without creating a note).

    Args:
        item_id: The UUID of the inbox item.

    Returns:
        Redirect to the inbox list.
    """
    with get_session() as session:
        repo = InboxRepository(session)
        item = repo.get_by_id(item_id)

        if item is None:
            raise HTTPException(status_code=404, detail="Inbox item not found")

        item.converted = True
        repo.update(item)
        session.commit()

    return RedirectResponse(url="/inbox", status_code=303)


def _ai_available() -> bool:
    """Check if AI conversion is available (API key configured)."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    )


@router.post("/inbox/{item_id}/convert", response_model=None)
async def inbox_convert(request: Request, item_id: str) -> Response:
    """
    Convert an inbox item to a draft tasting note using AI.

    If AI is not configured (no API key), falls back to creating a placeholder draft.
    If AI conversion fails, shows error on inbox detail page.

    Args:
        request: The FastAPI request object.
        item_id: The UUID of the inbox item.

    Returns:
        Redirect to the draft note view on success, or error page on failure.
    """
    with get_session() as session:
        inbox_repo = InboxRepository(session)
        note_repo = TastingNoteRepository(session)

        item = inbox_repo.get_by_id(item_id)

        if item is None:
            raise HTTPException(status_code=404, detail="Inbox item not found")

        if item.converted:
            # Check if there's an existing note
            existing_note = note_repo.get_by_inbox_item_id(item_id)
            if existing_note:
                return RedirectResponse(
                    url=f"/notes/draft/{existing_note.id}", status_code=303
                )

        # Try AI conversion if available
        if _ai_available():
            try:
                from wine_agent.services.ai.conversion import ConversionService

                service = ConversionService(session)
                # Run synchronous AI call in thread pool to avoid blocking event loop
                result = await asyncio.to_thread(service.convert_inbox_item, item_id)

                if result.success and result.tasting_note:
                    session.commit()
                    return RedirectResponse(
                        url=f"/notes/draft/{result.tasting_note.id}", status_code=303
                    )
                else:
                    # Conversion failed - show error on detail page
                    session.commit()  # Save the failed conversion run
                    logger.warning(f"AI conversion failed: {result.error_message}")

                    # Get updated data for the detail page
                    conversion_repo = AIConversionRepository(session)
                    conversion_runs = conversion_repo.get_by_inbox_item_id(item_id)
                    last_conversion = conversion_runs[0] if conversion_runs else None

                    return templates.TemplateResponse(
                        request=request,
                        name="inbox/detail.html",
                        context={
                            "item": item,
                            "associated_note": None,
                            "last_conversion": last_conversion,
                            "conversion_runs": conversion_runs,
                            "conversion_error": result.error_message,
                        },
                    )

            except Exception as e:
                logger.error(f"Conversion service error: {e}")
                # Fall through to placeholder creation
                pass

        # Fallback: Create placeholder draft tasting note (no AI)
        note = TastingNote(
            inbox_item_id=UUID(item_id) if isinstance(item_id, str) else item_id,
            source=NoteSource.INBOX_CONVERTED,
            status=NoteStatus.DRAFT,
        )

        note_repo.create(note)

        # Mark inbox item as converted
        item.converted = True
        inbox_repo.update(item)

        session.commit()

    return RedirectResponse(url=f"/notes/draft/{note.id}", status_code=303)
