"""
Entity Resolver Module
======================

Matches normalized wine listings to canonical entities (Producer, Wine, Vintage)
using string similarity and configurable confidence thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from wine_agent.db.models_canonical import ProducerDB, VintageDB, WineDB
from wine_agent.ingestion.normalizer import NormalizedListing

if TYPE_CHECKING:
    from wine_agent.ingestion.registry import EntityResolutionConfig

logger = logging.getLogger(__name__)


class MatchAction(str, Enum):
    """Action to take based on match confidence."""

    AUTO_MERGE = "auto_merge"  # High confidence - auto-link to existing entity
    REVIEW_QUEUE = "review_queue"  # Medium confidence - needs manual review
    NEW_CANDIDATE = "new_candidate"  # Low confidence - create new entity


@dataclass
class MatchCandidate:
    """A potential match for an entity."""

    entity_id: UUID
    entity_type: str  # "producer", "wine", "vintage"
    entity_name: str
    confidence: float  # 0.0 - 1.0
    matched_value: str  # The value that was matched against


@dataclass
class ResolutionResult:
    """Result of resolving a listing to canonical entities."""

    listing_id: UUID

    # Match results (None if no match found)
    producer_match: MatchCandidate | None = None
    wine_match: MatchCandidate | None = None
    vintage_match: MatchCandidate | None = None

    # Recommended action based on overall confidence
    action: MatchAction = MatchAction.NEW_CANDIDATE

    # Flags for creating new entities
    create_producer: bool = False
    create_wine: bool = False
    create_vintage: bool = False

    # Details
    notes: list[str] = field(default_factory=list)


class EntityResolver:
    """
    Resolves normalized listings to canonical entities.

    Uses string similarity matching to find existing entities
    and determines the appropriate action based on confidence thresholds.
    """

    def __init__(
        self,
        session: Session,
        auto_merge_threshold: float = 0.90,
        review_queue_threshold: float = 0.70,
    ) -> None:
        """
        Initialize the resolver.

        Args:
            session: SQLAlchemy database session
            auto_merge_threshold: Confidence >= this triggers auto-merge
            review_queue_threshold: Confidence >= this triggers review queue
        """
        self.session = session
        self.auto_merge_threshold = auto_merge_threshold
        self.review_queue_threshold = review_queue_threshold

    @classmethod
    def from_config(cls, session: Session, config: EntityResolutionConfig) -> EntityResolver:
        """Create resolver from configuration."""
        return cls(
            session=session,
            auto_merge_threshold=config.auto_merge_threshold,
            review_queue_threshold=config.review_queue_threshold,
        )

    def resolve(
        self,
        listing: NormalizedListing,
        listing_id: UUID | None = None,
    ) -> ResolutionResult:
        """
        Resolve a normalized listing to canonical entities.

        Args:
            listing: Normalized listing data
            listing_id: Optional pre-assigned listing ID

        Returns:
            ResolutionResult with matches and recommended actions
        """
        if listing_id is None:
            listing_id = uuid4()

        result = ResolutionResult(listing_id=listing_id)

        # Match producer
        if listing.producer_name:
            result.producer_match = self._match_producer(listing.producer_name)

        # Match wine (requires producer match for scoped lookup)
        if listing.wine_name:
            producer_id = result.producer_match.entity_id if result.producer_match else None
            result.wine_match = self._match_wine(listing.wine_name, producer_id)

        # Match vintage (requires wine match for scoped lookup)
        if listing.vintage_year:
            wine_id = result.wine_match.entity_id if result.wine_match else None
            result.vintage_match = self._match_vintage(listing.vintage_year, wine_id)

        # Determine overall action
        result.action = self._determine_action(result)

        # Determine what needs to be created
        result.create_producer = self._should_create_producer(result)
        result.create_wine = self._should_create_wine(result)
        result.create_vintage = self._should_create_vintage(result, listing)

        # Add notes
        self._add_resolution_notes(result, listing)

        return result

    def _match_producer(self, producer_name: str) -> MatchCandidate | None:
        """
        Find the best matching producer.

        Args:
            producer_name: Normalized producer name

        Returns:
            Best match if above minimum threshold, None otherwise
        """
        import json

        # Query all producers (in production, use full-text search or limit scope)
        producers = self.session.query(ProducerDB).all()

        best_match: MatchCandidate | None = None
        best_confidence = 0.0

        for producer in producers:
            # Match against canonical_name
            confidence = self._string_similarity(producer_name, producer.canonical_name)

            # Also check aliases if available
            try:
                aliases = json.loads(producer.aliases_json) if producer.aliases_json else []
            except (json.JSONDecodeError, TypeError):
                aliases = []

            for alias in aliases:
                alias_conf = self._string_similarity(producer_name, alias)
                confidence = max(confidence, alias_conf)

            if confidence > best_confidence and confidence >= 0.5:  # Minimum threshold
                best_confidence = confidence
                best_match = MatchCandidate(
                    entity_id=producer.id,
                    entity_type="producer",
                    entity_name=producer.canonical_name,
                    confidence=confidence,
                    matched_value=producer_name,
                )

        return best_match

    def _match_wine(self, wine_name: str, producer_id: UUID | None) -> MatchCandidate | None:
        """
        Find the best matching wine.

        Args:
            wine_name: Normalized wine name
            producer_id: Optional producer ID to scope the search

        Returns:
            Best match if above minimum threshold, None otherwise
        """
        query = self.session.query(WineDB)
        if producer_id:
            query = query.filter(WineDB.producer_id == producer_id)

        wines = query.all()

        best_match: MatchCandidate | None = None
        best_confidence = 0.0

        for wine in wines:
            confidence = self._string_similarity(wine_name, wine.canonical_name)

            # Boost confidence if producer matches
            if producer_id and wine.producer_id == producer_id:
                confidence = min(1.0, confidence + 0.1)

            if confidence > best_confidence and confidence >= 0.5:
                best_confidence = confidence
                best_match = MatchCandidate(
                    entity_id=wine.id,
                    entity_type="wine",
                    entity_name=wine.canonical_name,
                    confidence=confidence,
                    matched_value=wine_name,
                )

        return best_match

    def _match_vintage(self, vintage_year: int, wine_id: UUID | None) -> MatchCandidate | None:
        """
        Find the best matching vintage.

        Args:
            vintage_year: Vintage year
            wine_id: Optional wine ID to scope the search

        Returns:
            Exact match if found, None otherwise
        """
        query = self.session.query(VintageDB).filter(VintageDB.year == vintage_year)
        if wine_id:
            query = query.filter(VintageDB.wine_id == wine_id)

        vintage = query.first()
        if vintage:
            return MatchCandidate(
                entity_id=vintage.id,
                entity_type="vintage",
                entity_name=f"{vintage_year}",
                confidence=1.0,  # Exact year match
                matched_value=str(vintage_year),
            )

        return None

    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate string similarity using Levenshtein distance.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score between 0.0 and 1.0
        """
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()

        if s1 == s2:
            return 1.0

        if not s1 or not s2:
            return 0.0

        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))

        return 1.0 - (distance / max_len)

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate the Levenshtein distance between two strings.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Edit distance
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost is 0 if characters match, 1 otherwise
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _determine_action(self, result: ResolutionResult) -> MatchAction:
        """
        Determine the overall action based on match confidences.

        Args:
            result: Resolution result with matches

        Returns:
            Recommended action
        """
        # Collect all confidence scores
        confidences = []
        if result.producer_match:
            confidences.append(result.producer_match.confidence)
        if result.wine_match:
            confidences.append(result.wine_match.confidence)
        if result.vintage_match:
            confidences.append(result.vintage_match.confidence)

        if not confidences:
            return MatchAction.NEW_CANDIDATE

        # Use minimum confidence for conservative matching
        min_confidence = min(confidences)

        if min_confidence >= self.auto_merge_threshold:
            return MatchAction.AUTO_MERGE
        elif min_confidence >= self.review_queue_threshold:
            return MatchAction.REVIEW_QUEUE
        else:
            return MatchAction.NEW_CANDIDATE

    def _should_create_producer(self, result: ResolutionResult) -> bool:
        """Determine if a new producer should be created."""
        if result.producer_match is None:
            return True
        if result.producer_match.confidence < self.review_queue_threshold:
            return True
        return False

    def _should_create_wine(self, result: ResolutionResult) -> bool:
        """Determine if a new wine should be created."""
        if result.wine_match is None:
            return True
        if result.wine_match.confidence < self.review_queue_threshold:
            return True
        return False

    def _should_create_vintage(
        self,
        result: ResolutionResult,
        listing: NormalizedListing,
    ) -> bool:
        """Determine if a new vintage should be created."""
        if listing.vintage_year is None:
            return False  # Non-vintage wine
        if result.vintage_match is None:
            return True
        return False

    def _add_resolution_notes(
        self,
        result: ResolutionResult,
        listing: NormalizedListing,
    ) -> None:
        """Add human-readable notes to the resolution result."""
        if result.producer_match:
            result.notes.append(
                f"Producer '{listing.producer_name}' matched to "
                f"'{result.producer_match.entity_name}' "
                f"({result.producer_match.confidence:.0%} confidence)"
            )
        elif listing.producer_name:
            result.notes.append(f"No match found for producer '{listing.producer_name}'")

        if result.wine_match:
            result.notes.append(
                f"Wine '{listing.wine_name}' matched to "
                f"'{result.wine_match.entity_name}' "
                f"({result.wine_match.confidence:.0%} confidence)"
            )
        elif listing.wine_name:
            result.notes.append(f"No match found for wine '{listing.wine_name}'")

        if result.vintage_match:
            result.notes.append(
                f"Vintage {listing.vintage_year} matched to existing record"
            )
        elif listing.vintage_year:
            result.notes.append(f"No existing vintage record for {listing.vintage_year}")

        result.notes.append(f"Recommended action: {result.action.value}")


def create_entities_from_listing(
    session: Session,
    listing: NormalizedListing,
    result: ResolutionResult,
) -> dict[str, UUID]:
    """
    Create canonical entities from a listing based on resolution result.

    Args:
        session: Database session
        listing: Normalized listing
        result: Resolution result

    Returns:
        Dict mapping entity type to created/matched entity ID
    """
    entities: dict[str, UUID] = {}

    # Create or use existing producer
    if result.create_producer and listing.producer_name:
        producer = ProducerDB(
            id=str(uuid4()),
            canonical_name=listing.producer_name,
            country=listing.country or "",
            region=listing.region or "",
        )
        session.add(producer)
        entities["producer"] = producer.id
        logger.info(f"Created new producer: {listing.producer_name}")
    elif result.producer_match:
        entities["producer"] = result.producer_match.entity_id

    # Create or use existing wine
    if result.create_wine and listing.wine_name:
        producer_id = entities.get("producer")
        wine = WineDB(
            id=str(uuid4()),
            canonical_name=listing.wine_name,
            producer_id=producer_id,
            color=listing.color,
            style=listing.style,
        )
        session.add(wine)
        entities["wine"] = wine.id
        logger.info(f"Created new wine: {listing.wine_name}")
    elif result.wine_match:
        entities["wine"] = result.wine_match.entity_id

    # Create or use existing vintage
    if result.create_vintage and listing.vintage_year:
        wine_id = entities.get("wine")
        vintage = VintageDB(
            id=str(uuid4()),
            wine_id=wine_id,
            year=listing.vintage_year,
            abv=listing.abv,
            bottle_size_ml=listing.bottle_size_ml,
        )
        session.add(vintage)
        entities["vintage"] = vintage.id
        logger.info(f"Created new vintage: {listing.vintage_year}")
    elif result.vintage_match:
        entities["vintage"] = result.vintage_match.entity_id

    return entities
