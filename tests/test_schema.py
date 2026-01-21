"""Tests for canonical Pydantic models."""

import json
from datetime import date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from wine_agent.core.enums import (
    ConfidenceLevel,
    DrinkOrHold,
    NoteSource,
    NoteStatus,
    QualityBand,
    StructureLevel,
    Sweetness,
    WineColor,
    WineStyle,
)
from wine_agent.core.schema import (
    AIConversionRun,
    Confidence,
    Descriptors,
    Faults,
    InboxItem,
    Pairing,
    Provenance,
    PurchaseContext,
    Readiness,
    Revision,
    Scores,
    StructureLevels,
    SubScores,
    TastingContext,
    TastingNote,
    WineIdentity,
)


class TestInboxItem:
    """Tests for InboxItem model."""

    def test_create_inbox_item(self) -> None:
        """Test creating a basic inbox item."""
        item = InboxItem(raw_text="Great wine from Burgundy, 2019 vintage")
        assert item.raw_text == "Great wine from Burgundy, 2019 vintage"
        assert isinstance(item.id, UUID)
        assert isinstance(item.created_at, datetime)
        assert item.converted is False
        assert item.conversion_run_id is None

    def test_inbox_item_empty_text_fails(self) -> None:
        """Test that empty raw_text raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            InboxItem(raw_text="")
        assert "raw_text cannot be empty" in str(exc_info.value)

    def test_inbox_item_whitespace_only_fails(self) -> None:
        """Test that whitespace-only raw_text raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            InboxItem(raw_text="   \n\t  ")
        assert "raw_text cannot be empty" in str(exc_info.value)

    def test_inbox_item_with_tags(self) -> None:
        """Test inbox item with tags."""
        item = InboxItem(
            raw_text="Test note",
            tags=["burgundy", "pinot-noir", "2019"],
        )
        assert item.tags == ["burgundy", "pinot-noir", "2019"]


class TestWineIdentity:
    """Tests for WineIdentity model."""

    def test_default_wine_identity(self) -> None:
        """Test default wine identity."""
        wine = WineIdentity()
        assert wine.producer == ""
        assert wine.vintage is None
        assert wine.grapes == []
        assert wine.bottle_size_ml == 750

    def test_complete_wine_identity(self) -> None:
        """Test complete wine identity."""
        wine = WineIdentity(
            producer="Domaine de la Romanée-Conti",
            cuvee="La Tâche",
            vintage=2019,
            country="France",
            region="Burgundy",
            subregion="Côte de Nuits",
            appellation="La Tâche Grand Cru",
            grapes=["Pinot Noir"],
            color=WineColor.RED,
            style=WineStyle.STILL,
            sweetness=Sweetness.DRY,
            alcohol_percent=13.5,
        )
        assert wine.producer == "Domaine de la Romanée-Conti"
        assert wine.vintage == 2019
        assert wine.color == WineColor.RED


class TestSubScores:
    """Tests for SubScores model."""

    def test_default_subscores(self) -> None:
        """Test default subscores are all zero."""
        subscores = SubScores()
        assert subscores.appearance == 0
        assert subscores.nose == 0
        assert subscores.palate == 0
        assert subscores.structure_balance == 0
        assert subscores.finish == 0
        assert subscores.typicity_complexity == 0
        assert subscores.overall_judgment == 0

    def test_valid_subscores(self) -> None:
        """Test valid subscores within ranges."""
        subscores = SubScores(
            appearance=2,
            nose=10,
            palate=18,
            structure_balance=17,
            finish=9,
            typicity_complexity=14,
            overall_judgment=18,
        )
        assert subscores.appearance == 2
        assert subscores.nose == 10

    def test_appearance_out_of_range(self) -> None:
        """Test appearance score out of range."""
        with pytest.raises(ValidationError):
            SubScores(appearance=3)

    def test_nose_out_of_range(self) -> None:
        """Test nose score out of range."""
        with pytest.raises(ValidationError):
            SubScores(nose=15)

    def test_palate_out_of_range(self) -> None:
        """Test palate score out of range."""
        with pytest.raises(ValidationError):
            SubScores(palate=25)

    def test_negative_score_fails(self) -> None:
        """Test negative scores fail validation."""
        with pytest.raises(ValidationError):
            SubScores(appearance=-1)


class TestScores:
    """Tests for Scores model."""

    def test_scores_compute_total(self) -> None:
        """Test that total is computed from subscores."""
        scores = Scores(
            subscores=SubScores(
                appearance=2,
                nose=10,
                palate=18,
                structure_balance=17,
                finish=9,
                typicity_complexity=14,
                overall_judgment=18,
            )
        )
        expected_total = 2 + 10 + 18 + 17 + 9 + 14 + 18
        assert scores.total == expected_total
        assert scores.total == 88

    def test_scores_quality_band_outstanding(self) -> None:
        """Test outstanding quality band."""
        scores = Scores(
            subscores=SubScores(
                appearance=2,
                nose=12,
                palate=20,
                structure_balance=20,
                finish=10,
                typicity_complexity=16,
                overall_judgment=18,
            )
        )
        assert scores.total == 98
        assert scores.quality_band == QualityBand.OUTSTANDING

    def test_scores_quality_band_poor(self) -> None:
        """Test poor quality band."""
        scores = Scores(
            subscores=SubScores(
                appearance=1,
                nose=5,
                palate=10,
                structure_balance=10,
                finish=5,
                typicity_complexity=8,
                overall_judgment=10,
            )
        )
        assert scores.total == 49
        assert scores.quality_band == QualityBand.POOR


class TestTastingNote:
    """Tests for TastingNote model."""

    def test_create_empty_tasting_note(self) -> None:
        """Test creating a tasting note with defaults."""
        note = TastingNote()
        assert isinstance(note.id, UUID)
        assert note.status == NoteStatus.DRAFT
        assert note.source == NoteSource.MANUAL
        assert note.scores.total == 0

    def test_create_complete_tasting_note(self) -> None:
        """Test creating a complete tasting note."""
        note = TastingNote(
            wine=WineIdentity(
                producer="Ridge Vineyards",
                cuvee="Monte Bello",
                vintage=2018,
                country="USA",
                region="California",
                subregion="Santa Cruz Mountains",
                grapes=["Cabernet Sauvignon", "Merlot"],
                color=WineColor.RED,
            ),
            context=TastingContext(
                tasting_date=date(2023, 12, 15),
                location="Home",
            ),
            scores=Scores(
                subscores=SubScores(
                    appearance=2,
                    nose=11,
                    palate=18,
                    structure_balance=18,
                    finish=9,
                    typicity_complexity=15,
                    overall_judgment=18,
                )
            ),
            descriptors=Descriptors(
                primary_fruit=["blackcurrant", "black cherry"],
                secondary=["cedar", "vanilla"],
                tertiary=["tobacco"],
            ),
            status=NoteStatus.PUBLISHED,
        )
        assert note.wine.producer == "Ridge Vineyards"
        assert note.scores.total == 91
        assert note.scores.quality_band == QualityBand.VERY_GOOD
        assert note.status == NoteStatus.PUBLISHED

    def test_tasting_note_serialization(self) -> None:
        """Test that tasting note can be serialized to JSON."""
        note = TastingNote(
            wine=WineIdentity(
                producer="Test Producer",
                vintage=2020,
                color=WineColor.WHITE,
            ),
            scores=Scores(
                subscores=SubScores(
                    appearance=2,
                    nose=10,
                    palate=16,
                    structure_balance=15,
                    finish=8,
                    typicity_complexity=12,
                    overall_judgment=15,
                )
            ),
        )
        json_str = note.model_dump_json()
        data = json.loads(json_str)

        assert data["wine"]["producer"] == "Test Producer"
        assert data["wine"]["vintage"] == 2020
        assert data["wine"]["color"] == "white"
        assert data["scores"]["total"] == 78
        assert data["scores"]["quality_band"] == "acceptable"

    def test_tasting_note_deserialization(self) -> None:
        """Test that tasting note can be deserialized from JSON."""
        json_data = {
            "wine": {
                "producer": "Château Margaux",
                "vintage": 2015,
                "color": "red",
            },
            "scores": {
                "subscores": {
                    "appearance": 2,
                    "nose": 11,
                    "palate": 19,
                    "structure_balance": 19,
                    "finish": 10,
                    "typicity_complexity": 15,
                    "overall_judgment": 19,
                }
            },
        }
        note = TastingNote.model_validate(json_data)
        assert note.wine.producer == "Château Margaux"
        assert note.scores.total == 95
        assert note.scores.quality_band == QualityBand.OUTSTANDING


class TestAIConversionRun:
    """Tests for AIConversionRun model."""

    def test_create_conversion_run(self) -> None:
        """Test creating an AI conversion run."""
        inbox_id = UUID("12345678-1234-5678-1234-567812345678")
        run = AIConversionRun(
            inbox_item_id=inbox_id,
            provider="anthropic",
            model="claude-3-sonnet",
            prompt_version="1.0",
            input_hash="abc123",
            raw_input="Test input",
            raw_response='{"wine": {}}',
            parsed_json={"wine": {}},
            success=True,
        )
        assert run.inbox_item_id == inbox_id
        assert run.provider == "anthropic"
        assert run.success is True


class TestRevision:
    """Tests for Revision model."""

    def test_create_revision(self) -> None:
        """Test creating a revision."""
        note_id = UUID("12345678-1234-5678-1234-567812345678")
        revision = Revision(
            tasting_note_id=note_id,
            revision_number=1,
            changed_fields=["wine.producer", "scores.subscores.nose"],
            previous_snapshot={"wine": {"producer": "Old Producer"}},
            new_snapshot={"wine": {"producer": "New Producer"}},
            change_reason="Corrected producer name",
        )
        assert revision.tasting_note_id == note_id
        assert revision.revision_number == 1
        assert "wine.producer" in revision.changed_fields
