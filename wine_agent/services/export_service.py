"""Export service for tasting notes (Markdown, CSV, JSON)."""

import csv
import io
import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from wine_agent.core.schema import TastingNote
from wine_agent.db.repositories import TastingNoteRepository


def _serialize_value(value: Any) -> Any:
    """Serialize a value for YAML/JSON output."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "value"):  # Enum
        return value.value
    return value


def _build_yaml_frontmatter(note: TastingNote) -> str:
    """Build YAML frontmatter for a tasting note."""
    lines = ["---"]

    # Basic metadata
    lines.append("type: wine_tasting_note")
    lines.append(f'template_version: "{note.template_version}"')
    lines.append(f"tags:")
    for tag in note.tags:
        lines.append(f"  - {tag}")
    if not note.tags:
        lines.append("  - wine-agent")
        lines.append("  - tasting-note")

    lines.append(f'created: "{note.created_at.isoformat()}"')
    lines.append(f'updated: "{note.updated_at.isoformat()}"')
    lines.append(f'source: "{note.source.value}"')
    lines.append(f'status: "{note.status.value}"')
    if note.inbox_item_id:
        lines.append(f'inbox_item_id: "{note.inbox_item_id}"')
    else:
        lines.append("inbox_item_id: null")

    # Wine identity
    lines.append("wine:")
    lines.append(f'  producer: "{note.wine.producer}"')
    lines.append(f'  cuvee: "{note.wine.cuvee}"')
    lines.append(f"  vintage: {note.wine.vintage if note.wine.vintage else 'null'}")
    lines.append(f'  country: "{note.wine.country}"')
    lines.append(f'  region: "{note.wine.region}"')
    lines.append(f'  subregion: "{note.wine.subregion}"')
    lines.append(f'  appellation: "{note.wine.appellation}"')
    lines.append(f'  vineyard: "{note.wine.vineyard}"')
    lines.append("  grapes:")
    for grape in note.wine.grapes:
        lines.append(f"    - {grape}")
    if not note.wine.grapes:
        lines.append("    []")
    lines.append(f'  color: "{note.wine.color.value if note.wine.color else ""}"')
    lines.append(f'  style: "{note.wine.style.value if note.wine.style else ""}"')
    lines.append(f'  sweetness: "{note.wine.sweetness.value if note.wine.sweetness else ""}"')
    lines.append(f"  alcohol_percent: {note.wine.alcohol_percent if note.wine.alcohol_percent else 'null'}")
    lines.append(f'  closure: "{note.wine.closure.value if note.wine.closure else ""}"')
    lines.append(f"  bottle_size_ml: {note.wine.bottle_size_ml}")

    # Purchase context
    lines.append("purchase:")
    lines.append(f"  price_usd: {note.purchase.price_usd if note.purchase.price_usd else 'null'}")
    lines.append(f'  store: "{note.purchase.store}"')
    lines.append(f"  purchase_date: {note.purchase.purchase_date.isoformat() if note.purchase.purchase_date else 'null'}")

    # Tasting context
    lines.append("context:")
    lines.append(f"  tasting_date: {note.context.tasting_date.isoformat() if note.context.tasting_date else 'null'}")
    lines.append(f'  location: "{note.context.location}"')
    lines.append(f'  glassware: "{note.context.glassware}"')
    lines.append(f'  decant: "{note.context.decant.value if note.context.decant else ""}"')
    lines.append(f"  decant_minutes: {note.context.decant_minutes if note.context.decant_minutes else 'null'}")
    lines.append(f"  serving_temp_c: {note.context.serving_temp_c if note.context.serving_temp_c else 'null'}")
    lines.append(f'  companions: "{note.context.companions}"')
    lines.append(f'  occasion: "{note.context.occasion}"')
    lines.append(f'  food_pairing: "{note.context.food_pairing}"')
    lines.append(f'  mood: "{note.context.mood}"')

    # Confidence
    lines.append("confidence:")
    lines.append(f'  level: "{note.confidence.level.value}"')
    lines.append(f'  uncertainty_notes: "{note.confidence.uncertainty_notes}"')

    # Faults
    lines.append("faults:")
    lines.append(f"  present: {str(note.faults.present).lower()}")
    lines.append("  suspected:")
    for fault in note.faults.suspected:
        lines.append(f"    - {fault}")
    if not note.faults.suspected:
        lines.append("    []")
    lines.append(f'  notes: "{note.faults.notes}"')

    # Readiness
    lines.append("readiness:")
    lines.append(f'  drink_or_hold: "{note.readiness.drink_or_hold.value}"')
    lines.append(f"  window_start_year: {note.readiness.window_start_year if note.readiness.window_start_year else 'null'}")
    lines.append(f"  window_end_year: {note.readiness.window_end_year if note.readiness.window_end_year else 'null'}")
    lines.append(f'  notes: "{note.readiness.notes}"')

    # Scores
    lines.append("scores:")
    lines.append(f'  system: "{note.scores.system}"')
    lines.append("  subscores:")
    lines.append(f"    appearance: {note.scores.subscores.appearance}")
    lines.append(f"    nose: {note.scores.subscores.nose}")
    lines.append(f"    palate: {note.scores.subscores.palate}")
    lines.append(f"    structure_balance: {note.scores.subscores.structure_balance}")
    lines.append(f"    finish: {note.scores.subscores.finish}")
    lines.append(f"    typicity_complexity: {note.scores.subscores.typicity_complexity}")
    lines.append(f"    overall_judgment: {note.scores.subscores.overall_judgment}")
    lines.append(f"  total: {note.scores.total}")
    lines.append(f'  quality_band: "{note.scores.quality_band.value if note.scores.quality_band else ""}"')
    lines.append(f"  personal_enjoyment: {note.scores.personal_enjoyment if note.scores.personal_enjoyment else 'null'}")
    lines.append(f"  value_for_money: {note.scores.value_for_money if note.scores.value_for_money else 'null'}")

    # Structure levels
    lines.append("structure_levels:")
    lines.append(f'  acidity: "{note.structure_levels.acidity.value if note.structure_levels.acidity else ""}"')
    lines.append(f'  tannin: "{note.structure_levels.tannin.value if note.structure_levels.tannin else ""}"')
    lines.append(f'  body: "{note.structure_levels.body.value if note.structure_levels.body else ""}"')
    lines.append(f'  alcohol: "{note.structure_levels.alcohol.value if note.structure_levels.alcohol else ""}"')
    lines.append(f'  sweetness: "{note.structure_levels.sweetness.value if note.structure_levels.sweetness else ""}"')
    lines.append(f'  intensity: "{note.structure_levels.intensity.value if note.structure_levels.intensity else ""}"')
    lines.append(f'  oak: "{note.structure_levels.oak.value if note.structure_levels.oak else ""}"')

    # Descriptors
    lines.append("descriptors:")
    lines.append("  primary_fruit:")
    for desc in note.descriptors.primary_fruit:
        lines.append(f"    - {desc}")
    if not note.descriptors.primary_fruit:
        lines.append("    []")
    lines.append("  secondary:")
    for desc in note.descriptors.secondary:
        lines.append(f"    - {desc}")
    if not note.descriptors.secondary:
        lines.append("    []")
    lines.append("  tertiary:")
    for desc in note.descriptors.tertiary:
        lines.append(f"    - {desc}")
    if not note.descriptors.tertiary:
        lines.append("    []")
    lines.append("  non_fruit:")
    for desc in note.descriptors.non_fruit:
        lines.append(f"    - {desc}")
    if not note.descriptors.non_fruit:
        lines.append("    []")
    lines.append("  texture:")
    for desc in note.descriptors.texture:
        lines.append(f"    - {desc}")
    if not note.descriptors.texture:
        lines.append("    []")

    lines.append("---")
    return "\n".join(lines)


def _build_markdown_body(note: TastingNote) -> str:
    """Build the Markdown body for a tasting note."""
    lines = []

    # Title
    producer = note.wine.producer or "Unknown Producer"
    cuvee = note.wine.cuvee or ""
    vintage = note.wine.vintage or "NV"
    title = f"{producer}"
    if cuvee:
        title += f" - {cuvee}"
    title += f" ({vintage})"
    lines.append(f"# {title}")
    lines.append("")

    # Quick Snapshot
    lines.append("## Quick Snapshot")
    region_path = " -> ".join(filter(None, [
        note.wine.country,
        note.wine.region,
        note.wine.subregion,
        note.wine.appellation,
    ]))
    lines.append(f"- **Region:** {region_path or 'Unknown'}")
    lines.append(f"- **Grapes:** {', '.join(note.wine.grapes) if note.wine.grapes else 'Unknown'}")
    style_parts = filter(None, [
        note.wine.color.value if note.wine.color else None,
        note.wine.style.value if note.wine.style else None,
        note.wine.sweetness.value if note.wine.sweetness else None,
    ])
    lines.append(f"- **Style:** {' / '.join(style_parts) or 'Unknown'}")
    if note.wine.alcohol_percent:
        lines.append(f"- **ABV:** {note.wine.alcohol_percent}%")
    lines.append(f"- **Score:** **{note.scores.total} / 100** (Quality: {note.scores.quality_band.value if note.scores.quality_band else 'N/A'})")
    lines.append(f"- **Drink/Hold:** **{note.readiness.drink_or_hold.value}**", )
    if note.readiness.window_start_year or note.readiness.window_end_year:
        window = f"({note.readiness.window_start_year or '?'}-{note.readiness.window_end_year or '?'})"
        lines[-1] += f" {window}"
    lines.append("")

    # Appearance
    lines.append("---")
    lines.append("")
    lines.append("## Appearance (0-2)")
    if note.appearance_notes:
        lines.append(note.appearance_notes)
    lines.append(f"**Subscore (0-2):** {note.scores.subscores.appearance}")
    lines.append("")

    # Nose
    lines.append("---")
    lines.append("")
    lines.append("## Nose (0-12)")
    if note.nose_notes:
        lines.append(note.nose_notes)
    if note.descriptors.primary_fruit:
        lines.append(f"- **Primary:** {', '.join(note.descriptors.primary_fruit)}")
    if note.descriptors.secondary:
        lines.append(f"- **Secondary:** {', '.join(note.descriptors.secondary)}")
    if note.descriptors.tertiary:
        lines.append(f"- **Tertiary:** {', '.join(note.descriptors.tertiary)}")
    lines.append(f"**Subscore (0-12):** {note.scores.subscores.nose}")
    lines.append("")

    # Palate
    lines.append("---")
    lines.append("")
    lines.append("## Palate (0-20)")
    if note.palate_notes:
        lines.append(note.palate_notes)
    structure_parts = []
    if note.structure_levels.acidity:
        structure_parts.append(f"Acidity: {note.structure_levels.acidity.value}")
    if note.structure_levels.tannin:
        structure_parts.append(f"Tannin: {note.structure_levels.tannin.value}")
    if note.structure_levels.body:
        structure_parts.append(f"Body: {note.structure_levels.body.value}")
    if structure_parts:
        lines.append(f"- **Structure:** {', '.join(structure_parts)}")
    lines.append(f"**Subscore (0-20):** {note.scores.subscores.palate}")
    lines.append("")

    # Structure & Balance
    lines.append("---")
    lines.append("")
    lines.append("## Structure & Balance (0-20)")
    if note.structure_notes:
        lines.append(note.structure_notes)
    lines.append(f"**Subscore (0-20):** {note.scores.subscores.structure_balance}")
    lines.append("")

    # Finish
    lines.append("---")
    lines.append("")
    lines.append("## Finish / Length (0-10)")
    if note.finish_notes:
        lines.append(note.finish_notes)
    lines.append(f"**Subscore (0-10):** {note.scores.subscores.finish}")
    lines.append("")

    # Typicity & Complexity
    lines.append("---")
    lines.append("")
    lines.append("## Typicity & Complexity (0-16)")
    if note.typicity_notes:
        lines.append(note.typicity_notes)
    lines.append(f"**Subscore (0-16):** {note.scores.subscores.typicity_complexity}")
    lines.append("")

    # Overall Quality Judgment
    lines.append("---")
    lines.append("")
    lines.append("## Overall Quality Judgment (0-20)")
    if note.overall_notes:
        lines.append(note.overall_notes)
    lines.append(f"**Subscore (0-20):** {note.scores.subscores.overall_judgment}")
    lines.append("")

    # Final Score & Summary
    lines.append("---")
    lines.append("")
    lines.append("## Final Score & Summary")
    lines.append(f"**Total:** {note.scores.total} / 100")
    lines.append("")
    lines.append("### Score Breakdown")
    lines.append(f"- Appearance: {note.scores.subscores.appearance}")
    lines.append(f"- Nose: {note.scores.subscores.nose}")
    lines.append(f"- Palate: {note.scores.subscores.palate}")
    lines.append(f"- Structure & Balance: {note.scores.subscores.structure_balance}")
    lines.append(f"- Finish: {note.scores.subscores.finish}")
    lines.append(f"- Typicity & Complexity: {note.scores.subscores.typicity_complexity}")
    lines.append(f"- Overall Judgment: {note.scores.subscores.overall_judgment}")
    lines.append("")
    lines.append(f"**Quality band:** {note.scores.quality_band.value if note.scores.quality_band else 'N/A'}")
    lines.append("")

    # Conclusion
    if note.conclusion:
        lines.append("### Conclusion")
        lines.append(note.conclusion)
        lines.append("")

    return "\n".join(lines)


class ExportService:
    """Service for exporting tasting notes in various formats."""

    def __init__(self, session: Session):
        """
        Initialize the export service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.note_repo = TastingNoteRepository(session)

    def export_note_markdown(self, note_id: UUID | str) -> str | None:
        """
        Export a single tasting note as Markdown with YAML frontmatter.

        Args:
            note_id: The UUID of the note to export.

        Returns:
            Markdown string with YAML frontmatter, or None if not found.
        """
        note = self.note_repo.get_by_id(note_id)
        if note is None:
            return None

        frontmatter = _build_yaml_frontmatter(note)
        body = _build_markdown_body(note)

        return f"{frontmatter}\n\n{body}"

    def export_notes_csv(
        self,
        note_ids: list[UUID | str] | None = None,
        status: str = "published",
    ) -> str:
        """
        Export notes as CSV (flat summary).

        Args:
            note_ids: Optional list of note IDs to export. If None, exports all.
            status: Status filter when note_ids is None.

        Returns:
            CSV string.
        """
        if note_ids:
            notes = [self.note_repo.get_by_id(nid) for nid in note_ids]
            notes = [n for n in notes if n is not None]
        else:
            notes = self.note_repo.list_all(status=status if status != "all" else None)

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        headers = [
            "id",
            "status",
            "producer",
            "cuvee",
            "vintage",
            "country",
            "region",
            "appellation",
            "grapes",
            "color",
            "style",
            "sweetness",
            "alcohol_percent",
            "score_total",
            "quality_band",
            "score_appearance",
            "score_nose",
            "score_palate",
            "score_structure_balance",
            "score_finish",
            "score_typicity_complexity",
            "score_overall_judgment",
            "drink_or_hold",
            "window_start",
            "window_end",
            "tasting_date",
            "price_usd",
            "created_at",
            "updated_at",
        ]
        writer.writerow(headers)

        # Write data rows
        for note in notes:
            row = [
                str(note.id),
                note.status.value,
                note.wine.producer,
                note.wine.cuvee,
                note.wine.vintage or "",
                note.wine.country,
                note.wine.region,
                note.wine.appellation,
                "|".join(note.wine.grapes),
                note.wine.color.value if note.wine.color else "",
                note.wine.style.value if note.wine.style else "",
                note.wine.sweetness.value if note.wine.sweetness else "",
                note.wine.alcohol_percent or "",
                note.scores.total,
                note.scores.quality_band.value if note.scores.quality_band else "",
                note.scores.subscores.appearance,
                note.scores.subscores.nose,
                note.scores.subscores.palate,
                note.scores.subscores.structure_balance,
                note.scores.subscores.finish,
                note.scores.subscores.typicity_complexity,
                note.scores.subscores.overall_judgment,
                note.readiness.drink_or_hold.value,
                note.readiness.window_start_year or "",
                note.readiness.window_end_year or "",
                note.context.tasting_date.isoformat() if note.context.tasting_date else "",
                note.purchase.price_usd or "",
                note.created_at.isoformat(),
                note.updated_at.isoformat(),
            ]
            writer.writerow(row)

        return output.getvalue()

    def export_notes_json(
        self,
        note_ids: list[UUID | str] | None = None,
        status: str = "published",
    ) -> str:
        """
        Export notes as full structured JSON.

        Args:
            note_ids: Optional list of note IDs to export. If None, exports all.
            status: Status filter when note_ids is None.

        Returns:
            JSON string.
        """
        if note_ids:
            notes = [self.note_repo.get_by_id(nid) for nid in note_ids]
            notes = [n for n in notes if n is not None]
        else:
            notes = self.note_repo.list_all(status=status if status != "all" else None)

        # Convert to JSON-serializable format
        notes_data = [note.model_dump(mode="json") for note in notes]

        return json.dumps(
            {
                "export_version": "1.0",
                "export_date": datetime.now().isoformat(),
                "count": len(notes_data),
                "notes": notes_data,
            },
            indent=2,
        )
