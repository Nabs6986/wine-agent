"""Inbox routes for Wine Agent."""

import asyncio
import logging
import os
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from wine_agent.core.entitlements import EntitlementResolver, Feature
from wine_agent.core.enums import NoteSource, NoteStatus
from wine_agent.core.schema import InboxItem, TastingNote
from wine_agent.db.engine import get_session
from wine_agent.db.repositories import (
    AIConversionRepository,
    InboxRepository,
    TastingNoteRepository,
)
from wine_agent.web.dependencies import get_tier_context
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
        note_repo = TastingNoteRepository(session)

        if filter == "open":
            items = repo.list_all(include_converted=False)
        elif filter == "converted":
            all_items = repo.list_all(include_converted=True)
            items = [item for item in all_items if item.converted]
        else:
            items = repo.list_all(include_converted=True)

        # Get wine count and limit for FREE tier display
        resolver = EntitlementResolver(session)
        all_inbox = repo.list_all(include_converted=True)
        all_notes = note_repo.list_all()
        wine_count = len(all_inbox) + len(all_notes)
        wine_limit = resolver.get_limit("max_wines")

    return templates.TemplateResponse(
        request=request,
        name="inbox/list.html",
        context={
            "items": items,
            "current_filter": filter,
            "wine_count": wine_count,
            "wine_limit": wine_limit,
        },
    )


@router.get("/inbox/new", response_class=HTMLResponse)
async def inbox_new(request: Request) -> HTMLResponse:
    """
    Display form to create a new inbox item.

    Shows wine usage and limit warning for FREE tier users.

    Args:
        request: The FastAPI request object.

    Returns:
        Rendered new inbox item form.
    """
    with get_session() as session:
        # Get wine count and limit for FREE tier display
        resolver = EntitlementResolver(session)
        inbox_repo = InboxRepository(session)
        note_repo = TastingNoteRepository(session)

        all_inbox = inbox_repo.list_all(include_converted=True)
        all_notes = note_repo.list_all()
        wine_count = len(all_inbox) + len(all_notes)
        wine_limit = resolver.get_limit("max_wines")

        # Check if limit is already reached
        limit_reached = wine_limit is not None and wine_count >= wine_limit

    return templates.TemplateResponse(
        request=request,
        name="inbox/new.html",
        context={
            "wine_count": wine_count,
            "wine_limit": wine_limit,
            "limit_reached": limit_reached,
        },
    )


@router.post("/inbox", response_class=RedirectResponse)
async def inbox_create(
    request: Request,
    raw_text: str = Form(...),
    tags: str = Form(""),
) -> RedirectResponse:
    """
    Create a new inbox item.

    Enforces FREE tier wine limit (25 wines max).

    Args:
        request: The FastAPI request object.
        raw_text: The raw tasting note text.
        tags: Comma-separated tags (optional).

    Returns:
        Redirect to the inbox list, or error if limit reached.
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    with get_session() as session:
        # Check entitlements and limits
        resolver = EntitlementResolver(session)
        inbox_repo = InboxRepository(session)
        note_repo = TastingNoteRepository(session)

        # Count current wines for limit check
        inbox_count = len(inbox_repo.list_all(include_converted=True))
        note_count = len(note_repo.list_all())
        total_count = inbox_count + note_count

        limit_result = resolver.check_limit("max_wines", total_count)

        if not limit_result.allowed:
            # Return error page with upgrade prompt
            tier_context = get_tier_context(request)
            return templates.TemplateResponse(
                request=request,
                name="inbox/new.html",
                context={
                    **tier_context,
                    "error": limit_result.reason,
                    "show_upgrade": True,
                    "raw_text": raw_text,
                    "tags": tags,
                },
                status_code=403,
            )

        # Create the inbox item
        item = InboxItem(raw_text=raw_text, tags=tag_list)
        inbox_repo.create(item)
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

    Requires PRO tier or higher for AI-powered conversion.
    If AI is not configured (no API key), falls back to creating a placeholder draft.
    If AI conversion fails, shows error on inbox detail page.

    Args:
        request: The FastAPI request object.
        item_id: The UUID of the inbox item.

    Returns:
        Redirect to the draft note view on success, or error page on failure.
    """
    def _convert_in_thread(target_item_id: str):
        from wine_agent.services.ai.conversion import ConversionService

        with get_session() as thread_session:
            service = ConversionService(thread_session)
            result = service.convert_inbox_item(target_item_id)
            thread_session.commit()
            return result

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

        # Check entitlement for structured conversion (PRO feature)
        resolver = EntitlementResolver(session)
        conversion_allowed = resolver.can_access(Feature.STRUCTURED_CONVERSION)

        if not conversion_allowed.allowed:
            # Show upgrade prompt on detail page
            tier_context = get_tier_context(request)
            conversion_repo = AIConversionRepository(session)
            conversion_runs = conversion_repo.get_by_inbox_item_id(item_id)
            last_conversion = conversion_runs[0] if conversion_runs else None

            return templates.TemplateResponse(
                request=request,
                name="inbox/detail.html",
                context={
                    **tier_context,
                    "item": item,
                    "associated_note": None,
                    "last_conversion": last_conversion,
                    "conversion_runs": conversion_runs,
                    "conversion_error": conversion_allowed.reason,
                    "show_upgrade": True,
                    "required_tier": conversion_allowed.upgrade_tier.value if conversion_allowed.upgrade_tier else "pro",
                },
                status_code=403,
            )

        # Try AI conversion if available
        if _ai_available():
            try:
                # Run synchronous AI call in thread pool with its own session
                result = await asyncio.to_thread(_convert_in_thread, item_id)

                if result.success and result.tasting_note:
                    logger.info(
                        f"AI conversion successful, redirecting to note {result.tasting_note.id}, "
                        f"producer='{result.tasting_note.wine.producer}', "
                        f"cuvee='{result.tasting_note.wine.cuvee}'"
                    )
                    return RedirectResponse(
                        url=f"/notes/draft/{result.tasting_note.id}", status_code=303
                    )
                else:
                    # Conversion failed - show error on detail page
                    logger.warning(f"AI conversion failed: {result.error_message}")

                    # Get updated data for the detail page
                    tier_context = get_tier_context(request)
                    conversion_repo = AIConversionRepository(session)
                    conversion_runs = conversion_repo.get_by_inbox_item_id(item_id)
                    last_conversion = conversion_runs[0] if conversion_runs else None

                    return templates.TemplateResponse(
                        request=request,
                        name="inbox/detail.html",
                        context={
                            **tier_context,
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
