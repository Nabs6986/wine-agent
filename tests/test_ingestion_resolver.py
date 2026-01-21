"""Tests for the ingestion resolver module."""

from uuid import uuid4

import pytest

from wine_agent.ingestion.normalizer import NormalizedListing
from wine_agent.ingestion.resolver import EntityResolver, MatchAction, MatchCandidate


class TestEntityResolver:
    """Tests for the EntityResolver class."""

    def test_levenshtein_distance_identical(self) -> None:
        """Test Levenshtein distance for identical strings."""
        distance = EntityResolver._levenshtein_distance("hello", "hello")
        assert distance == 0

    def test_levenshtein_distance_different(self) -> None:
        """Test Levenshtein distance for different strings."""
        distance = EntityResolver._levenshtein_distance("hello", "hallo")
        assert distance == 1

    def test_levenshtein_distance_empty(self) -> None:
        """Test Levenshtein distance with empty string."""
        distance = EntityResolver._levenshtein_distance("hello", "")
        assert distance == 5

    def test_string_similarity_identical(self) -> None:
        """Test string similarity for identical strings."""
        resolver = EntityResolver.__new__(EntityResolver)
        similarity = resolver._string_similarity("Château Margaux", "Château Margaux")
        assert similarity == 1.0

    def test_string_similarity_case_insensitive(self) -> None:
        """Test string similarity is case insensitive."""
        resolver = EntityResolver.__new__(EntityResolver)
        similarity = resolver._string_similarity("CHÂTEAU MARGAUX", "château margaux")
        assert similarity == 1.0

    def test_string_similarity_similar(self) -> None:
        """Test string similarity for similar strings."""
        resolver = EntityResolver.__new__(EntityResolver)
        similarity = resolver._string_similarity("Chateau Margaux", "Château Margaux")
        # Should be high but not perfect due to accent
        assert similarity > 0.9

    def test_string_similarity_different(self) -> None:
        """Test string similarity for different strings."""
        resolver = EntityResolver.__new__(EntityResolver)
        similarity = resolver._string_similarity("Château Margaux", "Opus One")
        assert similarity < 0.5

    def test_string_similarity_empty(self) -> None:
        """Test string similarity with empty strings."""
        resolver = EntityResolver.__new__(EntityResolver)
        assert resolver._string_similarity("hello", "") == 0.0
        assert resolver._string_similarity("", "hello") == 0.0


class TestMatchCandidate:
    """Tests for the MatchCandidate dataclass."""

    def test_create_match_candidate(self) -> None:
        """Test creating a match candidate."""
        candidate = MatchCandidate(
            entity_id=uuid4(),
            entity_type="producer",
            entity_name="Test Producer",
            confidence=0.95,
            matched_value="Test Producr",  # Typo in source
        )
        assert candidate.entity_type == "producer"
        assert candidate.confidence == 0.95


class TestMatchAction:
    """Tests for the MatchAction enum."""

    def test_auto_merge_value(self) -> None:
        """Test AUTO_MERGE enum value."""
        assert MatchAction.AUTO_MERGE.value == "auto_merge"

    def test_review_queue_value(self) -> None:
        """Test REVIEW_QUEUE enum value."""
        assert MatchAction.REVIEW_QUEUE.value == "review_queue"

    def test_new_candidate_value(self) -> None:
        """Test NEW_CANDIDATE enum value."""
        assert MatchAction.NEW_CANDIDATE.value == "new_candidate"


class TestResolutionLogic:
    """Tests for resolution logic without database."""

    def test_determine_action_high_confidence(self) -> None:
        """Test action determination for high confidence matches."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)
        resolver.auto_merge_threshold = 0.90
        resolver.review_queue_threshold = 0.70

        result = ResolutionResult(
            listing_id=uuid4(),
            producer_match=MatchCandidate(
                entity_id=uuid4(),
                entity_type="producer",
                entity_name="Test",
                confidence=0.95,
                matched_value="Test",
            ),
        )

        action = resolver._determine_action(result)
        assert action == MatchAction.AUTO_MERGE

    def test_determine_action_medium_confidence(self) -> None:
        """Test action determination for medium confidence matches."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)
        resolver.auto_merge_threshold = 0.90
        resolver.review_queue_threshold = 0.70

        result = ResolutionResult(
            listing_id=uuid4(),
            producer_match=MatchCandidate(
                entity_id=uuid4(),
                entity_type="producer",
                entity_name="Test",
                confidence=0.80,
                matched_value="Test",
            ),
        )

        action = resolver._determine_action(result)
        assert action == MatchAction.REVIEW_QUEUE

    def test_determine_action_low_confidence(self) -> None:
        """Test action determination for low confidence matches."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)
        resolver.auto_merge_threshold = 0.90
        resolver.review_queue_threshold = 0.70

        result = ResolutionResult(
            listing_id=uuid4(),
            producer_match=MatchCandidate(
                entity_id=uuid4(),
                entity_type="producer",
                entity_name="Test",
                confidence=0.50,
                matched_value="Test",
            ),
        )

        action = resolver._determine_action(result)
        assert action == MatchAction.NEW_CANDIDATE

    def test_determine_action_no_matches(self) -> None:
        """Test action determination with no matches."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)
        resolver.auto_merge_threshold = 0.90
        resolver.review_queue_threshold = 0.70

        result = ResolutionResult(listing_id=uuid4())

        action = resolver._determine_action(result)
        assert action == MatchAction.NEW_CANDIDATE

    def test_should_create_producer_no_match(self) -> None:
        """Test that producer should be created when no match."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)
        resolver.review_queue_threshold = 0.70

        result = ResolutionResult(listing_id=uuid4())

        assert resolver._should_create_producer(result) is True

    def test_should_create_producer_low_confidence(self) -> None:
        """Test that producer should be created when confidence is low."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)
        resolver.review_queue_threshold = 0.70

        result = ResolutionResult(
            listing_id=uuid4(),
            producer_match=MatchCandidate(
                entity_id=uuid4(),
                entity_type="producer",
                entity_name="Test",
                confidence=0.50,
                matched_value="Test",
            ),
        )

        assert resolver._should_create_producer(result) is True

    def test_should_create_producer_high_confidence(self) -> None:
        """Test that producer should NOT be created when confidence is high."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)
        resolver.review_queue_threshold = 0.70

        result = ResolutionResult(
            listing_id=uuid4(),
            producer_match=MatchCandidate(
                entity_id=uuid4(),
                entity_type="producer",
                entity_name="Test",
                confidence=0.90,
                matched_value="Test",
            ),
        )

        assert resolver._should_create_producer(result) is False

    def test_should_create_vintage_no_vintage(self) -> None:
        """Test that vintage should NOT be created for NV wines."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)

        result = ResolutionResult(listing_id=uuid4())
        listing = NormalizedListing(vintage_year=None)  # Non-vintage

        assert resolver._should_create_vintage(result, listing) is False

    def test_should_create_vintage_no_match(self) -> None:
        """Test that vintage should be created when no match."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)

        result = ResolutionResult(listing_id=uuid4())
        listing = NormalizedListing(vintage_year=2019)

        assert resolver._should_create_vintage(result, listing) is True

    def test_resolution_notes(self) -> None:
        """Test that resolution notes are added."""
        from wine_agent.ingestion.resolver import ResolutionResult

        resolver = EntityResolver.__new__(EntityResolver)

        result = ResolutionResult(
            listing_id=uuid4(),
            producer_match=MatchCandidate(
                entity_id=uuid4(),
                entity_type="producer",
                entity_name="Test Producer",
                confidence=0.85,
                matched_value="Test Producr",
            ),
            action=MatchAction.REVIEW_QUEUE,
        )
        listing = NormalizedListing(
            producer_name="Test Producr",
            wine_name="Test Wine",
        )

        resolver._add_resolution_notes(result, listing)

        assert len(result.notes) > 0
        assert any("Producer" in note for note in result.notes)
        assert any("review_queue" in note for note in result.notes)
