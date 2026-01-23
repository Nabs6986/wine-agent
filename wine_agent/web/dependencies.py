"""FastAPI dependencies for entitlement checking and common patterns.

These dependencies provide a clean way to enforce entitlements in routes.
"""

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request

from wine_agent.core.entitlements import (
    EntitlementError,
    EntitlementResolver,
    EntitlementResult,
    Feature,
    SubscriptionTier,
)
from wine_agent.db.engine import get_session
from wine_agent.db.repositories import InboxRepository, TastingNoteRepository


def get_entitlements() -> EntitlementResolver:
    """Dependency to get the entitlement resolver.

    Creates a resolver with a new database session.
    Use this when you need to check entitlements in a route.

    Returns:
        EntitlementResolver instance.
    """
    with get_session() as session:
        return EntitlementResolver(session)


def require_feature(feature: Feature) -> Callable[[], EntitlementResult]:
    """Dependency factory for requiring a specific feature.

    Use as a route dependency to gate access to features by tier.

    Example:
        @router.get("/export/csv")
        async def export_csv(
            _: EntitlementResult = Depends(require_feature(Feature.EXPORT_CSV)),
        ):
            ...

    Args:
        feature: The feature to require access for.

    Returns:
        A dependency function that raises HTTPException if denied.
    """
    def checker() -> EntitlementResult:
        with get_session() as session:
            resolver = EntitlementResolver(session)
            result = resolver.can_access(feature)

            if not result.allowed:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "feature_not_available",
                        "message": result.reason,
                        "required_tier": result.upgrade_tier.value if result.upgrade_tier else None,
                        "feature": feature.value,
                    },
                )

            return result

    return checker


def check_wine_limit() -> Callable[[], EntitlementResult]:
    """Dependency factory for checking wine count limit.

    Use before creating new wines/notes to enforce FREE tier limit.

    Returns:
        A dependency function that raises HTTPException if limit reached.
    """
    def checker() -> EntitlementResult:
        with get_session() as session:
            resolver = EntitlementResolver(session)

            # Count total wines (inbox items + tasting notes)
            inbox_repo = InboxRepository(session)
            note_repo = TastingNoteRepository(session)

            inbox_count = len(inbox_repo.list_all(include_converted=True))
            note_count = len(note_repo.list_all())

            # For limit purposes, count unique wines (not notes for same wine)
            # This is a simplification - in Phase 2 we'll have proper Wine entities
            total_count = inbox_count + note_count

            result = resolver.check_limit("max_wines", total_count)

            if not result.allowed:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "limit_reached",
                        "message": result.reason,
                        "current_count": total_count,
                        "limit": resolver.get_limit("max_wines"),
                        "required_tier": result.upgrade_tier.value if result.upgrade_tier else None,
                    },
                )

            return result

    return checker


# Type aliases for dependency injection
EntitlementsDep = Annotated[EntitlementResolver, Depends(get_entitlements)]


class EntitlementContext:
    """Context manager for entitlement checking with session management.

    Use this in route handlers when you need to check entitlements
    and perform database operations in the same session.

    Example:
        async def my_route(request: Request):
            with EntitlementContext() as ctx:
                ctx.require_feature(Feature.EXPORT_CSV)
                # Use ctx.session for database operations
    """

    def __init__(self):
        self._session = None
        self._resolver = None

    def __enter__(self):
        from wine_agent.db.engine import get_session_factory

        factory = get_session_factory()
        self._session = factory()
        self._resolver = EntitlementResolver(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            self._session.close()
        return False

    @property
    def session(self):
        """Get the database session."""
        return self._session

    @property
    def resolver(self) -> EntitlementResolver:
        """Get the entitlement resolver."""
        return self._resolver

    @property
    def current_tier(self) -> SubscriptionTier:
        """Get the current subscription tier."""
        return self._resolver.current_tier

    def can_access(self, feature: Feature) -> EntitlementResult:
        """Check if current tier can access a feature."""
        return self._resolver.can_access(feature)

    def require_feature(self, feature: Feature) -> None:
        """Require access to a feature, raising HTTPException if denied."""
        result = self._resolver.can_access(feature)
        if not result.allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "feature_not_available",
                    "message": result.reason,
                    "required_tier": result.upgrade_tier.value if result.upgrade_tier else None,
                    "feature": feature.value,
                },
            )

    def check_limit(self, resource: str, current_count: int) -> EntitlementResult:
        """Check if a resource limit has been reached."""
        result = self._resolver.check_limit(resource, current_count)
        if not result.allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "limit_reached",
                    "message": result.reason,
                    "current_count": current_count,
                    "limit": self._resolver.get_limit(resource),
                    "required_tier": result.upgrade_tier.value if result.upgrade_tier else None,
                },
            )
        return result


def get_tier_context(request: Request) -> dict:
    """Get tier context for template rendering.

    Use this to get feature availability for conditional UI rendering.

    Returns:
        Dict with tier info and feature availability.
    """
    with get_session() as session:
        resolver = EntitlementResolver(session)
        return {
            "tier": resolver.current_tier.value,
            "tier_info": resolver.get_tier_info(),
            "features": resolver.get_feature_summary(),
            "can_convert": resolver.can_access(Feature.STRUCTURED_CONVERSION).allowed,
            "can_export_csv": resolver.can_access(Feature.EXPORT_CSV).allowed,
            "can_export_pdf": resolver.can_access(Feature.EXPORT_PDF).allowed,
            "can_export_json": resolver.can_access(Feature.EXPORT_JSON).allowed,
            "can_view_insights": resolver.can_access(Feature.PERSONAL_INSIGHTS).allowed,
            "can_use_calibration": resolver.can_access(Feature.CALIBRATION).allowed,
            "can_aging_notes": resolver.can_access(Feature.AGING_NOTES).allowed,
            "can_advanced_analytics": resolver.can_access(Feature.ADVANCED_ANALYTICS).allowed,
            "wine_limit": resolver.get_limit("max_wines"),
            "is_expired": resolver.is_expired,
        }
