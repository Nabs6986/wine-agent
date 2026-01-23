"""Centralized entitlement system for subscription tier management.

This module is the single source of truth for all feature access control.
All feature access must flow through the EntitlementResolver - no scattered
feature flags or direct tier checks elsewhere in the codebase.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SubscriptionTier(str, Enum):
    """Subscription tier levels."""

    FREE = "free"
    PRO = "pro"
    CELLAR = "cellar"


class Feature(str, Enum):
    """All features that can be gated by subscription tier.

    Features are organized by tier introduction. Higher tiers include
    all features from lower tiers.
    """

    # FREE tier features
    SAVE_WINE = "save_wine"
    FREE_FORM_NOTES = "free_form_notes"
    LABEL_PHOTO_UPLOAD = "label_photo_upload"
    BASIC_AUTOFILL = "basic_autofill"
    VIEW_LIBRARY = "view_library"
    BASIC_SEARCH = "basic_search"

    # PRO tier features
    UNLIMITED_WINES = "unlimited_wines"
    STRUCTURED_CONVERSION = "structured_conversion"
    PERSONAL_INSIGHTS = "personal_insights"
    EXPORT_PDF = "export_pdf"
    EXPORT_CSV = "export_csv"
    EXPORT_JSON = "export_json"
    VINTAGE_TRACKING = "vintage_tracking"
    CALIBRATION = "calibration"

    # CELLAR tier features
    MULTI_VINTAGE_TRACKING = "multi_vintage_tracking"
    AGING_NOTES = "aging_notes"
    DRINKING_WINDOWS = "drinking_windows"
    ADVANCED_ANALYTICS = "advanced_analytics"
    CELLAR_VALUATION = "cellar_valuation"


# Feature sets by tier (cumulative - higher tiers include lower tier features)
_FREE_FEATURES: set[Feature] = {
    Feature.SAVE_WINE,
    Feature.FREE_FORM_NOTES,
    Feature.LABEL_PHOTO_UPLOAD,
    Feature.BASIC_AUTOFILL,
    Feature.VIEW_LIBRARY,
    Feature.BASIC_SEARCH,
}

_PRO_FEATURES: set[Feature] = _FREE_FEATURES | {
    Feature.UNLIMITED_WINES,
    Feature.STRUCTURED_CONVERSION,
    Feature.PERSONAL_INSIGHTS,
    Feature.EXPORT_PDF,
    Feature.EXPORT_CSV,
    Feature.EXPORT_JSON,
    Feature.VINTAGE_TRACKING,
    Feature.CALIBRATION,
}

_CELLAR_FEATURES: set[Feature] = _PRO_FEATURES | {
    Feature.MULTI_VINTAGE_TRACKING,
    Feature.AGING_NOTES,
    Feature.DRINKING_WINDOWS,
    Feature.ADVANCED_ANALYTICS,
    Feature.CELLAR_VALUATION,
}

TIER_FEATURES: dict[SubscriptionTier, set[Feature]] = {
    SubscriptionTier.FREE: _FREE_FEATURES,
    SubscriptionTier.PRO: _PRO_FEATURES,
    SubscriptionTier.CELLAR: _CELLAR_FEATURES,
}


# Tier limits
TIER_LIMITS: dict[SubscriptionTier, dict[str, int | None]] = {
    SubscriptionTier.FREE: {
        "max_wines": 25,
        "max_notes_per_wine": 1,
    },
    SubscriptionTier.PRO: {
        "max_wines": None,  # Unlimited
        "max_notes_per_wine": None,
    },
    SubscriptionTier.CELLAR: {
        "max_wines": None,
        "max_notes_per_wine": None,
    },
}


# Minimum tier required for each feature (for upgrade prompts)
def _get_minimum_tier_for_feature(feature: Feature) -> SubscriptionTier:
    """Get the minimum tier required to access a feature."""
    if feature in _FREE_FEATURES:
        return SubscriptionTier.FREE
    if feature in _PRO_FEATURES:
        return SubscriptionTier.PRO
    return SubscriptionTier.CELLAR


class AppConfiguration(BaseModel):
    """Application configuration including subscription state.

    This is a singleton model - only one row exists in the database.
    """

    license_key: str | None = None
    license_validated_at: datetime | None = None
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    tier_expires_at: datetime | None = None
    email: str | None = None
    machine_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass
class EntitlementResult:
    """Result of an entitlement check."""

    allowed: bool
    reason: str | None = None
    upgrade_tier: SubscriptionTier | None = None

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.allowed


class EntitlementError(Exception):
    """Raised when an entitlement check fails."""

    def __init__(self, reason: str, upgrade_tier: SubscriptionTier | None = None):
        self.reason = reason
        self.upgrade_tier = upgrade_tier
        super().__init__(reason)


class EntitlementResolver:
    """Centralized entitlement resolution.

    All feature access checks must go through this class.
    Never check tier directly in routes or services.
    """

    def __init__(self, session: "Session"):
        """Initialize resolver with database session.

        Args:
            session: SQLAlchemy session for loading configuration.
        """
        self.session = session
        self._config: AppConfiguration | None = None

    @property
    def config(self) -> AppConfiguration:
        """Lazy-load app configuration from database.

        Returns default FREE tier config if no config exists.
        """
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> AppConfiguration:
        """Load configuration from database."""
        # Import here to avoid circular imports
        from wine_agent.db.models import AppConfigurationDB

        from sqlalchemy import select

        stmt = select(AppConfigurationDB).where(AppConfigurationDB.id == 1)
        db_config = self.session.execute(stmt).scalar_one_or_none()

        if db_config is None:
            # Return default config (FREE tier)
            return AppConfiguration()

        return AppConfiguration(
            license_key=db_config.license_key,
            license_validated_at=db_config.license_validated_at,
            subscription_tier=SubscriptionTier(db_config.subscription_tier),
            tier_expires_at=db_config.tier_expires_at,
            email=db_config.email,
            machine_id=db_config.machine_id,
            created_at=db_config.created_at,
            updated_at=db_config.updated_at,
        )

    @property
    def current_tier(self) -> SubscriptionTier:
        """Get current effective tier, accounting for expiration.

        Returns FREE tier if subscription has expired.
        """
        config = self.config

        # Check if subscription has expired
        if config.tier_expires_at is not None:
            if config.tier_expires_at < datetime.now(UTC):
                return SubscriptionTier.FREE

        return config.subscription_tier

    @property
    def is_expired(self) -> bool:
        """Check if the subscription has expired."""
        config = self.config
        if config.tier_expires_at is None:
            return False
        return config.tier_expires_at < datetime.now(UTC)

    @property
    def was_previously_paid(self) -> bool:
        """Check if user was previously on a paid tier (for downgrade handling)."""
        config = self.config
        return (
            config.subscription_tier != SubscriptionTier.FREE
            and self.is_expired
        )

    def can_access(self, feature: Feature) -> EntitlementResult:
        """Check if current tier can access a feature.

        Args:
            feature: The feature to check access for.

        Returns:
            EntitlementResult with allowed status and upgrade info if denied.
        """
        tier = self.current_tier
        allowed_features = TIER_FEATURES[tier]

        if feature in allowed_features:
            return EntitlementResult(allowed=True)

        # Feature not allowed - find minimum tier required
        min_tier = _get_minimum_tier_for_feature(feature)

        return EntitlementResult(
            allowed=False,
            reason=f"{feature.value} requires {min_tier.value.upper()} tier or higher",
            upgrade_tier=min_tier,
        )

    def require_feature(self, feature: Feature) -> None:
        """Require access to a feature, raising error if denied.

        Args:
            feature: The feature to require access for.

        Raises:
            EntitlementError: If the feature is not available for current tier.
        """
        result = self.can_access(feature)
        if not result.allowed:
            raise EntitlementError(result.reason or "Feature not available", result.upgrade_tier)

    def check_limit(self, resource: str, current_count: int) -> EntitlementResult:
        """Check if a resource limit has been reached.

        Args:
            resource: The resource type (e.g., 'max_wines').
            current_count: The current count of the resource.

        Returns:
            EntitlementResult with allowed status and limit info if reached.
        """
        tier = self.current_tier
        limits = TIER_LIMITS[tier]
        limit = limits.get(resource)

        # None means unlimited
        if limit is None:
            return EntitlementResult(allowed=True)

        if current_count >= limit:
            return EntitlementResult(
                allowed=False,
                reason=f"Limit of {limit} {resource.replace('_', ' ')} reached for {tier.value.upper()} tier",
                upgrade_tier=SubscriptionTier.PRO,
            )

        return EntitlementResult(allowed=True)

    def get_limit(self, resource: str) -> int | None:
        """Get the limit for a resource.

        Args:
            resource: The resource type (e.g., 'max_wines').

        Returns:
            The limit value, or None if unlimited.
        """
        tier = self.current_tier
        return TIER_LIMITS[tier].get(resource)

    def get_feature_summary(self) -> dict[str, bool]:
        """Get a summary of all feature access for current tier.

        Returns:
            Dict mapping feature names to access status.
        """
        return {
            feature.value: self.can_access(feature).allowed
            for feature in Feature
        }

    def get_tier_info(self) -> dict:
        """Get information about the current tier status.

        Returns:
            Dict with tier status, expiration, and limits.
        """
        config = self.config
        tier = self.current_tier

        return {
            "current_tier": tier.value,
            "stored_tier": config.subscription_tier.value,
            "is_expired": self.is_expired,
            "expires_at": config.tier_expires_at.isoformat() if config.tier_expires_at else None,
            "limits": TIER_LIMITS[tier],
            "email": config.email,
        }
